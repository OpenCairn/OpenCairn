#!/usr/bin/env bash
# Locked, atomic edit of a planning file (WIP / This Week / Tickler / project hub).
#
# The Edit tool does a lockless read-modify-write, so two concurrent /park or
# /goodnight runs silently clobber each other's edits to shared planning files.
# This wrapper serialises writers through the file's canonical lock and writes
# atomically, converting silent data loss into one of two safe outcomes:
#   - disjoint edits both land (each old_string still present after the other's write)
#   - conflicting edits fail loudly (the loser's old_string no longer matches)
#
# Usage:
#   locked-edit.sh <file> --replace       (stdin: OLD <SEP> NEW; OLD must match exactly once)
#   locked-edit.sh <file> --replace-all   (stdin: OLD <SEP> NEW; replaces every occurrence, >=1)
#   locked-edit.sh <file> --append        (stdin appended verbatim at end of file)
#
# For --replace/--replace-all, stdin is the old string, then a separator LINE
# equal to exactly:
#   ========OPENCAIRN-LOCKED-EDIT-SEP========
# then the new string. (A literal separator line must not appear inside content;
# it won't in normal vault prose.) Matching is LITERAL, never regex.
#
# Exit codes: 0 ok · 1 usage/lock error · 2 no match · 3 ambiguous (>1 match under --replace)
#
# Platform: Linux, macOS, Windows (Git Bash). Locking via lib-lock.sh
# (flock / mkdir fallback); literal string handling via python3.

set -euo pipefail

source "$(dirname "$0")/lib-lock.sh"

SEP='========OPENCAIRN-LOCKED-EDIT-SEP========'

if [ $# -lt 2 ]; then
    echo "Usage: $0 <file> --replace|--replace-all|--append" >&2
    exit 1
fi

TARGET="$1"
MODE="$2"

case "$MODE" in
    --replace|--replace-all|--append) ;;
    *) echo "Unknown mode: $MODE (expected --replace, --replace-all, or --append)" >&2; exit 1 ;;
esac

if ! command -v python3 &>/dev/null; then
    echo "locked-edit.sh requires python3 (literal string engine)" >&2
    exit 1
fi

STDIN_CONTENT="$(cat)"

LOCK_FILE="$(_lock_path_for "$TARGET")"
mkdir -p "$(dirname "$TARGET")"

_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock for $TARGET" >&2; exit 1; }

# All file I/O and matching happens in python (literal, atomic via os.replace),
# while bash holds the cross-platform lock. python reads the payload from the
# environment to avoid any shell-quoting/escaping of multiline content.
export _LE_TARGET="$TARGET"
export _LE_MODE="$MODE"
export _LE_SEP="$SEP"
export _LE_STDIN="$STDIN_CONTENT"

set +e
python3 - <<'PY'
import os, sys, tempfile

target = os.environ["_LE_TARGET"]
mode   = os.environ["_LE_MODE"]
sep    = os.environ["_LE_SEP"]
stdin  = os.environ["_LE_STDIN"]

def atomic_write(path, data):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".le-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(tmp, path)   # atomic within the same filesystem
    except BaseException:
        try: os.remove(tmp)
        except OSError: pass
        raise

if mode == "--append":
    existing = ""
    if os.path.exists(target):
        with open(target) as f:
            existing = f.read()
    # Append verbatim; ensure exactly one newline boundary before the new block.
    if existing and not existing.endswith("\n"):
        existing += "\n"
    atomic_write(target, existing + stdin)
    sys.exit(0)

# --replace / --replace-all: split stdin into OLD and NEW on the separator line.
lines = stdin.split("\n")
sep_idx = next((i for i, ln in enumerate(lines) if ln == sep), None)
if sep_idx is None:
    sys.stderr.write("No separator line found in stdin for %s mode\n" % mode)
    sys.exit(1)
old = "\n".join(lines[:sep_idx])
new = "\n".join(lines[sep_idx + 1:])
# A heredoc adds a trailing newline; the most common authoring shape is
# OLD\n<SEP>\nNEW\n — strip a single trailing newline the heredoc appended to NEW
# so it doesn't inject a spurious blank line. OLD is taken verbatim.
if new.endswith("\n"):
    new = new[:-1]

if not os.path.exists(target):
    sys.stderr.write("Target file does not exist: %s\n" % target)
    sys.exit(2)
with open(target) as f:
    content = f.read()

count = content.count(old)
if count == 0:
    sys.stderr.write("old_string not found in %s\n" % target)
    sys.exit(2)
if mode == "--replace" and count > 1:
    sys.stderr.write("old_string matched %d times in %s (use --replace-all or make it unique)\n" % (count, target))
    sys.exit(3)

if mode == "--replace":
    content = content.replace(old, new, 1)
else:
    content = content.replace(old, new)

atomic_write(target, content)
sys.exit(0)
PY
RC=$?
set -e

_unlock
unset _LE_TARGET _LE_MODE _LE_SEP _LE_STDIN

if [ "$RC" -eq 0 ]; then
    echo "Locked edit applied: $TARGET"
fi
exit "$RC"
