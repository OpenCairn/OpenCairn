#!/usr/bin/env bash
# Locked, atomic edit of a target file (planning docs or generated exports).
#
# The Edit tool does a lockless read-modify-write, so two concurrent /park or
# /goodnight runs silently clobber each other's edits to shared planning files.
# This wrapper serialises writers through the file's canonical lock and writes
# atomically, converting silent data loss into one of two safe outcomes:
#   - disjoint edits both land (each old_string still present after the other's write)
#   - conflicting edits fail loudly (the loser's old_string no longer matches)
#
# Usage:
#   locked-edit.sh <file> --replace       (stdin: OLD <SEP> NEW; OLD must match exactly once)
#   locked-edit.sh <file> --replace-all   (stdin: OLD <SEP> NEW; replaces every occurrence, >=1)
#   locked-edit.sh <file> --replace-many  (stdin: JSON array of {"old","new"} pairs; each OLD must match exactly once)
#   locked-edit.sh <file> --append        (stdin appended verbatim at end of file)
#   locked-edit.sh <file> --show-section '<heading line>'
#                                            (read-only: section printed to stdout, its SHA-256 to stderr)
#   locked-edit.sh <file> --delete-section '<heading line>' <expected-section-sha256> [--no-replacement]
#                                            (stdin: the replacement, or nothing with --no-replacement;
#                                             the section printed to stdout)
#   locked-edit.sh <file> --replace-whole <expected-sha256|MISSING>
#                                            (stdin: complete replacement file)
#   locked-edit.sh <source> --move <destination> <expected-source-sha256>
#
# For --replace/--replace-all, stdin is the old string, then a separator LINE
# equal to exactly:
#   ========OPENCAIRN-LOCKED-EDIT-SEP========
# then the new string. (A literal separator line must not appear inside content;
# it won't in normal vault prose.) Matching is LITERAL, never regex.
#
# --replace-many applies several exactly-once replacements under ONE lock
# acquisition and ONE atomic write. stdin is a JSON array of objects, each with
# exactly the string keys "old" and "new":
#   [{"old": "- [ ] first", "new": "- [x] first"}, {"old": "two\nlines", "new": ""}]
# JSON carries newlines and arbitrary characters (including the separator line)
# and nothing is trimmed: both strings are taken exactly as decoded. Every OLD
# is matched literally against the file as it stood before the call - pairs do
# not see each other's output - must be non-empty, must match exactly once, and
# must not overlap another pair's match. Any failure leaves the file untouched,
# names each failing pair by its 1-based position, and exits with the first
# failing pair's code.
#
# --show-section and --delete-section address one Markdown section without the
# caller retyping it. The argument is the complete heading line, markers
# included (for example '## Monday'); it is compared literally against whole
# lines, must start at column 0, and must match exactly one heading outside
# fenced code blocks. The section runs from that line to just before the next
# heading of the same or a higher level (the same number of '#' or fewer), or
# to end of file, trailing blank lines included; deeper sub-headings and fenced
# lines that merely look like headings stay inside it. Any line that starts
# with three or more backticks or tildes opens a fence; if a fence is still
# open at end of file the section's end cannot be known, so both modes exit 2
# and nothing is written.
#
# --show-section is the read: under the lock, and without writing anything, it
# prints the section to stdout and "Section sha256: <hash>" to stderr. The hash
# is the SHA-256 of exactly the bytes printed.
#
# --delete-section is the compare-and-swap write. It takes the hash of the
# section the caller read and, under the lock, recomputes it; if the section
# changed in any way since that read it writes nothing and exits 2 (read the
# section again and decide again).
#   - stdin non-empty: the section is replaced by stdin verbatim (newline-
#     terminated if it was not), and the section's trailing blank lines are kept
#     as the seam before the next heading. This collapses a section to a
#     summary in one call; the replacement supplies its own heading line.
#   - --no-replacement, with stdin empty or whitespace-only: the section is
#     deleted together with its trailing blank lines.
# The choice must be explicit: empty stdin without --no-replacement, or a
# replacement on stdin with it, is a usage error (exit 1) and writes nothing.
# stdout carries the section as it stood - the same bytes the hash covers, the
# caller's record of what was cut - so this mode alone reports "Locked edit
# applied" on stderr. A terminal on stdin is treated as empty rather than read.
#
# --replace-whole is a compare-and-swap for generated files whose content may
# itself contain the separator line. The caller reads a snapshot, supplies its
# SHA-256 (or MISSING when the target did not exist), and streams the complete
# replacement on stdin. If another writer changed the target after that read,
# the hash no longer matches and the write fails safely with exit 2.
#
# --move is a compare-and-move operation for an existing vault note. Both paths
# must resolve inside VAULT_PATH, the destination must not exist, and the source
# hash must match. It holds both canonical file locks while asking the live
# Obsidian CLI to perform the move, then verifies the resulting paths, content
# hash, and path-qualified links. It never falls back to a raw filesystem move.
# If the note did move but that verification fails (old links remain, or the
# moved content differs), it still exits 1, and with a session id it keeps a
# move receipt marked "complete": false with a "postcheck" reason, so the link
# heals that did land stay individually verifiable.
#
# Exit codes: 0 ok · 1 usage/lock/CLI/result error · 2 no match/stale snapshot ·
#             3 ambiguous (>1 match under --replace/--replace-many, overlapping --replace-many pairs,
#               or a duplicated --show-section/--delete-section heading)
#
# With a harness session id, every successful content-edit operation (--show-section
# is a read and records nothing) writes one JSON
# receipt under $CLAUDE_CONFIG_DIR/.session-state/<id>.locked-edit-receipts/.
# It carries pre/post hashes, exact replace payloads and bounded changed spans;
# --replace-many writes one chained --replace-shaped receipt per pair and
# --delete-section a single one (both tagged "invoked_mode"), so each change is
# reviewable exactly like a single --replace;
# $park uses those receipts to review mechanical locator edits without rereading
# the whole file. Receipt bookkeeping fails open and never reverses a landed edit.
# The stdin and receipt temp files under $TMPDIR are owner-only and are removed
# on every exit, whether or not a session id resolved.
#
# Platform: Linux, macOS, Windows (Git Bash). Locking via lib-lock.sh
# (flock / mkdir fallback); literal string handling via python3.
# Migration recovery compatibility: archive-bundle-v3.

set -euo pipefail

source "$(dirname "$0")/lib-lock.sh"
source "$(dirname "$0")/lib-session.sh"

SEP='========OPENCAIRN-LOCKED-EDIT-SEP========'

