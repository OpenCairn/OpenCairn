---
name: goodnight
description: End-of-day status report - inventory loops, set tomorrow's queue, close cleanly
---

# Goodnight - End-of-Day Status Report

You are running Harrison's end-of-day operational close-out. This is a technical/PM-focused review - think engineering standup for yourself, not therapy session.

## Philosophy

The goal is clean handoff to tomorrow-you:
- **Inventory** - what's the state of everything?
- **Accountability** - what got done?
- **Queue** - what's the priority sequence for tomorrow?
- **Context** - what would tomorrow-you need to know to hit the ground running?

This is the complement to `/morning` - morning surfaces the landscape, goodnight closes the books.

## Instructions

### 1. Check current date/time

```bash
date +"%A, %d %b %Y"  # friendly display
date +"%Y-%m-%d"       # for file paths
```

### 2. Gather Today's Activity (auto)

Read and compile:
- **Today's sessions:** Check `/mnt/nas/Files/06 Archive/Claude Sessions/YYYY-MM-DD.md` for today's date
- **Works in Progress:** Read `/mnt/nas/Files/01 Now/Works in Progress.md` for project states
- **Completed tasks:** Extract from session summaries
- **Candidate open loops:** Extract all unchecked items (`- [ ]`) from session files

**Important:** Store this data in working memory - it's a DRAFT inventory, not ground truth.

### 3. Pre-Verification Debrief (BEFORE presenting report)

**This step happens BEFORE displaying any open loops.** The goal is to update your working model with reality before presenting outdated information.

Ask:
> "Before I show today's report, let me check: did you complete anything outside Claude today? Any tasks from earlier sessions that are now done?"

Wait for response.

**If Harrison provides completions:**
1. Update your working memory (mark those items as completed in your draft)
2. **Update session files immediately** (see Step 3a)
3. Then proceed to Step 4 with the corrected data

**If Harrison says "no" or "nothing":** Proceed to Step 4 with original data.

### 3a. Update Session Files for Completed Loops

When Harrison reports a loop is complete, update the source session file:

1. **Locate the specific session** containing the loop (you have this from Step 2)
2. **Use flock for safe editing:**
   ```bash
   flock -w 10 "/mnt/nas/Files/06 Archive/Claude Sessions/.lock" -c "
     sed -i 's/^- \\[ \\] EXACT_LOOP_TEXT$/- [x] EXACT_LOOP_TEXT/' '/mnt/nas/Files/06 Archive/Claude Sessions/YYYY-MM-DD.md'
   "
   ```
3. **Confirm the update:** Display brief acknowledgement:
   ```
   ✓ Marked complete: "LOOP_TEXT" (in Session N)
   ```

**Why update immediately:** Prevents the same loop from appearing as open in future `/goodnight`, `/pickup`, or `/weekly-synthesis` runs.

### 4. Present Status Report

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

**Note:** The "(marked done just now)" annotation helps Harrison see what was just reconciled vs what was already recorded.

### 4a. Mid-Flow Corrections

**If Harrison corrects you during the report** ("actually that's done", "I finished that earlier"):

1. **Acknowledge immediately:** "Got it, marking that complete."
2. **Update session file** (same process as Step 3a)
3. **Update your working memory** - do NOT re-read session files (you'll get stale data)
4. **Continue with corrected state** - don't re-display the whole report

**Critical:** Once Harrison tells you something is done, treat it as done for the rest of this session. Do not pull from files again.

### 4b. Additional Captures (brief, optional)

Ask:
> "Anything else not captured? New blockers, decisions made, or items to add?"

- If yes: add to inventory (but don't add to session files - these go in the daily report)
- If no: proceed

### 5. Set Tomorrow's Queue

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

If Harrison doesn't have strong opinions, suggest based on:
- Time-sensitive items first
- Blocked items need unblocking
- High-momentum items worth continuing

### 6. Generate Daily Report

Create file at `/mnt/nas/Files/06 Archive/Daily Reports/YYYY-MM-DD.md`:

```markdown
# Daily Report - [Day], [Date]

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
mkdir -p "/mnt/nas/Files/06 Archive/Daily Reports"
```

### 7. Update Works in Progress

If any project status changed significantly today, update `/mnt/nas/Files/01 Now/Works in Progress.md` with current state.

### 8. Close

```
✓ Report saved: 06 Archive/Daily Reports/YYYY-MM-DD.md
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

### Working Memory Model (Critical)

**Session files are inputs, not ground truth.** Once you read them in Step 2, work from your working memory for the rest of the command. This prevents the bug where:
1. Harrison says "that's done"
2. You acknowledge it
3. You re-read the session file (which still shows it open)
4. You present it as open again

**The flow:**
1. Read session files once (Step 2) - populate working memory
2. Ask about completions BEFORE presenting (Step 3) - update working memory AND files
3. Present from working memory (Step 4) - never re-read files mid-flow
4. Handle mid-flow corrections (Step 4a) - update working memory AND files
5. Generate daily report from working memory (Step 6)

**Session file updates are write-only after initial read.** You update them when Harrison marks something done (so future runs see correct state), but you don't re-read them within this session.

## Triggers

This command should trigger when Harrison says:
- "goodnight"
- "end of day"
- "close out"
- "wrap up the day"
- "done for the day"

## Integration

- **Reads from:** Claude Sessions (today), Works in Progress
- **Creates:** Daily Reports
- **Updates:** Claude Sessions (marks loops complete), Works in Progress (if needed)
- **Complements:** `/morning` (start of day), `/park` (end of session), `/regroup` (mid-day)
- **Replaces:** `/daily-review` (deprecated)
