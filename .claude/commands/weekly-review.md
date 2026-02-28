---
name: weekly-review
description: Weekly patterns review - aggregate progress, insights, alignment, and vault maintenance
---

# Weekly Review - Patterns Over Time

You are facilitating the user's weekly review. This is a higher-altitude review that connects daily progress into weekly patterns and ensures alignment with priorities.

## Philosophy

The weekly review creates the crucial link between tactical execution (daily/session level) and strategic direction (monthly/quarterly goals). It's where you catch value drift, spot emerging patterns, realign effort with priorities, and keep the vault structurally healthy.

## Instructions

0. **Resolve Vault Path**

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

1. **Check current date and calculate week boundaries** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get ISO week number: `date +"%Y-W%V"` (for file naming: YYYY-Wnn.md)
   - Calculate week start: `date -d "last monday" +"%Y-%m-%d"` (or this Monday if today is Monday)
   - Calculate week end: current date
   - Get date range for display: e.g., "Week 3, Jan 13-19"

2. **Gather the week's data:**
   - Read daily reports from `$VAULT_PATH/06 Archive/Daily Reports/` for dates from week start to current date
   - Read session summaries from `$VAULT_PATH/06 Archive/Claude Sessions/` for the same date range
   - Read current `01 Now/Works in Progress.md` to see active projects
   - Check project files in `03 Projects/` that were active this week
   - Find all Scratchpad.md files in `04 Areas/`: `find $VAULT_PATH/04\ Areas -name "Scratchpad.md" -type f`
   - **Sweep for tagged tasks:**
     - Long Poles [LP]: `grep -r "\[LP\]" "$VAULT_PATH" --include="*.md" -l`
     - Cornerstones [CS]: `grep -r "\[CS\]" "$VAULT_PATH" --include="*.md" -l`
   - Read the matched files and extract the tagged items for review
   - **Claude Corrections Log review:**
     - Read `$VAULT_PATH/07 System/Claude Corrections Log.md`
     - Identify entries from this week (by date header)
     - Flag any lessons that should be promoted to CLAUDE.md or `~/.claude/projects/*/memory/MEMORY.md` for active recall
   - **Working Memory sweep:**
     - Read `$VAULT_PATH/01 Now/Working memory.md`
     - Count items in each section (Fresh Captures, To Review, etc.)
     - Flag sections with 10+ unprocessed items
     - Identify any items that appear to be actionable tasks that should be in WIP or project files
     - Note items that have routing guidance but haven't been moved yet
   - **Vault maintenance metrics:**
     - WIP line count: `wc -l "$VAULT_PATH/01 Now/Works in Progress.md"`
     - WIP session links: `grep -c "06 Archive/Claude Sessions" "$VAULT_PATH/01 Now/Works in Progress.md"`
     - WIP completed/strikethrough items: `grep -cE "\[x\]|~~.*~~" "$VAULT_PATH/01 Now/Works in Progress.md"`
     - Count session links per WIP section (Big Rocks vs Active vs Backlog) — heaviest sections are pruning candidates
     - For each Active/Big Rock project, check the **Last:** date — flag any 14+ days stale
   - **Projects folder audit:**
     - List top-level: `ls "$VAULT_PATH/03 Projects/"`
     - List Cold/: `ls "$VAULT_PATH/03 Projects/Cold/" 2>/dev/null`
     - List Backlog/: `ls "$VAULT_PATH/03 Projects/Backlog/" 2>/dev/null`
     - Cross-reference with WIP sections — flag tier mismatches (e.g., Active project with file in Cold/, Backlog WIP entry with file in root)
   - **Tickler hygiene:**
     - Read `$VAULT_PATH/01 Now/Tickler.md` (if it exists)
     - Flag items with dates that have passed (past-due and unactioned)
   - **CRM name scan** (if `$VAULT_PATH/07 System/CRM/` exists):
     - Read CRM index to get list of known names
     - Extract names from this week's session files:
       ```bash
       # Find name-shaped strings in this week's sessions
       find "$VAULT_PATH/06 Archive/Claude Sessions/" -name "*.md" -newermt "$(date -d 'last monday' +%Y-%m-%d)" -exec \
         grep -oh '[A-Z][a-z]+ [A-Z][a-z]+' {} + | sort | uniq -c | sort -rn | head -20
       # Note: Includes false positives (section headers, tool names).
       # Cross-reference against CRM — flag names that appear 2+ times but aren't in CRM.
       ```
     - Present candidates to user — **don't auto-add**

