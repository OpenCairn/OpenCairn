---
name: pickup
aliases: [resume, restore]
description: Interactive menu to pickup recent sessions with full context - the "pickup" in park and pickup
parameters:
  - "--days=N" - Show sessions from last N days (default: 9, max: 90)
  - "--project=NAME" - Filter to sessions related to specific project
  - "--with-loops" - Show only sessions with open loops
  - "--hibernate=DATE" - Load hibernate snapshot instead of session (redirects to /awaken)
  - "--all" - Show all sessions without pagination (use cautiously)
---

# Pickup - Session Pickup

You are helping the user pickup a previous work session with full context.

## Instructions

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current timestamp: `date +"%s"` (Unix timestamp for age calculations)
   - Use these to calculate how long ago each session was

2. **Parse parameters and scan for sessions:**
   - Check for parameters: `--days=N`, `--project=NAME`, `--with-loops`, `--hibernate=DATE`, `--all`
   - If `--hibernate` specified: Redirect to `/awaken --date=DATE` and stop
   - Determine lookback window:
     - Default: 9 days (reliably covers weekend-to-weekend)
     - Extended after break: If no sessions in last 9 days, automatically extend to 30 days
     - Explicit: Use `--days=N` value (max 90 days)
   - Read session files from `06 Archive/Claude Sessions/` for the determined window
   - Scan both main directory and year subdirectories (e.g., `2024/`, `2025/`)
   - Archive organization is transparent to pickup (finds sessions regardless of location)
   - Extract session metadata from each file:
     - Session number and title
     - Date and time
     - One-sentence summary or "Pickup Context"
     - **Open loops with timestamps:**
       - Count unchecked items (`- [ ]`)
       - Calculate age of each loop (days since session date)
       - Flag stale loops: 7+ days = ⚠️, 30+ days = 🔴
     - Related project (if linked)
     - Calculate session age: "2 hours ago", "yesterday", "3 days ago" using current time from step 1
   - Apply filters:
     - If `--project=NAME`: Keep only sessions linking to that project
     - If `--with-loops`: Keep only sessions with unchecked open loops

2a. **Check Works in Progress staleness:**
   - Read `01 Now/Works in Progress.md`
   - Extract "Last updated" timestamp from top of file
   - Calculate days since last update
   - If > 9 days old, prepare staleness warning to display with menu
   - If > 30 days old, prepare critical staleness warning

3. **Display interactive menu** (with pagination if needed):
   - **Pagination threshold:** Show first 15 sessions by default
   - If more than 15 sessions, display page 1 with navigation options
   - Group by day for better readability when 20+ sessions
   - **If Works in Progress is stale (9+ days):** Display warning banner before menu

**WIP staleness warning (if 9-29 days old):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Works in Progress may be stale
Last updated: N days ago

Your active projects list may not reflect current reality.
Consider reviewing and updating after pickup.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**WIP critical staleness warning (if 30+ days old):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 Works in Progress is STALE (N days old)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Projects list is likely out of date. Many listed projects may be
completed, abandoned, or deprioritized.

After pickup, consider:
- Running /awaken if returning from extended break
- Manually reviewing and updating Works in Progress
- Archiving completed projects
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Standard menu (< 15 sessions):**
```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Recent Sessions (Last 9 Days)           ║
╠════════════════════════════════════════════════════════════╣
║  1. Claude Code Learning - Sat 17 Jan 9:40am              ║
║     "Component analysis, template creation for a friend"      ║
║     Open loops: 3 | Last: 2 hours ago                     ║
║                                                            ║
║  2. Tab Management - Thu 16 Jan 7:23pm                    ║
║     "Limbic economy framework, multi-agent therapy"        ║
║     Open loops: 5 ⚠️ | Last: 9 days ago (STALE)           ║
║                                                            ║
║  3. Philosophy Work - Mon 23 Dec 11:15am                   ║
║     "Golden red team calibration exercise"                 ║
║     Open loops: 2 🔴 | Last: 25 days ago (AGED)            ║
║                                                            ║
║  [Enter number to pickup, 'n' for new session, 'q' to quit]║
║  Note: ⚠️ = 7+ days old, 🔴 = 30+ days old                 ║
╚════════════════════════════════════════════════════════════╝

>
```

**Paginated menu (15-30 sessions):**
```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Page 1 of 2 (25 total sessions)         ║
╠════════════════════════════════════════════════════════════╣
║  Sat 17 Jan (5 sessions)                                   ║
║  1. Claude Code Learning            9:40am  | Loops: 3     ║
║  2. Zac Boyce Meeting              12:19pm  | Loops: 2     ║
║  3. Private Practice Transition    12:26pm  | Loops: 3     ║
║                                                            ║
║  Fri 16 Jan (7 sessions)                                   ║
║  4. Hierarchical Navigation         3:40pm  | Loops: 0     ║
║  5. Blog Consolidation              2:15pm  | Loops: 1     ║
║  ...                                                       ║
║                                                            ║
║  [Number to pickup, 'm' more, 'f' filter, 'n' new, 'q' quit]║
╚════════════════════════════════════════════════════════════╝

>
```

