#!/usr/bin/env bash
# Stop hook: if any skill command file was edited this session (flagged by
# skill-edit-marker.sh), remind Claude to run a cross-pollination survey before the
# turn ends. Fires once per EDIT BATCH, not once per stop.
#
# Why the batch check exists: the marker is created by the edit itself, but Claude
# usually does the survey in that same turn — so a naive "marker exists → block" fires
# again after the work is already done, producing a no-op round-trip and a junk
# `none=no-skill-edits-since-prior-survey` log line. Every back-and-forth after a skill
# edit repeats it. So before blocking we ask: has an `outcome` line for THIS session
# been appended since the batch opened? If yes, the batch is covered — clear the marker
# and allow the stop silently. A fresh edit creates a fresh marker carrying a fresh
# baseline, so the next genuine batch still fires.
#
# The mechanism is a COUNT, not a timestamp: skill-edit-marker.sh writes this session's
# `outcome`-line count into the marker when the batch opens, and we fire unless that
# count has since risen. No `date -d`/`stat` (neither portable to macOS and Git Bash),
# and — unlike a log-mtime comparison — immune to a concurrent session appending to the
# shared log. Full reasoning at the batch check below.
#
# Output contract (Claude Code Stop hooks): top-level additionalContext is NOT read.
# The nested `hookSpecificOutput.additionalContext` IS read on the Stop path — but it
# only adds context, it does not buy the extra turn this survey needs. To force one
# more turn we must emit `decision:"block"`, and on the blocked path CC takes the
# model-visible body from `reason || stderr`. So we emit the full reminder on BOTH
# stderr and `reason`, with {"decision":"block", ...} on stdout. The marker is deleted
# on fire and we honour `stop_hook_active`, so this can never loop.
#
# Verify against the harness before trusting this paragraph — it is a volatile claim
# about one Claude Code version, not durable procedure.
#
# Enforcement is NUDGE-ONCE per batch, by design: the marker is deleted at fire
# time, before the survey happens, so an abandoned blocked turn (interrupt, closed
# session) loses that batch's survey with no retry. Accepted deliberately in
# preference to hold-until-outcome re-blocking, which would trade user-visible
# stop friction for coverage. Read the fired-vs-outcome ratio in the log before
# revisiting that call.
#
# cross-pollination.log field formats vary by era: legacy lines carry three
# tab-separated fields, current lines four (<ts>, fired|outcome, session=<id>,
# detail). Consumers must filter on fields 2/3 as the awk below does — never
# assume a uniform field count across the whole file.
#
# Platform: Linux, macOS, Windows (Git Bash). Requires jq.

INPUT=$(cat)
ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
SID=$(echo "$INPUT" | jq -r '.session_id // "nosession"')
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
MARKER="$CONFIG_DIR/.session-state/${SID}.skilledit"

# Allow the stop if we've already re-blocked once, or no skill was edited.
if [ "$ACTIVE" = "true" ] || [ ! -f "$MARKER" ]; then
  exit 0
fi

LOG="$CONFIG_DIR/cross-pollination.log"

# Batch check: has THIS session logged a NEW `outcome` since we last fired? If so the
# batch is covered — clear the marker and allow the stop silently.
#
# This deliberately does NOT compare the log's mtime against the marker's. The log is
# shared by every concurrent session, so any other session appending a line makes it
# newer than our marker and satisfies such a test — silently suppressing a survey this
# session genuinely owed. Counting only OUR session's outcome lines is immune to that,
# and needs no `stat`/`date -d` (both non-portable).
#
# The baseline is written INTO the marker by skill-edit-marker.sh when the batch
# opens, so the two values are captured at the right moments by construction and no
# extra state file can go missing. The reminder tells the model to append its outcome
# line LAST, after any skill edits, so an outcome that lands above the baseline
# belongs to this batch.
#
# Field-split with awk rather than grep: `outcome` free text can itself contain the
# word "fired", which over-counts a naive grep.
BASELINE=$(cat "$MARKER" 2>/dev/null || echo 0)
case "$BASELINE" in ''|*[!0-9]*) BASELINE=0 ;; esac

COUNT=$(awk -F'\t' -v s="session=${SID}" '$2=="outcome" && $3==s {n++} END{print n+0}' "$LOG" 2>/dev/null || echo 0)
case "$COUNT" in ''|*[!0-9]*) COUNT=0 ;; esac

if [ "$COUNT" -gt "$BASELINE" ]; then
  rm -f "$MARKER"        # batch already surveyed — allow the stop silently
  exit 0
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

# Model-visible body on stderr — CC reads `reason || stderr` on the blocked path.
printf '%s\n' "$REMINDER" >&2

# Block + reason on stdout (sync `claude -p` fallback path, plus the block decision).
jq -n --arg reason "$REMINDER" \
  '{decision: "block", reason: $reason, systemMessage: "Cross-pollination survey — skill files were edited this session."}'
exit 0
