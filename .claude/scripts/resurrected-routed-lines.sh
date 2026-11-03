#!/usr/bin/env bash
# Read-only, report-only. Flags a line that left a planning file in vault commit A *and
# appeared in another vault file in the same commit A* (a routing move), then was re-added
# to the planning file in a later commit B. Ordinary carry-forward (no paired addition
# elsewhere) is ignored. Needs the vault to be a git repository with frequent commits;
# a routing move and a re-add inside one commit are invisible.
# Usage: resurrected-routed-lines.sh <since> <until> [planning-file...]
#   Bare YYYY-MM-DD dates are whole local days, both inclusive: <since> from 00:00:00,
#   <until> to 23:59:59. Any other form is passed to git as given. "Local" is $HYGIENE_TZ
#   when set (an IANA zone such as Region/City), else the system zone. Explicit times
#   without a zone are read in the same zone.
#   Planning files are vault-relative; default "01 Now/This Week.md".
# Env: VAULT_PATH (required), HYGIENE_TZ (optional).
# PASS: "ROUTED-THEN-RESURRECTED: 0". FAIL: one HIT row per line; review each against the
# session record before acting. Exit 2 = bad input or no git history (check did not run).
set -uo pipefail
VAULT=${VAULT_PATH:?VAULT_PATH not set}
[ $# -ge 2 ] || { echo "usage: $0 <since> <until> [planning-file...]" >&2; exit 2; }
[ -n "${HYGIENE_TZ:-}" ] && export TZ="$HYGIENE_TZ"
bound() {  # $1 = date argument, $2 = start|end
  if [[ $1 =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    local t=00:00:00; [ "$2" = end ] && t=23:59:59
    date -d "$1 $t" '+%Y-%m-%d %H:%M:%S %z' || return 1
  else printf '%s\n' "$1"; fi
}
since=$(bound "$1" start) && until=$(bound "$2" end) || { echo "unparseable date" >&2; exit 2; }
shift 2
git -C "$VAULT" rev-parse --git-dir >/dev/null 2>&1 || { echo "ROUTED-THEN-RESURRECTED: unavailable (vault is not a git repository)"; exit 2; }
files=("$@"); [ ${#files[@]} -eq 0 ] && files=("01 Now/This Week.md")
echo "window: $since .. $until"
total=0
for f in "${files[@]}"; do
  cands=$(git -C "$VAULT" log --reverse --since="$since" --until="$until" -p --format='@@COMMIT %h %ad' --date=format-local:'%m-%d_%H:%M' -- "$f" |
  awk '
    /^@@COMMIT /{c=$2; t=$3; next}
    /^(\+\+\+|---) /{next}
    /^-/ { l=substr($0,2); if (l ~ /[[:alnum:]]/ && l !~ /^#/) {rem[l]=c; rt[l]=t}; next }
    /^\+/ { l=substr($0,2); if ((l in rem) && rem[l] != c) { print rem[l] "\t" rt[l] "\t" c "\t" t "\t" l; delete rem[l] } }
  ')
  while IFS=$'\t' read -r ca ta cb tb line; do
    [ -z "${ca:-}" ] && continue
    key=$(printf '%s' "$line" | sed -E 's/^[[:space:]]*- \[[ x]\] //' )
    # same-commit addition in a non-planning, non-archive file = routing move to a topic home
    # (planning-folder carry flow and archived day reports are the designed flow, so excluded)
    dest=$(git -C "$VAULT" show --format= --unified=0 "$ca" -- . ":(exclude)$f" ":(exclude)01 Now" ":(exclude)06 Archive" ":(exclude,glob)**/*Conflicted copy*" 2>/dev/null |
           awk -v k="$key" '/^\+\+\+ /{file=substr($0,7); sub(/\t$/,"",file); next} /^\+/ && index($0,k){print file; exit}')
    if [ -n "$dest" ]; then
      echo "HIT $f | routed $ta ($ca) -> $dest | re-added $tb ($cb) | ${key:0:120}"
      total=$((total+1))
    fi
  done <<< "$cands"
done
echo "ROUTED-THEN-RESURRECTED: $total"
