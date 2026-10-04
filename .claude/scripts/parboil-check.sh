#!/usr/bin/env bash
# parboil-check.sh - UserPromptSubmit: request a mid-session shadow park.
# Stop: observe a completed park and record its ledger-line watermark.
#
# Why: /park's cost is dominated by model turns, and per-turn cost rises with the
# context the turn runs in - so the same park run late in a long session costs
# materially more than run early. The expensive half of park (session narrative,
# changed-identifier enumeration, open-loop list) is derivable at any point in
# the session, and derived most cheaply while the context is still small. So: at
# a token threshold, ask the model - which already holds the whole session in
# context - to snapshot that half into a draft. /park Step 0 then adopts the
# draft wholesale if nothing has changed since, or patches only the delta.
#
# The default threshold is a starting point, not a measured constant: tune it to
# where your own sessions start feeling slow to park.
#
# Fires at the threshold, then again on each further INTERVAL tokens of context
# growth - a draft taken at 150k is stale by 400k, and a stale draft puts park
# back on the expensive delta-derivation the snapshot exists to avoid. Refreshes
# are incremental (patch the existing draft, don't rewrite it) and are suppressed
# unless the ledger has grown, so a session that stops writing stops being asked.
# A session that never writes files is never asked at all.
#
# stdout on exit 0 is added to Claude's context for UserPromptSubmit - that is
# the delivery mechanism for the instruction below.
#
# Config: OPENCAIRN_PARBOIL_TOKENS - peak context, in tokens, at which the first
#         snapshot fires. DEFAULT 0 = DISABLED. This hook ships off: its payback
#         is unproven (it consolidates work rather than eliminating it, and costs
#         one model turn per fire, wasted entirely on a session that never parks),
#         so it is opt-in per user rather than on by default. 150000 is a
#         reasonable starting value; tune it to where your own sessions start
#         feeling slow to park. Set it in settings.json's `env` block - a var
#         exported only in a shell rc will not reach this non-interactive hook.
#         OPENCAIRN_PARBOIL_INTERVAL_TOKENS (default: same as the threshold) -
#         context growth since the last snapshot before a refresh fires.
#
# Requires: jq. Platform: Linux, macOS, Windows (Git Bash). Fails open.
set -u

CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
STATE_DIR="$CONFIG_DIR/.session-state"
THRESHOLD="${OPENCAIRN_PARBOIL_TOKENS:-0}"
INTERVAL="${OPENCAIRN_PARBOIL_INTERVAL_TOKENS:-$THRESHOLD}"

[ "$THRESHOLD" -gt 0 ] 2>/dev/null || exit 0
# A non-numeric INTERVAL would make the refresh gate's arithmetic test error out,
# and its `|| exit 0` would then suppress every refresh silently. Fall back.
case "$INTERVAL" in ''|*[!0-9]*) INTERVAL=$THRESHOLD ;; esac
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
[ -n "$SID" ] || exit 0
TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null) || exit 0
[ -f "$TRANSCRIPT" ] || exit 0

MARKER="$STATE_DIR/$SID.parboil.state"   # "<peak-at-last-fire> <ledger-lines-at-last-fire>"
DRAFT="$STATE_DIR/$SID.parboil.md"
LEDGER="$STATE_DIR/$SID.tsv"
PARKED="$STATE_DIR/$SID.parked-ledger-lines"

# Nothing written this session -> nothing worth pre-parking.
[ -f "$LEDGER" ] || exit 0
LEDGER_LINES=$(wc -l < "$LEDGER" 2>/dev/null || echo 0)
[ "$LEDGER_LINES" -ge 3 ] 2>/dev/null || exit 0

