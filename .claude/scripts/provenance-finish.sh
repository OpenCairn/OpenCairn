#!/usr/bin/env bash
# Remove a processed flag only after validating every required attestation,
# while holding the flag's canonical lock. No source/log/proof is removed.
set -euo pipefail
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPTS/lib-lock.sh"
[ "$#" -eq 2 ] || { echo 'Usage: provenance-finish.sh <vault> <flag>' >&2; exit 1; }
FLAG=$(python3 - "$1" "$2" <<'PY'
from pathlib import Path
import sys
vault = Path(sys.argv[1]).expanduser().resolve(strict=True)
flag = Path(sys.argv[2]).expanduser().resolve(strict=True)
flag.relative_to(vault / '07 System/.Provenance/pending')
print(flag)
PY
)
_lock "$(_lock_path_for "$FLAG")" 10
python3 "$SCRIPTS/provenance-write.py" --vault "$1" check-flag --flag "$FLAG"
rm -- "$FLAG"
