---
name: landscape-scan
description: Weekly (or as-needed) scan + digest of AI/Claude Code/PKM landscape — curated-source scan, user-provided URL pile, or both. Contextualises against current workflow AND assesses for latent capability.
---

# Landscape Scan — External Intelligence (Scan + Digest)

A focused external-intelligence pass. Two modes that can run separately or together:

- **Scan mode** — go check a curated list of sources (proactive).
- **Digest mode** — the user has dropped a pile of URLs / tweets / posts they want reviewed (reactive).
- **Both** — run scan, then layer digest on top.

## Philosophy

Research, not shopping. Surface patterns and architecture insights. A run that produces zero actionable findings is a valid result — not every week will have something worth adopting.

**Two lenses, both reported** — fit pass (how it interacts with current workflow) *and* capability pass (what it unlocks that isn't being done today). Operational definition in Step 6. Object lesson behind the discipline: Obsidian CLI (OCLI) was nearly dismissed from a Zvi post because it didn't slot into the then-current vault-search pattern — turned out to be a major search-functionality upgrade and is now core infrastructure. Novel tools don't pattern-match current workflow by design; the more different a finding feels, the more carefully capability pass runs.

## Instructions

### 0. Resolve vault path and load shared rules

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout. All code below uses `{VAULT}` as placeholder — substitute the resolved vault path.

### 1. Current date + file naming

```bash
date +"%Y-W%V"
```

File naming: `YYYY-Www.md` (ISO week, e.g. `2026-W16.md`).

### 2. Mode selection

Determine which mode(s) apply, in precedence order:

- **User said "both" or similar** → both modes. (Explicit user intent wins.)
- **URLs present AND a scan verb ("scan" / "landscape scan" / "run landscape scan")** → both modes.
- **URLs present in the triggering message (or as args), no scan verb** → digest mode only.
- **Scan verb, no URLs** → **ask first**: "Scan mode (curated sources only), or do you also have URLs for a digest pass?" Default to scan-only if the user confirms no URLs. Do NOT lock in scan-only silently — the cost of asking is one question; the cost of mis-classification is the user having to supply URLs mid-run, which forces a mode switch and re-planning of the report structure. **Worked example:** 2026-W17 run was invoked as `/landscape-scan` (scan verb, no URLs in the first message). Assistant locked in scan-only per the pre-existing rule; user had URLs coming and was surprised they needed to be flagged upfront. The ask-first rule prevents the re-plan.
- **Ambiguous** → ask the user: "Scan (curated sources), digest (you have URLs), or both?"

### 3. Contextualising preamble (ALWAYS — before any assessment)

Relevance judgement requires knowing what the user is *already doing* AND what they're *publicly positioning*. Without this, assessments default to generic-audience relevance and miss what actually matters.

Load, proportionate to the scope of the run:

- **Current Claude Code usage patterns** — sample 2–4 recent files from `{VAULT}/06 Archive/Claude/` (daily logs, weekly reviews, corrections log). Get a feel for session shape, what gets delegated, friction points, and what the user praises.
- **Public-facing work relevant to the domain** — e.g. `hedwards.dev` for Claude Code / Obsidian / self-hosting content; other websites the user runs for other domains. Relevance is filtered through both "what I do privately" and "what I publicly claim to do."
- **Prior scan** (if one exists from the last week or two) from `{VAULT}/06 Archive/Landscape Scans/` — don't re-report things already classified unless their status has changed. Sort the folder by file mtime (`ls -t`) rather than by filename — legacy `YYYY-MM.md` files (if any) would sort lexicographically before new `YYYY-Www.md` files and give a stale "most recent."
- **Just-in-time routing-table context** — if a specific finding later touches a CLAUDE.md routing-table topic (health, photography, crypto, etc.), load that context before assessing that finding.

Keep this light — 2–4 reads, not an exhaustive survey. The goal is *calibration*, not total recall.

### 4. Scan mode — curated sources

Only if scan mode is active. For each, focus on what's new or changed since the last scan.

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
  - **Mandatory mechanical digest:** fetch *every* post published since the last scan run. Scan each post end-to-end (not just headlines/TOC) for any Claude Code / AI-tool / PKM / agent-workflow / AI-coding-infra item. Extract every such item regardless of how buried. The OCLI near-miss is the load-bearing precedent — headline-scan is not sufficient for this source.
  - **Bootstrap (first-ever scan run):** no prior scan exists, so "since last run" is undefined. Default window: last **4 weeks** of posts. Compute cutoff explicitly: `date -d "4 weeks ago" +%Y-%m-%d`. Acknowledge in the report that this is a cold-start pass, not a delta pass.
  - **Subsequent runs:** delta from the most recent scan file's date in `{VAULT}/06 Archive/Landscape Scans/` — use `ls -t` (mtime sort) to find the most recent file, then parse its report-date header.

**Docs-for-AI / knowledge structuring:**
- Mintlify — docs-as-code with AI search, structuring for dual human/AI consumption
- Documentation.AI — AI agents for documentation structure and maintenance
- GitBook — docs-as-code with AI features

**PKM landscape:**
- PKM Weekly newsletter (https://www.pkmweekly.com/) — weekly digest of the space
- AFFiNE, Tana — AI-native alternatives to Obsidian worth monitoring

If a source is unreachable or a repo has been deleted/moved, note it as "unavailable" and move on. Flag it in the *Sources list updates* section so the command file gets cleaned up.

### 5. Digest mode — user-provided URL pile

Only if digest mode is active.

- **Fetch all URLs in parallel.** Don't serialise.
- **Handle fetch failures gracefully.** If WebFetch returns 403/429/timeout/blocked (common on npm registry, X/Twitter, Cloudflare-protected sites), try `mcp__firecrawl__firecrawl_scrape` as fallback. If both fail, log the URL under "unfetchable" in the URLs-digested list and continue — don't halt the run. Flag unfetchables in the output so the user can either re-try later, paste content inline, or accept the gap.
- **Verify suspicious sources before trusting the pitch.** Red flags include:
  - Engagement-ratio anomalies (e.g. many retweets, zero likes/replies → bot amplification signature).
  - Self-promotion by the tool's author without independent endorsement.
  - Unverifiable superlative claims ("99% accuracy," "permanent solution to X," "10x faster").
  - Brand-new repo with unusually high star counts (astroturfing in hyped ecosystems).
- **When a tweet/blog points to a tool, fetch the underlying tool's repo or product page** and report on what's actually shipped (last commit, issues, licence, integration pattern) — not just the pitch.
- **Check commit activity on `main`, not just releases.** A stale release doesn't mean the project is dead, and an active release cadence doesn't mean `main` is alive — independent signals, look at both. Worked example: opcode had a v0.2.0 from Aug 2025 *and* a last commit on main from Oct 2025 — both stale, confirming dead-ish, not "release-stale-but-maintained."
- **Verify WebFetch summary claims against raw source when the claim is falsifiable and structural.** If a summary asserts the project is archived, deprecated, forked, superseded, renamed, or rewritten, re-fetch the raw `README.md` (e.g. `https://raw.githubusercontent.com/<owner>/<repo>/main/README.md`) and quote the verbatim text before acting on the claim. WebFetch summarisers occasionally confabulate plausible-sounding structural claims; high-stakes assertions need verbatim confirmation.
- **Flag red flags explicitly in the output.** Don't smooth them over, but don't let them pre-empt capability-pass assessment either.

### 6. Two-pass assessment (BOTH modes)

For every finding worth reporting — from scan sources *or* digest pile:

**Fit pass:**
- Does this replace something we already have? (adopt candidate)
- Does this extend or complement current workflow? (adapt candidate)
- Is our implementation still superior? (note-and-move)

**Capability pass (independent — do not skip based on fit-pass outcome):**
- What does this *unlock* that isn't being done today?
- Would adopting it change the shape of the work, or just optimise an existing step?
- If the user were willing to pivot or expand usage, does this open a new axis?
- If the tool doesn't slot into current workflow — is that because it's irrelevant, or because it's novel enough to reshape the workflow?

Report BOTH passes for each finding. Do not collapse into a single "verdict."

### 7. Skill-obsolescence check (runs regardless of mode)

*Distinct from Step 6's capability pass.* Step 6 asks "what does this finding unlock for the user?" — Step 7 asks "does this finding obsolete one of our existing skills?" Two different questions; run both.

Check whether any existing skill domains now have mature external alternatives that didn't exist (or weren't mature enough) when the skill was written. Lightweight, not a deep audit.

For each relevant finding, compare against the user's existing skills:
- Does this replace something we built? (adopt)
- Does this do something better that we could extract a pattern from? (adapt)
- Is our implementation still superior? (note)

If the vault contains a capability audit project doc (e.g. `03 Projects/OpenCairn Capability Audit.md`), update the relevant domain section.

### 8. Classify findings

For each:
- What does it do?
- What problem does it solve — manually handled or not handled today?
- **Classify:** adopt (use directly) / adapt (extract the pattern) / note (interesting, not actionable now) / skip (hype or low-value — document *why* so next scan doesn't re-surface it).
- **For adopt candidates — compute supply-chain cooldown explicitly.** Days since latest release (npm/PyPI/Docker/etc.) or last commit (for source-install tools). Compare against a ≥3–7 day cooldown window — don't install a package the day it publishes; let downstream users surface supply-chain compromises (malicious publishes, typosquats, compromised maintainer accounts) first. State the actionable recommendation in the output — **install now / pin earlier version vX.Y.Z / defer install until YYYY-MM-DD** — don't leave arithmetic to the user.

### 9. Generate scan report

```bash
mkdir -p "{VAULT}/06 Archive/Landscape Scans"
```

Create a file at `{VAULT}/06 Archive/Landscape Scans/YYYY-Www.md`:

```markdown
# Landscape Scan — YYYY-Www

**Modes run:** [scan / digest / both]
**Date generated:** [YYYY-MM-DD (day-of-week), location if relevant]

## Contextualising reads

- [files/sources loaded in step 3]

## Scan sources checked *(scan mode only)*

- [N sources; flag any unavailable]

## URLs digested *(digest mode only)*

- [N, list each]

## Derived via abstraction-expansion *(only if rule fired this run)*

- [N sources surfaced via the Guidelines category-abstraction rule — NOT in the input pile]

## Unfetchable

- [URLs that failed both WebFetch and firecrawl-scrape, with reason; or "None this run."]

---

*Convention: single-value fields inline at top (`**X:** Y`); multi-item fields as section headings below.*

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

## Red flags flagged
- [Source] — [what was suspicious; was the underlying thing verified or not]

## Skill-obsolescence check
- [Skill domain] — [external tool/pattern, how it compares, classify: adopt/adapt/note/inferior]
- (or: "No new skill-obsoleting findings this week")

## No change since last scan
- [Sources that had nothing new]

## Sources list updates
- [New sources to add or stale ones to remove from this command]

## Actions executed this run
- [Any edits made to CLAUDE.md, memories saved/updated, skills edited, tasks added to This Week.md or project hubs, configuration changes, etc. — anything the scan surfaced that resulted in immediate in-session action before report-write time. Makes the report self-contained rather than relying on the reader to remember what happened in the triggering session. If no in-session actions: "None."]
```

### 10. Update this command's source list

If any sources should be added or removed (repos deleted, new high-quality sources discovered), edit this command file directly.

### 11. Display confirmation

```
Landscape scan saved to: 06 Archive/Landscape Scans/YYYY-Www.md
Modes run: [scan / digest / both]
Sources checked: N    URLs digested: N    Derived: N    Unfetchable: N
Findings: N adopt, N adapt, N note, N skip
Red flags flagged: N
Skill-obsolescence check: N domains with new findings (or "no new findings")
Actions executed this run: N
Source list updates: [any changes made to this command]
```

## Guidelines

- **Research, not shopping.** "How did they solve X?" beats "should I switch to Y?"
- **Two passes, always.** Fit-pass dismissal does not close capability pass. Report both.
- **Delta over repeat.** Only report what's new since the last scan. Don't re-list stable repos that haven't changed.
- **Verify before trusting pitches.** Tweets and blog posts hype; repos and product pages ship. Fetch the underlying thing.
- **Update the source list.** If a source goes stale or a new one emerges, update this command file.
- **Quick and focused.** Scan mode: 10–20 minutes. Digest mode: scales with URL count but still snappy.
- **Expand category abstraction when a direct-match search returns nothing.** If an exact-match search yields zero hits, do not conclude "none exists." Abstract up one level and search again — from "Linux repackage of product X" to "Linux-native alternatives that serve the same need as X," or from "extension for tool Y" to "plugins/wrappers/bridges for tool Y's ecosystem." Worked example: searching "Linux build of Claude Code Desktop redesign" returned no hits; only after abstracting to "GUI frontends for Claude Code CLI on Linux" did CloudCLI / opcode / Code Harness surface. Direct-match null is a capability-pass failure mode if not expanded.
- **Honest about signal.** A null result is fine — say so.
- **Review the Zvi mandatory-digest rule after 3 runs.** The rule is single-point-justified (OCLI only). After the third weekly run with Zvi digest performed, explicitly evaluate: did Zvi surface anything non-obvious that headline-scan would have missed? If no, downgrade to headline-scan with selective deep-read on Claude-Code-adjacent sections. Record the evaluation in that run's report.

## Frequency

Run weekly (typical), or whenever the user explicitly requests it — including ad-hoc digest-only runs when they've batched up a pile of URLs.

## Integration with Other Commands

*Designed to complement — cross-references not currently wired in the consumer skills. Grep `~/.claude/commands/` for "landscape" to verify the integration state before relying on it; if value emerges, add the references into the consumer skills in a separate pass.*

- **Intended to complement /quarterly-review:** quarterly's strategic-alignment step would benefit from landscape-scan findings accumulated over the quarter.
- **Intended to complement /weekly-review:** weekly is internal (vault health, progress); landscape-scan is external (what's happening outside).
