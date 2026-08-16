---
name: audit
description: Rigorous six-layer evaluation (Layers 0-5) of any implementation (code, config, plans, processes, systems) — by a cross-model panel by default, gracefully downgrading to whatever models are available, or a single model on request.
---

# Audit - Rigorous Implementation Review

You are auditing an implementation. This applies to anything with logic and structure: code, infrastructure, configurations, plans, processes, decision frameworks, workflows.

## Philosophy

**Zoom out before zooming in.** Most review effort goes to implementation details (Layer 4), but Layers 0-3 are higher leverage and get skipped by default. A perfectly implemented wrong approach is still wrong — and a perfectly solved wrong problem is worse.

**Iterate until clean.** Every fix changes the system — re-audit after each fix. A single-pass audit is just a bug report. Keep going until a full pass finds nothing.

**Many eyes, uncorrelated.** By default the audit runs as a cross-model panel — Claude, Gemini, Codex, and Grok each run the full six-layer audit independently, then you synthesise. Different model families have different blind spots; agreement is signal and disagreement is more signal. A single reviewer is faster and fine for routine checks (`--claude`), but for anything hard to reverse, the panel is worth four passes.

## Reviewers and model selection

**Default (no flag): panel.** Run all available reviewers — Claude + Gemini + Codex + Grok, one seat per family — each performing Phase 2 independently, then synthesise per Phase 3. Graceful degradation is the rule: probe availability first and run with whoever's present. The first three read from source; Grok is an API seat that reviews inlined sources (see `_shared-rules.md` §10) — it is a full seat with a different evidence standard, not a lesser one.

**Flags** (parse from the free-text arguments after the invocation):
- *(no model flag)* → panel of all available models, always. The panel is the unconditional default — no auto-downgrade on low-stakes, small-surface, or easily-reversed targets. The only route to a single reviewer is an explicit flag (`--claude` / `--gemini` / `--codex` / `--grok`).
- `--claude` → single Claude reviewer only.
- `--gemini` → single Gemini reviewer only.
- `--codex` → single Codex reviewer only.
- `--grok` → single Grok reviewer only.
- Flags combine to force an explicit subset — `--gemini --codex` runs those two, no Claude.

**Availability probe (do this in Phase 1, before despatch).** Run `claude --version`, `gemini --version`, `codex --version`, and `"{VAULT}/.claude/scripts/xai_client.py" --probe` (there is no Grok binary — the probe exits 0 when the client resolves `XAI_API_KEY` from the process environment or `~/.claude/settings.json`, 1 otherwise; probe before despatch so an unavailable key degrades the panel up front rather than failing mid-run). Announce the resolved panel in one line: `"Panel: Claude + Gemini + Codex + Grok"`, or `"Claude unavailable — panel: Gemini + Codex + Grok"`. If a model was explicitly requested by flag but its CLI is missing, stop with a one-line install hint rather than silently dropping it. ⚠ **Under Codex as the primary harness, the Codex CLI seat shares the primary's model family** — a fresh `codex exec` is still a fresh context (it carries none of this session's normalisations), but the family-independence claim weakens: announce it and weight the Claude/Gemini/Grok seats accordingly (`_shared-rules.md` §10). If no external CLI is available at all, fall back to an inline single-reviewer audit by the running instance, tag its findings `[Codex-inline]`, and say so — an inline pass over work produced in this same session is the weakest seat (the running instance has already normalised its own choices); prefer any fresh seat over it.

**Execution shape per reviewer:**
- **Claude seat in panel mode** = the `claude` CLI in print mode (`cat <brief> | claude -p "Follow the instructions in the piped input exactly."`), independent of this conversation — important when auditing work produced in this same session (the running instance has already normalised its own choices). Configure it read-only per §10's despatch block (`--output-format json --disallowedTools "Bash,Write,Edit,NotebookEdit"`; capture `.session_id` from the JSON).
- **Single-reviewer modes** = one despatched seat only. Exception: `--codex` may run as the running instance auditing inline (cheapest, the classic single-pass audit — no despatch), tagged `[Codex-inline]`.
- **Gemini / Codex seats** = dispatched via their CLIs. The canonical command block is `_shared-rules.md` §10; see `$second-opinion` Phase 2A for the orchestration around it (fallbacks, auth caveats, session-handle capture). The compact despatch notes are in Phase 2 below.
  - **The seats are not equally able to verify** — a seat denied shell cannot check any claim locally, which changes both how you brief it and how much its unique findings weigh. §10 carries the mechanism and the remedy.
