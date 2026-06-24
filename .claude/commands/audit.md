---
name: audit
description: Rigorous five-layer evaluation of any implementation (code, config, plans, processes, systems) — by a cross-model panel by default, gracefully downgrading to whatever models are available, or a single model on request.
---

# Audit - Rigorous Implementation Review

You are auditing an implementation. This applies to anything with logic and structure: code, infrastructure, configurations, plans, processes, decision frameworks, workflows.

## Philosophy

**Zoom out before zooming in.** Most review effort goes to implementation details (Layer 4), but Layers 1-3 are higher leverage and get skipped by default. A perfectly implemented wrong approach is still wrong.

**Iterate until clean.** Every fix changes the system — re-audit after each fix. A single-pass audit is just a bug report. Keep going until a full pass finds nothing.

**Many eyes, uncorrelated.** By default the audit runs as a cross-model panel — Claude, Gemini, and Codex each run the full five-layer audit independently, then you synthesise. Different model families have different blind spots; agreement is signal and disagreement is more signal. A single reviewer is faster and fine for routine checks (`--claude`), but for anything hard to reverse, the panel is worth three passes.

## Reviewers and model selection

**Default (no flag): panel.** Run all available reviewers — a fresh Claude agent + Gemini + Codex — each performing Phase 2 independently from source, then synthesise per Phase 3. Graceful degradation is the rule: probe availability first and run with whoever's present.

**Flags** (parse from `$ARGUMENTS`):
- *(no model flag)* → panel of all available models, always. The panel is the unconditional default — no auto-downgrade on low-stakes, small-surface, or easily-reversed targets. The only route to a single reviewer is an explicit flag (`--claude` / `--gemini` / `--codex`).
- `--claude` → single Claude reviewer only.
- `--gemini` → single Gemini reviewer only.
- `--codex` → single Codex reviewer only.
- Flags combine to force an explicit subset — `--gemini --codex` runs those two, no Claude.

**Availability probe (do this in Phase 1, before despatch).** Run `gemini --version` and `codex --version`. Announce the resolved panel in one line: `"Panel: Claude + Gemini + Codex"`, or `"Codex unavailable — panel: Claude + Gemini"`. If a model was explicitly requested by flag but its CLI is missing, stop with a one-line install hint rather than silently dropping it. If no external CLI is available and no flag forced one, fall back to a single inline Claude audit and **say so** — `"No external model CLIs found — running single-Claude audit."` If the fresh Claude Agent (the Claude seat) fails to spawn: when the audit target was produced **in this same session**, drop the Claude seat and run the remaining panel — the running instance is exactly the reviewer the fresh-agent requirement disqualifies (it has already normalised its own choices), and substituting it while tagging findings `[Claude]` launders bias as independence. For targets *not* produced this session, fall back to an inline pass for that seat, tag its findings `[Claude-inline]`, and say so — the announced panel covered availability, not spawn success.

**Execution shape per reviewer:**
- **Claude seat in panel mode** = a *fresh* Agent (`subagent_type: general-purpose`), independent of this conversation — important when auditing work produced in this same session (the running instance has already normalised its own choices).
- **`--claude` single mode** = the running instance audits inline (cheapest, the classic single-pass audit); no agent spawn needed.
- **Gemini / Codex seats** = dispatched via their CLIs. The canonical command block is `_shared-rules.md` §10; see `/second-opinion` Phase 2A for the orchestration around it (fallbacks, auth caveats, session-handle capture). The compact despatch notes are in Phase 2 below.

The panel despatch, attribution tags, and no-vote-counting tiebreak are `/second-opinion`'s machinery — this skill reuses it rather than reinventing it (see the *Parallel cross-model trio despatch* pattern in `_shared-patterns.md`). Read `second-opinion.md` if you need the full despatch mechanics.

## Instructions

### Phase 1: Identify and Scope the Target

