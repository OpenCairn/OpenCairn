---
name: pickup
aliases: [resume, restore]
description: Interactive menu to pickup recent sessions with full context - the "pickup" in park and pickup
parameters:
  - "--days=N" - Show sessions from last N days (default: 10, max: 90)
  - "--project=NAME" - Filter to sessions related to specific project
  - "--with-loops" - Show only sessions with open loops
  - "--hibernate=DATE" - Load hibernate snapshot instead of session (redirects to /awaken)
  - "--all" - Show all sessions without pagination (use cautiously)
  - "--show-hidden" - Include hidden entries in the menu
---

# Pickup - Session Pickup

You are helping the user pickup a previous work session with full context.

## Instructions

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current timestamp: `date +"%s"` (Unix timestamp for age calculations)
   - Use these to calculate how long ago each session was

2. **Parse parameters and scan for sessions:**
   - Check for parameters: `--days=N`, `--project=NAME`, `--with-loops`, `--hibernate=DATE`, `--all`, `--show-hidden`
   - If `--hibernate` specified: Redirect to `/awaken --date=DATE` and stop
   - Determine lookback window:
     - Default: 10 days (reliably covers weekend-to-weekend plus buffer)
     - Extended after break: If no sessions in last 10 days, automatically extend to 30 days
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

2a. **Filter hidden entries:**
   - Read `06 Archive/Claude Sessions/.pickup-hidden` (if exists)
   - File format: one entry per line, lines starting with `#` are comments
     - Project names: `Home Renovation` (hides entire project cluster)
     - Session identifiers: `2026-01-18#Session 1 - Journal Setup` (hides specific session)
   - Unless `--show-hidden` is set, exclude matching projects and sessions from display
   - If `--show-hidden` is set, show all entries but mark hidden ones with `[H]`

2b. **Check Works in Progress staleness:**
   - Read `01 Now/Works in Progress.md`
   - Extract "Last updated" timestamp from top of file
   - Calculate days since last update
   - If > 10 days old, prepare staleness warning to display with menu
   - If > 30 days old, prepare critical staleness warning

3. **Group sessions by project:**
   - Extract `**Project:**` link from each session (if present)
   - Group sessions sharing the same project link
   - Sessions without project links remain standalone
   - For each project group, calculate:
     - Total session count
     - Most recent session (for display)
     - **Open loops from most recent session only** (older sessions are historical snapshots, their loops may be resolved)
     - Time since last activity (from most recent session)
   - Sort project groups by most recent activity (not alphabetically)

4. **Display interactive menu** (project-grouped by default):
   - **Default view:** By Project (clusters related sessions)
   - **Alternative view:** Flat/chronological (traditional, accessed via 'v')
   - **Pagination threshold:** Show first 15 entries by default
   - **If Works in Progress is stale (10+ days):** Display warning banner before menu

**WIP staleness warning (if 10-29 days old):**
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
completed, abandoned, or deprioritised.

After pickup, consider:
- Running /awaken if returning from extended break
- Manually reviewing and updating Works in Progress
- Archiving completed projects
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Default menu (project-grouped):**
```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Last 10 Days (By Project)               ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Home Renovation                            (8 sessions)║
║     Latest: Kitchen cabinets research      Today 7:10am   ║
║     Open loops: 2 | Last: 0 hours ago                      ║
║                                                            ║
║  2. Side Project - App                         (5 sessions)║
║     Latest: Auth flow implementation       Sat 1:49pm     ║
║     Open loops: 3 | Last: 17 hours ago                     ║
║                                                            ║
║  3. Tax Preparation                               [C] (1)  ║
║     Today 6:55am | Completed                               ║
║                                                            ║
║  4. Journal Setup                                 [C] (1)  ║
║     Today 6:21am | Completed                               ║
║                                                            ║
║  [1-9] select, [v] flat view, [h] hide, [n] new session   ║
║  Note: ⚠️ = 7+ days stale, 🔴 = 30+ days aged              ║
╚════════════════════════════════════════════════════════════╝

>
```

**Note:** Loop counts in project view come from the **most recent session only**, not aggregated across all sessions. Older sessions are historical snapshots - their loops may have been resolved in later sessions.

**Expanded project view (after selecting a project number):**
```
╔════════════════════════════════════════════════════════════╗
║  Home Renovation (8 sessions)                             ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Kitchen cabinets research         Today 7:10am        ║
║     "Compared IKEA vs custom, got quotes"                  ║
║     Open loops: 2  ← current state                         ║
║                                                            ║
║  2. Contractor calls                  Sat 9:16pm          ║
║     "Called 3 contractors, scheduled walkthroughs"         ║
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

**Note:** Only the most recent session shows loop count (marked "← current state"). Older sessions don't display loops since they're historical snapshots.

**Flat view (after 'v' - traditional chronological):**
```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Last 10 Days (Chronological)            ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Today - Sun 18 Jan                                        ║
║  1. Kitchen cabinets research         7:10am  | Loops: 2  ║
║  2. Tax Preparation                   6:55am  | [C]       ║
║  3. Journal Setup                     6:21am  | [C]       ║
║                                                            ║
║  Yesterday - Sat 17 Jan                                    ║
║  4. Contractor calls                  9:16pm              ║
║  5. Permit research                   8:17pm  | [C]       ║
║  ...                                                       ║
║                                                            ║
║  [1-9] pickup, [p] project view, [m] more, [n] new        ║
╚════════════════════════════════════════════════════════════╝

