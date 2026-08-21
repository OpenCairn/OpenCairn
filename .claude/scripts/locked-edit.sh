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
# Exit codes: 0 ok · 1 usage/lock error · 2 no match/stale snapshot · 3 ambiguous (>1 match under --replace)
#
# With a harness session id, every successful operation also writes one JSON
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
    echo "Usage: $0 <file> --replace|--replace-all|--append|--replace-whole [expected-sha256|MISSING]" >&2
    exit 1
fi

TARGET="$1"
MODE="$2"
EXPECTED_SNAPSHOT=""

case "$MODE" in
    --replace|--replace-all|--append) ;;
    --replace-whole)
        if [ $# -ne 3 ]; then
            echo "--replace-whole requires expected-sha256 or MISSING" >&2
            exit 1
        fi
        EXPECTED_SNAPSHOT="$3"
        ;;
    *) echo "Unknown mode: $MODE (expected --replace, --replace-all, --append, or --replace-whole)" >&2; exit 1 ;;
esac

if command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python &>/dev/null; then
    PYTHON_BIN="$(command -v python)"
else
    echo "locked-edit.sh requires Python 3 (python3 or python)" >&2
    exit 1
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
