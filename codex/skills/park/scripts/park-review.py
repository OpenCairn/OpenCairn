#!/usr/bin/env python3
"""Build delta-aware $park review briefs from session receipts."""

from __future__ import annotations

import argparse
import codecs
from contextlib import contextmanager
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
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
COMPLETE_RE = re.compile(r"^COMPLETE ([0-9a-fA-F]{64})$", re.MULTILINE)
REMOTE_PATH_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
# "(deleted)" / "(remote)" after a Files-row path, outside any backticks: the
# row names something not on this host's disk, or not to be read from it.
# Mirrors park-verify.sh's ANNOTATION handling.
# The annotation sits immediately before the " - " description separator or
# at the end of the row; the same word inside a description is not one.
ANNOTATION_RE = re.compile(r"\s*\((deleted|remote)\)(?= - |$)", re.IGNORECASE)
# Media types whose full-read review copy is text read by line range.
TEXT_REVIEW_MEDIA_TYPES = ("text/plain", "application/pdf")
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


def count_lines(path: Path) -> int:
    """Count readable lines, including a final line without a newline."""
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def is_binary_artifact(data: bytes) -> bool:
    """Recognise binary containers that may still decode as UTF-8."""
    return (
        data.startswith(b"%PDF-")
        or data.startswith(b"\x89PNG\r\n\x1a\n")
        or b"\x00" in data[:8192]
    )


def needs_binary_review(data: bytes) -> bool:
    """True for non-PDF bytes that cannot be reviewed as text by line range."""
    return not data.startswith(b"%PDF-") and (is_binary_artifact(data) or not is_utf8(data))


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


def write_file_snapshot(root: Path, source: Path, category: str = "snapshots") -> tuple[str, Path]:
    """Copy/hash a potentially large file without allocating it as one object."""
    directory = root / category
    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".capture-", dir=directory)
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as input_file:
            for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
                digest.update(chunk)
                output.write(chunk)
        value = digest.hexdigest()
        if sha256(source) != value:
            die(f"source changed while capturing: {source}")
        path = directory / f"{value}.snapshot"
        if path.exists():
            if sha256(path) != value:
                die(f"snapshot digest collision or corruption: {path}")
        else:
            os.replace(temporary, path)
        return value, path
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def raw_output_receipt(root: Path, source: Path) -> dict:
    digest, snapshot = write_file_snapshot(root, source, "raw")
    records = 0
    prefix = b""
    ongoing = False
    per_file: dict[bytes, int] = {}
    unparsed = 0

    def finish() -> None:
        nonlocal records, prefix, ongoing, unparsed
        records += 1
        # rg --null -n gives an unambiguous filename. Colon output is retained
        # too, but its diagnostic count is labelled rather than assumed exact.
        if b"\0" in prefix:
            name, tail = prefix.split(b"\0", 1)
            if not re.match(rb"^[0-9]+:", tail):
                name = b""
        else:
            match = re.match(rb"^(.+?):[0-9]+:", prefix)
            name = match.group(1) if match else b""
        if name:
            per_file[name] = per_file.get(name, 0) + 1
        else:
            unparsed += 1
        prefix, ongoing = b"", False

    with snapshot.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            pieces = chunk.split(b"\n")
            for index, piece in enumerate(pieces):
                if piece:
                    ongoing = True
                    prefix += piece[:max(0, 8192 - len(prefix))]
                if index < len(pieces) - 1:
                    finish()
    if ongoing:
        finish()
    counts = []
    for name, total in sorted(per_file.items()):
        try:
            display = name.decode("utf-8")
        except UnicodeDecodeError:
            display = None
        counts.append({"path": display, "path_bytes_hex": name.hex(), "records": total})
    return {"path": str(snapshot), "sha256": digest, "bytes": snapshot.stat().st_size,
            "lf_records": records, "per_file_counts": counts,
            "unparsed_records": unparsed,
            "count_format": "LF records; rg --null -n filenames without LF exact; colon prefix diagnostic"}


def file_is_utf8(path: Path) -> bool:
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                decoder.decode(chunk)
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True


