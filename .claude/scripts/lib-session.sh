#!/usr/bin/env bash
# Harness-neutral session id resolution.
# Source this from scripts that write or read per-session state (the ledger,
# parboil snapshots). Provides _session_id(): prints the current session's id,
# or nothing when no harness identifies one.
#
# Usage:
#   source "$(dirname "$0")/lib-session.sh"
#   SID="$(_session_id)"
#   [ -n "$SID" ] || ...fall back / fail open...
#
# Resolution order (first non-empty wins):
#   1. OPENCAIRN_SESSION_ID   - explicit override; the escape hatch for any
#                               harness that exports no session id of its own
#   2. CLAUDE_CODE_SESSION_ID - Claude Code (set in every Bash tool call)
#   3. CODEX_THREAD_ID        - Codex CLI (exported into its shell commands;
#                               verified codex-cli 0.147.0)
#
# Why CLAUDE_CODE_SESSION_ID outranks CODEX_THREAD_ID: a Codex seat despatched
# from inside a Claude Code session inherits the parent's CLAUDE_CODE_SESSION_ID
# alongside its own CODEX_THREAD_ID, and a despatched seat's writes belong in
# the despatching session's ledger — the same convention as sub-agents, whose
# writes ledger under the parent's session id.
#
# Platform: Linux, macOS, Windows (Git Bash).
# Migration recovery compatibility: archive-bundle-v3.

_session_id() {
    printf '%s' "${OPENCAIRN_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-}}}"
}

# Writer identity is separate from the ledger's parent session. Explicit
# metadata wins; otherwise Codex supplies the actual writer thread id. Claude
# shell calls without agent metadata remain unknown, never inferred as main.
_session_agent_id() {
    local agent="${OPENCAIRN_AGENT_ID:-}"
    if [ -z "$agent" ] && [ -n "${CODEX_THREAD_ID:-}" ]; then
        agent="codex:$CODEX_THREAD_ID"
    fi
    printf '%s' "${agent:-?}" | LC_ALL=C tr '[:cntrl:]' ' '
}

# Short, fail-open self-ledger for successful sanctioned script writes.
# The caller holds its existing target lock; this adds no lock or write policy.
_session_record_write() {
    local sid state target
    sid="$(_session_id)"
    [ -n "$sid" ] || return 0
    state="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state"
    target="$2"
    case "$target" in /*) ;; *) target="$PWD/$target" ;; esac
    target=$(printf '%s' "$target" | LC_ALL=C tr '[:cntrl:]' ' ')
    { mkdir -p "$state" &&
      printf '%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$1" "$target" "$(_session_agent_id)" \
          >> "$state/$sid.tsv"; } 2>/dev/null || true
}