**Grouped menu (30+ sessions):**
```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - 47 sessions in last 9 days              ║
║  Showing: 15 most recent                                   ║
╠════════════════════════════════════════════════════════════╣
║  Today (12 sessions)                                   [+] ║
║  Yesterday (15 sessions)                               [-] ║
║    1. Session A                     3:40pm  | Loops: 2     ║
║    2. Session B                     2:15pm  | Loops: 0     ║
║  ...                                                       ║
║                                                            ║
║  Options:                                                  ║
║    m - Show more sessions                                  ║
║    f - Filter (--project, --with-loops)                    ║
║    s - Search by keyword                                   ║
║                                                            ║
║  [Enter command or session number]                         ║
╚════════════════════════════════════════════════════════════╝

>
```

4. **Wait for user selection** (or if no input needed, continue automatically):
   - If specific session number provided (1-99): Load that session
   - If 'n' or no sessions found: Acknowledge, start fresh conversation
   - If 'q': Exit gracefully
   - If 'm' (more): Show next page of sessions
   - If 'f' (filter): Prompt for filter criteria and re-display filtered results
   - If 's' (search): Prompt for keyword and show matching sessions
   - If 'a' (all): Disable pagination, show all sessions (use cautiously)

5. **Load selected session context:**
   - Read the full session summary
   - Extract key information:
     - Session date and number (for continuation tracking)
     - What was accomplished
     - Open loops (unchecked items)
     - Files that were created/updated
     - Resume context (where to pick up)
     - Related project
   - **Store continuation context in conversation:**
     - Remember: "This session continues [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]"
     - This will be used by `/park` to create bidirectional continuation links

6. **Display session context:**

```
Loading: [Session Title] ([Date/Time])

Last session summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[2-3 sentence summary of what was accomplished]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open loops (N days old):
 [ ] First unchecked item
 [ ] Second unchecked item ⚠️ (Still open after 9 days)
 [ ] Third unchecked item 🔴 (Still open after 32 days - consider completing or dropping)

Key insights from last session:
 • Important realisation 1
 • Important realisation 2

Project: [[03 Projects/Project Name]] (if applicable)
Files updated: /path/to/file.md, /path/to/other.md

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  STALE LOOPS DETECTED
This session has loops that have been open for 9+ days.
Consider: Complete, delegate, or explicitly drop these items.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ready to continue. What's next?
```

7. **Auto-load relevant context files:**
   - Always load: `~/CLAUDE.md`
   - If project linked: Read the project hub file
   - Display what was loaded:
     ```
     Auto-loaded context:
      ✓ CLAUDE.md
      ✓ 03 Projects/[Project Name].md
      ✓ 07 System/Context - [Related Domain].md
     ```

8. **Prompt for next action:**
   - Present the most logical next step based on "Resume Context"
   - Ask: "Ready to continue. What's next?" or "Should I proceed with [suggested next action]?"

## Guidelines

- **Always check current date/time:** First step - run `date` command for accurate age calculations. Never assume time.
- **Auto-extend window after breaks:** If no sessions in last 9 days, automatically extend to 30 days and notify user
- **No sessions found:** If no sessions in extended window, suggest `/awaken` or starting fresh
- **Session ordering:** Display most recent first (reverse chronological)
- **Age display:** Show relative time ("2 hours ago", "yesterday", "3 days ago") using current time from step 1
- **Open loop counting:** Only count unchecked items (`- [ ]`), ignore completed ones (`- [x]`)
- **Open loop age tracking:**
  - Calculate days since session date for all unchecked loops
  - Flag stale (9-29 days): ⚠️ warning in menu
  - Flag aged (30+ days): 🔴 critical in menu + prominent warning on load
  - Purpose: Surface loops that may need completion or explicit dropping
- **Stale loop warnings:** Display only when loading sessions with 9+ day old loops
- **Loop age philosophy:** Long-open loops often indicate either low priority (should drop) or high friction (needs decomposition)
- **Context loading:** Be intelligent about which context files to load based on project and domain
- **Date formatting:** Use natural language ("Sat 17 Jan 9:40am" not "2026-01-17 09:40")
- **Menu width:** Keep menu width at 64 characters for terminal readability
- **Pagination threshold:** 15 sessions per page (prevents menu overflow)
- **Grouping threshold:** Group by day when 20+ sessions for better navigation
- **Filter preservation:** Once filter applied, maintain it until user clears or changes
- **Hibernate detection:** If user returning after month+ gap with no sessions, suggest `/awaken`
- **WIP staleness monitoring:** Always check Works in Progress timestamp and warn if 9+ days old
- **Critical staleness (30+ days):** Strong warning that projects list is likely outdated, suggest /awaken or manual review

## Integration with Claude Code

This command enables:
1. Zero-friction pickup (no mental "where was I?")
2. Explicit open loops displayed upfront
3. Auto-loading of relevant context (no need to manually re-read files)
4. Confidence in session continuity

Combined with `/park`, this creates the bulletproof **park and pickup system**.
