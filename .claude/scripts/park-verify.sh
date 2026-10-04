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
#   --touched  each file the session+park created or edited (repeatable). A
#              value that is not a path on disk but is a Files row's own text
#              ("[[Note]]", or an existing "path <sep> description") is resolved
#              the way that row is
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
#               [link-target] / [word-part] but do not raise REVIEW. Mid-word
#               means the preceding character is the same kind as the ident's
#               first (letter after letter, digit after digit); a digit ident
#               after letters, or the reverse, counts as [text]
#   touched     each --touched path exists, unless a Files Deleted row accounts
#               for it, --nonlocal classifies it, or it is an off-host form
#               ("host:/path", "C:\path", a URL) that names nothing local
#   backfill    each touched path matches a Files Created / Files Updated /
#               Files Deleted row by complete resolved path. Case-sensitive:
#               a row spelled in another case matches only when one row path
#               and one touched path fold together and are not two files on
#               disk. Row forms and the bare-wikilink rule are documented at
#               the coverage helper. Reverse coverage reports rows no --touched
#               path matched; off-host forms and Files Deleted rows whose path
#               is gone name nothing local to lint and are counted, not
#               compared. REVIEW also for a row that cannot be tied to one
#               file: a bare [[Note]] shared by several vault files, or an
#               unquoted row matched only through a truncated prefix
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

# --- Files-list coverage: computed here, reported under "backfill" below ------
# Row parsing, path identity and both coverage directions run in one python3
# process, so every path on either side is canonicalised by the same mechanism
# (os.path.realpath: no dependence on GNU `realpath -m`, missing paths allowed)
# and compared as a COMPLETE, case-sensitive resolved path. A substring test
# accepts a truncated --touched value ("docs/Plan" for "docs/Plan - draft.md")
# against the full row, and nothing downstream notices: every content check
# silently skips a path that is not a file.
#
# It runs before the content checks because a "[[Note]]" string passed as
# --touched is replaced by the file it resolves to, so that file is linted.
#
# Row forms (bullets "-", "*", "+"; a trailing CR is dropped):
#   `path` ...          exact; nothing outside the backticks is read
#   [[folder/Note]]     resolved by path (".md" optional)
#   [[Note]]            the ONE vault file of that name (".git" is the only
#                       directory not searched; directory symlinks are
#                       followed, each real directory once). Several -> REVIEW,
#                       covers nothing. None, or any bare link under Files
#                       Deleted -> the deleted-note case: covers the one absent
#                       in-vault --touched path with that basename, and never a
#                       surviving note of the same name
#   [label](path "t")   the link destination; an optional title and <angle>
#                       brackets are not part of it
#   **path** ...        the emphasised text
#   path <sep> text     <sep> is " - ", an em or en dash with spaces, ": " or
#                       " (". The longest left side that is an existing regular
#                       file wins, so a filename containing a separator is not
#                       truncated and a directory that merely prefixes the
#                       filename is not taken for it; nor is an extensionless
#                       file that prefixes a longer file-shaped name.
# Known gap: an unquoted row whose file is absent cannot be split mechanically.
# Every " - " boundary, plus any other boundary whose left side exists or ends
# in a file extension, is then a candidate, so a truncated --touched value equal
# to one of those candidates still matches. One shape is recognisable and
# raises REVIEW: the next " - " segment completes a file-shaped name and more
# text follows ("docs/Plan" against "docs/Plan - draft.md - text"). Without a
# trailing description, or when the real name has no extension, the truncated
# value passes. Two different --touched paths that only such a row accounts for
# also raise REVIEW and neither is covered. Backticks close the gap.
IFS= read -r -d '' COVERAGE_PY <<'PY' || true
import os
import re
import sys
from urllib.parse import unquote

vault, log, number = sys.argv[1:4]
home = os.environ.get("HOME", "")
touched_args, nonlocal_args = [], set()
rest = sys.argv[4:]
for flag, value in zip(rest[0::2], rest[1::2]):
    if flag == "--touched":
        touched_args.append(value)
    else:
        nonlocal_args.add(value)
block = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")

OFFHOST = re.compile(r"^[A-Za-z0-9._-]+:/|(^|\s)[A-Za-z]:\\")
EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,10}$")
MDTITLE = re.compile(r"""^(.*?)\s+("[^"]*"|'[^']*'|\([^()]*\))$""")
OTHER_SEPARATORS = (" \u2014 ", " \u2013 ", ": ", " (")
root = os.path.realpath(vault)
out = []
row_text = {}   # canonical "path <sep> description" spelling -> the row's file


def norm(path):
    """Mirror of the shell norm_path: absolute, ~-prefixed or vault-relative."""
    if path.startswith("./"):
        path = path[2:]
    if path.startswith("/"):
        return path
    if path.startswith("~/"):
        return home + "/" + path[2:]
    return vault + "/" + path


def canon(path):
    return os.path.realpath(norm(path))


def is_file(path):
    return os.path.isfile(norm(path))


def on_disk(path):
    return os.path.lexists(norm(path))


def stem(path):
    name = os.path.basename(path)
    return name[:-3] if name.endswith(".md") else name


def in_vault(key):
    return key.startswith(root + "/")


def show_touched(path):
    if path.startswith(vault + "/"):
        return path[len(vault) + 1:]
    if home and path.startswith(home + "/"):
        return "~/" + path[len(home) + 1:]
    return path


def truncation(candidate, candidates):
    """True when `candidate` may be a cut-off form of a longer, file-shaped one."""
    return not EXTENSION.search(candidate) and any(
        len(c) > len(candidate) and EXTENSION.search(c) for c in candidates)


def unquoted(value):
    """Candidate paths for an unquoted row -> (candidates, display, resolved)."""
    legacy, other = [], []
    for index in range(1, len(value)):
        if value.startswith(" - ", index):
            legacy.append(value[:index])
        elif value.startswith(OTHER_SEPARATORS, index):
            other.append(value[:index])
    ordered = sorted(dict.fromkeys([value] + legacy + other), key=len, reverse=True)
    for candidate in ordered:
        if is_file(candidate):
            if truncation(candidate, ordered):
                break   # an extensionless file that prefixes a file-shaped name
            # The row's text cut at a later boundary (path plus some or all of
            # the description) is how a caller that splits rows differently
            # names this file; a cut that is itself file-shaped is not assumed
            # to be one. Live consumer: parse_file_lines in
            # codex/skills/park/scripts/park-review.py splits only on " - " and
            # passes the whole row text as --touched. Not dead code.
            for longer in ordered:
                if len(longer) > len(candidate) and not EXTENSION.search(longer):
                    row_text.setdefault(canon(longer), candidate)
            return [candidate], candidate, True
    if on_disk(value):
        return [value], value, True
    # Nothing here is a file. The old first-separator rule cannot tell filename
    # from description, so keep every " - " boundary; another separator counts
    # only where its left side exists or ends in a file extension.
    kept = [value] + legacy + [c for c in other if on_disk(c) or EXTENSION.search(c)]
    kept = list(dict.fromkeys(kept))
    return kept, min(kept, key=len), False


def markdown_link(value):
    """Destinations a `[label](destination "title")` row may name, best first."""
    opening = re.match(r"\[[^\]]*\]\(", value)
    if not opening:
        return []
    depth, quote, end = 1, "", -1
    for index in range(opening.end(), len(value)):
        char = value[index]
        if quote:
            quote = "" if char == quote else quote
        elif char in "\"'" and value[index - 1].isspace():
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if not depth:
                end = index
                break
    if end < 0:
        return []
    body = value[opening.end():end].strip()
    titled = MDTITLE.match(body)
    if body.startswith("<") and ">" in body:
        destinations = [body[1:body.index(">")]]
    elif titled:
        # The whole body is tried first on disk: a destination may itself end
        # in "(...)". Absent, the part before the title is the destination.
        destinations = [titled.group(1).strip()]
        if is_file(body):
            return [body]
    else:
        destinations = [body]
    destinations = [d for d in dict.fromkeys(destinations + [unquote(d) for d in destinations]) if d]
    hit = next((d for d in destinations if is_file(d)), None)
    return [hit] if hit else destinations


