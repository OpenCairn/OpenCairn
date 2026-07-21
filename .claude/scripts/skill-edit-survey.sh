#!/usr/bin/env bash
# Stop hook: if any skill command file was edited this session (flagged by
# skill-edit-marker.sh), remind Claude to run a cross-pollination survey before the
# turn ends. Fires once per EDIT BATCH, not once per stop.
#
# Why the batch check exists: the marker is touched by the edit itself, but Claude
# usually does the survey in that same turn — so a naive "marker exists → block" fires
# again after the work is already done, producing a no-op round-trip and a junk
# `none=no-skill-edits-since-prior-survey` log line. Every back-and-forth after a skill
# edit repeats it. So before blocking we ask: has an `outcome` line for THIS session
# been appended since the marker was last touched? If yes, the batch is covered —
# clear the marker and allow the stop silently. A fresh edit re-touches the marker,
# making it newer than the log again, so the next genuine batch still fires.
#
# The test is `[ "$LOG" -nt "$MARKER" ]` plus "this session's last log line is an
# outcome" — deliberately no timestamp parsing, since `date -d` is GNU-only and this
# ships to macOS and Git Bash too. The session-scoped line check keeps a concurrent
# session's appends from suppressing our fire.
#
# Output contract (Claude Code Stop hooks): top-level additionalContext is NOT read
# on the Stop path — Stop is not a member of CC's hookSpecificOutput union. CC takes
# the model-visible body from `stderr || stdout`, and the sync (`claude -p`) fallback
# reads the top-level `reason` paired with `decision:"block"`. So we emit the full
# reminder on BOTH stderr (asyncRewake body) and `reason` (sync fallback), with
# {"decision":"block", ...} on stdout to force one more turn. The marker is deleted on
# fire and we honour `stop_hook_active`, so this can never loop.
#
# Platform: Linux, macOS, Windows (Git Bash). Requires jq.

INPUT=$(cat)
ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
SID=$(echo "$INPUT" | jq -r '.session_id // "nosession"')
MARKER="/tmp/claude-skill-edit-${SID}.marker"

# Allow the stop if we've already re-blocked once, or no skill was edited.
if [ "$ACTIVE" = "true" ] || [ ! -f "$MARKER" ]; then
  exit 0
fi

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
LOG="$CONFIG_DIR/cross-pollination.log"

# Batch check: if this session already logged an `outcome` after the last skill edit,
# the survey covered this batch — don't block again. Both conditions must hold:
#   1. the log has been written since the marker was last touched, and
#   2. this session's most recent log line is an `outcome` (not a bare `fired`).
# (1) alone would let another session's append suppress us; (2) alone can't tell an
# outcome from *this* batch from one from a previous batch.
if [ -f "$LOG" ] && [ "$LOG" -nt "$MARKER" ]; then
  LAST_LINE=$(grep -F "session=${SID}" "$LOG" 2>/dev/null | tail -1)
  case "$LAST_LINE" in
    *"	outcome	"*)
      rm -f "$MARKER"   # batch already surveyed — allow the stop silently
      exit 0
      ;;
  esac
fi

rm -f "$MARKER"  # fire once for this batch

# Resolve the pattern index. scripts/ and commands/ ship together under the same
# .claude/ dir, so a sibling lookup is robust across personal and vault-resident
# installs. Fall back to a generic phrasing if it isn't found.
PATTERNS="$(cd "$(dirname "$0")/../commands" 2>/dev/null && pwd)/_shared-patterns.md"
if [ ! -f "$PATTERNS" ]; then
  PATTERNS="_shared-patterns.md (in your .claude/commands directory)"
fi

# Flywheel telemetry: record that the survey fired. The outcome (ported X / nothing
# needed) is appended by Claude per the reminder below — together these answer
# "is the cross-pollination flywheel actually turning?"
echo "$(date -u +%FT%TZ)	fired	session=${SID}" >> "$LOG" 2>/dev/null

REMINDER="You edited one or more skill files in .claude/commands this session. Before finishing:

(0) PLACEMENT CHECK — run this FIRST, on what you just wrote. This gate can reverse the edit, so it comes before any survey. For each thing you added, ask: is it DURABLE PROCEDURE (a mechanism that stays true across environments and tool versions — belongs in the skill), or a VOLATILE FACT (which subcommand is currently broken, a version number, a service's present state, anything that changes when the environment or tool changes)? A volatile fact does NOT belong in a skill: it gets ONE canonical home in the project's own docs — the routing/context/reference doc the skill already points at — and pointers from everywhere else. A skill naming a currently-broken tool will still be asserting it a year after the fix, and it can't be corrected by updating one file. Tell: if a sentence you added would need editing when something outside the repo changes, move it out and leave a pointer. Related: strip environment-specific and personal detail from skills that ship publicly.

(1) Consult ${PATTERNS} (the pattern pointer-index).

(2) For any SUBSTANTIVE change — a new skill, or a new capability/phase/flag added to one — survey 2-3 relevant sibling skills for transferable infrastructure you did not reuse, and port or briefly note what fits. Port the MECHANISM, never the sibling's environment-specific findings. If a fitting pattern is missing from _shared-patterns.md, add a one-line pointer entry — but only per its proven-twice gate (>=2 reuses). If the edits were trivial (typo, wording, one-line tweak), no cross-pollination is needed.

THEN, regardless of outcome, append one tab-separated line to ${LOG} recording the result: four tab-separated fields = <UTC-ISO-timestamp>, the word 'outcome', session=<id>, and either 'ported=<from>-><to>' or 'none=<reason>'. Keep it to one line — a plain event log, no analysis. Do not re-survey patterns already incorporated this session."

# Model-visible body on stderr (asyncRewake path).
printf '%s\n' "$REMINDER" >&2

# Block + reason on stdout (sync `claude -p` fallback path, plus the block decision).
jq -n --arg reason "$REMINDER" \
  '{decision: "block", reason: $reason, systemMessage: "Cross-pollination survey — skill files were edited this session."}'
exit 0
