---
name: second-opinion
aliases: [tiebreak, panel]
description: Get an independent second opinion on work, decisions, or a prior audit by running two fresh reviewers in parallel and synthesising
---

# Second Opinion - Parallel Independent Review

Get an independent second opinion on a piece of work — code, writing, an audit pass, a plan, a judgement call — by running two fresh reviewers in parallel and acting as tiebreaker.

## Philosophy

**Fresh context produces independent judgement.** A reviewer who has seen the work being defended will anchor on it. A reviewer who walks in cold catches things the author (and their in-session AI collaborator) has normalised. The whole point of this skill is to deliberately surface perspectives that haven't been shaped by the conversation so far.

**Two reviewers, not one.** A single second opinion still leaves a 1-vs-1. Running two in parallel — one Claude, one non-Claude — shows you *where they agree* (high-confidence signal) and *where they disagree* (contested judgement worth thinking about). Cross-model disagreement is the most valuable output.

**The tiebreak is the work.** You are not running a committee. You are not counting votes. When the reviewers split, your job is to investigate the disagreement, decide which side is right, and say *why* — not to hedge or average.

**Don't automatically execute.** Running the panel surfaces candidate findings. The user (plus you) decides what to act on. A second opinion that mechanically applies every suggestion is just a slower first pass.

## Instructions

### Phase 1: Identify the target and construct the brief

1. **If the user specified the target, load it.** If not, ask — don't guess. The target can be a file, a PR, a prior audit pass, a decision, or a plan.
2. **Write a self-contained brief** that each reviewer can read cold. Include:
   - What the work product is and where it lives (absolute path if local).
   - What context matters: audience, publication target, constraints, dependencies, the author's situation.
   - What was previously done — for a review-of-review (second opinion on a `/audit` pass), list the findings and fixes faithfully without editorialising.
   - The specific question(s) you want judgement on.
   - The output format: structured sections, word cap, no-hedging directive.
3. **Strip bias from the brief.** Don't frame the question in a way that telegraphs your preferred answer. Present what was done, not whether it was good. Ask the reviewer to apply their own framework, not to rate yours.

Write the brief once — both reviewers get the same text verbatim. Save it to a temp file (e.g. `/tmp/second-opinion-prompt.md`) so you can pipe it to the CLI reviewer without shell-escaping pain.

### Phase 2: Launch reviewers in parallel

Send the brief to both reviewers in a **single message** with concurrent tool calls:

1. **Fresh Claude** via the Agent tool. Use `subagent_type: general-purpose` and pass the full brief as the prompt. Tell it explicitly: independent judgement, disagree where warranted, no sycophancy, no "looks good overall" hedging. If you don't tell it to disagree, it will default to polite confirmation of the framing.

2. **Gemini CLI** via Bash, in parallel with the Agent call:
   ```
   cat /tmp/second-opinion-prompt.md | gemini -p "Follow the instructions in the piped input exactly." --approval-mode plan -o text
   ```
   `--approval-mode plan` gives Gemini read-only tool access — it can Read files but not edit them, which matches the independent-review intent. `-o text` keeps the output pipe-friendly. Budget ~300s timeout for non-trivial targets.

If one reviewer is unavailable (Gemini not installed, API unreachable, quota hit), fall back to the single available reviewer and **say so explicitly in the synthesis** — don't silently pretend the panel ran.

### Phase 3: Tiebreak and synthesise

Once both reports come back, write the synthesis in this order:

1. **Confirmed by both** — findings the reviewers agree on. These are your highest-confidence action items. One line each.
2. **Disputed** — points where the reviewers disagree, OR where one reviewer's critique conflicts with the prior work being reviewed. For each, state your decision and *why*. This is the tiebreaker work — don't skip it, don't hedge, don't "both are valid." Pick a side and justify it.
3. **Uniquely flagged** — issues only one reviewer raised. Judge each on merit: a real issue, or a reviewer idiosyncrasy? Legitimate misses get promoted to the action list; shallow observations get dropped with a reason.
4. **Priority stack** — the full action list ordered by impact (critical → polish). Be explicit about severity so nothing silently rides along on the coat-tails of something important.
5. **"I don't know" items** — if either reviewer flagged something you can't confidently adjudicate without verification (docs, tests, running code), list it separately. Do *not* act on unverified claims just because they sound plausible.

### Phase 4: Decide next steps

Present the verdict and priority stack, then confirm with the user what to act on. Default to asking before applying further fixes unless the user pre-authorised action. A critical finding (something that causes silent failure or data loss) may warrant a clearer "I strongly recommend applying X before shipping" nudge — but still the user's call.

## Guidelines

- **Reviewers must be genuinely fresh.** Don't continue an existing Agent session from a prior `/audit` or `/review-pr`. Spawn a new one. Fresh context is the whole point — a resumed agent has already anchored.
- **Brief them like colleagues walking in cold.** They have zero prior knowledge of the task, the conversation, or why this matters. The prompt must stand on its own.
- **Two reviewers, not three.** A third turns synthesis into a committee and dilutes the signal. Two is enough to surface agreement vs disagreement cleanly. If the two agree on everything, that *is* the answer — stop there.
- **Cross-model, not cross-instance.** Two fresh Claudes will correlate more than one Claude plus one Gemini. Use different model families when you can — the whole value proposition is non-correlated error modes.
- **Report disagreement plainly.** When reviewers split, say so in the synthesis. That split is often more useful than the individual verdicts.
- **Don't launder the reviewers' claims as your own.** Attribute findings to which reviewer raised them, especially when you're overriding one. That lets the user audit your tiebreak.
- **Scope discipline.** This is not `/audit` redone from scratch. Trust the reviewers to bring their own framework; your job is synthesis, not re-review. If the target is large, the brief tells them to scope.
- **Verify before acting on unique finds.** A single reviewer confidently flagging a bug is a hypothesis, not a fact. Check it (read the code, test the command, look up the docs) before editing anything. Especially true for claims about tool behaviour, platform quirks, and version-sensitive APIs.
