---
name: weekly-synthesis
description: Weekly patterns review - aggregate progress, insights, and alignment
---

# Weekly Synthesis - Patterns Over Time

You are facilitating a weekly synthesis. This connects daily progress into weekly patterns and ensures alignment with priorities.

## Philosophy

Weekly synthesis links tactical execution (daily level) to strategic direction (monthly goals). It's where you catch value drift, spot patterns, and realign effort with priorities.

## Instructions

1. **Check current date and week** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get ISO week: `date +"%Y-W%V"` (for file naming)
   - Calculate date range for display

2. **Gather the week's data:**
   - Read daily reviews from `06 Archive/Daily Reviews/` for this week
   - Read session summaries from `06 Archive/Claude Sessions/`
   - Read `01 Now/Works in Progress.md` for active projects

3. **Run the weekly synthesis interview:**

**Collect - What happened:**
- "What were the major accomplishments this week?"
- "Which projects moved forward? Which stalled?"
- "Where did the bulk of time go?"

**Reflect - What matters:**
- "Key insights or learning from this week?"
- "What patterns emerged? (Good and bad)"
- "Any surprises?"

**Align - Priorities check:**
- "Looking at time spent vs stated priorities - any misalignment?"
- "What got attention that shouldn't have?"
- "What didn't get attention that should have?"

**Plan - What's next:**
- "What's the focus for next week?"
- "Any course corrections needed?"

4. **Generate weekly synthesis:**

Create `06 Archive/Weekly Reviews/YYYY-Wnn.md`:

```markdown
# Weekly Synthesis - Week [NN], [Date Range]

## Major Accomplishments
[Significant progress, completions, milestones]

## Projects Active This Week
**Advanced:**
- [[03 Projects/Project A]] - [What moved forward]

**Stalled:**
- [[03 Projects/Project B]] - [Why stalled]

## Key Insights & Patterns

### What's Working
[Patterns of success, effective strategies]

### Challenges
[Recurring problems, areas needing attention]

## Alignment Check
[Honest assessment: Is effort aligned with priorities?]

## Next Week's Focus
**Priority 1:** [Most important thing]
**Priority 2:** [Second priority]

## Daily Reviews This Week
- [[06 Archive/Daily Reviews/YYYY-MM-DD]] - Mon
- [[06 Archive/Daily Reviews/YYYY-MM-DD]] - Tue
```

5. **Display confirmation:**

```
✓ Weekly synthesis saved to: 06 Archive/Weekly Reviews/YYYY-Wnn.md
✓ Projects reviewed: N active, M completed
✓ Next week's focus: [Top priorities]

Weekly synthesis complete.
```

## Guidelines

- **Always check current date:** First step for accurate week boundaries
- **Patterns over details:** Look for recurring themes
- **Honest alignment check:** Catch yourself working on wrong things
- **Forward-looking:** Use insights to improve next week

## Frequency

Run weekly, typically Sunday evening or Monday morning.

## Integration

- **Synthesises daily reviews:** Aggregates daily patterns
- **Informs project planning:** Identifies what needs attention
- **Prevents value drift:** Ensures high-level course correction
