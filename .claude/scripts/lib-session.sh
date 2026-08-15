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
#                               verified codex-cli 0.145.0)
#
# Why CLAUDE_CODE_SESSION_ID outranks CODEX_THREAD_ID: a Codex seat despatched
# from inside a Claude Code session inherits the parent's CLAUDE_CODE_SESSION_ID
# alongside its own CODEX_THREAD_ID, and a despatched seat's writes belong in
# the despatching session's ledger — the same convention as sub-agents, whose
# writes ledger under the parent's session id.
#
# Platform: Linux, macOS, Windows (Git Bash).

_session_id() {
    printf '%s' "${OPENCAIRN_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-}}}"
}
