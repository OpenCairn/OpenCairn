#!/usr/bin/env bash
# Read-only, report-only. Lists Claude Code sessions (by first transcript timestamp) in a
# window that called a hosted-document tool (built-in Artifact, Claude Docs create/batch/update,
# claude-artifacts publish/edit). A hit is not a violation: documents and mock-ups default to
# local or vault files, so each hit needs a check of whether the user asked for a hosted one.
# Usage: hosted-doc-calls.sh <since-YYYY-MM-DD> <until-YYYY-MM-DD> [projects-dir]
#   Whole local days, both inclusive (local = $HYGIENE_TZ when set, else the system zone).
#   projects-dir: one Claude Code project directory holding *.jsonl transcripts
#   (default: ${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<VAULT_PATH with non-alphanumerics as ->).
# PASS: "SESSIONS-WITH-HOSTED-DOC-CALLS: 0". Otherwise one row per session, each ending
# "-> check whether the user asked". Exit 2 = bad input or missing projects dir.
set -uo pipefail
[ $# -ge 2 ] || { echo "usage: $0 <since-YYYY-MM-DD> <until-YYYY-MM-DD> [projects-dir]" >&2; exit 2; }
[ -n "${HYGIENE_TZ:-}" ] && export TZ="$HYGIENE_TZ"
since=$1; until=$2
for d in "$since" "$until"; do [[ $d =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && date -d "$d" >/dev/null 2>&1 || { echo "dates must be YYYY-MM-DD" >&2; exit 2; }; done
if [ $# -ge 3 ]; then P=$3
else P="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(printf '%s' "${VAULT_PATH:?VAULT_PATH not set}" | sed 's#[^A-Za-z0-9]#-#g')"; fi
[ -d "$P" ] || { echo "SESSIONS-WITH-HOSTED-DOC-CALLS: unavailable (no projects dir $P)"; exit 2; }
pat='"type":"tool_use","id":"[^"]*","name":"(Artifact|mcp__claude_ai_Claude_Docs__(create|batch|update)|mcp__claude-artifacts__publish_(version|files)|mcp__claude-artifacts__edit_version)"'
echo "window: $since .. $until (local days, inclusive); transcripts: $P"
rows=$(find "$P" -maxdepth 1 -name '*.jsonl' -newermt "$since 00:00:00" -print0 |
  while IFS= read -r -d '' f; do
    ts=$(grep -m1 -o '"timestamp":"[^"]*"' "$f" | cut -d'"' -f4)
    [ -z "$ts" ] && continue
    t=$(date -d "$ts" +%F 2>/dev/null) || continue
    [[ "$t" < "$since" || "$t" > "$until" ]] && continue
    calls=$(grep -oE "$pat" "$f" | sed -E 's/.*"name":"([^"]*)"/\1/' | sort | uniq -c | awk '{printf "%s×%s ",$2,$1}')
    [ -z "$calls" ] && continue
    echo "$t $(basename "$f" .jsonl) ${calls}-> check whether the user asked"
  done | sort)
[ -n "$rows" ] && echo "$rows"
echo "SESSIONS-WITH-HOSTED-DOC-CALLS: $(printf '%s' "$rows" | grep -c .)"