def artifact_helper(vault: Path) -> Path:
    candidates = []
    override = os.environ.get("OPENCAIRN_PARK_ARTIFACT_HELPER")
    if override:
        candidates.append(Path(override).expanduser())
    candidates.extend(
        [
            vault / ".claude/scripts/park-artifact.py",
            Path(__file__).resolve().parents[4] / ".claude/scripts/park-artifact.py",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    die("park-artifact.py is required for local reference and PDF artefacts")


def prepare_artifact(root: Path, vault: Path, source: Path, original: Path) -> dict:
    helper = artifact_helper(vault)
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    shared_state = config / ".session-state" / ".park-artifacts"
    result = subprocess.run(
        [
            sys.executable,
            str(helper),
            "--source",
            str(source),
            "--original",
            str(original),
            "--state-dir",
            str(shared_state),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        die(f"cannot prepare local artefact {original}: {detail}")
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        die(f"invalid park-artifact receipt for {original}: {exc}")
    if not isinstance(receipt, dict):
        die(f"invalid park-artifact receipt for {original}")
    return receipt


def forward_link_proof(vault: Path, path: Path, sid: str) -> dict | None:
    candidates = [vault / '.claude/scripts/add-forward-link.sh',
        Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home() / '.claude')) / 'scripts/add-forward-link.sh',
        Path(__file__).resolve().parents[4] / '.claude/scripts/add-forward-link.sh']
    helper = next((p for p in candidates if p.is_file()), None)
    if helper is None:
        return None
    run = subprocess.run(['bash', str(helper), '--find-proof', str(path), sid],
                         text=True, capture_output=True, check=False)
    if run.returncode:
        return None
    try:
        return json.loads(run.stdout)
    except ValueError:
        return None


def semantic_review_copy(
    root: Path, vault: Path, source: Path, data: bytes | None, classification: dict | None
) -> tuple[str, Path, Path, str, str, str]:
    """Return immutable source/review paths for a session-authored semantic file."""
    if data is None:
        digest = sha256(source)
        receipt = validated_artifact_receipt(source, digest, classification or {})
        source_snapshot = Path(receipt["source_snapshot"])
        media_type = receipt.get("media_type") or "application/octet-stream"
        if media_type not in TEXT_REVIEW_MEDIA_TYPES:
            return digest, source_snapshot, source_snapshot, digest, "", media_type
        data = source_snapshot.read_bytes()
    digest, snapshot_path = write_snapshot(root, data)
    binary = needs_binary_review(data)
    if not binary and not data.startswith(b"%PDF-"):
        review_text = decode_utf8(data, source)
        return digest, snapshot_path, snapshot_path, digest, review_text, "text/plain"
    receipt = classification.get("artifact") if isinstance(classification, dict) else None
    if not isinstance(receipt, dict) or receipt.get("source_sha256") != digest:
        receipt = prepare_artifact(root, vault, snapshot_path, source)
    if binary:
        # No text copy exists: the reviewer inspects the immutable source bytes
        # with a tool for the media type, and there is no text locator to own.
        source_snapshot = Path(str(receipt.get("source_snapshot", "")))
        if not source_snapshot.is_file() or sha256(source_snapshot) != digest:
            die(f"artefact source snapshot missing or corrupt: {source_snapshot}")
        media_type = receipt.get("media_type")
        if not isinstance(media_type, str) or media_type in TEXT_REVIEW_MEDIA_TYPES:
            media_type = "application/octet-stream"
        return digest, source_snapshot, source_snapshot, digest, "", media_type
    if receipt.get("text_status") != "available":
        die(
            f"semantic PDF has no extractable text: {source}; use format-specific authored-output "
            "review or classify an imported source as --reference"
        )
    review_path = Path(str(receipt["review_path"]))
    review_digest = str(receipt["review_sha256"])
    if not review_path.is_file() or sha256(review_path) != review_digest:
        die(f"semantic PDF review copy missing or corrupt: {review_path}")
    review_text = decode_utf8(review_path.read_bytes(), review_path)
    return (
        digest,
        Path(str(receipt["source_snapshot"])),
        review_path,
        review_digest,
        review_text,
        "application/pdf",
    )


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
    root = state / f"{sid}.park-review"
    active = load_json(root / "active-run.json", None)
    if active is not None:
        generation = active.get("generation") if isinstance(active, dict) else None
        if not isinstance(generation, str) or not re.fullmatch(r"[a-f0-9]{32}", generation):
            die("invalid active park generation; use begin-run")
        root = root / "runs" / generation
        if not (root / "run.json").is_file():
            die("active park generation is missing; use begin-run")
    return (
        sid,
        root,
        state / f"{sid}.locked-edit-receipts",
        state / ".park-audit-receipts",
    )


def cmd_begin_run(args: argparse.Namespace) -> int:
    """Start a new park, retaining earlier generations and clean audit receipts."""
    sid = session_id(args.session_id)
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    base = config / ".session-state" / f"{sid}.park-review"
    generation = uuid.uuid4().hex
    root = base / "runs" / generation
    record = {"schema": 1, "session_id": sid, "generation": generation,
              "started_at": now(), "root": str(root), "completion_protocol": 1}
    atomic_json(root / "run.json", record)
    atomic_json(base / "active-run.json", record)
    print(json.dumps(record))
    return 0


def canonical_path(raw: str, vault: Path | None = None) -> Path:
    expanded = Path(os.path.expanduser(raw))
    if not expanded.is_absolute():
        expanded = (vault if vault is not None else Path.cwd()) / expanded
    return Path(os.path.realpath(expanded))


def lexical_path(raw: str, vault: Path | None = None) -> Path:
    """Normalise a spelling without discarding an installed symlink's identity."""
    expanded = Path(os.path.expanduser(raw))
    if not expanded.is_absolute():
        expanded = (vault if vault is not None else Path.cwd()) / expanded
    return Path(os.path.abspath(expanded))


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
        item["_receipt_root"] = str(root.resolve())
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
    for match in JOINED_LIST_RE.finditer(text):
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
    return errors


def report_terminal_state(report: str) -> str | None:
    """Return one unambiguous terminal state from the review report.

    The report's final line must be exactly `Terminal state: <state>`, the form
    the brief requires and completion retention/lookup read with
    `report.rstrip().endswith(...)`; decorated variants are detected only so a
    second terminal-state line makes the report ambiguous.
    """
    final = re.fullmatch(r"Terminal state: (clean|findings|incomplete)",
                         report.rstrip().rsplit("\n", 1)[-1])
    if not final:
        return None
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
    return final.group(1)


def verify_mechanical(
    target: Path,
    vault: Path,
    replacements: list[list[str]],
    targets: list[str],
    receipt_root: Path,
    allow_inherited_lint: bool = False,
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
                # Each producer receipt describes one actual transition. A later
                # declared transition may consume this NEW in another receipt.
                if transformed == new_text:
                    break
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
        if allow_inherited_lint:
            lint_proof = receipt_lint_proof(receipt)
            if lint_proof == "missing":
                failures.append(
                    f"receipt lacks pre/post lint fingerprints: {receipt['_receipt_path']}"
                )
            elif lint_proof == "introduced":
                failures.append(
                    f"mechanical edit introduced lint: {receipt['_receipt_path']}"
                )
        receipt_summaries.append(
            {
                "path": receipt["_receipt_path"],
                "mode": mode,
                "pre_sha256": receipt.get("pre_sha256"),
                "post_sha256": receipt.get("post_sha256"),
                "pre_lint": receipt.get("pre_lint"),
                "post_lint": receipt.get("post_lint"),
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
    for index, (old, new) in enumerate(replacements):
        old_count = text.count(old)
        new_count = text.count(new)
        terminal = new
        for later_old, later_new in replacements[index + 1:]:
            if terminal == later_old:
                terminal = later_new
        terminal_count = text.count(terminal)
        if old_count:
            failures.append(f"old locator still present {old_count} time(s): {old!r}")
        if not terminal_count:
            failures.append(f"new locator absent: {terminal!r}")
        replacement_checks.append(
            {"old": old, "new": new, "old_count": old_count, "new_count": new_count,
             "effective_new": terminal, "effective_new_count": terminal_count}
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
    lint = lint_errors(text)
    if not allow_inherited_lint:
        failures.extend(lint)
    return {
        "ok": not failures,
        "failures": failures,
        "current_sha256": current_hash,
        "replacements": replacement_checks,
        "targets": resolved_targets,
        "separator_clean": not SEP_RE.search(text),
        "lint_clean": not lint,
        "accepted_inherited_lint": lint if allow_inherited_lint else [],
        "receipts": receipt_summaries,
    }


def receipt_lint_proof(receipt: dict) -> str:
    """Classify whether a locked edit proves its post-edit lint was inherited."""
    pre_lint = receipt.get("pre_lint")
    post_lint = receipt.get("post_lint")
    if not isinstance(pre_lint, list) or not isinstance(post_lint, list):
        return "missing"
    return "preserved" if post_lint == pre_lint else "introduced"


def classification_registry(value: object, vault: Path) -> dict:
    if not isinstance(value, dict):
        die("invalid classification registry")
    result: dict = {}
    for raw, entry in value.items():
        if not isinstance(raw, str) or not isinstance(entry, dict):
            die("malformed classification registry row")
        if entry.get("mode") not in ("semantic", "reference", "mechanical", "nonlocal"):
            die(f"invalid classification mode for {raw}")
        key = raw if raw.startswith("external::") else str(canonical_path(raw, vault))
        if key in result:
            old = result[key]
            signature = lambda item: (item.get("mode"), item.get("inspection_scope", "targeted" if item.get("mode") == "reference" else "full"),
                                      item.get("replacements"), item.get("mechanical_kind"))
            if signature(old) != signature(entry):
                die(f"classification aliases disagree on mode: {key}")
            if (old.get("sha256_at_classification") and entry.get("sha256_at_classification")
                    and old["sha256_at_classification"] != entry["sha256_at_classification"]):
                die(f"classification aliases disagree on content hash: {key}")
        else:
            result[key] = dict(entry)
        if not raw.startswith("external::"):
            aliases = result[key].setdefault("aliases", [])
            for alias in [*entry.get("aliases", []), str(lexical_path(raw, vault))]:
                if alias not in aliases:
                    aliases.append(alias)
    return result


@contextmanager
def classification_writer(root: Path, sid: str):
    root.mkdir(parents=True, exist_ok=True)
    directory_lock = root / ".classification.lockdir"
    owns_directory = False
    with (root / ".classification.lock").open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX)
        else:  # Windows: serialize the same writer's concurrent CLI calls too.
            deadline = time.monotonic() + 10
            while True:
                try:
                    directory_lock.mkdir()
                    owns_directory = True
                    break
                except FileExistsError:
                    if time.monotonic() >= deadline:
                        die("classification lock timed out; inspect its owner or begin a new generation")
                    time.sleep(0.02)
        try:
            identity = (os.environ.get("OPENCAIRN_AGENT_ID") or os.environ.get("CODEX_THREAD_ID")
                        or os.environ.get("CLAUDE_AGENT_ID") or "session:" + sid)
            owner_path = root / "classification-writer.json"
            owner = load_json(owner_path, None)
            if owner is not None and not isinstance(owner, dict):
                die("malformed classification writer record")
            if owner is not None and owner.get("writer") != identity:
                die("classification generation already has another writer; use the owning coordinator")
            if owner is None:
                atomic_json(owner_path, {"writer": identity, "claimed_at": now()})
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
            elif owns_directory:
                directory_lock.rmdir()


def store_classification(manifest: dict, path: Path, alias: Path, entry: dict) -> None:
    prior = manifest.get(str(path), {})
    scope = lambda item: item.get("inspection_scope", "targeted" if item.get("mode") == "reference" else "full")
    if alias != path and prior and (prior.get("mode"), scope(prior)) != (entry.get("mode"), scope(entry)):
        die(f"classification alias conflicts with the physical file's mode: {alias} -> {path}")
    entry["aliases"] = list(dict.fromkeys([*prior.get("aliases", []), str(alias)]))
    if alias != path:
        for key in ("inspection_targets", "dependencies"):
            entry[key] = list(dict.fromkeys([*prior.get(key, []), *entry.get(key, [])]))
    manifest[str(path)] = entry


def cmd_classify(args: argparse.Namespace) -> int:
    sid, root, receipt_root, _ = state_paths(args.session_id)
    with classification_writer(root, sid):
        return classify_locked(args, root, receipt_root)


def classify_locked(args: argparse.Namespace, root: Path, receipt_root: Path) -> int:
    vault = canonical_path(args.vault)
    manifest_path = root / "files.json"
    manifest = classification_registry(load_json(manifest_path, {}), vault)
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
    if args.semantic or args.reference:
        if not path.is_file():
            die(f"local file missing: {path}")
        if args.targeted and not args.semantic:
            die("--targeted is valid only with --semantic")
        if args.targeted and not args.inspection_target:
            die("targeted semantic review requires at least one --inspection-target")
        inspection_scope = "targeted" if args.reference or args.targeted else "full"
        artifact = None
        with path.open("rb") as handle:
            prefix = handle.read(8192)
        if (
            prefix.startswith(b"%PDF-")
            or inspection_scope == "targeted"
            or is_binary_artifact(prefix) or not file_is_utf8(path)
        ):
            artifact = prepare_artifact(root, vault, path, path)
        entry = {
            "mode": "reference" if args.reference else "semantic",
            "inspection_scope": inspection_scope,
            "inspection_targets": args.inspection_target or [],
            "dependencies": getattr(args, "dependency", None) or [],
            "reason": args.reason
            or (
                "imported local reference artefact"
                if args.reference
                else "meaning-bearing change"
            ),
            "classified_at": now(),
            "sha256_at_classification": sha256(path),
            "full_read_confirmed": bool(getattr(args, "confirm_full_read", False)),
            **({"artifact": artifact} if artifact else {}),
        }
        store_classification(manifest, path, lexical_path(args.path, vault), entry)
        atomic_json(manifest_path, manifest)
        label = "REFERENCE" if args.reference else "SEMANTIC"
        detail = ""
        if artifact:
            detail = (
                f" ({artifact.get('media_type')}; pages={artifact.get('pages')}; "
                f"text={artifact.get('text_status')}; lines={artifact.get('review_lines')})"
            )
        print(f"{label} {path}{detail}")
        return 0

    if not args.replace:
        die("--mechanical requires at least one --replace OLD NEW pair")
    if args.target and args.no_locator_target:
        die("--mechanical takes --target or --no-locator-target, never both")
    if not args.target and not args.no_locator_target:
        die(
            "--mechanical requires at least one --target, or --no-locator-target "
            "to declare that no substitution in this call is a locator"
        )
    result = verify_mechanical(
        path,
        vault,
        args.replace,
        args.target or [],
        receipt_root,
        allow_inherited_lint=args.allow_inherited_lint,
    )
    if not result["ok"]:
        for failure in result["failures"]:
            print(f"FAIL mechanical: {failure}", file=sys.stderr)
        return 1
    entry = {
        "mode": "mechanical",
        "classified_at": now(),
        "replacements": args.replace,
        "targets": args.target or [],
        "no_locator_target": bool(args.no_locator_target),
        "verification": result,
        "dependencies": getattr(args, "dependency", None) or [],
    }
    store_classification(manifest, path, lexical_path(args.path, vault), entry)
    atomic_json(manifest_path, manifest)
    print(
        f"PASS mechanical: {path} ({len(args.replace)} replacement(s), "
        f"{len(args.target or [])} target(s)"
        f"{', no-locator-target' if args.no_locator_target else ''}, "
        f"{len(result['receipts'])} receipt(s))"
    )
    return 0


def verify_move_heal(path: Path, vault: Path, proof: dict, *, check_current: bool = True) -> dict:
    failures: list[str] = []
    if not path.is_file():
        return {"ok": False, "failures": [f"file missing: {path}"]}
    current_hash = sha256(path)
    if check_current and current_hash != proof.get("post_sha256"):
        failures.append("current file hash does not match the move-healing receipt")
    if proof.get("diff_truncated"):
        failures.append("move-healing receipt has a truncated diff")
    destination = canonical_path(str(proof.get("destination", "")), vault)
    target = target_check(str(destination), vault)
    if not target["exists"]:
        failures.append(f"move destination missing: {destination}")
    if proof.get("pre_lint") != proof.get("post_lint"):
        failures.append("link healing changed the file's lint fingerprint")
    text = path.read_text(encoding="utf-8")
    separator_clean = not SEP_RE.search(text)
    if not separator_clean:
        failures.append("stranded locked-edit separator line")
    lint = lint_errors(text)
    accepted_lint = lint if proof.get("pre_lint") == proof.get("post_lint") else []
    return {
        "ok": not failures,
        "failures": failures,
        "current_sha256": current_hash,
        "replacements": [
            {
                "old": proof.get("source_locator"),
                "new": proof.get("destination_locator"),
                "old_count": 0,
                "new_count": proof.get("healed_links", 0),
            }
        ],
        "targets": [target],
        "separator_clean": separator_clean,
        "lint_clean": not lint,
        "accepted_inherited_lint": accepted_lint,
        "receipts": [
            {
                "path": proof.get("receipt_path"),
                "mode": "obsidian-link-heal",
                "pre_sha256": proof.get("pre_sha256"),
                "post_sha256": proof.get("post_sha256"),
                "pre_lint": proof.get("pre_lint"),
                "post_lint": proof.get("post_lint"),
                "changed_ranges": [],
                "ranges_truncated": False,
                "unified_diff": proof.get("unified_diff", ""),
                "diff_truncated": proof.get("diff_truncated", False),
            }
        ],
    }


def verify_move_heal_chain(path: Path, vault: Path, proof: dict) -> dict:
    """Verify every immutable producer receipt and the final bytes of a heal chain."""
    if not path.is_file():
        return {"ok": False, "failures": [f"file missing: {path}"]}
    items = proof.get("heals", [])
    if not items:
        return {"ok": False, "failures": ["empty move-healing chain"]}
    results = []
    previous = None
    failures = []
    for item in items:
        receipt = Path(item["receipt_path"])
        if not receipt.is_file() or sha256(receipt) != item.get("receipt_sha256"):
            failures.append(f"move receipt changed or missing: {receipt}")
        if previous is not None and previous != item.get("pre_sha256"):
            failures.append("move-healing receipt hash chain is discontinuous")
        previous = item.get("post_sha256")
        result = verify_move_heal(path, vault, item, check_current=False)
        failures.extend(result["failures"])
        results.append(result)
    if path.is_file() and sha256(path) != previous:
        failures.append("current file hash does not match the final move-healing receipt")
    last = results[-1]
    return {**last, "ok": not failures, "failures": failures,
            "replacements": [x for r in results for x in r["replacements"]],
            "targets": [x for r in results for x in r["targets"]],
            "receipts": [x for r in results for x in r["receipts"]]}


def verify_preserved_move(path: Path, vault: Path, proof: dict, receipt_dir: Path) -> dict:
    """Validate unchanged text against the actual current-session move producer."""
    receipt_path = Path(str(proof.get("receipt_path", ""))).expanduser()
    failures = []
    if (receipt_path.is_symlink() or not receipt_path.is_file()
            or receipt_path.resolve().parent != receipt_dir.resolve()):
        return {"ok": False, "failures": ["receipt is not a regular current-session move receipt"]}
    if sha256(receipt_path) != proof.get("receipt_sha256"):
        return {"ok": False, "failures": ["native move receipt changed after classification"]}
    receipt = load_json(receipt_path, {})
    if not isinstance(receipt, dict):
        return {"ok": False, "failures": ["invalid native move receipt"]}
    if (receipt.get("schema") != 2 or receipt.get("mode") != "--move"
            or receipt.get("complete") is not True
            or receipt.get("affected_files") != [] or receipt.get("unverified_files") != []):
        failures.append("requires a complete schema2 move without affected or unverified files")
    locators = [receipt.get(key) for key in ("vault", "source", "destination")]
    if not all(isinstance(value, str) and Path(value).is_absolute() for value in locators):
        return {"ok": False, "failures": ["native move paths must be absolute"]}
    owner, source, destination = (canonical_path(value) for value in locators)
    if owner != vault or not source.is_relative_to(vault) or not destination.is_relative_to(vault):
        failures.append("native move receipt belongs to another vault")
    if source == destination or source.exists() or Path(locators[1]).is_symlink():
        failures.append("native move source is not a distinct absent path")
    if (destination != path or Path(locators[2]).is_symlink()
            or path.is_symlink() or not path.is_file()):
        failures.append("native move destination is not the requested regular file")
    digest = sha256(path) if path.is_file() else None
    expected = receipt.get("source_sha256")
    if (not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected)
            or expected != receipt.get("content_sha256") or expected != digest):
        failures.append("native pre/post/current hashes do not prove zero content delta")
    if failures:
        return {"ok": False, "failures": failures}
    data = path.read_bytes()
    if sha256_bytes(data) != digest or not is_utf8(data) or is_binary_artifact(data):
        return {"ok": False, "failures": ["preserved move must remain unchanged UTF-8 text"]}
    text = data.decode("utf-8")
    if SEP_RE.search(text):
        return {"ok": False, "failures": ["stranded locked-edit separator line"]}
    # Equal producer pre/post/current hashes bind this exact lint fingerprint to
    # the preimage as well as the current bytes; no replacement receipt is invented.
    lint = lint_errors(text)
    return {"ok": True, "failures": [], "current_sha256": digest,
            "replacements": [], "targets": [target_check(str(path), vault)],
            "separator_clean": True, "lint_clean": not lint,
            "accepted_inherited_lint": lint,
            "receipts": [{"path": str(receipt_path), "mode": "--move",
                          "pre_sha256": expected, "post_sha256": digest,
                          "pre_lint": lint, "post_lint": lint,
                          "lint_proof": "equal native pre/post/current bytes",
                          "changed_ranges": [], "ranges_truncated": False,
                          "unified_diff": "", "diff_truncated": False}]}


def cmd_import_preserved_move(args: argparse.Namespace) -> int:
    sid, root, _, _ = state_paths(args.session_id)
    with classification_writer(root, sid):
        return import_preserved_move_locked(args)


def import_preserved_move_locked(args: argparse.Namespace) -> int:
    sid, root, receipt_root, _ = state_paths(args.session_id)
    vault = canonical_path(args.vault)
    path = lexical_path(args.path, vault)
    receipt_path = Path(args.receipt).expanduser().absolute()
    proof = {"receipt_path": str(receipt_path),
             "receipt_sha256": sha256(receipt_path) if receipt_path.is_file() else None}
    verification = verify_preserved_move(
        path, vault, proof, receipt_root.parent / f"{sid}.project-move-receipts")
    if not verification["ok"]:
        for failure in verification["failures"]:
            print(f"FAIL preserved move: {failure}", file=sys.stderr)
        return 1
    manifest_path = root / "files.json"
    manifest = load_json(manifest_path, {})
    if not isinstance(manifest, dict):
        die(f"invalid file manifest: {manifest_path}")
    manifest[str(path.resolve())] = {"mode": "mechanical",
                                    "mechanical_kind": "native-move-preserved",
                                    "classified_at": now(), "proof": proof,
                                    "verification": verification}
    atomic_json(manifest_path, manifest)
    print(f"PASS preserved move: {path} (native zero-content-delta proof)")
    return 0


def cmd_import_move_heals(args: argparse.Namespace) -> int:
    sid, root, _, _ = state_paths(args.session_id)
    with classification_writer(root, sid):
        return import_move_heals_locked(args)


def import_move_heals_locked(args: argparse.Namespace) -> int:
    """Import link-target-only rewrites proved by locked Obsidian moves."""
    sid, root, receipt_root, _ = state_paths(args.session_id)
    vault = canonical_path(args.vault)
    receipt_dir = receipt_root.parent / f"{sid}.project-move-receipts"
    if not receipt_dir.is_dir():
        print("MOVE_HEALS none")
        return 0
    manifest_path = root / "files.json"
    manifest = load_json(manifest_path, {})
    if not isinstance(manifest, dict):
        die(f"invalid file manifest: {manifest_path}")

    imported = 0
    moves = 0
    unverified = 0
    incomplete: list[str] = []
    grouped: dict[str, list[dict]] = {}
    incomplete_moves = []
    verified_by_receipt: dict[str, int] = {}
    receipts = []
    relocations = {}
    for move_path in receipt_dir.glob("*.json"):
        receipt = load_json(move_path, None)
        if not isinstance(receipt, dict) or receipt.get("schema") != 2:
            die(f"invalid project-move receipt: {move_path}")
        if canonical_path(str(receipt.get("vault", ""))) != vault:
            die(f"project-move receipt belongs to another vault: {move_path}")
        receipts.append((receipt.get("captured_at", ""), str(move_path), receipt))
        if receipt.get("source"):
            relocations[str(canonical_path(receipt["source"], vault))] = str(
                canonical_path(receipt["destination"], vault))
    for _, receipt_name, receipt in sorted(receipts):
        move_path = Path(receipt_name)
        destination = canonical_path(str(receipt.get("destination", "")), vault)
        moves += 1
        unverified += len(receipt.get("unverified_files", []))
        for item in receipt.get("affected_files", []):
            if not isinstance(item, dict):
                die(f"malformed affected-file row: {move_path}")
            path = str(canonical_path(str(item.get("path", "")), vault))
            seen = set()
            while path in relocations:
                if path in seen:
                    die(f"cyclic move paths: {path}")
                seen.add(path)
                path = relocations[path]
            grouped.setdefault(path, []).append({
                **item, "receipt_path": str(move_path),
                "receipt_sha256": sha256(move_path),
                "destination": str(destination),
                "source_locator": receipt.get("source_locator"),
                "destination_locator": receipt.get("destination_locator"),
            })
        if receipt.get("complete") is False:
            postcheck = receipt.get("postcheck")
            reason = postcheck.get("reason") if isinstance(postcheck, dict) else None
            incomplete_moves.append((move_path, reason, len(receipt.get("unverified_files", []))))

    for path_name, heals in grouped.items():
        path = Path(path_name)
        prior = manifest.get(path_name, {})
        if prior.get("mode") in ("semantic", "reference"):
            incomplete.append(f"MOVE_HEAL_REVIEW {path}: explicit {prior['mode']} classification retained")
            unverified += 1
            continue
        proof = {"heals": heals} if len(heals) > 1 else heals[0]
        result = (verify_move_heal_chain(path, vault, proof) if len(heals) > 1
                  else verify_move_heal(path, vault, proof))
        if not result["ok"]:
            # Reject this mechanical proof, not independently valid files from
            # other moves. Semantic edits can interrupt a receipt chain; moves
            # or deletions can also remove its target after it was produced.
            if manifest.get(path_name, {}).get("mode") == "mechanical":
                manifest.pop(path_name)
            unverified += 1
            incomplete.append(f"MOVE_HEAL_REVIEW {path}: semantic review required: "
                              + "; ".join(result["failures"]))
            continue
        manifest[path_name] = {
            "mode": "mechanical",
            "mechanical_kind": "obsidian-link-heal-chain" if len(heals) > 1 else "obsidian-link-heal",
            "classified_at": now(), "proof": proof, "verification": result,
        }
        imported += len(heals)
        for heal in heals:
            key = heal["receipt_path"]
            verified_by_receipt[key] = verified_by_receipt.get(key, 0) + 1
    for move_path, reason, count in incomplete_moves:
        incomplete.append(
            f"MOVE_INCOMPLETE {move_path}: the move failed its postcheck "
            f"({reason or 'no reason recorded'}); "
            f"{verified_by_receipt.get(str(move_path), 0)} verified link-healed file(s) imported, "
            f"{count} file(s) left for semantic review"
        )
    atomic_json(manifest_path, manifest)
    for line in incomplete:
        print(line)
    print(
        f"MOVE_HEALS imported {moves} move(s), {imported} link-healed file(s), "
        f"{unverified} file(s) left for semantic review"
        + (f", {len(incomplete_moves)} incomplete move(s)" if incomplete_moves else "")
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
        "run_generation": root.name if (root / "run.json").is_file() else None,
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
    structured = None
    raw = None
    if getattr(args, "raw_file", None):
        raw = raw_output_receipt(root, canonical_path(args.raw_file))
        text = (f"Complete raw-byte receipt: {raw['path']}\nSHA-256: {raw['sha256']}\n"
                f"Bytes: {raw['bytes']}; LF-delimited records: {raw['lf_records']}; "
                f"per-file counts retained in the capture JSON; unparsed records: {raw['unparsed_records']}")
    else:
        # Reading .buffer preserves CR and NUL bytes rather than universal-newline
        # conversion. Large or non-UTF-8 output uses --raw-file, never replacement
        # decoding that changes the receipt bytes.
        buffer = getattr(sys.stdin, "buffer", None)
        text = buffer.read().decode("utf-8") if buffer is not None else sys.stdin.read()
    if args.kind in ("enumeration", "propagation") and not getattr(args, "raw_file", None):
        try:
            candidate = json.loads(text)
        except ValueError:
            candidate = None
        if args.kind == "enumeration":
            if not isinstance(candidate, dict) or not isinstance(candidate.get("needles"), list):
                die('enumeration requires JSON {"needles": [{"needle": "...", "match_mode": "fixed|word|phrase"}]}')
            structured = {"needles": normalise_needles(candidate["needles"])}
        elif isinstance(candidate, dict) and "searches" in candidate:
            if not isinstance(candidate["searches"], list):
                die("propagation searches must be a list")
            searches = []
            for row in candidate["searches"]:
                needle = normalise_needles([row])[0]
                statuses = [row[k] for k in ("exit_status", "exit_code", "returncode") if k in row]
                if (not statuses or any(type(v) is not int for v in statuses)
                        or len(set(statuses)) != 1):
                    die("search receipt requires one consistent integer exit_status/exit_code/returncode")
                if not isinstance(row.get("command"), str) or not row["command"].strip():
                    die("search receipt requires its literal command")
                if not isinstance(row.get("cwd"), str) or not Path(row["cwd"]).is_absolute():
                    die("search receipt requires absolute cwd")
                validate_search_command({**row, **needle})
                output = {}
                for stream in ("stdout", "stderr"):
                    name = row.get(stream + "_file")
                    if not isinstance(name, str):
                        die(f"search receipt requires {stream}_file, including an empty output file")
                    output[stream] = raw_output_receipt(root, canonical_path(name))
                searches.append({**needle, "exit_status": statuses[0], "command": row["command"],
                                 "cwd": row["cwd"], **output})
            structured = {"searches": searches}
            text = str(candidate.get("report", "")) + "\nExecuted search receipts:\n" + "\n".join(
                f"{row['needle']!r} ({row['match_mode']}), exit_status={row['exit_status']}; "
                f"command={row['command']!r}; cwd={row['cwd']!r}; "
                + "; ".join(f"{stream}={row[stream]['path']} SHA-256={row[stream]['sha256']} "
                            f"bytes={row[stream]['bytes']} LF records={row[stream]['lf_records']}"
                            for stream in ("stdout", "stderr"))
                for row in searches)
    path = capture_record(
        root,
        kind=args.kind,
        label=args.label,
        text=text,
        source=args.source,
        provenance=args.provenance,
    )
    if structured is not None or raw is not None:
        record = load_json(path, {})
        if structured is not None:
            record["structured"] = structured
        if raw is not None:
            record["raw"] = raw
        atomic_json(path, record)
    if getattr(args, "dependency", None) or getattr(args, "mutation_for", None):
        record = load_json(path, {})
        record["dependencies"] = getattr(args, "dependency", None) or []
        if getattr(args, "mutation_for", None):
            if (not getattr(args, "command", None) or type(getattr(args, "exit_status", None)) is not int
                    or not getattr(args, "cwd", None) or not Path(args.cwd).is_absolute()):
                die("mutation evidence requires --command, absolute --cwd and integer --exit-status")
            record["mutation"] = {"path": args.mutation_for, "command": args.command,
                                  "cwd": args.cwd, "exit_status": args.exit_status}
        atomic_json(path, record)
    print(f"Receipt: {path}")
    return 0


def normalise_needles(rows: list) -> list[dict]:
    result = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("needle"), str)
                or not row["needle"] or "\n" in row["needle"] or "\0" in row["needle"]):
            die("needle rows require a non-empty single-line literal needle")
        mode = row.get("match_mode", "fixed")
        if mode not in ("fixed", "word", "phrase"):
            die("needle match_mode must be fixed, word or phrase")
        value = {"needle": row["needle"], "match_mode": mode}
        if value in result:
            die(f"duplicate needle/match_mode: {value}")
        result.append(value)
    return result


def decoded_json(value: object) -> object:
    """Unwrap escaped outer JSON without changing an ordinary textual result."""
    for _ in range(4):
        if not isinstance(value, str):
            break
        try:
            nested = json.loads(value)
        except ValueError:
            break
        if nested == value:
            break
        value = nested
    return value


def tool_text(value: object) -> str:
    value = decoded_json(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for item in value if (part := tool_text(item)))
    if isinstance(value, dict):
        # URL/title/date/size are metadata, not a retrieved supporting passage.
        for key in ("text", "body", "content", "output", "result"):
            if key in value:
                return tool_text(value[key])
    return ""


def tool_sources(arguments: object, output: object) -> list[str]:
    found = []
    def walk(value: object):
        value = decoded_json(value)
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("file_path", "path", "source", "url", "ref_id") and isinstance(item, str):
                    if (item.startswith(("/", "~/", "http://", "https://")) and item not in found):
                        found.append(item)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            for url in re.findall(r"https?://[^\s\"'<>\\)\]}]+", value):
                if url not in found:
                    found.append(url)
    walk(arguments)
    walk(output)
    return found



def web_run_opens(source: str) -> bool:
    """True when a JS `web__run({...})` call's top-level object requests `open`/`fetch`.

    Key order is irrelevant: the object literal is decoded as JSON where possible, and
    otherwise its depth-one keys are scanned.
    """
    for match in re.finditer(r"web__run\s*\(\s*(?=\{)", source):
        start = match.end()
        try:
            value, _ = json.JSONDecoder().raw_decode(source, start)
        except ValueError:
            value = None
        if isinstance(value, dict):
            if any(key in value for key in ("open", "fetch")):
                return True
            continue
        depth = 0
        for token in re.finditer(r'[{}\[\]]|["\']?(\w+)["\']?\s*:', source[start:]):
            text = token.group(0)
            if text in "{[":
                depth += 1
            elif text in "}]":
                depth -= 1
                if depth == 0:
                    break
            elif depth == 1 and token.group(1) in ("open", "fetch"):
                return True
    return False

def cmd_capture_tools(args: argparse.Namespace) -> int:
    """Index actual tool returns, pairing native custom calls and async waits."""
    _, root, _, _ = state_paths(args.session_id)
    transcript = canonical_path(args.transcript)
    index_path = root / "tool-source-index.json"
    index = load_json(index_path, {"schema": 1, "records": []})
    if not isinstance(index, dict) or not isinstance(index.get("records"), list):
        die("malformed tool source index")
    records = index["records"]
    calls: dict[str, dict] = {}
    cells: dict[str, dict] = {}
    seen = {(item.get("call_id"), item.get("raw_sha256")) for item in records}
    added = 0
    with transcript.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError:
                die(f"tool transcript is not UTF-8 at line {line_number}; retain it with capture --raw-file")
            try:
                outer = decoded_json(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(outer, dict):
                continue
            value = decoded_json(outer.get("payload", outer))
            if not isinstance(value, dict):
                continue
            message = value.get("message", value)
            events = ([value] if value.get("type") in (
                "function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output")
                else message.get("content", []) if isinstance(message, dict)
                and isinstance(message.get("content"), list) else [value])
            for event in events:
                if not isinstance(event, dict):
                    continue
                kind = event.get("type")
                if kind in ("function_call", "custom_tool_call", "tool_use"):
                    ident = str(event.get("call_id") or event.get("id") or "")
                    calls[ident] = {"id": ident, "name": event.get("name", "unknown"),
                                    "arguments": decoded_json(event.get("arguments", event.get("input", {})))}
                    continue
                if kind not in ("function_call_output", "custom_tool_call_output", "tool_result"):
                    continue
                ident = str(event.get("call_id") or event.get("tool_use_id") or "")
                call = calls.get(ident, {"id": ident, "name": "unknown", "arguments": {}})
                parent = call
                arguments = call.get("arguments")
                if isinstance(arguments, dict) and arguments.get("cell_id") in cells:
                    parent = cells[arguments["cell_id"]]
                output = event.get("output", event.get("content", ""))
                body = tool_text(output)
                match = re.search(r"Script running with cell ID\s+([\w-]+)", body)
                if match:
                    cells[match.group(1)] = parent
                raw_digest, raw_path = write_snapshot(root, raw_line)
                if (ident, raw_digest) in seen:
                    continue
                sources = tool_sources(parent.get("arguments"), output)
                requested_sources = tool_sources(parent.get("arguments"), {})
                entry = {"call_id": ident, "parent_call_id": parent.get("id"),
                         "tool": call["name"], "source_tool": parent["name"],
                         "sources": sources, "requested_sources": requested_sources,
                         "raw_sha256": raw_digest, "raw_path": str(raw_path),
                         "transcript": str(transcript), "line": line_number,
                         "metadata_only": not bool(body.strip()) or body.strip() in sources or bool(match), "support": []}
                # Keep decoded text as an immutable index for passage checks; the
                # original JSON line remains available byte-for-byte beside it.
                body_digest, body_path = write_snapshot(root, body.encode("utf-8"))
                entry.update(text_path=str(body_path), text_sha256=body_digest)
                origin = parent.get("arguments")
                if not isinstance(origin, str):
                    origin = json.dumps(origin, ensure_ascii=False)
                requested = parent.get("arguments")
                entry["direct_read"] = bool(
                    parent["name"].casefold() in ("read", "read_file", "webfetch")
                    or isinstance(requested, dict) and any(key in requested for key in ("open", "fetch"))
                    or isinstance(requested, str) and web_run_opens(origin))
                records.append(entry)
                seen.add((ident, raw_digest))
                added += 1
                source = sources[0] if len(sources) == 1 else f"tool:{call['name']}:{ident}"
                text = body if 0 < len(body) <= 16384 else (
                    f"Tool return retained at {raw_path} SHA-256 {raw_digest}; "
                    f"decoded passage index {body_path} SHA-256 {body_digest}; "
                    f"metadata_only={entry['metadata_only']}; sources={json.dumps(sources)}")
                receipt_path = capture_record(root, kind="evidence", label=f"tool {call['name']} {ident}",
                    text=text, source=source, provenance="unverified")
                receipt = load_json(receipt_path, {})
                receipt["tool_record"] = entry
                atomic_json(receipt_path, receipt)
    atomic_json(index_path, index)
    for item in records:
        for path_key, digest_key in (("raw_path", "raw_sha256"), ("text_path", "text_sha256")):
            retained = Path(str(item.get(path_key, "")))
            if not retained.is_file() or sha256(retained) != item.get(digest_key):
                die(f"tool source index snapshot missing or corrupt: {retained}")
    claims = load_json(canonical_path(args.claims_file), []) if args.claims_file else []
    if not isinstance(claims, list):
        die("claims file must be a list of source/passage declarations")
    for claim in claims:
        if (not isinstance(claim, dict) or not isinstance(claim.get("source"), str)
                or not isinstance(claim.get("passage"), str) or not claim["passage"].strip()):
            die("each source claim requires a source and nonempty literal passage")
        matches = [item for item in records if claim["source"] in item["sources"]
                   and (not claim.get("call_id") or claim["call_id"] in (item["call_id"], item["parent_call_id"]))
                   and not item["metadata_only"]
                   and claim["passage"] in Path(item["text_path"]).read_bytes().decode("utf-8")]
        if not matches:
            die(f"no captured passage supports source claim: {claim['source']}")
        item = matches[-1]
        provenance = claim.get("provenance", "primary")
        if provenance not in ("primary", "secondary", "unverified"):
            die("source claim provenance must be primary, secondary or unverified")
        if provenance == "primary" and (not item["direct_read"]
                or item.get("requested_sources") != [claim["source"]]):
            die(f"primary passage has ambiguous or discovery-only source association: {claim['source']}")
        capture_record(root, kind="evidence", label="captured supporting passage", text=claim["passage"],
                       source=claim["source"], provenance=provenance)
        item["support"].append(claim["passage"])
    atomic_json(index_path, index)
    print(f"Tool source index: {index_path}; returns added {added}; total {len(records)}; supported claims {len(claims)}")
    return 0


def validate_search_command(row: dict) -> None:
    try:
        argv = shlex.split(row.get("command", ""))
    except ValueError as exc:
        die(f"invalid literal search command: {exc}")
    if any(token in argv for token in ("|", "||", "&&", ";", ">", ">>")):
        die("search command must name rg before output redirection, without a filtering pipeline")
    start = next((i for i, value in enumerate(argv)
                  if Path(value).name.casefold() in ("rg", "rg.exe")), None)
    if start is None:
        die("structured search command must invoke rg")
    args = argv[start + 1:]
    delimiter = args.index("--") if "--" in args else len(args)
    options = args[:delimiter]
    fixed = "--fixed-strings" in options or any(re.fullmatch(r"-[A-Za-z]*F[A-Za-z]*", x) for x in options)
    word = "--word-regexp" in options or any(re.fullmatch(r"-[A-Za-z]*w[A-Za-z]*", x) for x in options)
    if not fixed or (row.get("match_mode") == "word") != word:
        die("search command flags do not match the declared literal match_mode")
    patterns = [options[i + 1] for i, x in enumerate(options[:-1]) if x in ("-e", "--regexp")]
    patterns += [x.split("=", 1)[1] for x in options if x.startswith("--regexp=")]
    if not patterns and delimiter < len(args) - 1:
        patterns = [args[delimiter + 1]]
    if row.get("needle") not in patterns:
        die("search command does not contain the declared pattern after -- or -e")


RG_VALUE_SHORT = set("ABCEMdefgjmrtT")
# Output forms whose records are not whole `path:line:text` matches.
RG_NON_LINE_SHORT = set("NIbcloMprUv")
RG_NON_LINE_LONG = {"--no-line-number", "--no-filename", "--count", "--count-matches",
                    "--files-with-matches", "--files-without-match", "--files", "--json",
                    "--only-matching", "--replace", "--max-columns", "--vimgrep", "--column",
                    "--multiline", "--invert-match", "--passthru", "--byte-offset",
                    "--heading", "--pretty"}


def stale_propagation_hits(row: dict) -> list[str]:
    """Name each hit line of a final search that no longer occurs in its file.

    Only `rg -n` match records are checked: the hit's whole line must still be a
    line of the current file (anywhere, so line shifts from unrelated edits pass).
    Other output forms and unparseable records (binary-match notices, context
    lines) carry no line text to compare and are skipped.
    """
    argv = shlex.split(row.get("command", ""))
    start = next(i for i, value in enumerate(argv) if Path(value).name.casefold() in ("rg", "rg.exe"))
    args = argv[start + 1:]
    options = args[:args.index("--")] if "--" in args else args
    numbered = False
    index = 0
    while index < len(options):
        token = options[index]
        index += 1
        if token.startswith("--"):
            name, _, value = token.partition("=")
            if name in ("--color", "--colour"):
                value = value or (options[index] if index < len(options) else "")
                if value in ("always", "ansi"):
                    return []
            if name in RG_NON_LINE_LONG:
                return []
            numbered = numbered or name == "--line-number"
        elif token.startswith("-") and len(token) > 1:
            for position, letter in enumerate(token[1:], 2):
                if letter in RG_NON_LINE_SHORT:
                    return []
                numbered = numbered or letter == "n"
                if letter in RG_VALUE_SHORT:
                    index += position == len(token)  # value is the next token
                    break
    if not numbered:
        return []
    cwd = Path(row["cwd"])
    wanted: dict[Path, dict[bytes, tuple[str, int]]] = {}
    with Path(row["stdout"]["path"]).open("rb") as handle:
        for raw in handle:
            record = raw[:-1] if raw.endswith(b"\n") else raw
            if b"\0" in record:
                name, tail = record.split(b"\0", 1)
                match = re.match(rb"([0-9]+):", tail)
                if not name or not match:
                    continue
                splits = [(name, int(match.group(1)), tail[match.end():])]
            else:
                splits = [(record[:m.start()], int(m.group(1)), record[m.end():])
                          for m in re.finditer(rb":([0-9]+):", record) if m.start()]
                if not splits:
                    continue
                # A colon-delimited name is ambiguous; prefer the split naming a file.
                splits = [s for s in splits if (cwd / os.fsdecode(s[0])).is_file()] or splits[:1]
            name, line, text = splits[0]
            wanted.setdefault(cwd / os.fsdecode(name), {}).setdefault(text, (os.fsdecode(name), line))
    stale = []
    for path, texts in wanted.items():
        if path.is_file():
            with path.open("rb") as handle:
                for raw in handle:
                    texts.pop(raw[:-1] if raw.endswith(b"\n") else raw, None)
                    if not texts:
                        break
        stale.extend(f"{name}:{line}" for name, line in texts.values())
    return stale


def validate_propagation_coverage(captures: list[dict], propagation: dict) -> dict | None:
    enumerations = [item for item in captures if item.get("kind") == "enumeration"]
    if not enumerations:
        return None  # Legacy callers remain usable; updated callers capture a final enumeration.
    rows = enumerations[-1].get("structured", {}).get("needles")
    if not isinstance(rows, list):
        die("malformed final enumeration receipt")
    expected = {(row["needle"], row["match_mode"]) for row in normalise_needles(rows)}
    searches = propagation.get("structured", {}).get("searches")
    if not isinstance(searches, list):
        die("Propagation coverage: latest propagation receipt has no structured executed-search set")
    executed = set()
    failed = []
    for row in searches:
        validate_search_command(row)
        needle = normalise_needles([row])[0]
        key = (needle["needle"], needle["match_mode"])
        if key in executed:
            die(f"Propagation coverage: duplicate executed needle {key}")
        executed.add(key)
        if row.get("exit_status") not in (0, 1):
            failed.append(key)
        for stream in ("stdout", "stderr"):
            raw = row.get(stream, {})
            path = Path(str(raw.get("path", "")))
            if not path.is_file() or sha256(path) != raw.get("sha256"):
                die(f"Propagation coverage: {stream} receipt missing or corrupt for {key}")
    result = {"enumerated": len(expected), "executed": len(executed),
              "missing": sorted(expected - executed), "unexpected": sorted(executed - expected),
              "failed": sorted(failed)}
    if result["missing"] or result["unexpected"] or result["failed"]:
        die("Propagation coverage: " + json.dumps(result, ensure_ascii=False))
    stale = [f"stale propagation receipt: {row['needle']!r} {hit} changed after search; rerun this needle"
             for row in searches for hit in stale_propagation_hits(row)]
    if stale:
        die("; ".join(stale))
    return result


def accepted_inherited_lint(
    output: str, accepted_paths: list[str]
) -> tuple[bool, list[str]]:
    """Validate the one park-verifier failure class the skill permits accepting."""
    if not accepted_paths:
        return False, []
    lines = output.splitlines()
    fail_indexes = [index for index, line in enumerate(lines) if line.startswith("FAIL ")]
    review_lines = [line for line in lines if line.startswith("REVIEW ")]
    result_lines = [line for line in lines if line.startswith("RESULT: ")]
    # The verifier appends ", <n> N/A" when an ident was absent everywhere; that
    # is not a failure or a review and leaves the counts it reports unchanged.
    if (
        len(fail_indexes) != 1
        or not lines[fail_indexes[0]].startswith("FAIL lint: ")
        or review_lines
        or len(result_lines) != 1
        or not re.fullmatch(
            r"RESULT: FAIL \(1 fail, 0 review(?:, [0-9]+ N/A)?\)", result_lines[0]
        )
    ):
        return False, []

    start = fail_indexes[0]
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith(
                ("PASS ", "FAIL ", "REVIEW ", "N/A ", "INFO ", "RESULT: ")
            )
        ),
        len(lines),
    )
    payload = "\n".join(lines[start:end]).removeprefix("FAIL lint: ")
    lint_paths = re.findall(
        r"(?:^|; )(/.*?)(?= joined-list: | \d+: 3\+ blank lines(?:;|$))",
        payload,
        flags=re.DOTALL,
    )
    allowed = {str(Path(path).expanduser().resolve()) for path in accepted_paths}
    found = {str(Path(path).resolve()) for path in lint_paths}
    if not found or found != allowed:
        return False, sorted(found)
    return True, sorted(found)


def approved_inherited_lint_paths(manifest: dict) -> set[str]:
    """Approve inherited lint only with mechanical proof or intact reference bytes."""
    approved: set[str] = set()
    for path, item in manifest.items():
        if not isinstance(item, dict):
            continue
        if item.get("mode") == "reference":
            source = Path(path).expanduser().resolve()
            if source.is_file():
                # References are imported evidence, not session-authored prose.
                # Require the live bytes and retained source/review snapshots to
                # match the classification before accepting any existing lint.
                digest = sha256(source)
                validated_artifact_receipt(source, digest, item)
                approved.add(str(source))
            continue
        if item.get("mode") != "mechanical":
            continue
        verification = item.get("verification")
        if (
            isinstance(verification, dict)
            and verification.get("accepted_inherited_lint")
        ):
            approved.add(str(Path(path).resolve()))
    return approved


def cmd_run_verifier(args: argparse.Namespace) -> int:
    _, root, _, _ = state_paths(args.session_id)
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        die("run-verifier requires a command after --")
    if Path(command[0]).name == "park-verify.sh" and len(command) >= 4:
        if "--reference" in command or "--nonlocal" in command:
            die("reference/nonlocal exemptions are derived from verified classifications")
        vault = canonical_path(command[1])
        classifications = load_json(root / "files.json", {})
        reference_args: list[str] = []
        seen_references: set[Path] = set()
        for index, token in enumerate(command[:-1]):
            if token != "--touched":
                continue
            nonlocal_item = classifications.get(f"external::{command[index + 1]}", {})
            if nonlocal_item.get("mode") == "nonlocal":
                reference_args.extend(["--nonlocal", command[index + 1]])
                continue
            source = canonical_path(command[index + 1], vault)
            item = classifications.get(str(source), {})
            if item.get("mode") != "reference" or source.is_relative_to(vault) or source in seen_references:
                continue
            digest = sha256(source)
            validated_artifact_receipt(source, digest, item)
            reference_args.extend(["--reference", str(source), digest])
            seen_references.add(source)
        command = [*command, *reference_args]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    combined = completed.stdout
    if completed.stderr:
        combined += "\n[stderr]\n" + completed.stderr
    effective_returncode = completed.returncode
    accepted_paths: list[str] = []
    if completed.returncode and args.accept_inherited_lint:
        manifest = load_json(root / "files.json", {})
        approved = approved_inherited_lint_paths(
            manifest if isinstance(manifest, dict) else {}
        )
        requested = {
            str(Path(path).expanduser().resolve())
            for path in args.accept_inherited_lint
        }
        accepted = requested <= approved
        if accepted:
            accepted, accepted_paths = accepted_inherited_lint(
                combined, args.accept_inherited_lint
            )
        if accepted:
            effective_returncode = 0
            note = (
                "ACCEPTED inherited lint only in explicitly named path(s): "
                + "; ".join(accepted_paths)
            )
            print(note)
            combined += "\n" + note + "\n"
    path = capture_record(
        root,
        kind="verifier",
        label=args.label,
        text=combined,
        source=" ".join(command),
        provenance="primary",
        returncode=effective_returncode,
    )
    print(f"Verifier receipt: {path}", file=sys.stderr)
    return effective_returncode


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
    return [path for path, _ in parse_file_rows(text, vault, classifications)]


def parse_file_rows(
    text: str, vault: Path, classifications: dict
) -> list[tuple[str, str | None]]:
    """Each Files row as (path, annotation); annotation is "deleted", "remote" or None."""
    rows: list[tuple[str, str | None]] = []
    for line in text.splitlines():
        value = line.strip()
        if not value.startswith("- "):
            continue
        value = value[2:]
        if not value or value.casefold() == "none":
            continue
        # The annotation sits outside a backticked path; strip it before the
        # " - " split so it is never read as part of the path or description.
        note = None
        quoted_end = value.find("`", 1) if value.startswith("`") else -1
        if quoted_end > 0:
            # Backticked path: the annotation must follow the closing backtick directly.
            annotated = ANNOTATION_RE.match(value, quoted_end + 1)
        else:
            # Unquoted path: the row-final form always counts; a mid-row candidate
            # counts only when its prefix reads as the path itself (no " - "
            # separator, a file extension, or a real/classified path). Otherwise it
            # sits inside the description.
            annotated = next(
                (
                    m
                    for m in ANNOTATION_RE.finditer(value)
                    if m.end() == len(value)
                    or " - " not in value[: m.start()]
                    or re.search(r"\.[A-Za-z0-9]{1,10}$", value[: m.start()].strip())
                    or f"external::{value[: m.start()].strip()}" in classifications
                    or str(canonical_path(value[: m.start()].strip(), vault)) in classifications
                    or canonical_path(value[: m.start()].strip(), vault).exists()
                ),
                None,
            )
        if annotated:
            note = annotated.group(1).lower()
            value = (value[: annotated.start()] + value[annotated.end() :]).strip()
        if value.startswith("`"):
            end = value.find("`", 1)
            if end < 0 or (value[end + 1 :] and not value[end + 1 :].startswith(" - ")):
                die(f"malformed backticked Files-list path: {line}")
            rows.append((value[1:end], note))
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
            rows.append((matched, note))
        elif split_points:
            # Backwards-compatible fallback for deleted paths, which no longer
            # exist and may predate explicit classification.
            rows.append((value[: split_points[-1]], note))
        else:
            rows.append((value, note))
    return rows


def partition_attributed_paths(
    raw_paths: list[str],
    vault: Path,
    classifications: dict,
    remote_rows: frozenset[str] = frozenset(),
) -> tuple[list[Path], list[dict]]:
    """Separate local paths from remote artefacts: rows annotated (remote), or
    exact, explicitly classified remote rows."""
    local_paths: list[Path] = []
    external_files: list[dict] = []
    seen: set[Path] = set()
    for raw in raw_paths:
        if raw in remote_rows:
            external_files.append({"path": raw, "reason": "row annotated (remote)"})
            continue
        external = classifications.get(f"external::{raw}")
        if isinstance(external, dict) and external.get("mode") == "nonlocal":
            external_files.append(
                {"path": raw, "reason": external.get("reason", "non-local artefact")}
            )
            continue
        if REMOTE_PATH_RE.match(raw):
            die(
                f"remote Files row is not classified exactly: {raw}; record one remote "
                "artefact per Files row and classify that exact row with --nonlocal"
            )
        path = canonical_path(raw, vault)
        if path not in seen:
            seen.add(path)
            local_paths.append(path)
    return local_paths, external_files


def load_captures(root: Path) -> list[dict]:
    records: list[dict] = []
    capture_dir = root / "captures"
    if not capture_dir.is_dir():
        return records
    for path in capture_dir.glob("*.json"):
        item = load_json(path, None)
        if isinstance(item, dict):
            item["_path"] = str(path)
            retained = [item["raw"]] if isinstance(item.get("raw"), dict) else []
            for row in item.get("structured", {}).get("searches", []):
                retained.extend(row.get(key, {}) for key in ("stdout", "stderr"))
            tool = item.get("tool_record", {})
            for path_key, hash_key in (("raw_path", "raw_sha256"), ("text_path", "text_sha256")):
                if path_key in tool:
                    retained.append({"path": tool[path_key], "sha256": tool.get(hash_key)})
            for raw in retained:
                source = Path(str(raw.get("path", "")))
                if not source.is_file() or sha256(source) != raw.get("sha256"):
                    die(f"capture snapshot missing or corrupt: {source}")
            records.append(item)
    records.sort(key=lambda item: item.get("captured_at", ""))
    return records


def dependency_coverage(classifications: dict, captures: list[dict], attributed: list[Path],
                        remote_rows: frozenset[str], vault: Path) -> dict:
    known = {str(path) for path in attributed}
    requested: set[str] = set()
    for capture in captures:
        source = capture.get("source")
        if isinstance(source, str) and source.startswith(("/", "~/")):
            known.add(str(canonical_path(source.split("#", 1)[0], vault)))
        requested.update(str(canonical_path(raw, vault)) for raw in capture.get("dependencies", []))
    for path in attributed:
        entry = classifications.get(str(path), {})
        requested.update(str(canonical_path(raw, vault)) for raw in entry.get("dependencies", []))
        for target in entry.get("inspection_targets", []):
            tokens = re.findall(r"`([^`]+)`", target)
            tokens += re.findall(r"(?:^|\s)((?:/|~/)[^\s`]+)", target)
            for token in tokens:
                token = token.rstrip(".,;)").split("#", 1)[0]
                if (not REMOTE_PATH_RE.match(token)
                        and re.search(r"\.(?:md|txt|py|sh|json|jsonl|yaml|yml|toml|pdf|html|js|ts|css|csv|tsv|xml)$", token, re.I)):
                    requested.add(str(canonical_path(token, vault)))
    mutations = {item.get("mutation", {}).get("path") for item in captures
                 if isinstance(item.get("mutation"), dict)
                 and item["mutation"].get("command") and item["mutation"].get("cwd")
                 and type(item["mutation"].get("exit_status")) is int}
    return {"requested": sorted(requested), "covered": sorted(requested & known),
            "missing": sorted(requested - known), "missing_remote_mutation": sorted(remote_rows - mutations)}


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
                "read_path": item.get("review_path", item["snapshot_path"]),
                "media_type": item.get("media_type", "text/plain"),
                "review_sha256": item.get("review_sha256", digest),
                "hash_path": item["snapshot_path"],
                "paths": [],
                "reasons": [],
            }
        group = groups[digest]
        group["paths"].append(item["path"])
        reason = item.get("reason", "meaning-bearing change")
        if reason not in group["reasons"]:
            group["reasons"].append(reason)
    return [groups[digest] for digest in order]


def validated_artifact_receipt(path: Path, digest: str, classification: dict) -> dict:
    """Validate the immutable source and optional review copy recorded at classification."""
    artifact = classification.get("artifact")
    if not isinstance(artifact, dict) or artifact.get("source_sha256") != digest:
        die(f"artefact classification is stale for {path}; rerun classify")
    source_snapshot = Path(str(artifact.get("source_snapshot", "")))
    if not source_snapshot.is_file() or sha256(source_snapshot) != digest:
        die(f"artefact source snapshot missing or corrupt: {source_snapshot}")
    review_raw = artifact.get("review_path")
    review_digest = artifact.get("review_sha256")
    if review_raw is not None or review_digest is not None:
        review_path = Path(str(review_raw))
        if (
            not isinstance(review_digest, str)
            or not review_path.is_file()
            or sha256(review_path) != review_digest
        ):
            die(f"artefact review copy missing or corrupt: {review_path}")
    return artifact


def cmd_build(args: argparse.Namespace) -> int:
    sid, root, receipt_root, audit_root = state_paths(args.session_id)
    vault = canonical_path(args.vault)
    log = canonical_path(args.session_log, vault)
    log_snapshot_at = now()
    log_bytes = log.read_bytes()
    log_text = decode_utf8(log_bytes, log)
    block, sections = extract_session_text(log_text, args.number, log)
    manifest_path = root / "files.json"
    classifications = classification_registry(load_json(manifest_path, {}), vault)
    created_rows = parse_file_rows(
        sections.get("Files Created", ""), vault, classifications
    )
    updated_rows = parse_file_rows(
        sections.get("Files Updated", ""), vault, classifications
    )
    deleted_rows = parse_file_rows(
        sections.get("Files Deleted", ""), vault, classifications
    )
    # A row annotated (deleted) in any list names a path that is gone; a row
    # annotated (remote) names one the build must never read.
    created_raw = [path for path, note in created_rows if note != "deleted"]
    updated_raw = [path for path, note in updated_rows if note != "deleted"]
    deleted_raw = [path for path, _ in deleted_rows] + [
        path for path, note in created_rows + updated_rows if note == "deleted"
    ]
    remote_rows = frozenset(
        path for path, note in created_rows + updated_rows if note == "remote"
    )
    descriptions: dict[str, list[str]] = {}
    for line in (sections.get("Files Created", "") + "\n" + sections.get("Files Updated", "")).splitlines():
        for raw, note in parse_file_rows(line, vault, classifications):
            if note not in ("deleted", "remote"):
                descriptions.setdefault(str(canonical_path(raw, vault)), []).append(line)

    created = {canonical_path(path, vault) for path in created_raw}
    local_paths, external_files = partition_attributed_paths(
        created_raw + updated_raw, vault, classifications, remote_rows
    )
    attributed_paths = []
    for raw in created_raw + updated_raw:
        physical = canonical_path(raw, vault)
        if physical in local_paths:
            item = {"path": str(lexical_path(raw, vault)), "physical_path": str(physical)}
            if item not in attributed_paths:
                attributed_paths.append(item)

    full_read: list[dict] = []
    targeted_review: list[dict] = []
    mechanical: list[dict] = []
    reused: list[dict] = []
    warnings: list[str] = []
    current_audits = current_audit_receipts(audit_root)
    captured_bytes = {log: log_bytes}
    snapshot_times = {log: log_snapshot_at}
    for path in local_paths:
        if not path.is_file():
            die(f"attributed local file is missing: {path}")
        classification = classifications.get(str(path))
        data = captured_bytes.get(path)
        snapshot_times.setdefault(path, now())
        digest = sha256_bytes(data) if data is not None else sha256(path)
        if isinstance(classification, dict) and classification.get("sha256_at_classification") not in (None, digest):
            die(f"classification is stale for {path}; reclassify current bytes before build")
        if isinstance(classification, dict) and (
            classification.get("mode") == "reference"
            or (classification.get("mode") == "semantic"
                and classification.get("inspection_scope") == "targeted")
        ):
            artifact = validated_artifact_receipt(path, digest, classification)
            targeted_review.append({
                "path": str(path), "sha256": digest, "kind": classification.get("mode"),
                "reason": classification.get("reason", "bounded inspection"),
                "inspection_targets": classification.get("inspection_targets", []),
                **{key: artifact.get(key) for key in (
                    "source_snapshot", "media_type", "bytes", "pages", "review_path",
                    "review_sha256", "review_lines", "text_status", "receipt_path")},
            })
            continue
        binary_receipt = (classification.get("artifact") if isinstance(classification, dict) else None)
        binary_receipt = (binary_receipt if isinstance(binary_receipt, dict)
                          and binary_receipt.get("media_type") not in TEXT_REVIEW_MEDIA_TYPES else None)
        automatic_proof = None
        if classification is None and path != log:
            if path not in created:
                automatic_proof = forward_link_proof(vault, path, sid)
            if not automatic_proof or automatic_proof.get("post_sha256") != digest:
                with path.open("rb") as handle:
                    prefix = handle.read(8192)
                kind = "non-text artefact" if is_binary_artifact(prefix) or not file_is_utf8(path) else "file"
                die(f"unclassified {kind}: {path}; use classify --reference for imported sources, "
                    "--semantic for authored work, or --semantic --targeted with inspection targets")
        if data is None:
            if binary_receipt is None:
                data = path.read_bytes()
        snapshot_at = snapshot_times[path]
        if classification is None and path != log and path not in created:
            proof = automatic_proof
            if proof and proof['post_sha256'] == digest and not lint_errors(proof['inserted_line']):
                verification = {'ok': True, 'failures': [], 'replacements': [],
                    'targets': [target_check(p['target_log'], vault) for p in proof['receipts']],
                    'separator_clean': True, 'lint_clean': True,
                    'accepted_inherited_lint': bool(lint_errors(decode_utf8(data, path))),
                    'receipts': [{'path': p['receipt_path'],
                        'pre_sha256': p['pre_sha256'], 'post_sha256': p['post_sha256'],
                        'changed_ranges': [{'insertion_offset': p['insertion_offset']}],
                        'unified_diff': '+ ' + p['inserted_line']} for p in proof['receipts']]}
                mechanical.append({'path': str(path), 'sha256': digest, 'verification': verification})
                continue
        if classification is None and path != log:
            kind = "non-text artefact" if data is not None and (is_binary_artifact(data) or not is_utf8(data)) else "file"
            die(f"unclassified {kind}: {path}; use classify --reference for imported sources, "
                "--semantic for authored work, or --semantic --targeted with inspection targets")
        if (classification and classification.get("mode") == "semantic"
                and classification.get("inspection_scope", "full") == "full" and path not in created
                and is_within(path, vault / "06 Archive")
                and not classification.get("full_read_confirmed")
                and re.search(r"continuation|continued|supersession|banner|forward.link",
                              classification.get("reason", "") + "\n" + "\n".join(descriptions.get(str(path), [])),
                              re.IGNORECASE)):
            die(f"historical continuation-only file needs explicit coverage confirmation: {path}; "
                "classify --semantic --targeted with inspection targets, or --confirm-full-read")
        # A clean receipt for these exact bytes covers created files too.
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
        if path in created:
            (
                snapshot_digest,
                snapshot_path,
                review_path,
                review_digest,
                review_text,
                media_type,
            ) = (
                semantic_review_copy(root, vault, path, data, classification)
            )
            full_read.append(
                {
                    "path": str(path),
                    "sha256": snapshot_digest,
                    "snapshot_path": str(snapshot_path),
                    "review_path": str(review_path),
                    "review_sha256": review_digest,
                    "media_type": media_type,
                    "snapshot_at": snapshot_at,
                    "reason": "created this session",
                    "owned_locators": [review_text] if review_text else [],
                    "owned_locators_complete": True,
                }
            )
            continue
        if isinstance(classification, dict) and classification.get("mode") == "mechanical":
            if classification.get("mechanical_kind") == "obsidian-link-heal":
                verification = verify_move_heal(
                    path, vault, classification.get("proof", {})
                )
            elif classification.get("mechanical_kind") == "obsidian-link-heal-chain":
                verification = verify_move_heal_chain(path, vault, classification.get("proof", {}))
            elif classification.get("mechanical_kind") == "native-move-preserved":
                verification = verify_preserved_move(
                    path, vault, classification.get("proof", {}),
                    receipt_root.parent / f"{sid}.project-move-receipts")
            else:
                verification = verify_mechanical(
                    path,
                    vault,
                    classification.get("replacements", []),
                    classification.get("targets", []),
                    receipt_root,
                    allow_inherited_lint=bool(
                        classification.get("verification", {}).get(
                            "accepted_inherited_lint"
                        )
                    ),
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
                if is_binary_artifact(data) or not is_utf8(data):
                    die(f"unclassified non-text artefact: {path}; use classify --reference "
                        "for imported sources, --semantic for a bounded authored output, "
                        "or --semantic --targeted with inspection targets")
                warnings.append(f"defaulted unclassified file to semantic: {path}")
            (
                snapshot_digest,
                snapshot_path,
                review_path,
                review_digest,
                snapshot_text,
                media_type,
            ) = (
                semantic_review_copy(root, vault, path, data, classification)
            )
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
                    "review_path": str(review_path),
                    "review_sha256": review_digest,
                    "media_type": media_type,
                    "snapshot_at": snapshot_at,
                    "reason": reason,
                    "owned_locators": locators,
                    "owned_locators_complete": locators_complete,
                }
            )

    captures = load_captures(root)
    generation = root.name if (root / "run.json").is_file() else None
    if any(item.get("run_generation") != generation for item in captures):
        die("capture belongs to a different park generation; recapture for this run")
    evidence = [item for item in captures if item.get("kind") == "evidence"]
    prestate = [item for item in captures if item.get("kind") == "prestate"]
    propagation_items = [item for item in captures if item.get("kind") == "propagation"]
    verifier_items = [item for item in captures if item.get("kind") == "verifier"]
    if not propagation_items:
        die("no propagation receipt; capture the agent report or the checked nil result")
    if not verifier_items:
        die("no verifier receipt; run park-verify through run-verifier")
    propagation = propagation_items[-1]
    propagation_coverage = validate_propagation_coverage(captures, propagation)
    dependencies = dependency_coverage(classifications, captures, local_paths, remote_rows, vault)
    if getattr(args, "check_dependencies", False) and (dependencies["missing"] or dependencies["missing_remote_mutation"]):
        die("Dependency coverage: " + json.dumps(dependencies, ensure_ascii=False))
    verifier = verifier_items[-1]
    if verifier.get("returncode") not in (None, 0):
        die("latest verifier receipt records a failing exit status")

    sources: dict[str, list[dict]] = {}
    for item in evidence:
        source = item.get("source")
        provenance = item.get("provenance")
        if not source or provenance not in ("primary", "secondary", "unverified"):
            die(f"malformed evidence receipt: {item.get('_path', 'unknown')}")
        sources.setdefault(source, []).append(item)
    embedded_excerpts = sum(len(items) for items in sources.values())

    ledger_path = (
        Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
        / ".session-state"
        / f"{sid}.tsv"
    )
    ledger = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else "NOTE: no ledger"

    read_groups = group_full_reads(full_read)
    digests = {item["path"]: item["sha256"]
               for item in [*full_read, *targeted_review, *mechanical, *reused]}
    modes = {item["path"]: label for rows, label in ((full_read, "semantic"),
             (mechanical, "mechanical"), (reused, "receipt-reuse")) for item in rows}
    modes.update({item["path"]: item["kind"] + "-targeted" for item in targeted_review})
    alias_lines = [f"- `{item['path']}` -> `{item['physical_path']}`; "
                   f"SHA-256 `{digests[item['physical_path']]}`; mode "
                   f"`{modes[item['physical_path']]}`"
                   for item in attributed_paths]
    requested = {str(path) for path in local_paths}
    registry_paths = {key for key in classifications if not key.startswith("external::")}
    classification_coverage = {"requested": sorted(requested), "registered": sorted(requested & registry_paths),
                               "automatic": sorted(requested - registry_paths),
                               "unused": sorted(registry_paths - requested)}
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
        "## Lexical aliases and physical identities",
        "",
        *alias_lines,
        "",
        "## Review modes",
        "",
        "The modes below are mechanically derived from the post-backfill Files lists, "
        "immutable snapshots, locked-edit receipts, and prior clean audit receipts.",
        "",
        "### Bounded semantic files — full coherence read",
        "",
    ]
    if read_groups:
        for group in read_groups:
            reasons = "; ".join(group["reasons"])
            if group["media_type"] in TEXT_REVIEW_MEDIA_TYPES:
                group["lines"] = count_lines(Path(str(group["read_path"])))
                lines.append(
                    f"- Read immutable review copy once: `{group['read_path']}` — "
                    f"lines `{group['lines']}` — "
                    f"review-copy SHA-256 `{group['review_sha256']}` — "
                    f"verify source bytes at `{group['hash_path']}` → `{group['sha256']}` — {reasons}"
                )
            else:
                group["bytes"] = Path(str(group["read_path"])).stat().st_size
                lines.append(
                    f"- Inspect immutable binary snapshot once: `{group['read_path']}` — "
                    f"media type `{group['media_type']}` — bytes `{group['bytes']}` — "
                    f"SHA-256 `{group['sha256']}` — {reasons}"
                )
            lines.append("  - Original path(s) covered by this snapshot:")
            for path in group["paths"]:
                lines.append(f"    - `{path}`")
    else:
        lines.append("None")

    lines.extend(
        [
            "",
            "### Reference and large semantic artefacts — bounded inspection only",
            "",
        ]
    )
    if targeted_review:
        for item in targeted_review:
            lines.extend(
                [
                    f"#### `{item['path']}`",
                    "",
                    f"Kind: `{item['kind']}`; reason: {item['reason']}",
                    f"Source snapshot: `{item['source_snapshot']}`; SHA-256 `{item['sha256']}`",
                    f"Media type: `{item['media_type']}`; bytes: `{item['bytes']}`; "
                    f"pages: `{item['pages']}`; extracted text: `{item['text_status']}`; "
                    f"review lines: `{item['review_lines']}`",
                    f"Review copy: `{item['review_path']}`; review SHA-256 `{item['review_sha256']}`",
                    "Inspection target(s):",
                ]
            )
            targets = item.get("inspection_targets") or []
            if targets:
                for target in targets:
                    lines.append(f"- {target}")
            else:
                lines.append(
                    "- Identity and metadata only; no session claim requires source-content review."
                )
            lines.append("")
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
            consumed = (f"; consumed by same-run chain -> `{check['effective_new']}`; "
                        f"final count {check['effective_new_count']}"
                        if check.get("effective_new", check["new"]) != check["new"] else "")
            lines.append(
                f"- `{check['old']}` → `{check['new']}`; old count {check['old_count']}; "
                f"new count {check['new_count']}" + consumed
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
        for source, items in sources.items():
            for index, item in enumerate(items, start=1):
                heading = f"### [{item['provenance']}] {item['label']} — `{source}`"
                if len(items) > 1:
                    heading += (
                        f" (receipt {index} of {len(items)}, captured "
                        f"{item.get('captured_at', 'unknown')}; all receipts for this "
                        "source are cumulative)"
                    )
                lines.extend([heading, "", fenced(item["text"]), ""])
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
            "## Checklist for this audit pass",
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
            "- Each `Read immutable review copy once` row under **Bounded semantic files — full coherence read** is one byte-identity group. "
            "Read only the review-copy path in that row; do not open the live original. "
            "Use bounded line ranges covering line 1 through the stated line count, including a final "
            "unterminated line. Report the ranges read; retry a truncated range in smaller chunks. "
            "Run `sha256sum` on the listed source-bytes path and return that SHA-256.",
            "- Each `Inspect immutable binary snapshot once` row in that section is a session-authored "
            "non-text artefact. Do not read it as text or by line range, and do not open the live original. "
            "Run `sha256sum` on the snapshot path and return that SHA-256, then inspect the whole snapshot "
            "with a tool suited to the stated media type: render an image, or list an archive's members and "
            "read those a session claim depends on. Report the tool used and what it showed. A snapshot you "
            "cannot inspect that way is a coverage gap, not a clean read.",
            "- Include exactly one machine-readable attestation line for every original path represented "
            "by those groups: `ATTEST <sha256> <absolute-original-path>`. Byte-identical aliases are attested but "
            "not reread. Do not wrap either field in backticks and do not leave trailing whitespace.",
            "- Do not reread files backed by a matching clean audit receipt.",
            "- For **Reference and large semantic artefacts**, verify the immutable source hash and, when present, the review-copy hash, "
            "then inspect only the listed targets needed to test session claims. Do not read the whole artefact merely "
            "because it was copied, downloaded, indexed, or touched. A complete text extraction is an index, not evidence "
            "that every page was reviewed. `empty` or `unsupported` text status proves no text coverage; use bounded "
            "format-specific rendering or OCR only when a listed target depends on it.",
            "- For mechanical-only files, review only the embedded locked-edit receipts, exact checks, "
            "and changed spans. Do not open or full-read those files.",
            "- Treat non-local paths only through embedded evidence. Use the propagation report for "
            "reference-graph coverage; do not repeat vault-wide searches.",
            "- Script probes: run a command only after reading its argument handling and establishing "
            "that the invocation is read-only. Otherwise copy its required inputs into a disposable scratch directory outside the vault "
            "and installed config, redirect all output/state there, and probe only that fixture. "
            "--help is not evidence of a read-only command. If isolation cannot be established, inspect "
            "the source and report the execution check unverified; never weaken host policy or bypass a missing sandbox.",
            "- Make no edits to reviewed originals or live state. Use no web, network, SSH, remote hosts, sub-agents, skill maintenance, "
            "or adjacent cleanup. Review this snapshot in one scoped pass. The main session applies "
            "confirmed fixes and sends a rebuilt brief for re-audit; repeat the full checklist on each "
            "new brief until a pass is clean. Do not treat a prior pass or a promised fix as evidence "
            "that the current snapshot is clean.",
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
            "concrete fix (a fix to a path already in the file list is stated as `<path>: description extension: <text>`), "
            "or one evidence-bearing clean line; files read with SHA-256; commands and quoted "
            "outputs; coverage gaps; and the required `ATTEST` line for every full-read file. Finish with "
            "a separate `COMPLETE <SHA-256 of this brief's exact bytes>` line (compute the digest or use the "
            "digest supplied by the parent). Every new completion requires this binding, including "
            "full-read reviews; it does not attest a targeted artefact as full-read. Then finish with "
            "exactly one line: `Terminal state: clean`, "
            "`Terminal state: findings`, or `Terminal state: incomplete`.",
        ]
    )

    brief = "\n".join(lines).rstrip() + "\n"
    out = canonical_path(args.out) if args.out else root / "review-brief.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(out, brief.encode("utf-8"))
    brief_manifest = {
        "schema": 3,
        "completion_binding": 1,
        "run_generation": root.name if (root / "run.json").is_file() else None,
        "built_at": now(),
        "brief": str(out),
        "vault": str(vault),
        "session_log": str(log),
        "session_number": args.number,
        "session_block_sha256": sha256_bytes(block.rstrip("\n").encode("utf-8")),
        "session_block_normalisation": "trailing-lf",
        "brief_sha256": sha256(out),
        "classification_sha256": sha256(manifest_path) if manifest_path.is_file() else None,
        "capture_files": [{"path": item["_path"], "sha256": sha256(Path(item["_path"]))}
                          for item in captures],
        "attributed_paths": attributed_paths,
        "classification_coverage": classification_coverage,
        "full_read": full_read,
        "targeted_review": targeted_review,
        "mechanical": [{"path": item["path"], "sha256": item["sha256"]} for item in mechanical],
        "reused": reused,
        "external": external_files,
        "deleted": deleted_raw,
        "propagation_coverage": propagation_coverage,
        "dependency_coverage": dependencies,
        "tool_source_index_sha256": sha256(root / "tool-source-index.json") if (root / "tool-source-index.json").is_file() else None,
    }
    atomic_json(root / "review-brief-manifest.json", brief_manifest)
    atomic_json(root / "completion-binding.json", {
        "protocol": 1, "run_generation": generation, "brief_sha256": brief_manifest["brief_sha256"],
        "manifest_sha256": sha256(root / "review-brief-manifest.json"),
    })
    print(f"Reviewer brief: {out}")
    print(f"Reviewer brief SHA-256: {sha256(out)}")
    print(
        f"Out-of-band evidence: sources drawn on {len(sources)} → excerpts embedded {embedded_excerpts}"
    )
    print(
        f"Review modes: bounded-full {len(full_read)} path(s) in {len(read_groups)} read(s) | targeted {len(targeted_review)} | mechanical {len(mechanical)} | "
        f"receipt-reuse {len(reused)} | non-local {len(external_files)} | deleted {len(deleted_raw)}"
    )
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print("Dependency coverage: " + json.dumps(dependencies, ensure_ascii=False))
    print(f"Classification coverage: requested {len(requested)}; registered {len(requested & registry_paths)}; "
          f"automatic {len(requested - registry_paths)}; unused registry entries {len(registry_paths - requested)} (see manifest)")
    return 0


