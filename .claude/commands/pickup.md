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
  - "--show-hidden" - Include hidden entries in the menu (shows snoozed items with resurface date)
---

# Pickup - Session Pickup

You are helping the user pickup a previous work session with full context.

## Instructions

1. **Resolve Vault Path**

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

2. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current timestamp: `date +"%s"` (Unix timestamp for age calculations)
   - Use these to calculate how long ago each session was

3. **Parse parameters and scan for sessions using shell script:**
   - Check for parameters: `--days=N`, `--project=NAME`, `--with-loops`, `--hibernate=DATE`, `--all`, `--show-hidden`
   - If `--hibernate` specified: Redirect to `/awaken --date=DATE` and stop
   - **Run the pickup scanner shell script** to extract metadata efficiently:
     ```bash
     "$VAULT_PATH/.claude/scripts/pickup-scan.sh" --days=N --hidden-file="[SESSION_DIR]/.pickup-hidden" [--show-hidden]
     ```
     (Script uses `CLAUDE_SESSION_DIR` env var or defaults to `$VAULT_PATH/06 Archive/Claude Sessions`)
   - The script outputs TSV with columns: `DATE`, `SESSION_NUM`, `TITLE`, `TIME`, `PROJECT`, `LOOP_COUNT`, `SUMMARY`
   - **Parse the TSV output** to build session list (this is ~10x smaller than reading full files)
   - If no sessions found in default window (10 days), re-run with `--days=30`
   - Apply additional filters on the parsed data:
     - If `--project=NAME`: Keep only sessions where PROJECT contains NAME (case-insensitive)
     - If `--with-loops`: Keep only sessions where LOOP_COUNT > 0
   - Calculate session age from DATE field: "2 hours ago", "yesterday", "3 days ago" using current time from step 2
   - Flag stale loops based on date: 7+ days = ⚠️, 30+ days = 🔴

4. **Hidden/snoozed entries (handled by shell script):**
   - The shell script handles filtering based on `.pickup-hidden` file
   - File format: one entry per line, lines starting with `#` are comments
     - Project names: `Website Redesign` (hides entire project cluster)
     - Session identifiers: `2026-01-18#Session 1 - Journal Folder Setup` (hides specific session)
     - **Snoozed entries:** Append `|until:YYYY-MM-DD` to snooze until a date
   - **Snooze auto-resurface:** Expired snoozes are shown by the script (not filtered)
   - **Snooze cleanup:** After displaying menu, remove expired snooze lines from `.pickup-hidden` using flock
   - If `--show-hidden` passed to script, hidden/snoozed entries are included in output

5. **Check Works in Progress staleness:**
   - Read `$VAULT_PATH/01 Now/Works in Progress.md`
   - Extract "Last updated" timestamp from top of file
   - Calculate days since last update
   - If > 10 days old, prepare staleness warning to display with menu
   - If > 30 days old, prepare critical staleness warning