- **Grok seat** = dispatched via `"{VAULT}/.claude/scripts/xai_client.py" --panel-review <brief> --source <target>`, also per §10. It has no filesystem access: the target is inlined into the prompt and its evidence standard is the inlined-source manifest rather than a read-list. Over `MAX_INLINE_BYTES` the wrapper fails closed — drop the seat and announce the reduced panel rather than truncating.

The panel despatch, attribution tags, and no-vote-counting tiebreak are `$second-opinion`'s machinery — this skill reuses it rather than reinventing it (see the *Parallel cross-model panel despatch* pattern in `~/.codex/skills/_shared-patterns.md`). Read `~/.codex/skills/second-opinion/SKILL.md` if you need the full despatch mechanics.

## Instructions

### Phase 1: Identify and Scope the Target

1. **Parse the invocation's free-text arguments** for the target and any model flags (above). Resolve the reviewer set and run the availability probe; announce the resolved panel.
2. **If the user specified what to audit**, load it. **If not**, ask: "What should I audit?" — don't guess.
3. **If the target is too large to read in full** (a whole repo, a multi-file system, a complex process), ask the user to narrow scope or state which parts to prioritise. An audit that silently skips things is worse than a scoped audit that's honest about its boundaries. In panel mode, scope it in the shared brief so every reviewer covers the same ground.
4. **Read the full implementation within scope** before forming opinions. No drive-by observations. In panel mode, each reviewer reads from source — the brief gives the path and is flagged as supplementary, possibly-biassed context, not a substitute for reading.
5. **Gather the problem's origin and intent** for brief field (i) below: pull the requester's words from the session or its records; if none are held and the requester is reachable, ask once — a one-line answer is enough. Only after that may the brief declare the origin genuinely unknown. Without this step every seat is forced to audit the frame as given, and Layer 0 cannot catch the drift it exists for.

### Phase 2: Six-Layer Audit

This is the protocol every reviewer runs. In single mode you run it directly; in panel mode it's the body of the shared brief. Write the brief once to a scratch file (`mktemp -t audit-brief.XXXXXX.md`) and pipe the same file to every seat. The brief *payload* is identical across seats; the per-channel wrappers (the per-CLI `-p` strings) need only be semantically equivalent, not byte-equal — channels differ irreducibly, so "same brief" means same payload, not same bytes on the wire.

Every panel brief must begin with this exact block. It is a role boundary, not supplementary context:

```markdown
## Reviewer-seat execution boundary

You are one leaf reviewer inside an already-running review panel. Execute this brief directly and return the requested review. Do not activate or follow any audit, second-opinion, reviewer, or orchestration skill as a workflow; if one is itself in scope, inspect it only as target material. Do not dispatch another reviewer or create another panel. Do not edit files.
```

The brief must contain: (a) the target path and what it is; (b) the scope boundaries (what's in, what's out); (c) the supplementary-context disclaimer — "read from source first; this summary is possibly biassed, not a substitute"; (d) the six-layer protocol body below — you may tailor each layer's per-type bullets to the target type (a doc target doesn't need "run the tests"), provided the tailored body is identical across all seats; (e) the output format: findings by layer, explicit "clean" per empty layer, and **the evidence attestation each seat owes, per `_shared-rules.md` §23** (it is the single source of truth; this file deliberately carries no copy to drift). §23 requires its attestation table be **pasted into the brief body verbatim**, not cross-referenced — the reviewer's workspace is the target, not this directory, so a pointer is an instruction it cannot follow. §23 also carries the receipt enforcement and the spot-check-before-promoting rule, both of which are yours to run, not the reviewer's; (f) the anti-sycophancy directive — "no hedging, disagree where warranted, no sycophancy" — without which a fresh reviewer defaults to politely confirming the brief's framing; (g) a per-layer findings cap (e.g. max 4) — uncapped lists invite padding; (h) **out-of-band evidence** — every source the target's claims rest on that a reviewer cannot reach from the target itself, embedded verbatim under an established-fact heading, per **`_shared-rules.md` §16** (it is the single source of truth; this file deliberately carries no copy to drift). §16 matters doubly here: an omitted source produces a false positive in *every* seat, and Phase 3 then reads that convergence as corroboration. Mind §16's size cap — this brief is piped into CLI seats with differing context windows under an identical-payload requirement, so an uncapped dump can truncate silently in one seat. This borrows the self-contained-brief idea from `second-opinion/SKILL.md` Phase 1 step 4 — read it if you want the worked field list. Finally, (i) **problem origin and intent** — where the stated problem came from and what the requester is ultimately after, quoted in their own words where the session has them — quote the request, not the session's gloss on it, prefer the earliest capture, and label a second-hand paraphrase as such. Layer 0 audits the frame against this field, so a brief without it forces every seat to either adopt the frame unexamined or invent an intent; if the session genuinely doesn't hold the origin (after Phase 1 step 5's gather-and-ask), the brief must say so rather than supplying a plausible reconstruction.

