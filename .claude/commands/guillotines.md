---
name: guillotines
description: Surface all [GT] (guillotine) tagged items across the vault — hard-deadline tasks that foreclose an option or cause irreversible loss if missed, sorted by how close the blade is
---

# Guillotines - Hard Deadline Scanner

You are scanning the vault for items tagged `[GT]` — *guillotine* items: tasks with a hard, immovable deadline where missing the date forecloses the option entirely or causes irreversible damage. Unlike longpoles (which are about *lead time* — start early or they set the schedule), guillotines are about *drop-dead dates* — miss the date and the blade drops, with no recovery and no ramp. The goal is a view sorted by how close each blade is, with anything overdue or imminent flagged loudly.

## Instructions

### 0. Resolve the Vault Path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If it errors, abort — no vault accessible; don't fall back to a guessed path. `{VAULT}` below is a placeholder — substitute the resolved path.

### 1. Establish "today"

Run `date +%Y-%m-%d` first so you can compute days-remaining accurately. Never infer today's date.

### 2. Scan the Vault

Use the Grep tool to find all `[GT]` references across `{VAULT}`:

- Search pattern: `\[GT\]`
- Search path: `{VAULT}`
- Use `output_mode: "content"` with `-C 1` (1 line of context) so the user can see what surrounds each tag
- Exclude `06 Archive/` — archived items aren't actionable. If the Grep tool can't express the exclusion directly, scan the whole vault and drop any hits under `06 Archive/` when grouping

### 3. Extract the Deadline for Each Item

For every `[GT]` hit, pull the hard date from the item text (e.g. "expires 30 Sep 2026", "by 1 Jul", "due 2026-09-30"):

- If a date is present, compute days remaining from today. Verify any ambiguous or weekday-bearing date with `date -d "<date>"` rather than trusting internal computation.
- **Bare dates with no year** (e.g. "by 1 Jul") resolve to the *next* occurrence: if that date in the current year is already past, assume next year. Exception: if the current-year date passed *recently* (within ~90 days), the item may be overdue rather than 9+ months out — flag it as ambiguous instead of silently assuming next year. Echo the resolved absolute date in the output so a mis-parse is visible.
- If **no** date is present, the item is mis-tagged — a guillotine without a deadline is just a task. Surface it separately under "Undated" for correction.

### 4. Sort and Flag

Order items by deadline **ascending — soonest blade first.** Undated items are excluded from the sort and surfaced in their own section (see template below). Apply status markers:

- 🔴 **OVERDUE** — deadline is in the past. The blade has dropped; surface first and loudest.
- 🟠 **IMMINENT** — ≤30 days out.
- 🟡 **APPROACHING** — ≤90 days out.
- ⚪ **DISTANT** — >90 days out.

### 5. Present Summary

```markdown
## Guillotines

**N items across M files** | Today: YYYY-MM-DD

🔴 **OVERDUE**
- [ ] [GT] Item description — deadline DD Mon YYYY (**X days ago**) — `relative/path.md`

🟠 **IMMINENT (≤30d)**
- [ ] [GT] Item description — deadline DD Mon YYYY (**X days left**) — `relative/path.md`

🟡 **APPROACHING (≤90d)**
- [ ] [GT] Item description — deadline DD Mon YYYY (X days) — `relative/path.md`

⚪ **DISTANT (>90d)**
- [ ] [GT] Item description — deadline DD Mon YYYY — `relative/path.md`

⚠ **UNDATED — mis-tagged**
- [ ] [GT] Item with no hard date — `relative/path.md` *(add a deadline or drop the tag)*

---
### Bottom line
The next blade: **[item]** in **X days** (DD Mon YYYY).
```

If no `[GT]` items found, report that clearly:
   ```
   No [GT] items found in the vault. No hard deadlines tagged — or none captured yet.
   ```

## Guidelines

- **Date accuracy is the whole point.** Always anchor on `date` output and verify ambiguous dates with `date -d`. A wrong days-remaining count is worse than no count.
- **Overdue is an emergency.** If the blade has dropped, lead with it — never bury it inside a sorted list.
- **Undated `[GT]` is a bug.** A guillotine with no deadline can't be one; flag it for correction rather than guessing a date.
- **Don't conflate with `[LP]`.** An item can be both a guillotine *and* a longpole (hard deadline *and* long lead time). Report it here for its deadline; `/longpoles` covers its lead time.
- **Speed over comprehensiveness.** Quick scan, not deep analysis. Present what's there; don't infer dependencies.
- **Don't modify anything.** This is read-only. Never edit files during a guillotine scan.
- **Relative paths for display.** Show paths relative to vault root so the output is scannable.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and propose specific edits to this skill at the end.
