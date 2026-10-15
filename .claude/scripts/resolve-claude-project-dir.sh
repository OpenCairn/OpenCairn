#!/usr/bin/env bash
# resolve-claude-project-dir.sh - locate the Claude Code project directory(ies)
# that belong to a vault, independent of the shell's current directory.
#
# Usage: resolve-claude-project-dir.sh <vault_path>
#
# Claude Code names each project directory under $CLAUDE_CONFIG_DIR/projects/
# (default ~/.claude/projects/) after the launch cwd with every "/" and "."
# replaced by "-". Deriving that name from `pwd` follows any earlier `cd`, so
# memory and plan attribution can land in another project's directory. This
# script derives it from the vault path instead:
#
#   1. derived: <projects>/<vault path with [/.] -> ->, printed when it exists
#   2. sweep:   every <projects>/*/ whose transcripts (*.jsonl, bounded by
#               --max-filesize) mention the vault path literally; each dir once
#
# stdout: one absolute project directory per line. stderr: which mode produced
# the result ("derived" or "sweep"). Exit 1 when neither finds a directory.
# Env: CLAUDE_CONFIG_DIR (default ~/.claude); CLAUDE_PROJECT_SWEEP_MAX_FILESIZE
# (default 50M, passed to rg --max-filesize).

set -euo pipefail

VAULT="${1:?usage: resolve-claude-project-dir.sh <vault_path>}"
VAULT="${VAULT%/}"
PROJECTS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
MAX_SIZE="${CLAUDE_PROJECT_SWEEP_MAX_FILESIZE:-50M}"

derived="$PROJECTS/$(printf '%s' "$VAULT" | sed 's#[/.]#-#g')"
if [ -d "$derived" ]; then
    echo "project dir: derived from vault path" >&2
    printf '%s\n' "$derived"
    exit 0
fi

if [ ! -d "$PROJECTS" ]; then
    echo "project dir: none ($PROJECTS does not exist)" >&2
    exit 1
fi
if ! command -v rg >/dev/null 2>&1; then
    echo "project dir: derived path $derived absent and rg unavailable for the sweep" >&2
    exit 1
fi

# --max-depth 2: <projects>/<dir>/<file>.jsonl only; memory/ and deeper are skipped.
found=$(rg -l -F --no-ignore --max-filesize "$MAX_SIZE" --max-depth 2 -g '*.jsonl' \
            -- "$VAULT" "$PROJECTS" 2>/dev/null \
        | while IFS= read -r f; do dirname "$f"; done | sort -u) || true

if [ -z "$found" ]; then
    echo "project dir: none (derived path $derived absent; no transcript under $PROJECTS names $VAULT)" >&2
    exit 1
fi

echo "project dir: sweep (derived path $derived absent)" >&2
printf '%s\n' "$found"
