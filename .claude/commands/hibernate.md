---
name: hibernate
description: Save comprehensive state snapshot before extended travel or breaks - enables context recovery weeks/months later
---

# Hibernate - Extended Break State Snapshot

You are preparing the user for an extended break from regular Claude Code usage (travel, vacation, sabbatical). Your task is to create a comprehensive state snapshot that enables confident context recovery weeks or months later.

## Philosophy

The park and pickup system assumes session-to-session continuity. But extended breaks (4-month travel, sabbatical, career transition) create context chasms. Hibernate captures:
- **All active projects** and their current states
- **Open loops** across all projects
- **Decisions pending** return
- **Context links** to key files

This is the "big picture" complement to session-level parking.

## Instructions

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current time: `date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'`
   - Store for metadata

2. **Read comprehensive context:**
   - `01 Now/Works in Progress.md` - active projects
   - Recent session files (last 7 days) - recent work
   - Last daily review (if exists) - recent progress
   - Last weekly synthesis (if exists) - patterns and insights

3. **Extract active state:**
   - All projects listed as "Active" in Works in Progress
   - All unchecked open loops from recent sessions
   - All time-sensitive items or deadlines
   - Any "waiting on" dependencies

4. **Interactive interview** (ask the user):
   - **Break duration:** "How long do you expect to be away?" (days/weeks/months)
   - **Expected return date:** "When do you plan to return to regular work?"
   - **Context to preserve:** "What should I remember about your current situation?"
   - **Deliberate deferrals:** "What are you intentionally NOT doing during this break?"
   - **Return priorities:** "What should be your focus when you return?"

5. **Generate hibernate snapshot** at `06 Archive/Hibernate Snapshots/YYYY-MM-DD-hibernate.md`:

```markdown
# Hibernate Snapshot - [Date]

**Created:** [Date and time]
**Expected return:** [User's answer or "Unknown"]
**Break type:** [Travel / Sabbatical / Career transition / etc.]

## Context at Hibernation

[2-3 sentence summary of the user's situation when hibernating - life stage, major transitions, current focus]

## Active Projects (N total)

### [Project Name 1] ⚠️
**Status:** [Current state from Works in Progress]
**Last activity:** [Date from WIP]
**Open loops:**
- [ ] [Open loop from sessions or WIP]
- [ ] [Another open loop]

**Resume context:** [One sentence about where to pick up]
**Links:** [[03 Projects/Project Name]]

### [Project Name 2]
[Same structure]

## Open Loops Across All Work

**High priority (time-sensitive):**
- [ ] [Item with deadline or urgency]

**Medium priority (important but not urgent):**
- [ ] [Item that matters but can wait]

**Low priority (nice to have):**
- [ ] [Item that could be dropped if needed]

## Deliberate Deferrals

**Not doing during break:**
- [Thing the user is intentionally pausing]
- [Another deferred activity]

**Reason:** [Why these are deferred - to focus on X, to rest from Y, etc.]

## Return Priorities

**When returning, focus on:**
1. [First priority]
2. [Second priority]
3. [Third priority]

**Avoid:**
- [Distraction or low-value activity to avoid]

## Recent Decisions & Insights

[Key decisions from last weekly synthesis or recent sessions that provide context]

## Session Links

**Last session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]
**Last daily review:** [[06 Archive/Daily Reviews/YYYY-MM-DD]]
**Last weekly synthesis:** [[06 Archive/Weekly Reviews/YYYY-Wnn]]

---

*To restore this context: `/awaken` or `/pickup --hibernate=YYYY-MM-DD`*
```

6. **Update Works in Progress:**
   - Add "Last updated" note: "Hibernated YYYY-MM-DD - see hibernate snapshot"
   - Optionally add 🛌 emoji to active projects to indicate hibernation

7. **Display confirmation:**

```
✓ Hibernate snapshot saved to: 06 Archive/Hibernate Snapshots/YYYY-MM-DD-hibernate.md
✓ Active projects: N
✓ Open loops captured: N total (X high priority, Y medium, Z low)
✓ Expected return: [Date or "Unknown"]

Hibernate complete. You can disconnect with confidence.

To restore context on return: `/awaken` or `/pickup --hibernate=2026-01-17`
```

## Guidelines

- **Comprehensive, not exhaustive:** Capture the big picture, not every detail. Session files provide detail.
- **Forward-looking:** Focus on what the user needs to know when returning, not historical record.
- **Honest assessment:** If projects are stalled or likely to be dropped, say so.
- **Deliberate deferrals are valuable:** Explicitly documenting "not doing X" prevents guilt/anxiety during break.
- **Return priorities prevent overwhelm:** Narrowing focus to 3 priorities makes return easier.
- **Always check current date/time:** Never assume or cache timestamps.

## Integration

- **Before travel:** Run `/hibernate` after final `/park` before departure
- **After return:** Run `/awaken` to load snapshot and update with changes
- **Multiple hibernations:** Can run multiple times for different break types (file naming includes date)

## Difference from `/park`

| Feature | /park | /hibernate |
|---------|-------|------------|
| Scope | Single session | All active work |
| Frequency | Every session | Extended breaks only |
| Granularity | Fine (decisions, files) | Coarse (projects, priorities) |
| Temporal | Session-to-session | Weeks/months apart |

Both complement each other. Park handles continuity; hibernate handles discontinuity.