if [ $# -lt 2 ]; then
    echo "Usage: $0 <file> --replace|--replace-all|--replace-many|--append|--show-section|--delete-section|--replace-whole|--move [argument]" >&2
    exit 1
fi

TARGET="$1"
MODE="$2"
EXPECTED_SNAPSHOT=""
MOVE_DESTINATION=""
SECTION_HEADING=""
SECTION_NO_REPLACEMENT=0

case "$MODE" in
    --replace|--replace-all|--replace-many|--append) ;;
    --show-section)
        if [ $# -ne 3 ]; then
            echo "--show-section requires the heading line of the section" >&2
            exit 1
        fi
        SECTION_HEADING="$3"
        ;;
    --delete-section)
        if [ $# -lt 4 ] || [ $# -gt 5 ] || { [ $# -eq 5 ] && [ "$5" != "--no-replacement" ]; }; then
            echo "--delete-section requires the heading line of the section and the section's expected SHA-256 (read both with --show-section), then optionally --no-replacement" >&2
            exit 1
        fi
        SECTION_HEADING="$3"
        EXPECTED_SNAPSHOT="$4"
        [ $# -eq 4 ] || SECTION_NO_REPLACEMENT=1
        ;;
    --replace-whole)
        if [ $# -ne 3 ]; then
            echo "--replace-whole requires expected-sha256 or MISSING" >&2
            exit 1
        fi
        EXPECTED_SNAPSHOT="$3"
        ;;
    --move)
        if [ $# -ne 4 ]; then
            echo "$MODE requires destination and expected source SHA-256" >&2
            exit 1
        fi
        MOVE_DESTINATION="$3"
        EXPECTED_SNAPSHOT="$4"
        ;;
    *) echo "Unknown mode: $MODE (expected --replace, --replace-all, --replace-many, --append, --show-section, --delete-section, --replace-whole, or --move)" >&2; exit 1 ;;
esac

if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "locked-edit.sh requires Python 3 (python3 or python)" >&2
    exit 1
fi

if [ "$MODE" = "--move" ]; then
    if [ -z "${VAULT_PATH:-}" ]; then
        echo "--move requires VAULT_PATH" >&2
        exit 1
    fi

    MOVE_META="$(mktemp "${TMPDIR:-/tmp}/locked-edit-move.XXXXXX")"
    MOVE_REFS="$(mktemp "${TMPDIR:-/tmp}/locked-edit-move-refs.XXXXXX")"
    MOVE_SNAPSHOT="$(mktemp "${TMPDIR:-/tmp}/locked-edit-move-snapshot.XXXXXX")"
    MOVE_SOURCE_COPY="$(mktemp "${TMPDIR:-/tmp}/locked-edit-move-source.XXXXXX")"
    _MOVE_LOCK_MODE=""
    _MOVE_LOCK_DIR_1=""
    _MOVE_LOCK_DIR_2=""

    _move_unlock_pair() {
        if [ "${_MOVE_LOCK_MODE:-}" = "flock" ]; then
            exec 8>&- 2>/dev/null || true
            exec 9>&- 2>/dev/null || true
        elif [ "${_MOVE_LOCK_MODE:-}" = "mkdir" ]; then
            [ -z "${_MOVE_LOCK_DIR_2:-}" ] || rmdir "$_MOVE_LOCK_DIR_2" 2>/dev/null || true
            [ -z "${_MOVE_LOCK_DIR_1:-}" ] || rmdir "$_MOVE_LOCK_DIR_1" 2>/dev/null || true
        fi
        _MOVE_LOCK_MODE=""
    }

    _move_cleanup() {
        _move_unlock_pair
        rm -f "$MOVE_META" "$MOVE_REFS" "$MOVE_SNAPSHOT" "$MOVE_SOURCE_COPY"
    }
    trap '_move_cleanup' EXIT

    export _LE_MOVE_VAULT="$VAULT_PATH"
    export _LE_MOVE_SOURCE="$TARGET"
    export _LE_MOVE_DESTINATION="$MOVE_DESTINATION"
    export _LE_MOVE_EXPECTED="$EXPECTED_SNAPSHOT"
    export _LE_MOVE_META="$MOVE_META"
    export _LE_MOVE_SOURCE_COPY="$MOVE_SOURCE_COPY"

    "$PYTHON_BIN" - <<'PY'
import hashlib, os, pathlib, re, sys

def fail(message, code=1):
    sys.stderr.write(message + "\n")
    raise SystemExit(code)

for name in ("_LE_MOVE_VAULT", "_LE_MOVE_SOURCE", "_LE_MOVE_DESTINATION"):
    if "\n" in os.environ[name] or "\r" in os.environ[name]:
        fail("Vault move paths cannot contain newlines")

expected = os.environ["_LE_MOVE_EXPECTED"]
if not re.fullmatch(r"[0-9a-f]{64}", expected):
    fail("Invalid expected source hash: use a lowercase SHA-256")

vault = pathlib.Path(os.environ["_LE_MOVE_VAULT"]).expanduser().resolve(strict=True)
if not vault.is_dir():
    fail("VAULT_PATH is not a directory: %s" % vault)

def input_path(raw):
    path = pathlib.Path(raw).expanduser()
    return path if path.is_absolute() else vault / path

source_input = input_path(os.environ["_LE_MOVE_SOURCE"])
if source_input.is_symlink():
    fail("Move source must not be a symbolic link: %s" % source_input)
try:
    source = source_input.resolve(strict=True)
except FileNotFoundError:
    fail("Move source does not exist: %s" % source_input, 2)
if not source.is_file():
    fail("Move source must be a regular file: %s" % source)

destination_input = input_path(os.environ["_LE_MOVE_DESTINATION"])
if destination_input.exists() or destination_input.is_symlink():
    fail("Move destination already exists: %s" % destination_input)
destination_parent = destination_input.parent.resolve(strict=False)
destination = destination_parent / destination_input.name

try:
    source_rel = source.relative_to(vault)
    destination_rel = destination.relative_to(vault)
except ValueError:
    fail("Move source and destination must both be inside VAULT_PATH")
if source == destination:
    fail("Move source and destination are the same path")

actual = hashlib.sha256(source.read_bytes()).hexdigest()
if actual != expected:
    fail("Source changed since snapshot read: %s (expected %s, found %s)" %
         (source, expected, actual), 2)

with open(os.environ["_LE_MOVE_META"], "w", encoding="utf-8", newline="\n") as handle:
    for value in (vault, source, destination, source_rel.as_posix(), destination_rel.as_posix()):
        handle.write(str(value) + "\n")
PY

    {
        IFS= read -r MOVE_VAULT
        IFS= read -r MOVE_SOURCE_ABS
        IFS= read -r MOVE_DESTINATION_ABS
        IFS= read -r MOVE_SOURCE_REL
        IFS= read -r MOVE_DESTINATION_REL
    } < "$MOVE_META"

    mkdir -p "$(dirname "$MOVE_DESTINATION_ABS")"
    MOVE_SOURCE_LOCK="$(_lock_path_for "$MOVE_SOURCE_ABS")"
    MOVE_DESTINATION_LOCK="$(_lock_path_for "$MOVE_DESTINATION_ABS")"
    if [ "$MOVE_SOURCE_LOCK" \< "$MOVE_DESTINATION_LOCK" ]; then
        MOVE_LOCK_1="$MOVE_SOURCE_LOCK"
        MOVE_LOCK_2="$MOVE_DESTINATION_LOCK"
    else
        MOVE_LOCK_1="$MOVE_DESTINATION_LOCK"
        MOVE_LOCK_2="$MOVE_SOURCE_LOCK"
    fi

    if command -v flock &>/dev/null; then
        _MOVE_LOCK_MODE="flock"
        exec 8>"$MOVE_LOCK_1"
        flock -w 10 8 || { echo "Failed to acquire lock for $MOVE_LOCK_1" >&2; exit 1; }
        exec 9>"$MOVE_LOCK_2"
        flock -w 10 9 || { echo "Failed to acquire lock for $MOVE_LOCK_2" >&2; exit 1; }
    else
        _MOVE_LOCK_MODE="mkdir"
        _MOVE_LOCK_DIR_1="${MOVE_LOCK_1}.d"
        _MOVE_LOCK_DIR_2="${MOVE_LOCK_2}.d"
        MOVE_DEADLINE=$(( $(date +%s) + 10 ))
        while ! mkdir "$_MOVE_LOCK_DIR_1" 2>/dev/null; do
            [ "$(date +%s)" -lt "$MOVE_DEADLINE" ] || { echo "Failed to acquire lock for $MOVE_LOCK_1" >&2; exit 1; }
            sleep 1
        done
        while ! mkdir "$_MOVE_LOCK_DIR_2" 2>/dev/null; do
            [ "$(date +%s)" -lt "$MOVE_DEADLINE" ] || { echo "Failed to acquire lock for $MOVE_LOCK_2" >&2; exit 1; }
            sleep 1
        done
    fi

    # Re-check every compare-and-move precondition under both locks. This is
    # the check that closes the race between the caller's snapshot and the CLI.
    export _LE_MOVE_SOURCE_ABS="$MOVE_SOURCE_ABS"
    export _LE_MOVE_DESTINATION_ABS="$MOVE_DESTINATION_ABS"
    export _LE_MOVE_SOURCE_REL="$MOVE_SOURCE_REL"
    export _LE_MOVE_DESTINATION_REL="$MOVE_DESTINATION_REL"
    "$PYTHON_BIN" - <<'PY'
import hashlib, os, pathlib, sys
source = pathlib.Path(os.environ["_LE_MOVE_SOURCE_ABS"])
destination = pathlib.Path(os.environ["_LE_MOVE_DESTINATION_ABS"])
expected = os.environ["_LE_MOVE_EXPECTED"]
if source.is_symlink() or not source.is_file():
    sys.stderr.write("Move source disappeared or changed type while waiting for locks: %s\n" % source)
    raise SystemExit(2)
if source.resolve(strict=True) != source:
    sys.stderr.write("Move source changed identity while waiting for locks: %s\n" % source)
    raise SystemExit(2)
if destination.exists() or destination.is_symlink():
    sys.stderr.write("Move destination appeared while waiting for locks: %s\n" % destination)
    raise SystemExit(2)
source_bytes = source.read_bytes()
actual = hashlib.sha256(source_bytes).hexdigest()
if actual != expected:
    sys.stderr.write("Source changed while waiting for locks: %s (expected %s, found %s)\n" %
                     (source, expected, actual))
    raise SystemExit(2)
# Keep the verified source bytes: post-move verification needs them to recognise
# Obsidian healing the note's own path-qualified self-links.
pathlib.Path(os.environ["_LE_MOVE_SOURCE_COPY"]).write_bytes(source_bytes)
PY

    if [ -n "${OBSIDIAN_CLI:-}" ]; then
        OBSIDIAN_BIN="$OBSIDIAN_CLI"
        [ -x "$OBSIDIAN_BIN" ] || { echo "Obsidian CLI is unavailable: $OBSIDIAN_BIN" >&2; exit 1; }
    else
        OBSIDIAN_BIN="$(command -v obsidian || true)"
        [ -n "$OBSIDIAN_BIN" ] || { echo "Obsidian CLI is unavailable" >&2; exit 1; }
    fi

    OBSIDIAN_CALL_TIMEOUT_SECONDS="${LOCKED_EDIT_OBSIDIAN_CALL_TIMEOUT_SECONDS:-5}"
    case "$OBSIDIAN_CALL_TIMEOUT_SECONDS" in
        ''|*[!0-9]*) echo "LOCKED_EDIT_OBSIDIAN_CALL_TIMEOUT_SECONDS must be an integer" >&2; exit 1 ;;
    esac
    if [ "$OBSIDIAN_CALL_TIMEOUT_SECONDS" -lt 1 ] || [ "$OBSIDIAN_CALL_TIMEOUT_SECONDS" -gt 30 ]; then
        echo "LOCKED_EDIT_OBSIDIAN_CALL_TIMEOUT_SECONDS must be between 1 and 30" >&2
        exit 1
    fi

    _obsidian_read_nonempty() {
        "$PYTHON_BIN" - "$OBSIDIAN_CALL_TIMEOUT_SECONDS" "$@" <<'PY'
import subprocess, sys, time
timeout = int(sys.argv[1])
command = sys.argv[2:]
for attempt in range(3):
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False,
        )
        if result.stdout:
            sys.stdout.write(result.stdout.rstrip("\n"))
            raise SystemExit(0)
    except subprocess.TimeoutExpired:
        pass
    if attempt < 2:
        time.sleep(1)
