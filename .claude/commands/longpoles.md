---
name: longpoles
aliases: [lp, critical-path, blockers]
description: Surface all [LP] (longpole) tagged items across the vault — critical-path items that block other work
---

# Longpoles - Critical Path Scanner

You are scanning the vault for items tagged with `[LP]` — longpole items that sit on the critical path and block other work. The goal is a quick, actionable view of what's blocking progress.

## Instructions

### Phase 1: Resolve Vault Path

1. **Resolve vault path** before proceeding:
   ```bash
   if [[ -z "${VAULT_PATH:-}" ]]; then
     echo "VAULT_PATH not set. Set it in your shell profile (e.g., export VAULT_PATH=/path/to/vault)"
     exit 1
   elif [[ ! -d "{VAULT}" ]]; then
     echo "VAULT_PATH={VAULT} does not exist"
     exit 1
   else
     echo "VAULT_PATH={VAULT}"
   fi
   ```
   If error, abort. **Store the resolved absolute path** (e.g. `/home/user/Files`). All references below use `{VAULT}` as a placeholder — substitute the resolved path before executing.

### Phase 2: Find All Longpoles

2. **Grep the vault for `[LP]` tags** using the Grep tool:
   - Search pattern: `\[LP\]`
   - Path: `{VAULT}/`
   - File type filter: `*.md`
   - Use `output_mode: "content"` with `-C 1` (one line of context above and below each hit)
   - Exclude `06 Archive/` — archived items aren't actionable

### Phase 3: Group and Present

4. **Group results by file.** For each file containing longpole items:
   - Show the file path (relative to vault root for readability)
   - Show each `[LP]` item with its surrounding context
   - If the item has a checkbox (`- [ ]` or `- [x]`), note completion status

5. **Output format:**

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

6. **If no `[LP]` items found**, report that clearly:
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
