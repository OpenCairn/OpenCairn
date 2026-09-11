#!/usr/bin/env bash
# Portable file locking library
# Source this from scripts that need file locking.
# Provides _lock() and _unlock() functions.
#
# Usage:
#   source "$(dirname "$0")/lib-lock.sh"
#   _lock "/path/to/.lock" 10
#   # ... do work ...
#   _unlock
#
# NOTE: _lock() sets an EXIT trap to auto-release the lock on unexpected exit.
# Do NOT set your own EXIT trap before calling _lock() — it will be overwritten.
# If you need cleanup logic, set your trap AFTER _unlock, or call _unlock
# explicitly and manage cleanup yourself.
#
# Platform: Linux, macOS, Windows (Git Bash).
# Uses flock where available, mkdir-based fallback otherwise. The fallback
# fails closed on an abandoned directory; it never auto-reaps a lock whose
# owner cannot be proved dead without a race.
# Migration recovery compatibility: archive-bundle-v3.

# Canonical lock path for a target file. EVERY writer of a given file must lock
# the SAME path or mutual exclusion silently fails — so all scripts derive the
# lock name from the target via this one function: <dir>/.<basename>.lock.
_lock_path_for() {
    local target="$1"
    printf '%s/.%s.lock' "$(dirname "$target")" "$(basename "$target")"
}

# Read a complete text payload from stdin without trusting the caller to close
# its pipe forever. A backgrounded heredoc wrapper can retain the writer end;
# an unbounded `cat` then waits indefinitely. EOF is normal for `read -d ''`,
# while a timeout returns >128 and fails before any lock is acquired.
_read_stdin_content() {
    local destination="$1"
    local timeout="${OPENCAIRN_STDIN_TIMEOUT_SECONDS:-30}"
    local content=""
    local status=0

    case "$timeout" in
        ''|*[!0-9]*)
            echo "Invalid stdin timeout: $timeout" >&2
            return 2
            ;;
    esac
    if [ "$timeout" -le 0 ]; then
        echo "Invalid stdin timeout: $timeout" >&2
        return 2
    fi

    IFS= read -r -d '' -t "$timeout" content || status=$?
    if [ "$status" -gt 128 ]; then
        echo "Timed out after ${timeout}s waiting for stdin to close" >&2
        return 2
    fi
    # Match the former $(cat) behaviour: command substitution removed trailing
    # newlines, and the session writers already add their own structural seams.
    while [ "${content%$'\n'}" != "$content" ]; do
        content="${content%$'\n'}"
    done
    printf -v "$destination" '%s' "$content"
}

_lock() {
    _LOCK_FILE="$1"
    local timeout="${2:-10}"
    if command -v flock &>/dev/null; then
        _LOCK_MODE="flock"
        exec 9>"$_LOCK_FILE"
        flock -w "$timeout" 9 || { echo "Lock timeout after ${timeout}s" >&2; return 1; }
        trap '_unlock' EXIT
    else
        _LOCK_MODE="mkdir"
        _LOCK_DIR="${_LOCK_FILE}.d"
        local waited=0
        while ! mkdir "$_LOCK_DIR" 2>/dev/null; do
            if [ "$waited" -ge "$timeout" ]; then
                local owner="unknown"
                if [ -r "$_LOCK_DIR/owner" ]; then
                    owner="$(sed -n '1p' "$_LOCK_DIR/owner" 2>/dev/null || echo unknown)"
                fi
                echo "Lock timeout after ${timeout}s (mkdir fallback; owner: $owner; no automatic stale-lock removal)" >&2
                return 1
            fi
            sleep 1
            waited=$((waited + 1))
        done
        printf 'pid=%s host=%s acquired=%s\n' \
            "$$" "${HOSTNAME:-$(uname -n 2>/dev/null || echo unknown)}" "$(date +%s)" \
            > "$_LOCK_DIR/owner" 2>/dev/null || true
        trap '_unlock' EXIT
    fi
}

# _unlock branches on the mode recorded by _lock (NOT a fresh `command -v flock`
# probe — PATH can differ between lock and unlock, which would release with the
# wrong primitive and leak the lock).
_unlock() {
    if [ "${_LOCK_MODE:-}" = "flock" ]; then
        exec 9>&- 2>/dev/null || true
    elif [ "${_LOCK_MODE:-}" = "mkdir" ]; then
        rm -rf "${_LOCK_DIR:-}" 2>/dev/null || true
    fi
    trap - EXIT
}
