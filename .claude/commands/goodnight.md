---
name: goodnight
description: End-of-day close-out - accountability, route undone items, daily report
---

# Goodnight - End-of-Day Status Report

You are running the user's end-of-day operational close-out. This is a technical/PM-focused review - think engineering standup for yourself, not therapy session.

## Philosophy

The goal is clean handoff to tomorrow-you:
- **Inventory** - what's the state of everything?
- **Accountability** - what got done?
- **Context** - what would tomorrow-you need to know to hit the ground running?

This is the complement to `/morning` - morning surfaces the landscape, goodnight closes the books.

## Instructions

### 0. Resolve Vault Path

Determine the vault base path. Run:

```bash
if [[ -z "${VAULT_PATH:-}" ]]; then
  echo "VAULT_PATH not set"; exit 1
elif [[ ! -d "{VAULT}" ]]; then
  echo "VAULT_PATH={VAULT} not found"; exit 1
else
  echo "VAULT_PATH={VAULT} OK"
fi
```

If ERROR, abort - no vault accessible. (Do NOT silently fall back to `~/Files` without an active failover symlink - that copy may be stale.) **Use the resolved path for all file operations below.** Wherever this document references `{VAULT}/`, substitute the resolved vault path.

### 1. Check current date/time

```bash
date +"%A, %d %b %Y — %H:%M %Z"  # friendly display with time and timezone
date +"%Y-%m-%d"                   # for file paths and session timestamp
```

### 2. Gather Today's Activity (auto)

Read and compile:
- **This Week.md:** Read `{VAULT}/01 Now/This Week.md` (if it exists and today falls within the date range) — find today's day section. Checked items (`[x]`) are completed, unchecked (`[ ]`) are open. This is the richest single source for what was planned vs what happened
- **Today's sessions:** Check `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md` for today's date
- **Works in Progress:** Read `{VAULT}/01 Now/Works in Progress.md` for project states
- **Session outcomes:** Note what each session accomplished (for the Sessions list)
- **Candidate open loops:** Extract unchecked items (`- [ ]`) from today's day section in This Week.md, plus due items from Tickler.md. Session files are historical records — open loops were routed to SSOT at park time

**Important:** Store this data in working memory - it's a DRAFT inventory, not ground truth.

### 3. Pre-Verification Debrief (BEFORE presenting report)

**This step happens BEFORE presenting the status report.** The goal is to update your working model with reality before presenting outdated information.

Ask:
> "Before I show today's report, let me check: did you complete anything outside Claude today? Any tasks from earlier sessions that are now done?"

Wait for response.

**If the user provides completions:**
1. Update your working memory (mark those items as completed in your draft)
2. **Update SSOT files immediately** (see Step 4) — This Week.md, Tickler, project files
3. Then proceed to Step 5 with the corrected data

**If the user says "no" or "nothing":** Proceed to Step 5 with original data.

### 4. Update SSOT Files for Completed Loops

When the user reports a loop is complete, update the SSOT files (not session docs — those are historical records with plain bullets):

1. **Update This Week.md:** If This Week.md is current and the completed item appears as unchecked in today's day section, mark it `[x]`. Use the Edit tool.
2. **Update Tickler.md:** If the completed item appears in Tickler, delete the line.
3. **Update project file:** If the item is scoped to a project, mark it complete in the project file.
4. **Confirm the update:** Display brief acknowledgement:
   ```
   ✓ Marked complete: "LOOP_TEXT" (in This Week.md / Tickler / Project)
   ```

**Why update immediately:** Prevents the same loop from appearing as open in future `/morning`, `/goodnight`, `/pickup`, or `/weekly-review` runs.

### 5. Present Status Report

**Now** display the report using your corrected working memory:

```
## Today's Report — [Day], [DD] [Mon] [YYYY] — [HH:MM TZ]

**Projects touched:** [list]
**Sessions:** [count]

### Sessions
1. [Topic] — [outcome]
2. [Topic] — [outcome]
...

### Blockers
- [Item] — waiting on [what]
```

### 6. Mid-Flow Corrections

**If the user corrects you during the report** ("actually that's done", "I finished that earlier"):

