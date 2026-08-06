#!/usr/bin/env bash
# parboil-check.sh - UserPromptSubmit hook: fire a mid-session shadow park once
# the session's context has grown expensive.
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
command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
SID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
[ -n "$SID" ] || exit 0
TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null) || exit 0
[ -f "$TRANSCRIPT" ] || exit 0

MARKER="$STATE_DIR/$SID.parboil.state"   # "<peak-at-last-fire> <ledger-lines-at-last-fire>"
DRAFT="$STATE_DIR/$SID.parboil.md"
LEDGER="$STATE_DIR/$SID.tsv"

# Nothing written this session -> nothing worth pre-parking.
[ -f "$LEDGER" ] || exit 0
LEDGER_LINES=$(wc -l < "$LEDGER" 2>/dev/null || echo 0)
[ "$LEDGER_LINES" -ge 3 ] 2>/dev/null || exit 0

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
if [ "$LAST_PEAK" -gt 0 ] && [ "$RETRY" -eq 0 ] 2>/dev/null; then
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

$HOWTO Work from context you already hold — do NOT re-read the session's files, re-run
greps, or despatch sub-agents for it. It is a cheap draft, not a park: if the session
moves on, /park patches or discards it.

Required format (first line exactly as shown — /park diffs against that count):

  SNAPSHOT-LEDGER-LINES: $LEDGER_LINES

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
