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
#   locked-edit.sh <file> --append        (stdin appended verbatim at end of file)
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
#
# Exit codes: 0 ok · 1 usage/lock/CLI/result error · 2 no match/stale snapshot · 3 ambiguous (>1 match under --replace)
#
# With a harness session id, every successful content-edit operation writes one JSON
# receipt under $CLAUDE_CONFIG_DIR/.session-state/<id>.locked-edit-receipts/.
# It carries pre/post hashes, exact replace payloads and bounded changed spans;
# $park uses those receipts to review mechanical locator edits without rereading
# the whole file. Receipt bookkeeping fails open and never reverses a landed edit.
#
# Platform: Linux, macOS, Windows (Git Bash). Locking via lib-lock.sh
# (flock / mkdir fallback); literal string handling via python3.
# Migration recovery compatibility: archive-bundle-v3.

set -euo pipefail

source "$(dirname "$0")/lib-lock.sh"
source "$(dirname "$0")/lib-session.sh"

SEP='========OPENCAIRN-LOCKED-EDIT-SEP========'

if [ $# -lt 2 ]; then
    echo "Usage: $0 <file> --replace|--replace-all|--append|--replace-whole|--move [argument]" >&2
    exit 1
fi

TARGET="$1"
MODE="$2"
EXPECTED_SNAPSHOT=""
MOVE_DESTINATION=""

case "$MODE" in
    --replace|--replace-all|--append) ;;
    --replace-whole)
        if [ $# -ne 3 ]; then
            echo "--replace-whole requires expected-sha256 or MISSING" >&2
            exit 1
        fi
        EXPECTED_SNAPSHOT="$3"
        ;;
    --move)
        if [ $# -ne 4 ]; then
            echo "--move requires destination and expected source SHA-256" >&2
            exit 1
        fi
        MOVE_DESTINATION="$3"
        EXPECTED_SNAPSHOT="$4"
        ;;
    *) echo "Unknown mode: $MODE (expected --replace, --replace-all, --append, --replace-whole, or --move)" >&2; exit 1 ;;
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
        rm -f "$MOVE_META" "$MOVE_REFS"
    }
    trap '_move_cleanup' EXIT

    export _LE_MOVE_VAULT="$VAULT_PATH"
    export _LE_MOVE_SOURCE="$TARGET"
    export _LE_MOVE_DESTINATION="$MOVE_DESTINATION"
    export _LE_MOVE_EXPECTED="$EXPECTED_SNAPSHOT"
    export _LE_MOVE_META="$MOVE_META"

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
try:
    destination_parent = destination_input.parent.resolve(strict=True)
except FileNotFoundError:
    fail("Move destination directory does not exist: %s" % destination_input.parent)
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
actual = hashlib.sha256(source.read_bytes()).hexdigest()
if actual != expected:
    sys.stderr.write("Source changed while waiting for locks: %s (expected %s, found %s)\n" %
                     (source, expected, actual))
    raise SystemExit(2)
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

if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
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
        exit 1
    fi

    _move_unlock_pair
    trap - EXIT
    rm -f "$MOVE_META" "$MOVE_REFS"
    echo "Locked move applied: $MOVE_SOURCE_ABS -> $MOVE_DESTINATION_ABS"
    exit 0
fi

# Payload goes through a temp FILE, not "$(cat)": command substitution strips ALL
# trailing newlines, so a replacement block that legitimately ends on a blank line
# (e.g. a day section followed by a blank line before the next "## " heading) could
# never survive. A file read preserves the payload byte-for-byte; the single
# heredoc-added newline is then trimmed explicitly below, where it can be reasoned about.
STDIN_FILE="$(mktemp "${TMPDIR:-/tmp}/locked-edit-stdin.XXXXXX")"
RECEIPT_TMP="$(mktemp "${TMPDIR:-/tmp}/locked-edit-receipt.XXXXXX")"
trap 'rm -f "$STDIN_FILE" "$RECEIPT_TMP"' EXIT
cat > "$STDIN_FILE"

LOCK_FILE="$(_lock_path_for "$TARGET")"
mkdir -p "$(dirname "$TARGET")"

_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock for $TARGET" >&2; exit 1; }

# All file I/O and matching happens in python (literal, atomic via os.replace),
# while bash holds the cross-platform lock. python reads the payload from the
# environment to avoid any shell-quoting/escaping of multiline content.
export _LE_TARGET="$TARGET"
export _LE_MODE="$MODE"
export _LE_SEP="$SEP"
export _LE_STDIN_FILE="$STDIN_FILE"
export _LE_EXPECTED_SNAPSHOT="$EXPECTED_SNAPSHOT"
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

def write_receipt(before, after, old_text=None, new_text=None, occurrences=None):
    """Write evidence before the target mutation; failure is deliberately non-fatal."""
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
                before_pos = before_text.find(old_text, before_offset)
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
        payload = {
            "schema": 1,
            "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds"),
            "target": os.path.realpath(os.path.abspath(target)),
            "mode": mode,
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
        with open(os.environ["_LE_RECEIPT_FILE"], "w", encoding="utf-8") as handle:
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

_unlock
unset _LE_TARGET _LE_MODE _LE_SEP _LE_STDIN_FILE _LE_EXPECTED_SNAPSHOT _LE_RECEIPT_FILE

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
    if [ -s "$RECEIPT_TMP" ]; then
        _RECEIPT_DIR="$_LEDGER_DIR/$_LE_SID.locked-edit-receipts"
        if mkdir -p "$_RECEIPT_DIR" 2>/dev/null; then
            _RECEIPT_DEST="$(mktemp "$_RECEIPT_DIR/receipt.XXXXXXXX" 2>/dev/null || true)"
            if [ -n "$_RECEIPT_DEST" ] && mv "$RECEIPT_TMP" "$_RECEIPT_DEST" 2>/dev/null; then
                :
            else
                echo "WARNING: locked-edit receipt could not be stored for $TARGET" >&2
            fi
        else
            echo "WARNING: locked-edit receipt directory unavailable for $TARGET" >&2
        fi
    fi
fi

if [ "$RC" -eq 0 ]; then
    echo "Locked edit applied: $TARGET"
fi
exit "$RC"