# Inspect genuine user requests, not skill text echoed by a tool, quoted advice,
# compaction summaries or sub-agent records. Stream the whole transcript so an
# active park does not disappear merely because it is older than the token tail.
# A malformed transcript leaves this guard unknown and the hook fails open.
ACTIVE_PARK=$(jq -n '
    def body: if type == "string" then . else
        [.[]? | select(.type == "text") | .text] | join("\n") end;
    def park_request:
        gsub("^\\s+|\\s+$"; "")
        | test("^[/$]park(?:[ \\t]+[^\\n]*)?$")
          or (startswith("<command-") and contains("<command-name>/park</command-name>"))
          or test("^<skill>\\s*<name>park</name>");
    reduce inputs as $r (false;
        if $r.type == "user" and ($r.isMeta != true)
           and ($r.isCompactSummary != true) and ($r.isSidechain != true)
           and (($r.message.content | type) == "string"
                or ([$r.message.content[]? | select(.type == "tool_result")] | length) == 0)
        then ($r.message.content | body) as $text
             | if ($text | park_request) then true
               elif ($text | ltrimstr(" ") | startswith("<")) or $text == "" then .
               else false end
        else . end)
' "$TRANSCRIPT" 2>/dev/null) || ACTIVE_PARK=false

EVENT=$(printf '%s' "$INPUT" | jq -r '.hook_event_name // "UserPromptSubmit"' 2>/dev/null) || exit 0
if [ "$EVENT" = "Stop" ]; then
    # Stop's last_assistant_message is the final conversational output. Require
    # the park completion contract outside code fences; tool output and a quoted
    # example of the contract do not establish completion.
    if printf '%s' "$INPUT" | jq -e '
        (.last_assistant_message // "") | split("\n")
        | reduce .[] as $line ({fenced:false, lines:[]};
            if ($line | test("^\\s*(```|~~~)")) then .fenced = (.fenced | not)
            elif .fenced then . else .lines += [$line] end)
        | (.lines | join("\n"))
        | (test("(?m)^\\s*(?:Quick )?Parked\\.\\s*$")
           and test("✓ Session [0-9]+ saved:"))
          or test("(?m)^\\s*✓ Merged into Session [0-9]+")
    ' >/dev/null 2>&1; then
        mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
        printf '%s\n' "$LEDGER_LINES" > "$PARKED" 2>/dev/null || true
    fi
    exit 0
fi
[ "$EVENT" = "UserPromptSubmit" ] || exit 0

# The current prompt may not yet be in the transcript. Suppress explicit park
# invocation before recording a trigger, as well as an already-active park.
if printf '%s' "$INPUT" | jq -e '
    (.prompt // "") | gsub("^\\s+|\\s+$"; "")
    | test("^[/$]park(?:[ \\t]+[^\\n]*)?$")
      or (startswith("<command-") and contains("<command-name>/park</command-name>"))
      or test("^<skill>\\s*<name>park</name>")
' >/dev/null 2>&1 || [ "$ACTIVE_PARK" = "true" ]; then
    exit 0
fi

NEW_POST_PARK_WORK=0
if [ -f "$PARKED" ]; then
    PARKED_LINES=$(cat "$PARKED" 2>/dev/null)
    case "$PARKED_LINES" in ''|*[!0-9]*) ;; *)
        [ "$LEDGER_LINES" -ne "$PARKED_LINES" ] || exit 0
        # A prior session-log block is not a permanent suppression: a fresh
        # ledger delta resumes snapshots without waiting another token interval.
        NEW_POST_PARK_WORK=1
        rm -f "$PARKED"
        ;;
    esac
fi

LAST_PEAK=0; LAST_LINES=0; RETRY=0
if [ -f "$MARKER" ]; then
    read -r LAST_PEAK LAST_LINES < "$MARKER" 2>/dev/null || { LAST_PEAK=0; LAST_LINES=0; }
    case "${LAST_PEAK:-}${LAST_LINES:-}" in ''|*[!0-9]*) LAST_PEAK=0; LAST_LINES=0 ;; esac
    if [ ! -f "$DRAFT" ]; then
        # Marker without a draft = the last trigger was ignored, interrupted, or
        # its write failed. The marker records that a trigger FIRED, not that a
        # snapshot EXISTS, so treating it as success burns the slot until the
        # session both writes more AND grows another INTERVAL - which for a long
        # single-task stretch means never. Retry instead, gates bypassed.
        RETRY=1
    else
        # A refresh with no new writes would re-derive an unchanged draft: skip it.
        [ "$LEDGER_LINES" -gt "$LAST_LINES" ] 2>/dev/null || exit 0
    fi
fi
[ "$NEW_POST_PARK_WORK" -eq 0 ] || RETRY=1

