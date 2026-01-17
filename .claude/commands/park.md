---
name: park
aliases: [shutdown-complete]
description: End session with Cal Newport "shutdown complete" - document work, open loops, enable frictionless pickup
---

# Park - Session Parking

You are ending a work session. Your task is to create a session summary that enables confident rest and frictionless pickup.

## Instructions

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"` (for session file naming)
   - Get current time: `date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'` (for session timestamp)

2. **Read the conversation** to understand what was accomplished and what remains open.

3. **Determine session metadata:**
   - Session number for today (check existing file, or start at 1)
   - Topic/name for this session (concise, descriptive)
   - Related project (if applicable)

4. **Generate session summary:**

```markdown
## Session N - [Topic/Name] ([Time])

### Summary
[2-3 sentence narrative of what was accomplished]

### Next Steps / Open Loops
- [ ] Specific actionable item
- [ ] Another open loop

### Files Created/Updated
- path/to/file.md - [what changed]

### Pickup Context
**For next session:** [One sentence about where to pick up]
**Previous session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N-1]]
**Project:** [[03 Projects/Project Name]] (if applicable)
```

5. **Write the summary:**
   - Append to `06 Archive/Claude Sessions/YYYY-MM-DD.md`
   - If file doesn't exist, create it with header: `# Claude Session - YYYY-MM-DD`

6. **Update Works in Progress** (if session relates to an active project):
   - Update project status with today's progress
   - Update "Last updated" timestamp at top of file

7. **Display completion message:**

```
✓ Session summary saved to: 06 Archive/Claude Sessions/YYYY-MM-DD.md
✓ Open loops: N items

Shutdown complete. You can rest.

To pickup: `/pickup`
```

## Guidelines

- **Always check current date/time:** Run `date` command for accurate timestamps
- **Completed work has no open loops:** Write "None - work completed" for finished sessions
- **Open loops clarity:** Each loop should be specific enough to resume without re-reading
- **One-sentence pickup:** The "For next session" line should be immediately actionable
- **Session naming:** Use descriptive names that make sense weeks later

## Cue Word Detection

This command should trigger when user says:
- "wrapping up"
- "done for now"
- "packing up"
- "shutdown complete"
- "park"

## Philosophy

The goal is Cal Newport's "shutdown complete" ritual - explicit acknowledgement of open loops so the mind can truly rest. Every incomplete task is captured in a trusted system.

**For completed work:** Park it anyway. The psychological closure is valuable, and you'll want the history later.
