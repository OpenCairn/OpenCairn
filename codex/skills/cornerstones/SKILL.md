---
name: cornerstones
description: Surface high-value foundational tasks tagged [CS] across the vault
---


# Cornerstones - Foundational Task Scanner

Cornerstones are high-value foundational tasks that aren't urgent but compound over time. They're tagged `[CS]` in the vault. Because they lack urgency, they tend to sink below the waterline — this command surfaces them.

## Instructions

### 0. Resolve the Vault Path

```bash
"${VAULT_PATH:?VAULT_PATH not set}/.claude/scripts/resolve-vault.sh"
```

If it errors, abort — no vault accessible; don't fall back to a guessed path. `{VAULT}` below is a placeholder — substitute the resolved path.

### 1. Scan the Vault

Use `rg` through the shell to find all `[CS]` references across `{VAULT}`:

- Search pattern: `\[CS\]`
- Search path: `{VAULT}`
- Restrict to Markdown with `--glob '*.md'` — notes are Markdown; without the filter the scan can hit scripts, JSON, or binary sidecars on vaults whose ignore rules don't already limit matches
- Use `-C 2` (2 lines of context) so the user can see what surrounds each tag
- Exclude `06 Archive/` with an `rg` glob exclusion — archived items aren't actionable
- Also drop hits inside frozen or generated artefacts — provenance snapshots, session transcripts, and similar records that quote historical text verbatim (e.g. `07 System/.Provenance/`). A `[CS]` copied into a frozen snapshot is not a live cornerstone
- Drop **mentions of the tag** as opposed to tagged items. A `[CS]` sitting inside running prose, or listed alongside other bare tag tokens (documentation of the tagging scheme, notes about the scanner, examples in a how-to), is describing the tag, not carrying a cornerstone. The tell: the tag isn't the leading marker of a task line, and the line reads as a sentence about tags. These are not mis-tagged items — never surface them for correction

Before classifying any task-shaped hit, read its enclosing heading ancestry (a parent heading may identify a sample even when the nearest heading does not) and the section through the hit. Establish whether it is inside a Markdown fence by locating the opening and closing fence; nearby grep context alone is insufficient. Exclude fenced examples and documented sample tasks. If the available read cannot settle task/example context, retain the hit as **Undetermined — task/example context unresolved**, outside confirmed task/status totals. A checkbox or a plausible deadline does not establish that a sample is live work.

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

- **Undetermined** — the grep context doesn't settle it

Assess status only after task/example context is confirmed. If status remains unclear after reading the enclosing context, mark it **Undetermined** — don't guess. A completed marker takes precedence over an old blocked note; classify an unfinished item as Stalled when explicitly blocked/waiting, otherwise Open.

Put each Undetermined hit only in the separate bucket, with the reason (task/example context unresolved or status unclear). Do not repeat it in a file group or count it as open, done or stalled. Count every retained hit once: total = open + done + stalled + undetermined.

### 4. Present Summary

Output format:

```
## Cornerstones

### [file path relative to vault]
- [CS] [task description] — **[status]**
  > [context snippet if helpful]

### [another file]
- [CS] [task description] — **[status]**

### ❓ Undetermined
- [CS] [task description or verbatim marker] — [file path] — what the context leaves unresolved

---

**Total:** X retained hits (Y open, Z done, W stalled, V undetermined)
```

Not every `[CS]` hit is a task line. Where the tag sits in a heading, a frontmatter or status field, or a note-level label rather than a bullet, quote the line verbatim and label it as a marker — don't manufacture a task description from it:

```
- [CS] marker — `[verbatim line]` — **[status]**
```

If no `[CS]` tags are found, say so clearly — the user may not have adopted the tag yet.

## Guidelines

- **Speed over completeness:** This is a quick scan, not a deep audit. Present what grep finds.
- **Don't modify anything.** This is read-only reconnaissance.
- **Cornerstones vs long poles vs guillotines:** Cornerstones (`[CS]`) are foundational tasks that compound — infrastructure, systems, habits. Long poles (`[LP]`, `$longpoles`) are critical-path items that block other work; guillotines (`[GT]`, `$guillotines`) are hard-deadline items. A task can carry more than one tag — they serve different purposes.

## Skill Monitor

As you execute this skill, follow `~/.codex/skills/_skill-monitor.md`: watch for gaps, and log observations at the end per that file.