raise SystemExit(1)
PY
    }

    MOVE_HELP="$(_obsidian_read_nonempty "$OBSIDIAN_BIN" help move || true)"
    case "$MOVE_HELP" in *'path=<path>'*'to=<path>'*) ;; *) echo "Obsidian CLI move syntax is unsupported" >&2; exit 1 ;; esac
    OBSIDIAN_VERSION="$(_obsidian_read_nonempty "$OBSIDIAN_BIN" version || true)"
    [ -n "$OBSIDIAN_VERSION" ] || { echo "Obsidian app is not responding to the CLI" >&2; exit 1; }
    ACTIVE_VAULT="$(_obsidian_read_nonempty "$OBSIDIAN_BIN" vault info=path || true)"
    [ -n "$ACTIVE_VAULT" ] || { echo "Obsidian app did not report an active vault" >&2; exit 1; }
    export _LE_MOVE_ACTIVE_VAULT="$ACTIVE_VAULT"
    "$PYTHON_BIN" - <<'PY'
import os, pathlib, sys
try:
    active = pathlib.Path(os.environ["_LE_MOVE_ACTIVE_VAULT"].strip()).expanduser().resolve(strict=True)
except (FileNotFoundError, OSError):
    sys.stderr.write("Obsidian reported an invalid active vault path\n")
    raise SystemExit(1)
expected = pathlib.Path(os.environ["_LE_MOVE_VAULT"]).expanduser().resolve(strict=True)
if active != expected:
    sys.stderr.write("Obsidian active vault does not match VAULT_PATH: %s != %s\n" % (active, expected))
    raise SystemExit(1)
PY

    # Snapshot only Markdown files that currently link to the source. After
    # the move, this lets $park prove Obsidian changed link targets and nothing
    # else without rereading every healed file as semantic work.
    export _LE_MOVE_SNAPSHOT="$MOVE_SNAPSHOT"
    "$PYTHON_BIN" - <<'PY'
import base64, json, os, pathlib, posixpath, re
from urllib.parse import unquote, urlsplit

vault = pathlib.Path(os.environ["_LE_MOVE_VAULT"]).resolve(strict=True)
source_rel = os.environ["_LE_MOVE_SOURCE_REL"]
source_no_ext = source_rel[:-3] if source_rel.lower().endswith(".md") else source_rel

def normalise_wiki(target):
    target = unquote(target.split("|", 1)[0].split("#", 1)[0].strip()).lstrip("/")
    return target[:-3] if target.lower().endswith(".md") else target

def normalise_markdown(target, note_rel):
    target = target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1:target.index(">")]
    else:
        target = target.split(None, 1)[0]
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path).replace("\\", "/")
    if path.startswith("/"):
        return posixpath.normpath(path.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(note_rel), path))

items = []
for note in vault.rglob("*.md"):
    note_rel = note.relative_to(vault).as_posix()
    if any(part.startswith(".") for part in pathlib.PurePosixPath(note_rel).parts):
        continue
    try:
        raw = note.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError):
        continue
    found = any(
        "/" in normalise_wiki(match.group(1))
        and normalise_wiki(match.group(1)) == source_no_ext
        for match in re.finditer(r"\[\[([^\]]+)\]\]", text)
    )
    if not found:
        found = any(
            normalise_markdown(match.group(1), note_rel) in (source_rel, source_no_ext)
            for match in re.finditer(r"\]\(([^)]+)\)", text)
        )
    if found:
        items.append({"path": note_rel, "bytes": base64.b64encode(raw).decode("ascii")})

with open(os.environ["_LE_MOVE_SNAPSHOT"], "w", encoding="utf-8", newline="\n") as handle:
    json.dump(items, handle, ensure_ascii=False)
    handle.write("\n")
PY

    # Obsidian's exit status is not a reliable indication of whether its
    # asynchronous move landed. Verification below is the authority.
    "$PYTHON_BIN" - "$OBSIDIAN_CALL_TIMEOUT_SECONDS" "$OBSIDIAN_BIN" \
        move "path=$MOVE_SOURCE_REL" "to=$MOVE_DESTINATION_REL" <<'PY'
