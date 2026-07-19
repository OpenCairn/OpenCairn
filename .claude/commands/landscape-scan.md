---
name: landscape-scan
description: Topic-parameterised external-intelligence scan + digest. Default topic is the AI/Claude Code/PKM landscape; pass a topic name (e.g. `cybersec`) to run a different profile. Curated-source scan, user-provided URL pile, or both — assessed through the active profile's lens.
---

# Landscape Scan — External Intelligence (Scan + Digest)

A focused external-intelligence pass. The **engine** (this file) is domain-agnostic orchestration: mode selection, fetch mechanics, verification discipline, supply-chain cooldown, report wrapper. The **profile** (a file under `landscape-profiles/`) supplies everything domain-specific: which sources to scan, what to read for context, how to assess findings, and which report sections to emit.

Two modes that can run separately or together:

- **Scan mode** — go check the profile's curated source list (proactive).
- **Digest mode** — the user has dropped a pile of URLs / tweets / posts they want reviewed (reactive).
- **Both** — run scan, then layer digest on top.

## Philosophy

Research, not shopping. Surface patterns, architecture insights, and (for threat-style profiles) exposure. A run that produces zero actionable findings is a valid result — not every week has something worth acting on.

The assessment *frame* lives in the profile, because what "actionable" means is domain-specific:
- a tool-adoption profile (the default `ai-cc-pkm`) asks "should this change how I work?" — **fit** + **capability** passes;
- a threat-intel profile (`cybersec`) asks "does this reach something I run, and what do I do about it?" — **exposure** + **action** passes.

The engine never collapses a profile's passes into a single verdict, and never skips the second pass based on the first.

## Instructions

### 0. Resolve vault path and load shared rules

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Set **`COMMANDS_DIR`** = the directory holding this command's sibling files (`_shared-rules.md`, the profiles). Claude Code does not expose a slash-command's own source path, so resolve it deterministically: prefer `~/.claude/commands/` if it exists, else `{VAULT}/.claude/commands/`; if both exist, use `~/.claude/commands/` and note in the report that both copies exist and resolution was heuristic — the two copies should match after a `/sync-template`, so a divergence between them is itself worth surfacing. (If a future Claude Code build *does* expose the source path, prefer whichever directory this file actually loaded from, since the two copies can diverge between syncs.) Read `_shared-rules.md` from `COMMANDS_DIR` and apply its rules throughout. All code below uses `{VAULT}` and `COMMANDS_DIR`/`$COMMANDS_DIR` as **placeholders** — substitute the resolved vault path and commands directory; they are not pre-set shell variables.

**Environment assumption:** this engine assumes a GNU/Linux shell (the profiles call `date -d`, `lsb_release`, `dpkg-query`), the WebSearch tool (the cybersec profile's vendor-advisory discovery), and the Firecrawl MCP for fetch-fallback. These are not portability-guarded — on a non-GNU shell or an install without Firecrawl the affected call fails loudly (a visible error, not a silent wrong answer), at which point the executor substitutes the platform equivalent (e.g. BSD `date -j`, the OS's own package query) or falls back to WebFetch-only. Documented as assumed rather than branched.

### 1. Resolve topic and load the profile

Determine the **topic** from the invocation:

- A topic word in the triggering message or args (e.g. `/landscape-scan cybersec`, "run a cybersec landscape scan") → that topic.
- No topic word → default topic **`ai-cc-pkm`** (preserves the original AI/Claude Code/PKM behaviour exactly).

Resolve the profile file: `$COMMANDS_DIR/landscape-profiles/<topic>.md` (under the `COMMANDS_DIR` fixed in Step 0 — do not re-pick between the two commands dirs). If the named profile doesn't exist, list the available profiles (`ls "$COMMANDS_DIR/landscape-profiles/"`) and ask the user which to run — don't silently fall back to default when a topic was explicitly named.

