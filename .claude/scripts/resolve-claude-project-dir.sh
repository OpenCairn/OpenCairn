#!/usr/bin/env bash
# resolve-claude-project-dir.sh - locate the Claude Code project directory(ies)
# that belong to the running session or to a vault, independent of the shell's
# current directory.
#
# Usage: resolve-claude-project-dir.sh <vault_path>
#
# Claude Code names each project directory under $CLAUDE_CONFIG_DIR/projects/
# (default ~/.claude/projects/) after the launch cwd with every non-alphanumeric
# character replaced by "-" (code.claude.com/docs/en/sessions, "where
# transcripts are stored"): "/", ".", "_", " " and the rest all become "-".
# Deriving that name from `pwd` follows any earlier `cd`, so memory and plan
# attribution can land in another project's directory. A session launched from
# a parent of the vault (cwd ~, vault ~/Files) keeps its transcript and memory/
# under the parent's project dir, not the vault's. Resolution order:
#
#   1. session: the directory holding this session's own transcript,
#               <projects>/*/<session id>.jsonl (id via lib-session.sh)
#   2. derived: <projects>/<vault path with [^A-Za-z0-9] -> ->, printed when it exists
#   3. sweep:   every <projects>/*/ whose transcripts (*.jsonl, bounded by
#               --max-filesize) mention the vault path literally; each dir once
#
# stdout: one absolute project directory per line. stderr: which mode produced
# the result ("this session's transcript", "derived" or "sweep"). Exit 1 when
# none finds a directory:
# "project dir: none (...)" is a confirmed absence (derived dir absent and no
# transcript names the vault); "project dir: lookup failed (...)" means the
# sweep could not run (rg unavailable) and says nothing about existence.
# Env: CLAUDE_CONFIG_DIR (default ~/.claude); CLAUDE_PROJECT_SWEEP_MAX_FILESIZE
# (default 50M, passed to rg --max-filesize).

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib-session.sh
. "$HERE/lib-session.sh"

VAULT="${1:?usage: resolve-claude-project-dir.sh <vault_path>}"
VAULT="${VAULT%/}"
PROJECTS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
MAX_SIZE="${CLAUDE_PROJECT_SWEEP_MAX_FILESIZE:-50M}"

SID="$(_session_id)"
if [ -n "$SID" ] && [ -d "$PROJECTS" ]; then
    for transcript in "$PROJECTS"/*/"$SID".jsonl; do
        [ -f "$transcript" ] || continue
        echo "project dir: this session's transcript" >&2
        dirname "$transcript"
        exit 0
    done
fi

derived="$PROJECTS/$(printf '%s' "$VAULT" | sed 's#[^A-Za-z0-9]#-#g')"
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
    echo "project dir: lookup failed (derived path $derived absent; rg unavailable for the transcript sweep)" >&2
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
