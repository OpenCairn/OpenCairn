#!/usr/bin/env bash
# Thin compatibility gate for the shared-agent archive namespace.
# archive-bundle-v3

set -euo pipefail

MODE="--enforce"
if [[ "${1:-}" == "--status" || "${1:-}" == "--enforce" ]]; then
    MODE="$1"
    shift
fi

VAULT="${1:-${VAULT_PATH:-}}"
if [[ -z "$VAULT" || ! -d "$VAULT" ]]; then
    printf '%s\n' \
        'ARCHIVE_LAYOUT=invalid-vault' \
        'ACTIONABLE_LEGACY_FILES=unknown' \
        'MIGRATION_JOURNAL_PHASE=unknown'
    [[ "$MODE" == "--status" ]] && exit 0
    echo 'OpenCairn could not resolve the vault. Set VAULT_PATH to the vault root.' >&2
    exit 24
fi

MIGRATION_HELPER="$(dirname "$0")/archive-namespace-migration.py"
mismatch() {
    printf '%s\n' \
        'ARCHIVE_LAYOUT=archive-core-mismatch' \
        'ACTIONABLE_LEGACY_FILES=unknown' \
        'MIGRATION_JOURNAL_PHASE=unknown'
    [[ "$MODE" == "--status" ]] && exit 0
    # $update is user-facing Codex syntax, not a shell expansion.
    # shellcheck disable=SC2016
    echo 'The installed archive gate and migration helper are from different releases. Use the documented helper-first update bridge, then rerun /update or $update.' >&2
    exit 26
}

python_missing() {
    printf '%s\n' \
        'ARCHIVE_LAYOUT=indeterminate' \
        'ACTIONABLE_LEGACY_FILES=unknown' \
        'MIGRATION_JOURNAL_PHASE=unknown'
    [[ "$MODE" == "--status" ]] && exit 0
    echo 'OpenCairn archive migration requires Python 3 available as python3 or python.' >&2
    exit 24
}

if command -v python3 &>/dev/null; then
    [[ -x "$MIGRATION_HELPER" ]] || mismatch
    HELPER_COMMAND=("$MIGRATION_HELPER")
elif command -v python &>/dev/null; then
    [[ -f "$MIGRATION_HELPER" && -r "$MIGRATION_HELPER" ]] || mismatch
    HELPER_COMMAND=(python "$MIGRATION_HELPER")
else
    python_missing
fi

set +e
OUTPUT=$("${HELPER_COMMAND[@]}" gate "$MODE" "$VAULT" 2> >(cat >&2))
HELPER_RC=$?
set -e

# Python writes CRLF on Windows; strip the transport CR before validating the
# helper's exact three-line protocol.
OUTPUT="${OUTPUT//$'\r'/}"
mapfile -t LINES <<< "$OUTPUT"
[[ ${#LINES[@]} -eq 3 ]] || mismatch
[[ "${LINES[0]}" =~ ^ARCHIVE_LAYOUT=[a-z0-9-]+$ ]] || mismatch
[[ "${LINES[1]}" =~ ^ACTIONABLE_LEGACY_FILES=([0-9]+|unknown)$ ]] || mismatch
[[ "${LINES[2]}" =~ ^MIGRATION_JOURNAL_PHASE=(absent|in-progress|complete|invalid|unknown)$ ]] || mismatch
printf '%s\n' "${LINES[@]}"

[[ "$MODE" == "--status" ]] && exit 0
exit "$HELPER_RC"
