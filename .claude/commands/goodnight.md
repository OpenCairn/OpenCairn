---
name: goodnight
description: End-of-day status report - inventory loops, set tomorrow's queue, close cleanly
---

# Goodnight - End-of-Day Status Report

You are running the user's end-of-day operational close-out. This is a technical/PM-focused review - think engineering standup for yourself, not therapy session.

## Philosophy

The goal is clean handoff to tomorrow-you:
- **Inventory** - what's the state of everything?
- **Accountability** - what got done?
- **Queue** - what's the priority sequence for tomorrow?
- **Context** - what would tomorrow-you need to know to hit the ground running?

This is the complement to `/morning` - morning surfaces the landscape, goodnight closes the books.

## Instructions

### 0. Resolve Vault Path

Determine the vault base path. Run:

```bash
if [[ -z "${VAULT_PATH:-}" ]]; then
  echo "VAULT_PATH not set"; exit 1
elif [[ ! -d "$VAULT_PATH" ]]; then
  echo "VAULT_PATH=$VAULT_PATH not found"; exit 1
else
  echo "VAULT_PATH=$VAULT_PATH OK"
fi
```

If ERROR, abort - no vault accessible. (Do NOT silently fall back to `~/Files` without an active failover symlink - that copy may be stale.) **Use the resolved path for all file operations below.** Wherever this document references `$VAULT_PATH/`, substitute the resolved vault path.

### 1. Check current date/time

```bash
date +"%A, %d %b %Y"  # friendly display
date +"%Y-%m-%d"       # for file paths
date +"%I:%M%P" | tr '[:upper:]' '[:lower:]'  # for session timestamp
```

### 2. Gather Today's Activity (auto)

Read and compile:
- **Today.md:** Read `$VAULT_PATH/01 Now/Today.md` (if it exists) — today's planned timeline, "Done today" items, and any notes sections. This is the richest single source for what was planned vs what happened
- **Today's sessions:** Check `$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md` for today's date
- **Works in Progress:** Read `$VAULT_PATH/01 Now/Works in Progress.md` for project states
- **Completed tasks:** Extract from Today.md "Done today" section AND session summaries (deduplicate)
- **Candidate open loops:** Extract unchecked items (`- [ ]`) from session files, plus any timeline items from Today.md that weren't completed or moved to "Done today"

**Important:** Store this data in working memory - it's a DRAFT inventory, not ground truth.

### 3. Pre-Verification Debrief (BEFORE presenting report)

**This step happens BEFORE displaying any open loops.** The goal is to update your working model with reality before presenting outdated information.

Ask:
> "Before I show today's report, let me check: did you complete anything outside Claude today? Any tasks from earlier sessions that are now done?"

Wait for response.

**If the user provides completions:**
1. Update your working memory (mark those items as completed in your draft)
2. **Update session files immediately** (see Step 4)
3. Then proceed to Step 5 with the corrected data

**If the user says "no" or "nothing":** Proceed to Step 5 with original data.

### 4. Update Session Files for Completed Loops

When the user reports a loop is complete, update the source session file:

1. **Locate the specific session** containing the loop (you have this from Step 2)
2. **Use flock for safe editing:**
   ```bash
   flock -w 10 "$VAULT_PATH/06 Archive/Claude Sessions/.lock" -c "
     sed -i 's/^- \\[ \\] EXACT_LOOP_TEXT$/- [x] EXACT_LOOP_TEXT/' '$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md'
   "
   ```
3. **Confirm the update:** Display brief acknowledgement:
   ```
   ✓ Marked complete: "LOOP_TEXT" (in Session N)
   ```

**Why update immediately:** Prevents the same loop from appearing as open in future `/goodnight`, `/pickup`, or `/weekly-synthesis` runs.

### 5. Present Status Report

**Now** display the report using your corrected working memory:

```
## Today's Report - [Day, Date]

**Sessions:** N
**Projects touched:** [list]

### Completed
- [x] Task 1 (session)
- [x] Task 2 (session)
- [x] Task 3 (marked done just now)

### Open Loops (by project)
**[Project A]**
- [ ] Loop 1
- [ ] Loop 2

**[Project B]**
- [ ] Loop 1

**Unassigned**
- [ ] Orphan loop
```

**Note:** The "(marked done just now)" annotation helps the user see what was just reconciled vs what was already recorded.

### 6. Mid-Flow Corrections

**If the user corrects you during the report** ("actually that's done", "I finished that earlier"):

