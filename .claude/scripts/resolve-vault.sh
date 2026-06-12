#!/usr/bin/env bash
# Resolve and validate the vault path from VAULT_PATH environment variable.
# Usage (from Claude Code commands): Run this script first in Step 0.
#   "{VAULT_PATH}/.claude/scripts/resolve-vault.sh"
#   OR if VAULT_PATH might not be set yet:
#   bash -c 'source "${VAULT_PATH:?VAULT_PATH not set}/.claude/scripts/resolve-vault.sh"' 2>/dev/null
#
# Simpler usage for commands (copy-paste into Step 0):
#   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
#
# Output on success: VAULT_PATH=/resolved/path
# Exit code 1 on failure with descriptive error.
#
# This script centralises the vault path check duplicated across all commands.
# If the check logic changes, update it here — all commands benefit.

set -euo pipefail

if [[ -z "${VAULT_PATH:-}" ]]; then
    echo "VAULT_PATH not set. Set it in your shell profile (e.g., export VAULT_PATH=/path/to/vault)" >&2
    exit 1
elif [[ ! -d "$VAULT_PATH" ]]; then
    echo "VAULT_PATH=$VAULT_PATH does not exist" >&2
    exit 1
else
    echo "VAULT_PATH=$VAULT_PATH"
fi
