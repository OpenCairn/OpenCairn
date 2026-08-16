#!/usr/bin/env python3
"""Inspect, rewrite, and verify the OpenCairn archive namespace migration."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


OLD_TOKEN = "06 Archive/Claude"
NEW_TOKEN = "06 Archive/OpenCairn"
OLD_LOCATOR = f"{OLD_TOKEN}/"
NEW_LOCATOR = f"{NEW_TOKEN}/"
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
    "*.canvas",
    "*.sh",
    "*.py",
    "*.json",
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.txt",
    "*.csv",
    "*.tex",
    "*.html",
    "*.css",
    "*.js",
)
SEP = "========OPENCAIRN-LOCKED-EDIT-SEP========"
MIGRATION_ID = "archive-namespace-opencairn-v1"
JOURNAL = Path("07 System/.OpenCairn Migration/archive-namespace-opencairn-v1.json")
RECORD = Path("07 System/Migration Record.md")
JOURNAL_PHASES = {"in-progress", "complete"}


def excluded(relative: Path) -> bool:
    parts = relative.parts
    if relative == Path("07 System/Migration Record.md"):
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


def matching_files(vault: Path, *, immutable: bool) -> list[Path]:
    roots = [root_name for root_name in ROOT_NAMES if (vault / root_name).exists()]
    if not roots:
        return []
    command = [
        "rg",
        "-l",
        "--hidden",
        "--no-ignore",
        "-F",
        OLD_LOCATOR,
        *roots,
    ]
    for pattern in TEXT_GLOBS:
        command.extend(("-g", pattern))
    completed = subprocess.run(
        command,
        cwd=vault,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(completed.stderr.strip() or "legacy-locator search failed")
    matches: list[Path] = []
    for line in completed.stdout.splitlines():
        candidate = Path(line.removeprefix("./"))
        path = candidate if candidate.is_absolute() else vault / candidate
        try:
            relative = path.resolve().relative_to(vault)
        except ValueError:
            raise RuntimeError(f"legacy-locator search escaped the vault: {line}")
        if excluded(relative) != immutable:
            continue
        if path.is_file():
            matches.append(path)
    return sorted(set(matches), key=lambda path: str(path.relative_to(vault)))


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
        files.update(
            path
            for path in root.rglob("*")
            if path.is_file() and not path.name.endswith(".lock")
        )
    return sorted(files, key=lambda path: str(path.relative_to(vault)))


def layout(vault: Path, actionable_count: int) -> str:
    old_path = vault / OLD_TOKEN
    new_path = vault / NEW_TOKEN
    if old_path.is_symlink():
        try:
            if new_path.is_dir() and old_path.samefile(new_path):
                return "legacy-symlink-alias"
        except OSError:
            pass
        return "legacy-symlink-unsafe"
    old_exists = old_path.is_dir()
    new_exists = new_path.is_dir()
    if old_exists and new_exists:
        return "split"
    if old_exists:
        return "old-only"
    if new_exists:
        return "new-with-legacy-locators" if actionable_count else "new-only"
    return "empty-with-legacy-locators" if actionable_count else "empty-clean"


def inspect(vault: Path) -> dict[str, object]:
    actionable = matching_files(vault, immutable=False)
    immutable_hits = matching_files(vault, immutable=True)
    protected = protected_immutable_files(vault)
    journal = load_journal(vault)
    return {
        "schema": 1,
        "migration": MIGRATION_ID,
        "layout": layout(vault, len(actionable)),
        "old_directory": str(vault / OLD_TOKEN),
        "new_directory": str(vault / NEW_TOKEN),
        "actionable_legacy_files": [str(path.relative_to(vault)) for path in actionable],
        "immutable_legacy_files": [
            str(path.relative_to(vault)) for path in immutable_hits
        ],
        "protected_immutable_file_count": len(protected),
        "immutable_sha256": {
            str(path.relative_to(vault)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in protected
        },
        "journal_phase": journal.get("phase") if journal else None,
    }


def editor(vault: Path) -> Path:
    result = vault / ".claude/scripts/locked-edit.sh"
    if not result.is_file():
        raise RuntimeError(f"locked editor missing: {result}")
    return result


def locked_call(vault: Path, target: Path, mode: str, payload: str, *extra: str) -> None:
    completed = subprocess.run(
        [str(editor(vault)), str(target), mode, *extra],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"locked edit failed: {target}")


def locked_whole(vault: Path, relative: Path, payload: str) -> None:
    target = vault / relative
    expected = (
        hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else "MISSING"
    )
    locked_call(vault, target, "--replace-whole", payload, expected)


def archive_members(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    )


def post_move_path(relative: Path) -> Path:
    old_parts = Path(OLD_TOKEN).parts
    if relative.parts[: len(old_parts)] == old_parts:
        return Path(NEW_TOKEN, *relative.parts[len(old_parts) :])
    return relative


def validate_journal(journal: object) -> dict[str, object]:
    if not isinstance(journal, dict):
        raise RuntimeError("migration journal must be a JSON object")
    if type(journal.get("schema")) is not int or journal["schema"] != 1:
        raise RuntimeError("migration journal has unsupported schema")
    if journal.get("migration") != MIGRATION_ID:
        raise RuntimeError("migration journal has the wrong migration identifier")
    if journal.get("phase") not in JOURNAL_PHASES:
        raise RuntimeError("migration journal has an invalid phase")
    members = journal.get("source_members")
    if not isinstance(members, list) or not all(isinstance(item, str) for item in members):
        raise RuntimeError("migration journal source_members must be a list of strings")
    immutable = journal.get("immutable_sha256")
    if not isinstance(immutable, dict) or not all(
        isinstance(path, str)
        and isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest)
        for path, digest in immutable.items()
    ):
        raise RuntimeError("migration journal immutable_sha256 must map paths to SHA-256 hashes")
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


def record(vault: Path, state: str) -> None:
    allowed = {"in-progress", "blocked", "deferred", "declined", "complete"}
    if state not in allowed:
        raise RuntimeError(f"invalid migration state: {state}")
    path = vault / RECORD
    row = f"| {MIGRATION_ID} | {state} | {dt.date.today().isoformat()} |"
    section = (
        "## Versioned migrations\n\n"
        "| Migration | State | Last checked |\n"
        "|---|---|---|\n"
        f"{row}\n"
    )
    if not path.exists():
        locked_call(vault, path, "--append", f"# OpenCairn Migration Record\n\n{section}")
        return
    text = path.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith(f"| {MIGRATION_ID} |")]
    if len(rows) > 1:
        raise RuntimeError(f"ambiguous migration rows for {MIGRATION_ID}")
    if rows:
        locked_call(vault, path, "--replace", f"{rows[0]}\n{SEP}\n{row}")
    elif "## Versioned migrations" in text:
        marker = "| Migration | State | Last checked |\n|---|---|---|"
        if text.count(marker) != 1:
            raise RuntimeError("versioned migration table header is missing or ambiguous")
        locked_call(vault, path, "--replace", f"{marker}\n{SEP}\n{marker}\n{row}")
    else:
        prefix = "" if text.endswith("\n\n") else "\n" if text.endswith("\n") else "\n\n"
        locked_call(vault, path, "--append", prefix + section)


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
    state = inspect(vault)
    if state["layout"] not in {
        "new-only",
        "new-with-legacy-locators",
        "empty-clean",
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
    payload = f"{OLD_LOCATOR}\n{SEP}\n{NEW_LOCATOR}"
    changed: list[str] = []
    for relative in state["actionable_legacy_files"]:
        target = vault / str(relative)
        completed = subprocess.run(
            [str(edit_script), str(target), "--replace-all"],
            input=payload,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr)
            print(f"locked rewrite failed: {relative}", file=sys.stderr)
            return completed.returncode or 1
        changed.append(str(relative))
    print(json.dumps({"changed": changed, "count": len(changed)}, indent=2))
    return 0


def verify(vault: Path) -> int:
    state = inspect(vault)
    errors: list[str] = []
    if state["layout"] not in {"new-only", "empty-clean"}:
        errors.append(f"unsafe live layout: {state['layout']}")
    journal = load_journal(vault)
    if journal:
        expected_members = journal.get("source_members", [])
        if "source_members" in journal:
            actual_members = archive_members(vault / NEW_TOKEN)
            if actual_members != expected_members:
                errors.append("destination member inventory differs from the pre-move source")
        for relative, expected in dict(journal.get("immutable_sha256", {})).items():
            path = vault / post_move_path(Path(relative))
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
            if actual != expected:
                errors.append(f"immutable file changed: {relative}")
    state["journal_phase"] = journal.get("phase") if journal else None
    state["errors"] = errors
    print(json.dumps(state, indent=2))
    return 0 if not errors else 1


def finish(vault: Path) -> int:
    journal = load_journal(vault)
    if journal is None:
        print("finish requires a valid migration journal", file=sys.stderr)
        return 1
    if verify(vault) != 0:
        return 1
    if journal.get("phase") != "complete":
        journal["phase"] = "complete"
        journal["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        save_journal(vault, journal)
    record(vault, "complete")
    return 0


def split_plan(vault: Path) -> int:
    old_root = vault / OLD_TOKEN
    new_root = vault / NEW_TOKEN
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "inspect",
            "journal-phase",
            "begin",
            "rewrite",
            "verify",
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
