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
- Also drop hits inside frozen or generated artefacts — provenance snapshots, session transcripts, and similar records that quote historical text verbatim (e.g. `07 System/Provenance/`). A `[GT]` copied into a frozen snapshot is not a live deadline
- Note each hit's completion marker: a checked-off item (`- [x]`) is a *met* (or dead) deadline, not a live one — route it to the Done section in Step 4, never to the timeline

### 3. Extract the Deadline for Each Item

For every `[GT]` hit, pull the hard date from the item text (e.g. "expires 30 Sep 2026", "by 1 Jul", "due 2026-09-30"):

- If a date is present, compute days remaining mechanically — `echo $(( ($(date -d "<deadline>" +%s) - $(date -d "<today>" +%s)) / 86400 ))` with `<today>` from Step 1, so both ends anchor at midnight and the result is exact whole days — never by internal arithmetic; month-boundary slips are exactly the errors this skill exists to prevent. Verify any ambiguous or weekday-bearing date with `date -d "<date>"` too.
- **Approximate or partial dates** (e.g. "March 2027", "late Oct") — don't invent a day. Resolve conservatively to the *earliest* day of the stated window for sorting, and prefix the displayed date with `~` so the imprecision is visible.
- **Bare dates with no year** (e.g. "by 1 Jul") resolve to the *next* occurrence: if that date in the current year is already past, assume next year. Exception: if the current-year date passed *recently* (within ~90 days), the item may be overdue rather than 9+ months out — flag it as ambiguous instead of silently assuming next year. Echo the resolved absolute date in the output so a mis-parse is visible.
- If **no** date is present in the grep context, Read the surrounding lines of the source file before classifying — `-C 1` often clips a date sitting in a nearby line or heading. Only if the file genuinely carries no hard date is the item mis-tagged — a guillotine without a deadline is just a task. Surface it separately under "Undated" for correction.
- If a date is present but can't be resolved to an absolute deadline (e.g. the recently-passed bare-date case above), classify it **Ambiguous** rather than guessing.

### 4. Sort and Flag

Order items by deadline **ascending — soonest blade first.** Undated items are excluded from the sort and surfaced in their own section (see template below). Apply status markers:

- 🔴 **OVERDUE** — deadline is in the past. The blade has dropped; surface first and loudest. Applies to *open* items only — a past deadline on a checked-off item (`- [x]`) was met, not missed; list it under **Done** *(tag can be removed)*, outside the timeline.
- 🟠 **IMMINENT** — due today (0 days — call it out as **DUE TODAY**) through ≤30 days out.
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

❓ **AMBIGUOUS**
- [ ] [GT] Item whose deadline can't be resolved — ~DD Mon YYYY? — `relative/path.md` *(clarify the date)*

⚠ **UNDATED — mis-tagged**
- [ ] [GT] Item with no hard date — `relative/path.md` *(add a deadline or drop the tag)*

✅ **DONE** *(tag can be removed)*
- [x] [GT] Met deadline — was DD Mon YYYY — `relative/path.md`

---
### Bottom line
The next blade: **[item]** in **X days** (DD Mon YYYY).
```

Omit any section with no items. Mirror each item's source marker (`- [ ]` / `- [x]` / plain bullet) — don't invent checkboxes. Bottom line adapts: if the soonest dated open item is overdue, lead with "The blade has dropped on **[item]** — X days ago"; if no dated open items exist, "No dated guillotines open."

If no `[GT]` items found, report that clearly:
   ```
   No [GT] items found in the vault. No hard deadlines tagged — or none captured yet.
   ```

## Guidelines

- **Date accuracy is the whole point.** Always anchor on `date` output and verify ambiguous dates with `date -d`. A wrong days-remaining count is worse than no count.
- **Overdue is an emergency.** If the blade has dropped, lead with it — never bury it inside a sorted list.
- **Undated `[GT]` is a bug.** A guillotine with no deadline can't be one; flag it for correction rather than guessing a date.
- **One obligation, one line.** The same deadline duplicated across files (e.g. tickler + project page) is one guillotine — list it once with all source paths rather than inflating the count.
- **Don't conflate with `[LP]`.** An item can be both a guillotine *and* a longpole (hard deadline *and* long lead time). Report it here for its deadline; `/longpoles` covers its lead time.
- **Speed over comprehensiveness.** Quick scan, not deep analysis. Present what's there; don't infer dependencies.
- **Don't modify anything.** This is read-only. Never edit files during a guillotine scan.
- **Relative paths for display.** Show paths relative to vault root so the output is scannable.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and propose specific edits to this skill at the end.
