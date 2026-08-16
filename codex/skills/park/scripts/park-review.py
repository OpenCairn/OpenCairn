#!/usr/bin/env python3
"""Build delta-aware $park review briefs from session receipts."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid


SEP_RE = re.compile(
    r"^[ \t]*={4,}OPENCAIRN-LOCKED-EDIT-SEP={4,}[ \t]*$", re.MULTILINE
)
JOINED_LIST_RE = re.compile(r"[^\s=`]- \[[ x]\]")
AUDIT_TABLE = """| Seat can reach | Required attestation |
|---|---|
| The filesystem | The list of files it read |
| A shell | For each command-backed claim: the exact command and the quoted output |
| The network | For each fetched-source claim: the URL and the quoted passage |
| Nothing (sources inlined into its prompt) | The source manifest reproduced verbatim, **and** the passages it relied on |"""


def die(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def session_id(explicit: str | None) -> str:
    value = explicit or next(
        (
            os.environ.get(name, "")
            for name in (
                "OPENCAIRN_SESSION_ID",
                "CLAUDE_CODE_SESSION_ID",
                "CODEX_THREAD_ID",
            )
            if os.environ.get(name)
        ),
        "",
    )
    if not value:
        die("no session id; set OPENCAIRN_SESSION_ID or use --session-id")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
        die("session id contains unsupported path characters")
    return value


def state_paths(explicit_sid: str | None) -> tuple[str, Path, Path, Path]:
    sid = session_id(explicit_sid)
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    state = config / ".session-state"
    return (
        sid,
        state / f"{sid}.park-review",
        state / f"{sid}.locked-edit-receipts",
        state / ".park-audit-receipts",
    )


def canonical_path(raw: str, vault: Path | None = None) -> Path:
    expanded = Path(os.path.expanduser(raw))
    if not expanded.is_absolute():
        expanded = (vault if vault is not None else Path.cwd()) / expanded
    return Path(os.path.realpath(expanded))


def load_json(path: Path, fallback: object) -> object:
    if not path.exists():
        return fallback
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        die(f"cannot read {path}: {exc}")


def load_locked_receipts(root: Path, target: Path) -> list[dict]:
    receipts: list[dict] = []
    if not root.is_dir():
        return receipts
    for path in root.iterdir():
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                item = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if canonical_path(str(item.get("target", ""))) != target:
            continue
        item["_receipt_path"] = str(path)
        receipts.append(item)
    receipts.sort(key=lambda item: (item.get("captured_at", ""), item["_receipt_path"]))
    return receipts


def resolve_target(raw: str, vault: Path) -> tuple[Path, str | None]:
    value = raw.strip()
    if value.startswith("[[") and value.endswith("]]" ):
        value = value[2:-2]
    value = value.split("|", 1)[0]
    path_text, marker, anchor = value.partition("#")
    path = canonical_path(path_text, vault)
    if not path.exists() and path.suffix == "":
        md_path = path.with_suffix(".md")
        if md_path.exists():
            path = md_path
    return path, anchor if marker else None


def target_check(raw: str, vault: Path) -> dict:
    path, anchor = resolve_target(raw, vault)
    result = {"requested": raw, "resolved": str(path), "exists": path.exists()}
    if anchor and path.is_file():
        wanted = anchor.replace("%20", " ").strip().casefold()
        headings = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
                if match:
                    headings.append(match.group(1).strip().casefold())
        except OSError:
            headings = []
        result["anchor"] = anchor
        result["anchor_exists"] = wanted in headings
    return result


def lint_errors(text: str) -> list[str]:
    errors: list[str] = []
    match = JOINED_LIST_RE.search(text)
    if match:
        line = text.count("\n", 0, match.start()) + 1
        errors.append(f"joined list item at line {line}")
    blanks = 0
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip():
            blanks = 0
        else:
            blanks += 1
            if blanks == 3:
                errors.append(f"3+ consecutive blank lines at line {number}")
                break
    return errors


def verify_mechanical(
    target: Path,
    vault: Path,
    replacements: list[list[str]],
    targets: list[str],
    receipt_root: Path,
) -> dict:
    failures: list[str] = []
    if not target.is_file():
        return {"ok": False, "failures": [f"file missing: {target}"]}
    receipts = load_locked_receipts(receipt_root, target)
    if not receipts:
        failures.append("no current-session locked-edit receipt for file")

    matched_pairs: set[int] = set()
    previous_post: str | None = None
    receipt_summaries: list[dict] = []
    for receipt in receipts:
        mode = receipt.get("mode")
        if mode not in ("--replace", "--replace-all"):
            failures.append(f"non-locator receipt mode {mode}: {receipt['_receipt_path']}")
            continue
        if receipt.get("old_text_truncated") or receipt.get("new_text_truncated"):
            failures.append(f"truncated replacement payload: {receipt['_receipt_path']}")
            continue
        old_text = receipt.get("old_text")
        new_text = receipt.get("new_text")
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            failures.append(f"receipt lacks exact OLD/NEW payload: {receipt['_receipt_path']}")
            continue
        transformed = old_text
        used_here: list[int] = []
        for index, pair in enumerate(replacements):
            old, new = pair
            if old in transformed:
                transformed = transformed.replace(old, new)
                used_here.append(index)
        if transformed != new_text:
            failures.append(
                f"receipt contains an undeclared or non-mechanical delta: {receipt['_receipt_path']}"
            )
        else:
            matched_pairs.update(used_here)
        if previous_post is not None and receipt.get("pre_sha256") != previous_post:
            failures.append(
                f"receipt hash chain is discontinuous before {receipt['_receipt_path']}"
            )
        previous_post = receipt.get("post_sha256")
        receipt_summaries.append(
            {
                "path": receipt["_receipt_path"],
                "mode": mode,
                "pre_sha256": receipt.get("pre_sha256"),
                "post_sha256": receipt.get("post_sha256"),
                "changed_ranges": receipt.get("changed_ranges", []),
                "unified_diff": receipt.get("unified_diff", ""),
                "diff_truncated": receipt.get("diff_truncated", False),
            }
        )

    missing_pairs = [
        f"{old!r} -> {new!r}"
        for index, (old, new) in enumerate(replacements)
        if index not in matched_pairs
    ]
    if missing_pairs:
        failures.append("replacement absent from exact receipts: " + "; ".join(missing_pairs))

    current_hash = sha256(target)
    if receipts and previous_post != current_hash:
        failures.append("current file hash does not match the final locked-edit receipt")

    text = target.read_text(encoding="utf-8")
    replacement_checks: list[dict] = []
    for old, new in replacements:
        old_count = text.count(old)
        new_count = text.count(new)
        if old_count:
            failures.append(f"old locator still present {old_count} time(s): {old!r}")
        if not new_count:
            failures.append(f"new locator absent: {new!r}")
        replacement_checks.append(
            {"old": old, "new": new, "old_count": old_count, "new_count": new_count}
        )

    resolved_targets = [target_check(item, vault) for item in targets]
    for item in resolved_targets:
        if not item["exists"]:
            failures.append(f"replacement target missing: {item['resolved']}")
        if item.get("anchor") and not item.get("anchor_exists"):
            failures.append(
                f"replacement target anchor missing: {item['resolved']}#{item['anchor']}"
            )

    if SEP_RE.search(text):
        failures.append("stranded locked-edit separator line")
    failures.extend(lint_errors(text))
    return {
        "ok": not failures,
        "failures": failures,
        "current_sha256": current_hash,
        "replacements": replacement_checks,
        "targets": resolved_targets,
        "separator_clean": not SEP_RE.search(text),
        "lint_clean": not lint_errors(text),
        "receipts": receipt_summaries,
    }


def cmd_classify(args: argparse.Namespace) -> int:
    _, root, receipt_root, _ = state_paths(args.session_id)
    vault = canonical_path(args.vault)
    manifest_path = root / "files.json"
    manifest = load_json(manifest_path, {})
    if not isinstance(manifest, dict):
        die(f"invalid file manifest: {manifest_path}")
    if args.non_local:
        manifest[f"external::{args.path}"] = {
            "mode": "nonlocal",
            "reason": args.reason or "non-local artefact represented by evidence",
            "classified_at": now(),
        }
        atomic_json(manifest_path, manifest)
        print(f"NONLOCAL {args.path}")
        return 0
    path = canonical_path(args.path, vault)
    if args.semantic:
        if not path.is_file():
            die(f"semantic file missing: {path}")
        manifest[str(path)] = {
            "mode": "semantic",
            "reason": args.reason or "meaning-bearing change",
            "classified_at": now(),
            "sha256_at_classification": sha256(path),
        }
        atomic_json(manifest_path, manifest)
        print(f"SEMANTIC {path}")
        return 0

    if not args.replace:
        die("--mechanical requires at least one --replace OLD NEW pair")
    if not args.target:
        die("--mechanical requires at least one --target")
    result = verify_mechanical(path, vault, args.replace, args.target, receipt_root)
    if not result["ok"]:
        for failure in result["failures"]:
            print(f"FAIL mechanical: {failure}", file=sys.stderr)
        return 1
    manifest[str(path)] = {
        "mode": "mechanical",
        "classified_at": now(),
        "replacements": args.replace,
        "targets": args.target,
        "verification": result,
    }
    atomic_json(manifest_path, manifest)
    print(
        f"PASS mechanical: {path} ({len(args.replace)} replacement(s), "
        f"{len(result['receipts'])} receipt(s))"
    )
    return 0


def capture_record(
    root: Path,
    *,
    kind: str,
    label: str,
    text: str,
    source: str | None,
    provenance: str | None,
    returncode: int | None = None,
) -> Path:
    if not text.strip():
        die(f"refusing empty {kind} receipt")
    record = {
        "schema": 1,
        "captured_at": now(),
        "kind": kind,
        "label": label,
        "source": source,
        "provenance": provenance,
        "text": text,
    }
    if returncode is not None:
        record["returncode"] = returncode
    path = root / "captures" / f"{kind}-{uuid.uuid4().hex}.json"
    atomic_json(path, record)
    return path


def cmd_capture(args: argparse.Namespace) -> int:
    _, root, _, _ = state_paths(args.session_id)
    if args.kind == "evidence" and (not args.source or not args.provenance):
        die("evidence receipts require --source and --provenance")
    text = sys.stdin.read()
    path = capture_record(
        root,
        kind=args.kind,
        label=args.label,
        text=text,
        source=args.source,
        provenance=args.provenance,
    )
    print(f"Receipt: {path}")
    return 0


def cmd_run_verifier(args: argparse.Namespace) -> int:
    _, root, _, _ = state_paths(args.session_id)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        die("run-verifier requires a command after --")
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    combined = completed.stdout
    if completed.stderr:
        combined += "\n[stderr]\n" + completed.stderr
    path = capture_record(
        root,
        kind="verifier",
        label=args.label,
        text=combined,
        source=" ".join(command),
        provenance="primary",
        returncode=completed.returncode,
    )
    print(f"Verifier receipt: {path}", file=sys.stderr)
    return completed.returncode


def extract_session(log: Path, number: int) -> tuple[str, dict[str, str]]:
    lines = log.read_text(encoding="utf-8").splitlines()
    heading = re.compile(rf"^## Session {number}(?:\s|$)")
    starts = [index for index, line in enumerate(lines) if heading.match(line)]
    if len(starts) != 1:
        die(f"expected one Session {number} heading in {log}; found {len(starts)}")
    start = starts[0]
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("## Session ")),
        len(lines),
    )
    block_lines = lines[start:end]
    sections: dict[str, str] = {}
    current: str | None = None
    collected: list[str] = []
    for line in block_lines[1:]:
        if line.startswith("### "):
            if current is not None:
                sections[current] = "\n".join(collected).strip()
            current = line[4:].strip()
            collected = []
        elif current is not None:
            collected.append(line)
    if current is not None:
        sections[current] = "\n".join(collected).strip()
    return "\n".join(block_lines), sections


def parse_file_lines(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        value = line.strip()
        if not value.startswith("- "):
            continue
        value = value[2:]
        if " - " in value:
            value = value.split(" - ", 1)[0]
        if value and value.casefold() != "none":
            paths.append(value)
    return paths


def load_captures(root: Path) -> list[dict]:
    records: list[dict] = []
    capture_dir = root / "captures"
    if not capture_dir.is_dir():
        return records
    for path in capture_dir.glob("*.json"):
        item = load_json(path, None)
        if isinstance(item, dict):
            item["_path"] = str(path)
            records.append(item)
    records.sort(key=lambda item: item.get("captured_at", ""))
    return records


def matching_audit_receipt(audit_root: Path, path: Path, digest: str) -> dict | None:
    matches: list[dict] = []
    if not audit_root.is_dir():
        return None
    for receipt_path in audit_root.glob("*.json"):
        item = load_json(receipt_path, None)
        if not isinstance(item, dict) or item.get("status") != "clean":
            continue
        for file_item in item.get("files", []):
            if (
                canonical_path(str(file_item.get("path", ""))) == path
                and file_item.get("sha256") == digest
            ):
                copy = dict(item)
                copy["_path"] = str(receipt_path)
                matches.append(copy)
                break
    return max(matches, key=lambda item: item.get("captured_at", ""), default=None)


def fenced(text: str, language: str = "text") -> str:
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}{language}\n{text.rstrip()}\n{fence}"


def cmd_build(args: argparse.Namespace) -> int:
    sid, root, receipt_root, audit_root = state_paths(args.session_id)
    vault = canonical_path(args.vault)
    log = canonical_path(args.session_log, vault)
    block, sections = extract_session(log, args.number)
    created_raw = parse_file_lines(sections.get("Files Created", ""))
    updated_raw = parse_file_lines(sections.get("Files Updated", ""))
    deleted_raw = parse_file_lines(sections.get("Files Deleted", ""))
    manifest_path = root / "files.json"
    classifications = load_json(manifest_path, {})
    if not isinstance(classifications, dict):
        die(f"invalid file manifest: {manifest_path}")

    created = {canonical_path(path, vault) for path in created_raw}
    local_paths: list[Path] = []
    external_files: list[dict] = []
    seen: set[Path] = set()
    for raw in created_raw + updated_raw:
        external = classifications.get(f"external::{raw}")
        if isinstance(external, dict) and external.get("mode") == "nonlocal":
            external_files.append(
                {"path": raw, "reason": external.get("reason", "non-local artefact")}
            )
            continue
        path = canonical_path(raw, vault)
        if path not in seen:
            seen.add(path)
            local_paths.append(path)

    full_read: list[dict] = []
    mechanical: list[dict] = []
    reused: list[dict] = []
    warnings: list[str] = []
    for path in local_paths:
        if not path.is_file():
            die(f"attributed local file is missing: {path}")
        digest = sha256(path)
        classification = classifications.get(str(path))
        if path in created:
            full_read.append(
                {"path": str(path), "sha256": digest, "reason": "created this session"}
            )
            continue
        prior = matching_audit_receipt(audit_root, path, digest)
        if prior:
            reused.append(
                {
                    "path": str(path),
                    "sha256": digest,
                    "receipt": prior["_path"],
                    "reviewer": prior.get("reviewer", "unknown"),
                    "captured_at": prior.get("captured_at", "unknown"),
                }
            )
            continue
        if isinstance(classification, dict) and classification.get("mode") == "mechanical":
            verification = verify_mechanical(
                path,
                vault,
                classification.get("replacements", []),
                classification.get("targets", []),
                receipt_root,
            )
            if not verification["ok"]:
                die(
                    f"mechanical verification is stale for {path}: "
                    + "; ".join(verification["failures"])
                )
            mechanical.append(
                {"path": str(path), "sha256": digest, "verification": verification}
            )
        else:
            reason = "meaning-bearing or conservatively unclassified change"
            if isinstance(classification, dict):
                reason = classification.get("reason", reason)
            else:
                warnings.append(f"defaulted unclassified file to semantic: {path}")
            full_read.append({"path": str(path), "sha256": digest, "reason": reason})

    captures = load_captures(root)
    evidence = [item for item in captures if item.get("kind") == "evidence"]
    prestate = [item for item in captures if item.get("kind") == "prestate"]
    propagation_items = [item for item in captures if item.get("kind") == "propagation"]
    verifier_items = [item for item in captures if item.get("kind") == "verifier"]
    if not propagation_items:
        die("no propagation receipt; capture the agent report or the checked nil result")
    if not verifier_items:
        die("no verifier receipt; run park-verify through run-verifier")
    propagation = propagation_items[-1]
    verifier = verifier_items[-1]
    if verifier.get("returncode") not in (None, 0):
        die("latest verifier receipt records a failing exit status")

    sources: dict[str, dict] = {}
    for item in evidence:
        source = item.get("source")
        provenance = item.get("provenance")
        if not source or provenance not in ("primary", "secondary", "unverified"):
            die(f"malformed evidence receipt: {item.get('_path', 'unknown')}")
        sources[source] = item

    ledger_path = (
        Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
        / ".session-state"
        / f"{sid}.tsv"
    )
    ledger = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else "NOTE: no ledger"

    lines = [
        "# Park close-out review brief",
        "",
        "## Session",
        "",
        f"- Resolved vault: `{vault}`",
        f"- Session log: `{log}`",
        f"- Session number: {args.number}",
        "",
        "## Session N block (attribution boundary)",
        "",
        fenced(block, "markdown"),
        "",
        "## Review modes",
        "",
        "The modes below are mechanically derived from the post-backfill Files lists, "
        "current hashes, locked-edit receipts, and prior clean audit receipts.",
        "",
        "### Full-read semantic files",
        "",
    ]
    if full_read:
        for item in full_read:
            lines.append(f"- `{item['path']}` — `{item['sha256']}` — {item['reason']}")
    else:
        lines.append("None")

    lines.extend(["", "### Reused clean audit receipts — do not reread", ""])
    if reused:
        for item in reused:
            lines.append(
                f"- `{item['path']}` — current SHA-256 `{item['sha256']}` matches "
                f"`{item['receipt']}` ({item['reviewer']}, {item['captured_at']})"
            )
    else:
        lines.append("None")

    lines.extend(["", "### Non-local artefacts — assess only through embedded evidence", ""])
    if external_files:
        for item in external_files:
            lines.append(f"- `{item['path']}` — {item['reason']}")
    else:
        lines.append("None")

    lines.extend(["", "### Mechanical-only files — inspect receipts and changed spans; do not full-read", ""])
    if not mechanical:
        lines.append("None")
    for item in mechanical:
        verification = item["verification"]
        lines.extend(
            [
                f"#### `{item['path']}`",
                "",
                f"Current SHA-256: `{item['sha256']}`",
                "",
                "Replacement checks:",
                "",
            ]
        )
        for check in verification["replacements"]:
            lines.append(
                f"- `{check['old']}` → `{check['new']}`; old count {check['old_count']}; "
                f"new count {check['new_count']}"
            )
        lines.extend(["", "Target checks:", ""])
        for check in verification["targets"]:
            anchor = ""
            if check.get("anchor"):
                anchor = f"; anchor exists={check.get('anchor_exists', False)}"
            lines.append(
                f"- `{check['requested']}` → `{check['resolved']}`; exists={check['exists']}{anchor}"
            )
        lines.extend(
            [
                "",
                f"Separator clean: {verification['separator_clean']}; lint clean: {verification['lint_clean']}",
                "",
                "Locked-edit receipts and changed spans:",
                "",
            ]
        )
        for receipt in verification["receipts"]:
            lines.append(
                f"- `{receipt['path']}` — `{receipt['pre_sha256']}` → `{receipt['post_sha256']}`; "
                f"ranges `{json.dumps(receipt['changed_ranges'], separators=(',', ':'))}`"
            )
            lines.extend(["", fenced(receipt["unified_diff"], "diff"), ""])

    lines.extend(["", "## Relevant pre-state receipts", ""])
    if prestate:
        for item in prestate:
            lines.extend(
                [
                    f"### {item['label']} — `{item.get('source') or 'session read'}`",
                    "",
                    fenced(item["text"]),
                    "",
                ]
            )
    else:
        lines.append("None recorded.")

    lines.extend(
        [
            "",
            "## Out-of-band evidence (treat as given — do NOT flag as fabricated)",
            "",
            "These excerpts were genuinely gathered. Their content remains open to challenge; "
            "secondary and unverified material especially so.",
            "",
        ]
    )
    if sources:
        for source, item in sources.items():
            lines.extend(
                [
                    f"### [{item['provenance']}] {item['label']} — `{source}`",
                    "",
                    fenced(item["text"]),
                    "",
                ]
            )
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Session write ledger",
            "",
            fenced(ledger, "tsv"),
            "",
            "## Reference-graph propagation result",
            "",
            fenced(propagation["text"]),
            "",
            "## Mechanical verifier result",
            "",
            fenced(verifier["text"]),
            "",
            "## One-pass checklist",
            "",
            "- Layer 1 — Does the approach serve the stated outcome?",
            "- Layer 2 — Do operating assumptions agree with the embedded evidence?",
            "- Layer 3 — Do the session summary, pending/completed state and listed files agree in both directions?",
            "- Layer 4 — Is the changed content internally correct?",
            "- Layer 5 — Are claimed results supported and future checks falsifiable?",
            "- Layer 0 is out of scope because the park frame is fixed.",
            "",
            "## Scope and method",
            "",
            "- Review the embedded Session N block; do not open the full session log.",
            "- Read every file under **Full-read semantic files** exactly once, each in its own tool call. "
            "If one truncates, continue only from its first unread line. Return the SHA-256 printed by "
            "your command beside every full-read file.",
            "- Do not reread files backed by a matching clean audit receipt.",
            "- For mechanical-only files, review only the embedded locked-edit receipts, exact checks, "
            "and changed spans. Do not open or full-read those files.",
            "- Treat non-local paths only through embedded evidence. Use the propagation report for "
            "reference-graph coverage; do not repeat vault-wide searches.",
            "- Make no edits. Use no web, network, SSH, remote hosts, sub-agents, skill maintenance, "
            "or adjacent cleanup. Run one bounded review pass.",
            "- Return only material findings introduced by this session. Omit style nits and speculative improvements.",
            "",
            "## Required evidence attestation",
            "",
            AUDIT_TABLE,
            "",
            "List the files read. For every command-backed claim, give the exact command and quote its output. "
            "State explicitly that no network was used.",
            "",
            "## Output",
            "",
            "Return: scope and coverage; findings tagged Layer 1–5 with exact file/line evidence and a "
            "concrete fix, or one evidence-bearing clean line; files read with SHA-256; commands and quoted "
            "outputs; coverage gaps; terminal state `clean`, `findings`, or `incomplete`.",
        ]
    )

    brief = "\n".join(lines).rstrip() + "\n"
    out = canonical_path(args.out) if args.out else root / "review-brief.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(brief, encoding="utf-8")
    brief_manifest = {
        "schema": 1,
        "built_at": now(),
        "brief": str(out),
        "session_log": str(log),
        "session_number": args.number,
        "full_read": full_read,
        "mechanical": [{"path": item["path"], "sha256": item["sha256"]} for item in mechanical],
        "reused": reused,
        "external": external_files,
        "deleted": deleted_raw,
    }
    atomic_json(root / "review-brief-manifest.json", brief_manifest)
    print(f"Reviewer brief: {out}")
    print(
        f"Out-of-band evidence: sources drawn on {len(sources)} → excerpts embedded {len(sources)}"
    )
    print(
        f"Review modes: full-read {len(full_read)} | mechanical {len(mechanical)} | "
        f"receipt-reuse {len(reused)} | non-local {len(external_files)} | deleted {len(deleted_raw)}"
    )
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    return 0


def cmd_record_audit(args: argparse.Namespace) -> int:
    _, root, _, audit_root = state_paths(args.session_id)
    vault = canonical_path(args.vault) if args.vault else None
    report = sys.stdin.read()
    if not report.strip():
        die("audit receipt requires the review report on stdin")
    if not re.search(r"\bclean\b", report, re.IGNORECASE):
        die("audit report does not contain a clean terminal state")
    files: list[dict] = []
    if args.from_brief:
        manifest = load_json(root / "review-brief-manifest.json", None)
        if not isinstance(manifest, dict):
            die("no review brief manifest; run build first")
        files.extend(manifest.get("full_read", []))
    for raw in args.file or []:
        path = canonical_path(raw, vault)
        if not path.is_file():
            die(f"audited file missing: {path}")
        files.append({"path": str(path), "sha256": sha256(path)})
    dedup: dict[str, dict] = {item["path"]: item for item in files}
    files = list(dedup.values())
    if not files:
        print("No full-read files; no audit receipt written")
        return 0
    for item in files:
        path = Path(item["path"])
        current = sha256(path)
        if current != item["sha256"]:
            die(f"file changed after review brief: {path}")
        if current.casefold() not in report.casefold():
            die(f"review report does not attest current SHA-256 for {path}: {current}")
    receipt = {
        "schema": 1,
        "captured_at": now(),
        "status": "clean",
        "reviewer": args.reviewer,
        "files": files,
        "report_sha256": hashlib.sha256(report.encode()).hexdigest(),
        "report": report,
    }
    path = audit_root / f"audit-{uuid.uuid4().hex}.json"
    atomic_json(path, receipt)
    print(f"Audit receipt: {path} ({len(files)} full-read file(s))")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", help="override harness session id")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    classify = subparsers.add_parser("classify", help="classify and verify a touched file")
    classify.add_argument("--vault", required=True)
    classify.add_argument("--path", required=True)
    mode = classify.add_mutually_exclusive_group(required=True)
    mode.add_argument("--semantic", action="store_true")
    mode.add_argument("--mechanical", action="store_true")
    mode.add_argument("--nonlocal", dest="non_local", action="store_true")
    classify.add_argument("--reason")
    classify.add_argument("--replace", nargs=2, action="append", metavar=("OLD", "NEW"))
    classify.add_argument("--target", action="append")
    classify.set_defaults(func=cmd_classify)

    capture = subparsers.add_parser("capture", help="capture review evidence immediately")
    capture.add_argument(
        "--kind", required=True, choices=("evidence", "prestate", "propagation")
    )
    capture.add_argument("--label", required=True)
    capture.add_argument("--source")
    capture.add_argument(
        "--provenance", choices=("primary", "secondary", "unverified")
    )
    capture.set_defaults(func=cmd_capture)

    run_verifier = subparsers.add_parser(
        "run-verifier", help="run and capture park-verify without losing its exit status"
    )
    run_verifier.add_argument("--label", default="park-verify")
    run_verifier.add_argument("command", nargs=argparse.REMAINDER)
    run_verifier.set_defaults(func=cmd_run_verifier)

    build = subparsers.add_parser("build", help="generate the bounded reviewer brief")
    build.add_argument("--vault", required=True)
    build.add_argument("--session-log", required=True)
    build.add_argument("--number", required=True, type=int)
    build.add_argument("--out")
    build.set_defaults(func=cmd_build)

    audit = subparsers.add_parser(
        "record-audit", help="cache a clean full-read audit against exact hashes"
    )
    audit.add_argument("--reviewer", required=True)
    audit.add_argument("--vault")
    audit.add_argument("--from-brief", action="store_true")
    audit.add_argument("--file", action="append")
    audit.set_defaults(func=cmd_record_audit)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
