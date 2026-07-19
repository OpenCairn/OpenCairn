---
name: cornerstones
description: Surface high-value foundational tasks tagged [CS] across the vault
---

# Cornerstones - Foundational Task Scanner

Cornerstones are high-value foundational tasks that aren't urgent but compound over time. They're tagged `[CS]` in the vault. Because they lack urgency, they tend to sink below the waterline — this command surfaces them.

## Instructions

### 0. Resolve the Vault Path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If it errors, abort — no vault accessible; don't fall back to a guessed path. `{VAULT}` below is a placeholder — substitute the resolved path.

### 1. Scan the Vault

Use the Grep tool to find all `[CS]` references across `{VAULT}`:

- Search pattern: `\[CS\]`
- Search path: `{VAULT}`
- Restrict to Markdown with `glob: "*.md"` — notes are Markdown; without the filter the scan can hit scripts, JSON, or binary sidecars on vaults whose ignore rules don't already limit matches
- Use `output_mode: "content"` with `-C 2` (2 lines of context) so the user can see what surrounds each tag
- Exclude `06 Archive/` — archived items aren't actionable. If the Grep tool can't express the exclusion directly, scan the whole vault and drop any hits under `06 Archive/` when grouping

### 2. Group by File

Organise the results by source file. For each file:
- Show the file path (relative to vault root)
- Show each `[CS]` hit with its surrounding context (carry context into the Step 4 summary only where it clarifies the task or its status)
- If a file has multiple hits, list them all under that file's heading

### 3. Assess Status

For each cornerstone, note whether it appears to be:
- **Open** — an unchecked checkbox (`- [ ]`) or a plain bullet with no completion marker
- **Done** — has a completion marker (`- [x]`)
- **Stalled** — context suggests no progress (e.g., explicitly noted as blocked or waiting)

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

**Total:** X cornerstones (Y open, Z done, W stalled)
```

If no `[CS]` tags are found, say so clearly — the user may not have adopted the tag yet.

## Guidelines

- **Speed over completeness:** This is a quick scan, not a deep audit. Present what grep finds.
- **Don't modify anything.** This is read-only reconnaissance.
- **Cornerstones vs long poles vs guillotines:** Cornerstones (`[CS]`) are foundational tasks that compound — infrastructure, systems, habits. Long poles (`[LP]`, `/longpoles`) are critical-path items that block other work; guillotines (`[GT]`, `/guillotines`) are hard-deadline items. A task can carry more than one tag — they serve different purposes.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and propose specific edits to this skill at the end.
