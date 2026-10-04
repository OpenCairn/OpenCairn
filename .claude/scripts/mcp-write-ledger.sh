#!/usr/bin/env bash
# PostToolUse adapter for the named Obsidian note mutators. Their resolved
# response path (not an active/periodic input target) identifies the landed note.
# Feed the existing file ledger and skill marker; never change note contents.
# --ledger / --marker select one independently opted-in hook; default feeds both.
# Requires jq and Python 3. Unknown/error responses fail open without attribution.
# This adapter does not make an MCP write lock-safe, run locale formatting, or
# prove that the harness emitted a PostToolUse event. Wire the matching hook.
set -uo pipefail
MODE="${1:-both}"
case "$MODE" in both|--ledger|--marker) ;; *) exit 0 ;; esac

command -v jq >/dev/null 2>&1 || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null) || exit 0
case "$TOOL" in
    mcp__obsidian__obsidian_write_note|mcp__obsidian__obsidian_append_to_note|mcp__obsidian__obsidian_patch_note|mcp__obsidian__obsidian_replace_in_note) ;;
    *) exit 0 ;;
esac
[ "$(printf '%s' "$INPUT" | jq -r '.hook_event_name // empty')" = "PostToolUse" ] || exit 0

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$SCRIPT_DIR/resolve-vault.sh" >/dev/null 2>&1 || exit 0
RELATIVE=$(printf '%s' "$INPUT" | jq -er '
    .tool_response
    | if type == "string" then fromjson else . end
    | if type == "array" then {content:.} else . end
    | select(type == "object" and .isError != true and .error == null
             and .structuredContent.error == null)
    | .structuredContent.path // .path //
      ([.content[]? | select(.type == "text") | .text | fromjson?
        | select(.error == null and .isError != true) | .path][0])
    | select(type == "string" and length > 0)
' 2>/dev/null) || exit 0

# Only the known vault-relative output schema is accepted. Reject escaping paths
# and symlinks rather than guessing ownership of a different filesystem target.
FILE=$(python3 - "$VAULT_PATH" "$RELATIVE" <<'PY'
from pathlib import Path
import sys
vault = Path(sys.argv[1]).resolve()
relative = Path(sys.argv[2])
if relative.is_absolute():
    raise SystemExit(1)
path = (vault / relative).resolve()
if not path.is_relative_to(vault) or not path.is_file():
    raise SystemExit(1)
print(path)
PY
) || exit 0

MAPPED=$(printf '%s' "$INPUT" | jq --arg path "$FILE" '.tool_input.file_path = $path') || exit 0
[ "$MODE" = "--marker" ] || printf '%s' "$MAPPED" | "$SCRIPT_DIR/session-ledger.sh"
[ "$MODE" = "--ledger" ] || printf '%s' "$MAPPED" | "$SCRIPT_DIR/skill-edit-marker.sh"
exit 0