**Pre-flight, before any despatch:** run §10's shell-denied-seat pre-flight — if any seat lacks shell and the audit turns on something a shell would settle, check it yourself now and embed the output under (h). Then open every source the target *cites* but the session never read, per **§16** — that gap is closed by opening the source, never by disclosing it in the brief, which merely aims all seats at the same hole and turns their agreement into an artefact of your own omission. Then: if the target is **not** in a git repo, snapshot mtimes/hashes of the target files now — it is the only baseline the integrity guard below can diff against, and there is nothing to reconstruct afterwards if you skip it.

Compact panel despatch (single message, concurrent calls). The canonical command block — read-only policy file, Gemini/Codex invocations, out-of-cwd workspace flags — lives in **`_shared-rules.md` §10**; use it verbatim rather than reciting from memory (it is the single source of truth; this file deliberately carries no copy to drift). Audit-specific notes on top of it: every seat (Claude included) is a CLI/API despatch — pipe the brief file to each; give each call a five-minute window and confirm the harness's command timeout allows it (§10's timeout note — mechanism unverified under Codex; a default timeout kills reviewers mid-audit). Despatch from the target's root: Gemini's reads are sandboxed to the **cwd it launches from** (not `~` — verified, see §10) and Codex reads relative to its workdir, so a target outside the despatch cwd needs §10's `--include-directories <root>` / `-C <root>` flags.

Surface each reviewer's session handle (Claude session id (`.session_id` in its `--output-format json` output), Gemini index, Codex UUID) in visible text — you'll need them for a Phase 4 re-audit. The Gemini index isn't printed in-band: capture it with `gemini --list-sessions | tail -3` (highest-numbered row, leading numeric column), **run from the same cwd you despatched Gemini from** — the session list is per-project/cwd, so a capture from anywhere else indexes into a different project's sessions and Phase 4 resumes the wrong one. Codex prints `session id: <uuid>` in its preamble. Grok has **no session handle** — persist the brief path, the `--source` list, and the output path beside the scratch brief and surface those paths alongside the other handles, since a Grok round 2 is a fresh call replaying them. See `second-opinion/SKILL.md` Phase 2A for the full capture recipe.

**Integrity guard (same as `second-opinion/SKILL.md` Phase 2A step 6).** The §10 `--policy` read-only file makes Gemini's edit tools "not found" (a hard guarantee on gemini 0.40.x), but keep this as a cheap backstop — it confirms the policy loaded and is the only protection on the no-`--policy` fallback. For a non-git target this depends on the pre-flight snapshot taken above. After the panel returns and before Phase 3, `git status` the target (if a repo; else diff the snapshot) and revert any reviewer-introduced changes; compare any "proposes text that already exists" finding against committed HEAD, not the working tree.

Work through these layers in order. Each layer can invalidate everything below it, so don't skip ahead.

#### Layer 0: Is this the right problem?

Step outside the problem statement before accepting it. Every layer below operates *inside* the frame the target was built against; this layer audits the frame itself. A problem statement is usually a translation of someone's underlying goal — made in a conversation, a ticket, a summary, an earlier session — and translations drift. Within-frame rigour cannot catch a mistranslation.

- Restate the requester's underlying goal in your own words, independent of how the target frames it. What outcome are they actually after?
- Is the stated problem a faithful rendering of that goal, or a proxy? Try to name a concrete way the target could succeed on its own terms and still leave the requester without what they wanted — finding one is a Layer 0 finding; an honest failed attempt to find one is the clean-pass evidence.
- Is there a different problem that serves the goal better — including doing nothing, or dissolving the constraint instead of satisfying it?
- If the brief is silent on origin/intent where a requester plainly exists, that omission is itself a Layer 0 finding — against the brief, not the target. If the brief declares the origin genuinely unknowable (found code, no identifiable requester), record the status note "intent unstated; frame audited as given" and proceed — a status, not a finding, and no bar to a clean pass.