1. **Acknowledge immediately:** "Got it, marking that complete."
2. **Update SSOT files** (same process as Step 4) — This Week.md, Tickler, project files
3. **Update your working memory** - do NOT re-read session files (you'll get stale data)
4. **Continue with corrected state** - don't re-display the whole report

**Critical:** Once the user tells you something is done, treat it as done for the rest of this session. Do not pull from files again.

### 7. Additional Captures (brief, optional)

Ask:
> "Anything else not captured? New blockers, decisions made, or items to add?"

- If yes: add to inventory (but don't add to session files - these go in the daily report)
- If no: proceed

### 8. Generate Daily Report

Create file at `{VAULT}/06 Archive/Claude/Daily Reports/YYYY-MM-DD.md`:

```markdown
# Daily Report - [Day], [Date]

## Today's Plan

[Include today's day section from This Week.md here (the `## [Day] [DD] [Mon]` heading and all items under it). Convert any `- [ ]` to plain `- ` bullets and any `- [x]` to `- ✓` — the daily report is an archival record, not a task SSOT. Checkboxes live in This Week.md, project files, and Tickler only. If This Week.md doesn't exist or today falls outside the date range, omit this section.]

## Sessions
1. [Topic] — [outcome]
2. [Topic] — [outcome]

## Blockers
- [Item] — waiting on [what]

---
*Links:*
- Sessions: [[06 Archive/Claude/Session Logs/YYYY-MM-DD]]
- Previous: [[06 Archive/Claude/Daily Reports/YYYY-MM-DD]] (yesterday if exists)
```

Ensure directory exists first:
```bash
mkdir -p "{VAULT}/06 Archive/Claude/Daily Reports"
```

### 9. Route undone items from past day sections

Before collapsing, scan today's section — and any earlier days that are still verbose — for `- [ ]` items. For each:
- **Has a natural future day?** → Move to that day's section.
- **Priority item that should happen tomorrow?** → Move to tomorrow's section in the appropriate time block.
- **Low priority / no deadline?** → Move to the Backlog section at the top of This Week.md.
- **Already appears in a future day?** → Delete the duplicate from today, don't move.

Preserve existing project/area links when moving items. If an item lacks a link, add one (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`, or `→ [[01 Now/Works in Progress#Heading]]`). No link for items with no project context.

Also check for sub-sections scoped to a future day. Move the entire sub-section to the appropriate future day before collapsing.

### 10. Collapse past day sections

After all undone items have been routed, collapse today's section — and any earlier days in This Week.md that are still verbose — to a one-line summary + link:

```markdown
## [emoji] [Day] [Date] — [Theme] ✅
[One sentence: what happened, what didn't, key outcome.] [[06 Archive/Claude/Daily Reports/YYYY-MM-DD|Full report]]
```

Sweep all past days, not just today. Earlier days may still be verbose if a previous `/goodnight` run predates this step or was interrupted. Any day before tomorrow should be a one-liner.

Nothing with `- [ ]` should remain in any collapsed section. If it does, something was missed in step 9 — route it before collapsing.

### 11. Maintain rolling 7-day horizon

Ensure This Week.md has day sections through at least `date -d "+7 days" +"%Y-%m-%d"` (i.e. today + 7 calendar days). Count existing future day headings (`## [emoji] [Day] [DD] [Mon]` or `## [Day] [DD] [Mon]`). For any missing days:

1. Run `date -d "+N days" +"%A %d %b"` for each missing day to get correct day-date mappings
2. Add new day sections after the last existing day, before the `---` / Refs / Pending decisions sections
3. **Populate from Tickler:** For each new day, convert to YYYY-MM-DD format and check Tickler.md for a matching `## YYYY-MM-DD` date header. Move any unchecked items from that Tickler section into the new day section and delete them from Tickler (This Week.md becomes SSOT per Tickler transfer rules). **Deduplicate against Backlog:** After migrating each Tickler item, check whether a matching item already exists in the Backlog section of This Week.md (same task, possibly different phrasing). If so, delete the Backlog copy — the day section is now SSOT.
4. Format for days with no Tickler items: `## [Day] [DD] [Mon]` with no content (just the heading)
5. **Update the file heading** date range to match the new end date: `# This Week — [start] – [new end] [YYYY]`

This prevents the file from shrinking as days get collapsed. The window always extends 7 days ahead.

### 12. Log Goodnight Session

Append a session entry for the goodnight session itself to today's session file.

### 13. Determine Next Session Number

Extract the last session number mechanically — do NOT count by reading:
```bash
PREV_NUM=$(grep -o "^## Session [0-9]*" "$SESSION_FILE" | tail -1 | grep -o "[0-9]*")
NEW_NUM=$((PREV_NUM + 1))
echo "New session number: $NEW_NUM"
```

**Concurrent session reconciliation:** Compare PREV_NUM against the last session number you saw during Step 2. If PREV_NUM is higher, one or more sessions were added by concurrent Claude instances between your initial read and now. For each missed session:
1. Read its summary and completions from the session file
2. Update your working memory (adjust session count, note outcomes)
3. **Patch the daily report** (Step 9 output already on disk) — add the missed session(s) to the Sessions list

This is the only exception to the "write-only after initial read" rule — you must re-read the session file here to discover what was missed, but only the specific new session blocks, not the whole file.

### 14. Append Goodnight Session Entry

**Do NOT use heredoc inside flock — nested quoting is fragile.** Instead, use the Write or Edit tool to append the session entry directly, or write to a temp file and use flock for the append:

```bash
# Write session entry to temp file first (no quoting issues)
cat > /tmp/goodnight_session.md << 'EOF'


## Session N - Goodnight: [Brief Topic Summary] (HH:MMam/pm)

### Summary
[2-3 sentences covering what was reviewed/decided/updated during goodnight]

### Key Insights / Decisions
- [Any significant decisions made during close-out]

### Next Steps / Open Loops
- [Remaining items for tomorrow]

### Files Updated
- [List any files modified during goodnight]

### Pickup Context
**For next session:** [One sentence for tomorrow morning]
EOF

# Append atomically under lock
flock -w 10 "{VAULT}/06 Archive/Claude/Session Logs/.lock" bash -c \
  'cat /tmp/goodnight_session.md >> "'"$SESSION_FILE"'"'
rm -f /tmp/goodnight_session.md
```

**Preferred method:** Use the Edit/Write tool to append (no shell quoting issues at all). Only use bash+flock if concurrent writes are a real risk (multiple Claude instances).

### 15. Check for Stranded Work Product

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

### 16. Update Works in Progress

If any project status changed significantly today, update `{VAULT}/01 Now/Works in Progress.md` with current state.

### 17. Close

```
✓ Report saved: 06 Archive/Claude/Daily Reports/YYYY-MM-DD.md
✓ Session logged: 06 Archive/Claude/Session Logs/YYYY-MM-DD.md (Session N)
Goodnight.
```

## Guidelines

- **Technical, not emotional:** Focus on state and status, not feelings
- **Accountability:** Each session line should clearly state what was accomplished — the Sessions list is the record of what got done
- **Quick:** This should take 3-5 minutes unless there's a lot to capture
- **No guilt:** If it was a low-output day, just note the status honestly
- **Always resolve vault path first:** Step 0 determines whether to use NAS mount or local fallback. If neither is accessible, abort rather than silently fail.
- **File locking is mandatory:** Use `flock` via Bash for session file writes. Lock file: `{VAULT}/06 Archive/Claude/Session Logs/.lock`

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
5. Generate daily report from working memory (Step 8)

**Session file updates are write-only after initial read.** You update them when the user marks something done (so future runs see correct state), but you don't re-read them within this session.

## Triggers

This command should trigger when the user says:
- "goodnight"
- "end of day"
- "close out"
- "wrap up the day"
- "done for the day"

## Integration

- **Reads from:** This Week.md, Claude Sessions (today), Works in Progress
- **Creates:** Daily Reports
- **Updates:** Claude Sessions (adds goodnight session), This Week.md (marks completed items `[x]`, collapses today's section, rolls undone items to future days/backlog), Tickler.md (deletes completed items), Project files (marks complete), Works in Progress (if needed)
- **Complements:** `/morning` (start of day), `/park` (end of session), `/regroup` (mid-day)
- **Replaces:** `/daily-review` (deprecated)

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