1. **Acknowledge immediately:** "Got it, marking that complete."
2. **Update session file** (same process as Step 4)
3. **Update your working memory** - do NOT re-read session files (you'll get stale data)
4. **Continue with corrected state** - don't re-display the whole report

**Critical:** Once the user tells you something is done, treat it as done for the rest of this session. Do not pull from files again.

### 7. Additional Captures (brief, optional)

Ask:
> "Anything else not captured? New blockers, decisions made, or items to add?"

- If yes: add to inventory (but don't add to session files - these go in the daily report)
- If no: proceed

### 8. Set Tomorrow's Queue

Ask:
> "What's the priority order for tomorrow?"

Help structure as:

```
### Tomorrow's Queue
1. **[Must-do]** - [why it's priority]
2. **[Should-do]** - [context]
3. **[If time]** - [nice to have]

**Blockers/Dependencies:**
- [Anything waiting on external input]
```

If the user doesn't have strong opinions, suggest based on:
- Time-sensitive items first
- Blocked items need unblocking
- High-momentum items worth continuing

### 9. Generate Daily Report

Create file at `$VAULT_PATH/06 Archive/Daily Reports/YYYY-MM-DD.md`:

```markdown
# Daily Report - [Day], [Date]

## Today's Plan

[Include the full Today.md timeline code block and Refs line here, verbatim from 01 Now/Today.md. If Today.md doesn't exist or has no date/stale date, omit this section.]

## Sessions
- Session 1: [Topic] - [outcome]
- Session 2: [Topic] - [outcome]

## Completed
- [x] Task 1
- [x] Task 2

## Open Loops

### [Project A]
- [ ] Loop 1
- [ ] Loop 2

### [Project B]
- [ ] Loop 1

### Unassigned
- [ ] Orphan loop

## Tomorrow's Queue
1. **[Priority 1]** - [why]
2. **[Priority 2]** - [context]
3. **[Priority 3]** - [if time]

## Blockers
- [Item] - waiting on [what]

## Notes
[Any context tomorrow-you needs]

---
*Links:*
- Sessions: [[06 Archive/Claude Sessions/YYYY-MM-DD]]
- Previous: [[06 Archive/Daily Reports/YYYY-MM-DD]] (yesterday if exists)
```

Ensure directory exists first:
```bash
mkdir -p "$VAULT_PATH/06 Archive/Daily Reports"
```

### 10. Log Goodnight Session with Bidirectional Links

Append a session entry for the goodnight session itself to today's session file.

### 11. Find Previous Session and Determine Next Session Number

1. Read today's session file to find the last session number
2. New session number = last + 1
3. Store previous session's heading for forward linking

### 12. Add Forward Link to Previous Session (with guards)

**GUARD 1 - Idempotency check:**
```bash
# Check if forward link already exists
if grep -q "\\*\\*Next session:\\*\\*.*#Session $NEW_NUM - Goodnight" "$SESSION_FILE"; then
  echo "Forward link already exists, skipping"
  # Skip insertion
fi
```

**GUARD 2 - Scoped insertion (find previous session's block):**

**CRITICAL: All line calculations MUST happen inside the flock** to prevent race conditions.

```bash
# Entire operation wrapped in single flock - calculate and insert atomically
flock -w 10 "$VAULT_PATH/06 Archive/Claude Sessions/.lock" bash -c '
  SESSION_FILE="'"$SESSION_FILE"'"
  PREV_NUM="'"$PREV_NUM"'"
  NEW_SESSION_LINK="'"$NEW_SESSION_LINK"'"

  # Find previous session heading line number
  PREV_HEADING=$(grep -n "^## Session $PREV_NUM - " "$SESSION_FILE" | tail -1 | cut -d: -f1)
  [ -z "$PREV_HEADING" ] && exit 1

  # Find next session heading (or EOF)
  NEXT_HEADING=$(tail -n +$((PREV_HEADING + 1)) "$SESSION_FILE" | grep -n "^## Session " | head -1 | cut -d: -f1)
  if [ -n "$NEXT_HEADING" ]; then
    END_LINE=$((PREV_HEADING + NEXT_HEADING - 1))
  else
    END_LINE=$(wc -l < "$SESSION_FILE")
  fi

  # Find insertion point (after last metadata line in previous session)
  INSERT_AFTER=$(sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | \
    grep -n "^\*\*\(Project\|Continues\|Previous session\):\*\*" | tail -1 | cut -d: -f1)

  # Fallback for Quick sessions (no metadata lines)
  if [ -z "$INSERT_AFTER" ]; then
    INSERT_AFTER=$(sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | \
      grep -n "." | tail -1 | cut -d: -f1)
  fi

  INSERT_LINE=$((PREV_HEADING + INSERT_AFTER - 1))

  # Insert
  sed -i "${INSERT_LINE}a\\${NEW_SESSION_LINK}" "$SESSION_FILE"
'
```

**Variable setup before flock:**
```bash
SESSION_FILE="$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md"
PREV_NUM=3  # Previous session number
NEW_SESSION_LINK="**Next session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session 4 - Goodnight: Topic]]"
```

**GUARD 3 - Post-insertion validation:**
After insertion, verify no duplicates were created. This runs outside the flock (read-only check):
```bash
# Fresh read to check for duplicates
PREV_HEADING=$(grep -n "^## Session $PREV_NUM - " "$SESSION_FILE" | tail -1 | cut -d: -f1)
NEXT_HEADING=$(tail -n +$((PREV_HEADING + 1)) "$SESSION_FILE" | grep -n "^## Session " | head -1 | cut -d: -f1)
if [ -n "$NEXT_HEADING" ]; then
  END_LINE=$((PREV_HEADING + NEXT_HEADING - 1))
else
  END_LINE=$(wc -l < "$SESSION_FILE")
fi
NEXT_COUNT=$(sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | grep -c "^\*\*Next session:\*\*")
if [ "$NEXT_COUNT" -gt 1 ]; then
  echo "⚠ WARNING: Previous session has $NEXT_COUNT 'Next session:' links - manual review needed"
fi
```

### 13. Append Goodnight Session Entry

Use flock for concurrent safety:

```bash
flock -w 10 "$VAULT_PATH/06 Archive/Claude Sessions/.lock" -c 'cat >> "$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md" << '\''EOF'\''

## Session N - Goodnight: [Brief Topic Summary] (HH:MMam/pm)

### Summary
[2-3 sentences covering what was reviewed/decided/updated during goodnight]

### Key Insights / Decisions
- [Any significant decisions made during close-out]

### Next Steps / Open Loops
- [ ] [Remaining items for tomorrow]

### Files Updated
- [List any files modified during goodnight]

### Pickup Context
**For next session:** [One sentence for tomorrow morning]
**Previous session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N-1 - Previous Title]]
EOF'
```

**Critical:** Always add the "Next session" link to the previous session BEFORE appending the new session. This maintains bidirectional linking.

### 14. Check for Stranded Work Product

Check whether any Claude-internal files were created or modified today that haven't been migrated to the vault:

```bash
find ~/.claude/plans/ -type f -newermt "$(date +%Y-%m-%d)" 2>/dev/null
```

If any files found:
1. Read each plan file
2. Identify the corresponding vault project doc
3. If vault doc is stale or missing the plan content, **migrate it now**
4. Display: `🔧 Migrated plan content to vault: [path]`

If none found: `✓ No stranded work product in ~/.claude/plans/`

**Why:** `~/.claude/plans/` doesn't sync, isn't visible in Obsidian, and effectively doesn't exist outside the session. Work product has been stranded there multiple times. End-of-day is the last safety net.

### 15. Update Works in Progress

If any project status changed significantly today, update `$VAULT_PATH/01 Now/Works in Progress.md` with current state.

### 16. Close

```
✓ Report saved: 06 Archive/Daily Reports/YYYY-MM-DD.md
✓ Session logged: 06 Archive/Claude Sessions/YYYY-MM-DD.md (Session N)
✓ Open loops: N items across M projects
✓ Tomorrow's #1: [Priority item]

Goodnight.
```

## Guidelines

- **Technical, not emotional:** Focus on state and status, not feelings
- **Accountability:** The completed list matters - own what got done
- **Forward-looking:** Tomorrow's queue is the point - set yourself up
- **Quick:** This should take 3-5 minutes unless there's a lot to capture
- **No guilt:** If it was a low-output day, just note the status honestly
- **Always resolve vault path first:** Step 0 determines whether to use NAS mount or local fallback. If neither is accessible, abort rather than silently fail.
- **File locking is mandatory:** Use `flock` via Bash for session file writes. Lock file: `$VAULT_PATH/06 Archive/Claude Sessions/.lock`
- **Scoped forward linking:** When adding "Next session:" links, always scope to specific session block. Never use global patterns that match all sessions.

### Working Memory Model (Critical)

**Session files are inputs, not ground truth.** Once you read them in Step 2, work from your working memory for the rest of the command. This prevents the bug where:
1. the user says "that's done"
2. You acknowledge it
3. You re-read the session file (which still shows it open)
4. You present it as open again

**The flow:**
1. Read session files once (Step 2) - populate working memory
2. Ask about completions BEFORE presenting (Step 3) - update working memory AND files
3. Present from working memory (Step 5) - never re-read files mid-flow
4. Handle mid-flow corrections (Step 6) - update working memory AND files
5. Generate daily report from working memory (Step 9)

**Session file updates are write-only after initial read.** You update them when the user marks something done (so future runs see correct state), but you don't re-read them within this session.

**Tomorrow's queue must respect working memory.** When generating tomorrow's queue (Step 8), cross-check every suggested item against corrections applied in Steps 3-6. Items marked complete during this session MUST NOT reappear as suggestions. This includes "if time" items and hedged suggestions like "or already done?" — if you know it's done, don't mention it.

## Triggers

This command should trigger when the user says:
- "goodnight"
- "end of day"
- "close out"
- "wrap up the day"
- "done for the day"

## Integration

- **Reads from:** Today.md, Claude Sessions (today), Works in Progress
- **Creates:** Daily Reports
- **Updates:** Claude Sessions (marks loops complete, adds goodnight session with bidirectional links), Works in Progress (if needed)
- **Complements:** `/morning` (start of day), `/park` (end of session), `/regroup` (mid-day)
- **Replaces:** `/daily-review` (deprecated)
