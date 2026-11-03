#!/usr/bin/env bash
# Read-only, report-only. Lists lines ADDED in the window to planning docs, project docs and
# session logs that carry a line-number locator ("line N" / "lines N-M") and that still
# exist at <as-of> revision (default HEAD). A line number breaks silently when the target
# file gains or loses a line above it; cite a heading, an ID or quoted text instead.
# Needs the vault to be a git repository.
# Usage: locator-rotguns.sh <since> <until> [as-of-rev]
#   Bare YYYY-MM-DD dates are whole local days, both inclusive (see HYGIENE_TZ).
# Env: VAULT_PATH (required); HYGIENE_TZ (optional IANA zone, else system zone);
#   HYGIENE_LOCATOR_IGNORE (optional; default $VAULT_PATH/.claude/hygiene-locator-ignore):
#   one grep -E pattern per line, '#' comments, matched against each "file | locator" row.
#   List rows whose target is frozen (a verbatim transcript, an archived record), where a
#   line number is stable and legitimate.
# PASS: "LOCATOR-ROTGUNS: 0". FAIL: one row per surviving line -> rewrite the locator, or add
# an ignore pattern if the target is frozen. Exit 2 = bad input or no git history.
set -uo pipefail
VAULT=${VAULT_PATH:?VAULT_PATH not set}
[ $# -ge 2 ] || { echo "usage: $0 <since> <until> [as-of-rev]" >&2; exit 2; }
[ -n "${HYGIENE_TZ:-}" ] && export TZ="$HYGIENE_TZ"
bound() {
  if [[ $1 =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    local t=00:00:00; [ "$2" = end ] && t=23:59:59
    date -d "$1 $t" '+%Y-%m-%d %H:%M:%S %z' || return 1
  else printf '%s\n' "$1"; fi
}
since=$(bound "$1" start) && until=$(bound "$2" end) || { echo "unparseable date" >&2; exit 2; }
rev=${3:-HEAD}
git -C "$VAULT" rev-parse --verify -q "$rev^{commit}" >/dev/null || { echo "LOCATOR-ROTGUNS: unavailable (vault is not a git repository or $rev is unknown)"; exit 2; }
IGN=${HYGIENE_LOCATOR_IGNORE:-$VAULT/.claude/hygiene-locator-ignore}
PAT=$(mktemp); trap 'rm -f "$PAT"' EXIT
[ -f "$IGN" ] && grep -v '^[[:space:]]*#' "$IGN" | grep -v '^[[:space:]]*$' > "$PAT"
npat=$(grep -c . "$PAT")
re='\b[Ll]ines? [0-9]+([–-][0-9]+)?\b'
paths=("01 Now" "03 Projects" "06 Archive/OpenCairn/Session Logs" ":(exclude,glob)**/*Conflicted copy*" ":(exclude,glob)**/*.sync-conflict-*")
echo "window: $since .. $until; as-of $rev; ignore patterns: $npat"
rows=$(git -C "$VAULT" log --since="$since" --until="$until" -p --format= --unified=0 -- "${paths[@]}" |
  awk '/^\+\+\+ b\//{f=substr($0,7); sub(/\t$/,"",f); next} /^\+[^+]/{print f "\t" substr($0,2)}' |
  grep -P "\t.*($re)" | sort -u |
  while IFS=$'\t' read -r f l; do
    # no grep -q below: an early exit SIGPIPEs git show and pipefail then reports a false miss
    # survival key = locator plus up to 25 preceding chars (tolerates later edits elsewhere in the line)
    key=$(grep -oP ".{0,25}(?:$re)" <<<"$l" | head -1)
    git -C "$VAULT" show "$rev:$f" 2>/dev/null | grep -F -- "$key" >/dev/null && printf '%s | %s\n' "$f" "$key"
  done | sort -u)
if [ -n "$rows" ] && [ "$npat" -gt 0 ]; then
  ignored=$(grep -E -c -f "$PAT" <<<"$rows")
  rows=$(grep -E -v -f "$PAT" <<<"$rows")
  echo "ignored by pattern: $ignored"
fi
[ -n "$rows" ] && echo "$rows"
echo "LOCATOR-ROTGUNS: $(printf '%s' "$rows" | grep -c .)"
