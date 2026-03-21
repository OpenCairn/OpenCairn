---
name: cornerstones
aliases: [cs, foundations]
description: Surface high-value foundational tasks tagged [CS] across the vault
---

# Cornerstones - Foundational Task Scanner

Cornerstones are high-value foundational tasks that aren't urgent but compound over time. They're tagged `[CS]` in the vault. Because they lack urgency, they tend to sink below the waterline — this command surfaces them.

## Instructions

### 1. Scan the Vault

Use the Grep tool to find all `[CS]` references across `{VAULT}`:

- Search pattern: `\[CS\]`
- Search path: `{VAULT}`
- Use `output_mode: "content"` with `-C 2` (2 lines of context) so the user can see what surrounds each tag
- Exclude `06 Archive/` — archived items aren't actionable

### 2. Group by File

Organise the results by source file. For each file:
- Show the file path (relative to vault root)
- Show each `[CS]` hit with its surrounding context
- If a file has multiple hits, list them all under that file's heading

### 3. Assess Status

For each cornerstone, note whether it appears to be:
- **Open** — no completion marker (`- [ ]` or just a bullet)
- **Done** — has a completion marker (`- [x]`)
- **Stalled** — context suggests no recent progress (e.g., same text for weeks, noted as blocked)

If you can't determine status from the grep context alone, say so — don't guess.

### 4. Present Summary

Output format:

```
## Cornerstones

### [file path relative to vault]
- [CS] [task description] — **[status]**
  > [context snippet if helpful]

### [another file]
- [CS] [task description] — **[status]**

---

**Total:** X cornerstones (Y open, Z done)
```

If no `[CS]` tags are found, say so clearly — the user may not have adopted the tag yet.

## Guidelines

- **Speed over completeness:** This is a quick scan, not a deep audit. Present what grep finds.
- **Don't modify anything.** This is read-only reconnaissance.
- **Cornerstones vs long poles:** Cornerstones (`[CS]`) are foundational tasks that compound — infrastructure, systems, habits. They differ from long poles (critical-path blockers with deadlines). A task can be both, but the tags serve different purposes.

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