def validate_completion_manifest(manifest: dict, root: Path, report: str) -> list[dict]:
    """Bind completion to the prepared packet without inventing full-read reuse."""
    full_read = manifest.get("full_read", [])
    if not isinstance(full_read, list):
        die("malformed full-read manifest")
    brief_digest = manifest.get("brief_sha256")
    binding_path = root / "completion-binding.json"
    run = load_json(root / "run.json", {})
    bound = (manifest.get("schema") == 3 or "completion_binding" in manifest
             or "brief_sha256" in manifest or "capture_files" in manifest
             or binding_path.exists() or isinstance(run, dict) and run.get("completion_protocol") == 1)
    if bound:
        binding = load_json(binding_path, None)
        if (manifest.get("schema") != 3 or manifest.get("completion_binding") != 1
                or not isinstance(binding, dict) or binding.get("protocol") != 1
                or binding.get("run_generation") != manifest.get("run_generation")
                or binding.get("manifest_sha256") != sha256(root / "review-brief-manifest.json")
                or binding.get("brief_sha256") != brief_digest):
            die("missing, malformed or changed completion binding; rebuild brief")
    if bound or brief_digest is not None or not full_read:
        brief = Path(str(manifest.get("brief", "")))
        if (not isinstance(brief_digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", brief_digest)
                or not brief.is_file() or sha256(brief) != brief_digest):
            die("review brief changed or is missing; rebuild brief")
        completions = COMPLETE_RE.findall(report)
        if (bound or completions or not full_read) and completions != [brief_digest]:
            die("missing, duplicate or stale completion attestation; expected COMPLETE " + brief_digest)
    if "capture_files" in manifest:
        expected = manifest["capture_files"]
        if not isinstance(expected, list):
            die("malformed review input manifest")
        current = [{"path": item["_path"], "sha256": sha256(Path(item["_path"]))}
                   for item in load_captures(root)]
        if current != expected:
            die("review inputs changed after build; rebuild brief")
        registry = root / "files.json"
        digest = sha256(registry) if registry.is_file() else None
        if digest != manifest.get("classification_sha256"):
            die("classification inputs changed after build; rebuild brief")
        source_index = root / "tool-source-index.json"
        index_digest = sha256(source_index) if source_index.is_file() else None
        if index_digest != manifest.get("tool_source_index_sha256"):
            die("tool source index inputs changed after build; rebuild brief")
    if "session_block_sha256" in manifest:
        try:
            block, _ = extract_session(Path(manifest["session_log"]), manifest["session_number"])
        except (KeyError, OSError, TypeError):
            die("review session block is missing or malformed")
        if manifest.get("session_block_normalisation") == "trailing-lf":
            block = block.rstrip("\n")
        if sha256_bytes(block.encode("utf-8")) != manifest["session_block_sha256"]:
            die("session block changed after review; rebuild brief")
    for item in manifest.get("attributed_paths", []):
        if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                or not isinstance(item.get("physical_path"), str)):
            die("malformed attributed alias mapping")
        alias = Path(item["path"])
        if not alias.is_file() or str(canonical_path(str(alias))) != item["physical_path"]:
            die(f"attributed alias changed after review: {alias}")
    completion_files: list[dict] = []
    for key in ("targeted_review", "mechanical", "reused"):
        entries = manifest.get(key, [])
        if not isinstance(entries, list):
            die(f"malformed {key} manifest")
        for item in entries:
            if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                    or not Path(item["path"]).is_absolute()
                    or not isinstance(item.get("sha256"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                die(f"malformed {key} file in review manifest")
            path = canonical_path(item["path"])
            if not path.is_file():
                die(f"completion file missing: {path}")
            if key == "targeted_review":
                snapshot = Path(str(item.get("source_snapshot", "")))
                if not snapshot.is_file() or sha256(snapshot) != item["sha256"]:
                    die(f"review snapshot missing or corrupt: {snapshot}")
                review_raw, review_digest = item.get("review_path"), item.get("review_sha256")
                if review_raw is not None or review_digest is not None:
                    review = Path(str(review_raw))
                    if (not isinstance(review_digest, str) or not review.is_file()
                            or sha256(review) != review_digest):
                        die(f"review copy missing or corrupt: {review}")
            # The declared targets may include a DIFFERENT pre-existing Session N.
            # An unchanged subject block alone cannot prove those targets survived.
            # Tolerate only a byte-preserving append of fresh session records.
            scoped_log = (str(path) == manifest.get("session_log")
                          and "session_block_sha256" in manifest)
            current = sha256(path)
            appended_session = (scoped_log and key == "targeted_review"
                                and current != item["sha256"]
                                and snapshot_preserved_with_new_sessions(snapshot, path))
            if current != item["sha256"] and not appended_session:
                die(f"completion file changed after review: {path}")
            completion_files.append({"path": str(path), "sha256": item["sha256"],
                                     "live_sha256": current, "mode": key})
    return completion_files


def snapshot_preserved_with_new_sessions(snapshot: Path, live: Path) -> bool:
    """Prove a log append without interpreting free-text inspection targets."""
    heading = re.compile(rb"^## Session ([0-9]+)(?:[ \t\r\n]|$)")
    seen: set[bytes] = set()
    last_byte = b""
    with snapshot.open("rb") as prior, live.open("rb") as current:
        for line in prior:
            if current.read(len(line)) != line:
                return False
            last_byte = line[-1:]
            match = heading.match(line)
            if match:
                seen.add(match.group(1).lstrip(b"0") or b"0")
        # A previously unterminated line must end before a fresh heading starts.
        if last_byte and last_byte != b"\n" and current.readline(3) not in (b"\n", b"\r\n"):
            return False
        added_session = False
        for line in current:
            match = heading.match(line)
            if not added_session and line.strip() and not match:
                return False
            if match:
                number = match.group(1).lstrip(b"0") or b"0"
                if number in seen:
                    return False
                seen.add(number)
                added_session = True
        return added_session


def cmd_record_audit(args: argparse.Namespace) -> int:
    _, root, receipt_root, audit_root = state_paths(args.session_id)
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
    completion_files: list[dict] = []
    if args.from_brief:
        manifest = load_json(root / "review-brief-manifest.json", None)
        if not isinstance(manifest, dict):
            die("no review brief manifest; run build first")
        generation = root.name if (root / "run.json").is_file() else None
        if manifest.get("run_generation") != generation:
            die("review brief belongs to a different park generation; run build first")
        files.extend(manifest.get("full_read", []))
        built_at = manifest.get("built_at", built_at)
        if vault is None and isinstance(manifest.get("vault"), str):
            vault = canonical_path(manifest["vault"])
        completion_files = validate_completion_manifest(manifest, root, report)
    for raw in args.file or []:
        path = canonical_path(raw, vault)
        if not path.is_file():
            die(f"audited file missing: {path}")
        files.append({"path": str(path), "sha256": sha256(path)})
    dedup: dict[str, dict] = {item["path"]: item for item in files}
    files = list(dedup.values())
    if not files and not args.from_brief:
        # Exit zero must always name a saved receipt.
        die("no audited files; use --file or a current --from-brief review")
    validate_report_attestations(report, files)
    state_root = receipt_root.parent
    reusable: list[dict] = []
    post_review_changes: list[dict] = []
    live_hashes: dict[str, str] = {}
    paths = [canonical_path(item["path"]) for item in files + completion_files]
    with vault_file_locks(paths, vault):
        for item in completion_files:
            path = canonical_path(item["path"])
            if not path.is_file() or sha256(path) != item["live_sha256"]:
                die(f"completion file changed after review validation: {path}")
            live_hashes[str(path)] = item["live_sha256"]
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
            review_path = Path(item.get("review_path", snapshot))
            review_digest = item.get("review_sha256", item["sha256"])
            if not review_path.is_file() or sha256(review_path) != review_digest:
                die(f"review copy missing or corrupt: {review_path}")
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
            if any(
                entry.get("_receipt_root") == str(receipt_root.resolve())
                for entry in chain
            ):
                die(f"audited session changed file after review snapshot; rebuild brief: {path}")
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
            "schema": 3,
            "run_generation": root.name if (root / "run.json").is_file() else None,
            "captured_at": now(),
            "status": "pending",
            "reviewer": args.reviewer,
            "files": reusable,
            "reviewed_files": files,
            "completion_files": completion_files,
            "post_review_changes": post_review_changes,
            "report_sha256": hashlib.sha256(report.encode()).hexdigest(),
            "report": report,
            "kind": ("completion" if manifest is not None and manifest.get("completion_binding") == 1
                     else "legacy-review" if manifest is not None else "source-attestation"),
            "completion": bool(manifest is not None and manifest.get("completion_binding") == 1),
        }
        if manifest is not None:
            manifest_digest, manifest_snapshot = write_snapshot(
                root, (root / "review-brief-manifest.json").read_bytes())
            receipt.update({
                "completion_binding": manifest.get("completion_binding"),
                "session_log": manifest.get("session_log"),
                "session_number": manifest.get("session_number"),
                "brief_sha256": manifest.get("brief_sha256"),
                "manifest_sha256": manifest_digest,
                "manifest_snapshot": str(manifest_snapshot),
            })
            if manifest.get("brief_sha256"):
                _, brief_snapshot = write_snapshot(root, Path(manifest["brief"]).read_bytes())
                receipt["brief_snapshot"] = str(brief_snapshot)
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
        if manifest is not None and manifest.get("brief_sha256"):
            # Captures, classification and immutable review inputs are evidence
            # too: a late mutation cannot leave a reusable clean receipt.
            validate_completion_manifest(manifest, root, report)
        receipt["status"] = "clean"
        receipt["completed_at"] = now()
        atomic_json(path, receipt)
    print(
        f"Audit receipt: {path} ({len(files)} snapshot-reviewed file(s); "
        f"{len(reusable)} live-reusable)"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", help="override harness session id")
    subparsers = parser.add_subparsers(dest="command_name", required=True)
    begin = subparsers.add_parser("begin-run", help="start a fresh park generation for this session")
    begin.set_defaults(func=cmd_begin_run)

    classify = subparsers.add_parser("classify", help="classify and verify a touched file")
    classify.add_argument("--vault", required=True)
    classify.add_argument("--path", required=True)
    mode = classify.add_mutually_exclusive_group(required=True)
    mode.add_argument("--semantic", action="store_true")
    mode.add_argument("--reference", action="store_true")
    mode.add_argument("--mechanical", action="store_true")
    mode.add_argument("--nonlocal", dest="non_local", action="store_true")
    classify.add_argument("--reason")
    classify.add_argument("--dependency", action="append", help="local supporting file that must be attributed or captured")
    classify.add_argument("--confirm-full-read", action="store_true",
                          help="explicitly confirm a whole coherence read for historical continuation-only text")
    classify.add_argument(
        "--targeted",
        action="store_true",
        help="use bounded target inspection for a large semantic artefact",
    )
    classify.add_argument(
        "--inspection-target",
        action="append",
        help="page, section, line range, or claim to inspect; repeat as needed",
    )
    classify.add_argument("--replace", nargs=2, action="append", metavar=("OLD", "NEW"))
    classify.add_argument("--target", action="append")
    classify.add_argument(
        "--no-locator-target",
        action="store_true",
        help=(
            "declare that no --replace pair in this --mechanical call is a locator, "
            "so there is no destination to validate; required when --target is omitted"
        ),
    )
    classify.add_argument(
        "--allow-inherited-lint",
        action="store_true",
        help=(
            "permit pre-existing whole-file lint only after every delta is proven "
            "an exact declared mechanical replacement"
        ),
    )
    classify.set_defaults(func=cmd_classify)

    import_heals = subparsers.add_parser(
        "import-move-heals",
        help="verify and import link healing from current-session move receipts",
    )
    import_heals.add_argument("--vault", required=True)
    import_heals.set_defaults(func=cmd_import_move_heals)

    import_preserved = subparsers.add_parser(
        "import-move-preserved", help="verify one complete unchanged native move receipt")
    import_preserved.add_argument("--vault", required=True)
    import_preserved.add_argument("--path", required=True)
    import_preserved.add_argument("--receipt", required=True)
    import_preserved.set_defaults(func=cmd_import_preserved_move)

    capture = subparsers.add_parser("capture", help="capture review evidence immediately")
    capture.add_argument(
        "--kind", required=True, choices=("evidence", "prestate", "propagation", "enumeration")
    )
    capture.add_argument("--label", required=True)
    capture.add_argument("--source")
    capture.add_argument("--dependency", action="append", help="local supporting file that must be attributed or captured")
    capture.add_argument("--mutation-for", help="exact (remote) Files-row path supported by this command evidence")
    capture.add_argument("--command", help="literal mutation command for --mutation-for")
    capture.add_argument("--cwd", help="absolute working directory for --mutation-for")
    capture.add_argument("--exit-status", type=int, help="actual mutation command exit status")
    capture.add_argument("--raw-file", help="retain complete raw bytes with LF/per-file record counts")
    capture.add_argument(
        "--provenance", choices=("primary", "secondary", "unverified")
    )
    capture.set_defaults(func=cmd_capture)

    tools_capture = subparsers.add_parser("capture-tools", help="capture/index native JSONL tool returns and literal supporting passages")
    tools_capture.add_argument("--transcript", required=True)
    tools_capture.add_argument("--claims-file", help="JSON list of source/passage[/call_id/provenance] declarations")
    tools_capture.set_defaults(func=cmd_capture_tools)

    run_verifier = subparsers.add_parser(
        "run-verifier", help="run and capture park-verify without losing its exit status"
    )
    run_verifier.add_argument("--label", default="park-verify")
    run_verifier.add_argument(
        "--accept-inherited-lint",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "accept a verifier exit 1 only when its sole failure is inherited lint "
            "in exactly the named path(s); repeat for each path"
        ),
    )
    run_verifier.add_argument("command", nargs=argparse.REMAINDER)
    run_verifier.set_defaults(func=cmd_run_verifier)

    build = subparsers.add_parser("build", help="generate the bounded reviewer brief")
    build.add_argument("--vault", required=True)
    build.add_argument("--session-log", required=True)
    build.add_argument("--number", required=True, type=int)
    build.add_argument("--out")
    build.add_argument("--check-dependencies", action="store_true", help="fail if cited local dependencies or remote mutation evidence are missing")
    build.set_defaults(func=cmd_build)

    audit = subparsers.add_parser(
        "record-audit", help="record a clean review and cache eligible full-file audits"
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
