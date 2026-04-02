---
name: landscape-scan
description: Monthly scan of the AI/PKM/tooling landscape for patterns, tools, and practitioner insights relevant to the user's workflow
---

# Landscape Scan - Monthly External Intelligence

You are running a landscape scan. This is a focused, monthly check of external sources for patterns, tools, and practitioner insights relevant to the user's workflow and tooling.

## Philosophy

This is research, not shopping. The goal is "how did they solve X?" over "should I switch to Y?" Surface patterns and architecture insights. A scan that produces zero actionable findings is a valid result - not every month will have something worth adopting.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder - substitute the resolved vault path.

1. **Check current date:**
   ```bash
   date +"%Y-%m-%d"
   ```
   File naming: `YYYY-MM.md`

2. **Load prior scan** (if exists) from `{VAULT}/06 Archive/Landscape Scans/` - read the most recent one to understand what was already found, adopted, or noted. Don't re-report things already classified in a prior scan unless their status has changed.

3. **Scan sources:**

   Use web search and scraping to check these sources. For each, focus on what's new or changed since the last scan.

   **Claude Code ecosystem:**
   - https://github.com/hesreallyhim/awesome-claude-code — curated skills, hooks, slash commands, agent orchestrators, plugins
   - https://github.com/rohitg00/awesome-claude-code-toolkit — comprehensive toolkit (agents, skills, commands, plugins, hooks, rules, templates, MCP configs)
   - https://github.com/travisvn/awesome-claude-skills — skills and workflow customisation
   - https://github.com/ComposioHQ/awesome-claude-skills — practical skills across Claude.ai, Claude Code, and Claude API
   - https://github.com/BehiSecc/awesome-claude-skills — skills collection incl. claude-starter (40 auto-activating skills, TOON format)
   - https://github.com/FlorianBruniaux/claude-code-ultimate-guide — beginner-to-power-user guide with production-ready templates
   - https://github.com/affaan-m/everything-claude-code — config collection with longform guide (skills, hooks, subagents, MCPs, plugins)
   - https://github.com/luongnv89/claude-howto — visual, example-driven guide to every Claude Code feature
   - https://github.com/davepoon/buildwithclaude — plugin marketplace/discovery platform for Claude Code
   - https://awesomeclaude.ai/ — web directory aggregating Claude AI tools, integrations, and resources
   - https://code.claude.com/docs/en/ — official docs (new features, patterns since last scan)

   **Obsidian + Claude PKM systems** (direct OpenCairn comparables):
   - https://github.com/ballred/obsidian-claude-pkm - starter kit with agents, skills, auto-commit hooks, goal hierarchy
   - https://github.com/ArtemXTech/claude-code-obsidian-starter - starter kit with skills for projects, tasks, daily routines
   - https://github.com/ashish141199/obsidian-claude-code - vault template optimised for networked thinking + Claude Code
   - https://github.com/aplaceforallmystuff/daily-patterns-pack - session logging to daily notes, pattern analysis, automations

   **Practitioner writeups** (people building similar systems):
   - Search for recent posts on Claude Code + PKM workflows, Obsidian + AI second brain patterns
   - Obie Fernandez's "Personal CTO Operating System with Claude Code" (Medium)
   - Matt Stockton's "How Claude Code Became My Knowledge Management System"
   - Noah Brier / Every.to - "How to Use Claude Code as a Second Brain" (podcast + transcript)
   - Peter Polgar - "Knowledge workflow 2026 updates: Obsidian, Claude" (polgarp.com)
   - N9O - "PMing with Claude Code" series (n9o.xyz, 4-part, incl. second brain chapter)
   - r/ClaudeCode + r/ClaudeAI - search for recent "second brain", "PKM", "Obsidian" posts

   **AI + productivity thought leaders:**
   - Tiago Forte / Forte Labs (https://fortelabs.com/blog/) - PARA creator, launched "The AI Second Brain" (Mar 2026). Evolving BASB methodology for AI-native workflows.
   - Nat Eliason (https://blog.nateliason.com/) - building OpenClaw (AI agent company), "Build Your Own Software with AI" course. AI agents for personal/business automation.

   **Docs-for-AI / knowledge structuring:**
   - Mintlify - docs-as-code with AI search, structuring for dual human/AI consumption
   - Documentation.AI - AI agents for documentation structure and maintenance
   - GitBook - docs-as-code with AI features

   **PKM landscape:**
   - PKM Weekly newsletter (https://www.pkmweekly.com/) - weekly digest of the space
   - AFFiNE, Tana - AI-native alternatives to Obsidian worth monitoring

   If a source is unreachable or a repo has been deleted/moved, note it as "unavailable" and move on. Flag it in the Sources list updates section so the command file gets cleaned up.

4. **Capability audit pass:**

   Check whether any skill domains now have mature external alternatives that didn't exist (or weren't mature enough) when the skill was written. This is a lightweight check, not a deep audit. Focus on domains where the scan sources surfaced something relevant.

   For each relevant finding, compare against the user's existing skills:
   - Does this replace something we built? (adopt candidate)
   - Does this do something better that we could extract a pattern from? (adapt candidate)
   - Is our implementation still superior? (note and move on)

   If the vault contains a capability audit project doc (e.g. `03 Projects/OpenCairn Capability Audit.md`), update the relevant domain section with any new findings.

5. **Classify findings:**

   For each relevant finding:
   - What does it do?
   - What problem does it solve that the user's system currently handles manually (or doesn't handle)?
   - Classify: **adopt** (use directly), **adapt** (extract the pattern), or **note** (interesting, not actionable now)

6. **Generate scan report:**

   ```bash
   mkdir -p "{VAULT}/06 Archive/Landscape Scans"
   ```

   Create a file at `{VAULT}/06 Archive/Landscape Scans/YYYY-MM.md`:

   ```markdown
   # Landscape Scan - YYYY-MM

   **Sources checked:** [N sources, list any that were unavailable]

   ## Adopt (use directly)
   - [Tool/pattern] - [what it does, why it's relevant, link]

   ## Adapt (extract the pattern)
   - [Pattern] - [how to apply it, link]

   ## Note (interesting, not actionable now)
   - [Thing] - [why it's interesting, when it might become relevant]

   ## Capability audit
   - [Skill domain] - [external tool/pattern found, how it compares to our implementation, classify: adopt/adapt/note/inferior]
   - (or: No new capability-relevant findings this month)

   ## No change since last scan
   - [Sources that had nothing new]

   ## Sources list updates
   - [New sources to add or stale ones to remove from this command]
   ```

7. **Update this command's source list** if any sources should be added or removed (repos deleted, new high-quality sources discovered during the scan). Edit the command file directly.

8. **Display confirmation:**

   ```
   Landscape scan saved to: 06 Archive/Landscape Scans/YYYY-MM.md
   Sources checked: N
   Findings: N adopt, N adapt, N note
   Capability audit: N domains with new findings (or "no new findings")
   Source list updates: [any changes made to this command]
   ```

## Guidelines

- **Research, not shopping.** "How did they solve X?" is more valuable than "should I switch to Y?"
- **Delta over repeat.** Only report what's new since the last scan. Don't re-list stable repos that haven't changed.
- **Update the source list.** If a source goes stale or a new one emerges, update this command file so next month's scan stays current.
- **Quick and focused.** This should take 10-15 minutes, not an hour. Scan headlines and recent commits/posts, don't deep-dive every repo.
- **Honest about signal.** If nothing interesting surfaced this month, say so. A null result is fine.

## Frequency

Run monthly, typically:
- First week of each month
- Or whenever the user explicitly requests it

## Integration with Other Commands

- **Feeds into /quarterly-review:** Quarterly review references landscape scan findings when doing strategic alignment
- **Complements /weekly-review:** Weekly is internal (vault health, progress); landscape scan is external (what's happening outside)