3. **Run the weekly review interview:**

**Collect - What happened:**
- "What were the major accomplishments this week?"
- "Which projects moved forward? Which stalled?"
- "Time allocation: Where did the bulk of hours go?"
- **Check for aged open loops:** Scan all sessions in the week for unchecked items, flag any that have been open 14+ days
- **Scratchpad sweep:** Scan all `Scratchpad.md` files in `04 Areas/` for items that have been sitting unprocessed. Flag any that are 14+ days old or have grown stale. Scratchpads are inboxes, not permanent homes.

**Reflect - What matters:**
- "Key insights or learning from this week?"
- "What patterns emerged? (Good and bad)"
- "Any surprises - things that were easier or harder than expected?"
- "What did you overestimate? Underestimate?"

**Align - Priorities check:**
- "Looking at how you spent time vs your stated priorities - any misalignment?"
- "What got attention that shouldn't have?"
- "What didn't get attention that should have?"
- "Are you working on the right things?"

**Plan - What's next:**
- "What's the focus for next week?"
- "Any course corrections needed?"
- "Anything to stop doing or delegate?"

4. **Ensure directory exists:**
   - Check if `$VAULT_PATH/06 Archive/Weekly Reviews/` directory exists
   - If not, create it: `mkdir -p "$VAULT_PATH/06 Archive/Weekly Reviews"`
   - This prevents first-run failures

5. **Generate weekly review:**

Create a file at `$VAULT_PATH/06 Archive/Weekly Reviews/YYYY-Wnn.md` (using ISO week number from step 1):

