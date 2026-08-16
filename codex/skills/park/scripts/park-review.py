#!/usr/bin/env python3
"""Build delta-aware $park review briefs from session receipts."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback uses the final rehash.
    fcntl = None


SEP_RE = re.compile(
    r"^[ \t]*={4,}OPENCAIRN-LOCKED-EDIT-SEP={4,}[ \t]*$", re.MULTILINE
)
JOINED_LIST_RE = re.compile(r"[^\s=`]- \[[ x]\]")
ATTEST_RE = re.compile(r"^ATTEST ([0-9a-fA-F]{64}) (/.+)$", re.MULTILINE)
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_utf8(data: bytes, path: Path) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        die(f"semantic review file is not UTF-8: {path}: {exc}")


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


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


def write_snapshot(root: Path, data: bytes) -> tuple[str, Path]:
    """Persist immutable review bytes under their digest and return both."""
    digest = sha256_bytes(data)
    path = root / "snapshots" / f"{digest}.snapshot"
    if path.exists():
        if path.read_bytes() != data:
            die(f"snapshot digest collision or corruption: {path}")
    else:
        atomic_bytes(path, data)
    return digest, path


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


@contextmanager
def vault_file_locks(paths: list[Path], vault: Path | None):
    """Hold the canonical locked-edit locks through live reconciliation."""
    handles = []
    if vault is None or fcntl is None:
        yield
        return
    targets = sorted({path for path in paths if is_within(path, vault)}, key=str)
    try:
        for target in targets:
            lock_path = target.parent / f".{target.name}.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = lock_path.open("a")
            deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=10)
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        handle.close()
                        raise
                    if dt.datetime.now(dt.timezone.utc) >= deadline:
                        handle.close()
                        die(f"lock timeout after 10s: {target}")
                    time.sleep(0.05)
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


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


def report_terminal_state(report: str) -> str | None:
    """Return one unambiguous terminal state from the review report."""
    states: list[str] = []
    for line in report.splitlines():
        normalised = line.strip()
        normalised = re.sub(r"^#{1,6}\s+", "", normalised)
        normalised = re.sub(r"^[-*]\s+", "", normalised)
        normalised = normalised.replace("**", "").replace("`", "")
        match = re.fullmatch(
            r"terminal state\s*[:\u2014-]\s*(clean|findings|incomplete)[.!]?",
            normalised,
            re.IGNORECASE,
        )
        if match:
            states.append(match.group(1).casefold())
    if len(states) != 1:
        return None
    return states[0]


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
        if receipt.get("ranges_truncated"):
            failures.append(f"truncated changed ranges: {receipt['_receipt_path']}")
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
                "ranges_truncated": receipt.get("ranges_truncated", False),
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


def extract_session_text(text: str, number: int, source: Path) -> tuple[str, dict[str, str]]:
    lines = text.splitlines()
    heading = re.compile(rf"^## Session {number}(?:\s|$)")
    starts = [index for index, line in enumerate(lines) if heading.match(line)]
    if len(starts) != 1:
        die(f"expected one Session {number} heading in {source}; found {len(starts)}")
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


def extract_session(log: Path, number: int) -> tuple[str, dict[str, str]]:
    return extract_session_text(log.read_text(encoding="utf-8"), number, log)


def parse_file_lines(text: str, vault: Path, classifications: dict) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        value = line.strip()
        if not value.startswith("- "):
            continue
        value = value[2:]
        if not value or value.casefold() == "none":
            continue
        if value.startswith("`"):
            end = value.find("`", 1)
            if end < 0 or (value[end + 1 :] and not value[end + 1 :].startswith(" - ")):
                die(f"malformed backticked Files-list path: {line}")
            paths.append(value[1:end])
            continue

        # Descriptions use the same " - " token that ordinary filenames may
        # contain. Prefer the longest prefix that is a real/classified path;
        # first-split truncates names such as "Context - Technical Infrastructure.md".
        split_points = [match.start() for match in re.finditer(r" - ", value)]
        candidates = [value] + [value[:index] for index in reversed(split_points)]
        matched = next(
            (
                candidate
                for candidate in candidates
                if f"external::{candidate}" in classifications
                or str(canonical_path(candidate, vault)) in classifications
                or canonical_path(candidate, vault).exists()
            ),
            None,
        )
        if matched is not None:
            paths.append(matched)
        elif split_points:
            # Backwards-compatible fallback for deleted paths, which no longer
            # exist and may predate explicit classification.
            paths.append(value[: split_points[-1]])
        else:
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


def current_audit_receipts(audit_root: Path) -> list[dict]:
    current: list[dict] = []
    if not audit_root.is_dir():
        return current
    for receipt_path in audit_root.glob("*.json"):
        item = load_json(receipt_path, None)
        if not isinstance(item, dict) or item.get("status") != "clean":
            continue
        files = item.get("files")
        if not isinstance(files, list) or not files:
            continue
        seen: set[Path] = set()
        valid = True
        for file_item in files:
            raw_path = file_item.get("path") if isinstance(file_item, dict) else None
            digest = file_item.get("sha256") if isinstance(file_item, dict) else None
            if (
                not isinstance(raw_path, str)
                or not Path(raw_path).is_absolute()
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
            ):
                valid = False
                break
            path = canonical_path(raw_path)
            if path in seen or not path.is_file() or sha256(path) != digest.casefold():
                valid = False
                break
            seen.add(path)
        if valid:
            copy = dict(item)
            copy["_path"] = str(receipt_path)
            current.append(copy)
    return current


def matching_audit_receipt(
    receipts: list[dict], path: Path, digest: str
) -> dict | None:
    matches = [
        item
        for item in receipts
        if any(
            canonical_path(str(file_item.get("path", ""))) == path
            and str(file_item.get("sha256", "")).casefold() == digest.casefold()
            for file_item in item.get("files", [])
        )
    ]
    return max(matches, key=lambda item: item.get("captured_at", ""), default=None)


def validate_report_attestations(report: str, files: list[dict]) -> None:
    attestations: dict[str, str] = {}
    for match in ATTEST_RE.finditer(report):
        digest, raw_path = match.groups()
        path = str(canonical_path(raw_path))
        if path in attestations:
            die(f"duplicate audit attestation for {path}")
        attestations[path] = digest.casefold()

    expected = {str(canonical_path(item["path"])): item["sha256"].casefold() for item in files}
    missing = sorted(set(expected) - set(attestations))
    unexpected = sorted(set(attestations) - set(expected))
    if missing:
        die("review report lacks paired attestation(s): " + ", ".join(missing))
    if unexpected:
        die("review report contains unexpected attestation(s): " + ", ".join(unexpected))
    for path, digest in expected.items():
        if attestations[path] != digest:
            die(
                f"review report attests wrong SHA-256 for {path}: "
                f"{attestations[path]} (expected {digest})"
            )


def receipt_chain(
    receipts: list[dict], start_digest: str, end_digest: str, after: str
) -> list[dict] | None:
    """Return a post-build locked-edit chain from one exact file hash to another."""
    candidates = [
        item
        for item in receipts
        if item.get("captured_at", "") >= after
        and isinstance(item.get("pre_sha256"), str)
        and isinstance(item.get("post_sha256"), str)
    ]
    by_pre: dict[str, list[dict]] = {}
    for item in candidates:
        by_pre.setdefault(item["pre_sha256"], []).append(item)
    for items in by_pre.values():
        items.sort(key=lambda item: (item.get("captured_at", ""), item.get("_receipt_path", "")))

    def walk(digest: str, seen: set[str]) -> list[dict] | None:
        if digest == end_digest:
            return []
        if digest in seen:
            return None
        for item in by_pre.get(digest, []):
            tail = walk(item["post_sha256"], seen | {digest})
            if tail is not None:
                return [item, *tail]
        return None

    return walk(start_digest, set())


def load_all_locked_receipts(state_root: Path, target: Path) -> list[dict]:
    receipts: list[dict] = []
    for receipt_root in state_root.glob("*.locked-edit-receipts"):
        receipts.extend(load_locked_receipts(receipt_root, target))
    receipts.sort(key=lambda item: (item.get("captured_at", ""), item.get("_receipt_path", "")))
    return receipts


def owned_locators(
    receipts: list[dict], snapshot_digest: str, snapshot_text: str
) -> list[str]:
    """Compatibility wrapper returning the locators from complete evidence."""
    return owned_locator_evidence(receipts, snapshot_digest, snapshot_text)[0]


def owned_locator_evidence(
    receipts: list[dict], snapshot_digest: str, snapshot_text: str
) -> tuple[list[str], bool]:
    """Return surviving current-session payloads and whether coverage is complete."""
    endings = [
        index
        for index, item in enumerate(receipts)
        if item.get("post_sha256") == snapshot_digest
    ]
    if not endings:
        return [], True
    chain: list[dict] = []
    index = endings[-1]
    chain.append(receipts[index])
    wanted = receipts[index].get("pre_sha256")
    for prior in reversed(receipts[:index]):
        if prior.get("post_sha256") == wanted:
            chain.append(prior)
            wanted = prior.get("pre_sha256")
    chain.reverse()
    whole_indexes = [
        chain_index
        for chain_index, item in enumerate(chain)
        if item.get("mode") == "--replace-whole"
    ]
    if whole_indexes:
        # The latest whole replacement supersedes every earlier ownership range;
        # all bytes in the final snapshot are consequently session-owned.
        return ([snapshot_text] if snapshot_text else []), True
    complete = len(chain) == index + 1
    locators: list[str] = []
    for chain_index, item in enumerate(chain):
        mode = item.get("mode")
        if item.get("post_sha256") == item.get("pre_sha256"):
            continue
        if mode not in ("--append", "--replace", "--replace-all"):
            complete = False
            continue
        if item.get("new_text_truncated"):
            complete = False
            continue
        value = item.get("new_text")
        if mode == "--append" and not isinstance(value, str):
            value = append_locator(item, snapshot_text)
        if not isinstance(value, str) or not value:
            complete = False
        elif value in snapshot_text:
            if value not in locators:
                locators.append(value)
        elif not payload_fully_superseded(value, item, chain[chain_index + 1 :]):
            # A later same-session edit may have superseded this payload, but the
            # evidence must account for every introduced occurrence before that
            # can be treated as complete supersession.
            complete = False
    return locators, complete


def payload_fully_superseded(value: str, source: dict, later: list[dict]) -> bool:
    """Prove later exact OLD locators consumed every introduced payload occurrence."""
    introduced = source.get("occurrences") if source.get("mode") == "--replace-all" else 1
    if not isinstance(introduced, int) or introduced < 1:
        introduced = 1
    consumed = 0
    for item in later:
        if item.get("old_text_truncated"):
            continue
        old_text = item.get("old_text")
        if not isinstance(old_text, str) or value not in old_text:
            continue
        operations = item.get("occurrences") if item.get("mode") == "--replace-all" else 1
        if not isinstance(operations, int) or operations < 1:
            operations = 1
        consumed += old_text.count(value) * operations
        if consumed >= introduced:
            return True
    return False


def append_locator(receipt: dict, snapshot_text: str) -> str | None:
    """Recover an append payload from the schema-1 diff receipt."""
    if receipt.get("diff_truncated"):
        return None
    diff = receipt.get("unified_diff")
    if not isinstance(diff, str):
        return None
    added: list[str] = []
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line.startswith("+"):
            added.append(line[1:])
    value = "\n".join(added)
    return value if value and value in snapshot_text else None


def validate_post_snapshot_chain(
    path: Path, chain: list[dict], locators: list[str]
) -> None:
    for item in chain:
        mode = item.get("mode")
        if mode == "--append":
            continue
        if mode not in ("--replace", "--replace-all"):
            die(f"untraceable post-review receipt mode for {path}: {mode}")
        if item.get("old_text_truncated") or item.get("new_text_truncated"):
            die(f"truncated post-review receipt for {path}: {item.get('_receipt_path')}")
        old_text = item.get("old_text")
        new_text = item.get("new_text")
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            die(f"incomplete post-review receipt for {path}: {item.get('_receipt_path')}")
        if any(old_text in locator or locator in old_text for locator in locators):
            die(f"post-review edit overlapped session-owned content: {path}")


def fenced(text: str, language: str = "text") -> str:
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}{language}\n{text.rstrip()}\n{fence}"


def group_full_reads(files: list[dict]) -> list[dict]:
    """Group byte-identical semantic files while retaining every original path."""
    groups: dict[str, dict] = {}
    order: list[str] = []
    for item in files:
        digest = item["sha256"]
        if digest not in groups:
            order.append(digest)
            groups[digest] = {
                "sha256": digest,
                "read_path": item["snapshot_path"],
                "paths": [],
                "reasons": [],
            }
        group = groups[digest]
        group["paths"].append(item["path"])
        reason = item.get("reason", "meaning-bearing change")
        if reason not in group["reasons"]:
            group["reasons"].append(reason)
    return [groups[digest] for digest in order]


def cmd_build(args: argparse.Namespace) -> int:
    sid, root, receipt_root, audit_root = state_paths(args.session_id)
    vault = canonical_path(args.vault)
    log = canonical_path(args.session_log, vault)
    log_snapshot_at = now()
    log_bytes = log.read_bytes()
    log_text = decode_utf8(log_bytes, log)
    block, sections = extract_session_text(log_text, args.number, log)
    manifest_path = root / "files.json"
    classifications = load_json(manifest_path, {})
    if not isinstance(classifications, dict):
        die(f"invalid file manifest: {manifest_path}")
    created_raw = parse_file_lines(
        sections.get("Files Created", ""), vault, classifications
    )
    updated_raw = parse_file_lines(
        sections.get("Files Updated", ""), vault, classifications
    )
    deleted_raw = parse_file_lines(
        sections.get("Files Deleted", ""), vault, classifications
    )

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
    current_audits = current_audit_receipts(audit_root)
    captured_bytes = {log: log_bytes}
    snapshot_times = {log: log_snapshot_at}
    for path in local_paths:
        if not path.is_file():
            die(f"attributed local file is missing: {path}")
        data = captured_bytes.get(path)
        if data is None:
            snapshot_times[path] = now()
            data = path.read_bytes()
        snapshot_at = snapshot_times[path]
        digest = sha256_bytes(data)
        classification = classifications.get(str(path))
        if path in created:
            snapshot_digest, snapshot_path = write_snapshot(root, data)
            full_read.append(
                {
                    "path": str(path),
                    "sha256": snapshot_digest,
                    "snapshot_path": str(snapshot_path),
                    "snapshot_at": snapshot_at,
                    "reason": "created this session",
                    "owned_locators": [decode_utf8(data, path)] if data else [],
                    "owned_locators_complete": True,
                }
            )
            continue
        prior = matching_audit_receipt(current_audits, path, digest)
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
            snapshot_digest, snapshot_path = write_snapshot(root, data)
            snapshot_text = decode_utf8(data, path)
            locators, locators_complete = owned_locator_evidence(
                load_locked_receipts(receipt_root, path), snapshot_digest, snapshot_text
            )
            if path == log and block not in locators:
                locators.append(block)
            full_read.append(
                {
                    "path": str(path),
                    "sha256": snapshot_digest,
                    "snapshot_path": str(snapshot_path),
                    "snapshot_at": snapshot_at,
                    "reason": reason,
                    "owned_locators": locators,
                    "owned_locators_complete": locators_complete,
                }
            )

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

    read_groups = group_full_reads(full_read)
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
        "immutable snapshots, locked-edit receipts, and prior clean audit receipts.",
        "",
        "### Full-read semantic files",
        "",
    ]
    if read_groups:
        for group in read_groups:
            reasons = "; ".join(group["reasons"])
            lines.append(
                f"- Read immutable snapshot once: `{group['read_path']}` — `{group['sha256']}` — {reasons}"
            )
            lines.append("  - Original path(s) covered by this snapshot:")
            for path in group["paths"]:
                lines.append(f"    - `{path}`")
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
            "- Review the embedded Session N block; do not open the live full session log. If its immutable "
            "snapshot is a full-read row, emit only Session N from that snapshot.",
            "- Each `Read immutable snapshot once` row under **Full-read semantic files** is one byte-identity group. "
            "Read only the snapshot path in that row, in its own tool call; do not open the live original. "
            "If it truncates, continue only from its "
            "first unread line. Return the SHA-256 printed by your command.",
            "- Include exactly one machine-readable attestation line for every original path represented "
            "by those groups: `ATTEST <sha256> <absolute-original-path>`. Byte-identical aliases are attested but "
            "not reread. Do not wrap either field in backticks and do not leave trailing whitespace.",
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
            "outputs; coverage gaps; and the required `ATTEST` line for every full-read file. Finish with "
            "exactly one line: `Terminal state: clean`, "
            "`Terminal state: findings`, or `Terminal state: incomplete`.",
        ]
    )

    brief = "\n".join(lines).rstrip() + "\n"
    out = canonical_path(args.out) if args.out else root / "review-brief.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(brief, encoding="utf-8")
    brief_manifest = {
        "schema": 2,
        "built_at": now(),
        "brief": str(out),
        "vault": str(vault),
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
        f"Review modes: full-read {len(full_read)} path(s) in {len(read_groups)} read(s) | mechanical {len(mechanical)} | "
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
    terminal_state = report_terminal_state(report)
    if terminal_state != "clean":
        detail = terminal_state or "missing or ambiguous"
        die(f"audit report terminal state is not clean ({detail})")
    files: list[dict] = []
    built_at = now()
    manifest: dict | None = None
    if args.from_brief:
        manifest = load_json(root / "review-brief-manifest.json", None)
        if not isinstance(manifest, dict):
            die("no review brief manifest; run build first")
        files.extend(manifest.get("full_read", []))
        built_at = manifest.get("built_at", built_at)
        if vault is None and isinstance(manifest.get("vault"), str):
            vault = canonical_path(manifest["vault"])
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
    validate_report_attestations(report, files)
    state_root = root.parent
    reusable: list[dict] = []
    post_review_changes: list[dict] = []
    live_hashes: dict[str, str] = {}
    paths = [canonical_path(item["path"]) for item in files]
    with vault_file_locks(paths, vault):
        for item in files:
            path = canonical_path(item["path"])
            if not path.is_file():
                die(f"audited file missing: {path}")
            snapshot_raw = item.get("snapshot_path")
            if not snapshot_raw:
                current = sha256(path)
                if current != item["sha256"]:
                    die(f"file changed after live review: {path}")
                reusable.append({"path": str(path), "sha256": item["sha256"]})
                live_hashes[str(path)] = current
                continue
            snapshot = Path(snapshot_raw)
            if not snapshot.is_file() or sha256(snapshot) != item["sha256"]:
                die(f"review snapshot missing or corrupt: {snapshot}")
            current = sha256(path)
            if current == item["sha256"]:
                reusable.append({"path": str(path), "sha256": item["sha256"]})
                live_hashes[str(path)] = current
                continue
            chain = receipt_chain(
                load_all_locked_receipts(state_root, path),
                item["sha256"],
                current,
                item.get("snapshot_at", built_at),
            )
            if chain is None:
                die(f"untraceable live change after review snapshot: {path}")
            locators = item.get("owned_locators", [])
            if not item.get("owned_locators_complete", True):
                die(f"incomplete session-owned content evidence: {path}")
            if not locators:
                die(f"cannot prove session-owned content survived live change: {path}")
            validate_post_snapshot_chain(path, chain, locators)
            try:
                live_text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                die(f"changed semantic file is not UTF-8: {path}: {exc}")
            missing = [locator for locator in locators if locator not in live_text]
            if missing:
                die(f"post-review edit overlapped session-owned content: {path}")
            live_hashes[str(path)] = current
            post_review_changes.append(
                {
                    "path": str(path),
                    "snapshot_sha256": item["sha256"],
                    "live_sha256": current,
                    "receipts": [entry["_receipt_path"] for entry in chain],
                }
            )
        receipt = {
            "schema": 2,
            "captured_at": now(),
            "status": "clean",
            "reviewer": args.reviewer,
            "files": reusable,
            "reviewed_files": files,
            "post_review_changes": post_review_changes,
            "report_sha256": hashlib.sha256(report.encode()).hexdigest(),
            "report": report,
        }
        path = audit_root / f"audit-{uuid.uuid4().hex}.json"
        atomic_json(path, receipt)
        changed_after_validation = [
            raw_path
            for raw_path, digest in live_hashes.items()
            if not Path(raw_path).is_file() or sha256(Path(raw_path)) != digest
        ]
        if changed_after_validation:
            receipt["status"] = "invalidated"
            receipt["invalidated_at"] = now()
            receipt["invalidation_reason"] = (
                "live file changed during audit receipt finalisation: "
                + ", ".join(changed_after_validation)
            )
            atomic_json(path, receipt)
            die(receipt["invalidation_reason"])
    print(
        f"Audit receipt: {path} ({len(files)} snapshot-reviewed file(s); "
        f"{len(reusable)} live-reusable)"
    )
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
