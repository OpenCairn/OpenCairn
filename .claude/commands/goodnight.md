---
name: goodnight
description: End-of-day status report - inventory loops, set tomorrow's queue, close cleanly
---

# Goodnight - End-of-Day Status Report

You are running the user's end-of-day operational close-out. This is a technical/PM-focused review - think engineering standup for yourself, not therapy session.

## Philosophy

The goal is clean handoff to tomorrow-you:
- **Inventory** - what's the state of everything?
- **Accountability** - what got done?
- **Queue** - what's the priority sequence for tomorrow?
- **Context** - what would tomorrow-you need to know to hit the ground running?

This is the complement to `/morning` - morning surfaces the landscape, goodnight closes the books.

## Instructions

### 1. Check current date/time

```bash
date +"%A, %d %b %Y"  # friendly display
date +"%Y-%m-%d"       # for file paths
```

### 2. Gather Today's Activity (auto)

Read and compile:
- **Today's sessions:** Check `06 Archive/Claude Sessions/YYYY-MM-DD.md` for today's date
- **Works in Progress:** Read `01 Now/Works in Progress.md` for project states
- **Completed tasks:** Extract from session summaries

### 3. Present Status Report

Display concisely:

```
## Today's Report - [Day, Date]

**Sessions:** N
**Projects touched:** [list]

### Completed
- [x] Task 1
- [x] Task 2

### Open Loops (by project)
**[Project A]**
- [ ] Loop 1
- [ ] Loop 2

**[Project B]**
- [ ] Loop 1

**Unassigned**
- [ ] Orphan loop
```

### 4. Quick Debrief (brief, optional)

Ask:
> "Anything not captured in sessions? Tasks done outside Claude, decisions made, blockers hit?"

- If yes: add to inventory
- If no: proceed

### 5. Set Tomorrow's Queue

Ask:
> "What's the priority order for tomorrow?"

Help structure as:

```
### Tomorrow's Queue
1. **[Must-do]** - [why it's priority]
2. **[Should-do]** - [context]
3. **[If time]** - [nice to have]

**Blockers/Dependencies:**
- [Anything waiting on external input]
```

If the user doesn't have strong opinions, suggest based on:
- Time-sensitive items first
- Blocked items need unblocking
- High-momentum items worth continuing

### 6. Generate Daily Report

Create file at `06 Archive/Daily Reports/YYYY-MM-DD.md`:

```markdown
# Daily Report - [Day], [Date]

## Sessions
- Session 1: [Topic] - [outcome]
- Session 2: [Topic] - [outcome]

## Completed
- [x] Task 1
- [x] Task 2

## Open Loops

### [Project A]
- [ ] Loop 1
- [ ] Loop 2

### [Project B]
- [ ] Loop 1

### Unassigned
- [ ] Orphan loop

## Tomorrow's Queue
1. **[Priority 1]** - [why]
2. **[Priority 2]** - [context]
3. **[Priority 3]** - [if time]

## Blockers
- [Item] - waiting on [what]

## Notes
[Any context tomorrow-you needs]

---
*Links:*
- Sessions: [[06 Archive/Claude Sessions/YYYY-MM-DD]]
- Previous: [[06 Archive/Daily Reports/YYYY-MM-DD]] (yesterday if exists)
```

Ensure directory exists first:
```bash
mkdir -p "06 Archive/Daily Reports"
```

### 7. Update Works in Progress

If any project status changed significantly today, update `01 Now/Works in Progress.md` with current state.

### 8. Close

```
✓ Report saved: 06 Archive/Daily Reports/YYYY-MM-DD.md
✓ Open loops: N items across M projects
✓ Tomorrow's #1: [Priority item]

Goodnight.
```

## Guidelines

- **Technical, not emotional:** Focus on state and status, not feelings
- **Accountability:** The completed list matters - own what got done
- **Forward-looking:** Tomorrow's queue is the point - set yourself up
- **Quick:** This should take 3-5 minutes unless there's a lot to capture
- **No guilt:** If it was a low-output day, just note the status honestly

## Triggers

This command should trigger when the user says:
- "goodnight"
- "end of day"
- "close out"
- "wrap up the day"
- "done for the day"

## Integration

- **Reads from:** Claude Sessions (today), Works in Progress
- **Creates:** Daily Reports
- **Updates:** Works in Progress (if needed)
- **Complements:** `/morning` (start of day), `/afternoon` (mid-day), `/park` (end of session)
- **Replaces:** `/daily-review` (deprecated)