```markdown
# Weekly Review - Week [NN], [Date Range]

## Major Accomplishments
[Bullet list of significant progress, completions, milestones]

## Projects Active This Week
**Advanced:**
- [[03 Projects/Project A]] - [What moved forward]
- [[03 Projects/Project B]] - [What moved forward]

**Stalled:**
- [[03 Projects/Project C]] - [Why stalled, what's blocking]

**Completed:**
- [[03 Projects/Project D]] - [Outcome achieved]

## Time Allocation
[High-level breakdown of where hours went]
- Work/Training: X%
- Projects: Y%
- Health/Fitness: Z%
- etc.

## Key Insights & Patterns

### Wins & What's Working
[Patterns of success, effective strategies, good decisions]

### Challenges & Friction
[Recurring problems, inefficiencies, areas needing attention]

### Learning
[New skills, realisations, mental model updates]

## Alignment Check

### Priorities vs Reality
[Honest assessment: Is effort aligned with stated priorities?]

### Value Drift Alerts
[Any signs of drift toward low-value activities?]

### Aged Open Loops (14+ Days)
**Stale items requiring action:**
- [ ] Item from Session X (N days old) - Complete, drop, or delegate?
- [ ] Item from Session Y (N days old) - Complete, drop, or delegate?

**Recommendation:** These have lingered for 2+ weeks. Either act or explicitly drop.

### Scratchpad Sweep
**Area scratchpads with unprocessed items:**
- `04 Areas/Photography/Scratchpad.md` - N items, oldest from [date]
- `04 Areas/Family/Scratchpad.md` - N items, oldest from [date]

**Action needed:** Route items to proper homes or delete. Scratchpads are inboxes, not storage.

### Long Poles [LP] & Cornerstones [CS]

**Long Poles** - Need lead time, can't be rushed:
- [ ] [LP task from file X] - Status/progress this week?
- [ ] [LP task from file Y] - Status/progress this week?

**Cornerstones** - Foundational, other things depend on these:
- [ ] [CS task from file X] - Status/progress this week?
- [ ] [CS task from file Y] - Status/progress this week?

**Review:** Are LP items getting attention early enough? Are CS blockers being addressed?

### Works in Progress Integrity Check
**Zombie projects (in WIP but inactive 30+ days):**
- [Project A] - Last activity: N days ago. Complete or drop?
- [Project B] - Last activity: N days ago. Complete or drop?

**Missing files:**
- [Project C] - Listed in WIP but project file doesn't exist

**Orphaned files:**
- [Project D] - Has project file but not in WIP (add or archive?)

**Recommendation:** Clean up discrepancies. Use `/complete-project` for zombie projects.

### Working Memory Sweep
**Current state:**
- Fresh Captures: N items
- To Review: N items
- Cornerstone Tasks [CS]: N items
- Long Poles [LP]: N items

**Stale sections (10+ items):**
- [Section] - N items, oldest from [date estimate]

**Actionable items that should be routed:**
- [ ] [Item] → Should be in WIP or [Project]
- [ ] [Item] → Route to [Area scratchpad]

**Recommendation:** Working Memory is a brain dump inbox, not storage. Process weekly or items become invisible.

### Vault Maintenance

**WIP Health:**
- Line count: N lines (target: <300; flag if >300)
- Session links: N total across all projects (heaviest: [Project] with M links)
- Completed/strikethrough items still present: N
- Stale Active projects (Last: 14+ days ago): [list any]
- **Action needed:** [Trim session links to 3-5 per project / Remove N completed items / Demote stale projects / No action needed]

**Projects Folder Hygiene:**
- Tier mismatches: [Active WIP projects with files in Cold/ or Backlog/, or vice versa]
- Projects that should move to Cold/ (inactive, not archived): [list any]
- Projects that graduated to Active but file is still in Backlog/: [list any]
- **Action needed:** [Move X to Cold/ / Move Y to root / No action needed]

**Tickler Hygiene:**
- Past-due items: N
- [List each past-due item with original date]
- **Action needed:** [Complete, reschedule, or drop each item]

### Claude Corrections Log Review
**New entries this week:**
- [Date] - [Mistake summary] - Lesson: [key takeaway]

**Promote to active recall?**
- [ ] [Entry] → Add to CLAUDE.md or MEMORY.md? (Y/N, reason)

*Corrections Log is write-only unless promoted. Review weekly to catch patterns worth internalising.*

### CRM Candidates
**New names this week (not in CRM, mentioned 2+ times):**
- [Name] - appeared N times - Context: [which sessions/projects]

**Action needed:** Review and add to CRM if worth tracking. False positives (section headers, tool names) can be ignored.

### Course Corrections Needed
[What to adjust for next week]

## Next Week's Focus

**Big Rocks (Priority 1):**
- [ ] Most important thing
- [ ] Second priority

**Active Projects:**
- [ ] Project A - [Specific next milestone]
- [ ] Project B - [Specific next milestone]

**Stop/Delegate:**
[Things to drop or hand off]

## Daily Reports This Week
[Links to daily reports for drill-down]
- [[06 Archive/Daily Reports/YYYY-MM-DD]] - Mon
- [[06 Archive/Daily Reports/YYYY-MM-DD]] - Tue
- etc.
```

6. **Check Works in Progress integrity:**
   - Read `$VAULT_PATH/01 Now/Works in Progress.md`
   - For each Active project:
     - Check if project file exists in `03 Projects/` or `06 Archive/`
     - Check when project folder/files were last modified (if applicable)
     - Check if project was referenced in any sessions this week
   - Flag discrepancies:
     - **Zombie projects:** In WIP but no file activity in 30+ days and no session references
     - **Missing files:** In WIP but project file doesn't exist
     - **Orphaned files:** Project files exist but not in WIP
   - Include in review output under "Alignment Check"