def wiki_target(text):
    return text.split("|")[0].split("#")[0].strip()


def wiki_paths(target):
    options = [target] if target.endswith(".md") else [target + ".md", target]
    hit = next((o for o in options if is_file(o)), None)
    return [hit] if hit else options


rows, touched, bare_names = [], [], set()


def add_row(section, raw, show, candidates, multi=False, bare=None):
    rows.append({"sec": section, "raw": raw, "show": show, "cands": candidates,
                 "keys": [canon(c) for c in candidates], "multi": multi,
                 "bare": bare, "hits": None, "skip": False})


section = ""
for line in block.split("\n"):
    line = line.rstrip("\r")
    if line.startswith("### Files Created"):
        section = "C"
        continue
    if line.startswith("### Files Updated"):
        section = "U"
        continue
    if line.startswith("### Files Deleted"):
        section = "D"
        continue
    if line.startswith("### "):
        section = ""
    if not section:
        continue
    row = line.strip()
    if row[:2] not in ("- ", "* ", "+ "):
        continue
    value = row[2:].strip()
    if not value or value.lower() == "none":
        continue
    if value.startswith("[["):
        end = value.find("]]")
        if end < 0:
            out.append("REVIEW backfill: unterminated wiki Files path: " + row)
            continue
        target = wiki_target(value[2:end])
        if not target:
            out.append("REVIEW backfill: wiki Files row names no file; write the vault-relative path instead: " + row)
        elif "/" in target:
            add_row(section, row, target, wiki_paths(target))
        else:
            name = target[:-3] if target.endswith(".md") else target
            bare_names.add(name)
            add_row(section, row, target, [], bare=name)
        continue
    if value.startswith("`"):
        end = value.find("`", 1)
        if end < 0:
            out.append("REVIEW backfill: unterminated quoted Files path: " + row)
        else:
            add_row(section, row, value[1:end], [value[1:end]])
        continue
    candidates, show, resolved = unquoted(value)
    if not resolved:
        link = markdown_link(value)
        closing = value.find("**", 2) if value.startswith("**") else -1
        if link:
            candidates, show, resolved = link, link[0], True
        elif closing > 2:
            candidates, show, resolved = unquoted(value[2:closing] + value[closing + 2:])
    if show.lower() == "none":
        continue
    add_row(section, row, show, candidates, multi=not resolved and len(candidates) > 1)

for index, path in enumerate(touched_args):
    entry = {"path": path, "show": show_touched(path), "keys": [canon(path)],
             "exists": os.path.lexists(path), "bare": None, "ambiguous": None,
             "skip": path == log}
    touched.append(entry)
    relative = entry["keys"][0][len(root) + 1:] if in_vault(entry["keys"][0]) else ""
    link = re.fullmatch(r"\[\[([^\]]+)\]\]", relative)
    if entry["exists"]:
        continue
    # Not a path on disk but a row's own text, path plus description: it
    # stands for the file that row resolves to.
    if entry["keys"][0] in row_text and path not in nonlocal_args:
        target = row_text[entry["keys"][0]]
        entry["keys"], entry["exists"] = [canon(target)], True
        out.append("T\t%d\t%s" % (index, norm(target)))
        continue
    if not link:
        continue
    # A wikilink string is what a Files row holds, not a path; resolve it the
    # way the row is resolved.
    target = wiki_target(link.group(1))
    if "/" in target:
        options = wiki_paths(target)
        entry["keys"] = [canon(o) for o in options]
        entry["exists"] = len(options) == 1 and is_file(options[0])
        if entry["exists"] and path not in nonlocal_args:
            out.append("T\t%d\t%s" % (index, norm(options[0])))
    elif target:
        entry["bare"] = target[:-3] if target.endswith(".md") else target
        entry["keys"] = []
        bare_names.add(entry["bare"])

