---
name: daily-review
description: End-of-day reflection - what happened, what matters, what's next
---

# Daily Review - End-of-Day Reflection

You are facilitating the user's daily review. This is a lightweight end-of-day reflection to capture progress, insights, and open loops.

## Philosophy

Daily reviews create temporal context - they bridge individual sessions into coherent days, and days into weeks. This is lighter than `/park` (which handles individual work sessions) but more structured than ad-hoc notes.

## Instructions

1. **Check current date** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get day of week: `date +"%A, %d %b %Y"` (for friendly display)
   - Use this for file paths and headers

2. **Check if today's session summary exists:**
   - Look for `06 Archive/Claude Sessions/YYYY-MM-DD.md` (using current date from step 1)
   - If it exists, read it to understand what happened today
   - If not, ask the user to summarise the day

3. **Run the daily review interview:**

Ask these questions in order:

**Wins & Progress:**
- "What got done today? (Work, personal, both)"
- "What progress happened on active projects?" (Reference `01 Now/Works in Progress.md`)

**Insights & Learning:**
- "What did you learn or realise today?"
- "Any decisions made that will shape future work?"

**Challenges & Friction:**
- "What was harder than expected?"
- "What caused frustration or delay?"
- "Anything to avoid or change going forward?"

**Open Loops & Next:**
- "What's incomplete and needs attention?"
- "What's the most important thing for tomorrow?"
- "Any time-sensitive items?"

4. **Ensure directory exists:**
   - Check if `06 Archive/Daily Reviews/` directory exists
   - If not, create it: `mkdir -p "06 Archive/Daily Reviews"`
   - This prevents first-run failures

5. **Generate daily summary:**

Create a file at `06 Archive/Daily Reviews/YYYY-MM-DD.md` (using current date from step 1):

```markdown
# Daily Review - [Day of Week], [Date]

## Wins & Progress
[Bullet list of accomplishments, progress on projects]

## Insights & Learning
[Key realisations, decisions, learning]

## Challenges & Friction
[What was hard, what caused delays, what to avoid]

## Open Loops
- [ ] Uncompleted task 1
- [ ] Uncompleted task 2
- [ ] Time-sensitive item 3

## Tomorrow's Focus
**Most important:** [The one thing to prioritise tomorrow]
**Secondary:** [Other important tasks]

## Sessions Today
[Links to today's Claude sessions, if any]
- [[06 Archive/Claude Sessions/YYYY-MM-DD#Session 1 - Topic]]
- [[06 Archive/Claude Sessions/YYYY-MM-DD#Session 2 - Topic]]
```

6. **Update Works in Progress** (if needed):
   - Scan for any projects that had significant progress today
   - Update `01 Now/Works in Progress.md` with today's status

7. **Display confirmation:**

```
✓ Daily review saved to: 06 Archive/Daily Reviews/YYYY-MM-DD.md
✓ Open loops: N items
✓ Tomorrow's focus: [Most important thing]

Daily review complete. Sleep well.
```

## Guidelines

- **Always check current date:** First step - run `date` command for accurate file naming and timestamps. Never assume.
- **Concise, not comprehensive:** Capture highlights, not every detail
- **Forward-looking:** The goal is to set up tomorrow for success
- **Pattern detection:** Note recurring friction or insights for weekly synthesis
- **Session integration:** Link to today's session summaries for full context
- **Natural language:** Write in the user's voice - direct, outcome-focused

## Frequency

Run this at end of day, typically after the last work session but before bed. Can be triggered:
- Explicitly with `/daily-review`
- As part of `/park` for the last session of the day
- When the user says "end of day" or similar phrases

## Integration with Other Commands

- **After /park:** If this is the last session, run daily review
- **Feeds into /weekly-synthesis:** Daily reviews are synthesized into weekly patterns
- **Updates Works in Progress:** Keep project status current

This creates a **daily rhythm** that complements session-level granularity.