import subprocess, sys
timeout = int(sys.argv[1])
command = sys.argv[2:]
try:
    subprocess.run(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=timeout, check=False,
    )
except subprocess.TimeoutExpired:
    pass
PY

    MOVE_SETTLE_TIMEOUT_SECONDS="${LOCKED_EDIT_MOVE_TIMEOUT_SECONDS:-10}"
    case "$MOVE_SETTLE_TIMEOUT_SECONDS" in
        ''|*[!0-9]*) echo "LOCKED_EDIT_MOVE_TIMEOUT_SECONDS must be an integer" >&2; exit 1 ;;
    esac
    if [ "$MOVE_SETTLE_TIMEOUT_SECONDS" -lt 1 ] || [ "$MOVE_SETTLE_TIMEOUT_SECONDS" -gt 60 ]; then
        echo "LOCKED_EDIT_MOVE_TIMEOUT_SECONDS must be between 1 and 60" >&2
        exit 1
    fi
    MOVE_DEADLINE=$(( $(date +%s) + MOVE_SETTLE_TIMEOUT_SECONDS ))
    MOVE_COMPLETE=false
    MOVE_VERIFY_RC=""
    MOVE_POSTCHECK=""
    while [ "$(date +%s)" -le "$MOVE_DEADLINE" ]; do
        if [ ! -e "$MOVE_SOURCE_ABS" ] && [ -f "$MOVE_DESTINATION_ABS" ]; then
            export _LE_MOVE_REFS="$MOVE_REFS"
            set +e
            "$PYTHON_BIN" - <<'PY'
import hashlib, os, pathlib, posixpath, re, sys
from urllib.parse import unquote, urlsplit

vault = pathlib.Path(os.environ["_LE_MOVE_VAULT"]).resolve(strict=True)
source_rel = os.environ["_LE_MOVE_SOURCE_REL"]
source_no_ext = source_rel[:-3] if source_rel.lower().endswith(".md") else source_rel
destination = pathlib.Path(os.environ["_LE_MOVE_DESTINATION_ABS"])
expected = os.environ["_LE_MOVE_EXPECTED"]
refs_file = os.environ["_LE_MOVE_REFS"]

destination_bytes = destination.read_bytes()
if hashlib.sha256(destination_bytes).hexdigest() != expected:
    # Obsidian also heals path-qualified links the note carries to *itself*
    # (e.g. a session log's Previous/Next-session anchors), so the moved bytes
    # may legitimately differ from the source snapshot by exactly that rewrite.
    # Accept that single transformation and nothing else.
    destination_rel = os.environ["_LE_MOVE_DESTINATION_REL"]
    destination_no_ext = destination_rel[:-3] if destination_rel.lower().endswith(".md") else destination_rel
    source_copy = os.environ.get("_LE_MOVE_SOURCE_COPY", "")
    accepted = False
    if source_copy and os.path.isfile(source_copy):
        source_bytes = pathlib.Path(source_copy).read_bytes()
        if hashlib.sha256(source_bytes).hexdigest() == expected:
            healed = source_bytes.replace(
                ("[[" + source_no_ext).encode("utf-8"),
                ("[[" + destination_no_ext).encode("utf-8"),
            )
            accepted = healed != source_bytes and healed == destination_bytes
    if not accepted:
        raise SystemExit(5)

def normalise_wiki(target):
    target = unquote(target.split("|", 1)[0].split("#", 1)[0].strip()).lstrip("/")
    return target[:-3] if target.lower().endswith(".md") else target

def normalise_markdown(target, note_rel):
    target = target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1:target.index(">")]
    else:
        target = target.split(None, 1)[0]
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path).replace("\\", "/")
    if path.startswith("/"):
        resolved = posixpath.normpath(path.lstrip("/"))
    else:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(note_rel), path))
    return resolved

hits = []
for note in vault.rglob("*.md"):
    try:
        note_rel = note.relative_to(vault).as_posix()
    except ValueError:
        continue
    if any(part.startswith(".") for part in pathlib.PurePosixPath(note_rel).parts):
        continue
    try:
        text = note.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        continue
    for match in re.finditer(r"\[\[([^\]]+)\]\]", text):
        target = normalise_wiki(match.group(1))
        if "/" in target and target == source_no_ext:
            hits.append((note_rel, text.count("\n", 0, match.start()) + 1))
    for match in re.finditer(r"\]\(([^)]+)\)", text):
        target = normalise_markdown(match.group(1), note_rel)
        if target in (source_rel, source_no_ext):
            hits.append((note_rel, text.count("\n", 0, match.start()) + 1))

with open(refs_file, "w", encoding="utf-8") as handle:
    for path, line in hits:
        handle.write("%s:%d\n" % (path, line))
raise SystemExit(4 if hits else 0)
PY
            MOVE_VERIFY_RC=$?
            set -e
            if [ "$MOVE_VERIFY_RC" -eq 0 ]; then
                MOVE_COMPLETE=true
                break
            fi
            if [ "$MOVE_VERIFY_RC" -ne 4 ] && [ "$MOVE_VERIFY_RC" -ne 5 ]; then
                echo "Could not verify Obsidian move result" >&2
                exit 1
            fi
        fi
        sleep 1
    done

    if [ "$MOVE_COMPLETE" != true ]; then
        echo "Obsidian move did not reach a verified complete state" >&2
        [ -e "$MOVE_SOURCE_ABS" ] && echo "Source still exists: $MOVE_SOURCE_ABS" >&2
        [ -e "$MOVE_DESTINATION_ABS" ] || echo "Destination is absent: $MOVE_DESTINATION_ABS" >&2
        if [ -s "$MOVE_REFS" ]; then
            echo "Old path-qualified links remain:" >&2
            sed -n '1,20p' "$MOVE_REFS" >&2
        fi
        # A move that landed but failed its postcheck still falls through to
        # the record step: the links that did heal are real edits, and without
        # a receipt they could not be told apart from unreviewed changes.
        if [ ! -e "$MOVE_SOURCE_ABS" ] && [ -f "$MOVE_DESTINATION_ABS" ]; then
            case "$MOVE_VERIFY_RC" in
                4) MOVE_POSTCHECK="old-links-remain" ;;
                5) MOVE_POSTCHECK="destination-content-mismatch" ;;
            esac
        fi
        [ -n "$MOVE_POSTCHECK" ] || exit 1
    fi

    # Structural moves bypass the ordinary content-edit tail below. Record the
    # endpoints plus each file whose observed delta is provably link healing.
    # A receipt for a move that failed its postcheck is marked incomplete.
    _LE_SID="$(_session_id)"
    if [ -n "$_LE_SID" ]; then
        _LEDGER_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state"
        mkdir -p "$_LEDGER_DIR" 2>/dev/null || true
        {
            printf '%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "locked-move-source" "$MOVE_SOURCE_ABS" "?"
            printf '%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "locked-move-destination" "$MOVE_DESTINATION_ABS" "?"
        } >> "$_LEDGER_DIR/$_LE_SID.tsv" 2>/dev/null || true
        _MOVE_RECEIPT_DIR="$_LEDGER_DIR/$_LE_SID.project-move-receipts"
        mkdir -p "$_MOVE_RECEIPT_DIR" 2>/dev/null || true
        export _LE_MOVE_RECEIPT_DIR="$_MOVE_RECEIPT_DIR"
        export _LE_MOVE_LEDGER="$_LEDGER_DIR/$_LE_SID.tsv"
        export _LE_MOVE_POSTCHECK="$MOVE_POSTCHECK"
        _LE_MOVE_RECEIPT_PATH="$("$PYTHON_BIN" - <<'PY' 2>/dev/null || true
