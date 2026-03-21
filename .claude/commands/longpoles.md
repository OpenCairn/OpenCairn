---
name: longpoles
aliases: [lp, critical-path, blockers]
description: Surface all [LP] (longpole) tagged items across the vault — critical-path items that block other work
---

# Longpoles - Critical Path Scanner

You are scanning the vault for items tagged with `[LP]` — longpole items that sit on the critical path and block other work. The goal is a quick, actionable view of what's blocking progress.

## Instructions

### 1. Scan the Vault

Use the Grep tool to find all `[LP]` references across `{VAULT}`:

- Search pattern: `\[LP\]`
- Search path: `{VAULT}`
- Use `output_mode: "content"` with `-C 1` (1 line of context) so the user can see what surrounds each tag
- Exclude `06 Archive/` — archived items aren't actionable

### 2. Group by File

**Group results by file.** For each file containing longpole items:
   - Show the file path (relative to vault root for readability)
   - Show each `[LP]` item with its surrounding context
   - If the item has a checkbox (`- [ ]` or `- [x]`), note completion status

### 3. Present Summary

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
- **Hottest file:** [file with most open longpoles]
```

If no `[LP]` items found, report that clearly:
   ```
   No [LP] items found in the vault. Nothing on the critical path — or nothing tagged yet.
   ```

## Guidelines

- **Speed over comprehensiveness.** This is a quick scan, not deep analysis. Present what's there; don't try to infer dependencies.
- **Flag completed longpoles.** An `[LP]` on a checked-off item (`- [x]`) is stale — nudge the user to clean it up.
- **Don't modify anything.** This is read-only. Never edit files during a longpole scan.
- **Relative paths for display.** Show paths relative to vault root so the output is scannable.

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
