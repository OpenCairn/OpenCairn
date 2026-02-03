---
name: awaken
aliases: [restore-hibernate, return]
description: Restore context from hibernate snapshot after extended break - reconnect to pre-break state
---

# Awaken - Restore from Hibernate

You are helping the user restore context after an extended break from regular work. Your task is to load the most recent hibernate snapshot, update with any changes during the break, and set up for productive return.

## Philosophy

After weeks or months away, the 10-day pickup window shows nothing relevant. Awaken bridges the gap by:
- Loading the pre-break state snapshot
- Acknowledging what changed during the break
- Updating priorities based on new reality
- Providing clear next actions

This is the "return from sabbatical" complement to daily pickup.

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

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current time: `date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'`
   - Calculate time since last activity

2. **Find hibernate snapshot:**
   - Check `$VAULT_PATH/06 Archive/Hibernate Snapshots/` for most recent snapshot
   - If multiple exist, use the most recent unless user specifies: `/awaken --date=2026-01-17`
   - If no snapshot exists, offer to run `/pickup` with extended window instead

3. **Load hibernate snapshot:**
   - Read the full snapshot file
   - Extract: active projects, open loops, return priorities, expected return date
   - Calculate break duration: days between hibernate date and now

4. **Display snapshot summary:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Welcome back, the user.

Last hibernate: [Date] ([N] days ago)
Expected return: [Date from snapshot] (Actual: today)
Break duration: [N days/weeks/months]

Snapshot context:
[2-3 sentence summary from snapshot about situation at hibernation]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Loading pre-break state...
```

5. **Interactive reorientation** (ask the user):
   - **What changed during break:** "What happened during the break that affects your work/priorities?"
   - **Completed offline:** "Did you complete any of the open loops while away?"
   - **New priorities:** "Have your priorities shifted since the snapshot?"
   - **Dropped projects:** "Are any of the active projects no longer relevant?"
   - **Time-sensitive updates:** "Any new deadlines or time-sensitive items?"

6. **Display active projects from snapshot:**

```
Active projects at hibernation (N total):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. [Project Name 1] ⚠️
   Status: [Status from snapshot]
   Open loops: [N items]
   → [[03 Projects/Project Name 1]]

2. [Project Name 2]
   Status: [Status from snapshot]
   Open loops: [N items]
   → [[03 Projects/Project Name 2]]

[etc.]

Which projects are still active? [Enter numbers, 'all', or 'none']
>
```

7. **Update based on the user's answers:**
   - Mark completed loops as `[x]`
   - Add new items from "what changed"
   - Archive dropped projects
   - Update priorities based on new reality

8. **Generate awaken summary** and append to the hibernate snapshot file:

```markdown
---

## Awaken - [Return Date]

**Returned:** [Date and time]
**Break duration:** [N days/weeks/months]
**Actual vs expected:** [On time / Early by X days / Late by X days]

### What Changed During Break

[Bullet list from the user's answers]

### Updated Project Status

**Still active:**
- [Project A] - [Updated status]
- [Project B] - [Updated status]

**Completed during break:**
- [Project C] - [Outcome]

**Dropped/deferred:**
- [Project D] - [Reason]

### Updated Priorities

1. [Current top priority]
2. [Second priority]
3. [Third priority]

**Changes from pre-break:** [What shifted and why]

### Immediate Next Actions

- [ ] [First thing to do]
- [ ] [Second thing to do]
- [ ] [Third thing to do]

### Session Link

**First session post-return:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]
```

9. **Update Works in Progress:**
   - Update "Last updated" timestamp
   - Update project statuses with post-break reality
   - Remove 🛌 emoji from active projects
   - Archive completed/dropped projects

10. **Display completion message:**

```
✓ Hibernate snapshot loaded from: [Date]
✓ Break duration: [N days/weeks/months]
✓ Projects updated: [N still active, M completed, P dropped]
✓ Works in Progress synchronized

Welcome back. You're oriented.

Immediate next actions:
1. [First action]
2. [Second action]
3. [Third action]

Ready to continue: What would you like to work on?
```

## Guidelines

- **Acknowledge the gap:** Explicitly state how long the user was away - this validates the discontinuity
- **Update, don't just restore:** The snapshot is a starting point, not gospel. Reality changed during the break.
- **Expect drift:** Projects that seemed important before the break may feel irrelevant after. That's normal.
- **Narrow focus on return:** Don't try to resume everything at once. Pick 1-3 priorities.
- **Link forward and backward:** Update the hibernate snapshot with awaken summary for future reference
- **Always check current date/time:** Never assume or cache timestamps.

## Handling Edge Cases

**If no hibernate snapshot exists:**
```
No hibernate snapshot found.

You can:
1. Run /pickup with extended window: /pickup --days=90
2. Manually review Works in Progress and recent sessions
3. Start fresh if the gap is too large

What would you like to do?
```

**If multiple snapshots exist:**
- Default to most recent
- Allow explicit selection: `/awaken --date=2026-01-17`
- Display list if ambiguous:
  ```
  Multiple hibernate snapshots found:
  1. 2026-01-17 (3 months ago) - Before travel
  2. 2025-12-20 (4 months ago) - Before holidays

  Which snapshot to restore? [1/2]
  ```

**If expected return date passed:**
```
Note: Expected return was [Date] ([N] days ago)
You're returning [N] days later than planned.
This is fine - life happens. Priorities may have shifted more than expected.
```

## Integration

- **After extended break:** Run `/awaken` as first command when returning to work
- **Complements /pickup:** If break was short (< 2 weeks), `/pickup` may suffice. Use `/awaken` for month+ gaps.
- **Updates hibernate snapshot:** Creates bidirectional record (snapshot → awaken summary)
- **Feeds into /weekly-synthesis:** First weekly synthesis post-return can reference awaken summary

## Difference from `/pickup`

| Feature | /pickup | /awaken |
|---------|---------|---------|
| Window | Last 10 days | Weeks/months |
| Source | Session files | Hibernate snapshot |
| Scope | Sessions | Projects |
| Update | Read-only | Interactive update |
| Frequency | Daily/session | Extended breaks only |

Use `/pickup` for yesterday. Use `/awaken` for months ago.
