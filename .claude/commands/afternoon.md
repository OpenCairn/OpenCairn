---
name: afternoon
description: Mid-day recalibration - zoom out, check drift, reprioritise remaining time
---

# Afternoon - Mid-Day Recalibration

You are running the user's afternoon check-in. This is for when they've been in the weeds and need to zoom out: Am I on track? Have I drifted? What's the best use of remaining time?

## Philosophy

The regroup addresses a specific failure mode: **productive drift**. You've been working, but maybe:
- Went down a rabbit hole that felt productive but wasn't priority
- Context-switched into reactive mode (emails, messages, small tasks)
- Lost track of what you set out to do this morning
- Energy shifted and the original plan no longer fits

This is a quick recalibration, not a full review. 2-5 minutes.

## Instructions

### 1. Check current time

```bash
date +"%H:%M"  # current time
date +"%A"     # day of week
```

Note roughly how much working time remains today.

### 2. Quick Status Check (auto)

Read:
- **Works in Progress:** `01 Now/Works in Progress.md` - what's meant to be priority?
- **Today's sessions:** `06 Archive/Claude Sessions/YYYY-MM-DD.md` - what's been done so far?
- **This morning's intention:** Check if `/morning` set a "one thing" for today

### 3. Present Current State

Display concisely:

```
## Afternoon Check-in - [Time]

**Time remaining:** ~[N] hours of working time

**Morning's intention:** [If set, or "None set"]

**Done so far:**
- [x] Task 1
- [x] Task 2

**Active projects (from WIP):**
- [Project] - [current status]
- [Project] - [current status]
```

### 4. Drift Check

Ask:
> "How's the day going? On track, drifted, or intentionally pivoted?"

**If on track:** Quick affirmation, ask if priorities still make sense for remaining time.

**If drifted:** No judgment. Ask:
> "What pulled you away? And is that actually more important, or just more urgent/interesting?"

Help distinguish:
- **Legitimate pivot:** Something genuinely more important came up - update priorities
- **Productive drift:** Felt productive but wasn't the priority - acknowledge and redirect
- **Reactive mode:** Got pulled into small tasks/communications - help batch or defer

**If intentionally pivoted:** Note the new priority, update WIP if needed.

### 5. Reprioritise Remaining Time

Ask:
> "Given what's left today, what's the best use of your remaining time?"

Help structure:

```
**Remaining priorities:**
1. [Top priority] - [why now]
2. [Secondary] - [if time]
3. [Defer to tomorrow] - [can wait]
```

Consider:
- Energy levels (afternoon slump = different task types)
- Time-sensitive items
- Momentum (sometimes continuing what you're in is right)
- Diminishing returns (sometimes stopping is right)

### 6. Output (minimal)

**Most regroups:** No artifact. The recalibration was the point.

**If priorities significantly shifted:** Update `01 Now/Works in Progress.md` with new status/priorities.

**If actionable decisions made:** Note them in today's session file if one exists.

### 7. Close

Quick and direct:

```
✓ Recalibrated
✓ Priority: [Top item for remaining time]

Go.
```

Or if it was a "you're on track" regroup:

```
You're on track. Keep going.
```

## Guidelines

- **Quick:** 2-5 minutes. This isn't a full review.
- **No guilt:** Drift happens. The point is catching it, not beating yourself up.
- **Energy-aware:** Afternoon brain is different from morning brain - adjust expectations
- **Permission to stop:** Sometimes the right answer is "you've done enough today"
- **Flexible timing:** Despite the name, use whenever you feel scattered - 10am, 2pm, 6pm
- **Never use park-language:** Do not say "Parked", "Shutdown complete", or similar /park closings. Even if user casually says "park this", use "Recalibrated" or "Keep going" - this is NOT a session-ending command and using park-language implies /park was run when it wasn't.

## Triggers

This command should trigger when the user says:
- "regroup"
- "recalibrate"
- "where was I"
- "what should I be doing"
- "am I on track"
- "afternoon check"
- "midday check"

## Integration

- **Reads from:** Works in Progress, today's Claude Sessions
- **May update:** Works in Progress (if priorities shifted)
- **Complements:** `/morning` (start of day), `/goodnight` (end of day), `/park` (end of session)
- **Not a replacement for:** `/park` (regroup doesn't close sessions, just recalibrates)