7. **Vault maintenance pass:**
   This is the weekly hygiene sweep. The vault accumulates structural debt through daily use — session links pile up, completed items linger, projects drift between tiers. Catching it weekly prevents the kind of 420→236 line emergency refactor that shouldn't be necessary.

   **WIP pruning:**
   - If WIP exceeds 300 lines, flag for pruning
   - Trim session links to **3-5 most recent per project** (session history lives in the session archive, not WIP)
   - Remove completed/strikethrough checklist items (the `[x] ~~done thing~~ ✅` pattern) — these are historical records, not active tasks
   - Remove resolved open decisions (strikethrough decisions that were answered)
   - Flag Active/Big Rock projects whose **Last:** date is 14+ days stale — either demote or nudge

   **Projects folder hygiene:**
   - Cross-reference WIP sections with `03 Projects/` folder structure:
     - Active/Big Rock WIP entries should have project files in `03 Projects/` root (not in `Cold/` or `Backlog/`)
     - Backlog WIP entries should have files in `03 Projects/Cold/` or `03 Projects/Backlog/`
     - Completed projects should be in `06 Archive/`
   - Flag and fix tier mismatches — move project files to match their WIP status
   - Check for project files that exist in `03 Projects/` but have no WIP entry (orphans — add to WIP or archive)

   **Tickler hygiene:**
   - Read `$VAULT_PATH/01 Now/Tickler.md`
   - Identify items with dates that have already passed
   - For each past-due item: recommend complete, reschedule (with new date), or drop
   - Clean up completed tickler items that were already pulled into weekly plans

   **Execute fixes** with user confirmation for anything destructive (file moves, deletions). Pruning WIP content and trimming session links can proceed automatically.

8. **Update Works in Progress** (if needed):
   - Archive completed projects to `06 Archive/`
   - Update project statuses based on weekly progress
   - Add new projects if they emerged this week
   - Address integrity issues flagged in step 6

9. **Display confirmation:**

```
✓ Weekly review saved to: 06 Archive/Weekly Reviews/YYYY-Wnn.md
✓ Projects reviewed: N active, M completed, P stalled
✓ Vault maintenance: [N issues found and fixed / No issues]
✓ Next week's focus: [Top 2-3 priorities]

Weekly review complete.

Recommended: Skim this review at the start of next week to set the week's direction.
```

## Guidelines

- **Always check current date:** First step - run `date` command to calculate accurate week boundaries. Never assume.
- **Patterns over details:** Look for recurring themes, not exhaustive documentation
- **Honest alignment check:** This is where you catch yourself working on the wrong things
- **Forward-looking:** Use insights to improve next week, not just to record past week
- **Connect timescales:** Link weekly patterns to monthly/quarterly goals (if tracked)
- **Quantify when useful:** Time allocation, completed tasks, etc. - numbers reveal patterns
- **Natural language:** Write in the user's voice - analytical, outcome-focused, honest

## Frequency

Run this weekly, typically:
- Sunday evening (week review and next week planning)
- Monday morning (week ahead orientation)
- Or whenever the user explicitly requests it

## Integration with Other Commands

- **Synthesizes daily reviews:** Aggregates daily patterns into weekly insights
- **Informs project planning:** Identifies what needs attention, what to drop
- **Feeds into monthly/quarterly reviews:** (If the user implements those)
- **Alignment with philosophy:** Connects tactics to values (see Philosophy & Worldview context)

This creates a **weekly rhythm** that prevents value drift and ensures high-level course correction.

## Goal Alignment (Optional Enhancement)

If the user starts tracking explicit goals in the vault:
- Compare weekly effort to goal progress
- Flag misalignments ("You spent 40% of time on X, but it's not in your top 3 goals")
- Suggest reallocation or goal updates
