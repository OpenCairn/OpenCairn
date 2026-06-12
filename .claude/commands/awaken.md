---
name: awaken
description: Restore context from hibernate snapshot after extended break - reconnect to pre-break state
argument-hint: "[--date=YYYY-MM-DD — optional, selects a specific snapshot]"
---

# Awaken - Restore from Hibernate

You are helping the user restore context after an extended break from regular work. Your task is to load the most recent hibernate snapshot, update with any changes during the break, and set up for productive return.

## Philosophy

After weeks or months away, bare `/pickup` shows current WIPs but lacks the context of *why* those projects exist or what changed during the break. Awaken bridges the gap by:
- Loading the pre-break state snapshot
- Acknowledging what changed during the break
- Updating priorities based on new reality
- Providing clear next actions

This is the "return from sabbatical" complement to daily pickup.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current time: `LC_TIME=C date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'` (the `LC_TIME=C` guard is load-bearing — `%p` expands empty under many non-English locales; same fix as `/park` step 1)

2. **Find hibernate snapshot:**
   - Check `{VAULT}/06 Archive/Hibernate Snapshots/` for most recent snapshot
   - If multiple exist, use the most recent unless user specifies: `/awaken --date=2026-01-17` (`--date` matches the filename prefix of `YYYY-MM-DD-hibernate.md` exactly; zero or multiple matches → display the candidates and ask)
   - If no snapshot exists, offer to run `/pickup` instead (it auto-extends search window)

3. **Load hibernate snapshot:**
   - Read the full snapshot file
   - Extract: active projects, open loops, return priorities, expected return date
   - Calculate break duration: days between hibernate date and now

4. **Display snapshot summary:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Welcome back[, name from CLAUDE.md — omit if unknown].

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
   - Record completed loops in the awaken summary's "Completed during break" lines (step 8); flip any matching `- [ ]` items in the SSOT files (This Week.md, Tickler, project hubs) to `[x]`. The snapshot itself keeps plain bullets — there are no checkboxes to flip there, and it stays a frozen record.
   - Capture new items from "what changed" in the awaken summary; route the actionable ones to SSOT via step 9 alongside the Immediate Next Actions.
   - Completed or dropped projects → route through `/complete-project` (it owns artefact routing and link-safe archival — don't improvise an archive move here).
   - Update priorities based on new reality

8. **Generate awaken summary** and append to the hibernate snapshot file:

```markdown
---

## Awaken - [Return Date]

**Returned:** [Date and time]
**Break duration:** [N days/weeks/months]
**Actual vs expected:** [On time / Early by X days / Late by X days / Unknown — no expected return set]

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

- [First thing to do]
- [Second thing to do]
- [Third thing to do]

**Note:** These actions are also routed to SSOT per step 9 (This Week.md / Tasks.md, or future-dated Tickler). The list above is a point-in-time record.

### Session Link

**First session post-return:** [placeholder — session numbers are assigned at park time, after this step; back-fill this link at the first `/park` after `/awaken`, or leave the placeholder]
```

9. **Route Immediate Next Actions to SSOT** (write mechanism: `locked-edit.sh` for This Week.md, `write-tickler.sh` for dated Tickler inserts — see `_shared-rules.md` §5):
   - For each action in "Immediate Next Actions" (plus actionable "what changed" items from step 7):
     - If This Week.md exists and is current (its window covers today per `_shared-rules.md` §9) → add to today's or tomorrow's section. Include project/area links (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`, or `→ [[01 Now/Works in Progress#Heading]]`).
     - If This Week.md is stale/missing → add to `01 Now/Tasks.md` — not a today-dated Tickler entry; Tickler is for future-dated triggers (§4), and a genuinely future-dated action goes there via `write-tickler.sh`.
   - Dedup check before each write: grep the target file, Tickler.md, and Tasks.md. Already present somewhere → skip the write; if the new placement supersedes a Tickler copy, delete the Tickler copy per §4 (Tickler SSOT transfer).
   - The awaken doc keeps plain-bullet records; the SSOT files get `- [ ]` checkboxes.

10. **Update Works in Progress** (via `locked-edit.sh`, not the Edit tool — WIP is a shared planning file, see `_shared-rules.md` §5):
   - Update "Last updated" timestamp
   - Update project statuses with post-break reality
   - Remove 🛌 emoji from active projects
   - Completed/dropped projects → `/complete-project` per step 7; remove only their WIP entries here, don't bare-archive project files

11. **Display completion message:**

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
1. Run `/pickup` and tell it what you want to resume (it auto-extends search window)
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
- **Feeds into /weekly-review:** First weekly review post-return can reference awaken summary

## Difference from `/pickup`

| Feature | /pickup | /awaken |
|---------|---------|---------|
| Source | Works in Progress | Hibernate snapshot |
| Scope | Current projects | Pre-break state + what changed |
| Update | Read-only | Interactive update |
| Frequency | Daily/session | Extended breaks only |

Use `/pickup` for yesterday. Use `/awaken` for months ago.