A confirmed Layer 0 finding means the work may be aimed at the wrong target. The remedy is to take it back to the requester for a reframe — never to quietly re-scope and continue. Still work the remaining layers, tagging their findings "moot unless reframed", but spend no fix-cycles on them until the reframe lands.

#### Layer 1: Is the approach right?

Before examining how it's built, ask whether it *should* be built this way. (Layer 0 asked whether this is the right problem; this layer asks whether it's the right solution to it.)

- Does this solve the stated problem fully and directly, or only a narrower proxy of it? (Whether the stated problem is the right one was Layer 0's question — don't re-litigate it here.)
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
- Treat tool/version observations embedded in a dated brief as gate-time measurements. Re-probe when the current value matters; report drift only where a durable claim or decision still depends on the old value.

#### Layer 3: What existing state needs to migrate or integrate?

Change always meets existing reality. What's already there?

- What does this replace or modify? What breaks if the old thing disappears?
- Are there consumers/dependents that expect the current interface/format/behaviour?
- Is there data, state, or configuration that needs to carry forward?
- For plans/processes: what habits, expectations, or workflows does this disrupt?
- For content edits (docs, notes, config values): grep **case-insensitively (`-i`)** for changed identifiers across the wider repository, then apply `_shared-rules.md` §12 in full — grep-target selection (changed value vs decision anchor), hit triage (stale cross-reference / current-state confirmation / live locator / historical record / different context; ambiguous → report, don't edit), bare-anchor sweeps for content that moved out of a document, and when to prefer structural queries over text grep all live there. Stale cross-references are the most common Layer 3 miss in non-code edits.

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
- For recursive artefact sets: enumerate recursively and return a positive-control count plus an expected member from the same run. A zero-result check with no positive control establishes nothing about the set.

### Phase 3: Report Findings

1. **State the audit scope and the panel composition** at the top of the report — what was audited, any boundaries (e.g., "Auditing `src/auth/` only, not the calling code"), and which reviewers ran (e.g., "Panel: Claude + Gemini; Codex unavailable").

2. **Present findings by layer**, not as a flat list. This makes severity obvious — a Layer 0 finding ("wrong problem") outranks a Layer 1 finding ("wrong approach"), which outranks ten Layer 4 findings ("minor bugs").

3. **In panel mode, tag every finding with attribution and tiebreak disagreements.** Name the reviewers who raised each finding — `[Claude]`, `[Gemini]`, `[Codex]`, `[Grok]`, combinations, or `[All]`. Then, within each layer:
   - **Confirmed (multi-reviewer):** higher confidence, but correlated agreement is weak evidence, not ground truth — two models can share a blind spot.
   - **Disputed:** reviewers split → investigate, pick a side, say *why*. Don't hedge, don't average, don't count votes.
   - **Uniquely flagged:** one reviewer only → judge on merit (real issue → promote; idiosyncrasy → drop with a reason). Verify a unique find before acting on it — a confident single-reviewer claim is a hypothesis, not a fact.
   - **Weigh by evidence class, not by seat** — command run > quoted primary > secondary > unattested, and evidence class outranks seat count. → `_shared-rules.md` §23.

4. **For each finding, state:**
   - What's wrong (specific, no hedging)
   - Why it matters (consequence if left unfixed)
   - Suggested fix (concrete, not "consider improving")

5. **If no findings at a layer**, say so explicitly. "Layer 3: No migration concerns — this is net-new with no existing dependents." (In panel mode, silence from a reviewer is not endorsement — only an explicit "no findings here" counts.)

### Phase 4: Fix and Re-audit

1. **If fixes are possible and authorised**, make them. If fixes aren't authorised or aren't possible (e.g., auditing someone else's work, a read-only review), the audit ends at Phase 3 — present findings and stop.
   - **Deletion discipline — surface, don't delete, content you can't attribute.** You may *delete* content only when you can attribute its creation to the change under audit. Content you cannot attribute — a bare line, an orphan, a stray value you're *inferring* is a "leak" — must be **surfaced as a finding, not removed**, especially in shared planning/state files (a weekly plan, a rendered dashboard, a tickler) where users park deliberate scratch notes (a number to grab later, a clipboard value). A bare unfamiliar token is as likely an intentional note as a leak and you cannot reliably tell them apart, so default to reporting it. Mirrors *don't auto-revert changes you didn't make*: getting it right by luck doesn't make auto-deletion correct. (Applies to delegated audits too: `park/SKILL.md` Step 9's sub-agent is briefed to read this rule.)
2. **After each round of fixes, re-audit from Layer 0.** Fixes can introduce new issues or invalidate prior findings.
3. **⛔ Re-audit requires re-reading.** A re-audit pass must include at least one fresh read of the modified files. "Clean pass" without a preceding read is a fabricated claim, not a verified result. Small, obvious fixes are the most dangerous — false confidence skips verification. This is transcript-checkable only for the orchestrating instance (its own reads are visible); a delegated reviewer's reads are not, so in panel re-audit require each reviewer to **state in its output what it re-read**.
4. **Re-audit despatch is a choice.** Cheap: a single-model re-audit (`--claude`, or just the running instance) for mechanical fixes. Thorough: resume the panel via `$second-opinion` Mode B (the Claude leg per `second-opinion/SKILL.md` Phase 2B; `gemini --resume <index>`; Codex per `second-opinion/SKILL.md` Phase 2B step 4 — **the sandbox flags must precede `resume`**, so take the command from there, not from memory; Grok as a `[Grok r2, fresh-with-replay]` leg — no session to resume, so re-invoke the wrapper with the persisted brief and `--source` list) with a narrow follow-up — "you flagged X; the author did Y; does it resolve your concern?" — for findings where "does the fix land?" is itself a judgement call. (Mode B: Codex and Gemini legs proven in real use; the Claude leg's resume mechanics round-trip, but no full review round 2 has run on it yet — see `second-opinion/SKILL.md` Phase 2B. The single-model re-audit is the fully proven option.)
5. **Repeat until the audit reaches a terminal state**, then report it. Terminal states: **clean** (a full pass finds nothing — "Clean pass, no further findings"); **accepted residual risk** (findings remain but are knowingly accepted — name them); **blocked** (a fix needs a user decision); **unresolved disagreement** (reviewers still split after one cross-check round — present both sides). "Iterate until clean" is the goal, not a mandate to loop indefinitely on subjective findings.

## Guidelines

- **Panel by default, single model only by explicit flag.** The panel is the unconditional default because uncorrelated reviewers catch what one misses — never auto-downgrade based on stakes or surface size. If the user wants a quicker single-reviewer pass, they say `--claude` (single inline pass); absent that flag, run the full panel even for a small target.
- **Graceful degradation, loudly.** Always announce the resolved panel and never silently drop a reviewer. A one-reviewer run is a single opinion, not a panel, and the synthesis must say so.
- **Identical brief payload across the panel.** Any framing asymmetry between reviewers defeats the cross-model signal. Write the Phase 2 brief once and send the same payload to each — the transport wrappers differ per CLI, so aim for semantic equivalence, not byte equality.
- **Cross-model, not cross-instance.** One Claude + one Gemini + one Codex + one Grok. Two Claudes correlate; non-correlated error modes are the whole point.
- **Specificity over breadth:** Five specific findings beat twenty vague observations.
- **No hedging:** "This will fail when X" not "This might potentially have issues with X."
- **Severity is implicit in the layer:** Don't add separate severity labels — the lower the layer number, the more a finding matters: Layer 0 outranks Layer 1, which outranks Layer 4. A lone reviewer's Layer 0 finding outranks every seat agreeing on a Layer 4 nit.
- **The tiebreak is the work.** You're not chairing a committee or counting votes — investigate disagreements and decide. A panel that mechanically applies every suggestion is a slower single pass.
- **Don't pad:** If the implementation is solid, say so. "Clean pass" is a valid audit result.
- **Scope to what was asked:** Audit the target, not the surrounding codebase. Flag adjacent concerns briefly if they're blocking, but don't expand scope without asking.
- **Earn the clean pass:** Layer 0-3 findings are uncomfortable but high-value — they mean the problem or the approach itself may be wrong. A clean pass at these layers must be earned by articulating *why* the frame and the approach are right, not assumed by jumping to implementation details. Layer 0's clean pass is the easiest to fake: "the problem is as stated" is adoption, not validation — the pass is earned by restating the goal and showing the stated problem serves it.
