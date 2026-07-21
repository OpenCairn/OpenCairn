---
name: patterns
description: Find patterns, themes, and connections across files related to a topic
---

# Cross-File Patterns

Find patterns, themes, and connections across files related to a topic.

## Usage
`/patterns [search term or topic]`

## Instructions

0. **Resolve the vault path**:
   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```
   If it errors, abort — no vault accessible; don't fall back to a guessed path. `{VAULT}` below is a placeholder — substitute the resolved path in every search (not the cwd, and not a shell variable, which won't persist across tool calls).

   If no search term or topic was supplied, ask the user for one — don't guess.

1. **Search broadly** - Use the Grep tool to find files matching the topic across `{VAULT}`:
   - Search with multiple keyword variations (synonyms, related terms)
   - Check `01 Now/`, `02 Inbox/`, `03 Projects/`, `04 Areas/`, `05 Resources/` for relevant content, plus `07 System/` hub files and `06 Archive/Claude/Session Logs/` — the archive is where evolution-over-time evidence lives. Skip any of these folders that don't exist in this vault and note the skipped locations
   - If an Obsidian MCP search tool is available, use it for richer results (tool names vary by server — check what's registered)
   - **Zero hits after keyword variations:** stop and say so — report the terms and locations searched, suggest broader terms or `/research-assistant` for a deeper dig. Don't force the output template onto an empty result

2. **Read matches** - Prioritise by relevance (title/heading matches, match density) and recency; read the top ~10-15 files first and expand only if the patterns are still thin. For each file read, extract:
   - Key claims or ideas
   - Sources cited
   - Dates (for recency)
   - Any contradictions with other files

3. **Synthesize patterns** - Look for:
   - Recurring themes across sources
   - Evolution of thinking over time
   - Contradictions or tensions
   - Gaps in coverage
   - Connections the user might not have noticed

4. **Output format**:
```markdown
## Patterns: [topic]

### Recurring Themes
- [theme 1]: found in [file1], [file2]
- [theme 2]: found in [file3]

### Evolution
- [Earlier thinking] → [Current thinking]

### Contradictions/Tensions
- [Source A] says X, but [Source B] says Y

### Connections
- [Unexpected link between ideas]

### Gaps
- [What's missing from the collected material]
```

5. **Be concise** - This is for quick pattern recognition, not comprehensive summaries. Aim for actionable insights.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and log observations at the end per that file.