1. **Parse `$ARGUMENTS`** for the target and any model flags (above). Resolve the reviewer set and run the availability probe; announce the resolved panel.
2. **If the user specified what to audit**, load it. **If not**, ask: "What should I audit?" — don't guess.
3. **If the target is too large to read in full** (a whole repo, a multi-file system, a complex process), ask the user to narrow scope or state which parts to prioritise. An audit that silently skips things is worse than a scoped audit that's honest about its boundaries. In panel mode, scope it in the shared brief so every reviewer covers the same ground.
4. **Read the full implementation within scope** before forming opinions. No drive-by observations. In panel mode, each reviewer reads from source — the brief gives the path and is flagged as supplementary, possibly-biassed context, not a substitute for reading.

### Phase 2: Five-Layer Audit

This is the protocol every reviewer runs. In single mode you run it directly; in panel mode it's the body of the shared brief. Write the brief once to a scratch file (`mktemp -t audit-brief.XXXXXX.md`), read its contents verbatim into the Claude Agent's prompt, and pipe the same file to each CLI. The brief *payload* is identical across seats; the per-channel wrappers (the Agent prompt frame, the CLI `-p` string) need only be semantically equivalent, not byte-equal — channels differ irreducibly, so "same brief" means same payload, not same bytes on the wire.

The brief must contain: (a) the target path and what it is; (b) the scope boundaries (what's in, what's out); (c) the supplementary-context disclaimer — "read from source first; this summary is possibly biassed, not a substitute"; (d) the five-layer protocol body below — you may tailor each layer's per-type bullets to the target type (a doc target doesn't need "run the tests"), provided the tailored body is identical across all seats; (e) the output format: findings by layer, explicit "clean" per empty layer, **and a list of the files the reviewer read — a review without a read-list is discarded** (delegated reads are invisible to you; the read-list is the only evidence the reviewer worked from source, not from the brief); (f) the anti-sycophancy directive — "no hedging, disagree where warranted, no sycophancy" — without which a fresh reviewer defaults to politely confirming the brief's framing; (g) a per-layer findings cap (e.g. max 4) — uncapped lists invite padding. This borrows the self-contained-brief idea from `second-opinion.md` Phase 1 step 4 — read it if you want the worked field list.

Compact panel despatch (single message, concurrent calls). The canonical command block — read-only policy file, Gemini/Codex invocations, out-of-cwd workspace flags — lives in **`_shared-rules.md` §10**; use it verbatim rather than reciting from memory (it is the single source of truth; this file deliberately carries no copy to drift). Audit-specific notes on top of it: the Claude seat is the Agent tool (`subagent_type: general-purpose`) with the brief contents verbatim as its prompt; `timeout: 300000` is a **Bash-tool argument** on each CLI call, not a shell flag — the default 120s kills reviewers mid-audit and the runner won't intuit it from prose alone. Despatch from the target's root: Gemini's reads are sandboxed to the **cwd it launches from** (not `~` — verified, see §10) and Codex reads relative to its workdir, so a target outside the despatch cwd needs §10's `--include-directories <root>` / `-C <root>` flags.

Surface each reviewer's session handle (Agent ID, Gemini index, Codex UUID) in visible text — you'll need them for a Phase 4 re-audit. The Gemini index isn't printed in-band: capture it with `gemini --list-sessions | tail -3` (highest-numbered row, leading numeric column). Codex prints `session id: <uuid>` in its preamble. See `second-opinion.md` Phase 2A for the full capture recipe.

**Integrity guard (same as `second-opinion.md` Phase 2A step 6).** The §10 `--policy` read-only file makes Gemini's edit tools "not found" (a hard guarantee on gemini 0.40.x), but keep this as a cheap backstop — it confirms the policy loaded and is the only protection on the no-`--policy` fallback. For a **non-git target, snapshot mtimes/hashes of the target files *before despatch*** — there's nothing to diff against afterwards if you skip this. After the panel returns and before Phase 3, `git status` the target (if a repo; else diff the snapshot) and revert any reviewer-introduced changes; compare any "proposes text that already exists" finding against committed HEAD, not the working tree.

Work through these layers in order. Each layer can invalidate everything below it, so don't skip ahead.

#### Layer 1: Is the approach right?

Before examining how it's built, ask whether it *should* be built this way.

