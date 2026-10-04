#!/usr/bin/env bash
# park-verify.sh - mechanical post-park verification for /park
#
# Usage: park-verify.sh <vault> <session-log> <N> [--ident STR]... [--touched PATH]...
#   --ident    a distinctive substring per item/identifier the session completed
#              (matched fixed-string, case-insensitive, against unchecked "- [ ]" lines).
#              Must be distinctive: a bare number under ~4 digits matches digit runs
#              inside phone numbers, order IDs and amounts, burying real hits in noise.
#              A doc name, a common word or a link target is not distinctive either:
#              it matches every open item that mentions or links that doc. Prefer
#              the completed item's own wording.
#   --touched  each file the session+park created or edited (repeatable)
#   --reference PATH SHA256  preserved external reference, hash-bound by the
#              review wrapper; still checked for Files-list coverage
#   --nonlocal PATH  explicitly classified remote/secret-bearing artefact;
#              retain Files-list coverage but never inspect/print its contents
#
# Paths (<session-log> and --touched) may be absolute, ~-prefixed, or relative to
# <vault> - all three are normalised on entry.
#
# Deterministic checks only - judgement stays with the caller:
#   numbering   session-log headings carry no duplicate session numbers;
#               exactly one "## Session N" heading exists
#   sections    Session N block has every required full-tier heading, with
#               exactly one "### Pickup Context"
#   project     block's "**Project:**" line exists (printed for caller comparison)
#   separator   no stranded locked-edit delimiter LINE in planning files, the
#               session log, or any touched file (the padded "====SEP====" form;
#               prose that merely names the token is not a leak)
#   lint        touched .md files: joined list items ("x- [ ]"), 3+ consecutive
#               blanks; exempts `- [ ]` in code spans and "==- [ ]==" highlights
#   closure     per --ident: unchecked "- [ ]" matches in This Week.md, Tickler.md,
#               and touched 03 Projects / 04 Areas files -> REVIEW (caller flips
#               genuinely-completed items, surfaces adjacent-open ones). Each
#               hit is labelled: [text] plain wording, [link] the visible name of
#               an unaliased wikilink. Hits only in a hidden link target (aliased
#               target, folder prefix, URL) or starting mid-word are listed as
#               [link-target] / [word-part] but do not raise REVIEW
#   touched     each --touched path exists, unless a Files Deleted row or
#               --nonlocal accounts for it
#   backfill    each touched file matches a Files Created / Files Updated /
#               Files Deleted row by complete resolved path; reverse coverage compares
#               Created/Updated rows only, minus off-host forms ("host:/path",
#               "C:\path") that name nothing local to lint
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

IDENTS=(); TOUCHED=(); REFERENCES=(); REFERENCE_HASHES=(); NONLOCAL=()
while [ $# -gt 0 ]; do
    case "$1" in
        --ident)   [ $# -ge 2 ] || usage; IDENTS+=("$2"); shift 2 ;;
        --touched) [ $# -ge 2 ] || usage; TOUCHED+=("$(norm_path "$2")"); shift 2 ;;
        --reference) [ $# -ge 3 ] || usage; REFERENCES+=("$(norm_path "$2")"); REFERENCE_HASHES+=("$3"); shift 3 ;;
        --nonlocal) [ $# -ge 2 ] || usage; NONLOCAL+=("$(norm_path "$2")"); shift 2 ;;
        *) usage ;;
    esac
done

# Repeated spellings normalised above identify one touched path, not extra files.
if [ "${#TOUCHED[@]}" -gt 0 ]; then
    mapfile -t TOUCHED < <(printf '%s\n' "${TOUCHED[@]}" | awk '!seen[$0]++')
fi

FAILS=0; REVIEWS=0
pass()   { echo "PASS $1: $2"; }
fail()   { echo "FAIL $1: $2"; FAILS=$((FAILS+1)); }
review() { echo "REVIEW $1: $2"; REVIEWS=$((REVIEWS+1)); }

