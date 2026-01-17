---
name: daily-review
description: End-of-day reflection - what happened, what matters, what's next
---

# Daily Review - End-of-Day Reflection

You are facilitating a daily review. This is a lightweight end-of-day reflection to capture progress, insights, and open loops.

## Philosophy

Daily reviews bridge individual sessions into coherent days, and days into weeks. Lighter than `/park` but more structured than ad-hoc notes.

## Instructions

1. **Check current date** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get day of week: `date +"%A, %d %b %Y"`

2. **Check if today's session summary exists:**
   - Look for `06 Archive/Claude Sessions/YYYY-MM-DD.md`
   - If exists, read it to understand what happened today
   - If not, ask user to summarise the day

3. **Run the daily review interview:**

**Wins & Progress:**
- "What got done today?"
- "What progress happened on active projects?"

**Insights & Learning:**
- "What did you learn or realise today?"
- "Any decisions made that will shape future work?"

**Challenges & Friction:**
- "What was harder than expected?"
- "Anything to avoid or change going forward?"

**Open Loops & Next:**
- "What's incomplete and needs attention?"
- "What's the most important thing for tomorrow?"

4. **Generate daily summary:**

Create `06 Archive/Daily Reviews/YYYY-MM-DD.md`:

```markdown
# Daily Review - [Day of Week], [Date]

## Wins & Progress
[Bullet list of accomplishments]

## Insights & Learning
[Key realisations, decisions]

## Challenges & Friction
[What was hard, what to avoid]

## Open Loops
- [ ] Uncompleted task 1
- [ ] Uncompleted task 2

## Tomorrow's Focus
**Most important:** [The one thing to prioritise]
**Secondary:** [Other important tasks]

## Sessions Today
- [[06 Archive/Claude Sessions/YYYY-MM-DD#Session 1 - Topic]]
```

5. **Display confirmation:**

```
✓ Daily review saved to: 06 Archive/Daily Reviews/YYYY-MM-DD.md
✓ Open loops: N items
✓ Tomorrow's focus: [Most important thing]

Daily review complete. Sleep well.
```

## Guidelines

- **Always check current date:** First step for accurate file naming
- **Concise, not comprehensive:** Capture highlights, not every detail
- **Forward-looking:** Set up tomorrow for success
- **Pattern detection:** Note recurring friction for weekly synthesis

## Frequency

Run at end of day, typically after last work session but before bed.

## Integration

- **After /park:** If this is last session, consider running daily review
- **Feeds into /weekly-synthesis:** Daily reviews aggregate into weekly patterns
