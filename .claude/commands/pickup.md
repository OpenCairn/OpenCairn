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

3. **Group sessions by project:**
   - Extract `**Project:**` link from each session (if present)
   - Group sessions sharing the same project link
   - Sessions without project links remain standalone
   - For each project group, calculate:
     - Total session count
     - Most recent session (for display)
     - Aggregate open loops (sum across all sessions)
     - Time since last activity (from most recent session)
   - Sort project groups by most recent activity (not alphabetically)

4. **Display interactive menu** (project-grouped by default):
   - **Default view:** By Project (clusters related sessions)
   - **Alternative view:** Flat/chronological (traditional, accessed via 'v')
   - **Pagination threshold:** Show first 15 entries by default
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

**Default menu (project-grouped):**
```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Last 9 Days (By Project)                ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Home Renovation                            (8 sessions)║
║     Latest: Kitchen cabinets research      Today 7:10am   ║
║     Open loops: 11 total | Last: 0 hours ago               ║
║                                                            ║
║  2. Side Project - App                         (5 sessions)║
║     Latest: Auth flow implementation       Sat 1:49pm     ║
║     Open loops: 7 total | Last: 17 hours ago               ║
║                                                            ║
║  3. Tax Preparation                               [C] (1)  ║
║     Today 6:55am | Completed                               ║
║                                                            ║
║  4. Journal Setup                                 [C] (1)  ║
║     Today 6:21am | Completed                               ║
║                                                            ║
║  [1-9] select project, [v] flat view, [n] new session      ║
║  Note: ⚠️ = 7+ days stale, 🔴 = 30+ days aged              ║
╚════════════════════════════════════════════════════════════╝

>
```

**Expanded project view (after 'e1'):**
```
╔════════════════════════════════════════════════════════════╗
║  Home Renovation (8 sessions)                             ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Kitchen cabinets research         Today 7:10am        ║
║     "Compared IKEA vs custom, got quotes"                  ║
║     Open loops: 2                                          ║
║                                                            ║
║  2. Contractor calls                  Sat 9:16pm          ║
║     "Called 3 contractors, scheduled walkthroughs"         ║
║     Open loops: 5                                          ║
║                                                            ║
║  3. Permit research                   Sat 8:17pm     [C]  ║
║     "Confirmed no permit needed for cabinets"              ║
║                                                            ║
║  ... (5 more sessions)                                     ║
║                                                            ║
║  [1-9] pickup session, [b] back to projects, [a] show all  ║
╚════════════════════════════════════════════════════════════╝

>
```

**Flat view (after 'v' - traditional chronological):**
```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Last 9 Days (Chronological)             ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Today - Sun 18 Jan                                        ║
║  1. Kitchen cabinets research         7:10am  | Loops: 2  ║
║  2. Tax Preparation                   6:55am  | [C]       ║
║  3. Journal Setup                     6:21am  | [C]       ║
║                                                            ║
║  Yesterday - Sat 17 Jan                                    ║
║  4. Contractor calls                  9:16pm  | Loops: 5  ║
║  5. Permit research                   8:17pm  | [C]       ║
║  ...                                                       ║
║                                                            ║
║  [1-9] pickup, [p] project view, [m] more, [n] new        ║
╚════════════════════════════════════════════════════════════╝

>
```

5. **Wait for user selection** (or if no input needed, continue automatically):
   - **Number (1-99):** Select that project/session
     - In project view: Expands to show all sessions in that project (never auto-loads)
     - In expanded/flat view: Loads that specific session
   - **'v':** Switch to flat/chronological view
   - **'p':** Switch back to project-grouped view (from flat view)
   - **'b':** Back to project list (from expanded view)
   - **'a':** Show all sessions in current project (from expanded view)
   - **'n':** Start fresh conversation (or if no sessions found)
   - **'q':** Exit gracefully
   - **'m':** Show next page (when paginated)
   - **'f':** Prompt for filter criteria and re-display
   - **'s':** Prompt for keyword and show matching sessions

6. **Load selected session context:**
   - **If project selected (from project view):**
     - Expand to show all sessions in that project (see expanded view format above)
     - User then selects specific session to load
     - Do NOT auto-load most recent - always let user choose
   - **If specific session selected (from expanded/flat view):**
     - Load just that session's context
   - Read the full session summary
   - Extract key information:
     - Session date and number (for continuation tracking)
     - What was accomplished
     - Open loops (unchecked items) - aggregate if project view
     - Files that were created/updated
     - Resume context (where to pick up)
     - Related project
   - **Store continuation context in conversation:**
     - Remember: "This session continues [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]"
     - This will be used by `/park` to create bidirectional continuation links

7. **Display session context:**

**When loading a session:**
```
Loading: [Session Title] ([Date/Time])

Last session summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[2-3 sentence summary of what was accomplished]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open loops (from this session only):
 [ ] First unchecked item
 [ ] Second unchecked item

Key insights from last session:
 • Important realisation 1
 • Important realisation 2

Project: [[03 Projects/Project Name]] (if applicable)
Files updated: /path/to/file.md, /path/to/other.md

Ready to continue. What's next?
```

8. **Auto-load relevant context files:**
   - Always load: `~/CLAUDE.md`
   - If project linked: Read the project hub file
   - Display what was loaded:
     ```
     Auto-loaded context:
      ✓ CLAUDE.md
      ✓ 03 Projects/[Project Name].md
      ✓ 07 System/Context - [Related Domain].md
     ```

9. **Prompt for next action:**
   - Present the most logical next step based on "Resume Context"
   - Ask: "Ready to continue. What's next?" or "Should I proceed with [suggested next action]?"

## Guidelines

### Project Clustering
- **Default view is project-grouped:** Sessions sharing a `**Project:**` link are clustered together
- **Clustering is mechanical:** Based solely on the `**Project:**` link, not title keywords
- **Standalone sessions:** Sessions without a project link appear individually
- **Project sorting:** By most recent activity, not alphabetically
- **Aggregate loops in menu:** When displaying a project in the menu, show total open loops across all its sessions
- **Always expand, never auto-load:** Selecting a project expands to show all its sessions; user always chooses which session to load
- **Mental model match:** "I'm working on the renovation" is the unit, not "Session 12 vs 14"

### Date and Time
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
- **Pagination threshold:** 15 entries per page (prevents menu overflow)
- **View modes:** Project-grouped (default), flat/chronological (via 'v')
- **Filter preservation:** Once filter applied, maintain it until user clears or changes
- **Hibernate detection:** If user returning after month+ gap with no sessions, suggest `/awaken`
- **WIP staleness monitoring:** Always check Works in Progress timestamp and warn if 9+ days old
- **Critical staleness (30+ days):** Strong warning that projects list is likely outdated, suggest /awaken or manual review

## Integration with Claude Code

This command enables:
1. Zero-friction pickup (no mental "where was I?")
2. **Project-grouped view** matches mental reality ("working on the renovation" not "Session 12")
3. **Always expand, always choose:** Selecting a project shows all its sessions; user picks which to load (no surprising auto-loads)
4. Aggregate open loops visible in project menu
5. Auto-loading of relevant context once session is selected
6. Confidence in session continuity

Combined with `/park`, this creates the bulletproof **park and pickup system**.