import base64, datetime, difflib, hashlib, json, os, pathlib, posixpath, re, tempfile
from urllib.parse import unquote, urlsplit

root = pathlib.Path(os.environ["_LE_MOVE_RECEIPT_DIR"])
vault = pathlib.Path(os.environ["_LE_MOVE_VAULT"]).resolve(strict=True)
source_abs = pathlib.Path(os.environ["_LE_MOVE_SOURCE_ABS"])
destination_abs = pathlib.Path(os.environ["_LE_MOVE_DESTINATION_ABS"])
source_rel = os.environ["_LE_MOVE_SOURCE_REL"]
destination_rel = os.environ["_LE_MOVE_DESTINATION_REL"]
source_no_ext = source_rel[:-3] if source_rel.lower().endswith(".md") else source_rel
destination_no_ext = destination_rel[:-3] if destination_rel.lower().endswith(".md") else destination_rel

def sha(data):
    return hashlib.sha256(data).hexdigest()

def lint_fingerprint(text):
    joined = len(re.findall(r"[^\s=`]- \[[ x]\]", text))
    blank_runs = 0
    blanks = 0
    for line in text.splitlines():
        if line.strip():
            blanks = 0
        else:
            blanks += 1
            if blanks == 3:
                blank_runs += 1
    return [f"joined-list-count:{joined}", f"blank-run-count:{blank_runs}"]

def normalise_wiki(target):
    target = unquote(target.strip()).lstrip("/")
    return target[:-3] if target.lower().endswith(".md") else target

def normalise_markdown(target, note_rel):
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path).replace("\\", "/")
    if path.startswith("/"):
        return posixpath.normpath(path.lstrip("/"))
    return posixpath.normpath(posixpath.join(posixpath.dirname(note_rel), path))

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]|(!?\[[^\]\n]*\]\()([^)\n]+)(\))")

def skeleton(text, note_rel, wanted):
    pieces = []
    cursor = 0
    healed = 0
    for match in LINK_RE.finditer(text):
        pieces.append(text[cursor:match.start()])
        if match.group(1) is not None:
            inner = match.group(1)
            locator, marker, alias = inner.partition("|")
            path, anchor_mark, anchor = locator.partition("#")
            if normalise_wiki(path) == wanted:
                path = "<OPENCAIRN-MOVED-TARGET>"
                healed += 1
            rebuilt = path + (anchor_mark + anchor if anchor_mark else "")
            if marker:
                rebuilt += marker + alias
            pieces.append("[[" + rebuilt + "]]" )
        else:
            raw = match.group(3)
            if raw.startswith("<") and ">" in raw:
                end = raw.index(">")
                target, prefix, suffix = raw[1:end], "<", raw[end:]
            else:
                token = re.match(r"(\S+)(.*)", raw, re.DOTALL)
                target, prefix, suffix = token.group(1), "", token.group(2)
            if normalise_markdown(target, note_rel) in (wanted, wanted + ".md"):
                parsed = urlsplit(target)
                target = "<OPENCAIRN-MOVED-TARGET>"
                if parsed.query:
                    target += "?" + parsed.query
                if parsed.fragment:
                    target += "#" + parsed.fragment
                healed += 1
            pieces.append(match.group(2) + prefix + target + suffix + match.group(4))
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces), healed

snapshots = json.loads(pathlib.Path(os.environ["_LE_MOVE_SNAPSHOT"]).read_text(encoding="utf-8"))
verified = []
unverified = []
ledger_paths = []
for item in snapshots:
    before_rel = item["path"]
    after_rel = destination_rel if before_rel == source_rel else before_rel
    after_path = vault / after_rel
    ledger_paths.append(str(after_path))
    try:
        before_bytes = base64.b64decode(item["bytes"], validate=True)
        after_bytes = after_path.read_bytes()
        before_text = before_bytes.decode("utf-8")
        after_text = after_bytes.decode("utf-8")
    except (OSError, UnicodeError, ValueError):
        unverified.append(after_rel)
        continue
    before_shape, before_count = skeleton(before_text, before_rel, source_no_ext)
    after_shape, after_count = skeleton(after_text, after_rel, destination_no_ext)
    if before_count < 1 or before_count != after_count or before_shape != after_shape:
        unverified.append(after_rel)
        continue
    unified = "".join(difflib.unified_diff(
        before_text.splitlines(keepends=True),
        after_text.splitlines(keepends=True),
        fromfile=before_rel,
        tofile=after_rel,
        n=2,
    ))
    verified.append({
        "path": after_rel,
        "pre_sha256": sha(before_bytes),
        "post_sha256": sha(after_bytes),
        "healed_links": before_count,
        "pre_lint": lint_fingerprint(before_text),
        "post_lint": lint_fingerprint(after_text),
        "unified_diff": unified[:65536],
        "diff_truncated": len(unified) > 65536,
    })

payload = {
    "schema": 2,
    "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds"),
    "mode": "--move",
    "vault": str(vault),
    "source": str(source_abs),
    "destination": str(destination_abs),
    "source_locator": source_no_ext,
    "destination_locator": destination_no_ext,
    "source_sha256": os.environ["_LE_MOVE_EXPECTED"],
    "content_sha256": sha(destination_abs.read_bytes()),
    "affected_files": verified,
    "unverified_files": unverified,
    "complete": not os.environ["_LE_MOVE_POSTCHECK"],
}
if not payload["complete"]:
    reason = os.environ["_LE_MOVE_POSTCHECK"]
    remaining = []
    if reason == "old-links-remain":
        try:
            remaining = pathlib.Path(os.environ["_LE_MOVE_REFS"]).read_text(encoding="utf-8").splitlines()
        except OSError:
            pass
    payload["postcheck"] = {"reason": reason, "remaining_links": remaining}
fd, tmp = tempfile.mkstemp(prefix=".move.", dir=root)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
path = root / ("move-" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20] + ".json")
os.replace(tmp, path)
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(os.environ["_LE_MOVE_LEDGER"], "a", encoding="utf-8") as ledger:
    for affected in ledger_paths:
        ledger.write(f"{stamp}\tobsidian-link-heal\t{affected}\t?\n")
print(path)
PY
        )"
        if [ -n "$_LE_MOVE_RECEIPT_PATH" ]; then
            if [ -z "$MOVE_POSTCHECK" ]; then
                echo "Move receipt: $_LE_MOVE_RECEIPT_PATH"
            else
                echo "Partial move receipt: $_LE_MOVE_RECEIPT_PATH" >&2
            fi
        fi
        unset _LE_MOVE_RECEIPT_DIR
        unset _LE_MOVE_LEDGER
        unset _LE_MOVE_POSTCHECK
    fi

    # The receipt above is evidence, not success: the move is still unverified.
    [ -z "$MOVE_POSTCHECK" ] || exit 1

    _move_unlock_pair
    trap - EXIT
    rm -f "$MOVE_META" "$MOVE_REFS" "$MOVE_SNAPSHOT" "$MOVE_SOURCE_COPY"
    echo "Locked move applied: $MOVE_SOURCE_ABS -> $MOVE_DESTINATION_ABS"
    exit 0
fi

# Payload goes through a temp FILE, not "$(cat)": command substitution strips ALL
# trailing newlines, so a replacement block that legitimately ends on a blank line
# (e.g. a day section followed by a blank line before the next "## " heading) could
# never survive. A file read preserves the payload byte-for-byte; the single
# heredoc-added newline is then trimmed explicitly below, where it can be reasoned about.
if [ "$MODE" = "--show-section" ] && [ ! -f "$TARGET" ]; then
    echo "Target file does not exist: $TARGET" >&2
    exit 2