6. **Check Tickler for due items:**
   - Read `$VAULT_PATH/01 Now/Tickler.md` (if file doesn't exist, skip this step)
   - Parse date headers (format: `## YYYY-MM-DD`)
   - For each date header where date <= today (from step 2):
     - Extract all unchecked items (`- [ ]`) under that header
     - Note if date is past (not today) — these are overdue
     - Store for display in tickler banner
   - If any items due, prepare tickler banner to display before menu

7. **Group sessions by project:**
   - Extract `**Project:**` link from each session (if present)
   - Group sessions sharing the same project link
   - Sessions without project links remain standalone
   - For each project group, calculate:
     - Total session count
     - Most recent session (for display)
     - **Open loops from most recent session only** (older sessions are historical snapshots, their loops may be resolved)
     - Time since last activity (from most recent session)
   - Sort project groups by most recent activity (not alphabetically)

8. **Display interactive menu** (project-grouped by default):
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

**Tickler items due (if any items where date <= today):**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 Tickler items due
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- [ ] Item 1 → [[context link]]
- [ ] Item 2 (⚠️ 3 days overdue) → [[context link]]

To action: edit 01 Now/Tickler.md (delete, reschedule, or move to WIP)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Default menu (project-grouped):**
```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Last 10 Days (By Project)               ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Website Redesign                         (8 sessions)║
║     Latest: Homepage Layout & Nav          Today 7:10am   ║
║     Open loops: 2 | Last: 0 hours ago                      ║
║                                                            ║
║  2. Claude Code Learning                       (5 sessions)║
║     Latest: GitHub Template Repository     Sat 1:49pm     ║
║     Open loops: 3 | Last: 17 hours ago                     ║
║                                                            ║
║  3. Template Repo v0.5 Release                    [C] (1)  ║
║     Today 6:55am | Completed                               ║
║                                                            ║
║  4. Journal Folder Setup                          [C] (1)  ║
║     Today 6:21am | Completed                               ║
║                                                            ║
║  [1-9] select, [v] flat, [h] hide, [z] snooze, [n] new     ║
║  Note: ⚠️ = 7+ days stale, 🔴 = 30+ days aged              ║
╚════════════════════════════════════════════════════════════╝

>
```

**Note:** Loop counts in project view come from the **most recent session only**, not aggregated across all sessions. Older sessions are historical snapshots - their loops may have been resolved in later sessions.

**Expanded project view (after selecting a project):**
```
╔════════════════════════════════════════════════════════════╗
║  Website Redesign (8 sessions)                            ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Homepage Layout & Nav              Today 7:10am       ║
║     "Added hero section, simplified navigation"            ║
║     Open loops: 2  ← current state                         ║
║                                                            ║
║  2. Tailscale & Skills Setup           Sat 9:16pm         ║
║     "Tailscale, 13 skills copied, SSH key auth"            ║
║                                                            ║
║  3. Old Laptop Clone & Wipe            Sat 8:17pm    [C]  ║
║     "Cloned data to USB, wiped for donation"               ║
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
║  1. Homepage Layout & Nav              7:10am  | Loops: 2 ║
║  2. Template Repo v0.5 Release         6:55am  | [C]      ║
║  3. Journal Folder Setup               6:21am  | [C]      ║
║                                                            ║
║  Yesterday - Sat 17 Jan                                    ║
║  4. Tailscale & Skills Setup           9:16pm             ║
║  5. Old Laptop Clone & Wipe            8:17pm  | [C]      ║
║  ...                                                       ║
║                                                            ║
║  [1-9] pickup, [p] project view, [m] more, [n] new        ║
╚════════════════════════════════════════════════════════════╝

>
```

**Note:** In flat view, only sessions from today show loop counts. Older sessions omit loops since they're historical snapshots - use project view to see current project state.

9. **Wait for user selection** (or if no input needed, continue automatically):
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
   - **'h':** Enter hide mode (see step 10)
   - **'z':** Enter snooze mode (see step 12)
   - **'u':** Unhide/unsnooze - show hidden entries and allow restoring them

10. **Hide mode** (when 'h' selected):
   - Display current menu with selection prompts
   - User enters numbers (comma-separated or space-separated) of entries to hide
   - For each selected entry:
     - If project: Add project name to `.pickup-hidden`
     - If standalone session: Add `YYYY-MM-DD#Session N - Title` to `.pickup-hidden`
   - **File locking:** Use `flock` when modifying `.pickup-hidden` to prevent race conditions
   - Append to `$VAULT_PATH/06 Archive/Claude Sessions/.pickup-hidden` (create if doesn't exist)
   - Re-display menu with hidden entries removed
   - Confirm: "Hidden N entries. Use --show-hidden or 'u' to unhide."

11. **Unhide mode** (when 'u' selected):
   - Read `.pickup-hidden` file
   - Display numbered list of currently hidden/snoozed entries (show snooze dates)
   - User enters numbers to restore (unhide/unsnooze)
   - **File locking:** Use `flock` when modifying `.pickup-hidden` to prevent race conditions
   - Remove selected lines from `.pickup-hidden` (exact line match)
   - Re-display main menu with restored entries visible

12. **Snooze mode** (when 'z' selected):
   - Display current menu with selection prompts
   - User enters numbers (comma-separated or space-separated) of entries to snooze
   - Prompt for duration. Accept flexible formats:
     - Relative: `2d` (2 days), `1w` (1 week), `3d` (3 days)
     - Absolute: `2026-01-28` or `28 Jan` or `Jan 28`
     - Natural: `tomorrow`, `until Wednesday`, `until next Monday` (always forward-looking - if today is Thursday, "until Wednesday" = next Wednesday, 6 days out; if today IS Wednesday, "until Wednesday" = next Wednesday, 7 days out)
   - Calculate the resurface date from current date (step 2)
   - **Validation:** If calculated date is today or in the past, warn and prompt for new duration
   - **Dedup check:** Before appending, check if entry already exists in `.pickup-hidden`:
     - If permanently hidden: Ask "Already hidden. Convert to snooze until [DATE]?"
     - If already snoozed: Update the existing snooze date (don't add duplicate)
   - For each selected entry:
     - If project (from project view): Add `Project Name|until:YYYY-MM-DD`
     - If session in flat view with a project link: Ask "Snooze entire project or just this session?"
     - If standalone session: Add `YYYY-MM-DD#Session N - Title|until:YYYY-MM-DD`
   - **Case preservation:** Use original case from session/project name (matching is case-insensitive, but file entries preserve original)
   - **File locking:** Use `flock` when modifying `.pickup-hidden` to prevent race conditions with concurrent sessions
   - Append to `$VAULT_PATH/06 Archive/Claude Sessions/.pickup-hidden` (create if doesn't exist)
   - Re-display menu with snoozed entries removed
   - Confirm: "Snoozed [ITEM NAMES] until [DATE]. They'll resurface automatically."

13. **Load selected session context (deferred loading):**
   - **IMPORTANT:** This is the first time the full session file is read. Menu building used only TSV metadata.
   - **If project selected (from project view):**
     - Expand to show all sessions in that project (using TSV data, still no file read)
     - User then selects specific session to load
     - Do NOT auto-load most recent - always let user choose
   - **If specific session selected (from expanded/flat view):**
     - **NOW read the full session file:** `$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md`
     - Navigate to the specific session section (`## Session N - Title`)
   - Extract key information from the session section:
     - Session date and number (for continuation tracking)
     - Full summary (not truncated)
     - Open loops with full text (unchecked items from Next Steps section)
     - Files that were created/updated
     - Resume context (from Pickup Context section)
     - Related project
   - **Store continuation context in conversation:**
     - Remember: "This session continues [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]"
     - This will be used by `/park` to create bidirectional continuation links

14. **Display session context:**

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

15. **Auto-load relevant context files:**
   - Always load: `~/CLAUDE.md`
   - If project linked: Read the project hub file (check both locations):
     - `$VAULT_PATH/03 Projects/[Project Name].md` (active projects)
     - `$VAULT_PATH/03 Projects/Backlog/[Project Name].md` (backlog projects)
   - Display what was loaded:
     ```
     Auto-loaded context:
      ✓ CLAUDE.md
      ✓ 03 Projects/[Project Name].md (or 03 Projects/Backlog/[Project Name].md)
      ✓ 07 System/Context - [Related Domain].md
     ```

16. **Prompt for next action:**
   - Present the most logical next step based on "Resume Context"
   - Ask: "Ready to continue. What's next?" or "Should I proceed with [suggested next action]?"

## Guidelines

### Project Clustering
- **Default view is project-grouped:** Sessions sharing a `**Project:**` link are clustered together
- **Clustering is mechanical:** Based solely on the `**Project:**` link, not title keywords
- **Standalone sessions:** Sessions without a project link appear individually
- **Project sorting:** By most recent activity, not alphabetically
- **Most recent session loops only:** When displaying a project, show open loops from the most recent session only - older sessions are historical snapshots whose loops may have been resolved
- **Always expand, never auto-load:** Selecting a project expands to show all its sessions; user always chooses which session to load
- **Mental model match:** "I'm working on the website redesign" is the unit, not "Session 12 vs 14"
- **Backlog projects included:** Projects in `03 Projects/Backlog/` cluster the same as active projects - the subfolder is transparent to clustering

### Hide/Unhide Feature
- **Purpose:** Declutter the pickup menu by hiding completed projects or irrelevant sessions
- **Hidden file location:** `$VAULT_PATH/06 Archive/Claude Sessions/.pickup-hidden`
- **Hiding is non-destructive:** Session files remain intact, just filtered from display
- **Project-level hiding:** Hiding a project hides all its sessions
- **Session-level hiding:** Can hide individual standalone sessions
- **Unhide anytime:** Use 'u' in menu or `--show-hidden` flag to see/restore hidden entries
- **Good candidates for hiding:**
  - Completed projects (already marked [C])
  - One-off sessions you won't return to
  - Old standalone sessions superseded by newer work
- **Don't hide:** Sessions with unresolved open loops (address them first or explicitly drop)

### Snooze Feature
- **Purpose:** Temporarily hide items that you want to revisit later - not forgotten, just deferred
- **Snooze vs Hide:** Hide = "I'm done with this". Snooze = "Not now, but remind me on [date]"
- **File format:** Same as hide, with `|until:YYYY-MM-DD` suffix
  - Example: `API Integration|until:2026-01-28`
- **Auto-resurface:** When pickup runs and today >= snooze date, item automatically reappears and line is removed from file
- **Auto-cleanup:** Expired snooze entries are removed from `.pickup-hidden` when pickup runs (prevents file bloat)
- **Duration formats accepted:**
  - Relative: `2d`, `3d`, `1w`, `2w`
  - Absolute: `2026-01-28`, `28 Jan`, `Jan 28`
  - Natural: `tomorrow`, `until Wednesday`, `until next Monday` (always next occurrence, never past)
- **Project name matching:** Uses display name extracted from wikilinks, case-insensitive
- **Idempotency:** Re-snoozing updates existing entry rather than adding duplicate
- **Past date protection:** Snooze date must be in the future (at least tomorrow)
- **Good candidates for snoozing:**
  - Projects you're deliberately pausing but want to reconsider soon
  - Items blocked by external factors with known resolution dates
  - "Not this week" items you don't want cluttering today's view
- **Snooze philosophy:** Snoozing is a commitment to reconsider, not a way to avoid. If you snooze something 3+ times, either do it or drop it.

### Date and Time
- **Always check current date/time:** First step - run `date` command for accurate age calculations. Never assume time.
- **Menu header shows configured window:** Display "Last 10 Days" (or whatever `--days=N` was set to), not the range of files found. The window is what we searched, not what we found. If sessions only exist from Jan 15-19 but we searched 10 days, header still says "Last 10 Days".
- **Auto-extend window after breaks:** If no sessions in last 10 days, automatically extend to 30 days and notify user
- **No sessions found:** If no sessions in extended window, suggest `/awaken` or starting fresh
- **Session ordering:** Display most recent first (reverse chronological)
- **Age display:** Show relative time ("2 hours ago", "yesterday", "3 days ago") using current time from step 2
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

### Context Efficiency (Two-Stage Loading)
- **Problem solved:** Reading all session files (~400KB+) for menu building consumed 50-80% of context before work began
- **Solution:** Shell script (`"$VAULT_PATH/.claude/scripts/pickup-scan.sh"`) extracts metadata outside Claude's context
- **Stage 1 (menu building):** Shell script scans files, outputs ~40KB TSV metadata
- **Stage 2 (session loading):** Only selected session file is read by Claude
- **Result:** ~10x reduction in context usage for pickup
- **Shell script location:** `"$VAULT_PATH/.claude/scripts/pickup-scan.sh"`
- **If script missing or fails:** Warn user that context usage will be high, then fall back to direct file reading. This works but defeats the context efficiency benefit.

## Integration with Claude Code

This command enables:
1. Zero-friction pickup (no mental "where was I?")
2. **Project-grouped view** matches mental reality ("working on the website" not "Session 12")
3. **Always expand, always choose:** Selecting a project shows all its sessions; user picks which to load (no surprising auto-loads)
4. Current open loops visible in project menu (from most recent session only)
5. Auto-loading of relevant context once session is selected
6. Confidence in session continuity
7. **Context-efficient:** Two-stage loading preserves context for actual work
8. **Tickler surfacing:** Deferred tasks automatically resurface when their date arrives

Combined with `/park`, this creates the bulletproof **park and pickup system**.

**Reads from:** Claude Sessions, Works in Progress, Tickler