# One walk of the vault, and only when a bare wikilink has to be resolved.
named, folded, within = {}, {}, {}   # within: real path -> its spelling inside the vault
if bare_names:
    wanted = {name.casefold() for name in bare_names}
    # Directory symlinks are followed: a note beneath one is in the vault as
    # far as a wikilink is concerned. Each real directory is entered once,
    # which both ends a symlink cycle and stops one directory reached by two
    # names from counting as two notes.
    entered = {root}
    for directory, subdirs, files in os.walk(root, followlinks=True):
        keep = []
        for name in subdirs:
            real = os.path.realpath(os.path.join(directory, name))
            if name != ".git" and real not in entered:
                entered.add(real)
                keep.append(name)
        subdirs[:] = keep
        for name in files:
            key = name[:-3] if name.endswith(".md") else name
            if key.casefold() in wanted:
                spelled = os.path.join(directory, name)
                real = os.path.realpath(spelled)
                within.setdefault(real, spelled[len(root) + 1:])
                named.setdefault(key, set()).add(real)
                folded.setdefault(key.casefold(), set()).add(real)


def vault_files(name):
    return sorted(named.get(name) or folded.get(name.casefold()) or ())


def vault_relative(real):
    return within.get(real) or (real[len(root) + 1:] if in_vault(real) else real)


# A bare wikilink under Files Deleted names a note that is gone. Notes of that
# name still in the vault are other notes: the row is not resolved to them, and
# a "[[Note]]" --touched value that repeats the row is not either.
deleted_names = {row["bare"] for row in rows if row["sec"] == "D" and row["bare"] is not None}
for row in rows:
    if row["bare"] is None or row["sec"] == "D":
        continue
    hits = vault_files(row["bare"])
    if len(hits) == 1:
        row["keys"], row["show"], row["hits"] = hits, vault_relative(hits[0]), hits
        row["bare"] = None
    elif hits:
        row["skip"] = True
        out.append("REVIEW backfill: ambiguous wikilink Files row '%s': %d vault files are named '%s' (%s); write the full vault-relative path instead"
                   % (row["raw"], len(hits), row["bare"], "; ".join(vault_relative(h) for h in hits[:4])))
ambiguous_touched = []
for index, entry in enumerate(touched):
    if entry["bare"] is None or entry["bare"] in deleted_names:
        continue
    hits = vault_files(entry["bare"])
    if len(hits) == 1:
        entry["keys"], entry["exists"], entry["bare"] = hits, True, None
        if entry["path"] not in nonlocal_args:
            out.append("T\t%d\t%s" % (index, norm(vault_relative(hits[0]))))
    elif hits:
        entry["ambiguous"] = hits
        ambiguous_touched.append("%s (%s)" % (entry["show"], "; ".join(vault_relative(h) for h in hits[:4])))

# --- matching ----------------------------------------------------------------
covers = {index: set() for index in range(len(touched))}   # touched -> rows
covered = {index: set() for index in range(len(rows))}     # row -> touched
via = {}


def link_up(row_index, touched_index, candidate=None):
    covers[touched_index].add(row_index)
    covered[row_index].add(touched_index)
    if candidate is not None:
        via.setdefault((row_index, touched_index), candidate)


live = [i for i, entry in enumerate(touched) if not entry["skip"] and not entry["ambiguous"]]
by_key = {}
for index in live:
    for key in touched[index]["keys"]:
        by_key.setdefault(key, []).append(index)

# 1. The same resolved path.
for row_index, row in enumerate(rows):
    if row["skip"]:
        continue
    for position, key in enumerate(row["keys"]):
        for index in by_key.get(key, ()):
            link_up(row_index, index, row["cands"][position] if row["cands"] else None)


def same(a, b):
    return a == b


def same_folded(a, b):
    return a.casefold() == b.casefold()


