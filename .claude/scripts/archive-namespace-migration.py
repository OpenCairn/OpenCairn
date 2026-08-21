#!/usr/bin/env python3
"""Inspect, rewrite, and verify the OpenCairn archive namespace migration."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys


OLD_TOKEN = "06 Archive/Claude"
NEW_TOKEN = "06 Archive/OpenCairn"
OLD_LOCATOR = f"{OLD_TOKEN}/"
NEW_LOCATOR = f"{NEW_TOKEN}/"
OLD_WINDOWS_TOKEN = OLD_TOKEN.replace("/", "\\")
NEW_WINDOWS_TOKEN = NEW_TOKEN.replace("/", "\\")
OLD_WINDOWS_LOCATOR = f"{OLD_WINDOWS_TOKEN}\\"
NEW_WINDOWS_LOCATOR = f"{NEW_WINDOWS_TOKEN}\\"
BARE_DELIMITERS = ('"', "'", "]", ")", "}", ">", ",", ";", ":")
LOCATOR_REPLACEMENTS = (
    (OLD_LOCATOR, NEW_LOCATOR),
    (OLD_WINDOWS_LOCATOR, NEW_WINDOWS_LOCATOR),
    *((OLD_TOKEN + delimiter, NEW_TOKEN + delimiter) for delimiter in BARE_DELIMITERS),
    *((OLD_WINDOWS_TOKEN + delimiter, NEW_WINDOWS_TOKEN + delimiter) for delimiter in BARE_DELIMITERS),
    (OLD_TOKEN + "\r\n", NEW_TOKEN + "\r\n"),
    (OLD_WINDOWS_TOKEN + "\r\n", NEW_WINDOWS_TOKEN + "\r\n"),
    (OLD_TOKEN + "\n", NEW_TOKEN + "\n"),
    ("\n" + OLD_TOKEN, "\n" + NEW_TOKEN),
    (OLD_WINDOWS_TOKEN + "\n", NEW_WINDOWS_TOKEN + "\n"),
    ("\n" + OLD_WINDOWS_TOKEN, "\n" + NEW_WINDOWS_TOKEN),
)
LOCATOR_PATTERN = re.compile(
    rf"(?:{re.escape(OLD_TOKEN)}(?=/|\r?$|[\"'\]\)\}}>,;:])|"
    rf"{re.escape(OLD_WINDOWS_TOKEN)}(?=\\|\r?$|[\"'\]\)\}}>,;:]))",
    flags=re.MULTILINE,
)
ARCHIVE_BUNDLE_VERSION = 3  # archive-bundle-v3
ROOT_NAMES = (
    "01 Now",
    "02 Inbox",
    "03 Projects",
    "04 Areas",
    "05 Resources",
    "06 Archive",
    "07 System",
)
TEXT_GLOBS = (
    "*.md",
    "*.md.*",
    "*.bak",
    "*.backup",
    "*.canvas",
    "*.sh",
    "*.py",
    "*.json",
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.txt",
    "*.csv",
    "*.tsv",
    "*.tex",
    "*.html",
    "*.css",
    "*.js",
    "*.ini",
    "*.conf",
    "*.xml",
    "*.org",
    "*.svg",
    "*.ipynb",
)
SEP = "========OPENCAIRN-LOCKED-EDIT-SEP========"
MIGRATION_ID = "archive-namespace-opencairn-v1"
JOURNAL = Path("07 System/.OpenCairn Migration/archive-namespace-opencairn-v1.json")
RECORD = Path("07 System/Migration Record.md")
JOURNAL_PHASES = {"in-progress", "complete"}
LEGACY_LOCATOR_EXEMPT_MARKER = "<!-- opencairn: legacy-locator-exempt -->"


def excluded(relative: Path) -> bool:
    parts = relative.parts
    if relative == Path("07 System/Migration Record.md"):
        return True
    if len(parts) >= 3 and parts[:2] == ("07 System", ".OpenCairn Migration"):
        return True
    if len(parts) >= 3 and parts[:2] == ("07 System", ".Provenance"):
        return True
    if (
        len(parts) >= 4
        and parts[0] == "06 Archive"
        and parts[1] in {"Claude", "OpenCairn"}
        and parts[2] == ".Session Transcripts"
    ):
        return True
    return relative.name.endswith(".lock")


def legacy_locator_exempt(path: Path) -> bool:
    return LEGACY_LOCATOR_EXEMPT_MARKER.encode() in path.read_bytes()


def matching_files(vault: Path, *, immutable: bool) -> list[Path]:
    matches: list[Path] = []
    for root_name in ROOT_NAMES:
        root = vault / root_name
        if not root.exists():
            continue
        for path in (vault / root_name).rglob("*"):
            if not path.is_file() or path.name.endswith(".lock"):
                continue
            try:
                relative = path.resolve().relative_to(vault)
            except ValueError as exc:
                raise RuntimeError(
                    f"legacy-locator search escaped the vault: {path}"
                ) from exc
            if excluded(relative) != immutable:
                continue
            if path.suffix and not any(
                fnmatch.fnmatch(path.name, pattern) for pattern in TEXT_GLOBS
            ):
                continue
            data = path.read_bytes()
            if b"\0" in data:
                continue
            if LEGACY_LOCATOR_EXEMPT_MARKER.encode() in data:
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                # Locator tokens are ASCII. Latin-1 preserves every byte so the
                # scan still reports the file and rewrite can fail explicitly.
                text = data.decode("latin-1")
            if LOCATOR_PATTERN.search(text):
                matches.append(path)
    return sorted(set(matches), key=lambda path: path.relative_to(vault).as_posix())


def protected_immutable_files(vault: Path) -> list[Path]:
    roots = [vault / "07 System/.Provenance"]
    old_archive = vault / OLD_TOKEN
    if not old_archive.is_symlink():
        roots.append(old_archive / ".Session Transcripts")
    roots.append(vault / NEW_TOKEN / ".Session Transcripts")
    files: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            root.resolve().relative_to(vault.resolve())
        except ValueError as exc:
            raise RuntimeError(
                f"protected immutable root resolves outside the vault: {root}"
            ) from exc
        for path in root.rglob("*"):
            if not path.is_file() or path.name.endswith(".lock"):
                continue
            try:
                path.resolve().relative_to(vault.resolve())
            except ValueError as exc:
                raise RuntimeError(
                    f"protected immutable file resolves outside the vault: {path}"
                ) from exc
            files.add(path)
    return sorted(files, key=lambda path: path.relative_to(vault).as_posix())


def physical_topology(vault: Path) -> str:
    old_path = vault / OLD_TOKEN
    new_path = vault / NEW_TOKEN
    if new_path.is_symlink():
        return "new-symlink-unsafe"
    if old_path.is_symlink():
        try:
            if new_path.is_dir() and old_path.samefile(new_path):
                return "legacy-symlink-alias"
        except OSError:
            pass
        return "legacy-symlink-unsafe"
    if new_path.exists() and not new_path.is_dir():
        return "new-path-unsafe"
    if old_path.exists() and not old_path.is_dir():
        return "legacy-path-unsafe"
    old_exists = old_path.is_dir()
    new_exists = new_path.is_dir()
    if old_exists and new_exists:
        return "split"
    if old_exists:
        return "old-root-only"
    if new_exists:
        return "new-root-only"
    return "no-root"


def layout(vault: Path, actionable_count: int) -> str:
    topology = physical_topology(vault)
    if topology == "old-root-only":
        return "old-only"
    if topology == "new-root-only":
        return "new-with-legacy-locators" if actionable_count else "new-only"
    if topology == "no-root":
        return "empty-with-legacy-locators" if actionable_count else "empty-clean"
    return topology


def migration_record_row(vault: Path) -> str | None:
    path = vault / RECORD
    if not path.is_file():
        return None
    rows = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| {MIGRATION_ID} |")
    ]
    if len(rows) > 1:
        raise RuntimeError(f"ambiguous migration rows for {MIGRATION_ID}")
    return rows[0] if rows else None


def has_canonical_complete_row(vault: Path) -> bool:
    row = migration_record_row(vault)
    if row is None:
        return False
    match = re.fullmatch(
        rf"\| {re.escape(MIGRATION_ID)} \| complete \| (\d{{4}}-\d{{2}}-\d{{2}}) \|",
        row,
    )
    if not match:
        return False
    try:
        dt.date.fromisoformat(match.group(1))
    except ValueError:
        return False
    return True


def gate_state(vault: Path) -> dict[str, object]:
    topology = physical_topology(vault)
    journal: dict[str, object] | None = None
    journal_phase = "absent"
    journal_error: str | None = None
    try:
        journal = load_journal(vault)
        if journal:
            journal_phase = str(journal["phase"])
    except RuntimeError as exc:
        journal_phase = "invalid"
        journal_error = str(exc)

    unsafe_topologies = {
        "split",
        "legacy-symlink-alias",
        "legacy-symlink-unsafe",
        "new-symlink-unsafe",
        "legacy-path-unsafe",
        "new-path-unsafe",
    }
    if topology in unsafe_topologies:
        return {
            "layout": topology,
            "actionable": "unknown",
            "journal_phase": journal_phase,
            "diagnostic": None,
        }
    if journal_error:
        return {
            "layout": "indeterminate",
            "actionable": "unknown",
            "journal_phase": journal_phase,
            "diagnostic": journal_error,
        }
    if journal and journal_phase == "in-progress":
        return {
            "layout": "pending-verification",
            "actionable": "unknown",
            "journal_phase": journal_phase,
            "diagnostic": None,
        }
    if journal and journal_phase == "complete":
        if topology == "new-root-only":
            return {
                "layout": "new-only",
                "actionable": 0,
                "journal_phase": journal_phase,
                "diagnostic": None,
            }
        return {
            "layout": "complete-journal-topology-mismatch",
            "actionable": "unknown",
            "journal_phase": journal_phase,
            "diagnostic": (
                f"complete migration journal conflicts with archive topology {topology}; "
                "inspect the archive paths and do not recreate or move either root automatically"
            ),
        }

    try:
        ledger_complete = has_canonical_complete_row(vault)
    except RuntimeError as exc:
        return {
            "layout": "indeterminate",
            "actionable": "unknown",
            "journal_phase": journal_phase,
            "diagnostic": str(exc),
        }
    if ledger_complete:
        if topology == "new-root-only":
            return {
                "layout": "new-only",
                "actionable": 0,
                "journal_phase": journal_phase,
                "diagnostic": None,
            }
        return {
            "layout": "complete-ledger-topology-mismatch",
            "actionable": "unknown",
            "journal_phase": journal_phase,
            "diagnostic": (
                f"complete migration ledger row conflicts with archive topology {topology}; "
                "inspect the archive paths and do not recreate or move either root automatically"
            ),
        }

    actionable = matching_files(vault, immutable=False)
    return {
        "layout": layout(vault, len(actionable)),
        "actionable": len(actionable),
        "journal_phase": journal_phase,
        "diagnostic": None,
    }


def gate(vault: Path, mode: str) -> int:
    state = gate_state(vault)
    print(f"ARCHIVE_LAYOUT={state['layout']}")
    print(f"ACTIONABLE_LEGACY_FILES={state['actionable']}")
    print(f"MIGRATION_JOURNAL_PHASE={state['journal_phase']}")
    if mode == "--status":
        return 0

    layout_name = str(state["layout"])
    diagnostic = state.get("diagnostic")
    if layout_name in {"new-only", "empty-clean"}:
        return 0
    if layout_name in {
        "old-only",
        "new-with-legacy-locators",
        "empty-with-legacy-locators",
    }:
        print(
            "OpenCairn archive migration required. Run /migrate in Claude Code or "
            "$migrate in Codex before using this workflow.",
            file=sys.stderr,
        )
        return 20
    if layout_name == "pending-verification":
        print(
            "OpenCairn archive migration is awaiting journal-backed verification. "
            "Run /migrate in Claude Code or $migrate in Codex before using this workflow.",
            file=sys.stderr,
        )
        return 20
    messages = {
        "split": (
            21,
            "Both 06 Archive/Claude and 06 Archive/OpenCairn exist. Stop archive-backed "
            "work and run /migrate or $migrate for split-archive reconciliation.",
        ),
        "legacy-symlink-alias": (
            22,
            "06 Archive/Claude is a compatibility symlink to OpenCairn. Stop archive-backed "
            "work and run /migrate or $migrate to retire the alias without traversing it.",
        ),
        "legacy-symlink-unsafe": (
            23,
            "06 Archive/Claude is a symlink with an unsafe or unresolved target. Stop "
            "archive-backed work and run /migrate or $migrate for inspection.",
        ),
        "new-symlink-unsafe": (
            23,
            "06 Archive/OpenCairn is a symlink. Stop archive-backed work and run /migrate "
            "or $migrate for inspection; the active archive root must remain inside the vault.",
        ),
        "legacy-path-unsafe": (
            23,
            "06 Archive/Claude exists but is not a directory. Stop archive-backed work "
            "and run /migrate or $migrate for inspection.",
        ),
        "new-path-unsafe": (
            23,
            "06 Archive/OpenCairn exists but is not a directory. Stop archive-backed work "
            "and run /migrate or $migrate for inspection.",
        ),
    }
    if layout_name in messages:
        code, message = messages[layout_name]
        print(message, file=sys.stderr)
        return code
    if layout_name in {
        "complete-journal-topology-mismatch",
        "complete-ledger-topology-mismatch",
    }:
        print(str(diagnostic), file=sys.stderr)
        return 25
    if diagnostic:
        print(str(diagnostic), file=sys.stderr)
    print(
        "OpenCairn could not prove the archive layout safe. Run /migrate or $migrate "
        "and inspect the reported journal/tool error.",
        file=sys.stderr,
    )
    return 24


def inspect(vault: Path) -> dict[str, object]:
    actionable = matching_files(vault, immutable=False)
    immutable_hits = matching_files(vault, immutable=True)
    protected = protected_immutable_files(vault)
    journal_error: str | None = None
    try:
        journal = load_journal(vault)
    except RuntimeError as exc:
        journal = None
        journal_error = str(exc)
    return {
        "schema": 1,
        "migration": MIGRATION_ID,
        "layout": layout(vault, len(actionable)),
        "old_directory": str(vault / OLD_TOKEN),
        "new_directory": str(vault / NEW_TOKEN),
        "actionable_legacy_files": [path.relative_to(vault).as_posix() for path in actionable],
        "immutable_legacy_files": [
            path.relative_to(vault).as_posix() for path in immutable_hits
        ],
        "protected_immutable_file_count": len(protected),
        "immutable_sha256": {
            path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in protected
        },
        "journal_phase": "invalid" if journal_error else journal.get("phase") if journal else None,
        "journal_error": journal_error,
    }


def editor(vault: Path) -> Path:
    result = vault / ".claude/scripts/locked-edit.sh"
    if not result.is_file():
        raise RuntimeError(f"locked editor missing: {result}")
    return result


def bash_executable() -> str:
    """Return Bash, including Git for Windows installations not on PATH."""
    if os.name == "nt":
        roots = (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        )
        suffixes = ("Git/bin/bash.exe", "Programs/Git/bin/bash.exe")
        for root in roots:
            if not root:
                continue
            for suffix in suffixes:
                candidate = Path(root) / suffix
                if candidate.is_file():
                    return str(candidate)
    found = shutil.which("bash")
    if found:
        return found
    raise RuntimeError("Bash is required to run the locked editor")


def shell_path(path: Path) -> str:
    """Use separators understood by Bash while retaining native drive paths."""
    return path.as_posix() if os.name == "nt" else str(path)


def run_locked_editor(
    vault: Path, target: Path, mode: str, payload: str, *extra: str
) -> subprocess.CompletedProcess[bytes]:
    # Bytes preserve the locked-edit protocol's LF separator on Windows. Text
    # mode would translate it to CRLF before Git Bash reads stdin.
    return subprocess.run(
        [
            bash_executable(),
            shell_path(editor(vault)),
            shell_path(target),
            mode,
            *extra,
        ],
        input=payload.encode("utf-8"),
        capture_output=True,
        check=False,
    )


def locked_call(vault: Path, target: Path, mode: str, payload: str, *extra: str) -> None:
    completed = run_locked_editor(vault, target, mode, payload, *extra)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or f"locked edit failed: {target}")


def locked_whole(vault: Path, relative: Path, payload: str) -> None:
    target = vault / relative
    expected = (
        hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else "MISSING"
    )
    locked_call(vault, target, "--replace-whole", payload, expected)


def locked_whole_cas(vault: Path, relative: Path, transform) -> None:
    target = vault / relative
    for _ in range(8):
        exists = target.exists()
        before = target.read_bytes() if exists else b""
        expected = hashlib.sha256(before).hexdigest() if exists else "MISSING"
        try:
            current = before.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"record is not UTF-8 text: {target}") from exc
        payload = transform(current, exists)
        completed = run_locked_editor(
            vault, target, "--replace-whole", payload, expected
        )
        if completed.returncode == 0:
            return
        if completed.returncode != 2:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                stderr or f"locked edit failed: {target}"
            )
    raise RuntimeError(f"record changed repeatedly during locked update: {target}")


def archive_members(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    )


def post_move_path(relative: Path) -> Path:
    old_parts = Path(OLD_TOKEN).parts
    if relative.parts[: len(old_parts)] == old_parts:
        return Path(NEW_TOKEN, *relative.parts[len(old_parts) :])
    return relative


def validated_relative_path(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"migration journal {field} must contain non-empty paths")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or ".." in path.parts:
        raise RuntimeError(
            f"migration journal {field} contains an unsafe or non-normalised path: {value}"
        )
    return value


def validated_timestamp(value: object, *, field: str) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"migration journal {field} must be an ISO-8601 timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(
            f"migration journal {field} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeError(
            f"migration journal {field} must include a UTC offset"
        )
    return parsed


def validate_journal(journal: object) -> dict[str, object]:
    if not isinstance(journal, dict):
        raise RuntimeError("migration journal must be a JSON object")
    if type(journal.get("schema")) is not int or journal["schema"] != 1:
        raise RuntimeError("migration journal has unsupported schema")
    if journal.get("migration") != MIGRATION_ID:
        raise RuntimeError("migration journal has the wrong migration identifier")
    phase = journal.get("phase")
    if phase not in JOURNAL_PHASES:
        raise RuntimeError("migration journal has an invalid phase")
    started_at = validated_timestamp(journal.get("started_at"), field="started_at")
    if phase == "complete":
        completed_at = validated_timestamp(
            journal.get("completed_at"), field="completed_at"
        )
        if completed_at < started_at:
            raise RuntimeError(
                "migration journal completed_at precedes started_at"
            )
    elif "completed_at" in journal:
        raise RuntimeError(
            "migration journal completed_at is invalid while phase is in-progress"
        )
    members = journal.get("source_members")
    if not isinstance(members, list):
        raise RuntimeError("migration journal source_members must be a list of strings")
    validated_members = [
        validated_relative_path(item, field="source_members") for item in members
    ]
    if len(set(validated_members)) != len(validated_members):
        raise RuntimeError("migration journal source_members contains duplicate paths")
    immutable = journal.get("immutable_sha256")
    if not isinstance(immutable, dict):
        raise RuntimeError("migration journal immutable_sha256 must map paths to SHA-256 hashes")
    allowed_immutable_prefixes = (
        "07 System/.Provenance/",
        f"{OLD_TOKEN}/.Session Transcripts/",
        f"{NEW_TOKEN}/.Session Transcripts/",
    )
    for path, digest in immutable.items():
        safe_path = validated_relative_path(path, field="immutable_sha256")
        if not safe_path.startswith(allowed_immutable_prefixes):
            raise RuntimeError(
                f"migration journal immutable_sha256 path is outside protected namespaces: {path}"
            )
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(
                "migration journal immutable_sha256 must map paths to SHA-256 hashes"
            )
    return journal


def load_journal(vault: Path) -> dict[str, object] | None:
    path = vault / JOURNAL
    if not path.is_file():
        return None
    try:
        journal = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid migration journal: {exc}") from exc
    return validate_journal(journal)


def journal_phase(vault: Path) -> int:
    journal = load_journal(vault)
    print(journal["phase"] if journal else "absent")
    return 0


def save_journal(vault: Path, journal: dict[str, object]) -> None:
    locked_whole(vault, JOURNAL, json.dumps(journal, indent=2) + "\n")


def render_record(current: str, exists: bool, row: str) -> str:
    crlf_count = current.count("\r\n")
    lf_count = current.count("\n") - crlf_count
    newline = "\r\n" if crlf_count > lf_count else "\n"
    section = newline.join(
        (
            "## Versioned migrations",
            "",
            "| Migration | State | Last checked |",
            "|---|---|---|",
            row,
            "",
        )
    )
    if not exists:
        return f"# OpenCairn Migration Record{newline}{newline}{section}"
    if not current:
        return section
    rows = [
        line for line in current.splitlines() if line.startswith(f"| {MIGRATION_ID} |")
    ]
    if rows:
        output: list[str] = []
        inserted = False
        for raw_line in current.splitlines(keepends=True):
            if raw_line.endswith("\r\n"):
                line, ending = raw_line[:-2], "\r\n"
            elif raw_line.endswith("\n"):
                line, ending = raw_line[:-1], "\n"
            else:
                line, ending = raw_line, ""
            if line.startswith(f"| {MIGRATION_ID} |"):
                if not inserted:
                    output.append(row + ending)
                    inserted = True
                continue
            output.append(raw_line)
        return "".join(output)
    if "## Versioned migrations" in current:
        marker_pattern = re.compile(
            r"\| Migration \| State \| Last checked \|\r?\n\|---\|---\|---\|"
        )
        markers = list(marker_pattern.finditer(current))
        if len(markers) != 1:
            raise RuntimeError("versioned migration table header is missing or ambiguous")
        marker = markers[0]
        marker_newline = "\r\n" if "\r\n" in marker.group(0) else "\n"
        return current[: marker.end()] + marker_newline + row + current[marker.end() :]
    prefix = (
        ""
        if current.endswith(newline * 2)
        else newline
        if current.endswith(newline)
        else newline * 2
    )
    return current + prefix + section


def terminal_completion(vault: Path) -> bool:
    if physical_topology(vault) != "new-root-only":
        return False
    journal = load_journal(vault)
    if journal:
        return journal["phase"] == "complete"
    return has_canonical_complete_row(vault)


def record(vault: Path, state: str) -> None:
    allowed = {"in-progress", "blocked", "deferred", "declined", "complete"}
    if state not in allowed:
        raise RuntimeError(f"invalid migration state: {state}")
    if state == "complete" and not terminal_completion(vault):
        topology = physical_topology(vault)
        if topology != "new-root-only":
            raise RuntimeError(
                f"complete record requires new-root-only topology; found {topology}"
            )
        journal = load_journal(vault)
        if journal is not None:
            raise RuntimeError("complete record requires a completed migration journal")
        if matching_files(vault, immutable=False):
            raise RuntimeError("complete record refused while actionable legacy locators remain")
    row = f"| {MIGRATION_ID} | {state} | {dt.date.today().isoformat()} |"
    locked_whole_cas(vault, RECORD, lambda current, exists: render_record(current, exists, row))


def begin(vault: Path) -> int:
    state = inspect(vault)
    if state["layout"] != "old-only":
        print(f"begin requires old-only layout; found {state['layout']}", file=sys.stderr)
        return 2
    existing = load_journal(vault)
    members = archive_members(vault / OLD_TOKEN)
    if existing and existing.get("phase") == "in-progress":
        if existing.get("source_members") != members:
            print("source archive changed since migration began", file=sys.stderr)
            return 2
        print(json.dumps(existing, indent=2))
        return 0
    journal = {
        "schema": 1,
        "migration": MIGRATION_ID,
        "phase": "in-progress",
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source_members": members,
        "immutable_sha256": state["immutable_sha256"],
    }
    save_journal(vault, journal)
    record(vault, "in-progress")
    print(json.dumps(journal, indent=2))
    return 0


def rewrite(vault: Path) -> int:
    if terminal_completion(vault):
        print(json.dumps({"changed": [], "count": 0}, indent=2))
        return 0
    state = inspect(vault)
    if state["layout"] not in {
        "new-only",
        "new-with-legacy-locators",
        "empty-clean",
        "empty-with-legacy-locators",
    }:
        print(
            f"rewrite refused while layout is {state['layout']}; complete or reconcile the folder move first",
            file=sys.stderr,
        )
        return 2
    edit_script = vault / ".claude/scripts/locked-edit.sh"
    if not edit_script.is_file():
        print(f"locked editor missing: {edit_script}", file=sys.stderr)
        return 2
    changed: list[str] = []
    for relative in state["actionable_legacy_files"]:
        target = vault / str(relative)
        try:
            with target.open("r", encoding="utf-8", newline="") as handle:
                text = handle.read()
        except UnicodeDecodeError:
            print(f"legacy locator is in non-UTF-8 text: {relative}", file=sys.stderr)
            return 2
        original_text = text
        if text in {OLD_TOKEN, OLD_WINDOWS_TOKEN}:
            exact_new = NEW_TOKEN if text == OLD_TOKEN else NEW_WINDOWS_TOKEN
            payload = f"{text}\n{SEP}\n{exact_new}"
            completed = run_locked_editor(vault, target, "--replace-all", payload)
            if completed.returncode != 0:
                sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
                print(f"locked rewrite failed: {relative}", file=sys.stderr)
                return completed.returncode or 1
            text = exact_new
        for old, new in LOCATOR_REPLACEMENTS:
            if old not in text:
                continue
            payload = f"{old}\n{SEP}\n{new}"
            if new.endswith("\n"):
                payload += "\n"
            completed = run_locked_editor(vault, target, "--replace-all", payload)
            if completed.returncode != 0:
                sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
                print(f"locked rewrite failed: {relative}", file=sys.stderr)
                return completed.returncode or 1
            text = text.replace(old, new)
        for old, new in ((OLD_TOKEN, NEW_TOKEN), (OLD_WINDOWS_TOKEN, NEW_WINDOWS_TOKEN)):
            if not text.endswith(old):
                continue
            line_start = text.rfind("\n") + 1
            old_line = text[line_start:]
            new_line = old_line[: -len(old)] + new
            payload = f"{old_line}\n{SEP}\n{new_line}"
            completed = run_locked_editor(vault, target, "--replace-all", payload)
            if completed.returncode != 0:
                sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
                print(f"locked EOF rewrite failed: {relative}", file=sys.stderr)
                return completed.returncode or 1
            text = text.replace(old_line, new_line)
        if LOCATOR_PATTERN.search(text):
            print(
                f"legacy locator remains after deterministic rewrite: {relative}",
                file=sys.stderr,
            )
            return 2
        if text != original_text:
            changed.append(str(relative))
    print(json.dumps({"changed": changed, "count": len(changed)}, indent=2))
    return 0


def immutable_verification_errors(vault: Path, journal: dict | None) -> list[str]:
    errors: list[str] = []
    if not journal:
        return errors
    for relative, expected in dict(journal.get("immutable_sha256", {})).items():
        path = vault / post_move_path(Path(relative))
        actual = "MISSING"
        if path.is_file():
            try:
                path.resolve().relative_to(vault.resolve())
            except ValueError:
                errors.append(f"immutable file resolves outside the vault: {relative}")
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"immutable file changed: {relative}")
    return errors


def verify_immutable(vault: Path) -> int:
    journal = load_journal(vault)
    if journal is None:
        print("immutable verification requires a valid migration journal", file=sys.stderr)
        return 1
    if journal["phase"] == "complete":
        errors = [] if physical_topology(vault) == "new-root-only" else [
            f"completed migration conflicts with archive topology {physical_topology(vault)}"
        ]
    else:
        errors = immutable_verification_errors(vault, journal)
    print(json.dumps({"migration": MIGRATION_ID, "errors": errors}, indent=2))
    return 0 if not errors else 1


def verify(vault: Path) -> int:
    if terminal_completion(vault):
        print(
            json.dumps(
                {
                    "schema": 1,
                    "migration": MIGRATION_ID,
                    "layout": "new-only",
                    "journal_phase": (
                        load_journal(vault)["phase"] if load_journal(vault) else None
                    ),
                    "errors": [],
                },
                indent=2,
            )
        )
        return 0
    state = inspect(vault)
    errors: list[str] = []
    journal = load_journal(vault)
    allowed_layouts = {"new-only"} if journal else {"new-only", "empty-clean"}
    if state["layout"] not in allowed_layouts:
        errors.append(f"unsafe live layout: {state['layout']}")
    if journal:
        expected_members = journal.get("source_members", [])
        if journal.get("phase") == "in-progress":
            actual_members = archive_members(vault / NEW_TOKEN)
            if actual_members != expected_members:
                errors.append("destination member inventory differs from the pre-move source")
        errors.extend(immutable_verification_errors(vault, journal))
    state["journal_phase"] = journal.get("phase") if journal else None
    state["errors"] = errors
    print(json.dumps(state, indent=2))
    return 0 if not errors else 1


def finish(vault: Path) -> int:
    journal = load_journal(vault)
    if journal is None:
        print("finish requires a valid migration journal", file=sys.stderr)
        return 1
    if journal.get("phase") == "complete":
        if physical_topology(vault) != "new-root-only":
            print(
                f"completed migration conflicts with archive topology {physical_topology(vault)}",
                file=sys.stderr,
            )
            return 1
    else:
        if verify(vault) != 0:
            return 1
        journal["phase"] = "complete"
        journal["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        save_journal(vault, journal)
    record(vault, "complete")
    return 0


def archive_root(vault: Path, *, write: bool) -> int:
    if not write:
        print("archive-root requires --write", file=sys.stderr)
        return 2
    topology = physical_topology(vault)
    journal = load_journal(vault)
    ledger_complete = has_canonical_complete_row(vault)

    if topology == "old-root-only" and journal is None and not ledger_complete:
        (vault / OLD_TOKEN / ".Session Transcripts").mkdir(parents=True, exist_ok=True)
        print(OLD_TOKEN)
        return 0
    if topology == "new-root-only":
        if journal and journal["phase"] != "complete":
            print("archive root is mid-migration; run /migrate or $migrate", file=sys.stderr)
            return 2
        if not journal and not ledger_complete:
            record(vault, "complete")
        (vault / NEW_TOKEN / ".Session Transcripts").mkdir(parents=True, exist_ok=True)
        print(NEW_TOKEN)
        return 0
    if topology == "no-root" and journal is None and not ledger_complete:
        if matching_files(vault, immutable=False):
            print(
                "archive-root refused empty archive topology with actionable legacy locators; "
                "run /migrate or $migrate",
                file=sys.stderr,
            )
            return 2
        (vault / NEW_TOKEN / ".Session Transcripts").mkdir(parents=True, exist_ok=True)
        record(vault, "complete")
        print(NEW_TOKEN)
        return 0
    print(
        f"archive-root refused unsafe or contradictory archive state: {topology}",
        file=sys.stderr,
    )
    return 2


def split_plan(vault: Path) -> int:
    old_root = vault / OLD_TOKEN
    new_root = vault / NEW_TOKEN
    if new_root.is_symlink():
        print(
            json.dumps(
                {
                    "kind": "new-symlink-unsafe",
                    "new_path": str(new_root),
                    "link_target": str(new_root.readlink()),
                    "member_reconciliation_permitted": False,
                },
                indent=2,
            )
        )
        return 2
    if old_root.is_symlink():
        same_target = False
        try:
            same_target = new_root.is_dir() and old_root.samefile(new_root)
        except OSError:
            pass
        print(
            json.dumps(
                {
                    "kind": "legacy-symlink-alias" if same_target else "legacy-symlink-unsafe",
                    "old_path": str(old_root),
                    "link_target": str(old_root.readlink()),
                    "same_as_new": same_target,
                    "member_reconciliation_permitted": False,
                },
                indent=2,
            )
        )
        return 2
    if not old_root.is_dir() or not new_root.is_dir():
        print("split-plan requires both archive directories", file=sys.stderr)
        return 2
    old = {relative: old_root / relative for relative in archive_members(old_root)}
    new = {relative: new_root / relative for relative in archive_members(new_root)}
    report = {
        "kind": "split-directories",
        "old_only": [],
        "new_only": [],
        "identical": [],
        "conflicts": [],
    }
    for relative in sorted(old.keys() | new.keys()):
        if relative not in new:
            report["old_only"].append(
                {"path": relative, "old_sha256": hashlib.sha256(old[relative].read_bytes()).hexdigest()}
            )
        elif relative not in old:
            report["new_only"].append(
                {"path": relative, "new_sha256": hashlib.sha256(new[relative].read_bytes()).hexdigest()}
            )
        else:
            old_hash = hashlib.sha256(old[relative].read_bytes()).hexdigest()
            new_hash = hashlib.sha256(new[relative].read_bytes()).hexdigest()
            if old_hash == new_hash:
                report["identical"].append({"path": relative, "sha256": old_hash})
            else:
                report["conflicts"].append(
                    {"path": relative, "old_sha256": old_hash, "new_sha256": new_hash}
                )
    print(json.dumps(report, indent=2))
    return 1 if report["conflicts"] else 0


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "gate" and sys.argv[2] in {"--status", "--enforce"}:
        vault = Path(sys.argv[3]).resolve()
        if not vault.is_dir():
            print(f"vault does not exist: {vault}", file=sys.stderr)
            return 2
        try:
            return gate(vault, sys.argv[2])
        except RuntimeError as exc:
            print("ARCHIVE_LAYOUT=indeterminate")
            print("ACTIONABLE_LEGACY_FILES=unknown")
            print("MIGRATION_JOURNAL_PHASE=unknown")
            print(exc, file=sys.stderr)
            return 24
    if len(sys.argv) == 4 and sys.argv[1] == "archive-root" and sys.argv[2] == "--write":
        vault = Path(sys.argv[3]).resolve()
        if not vault.is_dir():
            print(f"vault does not exist: {vault}", file=sys.stderr)
            return 2
        try:
            return archive_root(vault, write=True)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "inspect",
            "journal-phase",
            "begin",
            "rewrite",
            "verify",
            "verify-immutable",
            "finish",
            "split-plan",
            "record",
        ),
    )
    parser.add_argument("vault", type=Path)
    parser.add_argument("state", nargs="?")
    args = parser.parse_args()
    vault = args.vault.resolve()
    if not vault.is_dir():
        parser.error(f"vault does not exist: {vault}")
    try:
        if args.command == "inspect":
            print(json.dumps(inspect(vault), indent=2))
            return 0
        if args.command == "journal-phase":
            return journal_phase(vault)
        if args.command == "begin":
            return begin(vault)
        if args.command == "rewrite":
            return rewrite(vault)
        if args.command == "verify":
            return verify(vault)
        if args.command == "verify-immutable":
            return verify_immutable(vault)
        if args.command == "finish":
            return finish(vault)
        if args.command == "split-plan":
            return split_plan(vault)
        if not args.state:
            parser.error("record requires a state")
        record(vault, args.state)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
