---
name: weekly-synthesis
description: Weekly patterns review - aggregate progress, insights, and alignment
---

# Weekly Synthesis - Patterns Over Time

You are facilitating the user's weekly synthesis. This is a higher-altitude review that connects daily progress into weekly patterns and ensures alignment with priorities.

## Philosophy

Weekly synthesis creates the crucial link between tactical execution (daily/session level) and strategic direction (monthly/quarterly goals). It's where you catch value drift, spot emerging patterns, and realign effort with priorities.

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

3. **Run the weekly synthesis interview:**

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

5. **Generate weekly synthesis:**

Create a file at `$VAULT_PATH/06 Archive/Weekly Reviews/YYYY-Wnn.md` (using ISO week number from step 1):

```markdown
# Weekly Synthesis - Week [NN], [Date Range]

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

### Claude Corrections Log Review
**New entries this week:**
- [Date] - [Mistake summary] - Lesson: [key takeaway]

**Promote to active recall?**
- [ ] [Entry] → Add to CLAUDE.md or MEMORY.md? (Y/N, reason)

*Corrections Log is write-only unless promoted. Review weekly to catch patterns worth internalising.*

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
   - Include in synthesis output under "Alignment Check"

7. **Update Works in Progress** (if needed):
   - Archive completed projects to `06 Archive/`
   - Update project statuses based on weekly progress
   - Add new projects if they emerged this week
   - Address integrity issues flagged in step 6

8. **Display confirmation:**

```
✓ Weekly synthesis saved to: 06 Archive/Weekly Reviews/YYYY-Wnn.md
✓ Projects reviewed: N active, M completed, P stalled
✓ Next week's focus: [Top 2-3 priorities]

Weekly synthesis complete.

Recommended: Review this synthesis at start of next week to set the week's direction.
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
