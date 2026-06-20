# Landscape Profile — AI / Claude Code / PKM (default)

The default profile. Tool-adoption lens on the AI / Claude Code / Obsidian-PKM landscape. This is the original landscape-scan domain, ported verbatim; a bare `/landscape-scan` runs this profile and behaves exactly as before.

**One-liner:** AI/Claude Code/PKM landscape — adopt/adapt/note/skip tooling against the user's current workflow and public positioning.

## File naming

- Filename suffix: **none** (display form `YYYY-Www.md`, e.g. `2026-W16.md`).
- Prior-scan glob (executable): **`20[0-9][0-9]-W[0-9][0-9].md`** — anchored so the `.md` follows the week number directly, which excludes both topic-suffixed files like `2026-W16-cybersec.md` and any legacy `YYYY-MM.md` files (neither matches the pattern). Pick the most recent match by parsed week label, or `ls -t` mtime as a cheap proxy.

## Contextualising reads

Relevance is filtered through both "what I do privately" and "what I publicly claim to do."

- **Current Claude Code usage patterns** — sample 2–4 recent files from `{VAULT}/06 Archive/Claude/` (daily logs, weekly reviews, corrections log). Get a feel for session shape, what gets delegated, friction points, and what the user praises.
- **Public-facing work relevant to the domain** — the user's public site(s), if any are listed in CLAUDE.md (e.g. a personal site posting Claude Code / Obsidian / self-hosting content); other sites the user runs for other domains.

## Sources

For each, focus on what's new or changed since the last scan.

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
- https://claude.com/blog — Anthropic engineering/product blog (Claude Code + API updates)
- https://www.anthropic.com/news — Anthropic model and product announcements

**Obsidian + Claude PKM systems** (direct OpenCairn comparables):
- https://github.com/ballred/obsidian-claude-pkm - starter kit with agents, skills, auto-commit hooks, goal hierarchy
- https://github.com/ArtemXTech/claude-code-obsidian-starter - starter kit with skills for projects, tasks, daily routines
- https://github.com/ashish141199/obsidian-claude-code - vault template optimised for networked thinking + Claude Code
- https://github.com/aplaceforallmystuff/daily-patterns-pack - session logging to daily notes, pattern analysis, automations

**Practitioner writeups** (people building similar systems):
- Recent posts on Claude Code + PKM workflows, Obsidian + AI second brain patterns
- Obie Fernandez's "Personal CTO Operating System with Claude Code" (Medium)
- Matt Stockton's "How Claude Code Became My Knowledge Management System"
- Noah Brier / Every.to — "How to Use Claude Code as a Second Brain" (podcast + transcript)
- Peter Polgar — "Knowledge workflow 2026 updates: Obsidian, Claude" (polgarp.com)
- N9O — "PMing with Claude Code" series (n9o.xyz, 4-part, incl. second brain chapter)
- r/ClaudeCode + r/ClaudeAI — search for recent "second brain", "PKM", "Obsidian" posts

