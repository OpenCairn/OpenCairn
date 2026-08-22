---
name: hibernate
description: Save comprehensive state snapshot before extended travel or breaks - enables context recovery weeks/months later
---


# Hibernate - Extended Break State Snapshot

You are preparing the user for an extended break from regular OpenCairn usage (travel, vacation, sabbatical). Your task is to create a comprehensive state snapshot that enables confident context recovery weeks or months later.

## Philosophy

The park and pickup system assumes session-to-session continuity. But extended breaks (4-month travel, sabbatical, career transition) create context chasms. Hibernate captures:
- **All active projects** and their current states
- **Open loops** across all projects
- **Decisions pending** return
- **Context links** to key files

This is the "big picture" complement to session-level parking.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   "$VAULT_PATH/.claude/scripts/check-archive-layout.sh" --enforce "$VAULT_PATH"
   ```

   If error, abort. Read `~/.codex/skills/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current time: `LC_TIME=C date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'` (the `LC_TIME=C` guard is load-bearing — `%p` expands empty under many non-English locales; same fix as `$park` Step 0)
   - Combined stamp for the snapshot's `**Created:**` field: `YYYY-MM-DD at HH:MMam/pm`

2. **Read comprehensive context:**
   - `{VAULT}/03 Projects/` root docs - active projects (each doc's `bucket:` plus its existing current-state/action structure)
   - `{VAULT}/01 Now/This Week.md` - the day-level SSOT for live status (deadlines, deferrals, current position); reconcile against it per step 3
   - Recent session metadata via `"{VAULT}/.claude/scripts/pickup-scan.sh"` (its default window is the same 10 days) — then read only the session blocks relevant to active projects, not 10 days of logs end-to-end. If the script errors (fresh vault, old bash), fall back to reading the most recent 2-3 session logs directly.
   - Last daily report (if exists) - recent progress
   - Last weekly review (if exists) - patterns and insights

3. **Extract active state:**
   - All project docs in the `03 Projects/` root (root = active; folder location is status)
   - All unchecked open loops from recent sessions
   - All time-sensitive items or deadlines
   - Any "waiting on" dependencies
   - **Reconcile every status fact against This Week.md before it enters the snapshot** (deadlines, review dates, deferrals, "waiting on", current position) — project docs and session logs can lag the day plan by a session or two, and this snapshot is read back weeks/months later, so a stale fact rots the longest. The trap is promoting a *secondary-surface* value (a session-log "Files Updated" line, a project doc's Next Actions pointer, a prior snapshot) to current state: a date that appears in a session log as a window-roll/relocation artefact is not automatically the status it superficially resembles. If This Week.md says the underlying item is deferred/closed/moved, the day plan wins. Per "Never fabricate a specific value": if a status fact can't be traced to This Week.md (or another primary source confirmed this run), generalise it or omit it — don't snapshot a plausible-looking secondary-surface value as fact. **If This Week.md doesn't exist** (it's optional in the template), project docs and session logs are the primary sources — skip the reconciliation pass rather than omitting every status fact.

4. **Interactive interview** (ask the user):
   - **Break duration:** "How long do you expect to be away?" (days/weeks/months)
   - **Expected return date:** "When do you plan to return to regular work?"
   - **Context to preserve:** "What should I remember about your current situation?"
   - **Deliberate deferrals:** "What are you intentionally NOT doing during this break?"
   - **Return priorities:** "What should be your focus when you return?"

5. **Generate hibernate snapshot** at `{VAULT}/06 Archive/Hibernate Snapshots/YYYY-MM-DD-hibernate.md`:

   ```bash
   mkdir -p "{VAULT}/06 Archive/Hibernate Snapshots"
   ```

   Render the block below, then create the snapshot by piping it to `"{VAULT}/.claude/scripts/locked-edit.sh" "{VAULT}/06 Archive/Hibernate Snapshots/YYYY-MM-DD-hibernate.md" --append`. Never redirect or edit the snapshot directly.

```markdown
# Hibernate Snapshot - [Date]

**Created:** [Date and time]
**Expected return:** [User's answer or "Unknown"]
**Break type:** [Travel / Sabbatical / Career transition / etc.]

## Context at Hibernation

[2-3 sentence summary of the user's situation when hibernating - life stage, major transitions, current focus]

## Active Projects (N total)

### [Project Name 1] ⚠️
**State:** [Current state from the project's existing current-state content]
**Last activity:** [Date from the project doc's Last update stamp]
**Open loops:**
- [Open loop from sessions or the project doc]
- [Another open loop]

**Resume context:** [One sentence about where to pick up]
**Links:** [[03 Projects/Project Name]]

### [Project Name 2]
[Same structure]

## Open Loops Across All Work

**High priority (time-sensitive):**
- [Item with deadline or urgency]

**Medium priority (important but not urgent):**
- [Item that matters but can wait]

**Low priority (nice to have):**
- [Item that could be dropped if needed]

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

[Key decisions from last weekly review or recent sessions that provide context]

## Session Links

**Last session:** [[06 Archive/OpenCairn/Session Logs/YYYY-MM-DD]] (Session N - Topic)
**Last daily report:** [[06 Archive/OpenCairn/Daily Reports/YYYY-MM-DD]]
**Last weekly review:** [[06 Archive/OpenCairn/Weekly Reviews/YYYY-Wnn]]

---

*To restore this context: `$awaken` or `$awaken --date=YYYY-MM-DD`*
```

   Each **Session Links** line is conditional: omit the line entirely if no such file exists. Never write a placeholder or guessed wikilink into the snapshot.

6. **Update project docs:** (via `locked-edit.sh`, never a raw edit — project docs are shared planning files, see `_shared-rules.md` §5)
   - Where an active project doc has an explicit current-state section, add "Hibernated YYYY-MM-DD - see hibernate snapshot" there; otherwise leave its structure untouched and rely on the snapshot
   - Optionally add 🛌 emoji to the doc's status line to indicate hibernation (`$awaken` step 10 removes it)

7. **Display confirmation:**

```
✓ Hibernate snapshot saved to: 06 Archive/Hibernate Snapshots/YYYY-MM-DD-hibernate.md
✓ Active projects: N
✓ Open loops captured: N total (X high priority, Y medium, Z low)
✓ Expected return: [Date or "Unknown"]

Hibernate complete. You can disconnect with confidence.

To restore context on return: `$awaken` or `$awaken --date=2026-01-17`
```

## Guidelines

- **Comprehensive, not exhaustive:** Capture the big picture, not every detail. Session files provide detail.
- **Forward-looking:** Focus on what the user needs to know when returning, not historical record.
- **Honest assessment:** If projects are stalled or likely to be dropped, say so.
- **Deliberate deferrals are valuable:** Explicitly documenting "not doing X" prevents guilt/anxiety during break.
- **Return priorities prevent overwhelm:** Narrowing focus to 3 priorities makes return easier.
- **Always check current date/time:** Never assume or cache timestamps.

## Integration

- **Before travel:** Run `$hibernate` after final `$park` before departure
- **After return:** Run `$awaken` to load snapshot and update with changes
- **Multiple hibernations:** Can run multiple times for different break types (file naming includes date)

## Difference from `$park`

| Feature | $park | $hibernate |
|---------|-------|------------|
| Scope | Single session | All active work |
| Frequency | Every session | Extended breaks only |
| Granularity | Fine (decisions, files) | Coarse (projects, priorities) |
| Temporal | Session-to-session | Weeks/months apart |

Both complement each other. Park handles continuity; hibernate handles discontinuity.