fi
STDIN_FILE="$(mktemp "${TMPDIR:-/tmp}/locked-edit-stdin.XXXXXX")"
RECEIPT_TMP="$(mktemp "${TMPDIR:-/tmp}/locked-edit-receipt.XXXXXX")"
_le_cleanup() {
    rm -f "$STDIN_FILE" "$RECEIPT_TMP" "$RECEIPT_TMP".*
}
trap '_le_cleanup' EXIT
if [ "$MODE" = "--show-section" ] || { [ "$MODE" = "--delete-section" ] && [ -t 0 ]; }; then
    : > "$STDIN_FILE"
else
    cat > "$STDIN_FILE"
fi

LOCK_FILE="$(_lock_path_for "$TARGET")"
mkdir -p "$(dirname "$TARGET")"

_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock for $TARGET" >&2; exit 1; }
# _lock replaces the EXIT trap with its own release; put the temp-file cleanup
# back beside it so an exit while the lock is held does both.
trap '_unlock; _le_cleanup' EXIT

# All file I/O and matching happens in python (literal, atomic via os.replace),
# while bash holds the cross-platform lock. python reads the payload from the
# environment to avoid any shell-quoting/escaping of multiline content.
export _LE_TARGET="$TARGET"
export _LE_MODE="$MODE"
export _LE_SEP="$SEP"
export _LE_STDIN_FILE="$STDIN_FILE"
export _LE_EXPECTED_SNAPSHOT="$EXPECTED_SNAPSHOT"
export _LE_SECTION_HEADING="$SECTION_HEADING"
export _LE_SECTION_NO_REPLACEMENT="$SECTION_NO_REPLACEMENT"
export _LE_RECEIPT_FILE="$RECEIPT_TMP"

set +e
"$PYTHON_BIN" - <<'PY'
import datetime, difflib, hashlib, json, os, re, sys, tempfile

target = os.environ["_LE_TARGET"]
mode   = os.environ["_LE_MODE"]
sep    = os.environ["_LE_SEP"]
with open(os.environ["_LE_STDIN_FILE"], "rb") as _f:
    stdin_bytes = _f.read()

def atomic_write(path, data):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".le-", suffix=".tmp")
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        # Preserve the target's existing mode: mkstemp creates the temp file
        # 0600, so without this every locked edit would silently reset the
        # planning file's permissions (breaking group-readable / NAS setups).
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except FileNotFoundError:
            # Match an ordinary file creation instead of installing mkstemp's
            # private 0600 mode when --replace-whole creates a new target.
            current_umask = os.umask(0)
            os.umask(current_umask)
            os.chmod(tmp, 0o666 & ~current_umask)
        os.replace(tmp, path)   # atomic within the same filesystem
    except BaseException:
        try: os.remove(tmp)
        except OSError: pass
        raise

receipt_clock = datetime.datetime.now(datetime.timezone.utc)
# Modes whose every change is one literal splice are recorded as the single
# --replace they are equivalent to, so receipt consumers need no new case.
receipt_mode = "--replace" if mode in ("--replace-many", "--delete-section") else mode

def receipt_text(value, limit=65536):
    if value is None:
        return None, False
    if len(value) <= limit:
        return value, False
    return value[:limit], True

def lint_fingerprint(text):
    """Return counts for every occurrence of the park verifier's lint classes."""
    joined_count = sum(1 for _ in re.finditer(r"[^\s=`]- \[[ x]\]", text))
    blank_run_count = 0
    blanks = 0
    for line in text.splitlines():
        if line.strip():
            blanks = 0
        else:
            blanks += 1
            if blanks == 3:
                blank_run_count += 1
    return [f"joined-list-count:{joined_count}", f"blank-run-count:{blank_run_count}"]