# Peak context from the transcript tail. Context grows monotonically between
# compactions, so the tail carries the peak; reading 200 lines keeps this hook
# cheap enough to run on every prompt regardless of transcript size.
PEAK=$(tail -n 200 "$TRANSCRIPT" 2>/dev/null | jq -r '
    select(.message.usage != null)
    | (.message.usage.input_tokens // 0)
      + (.message.usage.cache_read_input_tokens // 0)
      + (.message.usage.cache_creation_input_tokens // 0)
  ' 2>/dev/null | sort -n | tail -1)
[ -n "${PEAK:-}" ] || exit 0
[ "$PEAK" -ge "$THRESHOLD" ] 2>/dev/null || exit 0
COMPACTED=0
if [ "$LAST_PEAK" -gt 0 ] 2>/dev/null && [ "$PEAK" -lt "$LAST_PEAK" ] 2>/dev/null; then
    # Compaction detected: peak fell below the recorded high-water mark. Bypass
    # the interval gate this round — the draft predates the compaction, so if the
    # ledger grew it should refresh now, and the fire path re-stamps the marker
    # with the post-compaction peak. Without this, refreshes stay suppressed until
    # peak exceeds the OLD peak plus the interval, which a compacted session may
    # never reach again. (No ledger growth exits earlier as usual — an unchanged
    # draft needs no refresh, however the peak moved.)
    COMPACTED=1
fi
if [ "$LAST_PEAK" -gt 0 ] && [ "$RETRY" -eq 0 ] && [ "$COMPACTED" -eq 0 ] 2>/dev/null; then
    [ "$((PEAK - LAST_PEAK))" -ge "$INTERVAL" ] 2>/dev/null || exit 0
fi

mkdir -p "$STATE_DIR" 2>/dev/null || exit 0
printf '%s %s\n' "$PEAK" "$LEDGER_LINES" > "$MARKER" 2>/dev/null || exit 0

if [ -f "$DRAFT" ]; then
    VERB="Update the existing shadow-park snapshot at"
    HOWTO="Patch it — read it, then extend or correct only what has changed since its
SNAPSHOT-LEDGER-LINES count ($LAST_LINES, now $LEDGER_LINES). Do not rewrite what still holds."
else
    VERB="write a shadow-park snapshot to"
    HOWTO="Write it in one pass."
fi

cat <<EOF
<parboil-trigger source="parboil-check.sh">
Context is at ~$((PEAK / 1000))k tokens (threshold $((THRESHOLD / 1000))k) and this session has
written files. Answer the user's message FIRST, then — at the end of the same turn — $VERB:

  $DRAFT

Ordering is deliberate: the snapshot must not sit between the user and their answer. It
also cannot be backgrounded — its whole value is reusing context only this turn holds, so
a sub-agent would have to reconstruct the session from its transcript, which is the cost
the snapshot exists to avoid.

If /park is already in progress when this trigger arrives, do not write or refresh the
shadow snapshot: the active park satisfies the trigger.

$HOWTO Work from context you already hold — do NOT re-read the session's files, re-run
greps, or despatch sub-agents for it. It is a cheap draft, not a park: if the session
moves on, /park patches or discards it.

Required format (first line exactly as shown — /park diffs against that count):

  SNAPSHOT-LEDGER-LINES: $LEDGER_LINES

That number is the hook's exact \`wc -l < "$LEDGER"\` result at trigger time. It is not
a count of bullets, files, or sections in the draft. If refreshing this draft
manually later, recompute that ledger line count at the refresh and replace the
header; never retain the old count beside a refreshed body.

  ## Draft session log
  ### Summary            — 2-4 sentences, outcomes and decisions
  ### Key Insights / Decisions
  ### Next Steps / Open Loops
  ### Files Created      — path - purpose
  ### Files Updated      — path - what changed and why
  ### Pickup Context     — **For next session:** one actionable sentence

  ## Draft identifier enumeration   (/park Step 6)
  — every value the session changed, as \`old → new\`, incl. status flips, renames
    with full old paths, and world-state changes with no file token. \`None\` if nil.

  ## Draft open loops               (/park Step 7)
  — one line each: \`item → target surface\`, per park's routing rules.

Mention the snapshot in one short line at most.
</parboil-trigger>
EOF
exit 0
