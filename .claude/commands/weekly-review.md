---
name: weekly-review
description: Weekly patterns review - aggregate progress, insights, and alignment
---

# Weekly Review - Patterns Over Time

You are facilitating the user's weekly review. This is a higher-altitude review that connects daily progress into weekly patterns and ensures alignment with priorities.

## Philosophy

The weekly review creates the crucial link between tactical execution (daily/session level) and strategic direction (monthly/quarterly goals). It's where you catch value drift, spot emerging patterns, and realign effort with priorities. Vault structural maintenance is handled by `/weekly-hygiene` — this command focuses on reflection and planning.

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

1. **Check current date and calculate review boundaries** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get ISO week number: `date +"%Y-W%V"` (for file naming: YYYY-Wnn.md)
   - Find the previous weekly review: `ls -1 "$VAULT_PATH/06 Archive/Claude/Weekly Reviews/" 2>/dev/null | sort -r | head -1`
   - **Review period starts** at the day after the previous review's last covered date (parse from the file's date range header), or Monday of the current ISO week if no previous review exists. Store as `PERIOD_START`.
   - **Review period ends** at the current date.
   - Get date range for display: e.g., "Week 11, Mar 9-11" or "Weeks 10-11, Mar 2-11" if the period spans multiple ISO weeks.
   - This command can be run on any day of the week, at any cadence (4-12 days between reviews is normal). Do not assume Sunday-to-Sunday cycles.

2. **Check for Hygiene Report and gather the week's data:**

   **Hygiene report:**
   - Look for the latest file in `$VAULT_PATH/06 Archive/Claude/Hygiene Reports/` (sorted by filename descending)
   - If a report exists, parse the week number from its filename (e.g., `2026-W10.md` → W10) and compare to the current ISO week (`date +%G-W%V`):
     - **Current week:** Read and incorporate — no warning
     - **Previous week or older:** Warn: "Latest hygiene report is from [week] — vault state may have changed. Consider re-running `/weekly-hygiene` before continuing. Proceeding with stale data." Continue with the review but flag staleness in the output.
   - If no reports exist, note this and suggest running `/weekly-hygiene` first (but continue with the review)

   **Week's activity data:**
   - Read daily reports from `$VAULT_PATH/06 Archive/Claude/Daily Reports/` for dates from week start to current date
   - Read session summaries from `$VAULT_PATH/06 Archive/Claude/Session Logs/` for the same date range
   - Read current `01 Now/Works in Progress.md` to see active projects
   - Check project files in `03 Projects/` that were active this week

   **Sweep for tagged tasks:**
   - Long Poles [LP]: `grep -r "\[LP\]" "$VAULT_PATH" --include="*.md" --exclude-dir=".stversions" --exclude-dir="06 Archive" -l`
   - Cornerstones [CS]: `grep -r "\[CS\]" "$VAULT_PATH" --include="*.md" --exclude-dir=".stversions" --exclude-dir="06 Archive" -l`
   - Read the matched files and extract the tagged items for review

   **Claude Corrections Log review:**
   - Read `$VAULT_PATH/07 System/Claude Corrections Log.md`
   - Identify entries from this week (by date header)
   - Flag any lessons that should be promoted to CLAUDE.md or `~/.claude/projects/*/memory/MEMORY.md` for active recall

3. **Run the weekly review interview:**

Before diving into the lenses below, ask the user once whether they want interactive mode (walk through each lens together) or auto-generate mode (compile answers from data, present for validation). One question upfront — don't re-ask per section.

**Collect - What happened:**
- "What were the major accomplishments this week?"
- "Which projects moved forward? Which stalled?"
- "Time allocation: Where did the bulk of hours go?"
- If hygiene report exists, reference its open loop / scratchpad / tickler findings here rather than re-gathering

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
   - Check if `$VAULT_PATH/06 Archive/Claude/Weekly Reviews/` directory exists
   - If not, create it: `mkdir -p "$VAULT_PATH/06 Archive/Claude/Weekly Reviews"`
   - This prevents first-run failures

5. **Generate weekly review:**

Create a file at `$VAULT_PATH/06 Archive/Claude/Weekly Reviews/YYYY-Wnn.md` (using ISO week number from step 1):

```markdown
# Weekly Review - Week [NN], [Date Range]

## Synthesis
**The week:** [One-line summary of what the week was about and what got done]
**Honest take:** [Candid 1-2 sentence assessment - alignment, drift, or what the user should hear]

## Session Count
[Total sessions, daily breakdown table if useful, average per day]

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

### Long Poles [LP] & Cornerstones [CS]

**Long Poles** - Need lead time, can't be rushed:
- [ ] [LP task from file X] - Status/progress this week?
- [ ] [LP task from file Y] - Status/progress this week?

**Cornerstones** - Foundational, other things depend on these:
- [ ] [CS task from file X] - Status/progress this week?
- [ ] [CS task from file Y] - Status/progress this week?

**Review:** Are LP items getting attention early enough? Are CS blockers being addressed?

### Claude Corrections Log Review
**New entries this week:**
- [Date] - [Mistake summary] - Lesson: [key takeaway]

**Promote to active recall?**
- [ ] [Entry] → Add to CLAUDE.md or MEMORY.md? (Y/N, reason)

*Corrections Log is write-only unless promoted. Review weekly to catch patterns worth internalising.*

### Vault Maintenance
*Hygiene report from: YYYY-Wnn (current week / stale — re-run recommended / not found)*

[Populated from Hygiene Report if available — see `/weekly-hygiene`]

[Summary of hygiene findings: WIP health, tier mismatches, tickler items, broken links, etc.]

*If no hygiene report: "No hygiene report available — run `/weekly-hygiene` for vault maintenance."*

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
- [[06 Archive/Claude/Daily Reports/YYYY-MM-DD]] - Mon
- [[06 Archive/Claude/Daily Reports/YYYY-MM-DD]] - Tue
- etc.
```

6. **Populate Vault Maintenance section from hygiene report.** If a hygiene report was found (from step 2), include its findings in the review output's Vault Maintenance section. If no report exists, note "No hygiene report available — run `/weekly-hygiene` for vault maintenance" in that section.

7. **Update Works in Progress** (if needed):
   - Update project statuses based on weekly progress
   - Add new projects if they emerged this week

8. **Display confirmation:**

```
✓ Weekly review saved to: 06 Archive/Claude/Weekly Reviews/YYYY-Wnn.md
✓ Projects reviewed: N active, M completed, P stalled
✓ Hygiene report: [Incorporated / Not found — run /weekly-hygiene]
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

Run whenever the user requests it. Typical cadence is every 4-12 days — there is no fixed day-of-week requirement. The review period adapts to cover whatever time has elapsed since the last review.

## Integration with Other Commands

- **Consumes `/weekly-hygiene`:** Reads the hygiene report for vault maintenance findings — no need to re-gather
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

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