def write_receipt(before, after, old_text=None, new_text=None, occurrences=None,
                  position=None, batch_index=None):
    """Write evidence before the target mutation; failure is deliberately non-fatal.

    `position` pins a single replacement to a known offset instead of the first
    literal occurrence. `batch_index` marks one pair of a multi-pair call: its
    receipt goes to its own file, with a timestamp that preserves pair order.
    """
    try:
        before_bytes = before if isinstance(before, bytes) else before.encode()
        after_bytes = after if isinstance(after, bytes) else after.encode()
        before_text = before_bytes.decode("utf-8", errors="replace")
        after_text = after_bytes.decode("utf-8", errors="replace")
        ranges = []
        diff_before = ""
        diff_after = ""
        if old_text is not None and new_text is not None:
            # Locator receipts already carry the exact replacement payload, so
            # derive ranges from literal positions instead of diffing the full
            # file. This keeps receipt creation linear even for large notes.
            before_offset = 0
            line_delta = 0
            for _ in range(occurrences or 1):
                before_pos = before_text.find(old_text, before_offset) if position is None else position
                if before_pos < 0:
                    break
                before_start = before_text.count("\n", 0, before_pos) + 1
                after_start = before_start + line_delta
                old_line_count = max(1, len(old_text.splitlines()))
                new_line_count = max(1, len(new_text.splitlines()))
                ranges.append({
                    "tag": "replace",
                    "before_start": before_start,
                    "before_end": before_start + old_line_count - 1,
                    "after_start": after_start,
                    "after_end": after_start + new_line_count - 1,
                })
                before_offset = before_pos + len(old_text)
                line_delta += new_line_count - old_line_count
            diff_before = old_text
            diff_after = new_text
        elif mode == "--append" and after_text.startswith(before_text):
            diff_after = after_text[len(before_text):]
            start = len(before_text.splitlines()) + 1
            ranges.append({
                "tag": "insert",
                "before_start": start,
                "before_end": start - 1,
                "after_start": start,
                "after_end": start + max(1, len(diff_after.splitlines())) - 1,
            })
        else:
            ranges.append({
                "tag": "replace" if before_text else "insert",
                "before_start": 1,
                "before_end": len(before_text.splitlines()),
                "after_start": 1,
                "after_end": len(after_text.splitlines()),
            })
        # Give difflib newline-terminated logical lines even when the source
        # file itself lacks a final newline; otherwise a deletion and addition
        # can concatenate into one unreadable receipt line.
        diff = "".join(difflib.unified_diff(
            [line + "\n" for line in diff_before.splitlines()],
            [line + "\n" for line in diff_after.splitlines()],
            fromfile="before", tofile="after", n=2,
        ))
        diff_truncated = len(diff) > 65536
        if diff_truncated:
            diff = diff[:65536] + "\n[diff truncated]\n"
        old_value, old_truncated = receipt_text(old_text)
        new_value, new_truncated = receipt_text(new_text)
        captured = receipt_clock + datetime.timedelta(microseconds=batch_index or 0)
        payload = {
            "schema": 1,
            "captured_at": captured.isoformat(timespec="microseconds"),
            "target": os.path.realpath(os.path.abspath(target)),
            "mode": receipt_mode,
            "pre_sha256": hashlib.sha256(before_bytes).hexdigest() if os.path.exists(target) else "MISSING",
            "post_sha256": hashlib.sha256(after_bytes).hexdigest(),
            "pre_lint": lint_fingerprint(before_text),
            "post_lint": lint_fingerprint(after_text),
            "old_text": old_value,
            "new_text": new_value,
            "old_text_truncated": old_truncated,
            "new_text_truncated": new_truncated,
            "occurrences": occurrences,
            "changed_ranges": ranges[:200],
            "ranges_truncated": len(ranges) > 200,
            "unified_diff": diff,
            "diff_truncated": diff_truncated,
        }
        if receipt_mode != mode:
            payload["invoked_mode"] = mode
        receipt_file = os.environ["_LE_RECEIPT_FILE"]
        if batch_index is not None:
            receipt_file += ".%04d" % batch_index
        # Receipts carry file text: owner-only, like the mktemp file they sit beside.
        descriptor = os.open(receipt_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with open(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.write("\n")
    except Exception as exc:
        sys.stderr.write("WARNING: locked-edit receipt unavailable: %s\n" % exc)

if os.path.exists(target):
    with open(target, "rb") as _f:
        before_bytes = _f.read()
else:
    before_bytes = b""

if mode == "--replace-whole":
    expected = os.environ["_LE_EXPECTED_SNAPSHOT"]
    if expected != "MISSING" and not re.fullmatch(r"[0-9a-f]{64}", expected):
        sys.stderr.write("Invalid expected snapshot for --replace-whole: use a lowercase SHA-256 or MISSING\n")
        sys.exit(1)
    if os.path.exists(target):
        with open(target, "rb") as f:
            current = f.read()
        actual = hashlib.sha256(current).hexdigest()
    else:
        actual = "MISSING"
    if actual != expected:
        sys.stderr.write("Target changed since snapshot read: %s (expected %s, found %s)\n" %
                         (target, expected, actual))
        sys.exit(2)
    write_receipt(before_bytes, stdin_bytes)
    atomic_write(target, stdin_bytes)
    sys.exit(0)

stdin = stdin_bytes.decode("utf-8")

if mode == "--append":
    existing = before_bytes.decode("utf-8")
    # Append verbatim; ensure exactly one newline boundary before the new block.
    if existing and not existing.endswith("\n"):
        existing += "\n"
    # Terminate the appended block with a newline: a payload piped without a
    # trailing newline (printf '%s', echo -n) would otherwise leave the file
    # unterminated, and a later foreign appender (Edit tool) would concatenate
    # onto the last line.
    if stdin and not stdin.endswith("\n"):
        stdin += "\n"
    after = (existing + stdin).encode("utf-8")
    write_receipt(before_bytes, after)
    atomic_write(target, after)
    sys.exit(0)

if mode == "--replace-many":
    def usage(message):
        sys.stderr.write("--replace-many: %s\n" % message)
        sys.exit(1)

    try:
        pairs = json.loads(stdin)
    except ValueError as exc:
        usage("stdin is not valid JSON (%s)" % exc)
    if not isinstance(pairs, list) or not pairs:
        usage('stdin must be a non-empty JSON array of {"old", "new"} objects')
    total = len(pairs)
    for number, pair in enumerate(pairs, 1):
        if (not isinstance(pair, dict) or set(pair) != {"old", "new"}
                or not isinstance(pair["old"], str) or not isinstance(pair["new"], str)):
            usage('pair %d of %d must be an object with exactly the string keys "old" and "new"'
                  % (number, total))
        if not pair["old"]:
            usage("pair %d of %d has an empty old string" % (number, total))

    if not os.path.exists(target):
        sys.stderr.write("Target file does not exist: %s\n" % target)
        sys.exit(2)
    content = before_bytes.decode("utf-8")

    def label(number, old):
        shown = old if len(old) <= 60 else old[:60] + "..."
        return "pair %d of %d (%s)" % (number, total, json.dumps(shown, ensure_ascii=False))

    # Validate every pair against the untouched content before changing anything.
    failure = 0
    matches = []
    for number, pair in enumerate(pairs, 1):
        count = content.count(pair["old"])
        if count == 0:
            sys.stderr.write("%s: old_string not found in %s\n" % (label(number, pair["old"]), target))
            failure = failure or 2
        elif count > 1:
            sys.stderr.write("%s: old_string matched %d times in %s (make it unique)\n"
                             % (label(number, pair["old"]), count, target))
            failure = failure or 3
        else:
            matches.append((content.find(pair["old"]), number, pair["old"], pair["new"]))
    if not failure:
        matches.sort()
        for (start, number, old, _), (next_start, next_number, _, _) in zip(matches, matches[1:]):
            if start + len(old) > next_start:
                first, second = sorted((number, next_number))
                sys.stderr.write("pairs %d and %d overlap in %s (merge them into one pair)\n"
                                 % (first, second, target))
                failure = 3
    if failure:
        sys.stderr.write("No changes written to %s\n" % target)
        sys.exit(failure)

    # Splice from the end of the file backwards so earlier offsets stay valid
    # and each intermediate state is exactly one --replace away from the next.
    state = content
    for index, (start, _, old, new) in enumerate(reversed(matches)):
        following = state[:start] + new + state[start + len(old):]
        write_receipt(state, following, old, new, 1, position=start, batch_index=index)
        state = following
    atomic_write(target, state.encode("utf-8"))
    sys.exit(0)

if mode in ("--show-section", "--delete-section"):
    heading = os.environ["_LE_SECTION_HEADING"]
    wanted = re.fullmatch(r"(#{1,6})[ \t]+\S[^\r\n]*", heading)
    if not wanted:
        sys.stderr.write("%s: argument must be one complete heading line "
                         "starting with 1-6 '#' and a space\n" % mode)
        sys.exit(1)
    expected = os.environ["_LE_EXPECTED_SNAPSHOT"]
    if mode == "--delete-section" and not re.fullmatch(r"[0-9a-f]{64}", expected):
        sys.stderr.write("--delete-section: the expected section hash must be a lowercase SHA-256 "
                         "(read it with --show-section)\n")
        sys.exit(1)
    # Replace or delete must be the caller's stated choice, never inferred from
    # a payload that happened to arrive empty.
    replacement = stdin if stdin.strip() else ""
    no_replacement = os.environ["_LE_SECTION_NO_REPLACEMENT"] == "1"
    if mode == "--delete-section" and not replacement and not no_replacement:
        sys.stderr.write("--delete-section: stdin is empty. Supply the replacement on stdin, or pass "
                         "--no-replacement to delete the section outright\n")
        sys.exit(1)
    if mode == "--delete-section" and replacement and no_replacement:
        sys.stderr.write("--delete-section: --no-replacement was given but stdin carries a replacement\n")
        sys.exit(1)
    level = len(wanted.group(1))
    if not os.path.exists(target):
        sys.stderr.write("Target file does not exist: %s\n" % target)
        sys.exit(2)
    content = before_bytes.decode("utf-8")

    # One pass over the lines: record every real heading (outside fenced code)
    # with its offset, so both the match and the section end ignore fences.
    headings = []
    fence = None
    fence_line = 0
    offset = 0
    for number, raw in enumerate(content.splitlines(keepends=True), 1):
        line = raw.rstrip("\n").rstrip("\r")
        marker = re.match(r" {0,3}(`{3,}|~{3,})(.*)", line)
        if fence is None:
            if marker:
                fence = marker.group(1)
                fence_line = number
            else:
                found = re.match(r"(#{1,6})(?:[ \t]|$)", line)
                if found:
                    headings.append((offset, len(found.group(1)), line))
        elif (marker and marker.group(1)[0] == fence[0]
              and len(marker.group(1)) >= len(fence) and not marker.group(2).strip()):
            fence = None
        offset += len(raw)
    if fence is not None:
        # Every heading after an unclosed fence is hidden, so the section's end
        # cannot be trusted: it would silently run to end of file.
        sys.stderr.write("%s: the code fence opened on line %d of %s is never closed, so section "
                         "boundaries cannot be determined\n" % (mode, fence_line, target))
        sys.stderr.write("No changes written to %s\n" % target)
        sys.exit(2)

    hits = [index for index, item in enumerate(headings) if item[2] == heading]
    if not hits:
        sys.stderr.write("Section heading not found in %s: %s\n" % (target, heading))
        sys.exit(2)
    if len(hits) > 1:
        sys.stderr.write("Section heading matched %d times in %s (make it unique): %s\n"
                         % (len(hits), target, heading))
        sys.exit(3)
    start = headings[hits[0]][0]
    end = next((item[0] for item in headings[hits[0] + 1:] if item[1] <= level), len(content))

    # The preimage: the whole section, which covers every byte either form of
    # the write can remove.
    section = content[start:end]
    actual = hashlib.sha256(section.encode("utf-8")).hexdigest()
    if mode == "--show-section":
        sys.stdout.buffer.write(section.encode("utf-8"))
        sys.stdout.flush()
        sys.stderr.write("Section sha256: %s\n" % actual)
        sys.exit(0)
    if actual != expected:
        sys.stderr.write("Section changed since it was read: %s in %s (expected %s, found %s)\n"
                         % (heading, target, expected, actual))
        sys.stderr.write("No changes written to %s\n" % target)
        sys.exit(2)

    if replacement:
        if not replacement.endswith("\n"):
            replacement += "\n"
        # Keep the section's trailing blank lines as the seam before whatever
        # follows; only the heading and body are swapped for the replacement.
        body = content[start:end]
        kept = len(body) - len(body.rstrip("\r\n \t"))
        tail = body[len(body) - kept:]
        end -= kept
        end += tail.index("\n") + 1 if "\n" in tail else kept
    removed = content[start:end]
    after_bytes = (content[:start] + replacement + content[end:]).encode("utf-8")
    write_receipt(before_bytes, after_bytes, removed, replacement, 1, position=start)
    atomic_write(target, after_bytes)
    sys.stdout.buffer.write(section.encode("utf-8"))
    sys.stdout.flush()
    sys.exit(0)

# --replace / --replace-all: split stdin into OLD and NEW on the separator line.
lines = stdin.split("\n")
sep_idx = next((i for i, ln in enumerate(lines) if ln == sep), None)
if sep_idx is None:
    sys.stderr.write("No separator line found in stdin for %s mode\n" % mode)
    sys.exit(1)
old = "\n".join(lines[:sep_idx])
new = "\n".join(lines[sep_idx + 1:])
# A heredoc adds a trailing newline; the most common authoring shape is
# OLD\n<SEP>\nNEW\n — strip a single trailing newline the heredoc appended to NEW
# so it doesn't inject a spurious blank line. OLD is taken verbatim.
if new.endswith("\n"):
    new = new[:-1]

if not os.path.exists(target):
    sys.stderr.write("Target file does not exist: %s\n" % target)
    sys.exit(2)
content = before_bytes.decode("utf-8")

count = content.count(old)
if count == 0:
    sys.stderr.write("old_string not found in %s\n" % target)
    sys.exit(2)
if mode == "--replace" and count > 1:
    sys.stderr.write("old_string matched %d times in %s (use --replace-all or make it unique)\n" % (count, target))
    sys.exit(3)

if mode == "--replace":
    content = content.replace(old, new, 1)
else:
    content = content.replace(old, new)

after_bytes = content.encode("utf-8")
write_receipt(before_bytes, after_bytes, old, new, count)
atomic_write(target, after_bytes)
sys.exit(0)
PY
RC=$?
set -e

# --delete-section reserves stdout for the removed block, so its confirmation
# goes to stderr - reported here, while stderr is still the caller's.
if [ "$RC" -eq 0 ] && [ "$MODE" = "--delete-section" ]; then
    echo "Locked edit applied: $TARGET" >&2
fi

_unlock
# _unlock clears the EXIT trap; re-arm the cleanup for the rest of the run.
trap '_le_cleanup' EXIT
unset _LE_TARGET _LE_MODE _LE_SEP _LE_STDIN_FILE _LE_EXPECTED_SNAPSHOT _LE_SECTION_HEADING _LE_SECTION_NO_REPLACEMENT _LE_RECEIPT_FILE

# A read leaves no ledger row, no receipt and no confirmation line.
if [ "$MODE" = "--show-section" ]; then
    exit "$RC"
fi

# Self-ledger the write. locked-edit.sh bypasses the Write|Edit tools, so the
# PostToolUse ledger hook (session-ledger.sh) never sees these edits - and the
# files this script exists for (planning files, hubs) are exactly the ones
# /park's enumeration and the parboil draft-adoption diff care most about. A
# missing row there forces park back onto full re-derivation. Same TSV format
# as the hook, but the agent id is recorded as "?" (unknown): hook input
# carries an agent_id field, a shell environment does not, and --read already
# reports "?" honestly - never a positive "main".
# The session id is harness-neutral (lib-session.sh): under a harness with no
# Write|Edit hook at all (Codex), this self-ledger is the ledger - its rules
# route every vault write through this script, so coverage holds.
# Fails open: a ledger problem must never turn a landed edit into an error.
_LE_SID="$(_session_id)"
if [ "$RC" -eq 0 ] && [ -n "$_LE_SID" ]; then
    _LEDGER_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state"
    _LEDGER_PATH="$TARGET"
    case "$_LEDGER_PATH" in /*) ;; *) _LEDGER_PATH="$PWD/$_LEDGER_PATH" ;; esac
    # Never ledger the state files themselves (mirrors the hook's guard).
    case "$_LEDGER_PATH" in
        "$_LEDGER_DIR"/*) ;;
        *)
            _LEDGER_PATH=${_LEDGER_PATH//$'\t'/ }; _LEDGER_PATH=${_LEDGER_PATH//$'\n'/ }
            # First write of a session prunes stale ledgers (mirrors the hook's
            # sweep - under a hookless harness this is the only place it runs).
            { mkdir -p "$_LEDGER_DIR" &&
              { [ -f "$_LEDGER_DIR/$_LE_SID.tsv" ] ||
                { find "$_LEDGER_DIR" -maxdepth 1 -type f -mtime +14 -delete 2>/dev/null;
                  find "$_LEDGER_DIR" -maxdepth 2 -type f -path '*.locked-edit-receipts/*' -mtime +14 -delete 2>/dev/null;
                  find "$_LEDGER_DIR" -maxdepth 1 -type d -name '*.locked-edit-receipts' -empty -delete 2>/dev/null; } || true; } &&
              printf '%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "locked-edit" \
                  "$_LEDGER_PATH" "?" \
                  >> "$_LEDGER_DIR/$_LE_SID.tsv"; } 2>/dev/null || true
            ;;
    esac

    # One JSON file per operation avoids interleaved JSONL writes when park and
    # its propagation agent edit concurrently. Receipt failure stays fail-open:
    # the target edit has already landed, so a bookkeeping problem is a warning,
    # never a false non-zero edit result.
    # --replace-many leaves one numbered receipt file per pair beside the
    # (then empty) single-receipt file.
    for _RECEIPT_SRC in "$RECEIPT_TMP" "$RECEIPT_TMP".*; do
        [ -s "$_RECEIPT_SRC" ] || continue
        _RECEIPT_DIR="$_LEDGER_DIR/$_LE_SID.locked-edit-receipts"
        if mkdir -p "$_RECEIPT_DIR" 2>/dev/null; then
            _RECEIPT_DEST="$(mktemp "$_RECEIPT_DIR/receipt.XXXXXXXX" 2>/dev/null || true)"
            if [ -n "$_RECEIPT_DEST" ] && mv "$_RECEIPT_SRC" "$_RECEIPT_DEST" 2>/dev/null; then
                :
            else
                echo "WARNING: locked-edit receipt could not be stored for $TARGET" >&2
            fi
        else
            echo "WARNING: locked-edit receipt directory unavailable for $TARGET" >&2
        fi
    done
fi

if [ "$RC" -eq 0 ] && [ "$MODE" != "--delete-section" ]; then
    echo "Locked edit applied: $TARGET"
fi
exit "$RC"