# 2. A bare wikilink naming no vault file: the deleted note. It stands for one
#    absent path inside the vault with that basename, never for several.
for row_index, row in enumerate(rows):
    if row["skip"] or row["bare"] is None:
        continue
    for equal in (same, same_folded):
        hits = [i for i in live if (
            touched[i]["bare"] is not None and equal(touched[i]["bare"], row["bare"])
        ) or (
            touched[i]["bare"] is None and not touched[i]["exists"]
            and any(in_vault(k) and equal(stem(k), row["bare"]) for k in touched[i]["keys"])
        )]
        if hits:
            break
    if len(hits) == 1:
        link_up(row_index, hits[0])
    elif hits:
        row["skip"] = True
        out.append("REVIEW backfill: ambiguous wikilink Files row '%s': %d --touched paths share that name (%s); write the full vault-relative path instead"
                   % (row["raw"], len(hits), "; ".join(touched[i]["show"] for i in hits[:4])))
for index in live:
    entry = touched[index]
    if entry["bare"] is None or covers[index]:
        continue
    hits = [r for r, row in enumerate(rows) if not row["skip"] and row["bare"] is None
            and not any(on_disk(c) for c in row["cands"])
            and any(in_vault(k) and stem(k) == entry["bare"] for k in row["keys"])]
    if len(hits) == 1:
        link_up(hits[0], index)

# 3. A home path written without "~/": the row is a relative path of three or
#    more components that names nothing in the vault and is the tail of exactly
#    one --touched path under $HOME outside the vault.
#    A path some other row already covers is not claimed again: the longest
#    tail is tried first, and the shorter row stays uncovered.
tails = []
for row_index, row in enumerate(rows):
    if row["skip"]:
        continue
    for candidate in row["cands"]:
        tail = candidate[2:] if candidate.startswith("./") else candidate
        if tail.startswith(("/", "~/")) or tail.count("/") < 2 or on_disk(candidate):
            continue
        tails.append((-len(tail), row_index, tail))
for _, row_index, tail in sorted(tails):
    hits = [i for i in live if home and touched[i]["path"].startswith(home + "/")
            and not any(in_vault(k) for k in touched[i]["keys"])
            and touched[i]["path"].endswith("/" + tail)]
    if len(hits) == 1 and not covers[hits[0]] - {row_index}:
        link_up(row_index, hits[0])

# 4. Case. Keys are case-sensitive, so two files differing only in case never
#    cover each other. A row spelled in a different case from its file still
#    matches when the pairing is unambiguous: exactly one row path and exactly
#    one --touched path fold to the same string, and they are not two distinct
#    files on disk.
row_fold, touched_fold = {}, {}
for row in rows:
    if not row["skip"]:
        for key in row["keys"]:
            row_fold.setdefault(key.casefold(), set()).add(key)
for index in live:
    for key in touched[index]["keys"]:
        touched_fold.setdefault(key.casefold(), set()).add(key)


def distinct_files(a, b):
    if not (os.path.lexists(a) and os.path.lexists(b)):
        return False
    try:
        return not os.path.samefile(a, b)
    except OSError:
        return True


for index in live:
    if covers[index]:
        continue
    for key in touched[index]["keys"]:
        row_keys = row_fold.get(key.casefold(), set())
        if len(row_keys) != 1 or len(touched_fold[key.casefold()]) != 1:
            continue
        row_key = next(iter(row_keys))
        if row_key == key or distinct_files(row_key, key):
            continue
        for row_index, row in enumerate(rows):
            if not row["skip"] and row_key in row["keys"]:
                link_up(row_index, index)

# An unsplittable row names ONE file, whichever of its candidates that is. When
# two different --touched paths rely on it alone, at least one of them is not
# that file, and nothing here can say which: neither is covered. A path that
# another row also covers does not rely on this one (two rows for one file, one
# of them carrying a parenthetical, is an ordinary log shape).
for row_index, row in enumerate(rows):
    if row["skip"] or not row["multi"]:
        continue
    sole = sorted(i for i in covered[row_index] if covers[i] == {row_index})
    distinct = {frozenset(touched[i]["keys"]) for i in sole}
    if len(distinct) < 2:
        continue
    out.append("REVIEW backfill: Files row '%s' matched %d different --touched paths (%s) and names only one file; write the row's path in backticks; not counted for any of them"
               % (row["raw"], len(distinct), "; ".join(touched[i]["show"] for i in sole)))
    for index in sole:
        covers[index].discard(row_index)
        covered[row_index].discard(index)
        via.pop((row_index, index), None)
    row["skip"] = True