- Does this solve the actual problem, or a proxy of it?
- Are there simpler approaches that weren't considered?
- Does the architecture match the constraints (scale, maintainability, who will operate it)?
- Is there unnecessary complexity? (Premature abstraction, over-engineering, speculative features)

#### Layer 2: What's the operating environment?

The implementation doesn't exist in isolation. What surrounds it matters.

- For code: runtime, dependencies, network paths, resource contention, competing workloads
- For plans: who executes, what resources exist, what's the timeline, what else is in flight
- For processes: who are the actors, what are their incentives, where does friction live
- For config: what reads this, what else touches these settings, what's the failure mode
- For docs/prompts/specs: who executes them, with what tools, at what point — and which environment facts they assert that could drift or differ across machines

#### Layer 3: What existing state needs to migrate or integrate?

Change always meets existing reality. What's already there?

- What does this replace or modify? What breaks if the old thing disappears?
- Are there consumers/dependents that expect the current interface/format/behaviour?
- Is there data, state, or configuration that needs to carry forward?
- For plans/processes: what habits, expectations, or workflows does this disrupt?
- For content edits (docs, notes, config values): grep **case-insensitively (`-i`)** for changed identifiers across the wider repository, then apply `_shared-rules.md` §12 in full — grep-target selection (changed value vs decision anchor), hit triage (stale cross-reference / live locator / historical record / different context; ambiguous → report, don't edit), bare-anchor sweeps for content that moved out of a document, and when to prefer structural queries over text grep all live there. Stale cross-references are the most common Layer 3 miss in non-code edits.

#### Layer 4: Is the implementation correct?

Now zoom in. Evaluate the actual work product.

- For code: logic errors, edge cases, error handling, security (OWASP top 10), naming, readability
- For plans: gaps in sequencing, missing dependencies, unrealistic assumptions, unowned tasks
- For processes: missing steps, ambiguous responsibilities, no feedback loops, single points of failure
- For config: typos, wrong values, missing entries, inconsistencies with documentation
- For docs/prompts/specs: contradictions between sections, instructions an executor could reasonably misread, stale claims about tools/flags/paths/versions, inconsistency with its own stated rules

#### Layer 5: Does it actually work?

Theory vs. reality. Can you verify it runs?

- For code: run it, run tests, check for obvious runtime failures
- For plans: pick one concrete scenario and trace through every step — narrate what happens, what each actor does, where they get the information they need. Does it hold up?
- For processes: simulate the first real execution the same way — who does what, in what order, with what inputs? Where does someone get stuck or confused?
- For config: validate syntax, check that referenced paths/services exist
- For docs/prompts/specs: trace one concrete execution of the document's instructions — where does the executor stall, guess, or improvise past the letter of the text? Executor friction is evidence; cheaply testable claims (cited sections, flags, paths) get tested

### Phase 3: Report Findings

1. **State the audit scope and the panel composition** at the top of the report — what was audited, any boundaries (e.g., "Auditing `src/auth/` only, not the calling code"), and which reviewers ran (e.g., "Panel: Claude + Gemini; Codex unavailable").

2. **Present findings by layer**, not as a flat list. This makes severity obvious — a Layer 1 finding ("wrong approach") outranks ten Layer 4 findings ("minor bugs").

3. **In panel mode, tag every finding with attribution and tiebreak disagreements.** Name the reviewers who raised each finding — `[Claude]`, `[Gemini]`, `[Codex]`, combinations, or `[All]`. Then, within each layer:
   - **Confirmed (multi-reviewer):** higher confidence, but correlated agreement is weak evidence, not ground truth — two models can share a blind spot.
   - **Disputed:** reviewers split → investigate, pick a side, say *why*. Don't hedge, don't average, don't count votes.
   - **Uniquely flagged:** one reviewer only → judge on merit (real issue → promote; idiosyncrasy → drop with a reason). Verify a unique find before acting on it — a confident single-reviewer claim is a hypothesis, not a fact.

4. **For each finding, state:**
   - What's wrong (specific, no hedging)
   - Why it matters (consequence if left unfixed)
   - Suggested fix (concrete, not "consider improving")

5. **If no findings at a layer**, say so explicitly. "Layer 3: No migration concerns — this is net-new with no existing dependents." (In panel mode, silence from a reviewer is not endorsement — only an explicit "no findings here" counts.)

### Phase 4: Fix and Re-audit

1. **If fixes are possible and authorised**, make them. If fixes aren't authorised or aren't possible (e.g., auditing someone else's work, a read-only review), the audit ends at Phase 3 — present findings and stop.
2. **After each round of fixes, re-audit from Layer 1.** Fixes can introduce new issues or invalidate prior findings.
3. **⛔ Re-audit requires re-reading.** A re-audit pass must include at least one Read tool call on modified files. "Clean pass" without a preceding Read is a fabricated claim, not a verified result. Small, obvious fixes are the most dangerous — false confidence skips verification. This is transcript-checkable only for the orchestrating instance (its own Read calls are visible); a delegated reviewer's reads are not, so in panel re-audit require each reviewer to **state in its output what it re-read**.
4. **Re-audit despatch is a choice.** Cheap: a single-model re-audit (`--claude`, or just the running instance) for mechanical fixes. Thorough: resume the panel via `/second-opinion` Mode B (`SendMessage` to the Agent; `gemini --resume <index>`; Codex per `second-opinion.md` Phase 2B step 4 — **the sandbox flags must precede `resume`**, so take the command from there, not from memory) with a narrow follow-up — "you flagged X; the author did Y; does it resolve your concern?" — for findings where "does the fix land?" is itself a judgement call. (Mode B is only partially validated — Codex and Gemini legs proven, Claude leg not; see the warning in `second-opinion.md` Phase 2B. The single-model re-audit is the fully proven option.)
5. **Repeat until the audit reaches a terminal state**, then report it. Terminal states: **clean** (a full pass finds nothing — "Clean pass, no further findings"); **accepted residual risk** (findings remain but are knowingly accepted — name them); **blocked** (a fix needs a user decision); **unresolved disagreement** (reviewers still split after one cross-check round — present both sides). "Iterate until clean" is the goal, not a mandate to loop indefinitely on subjective findings.

## Guidelines

- **Panel by default, single model only by explicit flag.** The panel is the unconditional default because uncorrelated reviewers catch what one misses — never auto-downgrade based on stakes or surface size. If the user wants a quicker single-reviewer pass, they say `--claude` (single inline pass); absent that flag, run the full panel even for a small target.
- **Graceful degradation, loudly.** Always announce the resolved panel and never silently drop a reviewer. A one-reviewer run is a single opinion, not a panel, and the synthesis must say so.
- **Identical brief payload across the panel.** Any framing asymmetry between reviewers defeats the cross-model signal. Write the Phase 2 brief once and send the same payload to each — the transport wrappers differ (Agent prompt vs CLI `-p` string), so aim for semantic equivalence, not byte equality.
- **Cross-model, not cross-instance.** One Claude + one Gemini + one Codex. Two Claudes correlate; non-correlated error modes are the whole point.
- **Specificity over breadth:** Five specific findings beat twenty vague observations.
- **No hedging:** "This will fail when X" not "This might potentially have issues with X."
- **Severity is implicit in the layer:** Don't add separate severity labels — Layer 1 findings are inherently more important than Layer 4. A lone reviewer's Layer 1 finding outranks all three agreeing on a Layer 4 nit.
- **The tiebreak is the work.** You're not chairing a committee or counting votes — investigate disagreements and decide. A panel that mechanically applies every suggestion is a slower single pass.
- **Don't pad:** If the implementation is solid, say so. "Clean pass" is a valid audit result.
- **Scope to what was asked:** Audit the target, not the surrounding codebase. Flag adjacent concerns briefly if they're blocking, but don't expand scope without asking.
- **Earn the clean pass:** Layer 1-3 findings are uncomfortable but high-value — they mean the approach itself may be wrong. A clean pass at these layers must be earned by articulating *why* the approach is right, not assumed by jumping to implementation details.
