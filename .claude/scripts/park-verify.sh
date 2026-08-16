#!/usr/bin/env bash
# park-verify.sh - mechanical post-park verification for /park
#
# Usage: park-verify.sh <vault> <session-log> <N> [--ident STR]... [--touched PATH]...
#   --ident    a distinctive substring per item/identifier the session completed
#              (matched fixed-string, case-insensitive, against unchecked "- [ ]" lines).
#              Must be distinctive: a bare number under ~4 digits matches digit runs
#              inside phone numbers, order IDs and amounts, burying real hits in noise.
#   --touched  each file the session+park created or edited (repeatable)
#
# Paths (<session-log> and --touched) may be absolute, ~-prefixed, or relative to
# <vault> - all three are normalised on entry.
#
# Deterministic checks only - judgement stays with the caller:
#   numbering   session-log headings carry no duplicate session numbers;
#               exactly one "## Session N" heading exists
#   sections    Session N block has "### Summary", both "### Files Created" and
#               "### Files Updated" (checked as two separate headings),
#               and exactly one "### Pickup Context"
#   project     block's "**Project:**" line exists (printed for caller comparison)
#   separator   no stranded locked-edit delimiter LINE in planning files, the
#               session log, or any touched file (the padded "====SEP====" form;
#               prose that merely names the token is not a leak)
#   lint        touched .md files: joined list items ("x- [ ]"), 3+ consecutive
#               blanks; exempts `- [ ]` in code spans and "==- [ ]==" highlights
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