# An unsplittable row matched through a candidate that looks like a truncation.
for (row_index, index), candidate in sorted(via.items()):
    row = rows[row_index]
    # Flagged only in the one shape that is recognisable: the next " - " segment
    # completes a file-shaped name and more text follows it ("docs/Plan" in
    # "docs/Plan - draft.md - text"). A directory row whose description merely
    # ends in something extension-like is left alone. An existing regular file
    # was at least linted as itself.
    if not row["multi"] or is_file(candidate) or EXTENSION.search(candidate):
        continue
    full = max(row["cands"], key=len)
    longer = [c for c in row["cands"] if c.startswith(candidate + " - ")
              and " - " not in c[len(candidate) + 3:] and full.startswith(c + " - ")
              and EXTENSION.search(c)]
    if longer:
        out.append("REVIEW backfill: Files row '%s' matched --touched '%s' only through the prefix '%s', but the row may name '%s'; write the row's path in backticks"
                   % (row["raw"], touched[index]["show"], candidate, min(longer, key=len)))

# --- report --------------------------------------------------------------------
if ambiguous_touched:
    out.append("FAIL touched: wikilink passed to --touched names several vault files; pass the full path instead: "
               + "; ".join(ambiguous_touched) + "; ")
absent = missing = ""
for index, entry in enumerate(touched):
    if entry["ambiguous"]:
        missing += entry["show"] + "; "
    if entry["skip"] or entry["ambiguous"]:
        continue
    if not covers[index]:
        missing += entry["show"] + "; "
    # A target that is not on disk was never linted or separator-scanned. Only a
    # Files Deleted row, an explicit --nonlocal classification, or an off-host
    # form (which names nothing on this machine) explains that.
    if (not entry["exists"] and entry["path"] not in nonlocal_args
            and not OFFHOST.search(entry["show"])
            and not any(rows[r]["sec"] == "D" for r in covers[index])):
        absent += entry["show"] + "; "
if absent:
    out.append("FAIL touched: path(s) do not exist and are not recorded under Files Deleted (truncated or mistyped? a path on another host or a glob needs --nonlocal): " + absent)
if missing:
    out.append("FAIL backfill: touched but absent from Session %s Files lists (a row must begin with the complete path; backtick a path the row does not end at): %s"
               % (number, missing))
else:
    # Scoped to the ARGUMENTS, not to the session. "all N touched files recorded"
    # read as a coverage statement about the run and was written up as one, off a
    # --touched list narrower than the log's own Files list. The check can only
    # ever speak for what it was handed; the reverse-coverage REVIEW below is what
    # speaks for the rest.
    out.append("PASS backfill: all %d path(s) PASSED TO --touched are recorded in Files lists (says nothing about paths not passed)"
               % len(touched))

# Reverse coverage: does the log list files --touched never saw? Two kinds of
# row name nothing local to lint and are counted, not compared: an off-host form
# ("host:/path", "C:\path"), and a Files Deleted row whose path is gone. A
# Deleted row whose path is still on disk is compared like any other.
log_key = os.path.realpath(log)
uncovered, off_host, deleted_absent = "", 0, 0
for row_index, row in enumerate(rows):
    if row["skip"] or norm(row["show"]) == log or log_key in row["keys"]:
        continue   # the log may list itself; it is checked separately
    # A regular file on disk is present whatever the description looks like;
    # only a directory or other non-file prefix of a file-shaped name is not
    # taken as the row's own path.
    present = bool(row["hits"]) or any(
        on_disk(c) and (is_file(c) or not (row["multi"] and truncation(c, row["cands"])))
        for c in row["cands"])
    if not present and OFFHOST.search(row["show"]):
        off_host += 1
    elif not present and row["sec"] == "D":
        deleted_absent += 1
    elif not covered[row_index]:
        uncovered += row["show"] + "; "
