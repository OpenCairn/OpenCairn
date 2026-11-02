#!/usr/bin/env python3
"""Advisory live-run registry: which unattended runs claim which repo, queue or log.

Concurrent sessions and unattended runs share files (a work queue, a session
log, a repo). A skill with disposition authority over such a file checks the
registry first and skips its write when another live run claims the file.
register does not refuse a claim that overlaps another live run's, so a claim
records intent; it does not grant exclusive ownership.

Registry: JSON Lines at $OPENCAIRN_RUN_REGISTRY, default
~/.local/state/runs/registry.jsonl. One object per line:

    {"run_id": "...", "owner": "<session id>", "claims": ["/abs/path", ...],
     "ends_at": "2026-11-03T10:00:00+10:00", "released": false}

The latest line for a run_id wins. A claim is live until it is released or
its ends_at passes; a row without ends_at stays live (an unbounded claim is
the run's defect to fix, not the reader's to assume away). A claim on a
directory covers everything beneath it, and a directory is claimed when
anything beneath it is.

Usage:
    run-claims.py check [--self RUN_ID] PATH...
    run-claims.py register --run-id ID --owner SESSION --ends-at ISO --claim PATH [--claim PATH ...]
    run-claims.py release --run-id ID

check exits 0 when every PATH is free, 3 when any is claimed by another live
run (one "claimed by <run>" line per hit), 2 when the registry is unreadable.
A missing registry means no claims (check says so and exits 0).
"""

from __future__ import annotations

import argparse
try:
    import fcntl
except ImportError:  # Windows: check still works; register/release refuse below
    fcntl = None
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def registry_path() -> Path:
    raw = os.environ.get("OPENCAIRN_RUN_REGISTRY")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".local/state/runs/registry.jsonl"


def parse_time(raw: str, label: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ValueError(f"{label}: not an ISO 8601 time: {raw!r}")
    if value.tzinfo is None:
        raise ValueError(f"{label}: time has no zone: {raw!r}")
    return value


def norm(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


def load(path: Path) -> dict[str, dict]:
    """Latest row per run_id. Raises ValueError on a malformed line."""
    runs: dict[str, dict] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return runs
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON ({exc.msg})")
        if not isinstance(row, dict) or not isinstance(row.get("run_id"), str):
            raise ValueError(f"{path}:{number}: row needs a string run_id")
        claims = row.get("claims", [])
        if not isinstance(claims, list) or not all(isinstance(c, str) and os.path.isabs(c) for c in claims):
            raise ValueError(f"{path}:{number}: claims must be a list of absolute paths")
        if not isinstance(row.get("released", False), bool):
            raise ValueError(f"{path}:{number}: released must be true or false")
        if row.get("ends_at") is not None:
            parse_time(row["ends_at"], f"{path}:{number}")
        runs[row["run_id"]] = row
    return runs


def beneath(path: str, parent: str) -> bool:
    return path.startswith(parent.rstrip(os.sep) + os.sep)


def covers(claim: str, target: str) -> bool:
    """Same path, target inside a claimed directory, or a claim inside the target directory."""
    return target == claim or beneath(target, claim) or beneath(claim, target)


def cmd_check(args) -> int:
    now = parse_time(args.now, "--now") if args.now else datetime.now(timezone.utc)
    try:
        runs = load(registry_path())
    except (OSError, ValueError) as exc:
        print(f"run-claims: registry unreadable: {exc}", file=sys.stderr)
        return 2
    if not runs and not registry_path().exists():
        print(f"no registry at {registry_path()} (not configured): nothing is claimed")
    claimed = False
    for raw in args.paths:
        target = norm(raw)
        holders = []
        for run_id, row in runs.items():
            if run_id == args.self or row.get("released"):
                continue
            ends = row.get("ends_at")
            if ends and parse_time(ends, run_id) <= now:
                continue
            if any(covers(norm(c), target) for c in row.get("claims", [])):
                holders.append((run_id, row.get("owner", "?"), ends or "no end time"))
        for run_id, owner, ends in holders:
            print(f"claimed by {run_id} (owner {owner}, until {ends}): {raw}")
        if holders:
            claimed = True
        else:
            print(f"free: {raw}")
    return 3 if claimed else 0


def append(row: dict) -> None:
    if fcntl is None:
        raise ValueError("register/release need file locking (fcntl), unavailable on this platform")
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def stamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def cmd_register(args) -> int:
    parse_time(args.ends_at, "--ends-at")
    append({
        "run_id": args.run_id,
        "owner": args.owner,
        "claims": [norm(c) for c in args.claim],
        "ends_at": args.ends_at,
        "released": False,
        "at": stamp(),
    })
    print(f"registered {args.run_id}: {len(args.claim)} claim(s) until {args.ends_at}")
    return 0


def cmd_release(args) -> int:
    append({"run_id": args.run_id, "claims": [], "released": True, "at": stamp()})
    print(f"released {args.run_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("paths", nargs="+")
    check.add_argument("--self", help="ignore this run's own claims")
    check.add_argument("--now", help=argparse.SUPPRESS)
    register = sub.add_parser("register")
    register.add_argument("--run-id", required=True)
    register.add_argument("--owner", required=True)
    register.add_argument("--ends-at", required=True)
    register.add_argument("--claim", action="append", required=True)
    release = sub.add_parser("release")
    release.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        return {"check": cmd_check, "register": cmd_register, "release": cmd_release}[args.command](args)
    except ValueError as exc:
        print(f"run-claims: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