>
```

**Note:** In flat view, only sessions from today show loop counts. Older sessions omit loops since they're historical snapshots - use project view to see current project state.

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
   - **'h':** Enter hide mode (see step 5a)
   - **'u':** Unhide - show hidden entries and allow restoring them

5a. **Hide mode** (when 'h' selected):
   - Display current menu with selection prompts
   - User enters numbers (comma-separated or space-separated) of entries to hide
   - For each selected entry:
     - If project: Add project name to `.pickup-hidden`
     - If standalone session: Add `YYYY-MM-DD#Session N - Title` to `.pickup-hidden`
   - Append to `06 Archive/Claude Sessions/.pickup-hidden`
   - Re-display menu with hidden entries removed
   - Confirm: "Hidden N entries. Use --show-hidden or 'u' to unhide."

5b. **Unhide mode** (when 'u' selected):
   - Read `.pickup-hidden` file
   - Display numbered list of currently hidden entries
   - User enters numbers to restore (unhide)
   - Remove selected lines from `.pickup-hidden`
   - Re-display main menu with restored entries visible

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

### Hide/Unhide Feature
- **Purpose:** Declutter the pickup menu by hiding completed projects or irrelevant sessions
- **Hidden file location:** `06 Archive/Claude Sessions/.pickup-hidden`
- **Hiding is non-destructive:** Session files remain intact, just filtered from display
- **Project-level hiding:** Hiding a project hides all its sessions
- **Session-level hiding:** Can hide individual standalone sessions
- **Unhide anytime:** Use 'u' in menu or `--show-hidden` flag to see/restore hidden entries
- **Good candidates for hiding:**
  - Completed projects (already marked [C])
  - One-off sessions you won't return to
  - Old standalone sessions superseded by newer work
- **Don't hide:** Sessions with unresolved open loops (address them first or explicitly drop)

### Project Clustering
- **Default view is project-grouped:** Sessions sharing a `**Project:**` link are clustered together
- **Clustering is mechanical:** Based solely on the `**Project:**` link, not title keywords
- **Standalone sessions:** Sessions without a project link appear individually
- **Project sorting:** By most recent activity, not alphabetically
- **Most recent session loops only:** When displaying a project, show open loops from the most recent session only - older sessions are historical snapshots whose loops may have been resolved
- **Always expand, never auto-load:** Selecting a project expands to show all its sessions; user always chooses which session to load
- **Mental model match:** "I'm working on the renovation" is the unit, not "Session 12 vs 14"

### Date and Time
- **Always check current date/time:** First step - run `date` command for accurate age calculations. Never assume time.
- **Menu header shows configured window:** Display "Last 10 Days" (or whatever `--days=N` was set to), not the range of files found. The window is what we searched, not what we found. If sessions only exist from Jan 15-19 but we searched 10 days, header still says "Last 10 Days".
- **Auto-extend window after breaks:** If no sessions in last 10 days, automatically extend to 30 days and notify user
- **No sessions found:** If no sessions in extended window, suggest `/awaken` or starting fresh
- **Session ordering:** Display most recent first (reverse chronological)
- **Age display:** Show relative time ("2 hours ago", "yesterday", "3 days ago") using current time from step 1
- **Open loop counting:** Only count unchecked items (`- [ ]`), ignore completed ones (`- [x]`)
- **Open loop age tracking:**
  - Calculate days since session date for all unchecked loops
  - Flag stale (10-29 days): ⚠️ warning in menu
  - Flag aged (30+ days): 🔴 critical in menu + prominent warning on load
  - Purpose: Surface loops that may need completion or explicit dropping
- **Stale loop warnings:** Display only when loading sessions with 10+ day old loops
- **Loop age philosophy:** Long-open loops often indicate either low priority (should drop) or high friction (needs decomposition)
- **Context loading:** Be intelligent about which context files to load based on project and domain
- **Date formatting:** Use natural language ("Sat 17 Jan 9:40am" not "2026-01-17 09:40")
- **Menu width:** Keep menu width at 64 characters for terminal readability
- **Pagination threshold:** 15 entries per page (prevents menu overflow)
- **View modes:** Project-grouped (default), flat/chronological (via 'v')
- **Filter preservation:** Once filter applied, maintain it until user clears or changes
- **Hibernate detection:** If user returning after month+ gap with no sessions, suggest `/awaken`
- **WIP staleness monitoring:** Always check Works in Progress timestamp and warn if 10+ days old
- **Critical staleness (30+ days):** Strong warning that projects list is likely outdated, suggest /awaken or manual review

## Integration with Claude Code

This command enables:
1. Zero-friction pickup (no mental "where was I?")
2. **Project-grouped view** matches mental reality ("working on the renovation" not "Session 12")
3. **Always expand, always choose:** Selecting a project shows all its sessions; user picks which to load (no surprising auto-loads)
4. Current open loops visible in project menu (from most recent session only)
5. Auto-loading of relevant context once session is selected
6. Confidence in session continuity

Combined with `/park`, this creates the bulletproof **park and pickup system**.