**AI + productivity thought leaders:**
- Tiago Forte / Forte Labs (https://fortelabs.com/blog/) — PARA creator, "The AI Second Brain" (Mar 2026). Evolving BASB methodology for AI-native workflows.
- Nat Eliason (https://blog.nateliason.com/) — building OpenClaw, "Build Your Own Software with AI" course. AI agents for personal/business automation.
- **Zvi Mowshowitz (https://thezvi.substack.com/)** — weekly AI roundups; historically high signal on tool launches (OCLI was first surfaced here, buried mid-post).

**Docs-for-AI / knowledge structuring:**
- Mintlify — docs-as-code with AI search, structuring for dual human/AI consumption
- Documentation.AI — AI agents for documentation structure and maintenance
- GitBook — docs-as-code with AI features

**PKM landscape:**
- PKM Weekly newsletter (https://www.pkmweekly.com/) — weekly digest of the space
- AFFiNE, Tana — AI-native alternatives to Obsidian worth monitoring

### Source-specific mandatory-digest rule (Zvi)

- **Mandatory mechanical digest:** fetch *every* Zvi post published since the last scan run. Scan each post end-to-end (not just headlines/TOC) for any Claude Code / AI-tool / PKM / agent-workflow / AI-coding-infra item. Extract every such item regardless of how buried. The OCLI near-miss is the load-bearing precedent — headline-scan is not sufficient for this source.
- **Bootstrap (first-ever scan run):** no prior scan exists, so "since last run" is undefined. Default window: last **4 weeks** of posts. Compute cutoff explicitly: `date -d "4 weeks ago" +%Y-%m-%d`. Acknowledge in the report that this is a cold-start pass.
- **Subsequent runs:** delta from the most recent scan file's date — use `ls -t` (mtime sort) to find the most recent file, then parse its report-date header.
- **Review the Zvi mandatory-digest rule after 3 runs.** The rule is single-point-justified (OCLI only). After the third run with Zvi digest performed, explicitly evaluate: did Zvi surface anything non-obvious that headline-scan would have missed? If no, downgrade to headline-scan with selective deep-read on Claude-Code-adjacent sections. Record the evaluation in that run's report.

## Assessment frame

Two passes per finding. Run both, report both, never collapse to one verdict.

**Fit pass:**
- Does this replace something we already have? (adopt candidate) — *naming a specific local skill here triggers the engine's Step 8 read-the-source gate; don't assert replacement from a name match.*
- Does this extend or complement current workflow? (adapt candidate)
- Is our implementation still superior? (note-and-move)

**Capability pass (independent — do not skip based on fit-pass outcome):**
- What does this *unlock* that isn't being done today?
- Would adopting it change the shape of the work, or just optimise an existing step?
- If the user were willing to pivot or expand usage, does this open a new axis?
- If the tool doesn't slot into current workflow — is that because it's irrelevant, or because it's novel enough to reshape the workflow?

**Why both, always:** novel tools don't pattern-match current workflow by design — the more different a finding feels, the more carefully the capability pass runs. Object lesson: Obsidian CLI (OCLI) was nearly dismissed from a Zvi post because it didn't slot into the then-current vault-search pattern — turned out to be a major search upgrade and is now core infrastructure.

## Obsolescence check

**Value: runs.** *Distinct from the capability pass.* The capability pass asks "what does this finding unlock for the user?" — this asks "does this finding obsolete one of our existing skills?" Two different questions.

Check whether any existing skill domains now have mature external alternatives that didn't exist (or weren't mature enough) when the skill was written. Lightweight, not a deep audit. The engine's Step 8 read-the-source gate governs every comparative claim that names a local skill.

Per relevant finding, compare against the user's existing skills:
- Does this replace something we built? (adopt)
- Does this do something better that we could extract a pattern from? (adapt)
- Is our implementation still superior? (note)

If the vault contains a capability-audit project doc (e.g. `03 Projects/<Capability Audit>.md`), update the relevant domain section.

## Report sections

Insert these in place of the engine's `<<< PROFILE REPORT SECTIONS >>>` marker:

```markdown
## Adopt (use directly)
For each:
- **[Tool/pattern]** — [what it does, link]
  - *Fit:* [how it interacts with current workflow]
  - *Capability:* [what it unlocks that isn't being done today]
  - *Supply-chain cooldown:* [latest version + publish date; N days old; passes / fails ≥3–7 day cooldown; recommendation: install now / pin earlier version vX.Y.Z / defer until YYYY-MM-DD]

## Adapt (extract the pattern)
- **[Pattern]** — [how to apply it, link]
  - *Fit:* …
  - *Capability:* …

## Note (interesting, not actionable now)
- **[Thing]** — [why it's interesting, when it might become relevant]
  - *Fit:* …
  - *Capability:* …

## Skip (hype / low-value)
- **[Thing]** — [why skipped, so it isn't re-surfaced]

## Skill-obsolescence check
- [Skill domain] — [external tool/pattern, how it compares, classify: adopt/adapt/note/inferior]
  - *Source read:* [`$COMMANDS_DIR/<name>.md` read this run + one-line source-based basis | `no file — claim dropped` | `n/a — names no local skill`]
- (or: "No new skill-obsoleting findings this week")
```

Section counts for the Step 12 confirmation line: `N adopt, N adapt, N note, N skip`.