is_nonlocal() {
    local candidate
    for candidate in "${NONLOCAL[@]:-}"; do
        [ "$candidate" = "$1" ] && return 0
    done
    return 1
}
for excluded in "${NONLOCAL[@]:-}"; do
    [ -n "$excluded" ] || continue
    declared=false
    for candidate in "${TOUCHED[@]:-}"; do
        [ "$candidate" = "$excluded" ] && declared=true
    done
    if [ "$excluded" = "$LOG" ] || [ "$declared" != true ]; then
        fail nonlocal "exemption must name a touched artefact other than the session log: $excluded"
        echo "RESULT: FAIL ($FAILS fail, $REVIEWS review)"
        exit 1
    fi
    pass nonlocal "content checks excluded; audit via supplied evidence: $excluded"
done
for reference in "${REFERENCES[@]:-}"; do
    if [ -n "$reference" ] && is_nonlocal "$reference"; then
        fail nonlocal "artefact cannot be both reference and nonlocal: $reference"
        echo "RESULT: FAIL ($FAILS fail, $REVIEWS review)"
        exit 1
    fi
done

# Reference bytes are evidence, not editable output. Validate their identity
# before exempting quoted source markers; never exempt live vault content.
VALID_REFERENCES=()
for i in "${!REFERENCES[@]}"; do
    ref="${REFERENCES[$i]}"
    if ! grep -qxF -- "$ref" <<< "$(printf '%s\n' "${TOUCHED[@]}")"; then
        fail reference "reference is not in --touched: $ref"
        continue
    fi
    if python3 -c 'import hashlib,re,sys; from pathlib import Path; p=Path(sys.argv[1]); v=Path(sys.argv[2]).resolve(); expected=sys.argv[3]; ok = re.fullmatch(r"[0-9a-f]{64}",expected) and p.is_file() and not p.is_symlink() and not p.resolve().is_relative_to(v) and hashlib.sha256(p.read_bytes()).hexdigest()==expected; sys.exit(0 if ok else 1)' "$ref" "$VAULT" "${REFERENCE_HASHES[$i]}" 2>/dev/null; then
        VALID_REFERENCES+=("$ref")
    else
        fail reference "external reference hash/path check failed: $ref"
    fi
