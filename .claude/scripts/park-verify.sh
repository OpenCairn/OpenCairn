#!/usr/bin/env bash
# park-verify.sh - mechanical post-park verification for /park
#
# Usage: park-verify.sh <vault> <session-log> <N> [--ident STR]... [--touched PATH]...
#   --ident    a distinctive substring per item/identifier the session completed
#              (matched fixed-string, case-insensitive, against unchecked "- [ ]" lines)
#   --touched  each file the session+park created or edited (repeatable)
#
# Deterministic checks only - judgement stays with the caller:
#   numbering   session-log headings carry no duplicate session numbers;
#               exactly one "## Session N" heading exists
#   sections    Session N block has "### Summary", both "### Files Created" and
#               "### Files Updated" (checked as two separate headings),
#               and exactly one "### Pickup Context"
#   project     block's "**Project:**" line exists (printed for caller comparison)
#   separator   no OPENCAIRN-LOCKED-EDIT-SEP token left in planning files,
#               the session log, or any touched file
#   lint        touched .md files: joined list items ("x- [ ]"), 3+ consecutive blanks
#   closure     per --ident: unchecked "- [ ]" matches in This Week.md, Tickler.md,
#               and touched 03 Projects / 04 Areas files -> REVIEW (caller flips
#               genuinely-completed items, surfaces adjacent-open ones)
#   backfill    each touched vault file appears in the block's Files Created /
#               Files Updated / Files Deleted lists
#
# Output: "PASS|FAIL|REVIEW <check>: <detail>" lines, then "RESULT: PASS|REVIEW|FAIL".
# Exit 1 if any FAIL, else 0 (REVIEW lines need caller triage but are not failures).
set -euo pipefail

usage() { echo "Usage: $0 <vault> <session-log> <N> [--ident STR]... [--touched PATH]..." >&2; exit 1; }
[ $# -ge 3 ] || usage
VAULT="$1"; LOG="$2"; N="$3"; shift 3
case "$N" in ''|*[!0-9]*) usage ;; esac
[ -f "$LOG" ] || { echo "ERROR: session log not found: $LOG" >&2; exit 1; }

IDENTS=(); TOUCHED=()
while [ $# -gt 0 ]; do
    case "$1" in
        --ident)   [ $# -ge 2 ] || usage; IDENTS+=("$2"); shift 2 ;;
        --touched) [ $# -ge 2 ] || usage; TOUCHED+=("$2"); shift 2 ;;
        *) usage ;;
    esac
done

FAILS=0; REVIEWS=0
pass()   { echo "PASS $1: $2"; }
fail()   { echo "FAIL $1: $2"; FAILS=$((FAILS+1)); }
review() { echo "REVIEW $1: $2"; REVIEWS=$((REVIEWS+1)); }

# --- numbering ---------------------------------------------------------------
DUPES=$(grep -E '^## Session [0-9]+ ' "$LOG" | awk '{print $3}' | sort | uniq -d || true)
if [ -n "$DUPES" ]; then
    fail numbering "duplicate session number(s) in log: $(echo "$DUPES" | tr '\n' ' ')"
else
    pass numbering "no duplicate session numbers"
fi
COUNT_N=$(grep -c -E "^## Session $N " "$LOG" || true)
if [ "$COUNT_N" -ne 1 ]; then
    fail numbering "expected exactly one '## Session $N' heading, found $COUNT_N"
fi

# --- extract Session N block -------------------------------------------------
BLOCK=$(awk -v n="$N" '$0 ~ "^## Session " n " " {p=1; next} p && /^## Session /{exit} p' "$LOG")

# --- sections ----------------------------------------------------------------
if ! printf '%s\n' "$BLOCK" | grep -q '^### Summary'; then
    fail sections "Session $N has no '### Summary'"
else
    pass sections "Summary present"
fi
for SEC in "### Files Created" "### Files Updated"; do
    if ! printf '%s\n' "$BLOCK" | grep -q "^$SEC"; then
        fail sections "Session $N has no '$SEC' (backfill contract)"
    else
        pass sections "${SEC#\#\#\# } present"
    fi
done
PC=$(printf '%s\n' "$BLOCK" | grep -c '^### Pickup Context' || true)
if [ "$PC" -ne 1 ]; then
    fail sections "Session $N has $PC '### Pickup Context' sections (need exactly 1)"
else
    pass sections "Pickup Context present exactly once"
fi

# --- project line ------------------------------------------------------------
PROJ=$(printf '%s\n' "$BLOCK" | grep '^\*\*Project:\*\*' | tail -1 || true)
if [ -n "$PROJ" ]; then
    pass project "$PROJ"
else
    fail project "Session $N has no '**Project:**' line in Pickup Context"
fi

