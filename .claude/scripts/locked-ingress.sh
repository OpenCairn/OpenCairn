#!/usr/bin/env bash
# Lock-aware atomic ingress for binary files and directories.
#
# Usage: locked-ingress.sh <vault> <source> <destination> [--move]
#
# The destination must be a new path inside <vault> with an existing parent.
# --move is accepted only for sources outside the vault: the target lands first,
# then the source is removed. A removal failure leaves a safe duplicate.

set -euo pipefail

source "$(dirname "$0")/lib-lock.sh"

if [ $# -lt 3 ] || [ $# -gt 4 ]; then
    echo "Usage: $0 <vault> <source> <destination> [--move]" >&2
    exit 1
fi

VAULT="$1"
SOURCE="$2"
TARGET="$3"
MODE="${4:---copy}"
case "$MODE" in --copy|--move) ;; *) echo "Unknown mode: $MODE" >&2; exit 1 ;; esac

command -v python3 >/dev/null 2>&1 || { echo "locked-ingress.sh requires python3" >&2; exit 1; }

RESOLVED_FILE="$(mktemp "${TMPDIR:-/tmp}/opencairn-ingress-paths.XXXXXX")"
trap 'rm -f "$RESOLVED_FILE"' EXIT
python3 - "$VAULT" "$SOURCE" "$TARGET" "$MODE" > "$RESOLVED_FILE" <<'PY'
import os
from pathlib import Path
import sys

vault = Path(sys.argv[1]).expanduser().resolve(strict=True)
source_arg = Path(sys.argv[2]).expanduser()
if source_arg.is_symlink():
    raise SystemExit("source symlinks are not accepted")
source = source_arg.resolve(strict=True)
target_arg = Path(sys.argv[3]).expanduser()
target = (Path.cwd() / target_arg).resolve(strict=False) if not target_arg.is_absolute() else target_arg.resolve(strict=False)
mode = sys.argv[4]

try:
    inside = os.path.commonpath((str(target), str(vault))) == str(vault)
except ValueError:
    inside = False
if not inside or target == vault:
    raise SystemExit("destination must be a child path inside the resolved vault")
if not target.parent.is_dir():
    raise SystemExit("destination parent must already exist")
if target.exists():
    raise SystemExit("destination already exists")
if mode == "--move":
    try:
        source_inside = os.path.commonpath((str(source), str(vault))) == str(vault)
    except ValueError:
        source_inside = False
    if source_inside:
        raise SystemExit("--move source must be outside the vault")
print(vault)
print(source)
print(target)
PY
{
    IFS= read -r VAULT
    IFS= read -r SOURCE
    IFS= read -r TARGET
} < "$RESOLVED_FILE"
rm -f "$RESOLVED_FILE"
trap - EXIT
[ -n "$VAULT" ] && [ -n "$SOURCE" ] && [ -n "$TARGET" ] || {
    echo "Failed to resolve ingress paths" >&2
    exit 1
}

LOCK_FILE="$(_lock_path_for "$TARGET")"
_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock for $TARGET" >&2; exit 1; }

python3 - "$SOURCE" "$TARGET" "$MODE" <<'PY'
import os
from pathlib import Path
import shutil
import sys
import tempfile

source = Path(sys.argv[1])
target = Path(sys.argv[2])
mode = sys.argv[3]
if target.exists():
    raise SystemExit(f"destination appeared while waiting for lock: {target}")

parent = target.parent
stage = None
try:
    if source.is_dir():
        stage = Path(tempfile.mkdtemp(prefix=".ingress-", dir=parent))
        shutil.copytree(source, stage, dirs_exist_ok=True, copy_function=shutil.copy2)
        shutil.copystat(source, stage)
    elif source.is_file():
        fd, stage_name = tempfile.mkstemp(prefix=".ingress-", dir=parent)
        os.close(fd)
        stage = Path(stage_name)
        shutil.copy2(source, stage)
    else:
        raise SystemExit(f"source is not a regular file or directory: {source}")
    os.replace(stage, target)
    stage = None
    if mode == "--move":
        try:
            if source.is_dir():
                shutil.rmtree(source)
            else:
                source.unlink()
        except OSError as exc:
            raise SystemExit(f"target installed but source retained: {exc}")
finally:
    if stage is not None and stage.exists():
        if stage.is_dir():
            shutil.rmtree(stage)
        else:
            stage.unlink()
PY

_unlock
printf 'Locked ingress applied: %s -> %s (%s)\n' "$SOURCE" "$TARGET" "$MODE"