**Read the profile now.** It defines, for the rest of this run (step numbers below refer to this engine's steps):
- `One-liner` — the profile's one-line self-description; surface it in the Step 10 report header.
- `Contextualising reads` — what to load in Step 4.
- `Sources` — the curated list for Step 5 (scan mode), plus any source-specific mandatory-digest rules.
- `Assessment frame` — the passes to run in Step 7 and their definitions.
- `Report sections` — the finding-sections Step 9 classifies into and Step 10 inserts (the engine supplies the common wrapper).
- `File naming` — the filename suffix + prior-scan glob (default profile: none; others: `-<topic>`).
- `Obsolescence check` — its **value** governs whether Step 8 runs (tool-adoption profiles only).

Everything below that says "per the profile" reads from this file.

### 2. Current date + file naming

```bash
date +"%G-W%V"
```

File naming: `YYYY-Www<suffix>.md` (ISO week). Use `%G` (ISO week-numbering year), **not** `%Y` (calendar year) — the two disagree in late-Dec / early-Jan and `%Y-W%V` produces self-contradictory labels (e.g. `2024-W01`) that break the prior-scan delta glob across the year boundary. The default `ai-cc-pkm` profile uses no suffix (`2026-W16.md`) so existing files and delta logic are unaffected; other profiles use `-<topic>` (`2026-W16-cybersec.md`). Prior-scan lookups in later steps glob **only the active profile's pattern** so topics don't cross-contaminate each other's deltas.

### 3. Mode selection

Determine which mode(s) apply, in precedence order:

- **Bare invocation — just `/landscape-scan` (or `/landscape-scan <topic>`), no URLs and no extra natural-language request** → **scan mode** on the resolved profile. Don't ask; this is the original default behaviour. (The clarifying question below is only for an ambiguous *natural-language* scan request.)
- **User said "both" or similar** → both modes. (Explicit user intent wins.)
- **URLs present AND a scan verb ("scan" / "landscape scan" / "run landscape scan")** → both modes.
- **URLs present in the triggering message (or as args), no scan verb** → digest mode only.
- **Scan verb, no URLs** → **ask first**: "Scan mode (curated sources only), or do you also have URLs for a digest pass?" Default to scan-only if the user confirms no URLs. Do NOT lock in scan-only silently — the cost of asking is one question; the cost of mis-classification is the user having to supply URLs mid-run, which forces a mode switch and re-planning of the report structure.
- **Ambiguous** → ask the user: "Scan (curated sources), digest (you have URLs), or both?"

### 4. Contextualising preamble (ALWAYS — before any assessment)

Relevance judgement requires knowing what the user is *already doing* (and, for tool profiles, what they're *publicly positioning*; for threat profiles, *what they actually run*). Without this, assessments default to generic-audience relevance and miss what matters.

**Load the profile's `Contextualising reads` list**, proportionate to the scope of the run. Also:

- **Prior scan** — the most recent one for *this topic* regardless of age (it stays the delta anchor after a multi-week gap; note in the report if it's older than ~2 weeks), from `{VAULT}/06 Archive/Landscape Scans/` — use the profile's **concrete prior-scan glob** (an executable shell pattern, e.g. `20[0-9][0-9]-W[0-9][0-9]-cybersec.md`, not the display template `YYYY-Www.md`), sort by mtime (`ls -t`). Quote the directory but never the glob — `ls -t "{VAULT}/06 Archive/Landscape Scans/"<glob>` — a fully-quoted path makes the brackets literal and false-reports a cold start; an unquoted path breaks on the directory's spaces. Don't re-report things already classified unless their status changed. If the glob returns nothing, list the directory before concluding: no landscape files at all → genuine cold start, say so; files from other topics present but none matching this profile's pattern → report "no prior scans matched glob `<glob>`" so a mis-written pattern surfaces instead of silently reading as a cold start.
- **Just-in-time routing-table context** — if a specific finding later touches a CLAUDE.md routing-table topic, load that context before assessing that finding.

Keep this light — the goal is *calibration*, not total recall.

### 5. Scan mode — curated sources

Only if scan mode is active. Work the profile's `Sources` list; for each, focus on what's new or changed since the last scan for this topic. Honour any source-specific mandatory-digest rules the profile defines (e.g. the default profile's Zvi end-to-end digest).

If a source is unreachable or a repo has been deleted/moved, note it as "unavailable" and move on. Flag it in the *Sources list updates* section so the profile file gets cleaned up.

### 6. Digest mode — user-provided URL pile

Only if digest mode is active. These verification disciplines are domain-agnostic — they apply whatever the topic:

- **Fetch all URLs in parallel.** Don't serialise.
- **Handle fetch failures gracefully.** If WebFetch returns 403/429/timeout/blocked (common on npm registry, X/Twitter, Cloudflare-protected sites, and some vendor advisories), try `mcp__firecrawl__firecrawl_scrape` as fallback. If both fail, log the URL under "unfetchable" and continue — don't halt the run.
- **Verify suspicious sources before trusting the pitch.** Red flags: engagement-ratio anomalies (many retweets, zero likes → bot amplification); self-promotion by the author without independent endorsement; unverifiable superlatives ("99% accuracy," "permanent fix"); brand-new repo with improbable star counts (astroturfing). For threat profiles, add: unsubstantiated severity claims, vendor marketing dressed as advisory, and "patch available" claims with no CVE or commit to point to.
- **Fetch the underlying primary source, not just the pitch.** A tweet/blog pointing to a tool → fetch the repo/product page (last commit, issues, licence). A post describing a vulnerability → fetch the CVE record / vendor advisory / commit, and report what's actually confirmed.
- **Check commit activity on `main`, not just releases.** Stale release ≠ dead; active releases ≠ live `main`. Independent signals — look at both.
- **Verify falsifiable structural claims against raw source.** If a summary asserts a project is archived/deprecated/forked/superseded/renamed/rewritten — or that a vuln is patched/exploited-in-the-wild/disputed — re-fetch the raw source (e.g. `raw.githubusercontent.com/<owner>/<repo>/main/README.md`, the NVD entry, the vendor bulletin) and quote verbatim before acting. Summarisers occasionally confabulate plausible structural claims; high-stakes assertions need verbatim confirmation.
- **Flag red flags explicitly in the output.** Don't smooth them over, but don't let them pre-empt the profile's second-pass assessment either.

### 7. Assessment — per the profile's frame (BOTH modes)

For every finding worth reporting — from scan sources *or* digest pile — run the profile's `Assessment frame`. Each profile defines two passes; **run both, report both, never collapse to one verdict, never skip the second based on the first.**

The active profile's frame is authoritative; the two below are illustrative of the shipped profiles, not a closed set:
- Default `ai-cc-pkm`: **Fit** (does it replace / extend / lose-to what we have?) + **Capability** (what does it unlock that isn't being done today?).
- `cybersec`: **Exposure** (does it reach something on the stack inventory, and by what path?) + **Action** (severity → patch now / cooldown-then-patch / monitor / not-exposed-note).

The default profile's fit pass may name a specific local skill — that triggers the read-the-source gate in Step 8. The cybersec profile's exposure pass may name a specific stack component — that requires checking it against the stack-inventory doc, not asserting exposure from a product-name match.

### 8. Obsolescence / collision check — only if the profile's `Obsolescence check` value calls for it

*Tool-adoption profiles only.* Branch on the **value** of the profile's `Obsolescence check` key, not on whether the heading exists — every profile defines the key, so heading-presence is not the signal. Run this step only if that value specifies a check: the default `ai-cc-pkm` does; `cybersec` sets it to "does not run," so skip the step entirely for it.

Check whether any existing skill domains now have mature external alternatives that didn't exist (or weren't mature enough) when the skill was written. Lightweight, not a deep audit.

**⛔ Read-the-source gate (mandatory).** Any *comparative claim that names a specific local skill* — that an external finding obsoletes / upgrades / replaces / collides with / is inferior or superior to / makes redundant `/X` — MUST be backed by reading `/X`'s own source *this run*, **wherever the claim appears** (Step 7's fit pass, this step, or any section of the report). Sub-agents and external write-ups only ever see a name plus a one-line description, so their comparative claims are *structurally speculation*. **Name/description overlap is a prompt to open the file, never a verdict.**

- **Who reads:** the actor that writes the claim. A sub-agent that can't load local skills emits "name overlap — source unread" and leaves the verdict to the orchestrator, which opens the named source itself before accepting or reporting it.
- **What to read:** the named skill's source at `$COMMANDS_DIR/<name>.md` (the commands dir resolved in Step 0; fall back to `~/.claude/commands/<name>.md` only if `COMMANDS_DIR` couldn't be fixed) — enough of the body to establish its operating layer and mechanism, not just the frontmatter one-liner.
- **If no source file exists, the claim is *more* suspect, not less.** Confirm the skill exists at all; absence of a file is grounds to **drop the claim**, never wave it through.
- **Checkable:** every comparative verdict naming a skill traces to a source read this run, recorded as `Source read: <path>` (or `no file — claim dropped`).

If the vault contains a capability audit project doc, update the relevant domain section.

### 9. Classify findings

Classification labels come from the profile's `Report sections`. For each finding, state what it is and its significance in the active profile's terms — tool-adoption profiles: what problem it solves (handled or not today); threat profiles: what it reaches and the action trigger — and place it in the right section.

**For any finding whose action is "install / adopt a package" (either profile — a Claude Code tool, or a security tool), compute supply-chain cooldown explicitly.** Days since latest release (npm/PyPI/Docker) or last commit (source installs). Compare against a ≥3–7 day cooldown window — don't install a package the day it publishes; let downstream users surface supply-chain compromises (malicious publishes, typosquats, compromised maintainer accounts) first. State the recommendation — **install now / pin earlier version vX.Y.Z / defer until YYYY-MM-DD** — don't leave arithmetic to the user. **Exception:** an exposed, exploited-in-the-wild or critical-reachable security patch overrides the cooldown — when the profile's action pass says *patch now*, apply it immediately and state why (active exploitation outweighs the fresh-publish risk); the cooldown still governs optional tool/source adoption. (This discipline is doubly load-bearing for the `cybersec` profile, whose own beat is supply-chain attacks — the override resolves the irony that a rushed patch can itself be poisoned, but an exploited critical can't wait.)

### 10. Generate scan report

```bash
mkdir -p "{VAULT}/06 Archive/Landscape Scans"
```

Create `{VAULT}/06 Archive/Landscape Scans/YYYY-Www<suffix>.md`. If that file already exists (a second run this week — e.g. an ad-hoc digest after the weekly scan), **append a dated addendum section to it rather than overwriting**, and never invent a suffixed filename (`…b.md`) — the profiles' prior-scan globs won't match it. The engine supplies the common wrapper; the profile supplies the middle finding-sections:

```markdown
# Landscape Scan (<topic>) — YYYY-Www

**Topic / profile:** <topic> — <profile `One-liner`>
**Modes run:** [scan / digest / both]
**Date generated:** [YYYY-MM-DD (day-of-week), location if relevant]

## Contextualising reads
- [files/sources loaded in step 4]

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

<<< PROFILE REPORT SECTIONS — insert the active profile's `Report sections` here >>>

## Red flags flagged
- [Source] — [what was suspicious; was the underlying thing verified or not]

## No change since last scan
- [Sources that had nothing new]

## Sources list updates
- [New sources to add or stale ones to remove from the profile file]

## Actions executed this run
- [Any edits made to CLAUDE.md, memories, skills, profile files, tasks added to This Week / project hubs, config changes — anything the scan surfaced that resulted in immediate in-session action. Makes the report self-contained. If none: "None."]
```

### 11. Update the profile's source list

If any sources should be added or removed (repos deleted, new high-quality sources discovered), edit the **profile file** directly (not this engine file).

### 12. Display confirmation

```
Landscape scan (<topic>) saved to: 06 Archive/Landscape Scans/YYYY-Www<suffix>.md
Modes run: [scan / digest / both]
Sources checked: N    URLs digested: N    Derived: N    Unfetchable: N
Findings: [per profile's section counts]
Red flags flagged: N
Obsolescence check: [N domains / n/a for this profile]
Actions executed this run: N
Source list updates: [any changes made to the profile file]
```

## Guidelines

- **Research, not shopping.** "How did they solve X?" / "Does this reach me?" beats "should I switch to Y?"
- **Two passes, always.** First-pass dismissal does not close the second pass. Report both, per the profile's frame.
- **Delta over repeat.** Only report what's new since the last scan *for this topic*. Don't re-list stable sources that haven't changed.
- **Verify before trusting pitches.** Tweets/blogs/vendor marketing hype; repos, product pages, CVE records, and commits ship. Fetch the underlying thing.
- **Update the profile source list,** not this engine, when a source goes stale or a new one emerges.
- **Quick and focused.** Scan mode: 10–20 min for a light delta with few new items; longer on a cold start or a heavy Zvi week — the full source list plus an end-to-end Zvi digest is realistically 30–60+ min, so budget accordingly rather than skimming to hit the lower number. Digest mode: scales with URL count but stays snappy.
- **Expand category abstraction when a direct-match search returns nothing.** If an exact-match search yields zero hits, don't conclude "none exists." Abstract up one level and search again. Direct-match null is a second-pass failure mode if not expanded.
- **Honest about signal.** A null result is fine — say so.

## Frequency

Run weekly (typical) per topic, or whenever the user explicitly requests it — including ad-hoc digest-only runs when they've batched up a pile of URLs.

## Adding a new topic

Drop a `landscape-profiles/<topic>.md` file defining the seven profile keys (`One-liner`, `Contextualising reads`, `Sources`, `Assessment frame`, `Report sections`, `File naming`, `Obsolescence check` — the last with an explicit value, e.g. "does not run", since Step 8 branches on the value). No engine edits needed. Keep profiles template-suitable where possible: cite the user's real infrastructure by pointing the profile at a vault doc (e.g. a stack-inventory note) rather than hardcoding personal specifics into the profile.

## Integration with Other Commands

- **/quarterly-review:** quarterly's strategic-alignment step would benefit from accumulated landscape findings. *(Intended complement — not yet wired into that skill.)*
- **/weekly-review:** weekly is internal (vault health, progress); landscape-scan is external. *(Intended complement — not yet wired into that skill.)*
- **The `cybersec` profile and an internal security-audit skill:** the audit is internal posture (what's misconfigured on the machine *now*); the cybersec scan is external threat intel (what got disclosed that touches the stack). Neither subsumes the other. The template ships no security-audit skill — if you run one, wire the pair by having both read the same stack-inventory doc (the one the cybersec profile's `Contextualising reads` names).