# --- separator tokens --------------------------------------------------------
SEP_TARGETS=("$LOG" "$VAULT/01 Now/This Week.md" "$VAULT/01 Now/Tickler.md")
for t in "${TOUCHED[@]:-}"; do [ -n "$t" ] && SEP_TARGETS+=("$t"); done
mapfile -t SEP_TARGETS < <(printf '%s\n' "${SEP_TARGETS[@]}" | awk '!seen[$0]++')
SEP_HITS=""
for t in "${SEP_TARGETS[@]}"; do
    [ -f "$t" ] || continue
    # Skill/command/script files legitimately QUOTE the separator token (park.md
    # documents the post-locked-edit grep; locked-edit.sh defines it). Same
    # carve-out the lint check below makes, and for the same reason: a file that
    # documents a marker is not a file that leaked one. locked-edit.sh only ever
    # writes planning files, so nothing under .claude/ can carry a real leak.
    case "$t" in */.claude/*) continue ;; esac
    h=$(grep -n 'OPENCAIRN-LOCKED-EDIT-SEP' "$t" 2>/dev/null | head -3 || true)
    [ -n "$h" ] && SEP_HITS="$SEP_HITS$t: $h; "
done
if [ -n "$SEP_HITS" ]; then
    fail separator "leftover locked-edit separator token(s): $SEP_HITS"
else
    pass separator "no leftover separator tokens (${#SEP_TARGETS[@]} files checked)"
fi

# --- lint on touched .md files ----------------------------------------------
LINT_HITS=""
for t in "${TOUCHED[@]:-}"; do
    [ -n "$t" ] && [ -f "$t" ] || continue
    case "$t" in *.md) ;; *) continue ;; esac
    case "$t" in */.claude/*) continue ;; esac        # skill/command/script files carry quoted checkbox templates - never lint them, in or out of the vault
    case "$t" in "$VAULT"/*) ;; *) continue ;; esac   # lint vault content files only
    j=$(grep -nE '[^[:space:]]- \[[ x]\]' "$t" | head -3 || true)
    [ -n "$j" ] && LINT_HITS="$LINT_HITS$t joined-list: $j; "
    b=$(awk 'NF{n=0;next}{n++} n==3{print FNR": 3+ blank lines"; exit}' "$t" || true)
    [ -n "$b" ] && LINT_HITS="$LINT_HITS$t $b; "
done
if [ -n "$LINT_HITS" ]; then
    fail lint "$LINT_HITS"
else
    pass lint "touched .md files clean (joined lists, blank-line residue)"
fi

# --- closure greps per ident -------------------------------------------------
# Fixed-string ident match first (no regex injection), then unchecked-checkbox filter.
CLOSURE_TARGETS=("$VAULT/01 Now/This Week.md" "$VAULT/01 Now/Tickler.md")
for t in "${TOUCHED[@]:-}"; do
    case "$t" in
        *"03 Projects/"*|*"04 Areas/"*) [ -f "$t" ] && CLOSURE_TARGETS+=("$t") ;;
    esac
done
for ident in "${IDENTS[@]:-}"; do
    [ -n "$ident" ] || continue
    HITS=""
    for t in "${CLOSURE_TARGETS[@]}"; do
        [ -f "$t" ] || continue
        h=$(grep -n -i -F -- "$ident" "$t" | grep -E '^[0-9]+:[[:space:]]*-[[:space:]]*\[ \]' | cut -c1-100 || true)
        [ -n "$h" ] && HITS="$HITS$t -> $(echo "$h" | tr '\n' ' '); "
    done
    if [ -n "$HITS" ]; then
        review closure "ident '$ident' has unchecked matches: $HITS"
    else
        pass closure "ident '$ident': no unchecked [ ] match in ${#CLOSURE_TARGETS[@]} planning file(s)"
    fi
done
[ "${#IDENTS[@]}" -eq 0 ] && pass closure "no idents supplied (nothing completed to grep)"

# --- backfill coverage -------------------------------------------------------
FILES_SECTIONS=$(printf '%s\n' "$BLOCK" | awk '/^### Files (Created|Updated|Deleted)/{f=1;next} /^### /{f=0} f')
# Non-vault paths reduce to a 3-directory suffix (".claude/commands/x.md"). Mirror
# pairs (personal + repo copy of the same file) still collapse to one needle, so
# count occurrences: a needle shared by K touched paths must appear >= K times.
declare -A NEEDLE_WANT=()
NEEDLE_ORDER=()
for t in "${TOUCHED[@]:-}"; do
    [ -n "$t" ] || continue
    [ "$t" = "$LOG" ] && continue   # the log never lists itself
    case "$t" in
        "$VAULT"/*) needle="${t#"$VAULT"/}" ;;
        *)          d1="$(dirname "$t")"; d2="$(dirname "$d1")"
                    needle="$(basename "$d2")/$(basename "$d1")/$(basename "$t")" ;;
    esac
    [ -n "${NEEDLE_WANT[$needle]:-}" ] || NEEDLE_ORDER+=("$needle")
    NEEDLE_WANT[$needle]=$(( ${NEEDLE_WANT[$needle]:-0} + 1 ))
done
MISSING=""
for needle in "${NEEDLE_ORDER[@]:-}"; do
    [ -n "$needle" ] || continue
    want="${NEEDLE_WANT[$needle]}"
    got=$(printf '%s\n' "$FILES_SECTIONS" | grep -c -i -F -- "$needle" || true)
    if [ "$got" -lt "$want" ]; then
        if [ "$want" -gt 1 ]; then
            MISSING="$MISSING$needle (expected $want entries, found $got); "
        else
            MISSING="$MISSING$needle; "
        fi
    fi
done
if [ -n "$MISSING" ]; then
    fail backfill "touched but absent from Session $N Files lists: $MISSING"
else
    pass backfill "all ${#TOUCHED[@]} touched file(s) recorded in Files lists"
fi

# --- result ------------------------------------------------------------------
if [ "$FAILS" -gt 0 ]; then
    echo "RESULT: FAIL ($FAILS fail, $REVIEWS review)"
    exit 1
elif [ "$REVIEWS" -gt 0 ]; then
    echo "RESULT: REVIEW ($REVIEWS item(s) need caller triage)"
else
    echo "RESULT: PASS"
fi
exit 0
