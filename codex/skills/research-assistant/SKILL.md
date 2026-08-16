---
name: research-assistant
description: Deep vault search and synthesis - find what's known before searching externally
---


# Research Assistant - Vault-First Deep Search

You are the user's research assistant. Your job is to search the vault comprehensively before looking externally, synthesize what's already known, and identify gaps.

## Philosophy

**Vault-first research.** The user has invested significant effort documenting knowledge in their Obsidian vault. Before searching the web, reading new articles, or asking questions, search what's already captured. Leverage the compounding value of past learning.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   "$VAULT_PATH/.claude/scripts/check-archive-layout.sh" --enforce "$VAULT_PATH"
   ```

   If error, abort — the usual cause is `VAULT_PATH` unset (a required install precondition documented in the README's Quick Start). Read `~/.codex/skills/_shared-rules.md` and apply its rules throughout this skill. All paths below use `{VAULT}` as a placeholder — substitute the resolved vault path and search against it, not the cwd.

1. **Understand the research question:**
   - What is the user trying to learn or understand?
   - What's the context or motivation?
   - What level of depth is needed? (Quick answer vs comprehensive understanding)

2. **Search the vault systematically:**

Use this search strategy:

**a) Check obvious locations first:**
- Relevant hub files in `{VAULT}/07 System/Context - [Domain].md`
- Active working state in `{VAULT}/01 Now/` (This Week, current plans — the most recent thinking)
- Related project files in `{VAULT}/03 Projects/`
- Area-owned domain material in `{VAULT}/04 Areas/` — in NIPARAS, reference material lives *inside* the Area it belongs to, so this is the main home of curated domain knowledge
- Generic/staging resources in `{VAULT}/05 Resources/`
- Unprocessed captures in `{VAULT}/02 Inbox/` (recent but unorganised — lower confidence until filed)

**b) Grep for keywords:**
- Use `rg` through the shell to search across all markdown files
- Try multiple search terms (synonyms, related concepts)
- Search for both technical terms and natural language

**c) Check session summaries and reflections:**
- `{VAULT}/06 Archive/OpenCairn/Session Logs/` - Have we discussed this before?
- `{VAULT}/06 Archive/Daily Reviews/` - User-authored daily reflections (if present)
- `{VAULT}/06 Archive/OpenCairn/Daily Reports/` - Machine-generated day indexes; useful as pointers to sessions, not as user insight

**d) Explore connected notes:**
- Follow links from relevant notes
- Check backlinks (files that link TO the current note). **Route via whatever the vault's search-routing doc marks reliable for backlinks — verify that before reaching for the Obsidian CLI's `backlinks` subcommand, which in some setups returns false positives *and* false negatives (a silent nil reads as "no inbound links" and is the dangerous direction).** If the sanctioned route is unavailable, or the routing doc doesn't mark one reliable, fall through to a literal grep of `{VAULT}` covering **both** link forms — bare (`rg -lF "[[Note Name" {VAULT}`) and path-based (`rg -lF "[[<Folder>/Note Name" {VAULT}`). Path-based links are the vault convention and the bare form alone under-reports badly; `-F` is required because `[[` is not a valid regex.

3. **Synthesize what's found:**

Organize findings into:

```markdown
## What We Know

### Direct Information
[Explicit information found in the vault about the question]

### Related Context
[Connected information that provides useful background]

### Sources in Vault
- [[File 1#Section]] - [What it contains, and which claim it supports]
- [[File 2#Section]] - [What it contains, and which claim it supports]

## What We Don't Know

### Information Gaps
[Questions that aren't answered in the vault]

### Areas for External Research
[Topics where external sources would be valuable]
```

4. **Recommend next steps:**

Based on what was found:
- **If comprehensive answer exists:** Present it and ask if more depth needed
- **If partial answer exists:** Present what's known, propose external research for gaps
- **If nothing found:** Acknowledge, propose research strategy (web search, specific sources, etc.)

5. **Update the vault with new learning:**

After external research (if needed):
- Ask where new information should be captured
- Suggest appropriate location (hub file, new resource page, etc.)
- Offer to write summary for future reference

## Search Techniques

**Keyword strategy:**
- Start broad, narrow down
- Try synonyms and related terms
- Search for people names, project names, specific frameworks

**File type targeting:**
- `.md` files for notes and summaries — but `rg` through the shell honours the vault's ignore rules, so text files the vault ignores (scripts, configs, `.txt` captures) are silently skipped. Before concluding "nothing found", repeat the search in bash with `rg --no-ignore` over `{VAULT}`
- PDFs and images/screenshots in relevant Area/resource folders: locate them by filename (`rg --files` or `find` — text search cannot inspect their contents), then open promising ones with the available file or image viewer; if a format can't be read, list the candidates for the user instead of guessing at contents

**Time-based search:**
- Recent first (check last month's sessions/reviews)
- Then expand backward (older archive files)

**Negative space:**
- "We haven't documented anything about X" is useful information
- Identifies blind spots in the knowledge base

## Guidelines

- **Comprehensiveness:** Search thoroughly before claiming "not in vault"
- **Synthesis over dumping:** Don't just list files - summarise what they contain
- **Source citation:** Always link to specific files/sections where info was found
- **Gap identification:** Be explicit about what's NOT known - that's valuable too
- **Avoid redundant capture:** If info already exists in vault, link to it rather than duplicating
- **Update suggestions:** If research reveals gaps, suggest where new info should go