if uncovered:
    out.append("REVIEW backfill: Files lists name path(s) not passed to --touched, so no lint/separator check ran on them: " + uncovered)
else:
    notes = []
    if off_host:
        notes.append("%d off-host path form(s) not compared" % off_host)
    if deleted_absent:
        notes.append("%d absent Files Deleted row(s) not compared" % deleted_absent)
    out.append("PASS backfill: --touched covers every path the Session %s Files lists name%s"
               % (number, " (" + "; ".join(notes) + ")" if notes else ""))

for line in out:
    if not line.startswith("T\t"):
        line = "O\t" + line
    sys.stdout.buffer.write((line + "\n").encode("utf-8", "surrogateescape"))
PY
COVERAGE_ARGS=()
for t in "${TOUCHED[@]:-}"; do [ -n "$t" ] && COVERAGE_ARGS+=(--touched "$t"); done
for t in "${NONLOCAL[@]:-}"; do [ -n "$t" ] && COVERAGE_ARGS+=(--nonlocal "$t"); done
# With no --touched path and no Files row there is nothing to compare, and the
# verdict does not depend on python3. Otherwise a missing or broken helper must
# not read as "nothing to report".
FILE_ROWS=$(awk '
    /^### Files (Created|Updated|Deleted)/{s=1;next} /^### /{s=0} !s{next}
    {sub(/\r$/,""); sub(/^[[:space:]]+/,""); sub(/[[:space:]]+$/,"")}
    /^[-*+] / && tolower(substr($0,3)) !~ /^[[:space:]]*none$/ {n++}
    END{print n+0}' <<< "$BLOCK")
if [ "${#COVERAGE_ARGS[@]}" -eq 0 ] && [ "$FILE_ROWS" -eq 0 ]; then
    COVERAGE=$'O\tPASS backfill: all 0 path(s) PASSED TO --touched are recorded in Files lists (says nothing about paths not passed)\n'"O"$'\t'"PASS backfill: --touched covers every path the Session $N Files lists name"
elif ! COVERAGE=$(python3 -c "$COVERAGE_PY" "$VAULT" "$LOG" "$N" ${COVERAGE_ARGS[@]+"${COVERAGE_ARGS[@]}"} <<< "$BLOCK"); then
    fail backfill "Files-list coverage helper failed (python3 required); nothing was compared"
    echo "RESULT: FAIL ($FAILS fail, $REVIEWS review)"
    exit 1
fi
COVERAGE_LINES=()
while IFS= read -r line; do
    case "$line" in
        T$'\t'*) line="${line#T$'\t'}"; TOUCHED[${line%%$'\t'*}]="${line#*$'\t'}" ;;
        O$'\t'*) COVERAGE_LINES+=("${line#O$'\t'}") ;;
    esac
done <<< "$COVERAGE"
if [ "${#TOUCHED[@]}" -gt 0 ]; then
    mapfile -t TOUCHED < <(printf '%s\n' "${TOUCHED[@]}" | awk '!seen[$0]++')
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
        # Mid-word only when the match continues a run of its own kind: a
        # letter after a letter, a digit after a digit. A digit ident after
        # letters ("INV" + "20417") is a complete token and stays countable.
        if (a and word_char(body[a - 1]) and word_char(ident[0])
                and body[a - 1].isdigit() == ident[0].isdigit()):
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
# Computed by the coverage helper above; printed here to keep the report order.
for line in ${COVERAGE_LINES[@]+"${COVERAGE_LINES[@]}"}; do
    echo "$line"
    case "$line" in
        FAIL\ *)   FAILS=$((FAILS+1)) ;;
        REVIEW\ *) REVIEWS=$((REVIEWS+1)) ;;
    esac
done

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