done

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
SEP_SCANNED=0
SEP_SKIPPED=0
for t in "${SEP_TARGETS[@]}"; do
    if is_nonlocal "$t"; then
        SEP_SKIPPED=$((SEP_SKIPPED + 1))
        continue
    fi
    if [ "${#VALID_REFERENCES[@]}" -gt 0 ] && grep -qxF -- "$t" <<< "$(printf '%s\n' "${VALID_REFERENCES[@]}")"; then
        SEP_SKIPPED=$((SEP_SKIPPED + 1))
        continue
    fi
    if [ ! -f "$t" ]; then
        SEP_SKIPPED=$((SEP_SKIPPED + 1))
        continue
    fi
    # Skill/command/script files legitimately QUOTE the separator token (park.md
    # documents the post-locked-edit grep; locked-edit.sh defines it). Same
    # carve-out the lint check below makes, and for the same reason: a file that
    # documents a marker is not a file that leaked one. locked-edit.sh only ever
    # writes planning files, so harness instruction/skill/command surfaces cannot
    # carry a real leak.
    case "$t" in
        */06\ Archive/OpenCairn/.Session\ Transcripts/*.md) SEP_SKIPPED=$((SEP_SKIPPED + 1)); continue ;; # verbatim transcript exports preserve source shell snippets
        */06\ Archive/OpenCairn/Panel\ Runs/*) SEP_SKIPPED=$((SEP_SKIPPED + 1)); continue ;; # immutable panel evidence preserves quoted source markers
        */07\ System/.Provenance/*.snapshot.*) SEP_SKIPPED=$((SEP_SKIPPED + 1)); continue ;; # immutable provenance snapshots preserve exact source bytes
        */.claude/*|*/.codex/AGENTS.md|*/.codex/skills/*|*/codex/AGENTS.md|*/codex/skills/*) SEP_SKIPPED=$((SEP_SKIPPED + 1)); continue ;;
    esac
    SEP_SCANNED=$((SEP_SCANNED + 1))
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
    pass separator "no leftover separator tokens ($SEP_SCANNED scanned, $SEP_SKIPPED skipped)"
fi

# --- lint on touched .md files ----------------------------------------------
LINT_HITS=""
for t in "${TOUCHED[@]:-}"; do
    is_nonlocal "$t" && continue
    [ -n "$t" ] && [ -f "$t" ] || continue
    case "$t" in *.md) ;; *) continue ;; esac
    case "$t" in                                      # skill/command/script files carry quoted checkbox templates - never lint them, in or out of the vault
        */06\ Archive/OpenCairn/.Session\ Transcripts/*.md) continue ;; # verbatim exports retain source formatting by design
        */07\ System/.Provenance/*.snapshot.*) continue ;; # immutable provenance snapshots retain exact source formatting
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
# Python slices Unicode code points; cut -c can split UTF-8 bytes even in a UTF-8 locale.
CLOSURE_TARGETS=("$VAULT/01 Now/This Week.md" "$VAULT/01 Now/Tickler.md")
for t in "${TOUCHED[@]:-}"; do
    case "$t" in
        *"03 Projects/"*|*"04 Areas/"*) [ -f "$t" ] && CLOSURE_TARGETS+=("$t") ;;
    esac
done
for ident in "${IDENTS[@]:-}"; do
    [ -n "$ident" ] || continue
    HITS=""
    SOFT=""
    for t in "${CLOSURE_TARGETS[@]}"; do
        is_nonlocal "$t" && continue
        [ -f "$t" ] || continue
        h=$(grep -n -i -F -- "$ident" "$t" | grep -E '^[0-9]+:[[:space:]]*-[[:space:]]*\[ \]' || true)
        [ -n "$h" ] || continue
        # Classify where the ident sits, then excerpt. A line takes its strongest
        # occurrence; one the classifier cannot locate stays "text".
        # A missing or broken encoder must not erase a real unchecked match.
        if ! h=$(printf '%s\n' "$h" | python3 -c 'import re, sys
ident = sys.argv[1]
pattern = re.compile(re.escape(ident), re.IGNORECASE)
rank = {"word-part": 0, "link-target": 1, "link": 2, "text": 3}
def word_char(c):
    return c.isascii() and c.isalnum()
for raw in sys.stdin.buffer:
    line = raw.decode("utf-8", errors="backslashreplace").rstrip("\n")
    body = line.partition(":")[2]
    kinds = ["text"] * len(body)
    for m in re.finditer(r"\[\[([^\]]*)\]\]", body):
        a, b = m.span(1)
        bar = m.group(1).find("|")
        cut = a + bar + 1 if bar >= 0 else a + m.group(1).rfind("/") + 1
        kinds[a:cut] = ["link-target"] * (cut - a)
        if bar < 0:
            kinds[cut:b] = ["link"] * (b - cut)
    for m in re.finditer(r"\]\(([^)]*)\)", body):
        a, b = m.span(1)
        kinds[a:b] = ["link-target"] * (b - a)
    best = None
    for m in pattern.finditer(body):
        a, b = m.span()
        if a and word_char(body[a - 1]) and word_char(ident[0]):
            kind = "word-part"
        else:
            kind = max(set(kinds[a:b]), key=rank.get)
        if best is None or rank[kind] > rank[best]:
            best = kind
    sys.stdout.buffer.write(((best or "text") + "\t" + line[:100] + "\n").encode("utf-8"))' "$ident"); then
            fail closure "UTF-8 excerpt conversion failed for $t"
            echo "RESULT: FAIL ($FAILS fail, $REVIEWS review)"
            exit 1
        fi
        hard=""; soft=""
        while IFS=$'\t' read -r kind excerpt; do
            case "$kind" in
                text|link) hard="$hard[$kind] $excerpt " ;;
                *)         soft="$soft[$kind] $excerpt " ;;
            esac
        done <<< "$h"
        [ -n "$hard" ] && HITS="$HITS$t -> $hard; "
        [ -n "$soft" ] && SOFT="$SOFT$t -> $soft; "
    done
    [ -n "$SOFT" ] && SOFT=" not counted (hidden link target or mid-word): $SOFT"
    if [ -n "$HITS" ]; then
        review closure "ident '$ident' has unchecked matches: $HITS$SOFT"
    elif [ -n "$SOFT" ]; then
        pass closure "ident '$ident': no unchecked [ ] text or link match in ${#CLOSURE_TARGETS[@]} planning file(s);$SOFT"
    else
        pass closure "ident '$ident': no unchecked [ ] match in ${#CLOSURE_TARGETS[@]} planning file(s)"
    fi
done
[ "${#IDENTS[@]}" -eq 0 ] && pass closure "no idents supplied (nothing completed to grep)"

# --- backfill coverage -------------------------------------------------------
# Both directions compare COMPLETE resolved paths. A substring test accepts a
# truncated --touched value ("docs/Plan" for "docs/Plan - draft.md") against the
# full row, and nothing downstream notices: every content check silently skips
# a path that is not a file.
canon() {
    local p
    p="$(norm_path "$1")"
    p="$(realpath -m -- "$p" 2>/dev/null || printf '%s\n' "$p")"
    [ "$p" = / ] || p="${p%/}"
    printf '%s\n' "${p,,}"
}
# One key set per side. Resolved paths start with "/", so the two prefixed
# spellings cannot collide with them: "name:" is a bare wikilink (resolved by
# note name, as the vault does) and "alt:" the short home-relative suffix a
# human-written row may use for a path outside the vault.
declare -A ROW_KEY=() DEL_KEY=() TOUCHED_KEY=()
LOGGED=(); LOGGED_KEYS=()
record_row() {   # <section C|U|D> <display path> <wikilink 0|1> <candidate path>...
    local sec="$1" show="$2" wiki="$3" cand key keys=""
    shift 3
    for cand in "$@"; do
        key="$(canon "$cand")"
        keys="$keys$key"$'\n'
        [ "$sec" = D ] && DEL_KEY[$key]=1
        cand="${cand#./}"; cand="${cand,,}"
        case "$cand" in
            /*|"~/"*) ;;
            */*) keys="${keys}alt:$cand"$'\n' ;;
            *)   [ "$wiki" = 1 ] && keys="${keys}name:${cand%.md}"$'\n' ;;
        esac
    done
    while IFS= read -r key; do
        [ -n "$key" ] && ROW_KEY[$key]=1
    done <<< "$keys"
    # Reverse coverage speaks only for rows that could have been linted: a
    # Files Deleted row names a file that no longer exists.
    if [ "$sec" != D ]; then LOGGED+=("$show"); LOGGED_KEYS+=("$keys"); fi
}
# Parse explicit backtick paths atomically. For unquoted paths prefer the
# longest existing prefix, so a filename containing " - " is not truncated.
while IFS= read -r row; do
    sec="${row:0:1}"; row="${row:1}"
    row="${row#"${row%%[![:space:]]*}"}"
    case "$row" in '- '*) value="${row#- }" ;; *) continue ;; esac
    case "$value" in ''|[Nn][Oo][Nn][Ee]) continue ;; esac
    if [[ "$value" == \[\[* ]]; then
        if [[ "$value" == *\]\]* ]]; then
            value="${value#\[\[}"
            value="${value%%\]\]*}"
            value="${value%%|*}"
            value="${value%%#*}"
            case "$value" in
                *.md) record_row "$sec" "$value" 1 "$value" ;;
                *)    record_row "$sec" "$value" 1 "$value" "$value.md" ;;
            esac
        else
            review backfill "unterminated wiki Files path: $row"
        fi
        continue
    fi
    if [[ "$value" == \`* ]]; then
        value="${value#\`}"
        if [[ "$value" == *\`* ]]; then
            record_row "$sec" "${value%%\`*}" 0 "${value%%\`*}"
        else
            review backfill "unterminated quoted Files path: $row"
        fi
        continue
    fi
    candidate="$value"
    while [[ "$candidate" == *' - '* ]] && [ ! -e "$(norm_path "$candidate")" ]; do
        candidate="${candidate% - *}"
    done
    if [ -e "$(norm_path "$candidate")" ]; then
        record_row "$sec" "$candidate" 0 "$candidate"
    else
        # An absent unquoted path gives no way to tell filename from description,
        # so every " - " boundary is a candidate; display the first-separator form.
        cands=("$value"); candidate="$value"
        while [[ "$candidate" == *' - '* ]]; do
            candidate="${candidate% - *}"
            cands+=("$candidate")
        done
        record_row "$sec" "${value%% - *}" 0 "${cands[@]}"
    fi
done < <(printf '%s\n' "$BLOCK" | awk '
    /^### Files Created/{s="C";next} /^### Files Updated/{s="U";next}
    /^### Files Deleted/{s="D";next} /^### /{s=""} s!=""{print s $0}')

# Home paths keep a short alternate suffix for human-written Files rows. Other
# absolute paths stay absolute: reconstructing a three-component suffix turns a
# root-level path such as /tmp/file into the nonexistent //tmp/file.
MISSING=""
ABSENT=""
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
        "$HOME"/*)  needle="~/${t#"$HOME"/}"; alt="alt:${suffix,,}" ;;
        *)          needle="$t"; alt="" ;;
    esac
    key="$(canon "$t")"
    name="${t##*/}"; name="name:${name%.md}"; name="${name,,}"
    TOUCHED_KEY[$key]=1; TOUCHED_KEY[$name]=1
    [ -n "$alt" ] && TOUCHED_KEY[$alt]=1
    if [ -z "${ROW_KEY[$key]:-}" ] && [ -z "${ROW_KEY[$name]:-}" ] \
        && { [ -z "$alt" ] || [ -z "${ROW_KEY[$alt]:-}" ]; }; then
        MISSING="$MISSING$needle; "
    fi
    # A target that is not on disk was never linted or separator-scanned. Only a
    # Files Deleted row or an explicit --nonlocal classification explains that.
    if [ ! -e "$t" ] && [ ! -L "$t" ] && ! is_nonlocal "$t" && [ -z "${DEL_KEY[$key]:-}" ]; then
        ABSENT="$ABSENT$needle; "
    fi
done
if [ -n "$ABSENT" ]; then
    fail touched "path(s) do not exist and are not recorded under Files Deleted (truncated or mistyped?): $ABSENT"
fi
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
# An off-host form names a file this machine cannot read, so reporting it as
# "not passed to --touched" is a REVIEW no rerun can clear.
OFFHOST_RE='^[A-Za-z0-9._-]+:/|(^|[[:space:]])[A-Za-z]:\\'
UNCOVERED=""
OFFHOST=0
for i in "${!LOGGED[@]}"; do
    lp="${LOGGED[$i]}"
    case "$lp" in [Nn][Oo][Nn][Ee]) continue ;; esac
    lp_abs="$(norm_path "$lp")"
    [ "$lp_abs" = "$LOG" ] && continue   # the log may list itself; it is checked separately
    if [ ! -e "$lp_abs" ] && [[ "$lp" =~ $OFFHOST_RE ]]; then
        OFFHOST=$((OFFHOST + 1))
        continue
    fi
    hit=""
    while IFS= read -r key; do
        [ -n "$key" ] && [ -n "${TOUCHED_KEY[$key]:-}" ] && hit=1
    done <<< "${LOGGED_KEYS[$i]}"
    [ -z "$hit" ] && UNCOVERED="$UNCOVERED$lp; "
done
if [ -n "$UNCOVERED" ]; then
    review backfill "Files lists name path(s) not passed to --touched, so no lint/separator check ran on them: $UNCOVERED"
else
    NOTE=""
    [ "$OFFHOST" -gt 0 ] && NOTE=" ($OFFHOST off-host path form(s) not compared)"
    pass backfill "--touched covers every path the Session $N Files lists name$NOTE"
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
