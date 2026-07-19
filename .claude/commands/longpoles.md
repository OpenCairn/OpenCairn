---
name: longpoles
description: Surface all [LP] (longpole) tagged items across the vault — critical-path items that block other work
---

# Longpoles - Critical Path Scanner

You are scanning the vault for items tagged with `[LP]` — longpole items that sit on the critical path and block other work. The goal is a quick, actionable view of what's blocking progress.

## Instructions

### 0. Resolve the Vault Path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If it errors, abort — no vault accessible; don't fall back to a guessed path. `{VAULT}` below is a placeholder — substitute the resolved path.

### 1. Scan the Vault

Use the Grep tool to find all `[LP]` references across `{VAULT}`:

- Search pattern: `\[LP\]`
- Search path: `{VAULT}`
- Use `output_mode: "content"` with `-C 1` (1 line of context) so the user can see what surrounds each tag
- Exclude `06 Archive/` — archived items aren't actionable. If the Grep tool can't express the exclusion directly, scan the whole vault and drop any hits under `06 Archive/` when grouping
- Also drop hits inside frozen or generated artefacts — provenance snapshots, session transcripts, and similar records that quote historical text verbatim (e.g. `07 System/Provenance/`). A checkbox copied into a frozen snapshot is not a live task

### 2. Group by File

**Group results by file.** For each file containing longpole items:
   - Show the file path (relative to vault root for readability)
   - Derive the group heading from the file's name or its parent project/area folder — whichever reads as the natural short label; don't open files just to name the heading
   - Show each `[LP]` item with its surrounding context
   - If the item has a checkbox (`- [ ]` or `- [x]`), note completion status

### 3. Present Summary

Run `date +%Y-%m-%d` for the Scanned date — never infer it.

```markdown
## Longpoles

**N items across M files** | Scanned: YYYY-MM-DD

### [Project or Area Name] — `relative/path/to/file.md`
- [ ] [LP] Item description (with context)
- [x] [LP] Completed item *(done — consider removing tag)*

### [Another File] — `relative/path/to/other.md`
- [ ] [LP] Another blocking item

---

### Summary
- **Open:** X items still blocking
- **Done:** Y items completed (can be cleaned up)
- **Hottest file:** [file with most open longpoles, or "none" if no items are open]
```

If no `[LP]` items found, report that clearly:
   ```
   No [LP] items found in the vault. Nothing on the critical path — or nothing tagged yet.
   ```

## Guidelines

- **Speed over comprehensiveness.** This is a quick scan, not deep analysis. Present what's there; don't try to infer dependencies.
- **Flag completed longpoles.** An `[LP]` on a checked-off item (`- [x]`) is stale — nudge the user to clean it up.
- **Lead time, not deadlines.** `[LP]` is for long-lead-time items. A task whose risk is a hard drop-dead date belongs in `[GT]` / `/guillotines` instead — an item can carry both.
- **Don't modify anything.** This is read-only. Never edit files during a longpole scan.
- **Relative paths for display.** Show paths relative to vault root so the output is scannable.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and propose specific edits to this skill at the end.