# --- path normalisation ------------------------------------------------------
# Every downstream check keys off the same paths, and all of them used to assume
# an absolute argument. A relative path (the natural form to paste, since it is
# what the session log itself uses) fell through the needle builder's non-vault
# branch to an unmatchable "./01 Now/This Week.md" -> false FAIL backfill; the
# SAME path also missed the lint branch's "$VAULT"/* guard, so zero files were
# linted and the check still printed PASS. One root cause, two symptoms, the
# silent PASS being the dangerous half. Resolve relative args here, once, so no
# check downstream has to care again.
VAULT="${VAULT%/}"
norm_path() {
    # Strip any leading "./" FIRST. Joining it produces "$VAULT/./x", whose
    # vault-relative needle is "./x" — the same unmatchable form this function
    # exists to eliminate, reintroduced by the one path spelling the pre-fix
    # failure output actually printed (and so the one an operator is most
    # likely to paste straight back in).
    set -- "${1#./}"
    case "$1" in
        /*)    printf '%s\n' "$1" ;;
        "~/"*) printf '%s\n' "$HOME/${1#\~/}" ;;
        *)     printf '%s\n' "$VAULT/$1" ;;
    esac
}
LOG="$(norm_path "$LOG")"
[ -f "$LOG" ] || { echo "ERROR: session log not found: $LOG" >&2; exit 1; }

IDENTS=(); TOUCHED=()
while [ $# -gt 0 ]; do
    case "$1" in
        --ident)   [ $# -ge 2 ] || usage; IDENTS+=("$2"); shift 2 ;;
        --touched) [ $# -ge 2 ] || usage; TOUCHED+=("$(norm_path "$2")"); shift 2 ;;
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
# Feed the captured block directly. With `pipefail`, `printf | grep -q` reports
# failure when grep finds an early match and closes a block larger than the pipe
# buffer, because printf then exits on SIGPIPE.
if ! grep -q '^### Summary' <<< "$BLOCK"; then
    fail sections "Session $N has no '### Summary'"
else
    pass sections "Summary present"
fi
for SEC in "### Files Created" "### Files Updated"; do
    if ! grep -q "^$SEC" <<< "$BLOCK"; then
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
    # writes planning files, so harness instruction/skill/command surfaces cannot
    # carry a real leak.
    case "$t" in
        */.claude/*|*/.codex/AGENTS.md|*/.codex/skills/*|*/codex/AGENTS.md|*/codex/skills/*) continue ;;
    esac
    # Match the leaked ARTEFACT, not the token. What locked-edit.sh can strand in
    # a file is its padded stdin delimiter alone on a line; a vault doc that
    # merely names the token in prose (this repo's own monitor log does, in the
    # very observations reporting this check's false FAILs) never produces one.
    # Anchoring here is what makes those hits unresolvable-by-construction, since
    # "fixing" them would mean editing an earlier session's record.
    h=$(grep -nE '^[[:space:]]*={4,}OPENCAIRN-LOCKED-EDIT-SEP={4,}[[:space:]]*$' "$t" 2>/dev/null | head -3 || true)
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
    case "$t" in                                      # skill/command/script files carry quoted checkbox templates - never lint them, in or out of the vault
        */.claude/*|*/.codex/AGENTS.md|*/.codex/skills/*|*/codex/AGENTS.md|*/codex/skills/*) continue ;;
    esac
    case "$t" in "$VAULT"/*) ;; *) continue ;; esac   # lint vault content files only
    # A real joined list is "textrun- [ ] next item". Two preceding characters are
    # never that: a backtick (prose quoting `- [ ]`, common in corrections entries
    # and skill-monitor observations whose whole subject IS checkbox syntax) and
    # "=" (Obsidian's highlight form, "==- [ ] item=="). Both were
    # flagged repeatedly against content the session never touched, and neither
    # can be "fixed" without corrupting the file.
    j=$(grep -nE '[^[:space:]=`]- \[[ x]\]' "$t" | head -3 || true)
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
# Home paths keep a short alternate suffix for human-written Files rows. Other
# absolute paths stay absolute: reconstructing a three-component suffix turns a
# root-level path such as /tmp/file into the nonexistent //tmp/file.
# Mirror pairs can still collapse to one needle, so count occurrences: a needle
# shared by K touched paths must appear >= K times.
declare -A NEEDLE_WANT=()
declare -A NEEDLE_ALT=()
NEEDLE_ORDER=()
for t in "${TOUCHED[@]:-}"; do
    [ -n "$t" ] || continue
    [ "$t" = "$LOG" ] && continue   # the log never lists itself
    d1="$(dirname "$t")"; d2="$(dirname "$d1")"
    suffix="$(basename "$d2")/$(basename "$d1")/$(basename "$t")"
    case "$t" in
        "$VAULT"/*) needle="${t#"$VAULT"/}"; alt="" ;;
        # A file one level under a home dotdir reduces to "<user>/.config/x.json",
        # which no sane log entry contains - it is written "~/.config/x.json". Prefer
        # the ~-form and keep the suffix as an alternate for logs using the long form.
        "$HOME"/*)  needle="~/${t#"$HOME"/}"; alt="$suffix" ;;
        *)          needle="$t"; alt="" ;;
    esac
    [ -n "${NEEDLE_WANT[$needle]:-}" ] || NEEDLE_ORDER+=("$needle")
    NEEDLE_WANT[$needle]=$(( ${NEEDLE_WANT[$needle]:-0} + 1 ))
    NEEDLE_ALT[$needle]="$alt"
done
MISSING=""
for needle in "${NEEDLE_ORDER[@]:-}"; do
    [ -n "$needle" ] || continue
    want="${NEEDLE_WANT[$needle]}"
    got=$(printf '%s\n' "$FILES_SECTIONS" | grep -c -i -F -- "$needle" || true)
    alt="${NEEDLE_ALT[$needle]:-}"
    if [ "$got" -lt "$want" ] && [ -n "$alt" ]; then
        got=$(printf '%s\n' "$FILES_SECTIONS" | grep -c -i -F -- "$alt" || true)
    fi
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
    # Scoped to the ARGUMENTS, not to the session. "all N touched files recorded"
    # read as a coverage statement about the run and was written up as one, off a
    # --touched list narrower than the log's own Files list. The check can only
    # ever speak for what it was handed; the reverse-coverage REVIEW below is what
    # speaks for the rest.
    pass backfill "all ${#TOUCHED[@]} path(s) PASSED TO --touched are recorded in Files lists (says nothing about paths not passed)"
fi

# --- reverse coverage: does the log list files --touched never saw? ----------
mapfile -t LOGGED < <(printf '%s\n' "$FILES_SECTIONS" \
    | awk '/^[[:space:]]*- /{sub(/^[[:space:]]*- /,""); i=index($0," - "); if(i>0) $0=substr($0,1,i-1); if(length($0)) print}')
UNCOVERED=""
for lp in "${LOGGED[@]:-}"; do
    [ -n "$lp" ] || continue
    case "$lp" in [Nn][Oo][Nn][Ee]) continue ;; esac
    lp_abs="$(norm_path "$lp")"
    [ "$lp_abs" = "$LOG" ] && continue   # the log may list itself; it is checked separately
    # Compare on a canonical form. A $HOME path yields a "~/..." needle while the
    # log may well spell it "/home/<user>/..." — neither is a substring of the
    # other, so a raw comparison reports a path as uncovered that WAS passed.
    lp_c="$lp"; case "$lp_c" in "$HOME"/*) lp_c="~/${lp_c#"$HOME"/}" ;; esac
    hit=""
    for needle in "${NEEDLE_ORDER[@]:-}"; do
        [ -n "$needle" ] || continue
        n_c="$needle"; case "$n_c" in "$HOME"/*) n_c="~/${n_c#"$HOME"/}" ;; esac
        case "$n_c" in *"$lp_c"*) hit=1; break ;; esac
        case "$lp_c" in *"$n_c"*) hit=1; break ;; esac
    done
    [ -z "$hit" ] && UNCOVERED="$UNCOVERED$lp; "
done
if [ -n "$UNCOVERED" ]; then
    review backfill "Files lists name path(s) not passed to --touched, so no lint/separator check ran on them: $UNCOVERED"
else
    pass backfill "--touched covers every path the Session $N Files lists name"
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
