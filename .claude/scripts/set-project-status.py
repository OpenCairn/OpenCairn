#!/usr/bin/env python3
"""Move a project hub between active, Cold, and Backlog through Obsidian."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


STATUSES = {
    "active": Path("03 Projects"),
    "cold": Path("03 Projects/Cold"),
    "backlog": Path("03 Projects/Backlog"),
}
DEFAULT_ACTIVE_CAP = 5
CAP_PATTERN = re.compile(r"\*\*Active project cap:\s*(\d+)\*\*")


def die(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_projects(vault: Path) -> list[str]:
    return sorted(path.stem for path in (vault / "03 Projects").glob("*.md"))


def active_cap(vault: Path) -> tuple[int, str]:
    principles = vault / "07 System/Vault Organisation Principles.md"
    try:
        text = principles.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return DEFAULT_ACTIVE_CAP, "default"
    match = CAP_PATTERN.search(text)
    if not match:
        return DEFAULT_ACTIVE_CAP, "default"
    value = int(match.group(1))
    if value < 1:
        die(f"invalid active-project cap in {principles}: {value}")
    return value, principles.relative_to(vault).as_posix()


def unresolved_total() -> int | None:
    command = os.environ.get("OBSIDIAN_CLI") or "obsidian"
    try:
        result = subprocess.run(
            [command, "unresolved", "total"],
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in reversed(result.stdout.splitlines()):
        value = line.strip()
        if value.isdigit():
            return int(value)
    return None


def run_locked_move(wrapper: Path, source: Path, destination: Path) -> str | None:
    result = subprocess.run(
        [str(wrapper), str(source), "--move", str(destination), digest(source)],
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        die(f"project move failed: {detail}")
    for line in result.stdout.splitlines():
        if line.startswith("Move receipt: "):
            return line.removeprefix("Move receipt: ").strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--project", required=True, help="project basename, without a path")
    parser.add_argument("--to", required=True, choices=tuple(STATUSES))
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--dry-run", action="store_true")
    action.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve(strict=True)
    os.environ["VAULT_PATH"] = str(vault)
    name = args.project.removesuffix(".md").strip()
    if (
        not name
        or "\n" in name
        or "\r" in name
        or Path(name).name != name
        or name in (".", "..")
    ):
        die("--project must be one project basename, not a path")

    candidates = {
        status: vault / folder / f"{name}.md" for status, folder in STATUSES.items()
    }
    existing = [(status, path) for status, path in candidates.items() if path.is_file()]
    if len(existing) != 1:
        found = ", ".join(str(path) for _, path in existing) or "none"
        die(f"expected exactly one lifecycle file for {name!r}; found {found}")
    current_status, source = existing[0]
    destination = candidates[args.to]
    if current_status == args.to:
        die(f"project is already {args.to}: {source}")

    projects = active_projects(vault)
    cap, cap_source = active_cap(vault)
    active_after = len(projects) + (1 if args.to == "active" else 0) - (
        1 if current_status == "active" else 0
    )
    if args.to == "active" and active_after > cap:
        die(
            f"activation would exceed the active-project cap of {cap}; "
            "cool another project first: " + ", ".join(projects)
        )

    plan = {
        "project": name,
        "from": current_status,
        "to": args.to,
        "source": source.relative_to(vault).as_posix(),
        "destination": destination.relative_to(vault).as_posix(),
        "destination_directory_exists": destination.parent.is_dir(),
        "destination_directory_will_create": not destination.parent.is_dir(),
        "active_project_cap": cap,
        "active_project_cap_source": cap_source,
        "active_count_before": len(projects),
        "active_count_after": active_after,
    }
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    wrapper = Path(__file__).with_name("locked-edit.sh")
    if not wrapper.is_file():
        die(f"locked-edit wrapper is missing: {wrapper}")
    unresolved_before = unresolved_total()
    if unresolved_before is None:
        die("could not read the pre-move unresolved-link count")

    receipt = run_locked_move(wrapper, source, destination)
    unresolved_after = unresolved_total()
    result = {
        "result": "complete",
        **plan,
        "move_receipt": receipt,
        "unresolved_before": unresolved_before,
        "unresolved_after": unresolved_after,
        "unresolved_delta": (
            unresolved_after - unresolved_before if unresolved_after is not None else None
        ),
        "verification": (
            "complete"
            if unresolved_after is not None and unresolved_after <= unresolved_before
            else "needs-review"
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
