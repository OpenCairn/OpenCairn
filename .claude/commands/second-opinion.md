---
name: second-opinion
aliases: [tiebreak, panel]
description: Get an independent second opinion on work or decisions — either by running a fresh cross-model panel in parallel, or by bringing the same reviewers back for iterative deepening
---

# Second Opinion - Parallel Panel and Iterative Review

Get a second opinion on a piece of work — code, writing, an audit pass, a plan, a judgement call — by running reviewers in one of two modes, then synthesising.

## When to use this

**TRIGGER when:**
- High-stakes work is about to ship (publication, merge to main, send to client, deploy to prod) and a single reviewer's confidence feels load-bearing.
- A decision is hard to reverse and the cost of being wrong exceeds the 2–5 minute cost of running the review.
- You just finished a first-pass review (e.g. `/audit`) and want an independent check before acting on the findings. This is *review-of-review* mode — the highest-value use of the skill, and also the most prone to bias-leaking. See Phase 1 step 4.
- You're stuck between two framings of a problem and want non-correlated voices.
- You've already run a panel, applied fixes, and want to verify the fixes against the reviewers who raised the concerns (iterative mode — see below).

**DO NOT use for:**
- Trivial bug fixes, typo corrections, obvious refactors. Running reviewers takes 2–5 minutes and burns model API calls; spending that on a one-line change is theatre, not verification.
- Exploratory questions where you haven't yet committed to a direction. This skill reviews *work*, not open-ended brainstorming.
- Work where you already know the answer and want confirmation. That's sycophancy-shopping — run reviewers only if you're willing to be wrong.

## The two modes

**Mode A — Independent panel (parallel, fresh reviewers).** Two reviewers from different model families, each seeing the work for the first time, running concurrently. Maximum non-anchoring; cross-model signal on agreement vs disagreement. Use when the question is "is my understanding of this right?" and you want judgement uncorrelated with the in-session conversation. This is the default mode.

**Mode B — Iterative deepening (sequential, resumed reviewers).** Bring the *same* reviewer(s) back for round 2, 3, or more. They carry their prior context forward — you don't have to re-brief them on the work or the history. Use when:
- You've fixed the thing the reviewer flagged in round 1 and want to know whether the fix actually resolves their concern.
- The reviewer was uncertain in round 1 and you've gathered new evidence (docs, test results, source reads) that should shift the judgement.
- You want to push back on a critique and have the reviewer defend or revise it.
- You want depth on a specific finding the reviewer raised, rather than breadth across new ones.

**They compose.** The canonical workflow is panel-first, then iterate: run Mode A for round 1 to surface candidate findings, act on the findings the tiebreak selects, then run Mode B in round 2 to verify the fixes against the reviewers who raised them. Avoid running a fresh panel in round 2 — you pay the briefing cost again and lose continuity with the specific concerns that produced the fixes.

**Don't over-iterate.** If you've gone back to the same reviewer three times on the same issue and you still disagree, the problem isn't review cadence — it's a genuine substantive disagreement. Stop iterating, escalate to the user, and present both positions.

## Philosophy

**Fresh context is a tool, not a virtue.** A reviewer who walks in cold catches things the author has normalised — that's Mode A's value. A reviewer who already has context can go deeper on a specific thread without re-briefing cost — that's Mode B's value. Pick the mode that matches your question, not the one that feels more rigorous.

**Mode A's freshness is conditional on the brief.** If you brief a fresh reviewer with a summary written by the author of the work being reviewed, you've laundered your framing into their context and their judgement is no longer independent. This is the skill's single biggest failure mode; Phase 1 step 4 addresses it directly. Mode B doesn't suffer from this (the reviewer's context is their *own* prior reading, not the author's summary) — one reason Mode B is sometimes the better tool even for first-round questions.

**Two reviewers surface disagreement; three surface votes.** The valuable signal isn't the aggregate verdict — it's *where reviewers disagree*, because that's where the real judgement calls live. Two reviewers expose disagreement cleanly; a third just adds a third opinion to count. Scale up to three only if the two agree on everything and you suspect they're correlating.

**Cross-model matters more than cross-instance.** Two fresh Claudes share training data, prior-art exposure, and many error modes. One Claude plus one Gemini gives genuinely non-correlated opinions. If only one model family is available, say so in the synthesis — the value proposition changes.

**The tiebreak is the work.** You are not running a committee. You are not counting votes. When reviewers split, investigate the disagreement, decide which side is right, and say *why* — don't hedge, don't average. Correlated agreement is weak evidence, not ground truth: two models trained on similar data can confidently share a blind spot.

**Don't automatically execute.** Running reviewers surfaces candidate findings. The user (plus you) decides what to act on. A second opinion that mechanically applies every suggestion is just a slower first pass.

## Instructions

### Phase 1: Identify the target, pick the mode, construct the brief

1. **If the user specified the target, load it.** If not, ask — don't guess. The target can be a file, a PR, a prior audit pass, a decision, or a plan.

2. **Pick the mode.** If this is round 1 on a new question and you want independent judgement: Mode A. If you're iterating on a specific finding from a previous review and want the same reviewer(s) back: Mode B. If you're not sure, default to Mode A. Tell the user which mode you're running so they know what to expect.

3. **Check the target fits.** If it's too large to fit in a reviewer's context window (a multi-file system, a whole repo, an entire knowledge base), scope it in the brief: name the files or sections to focus on, or ask the user to narrow scope. A run that silently skips half the target is worse than a scoped one that's honest about its boundaries.

4. **Write a self-contained brief** that each reviewer can read. For Mode A they read it cold; for Mode B they read it on top of their existing context. Include:
   - What the work product is and where it lives (absolute path if local).
   - What context matters: audience, publication target, constraints, dependencies, the author's situation.
   - The specific question(s) you want judgement on.
   - The output format: structured sections, word cap, explicit "no hedging, disagree where warranted, no sycophancy" directive.

5. **For review-of-review mode in Mode A (second opinion on a prior audit, code review, or decision memo written by the current session), add this explicitly:**
   - **Require the reviewers to read the original work product from source.** The brief gives them the path; their job is to go read it, not to take your word for what it says. Include a sentence like: "Read the work yourself before forming opinions. The summary below is supplementary context, not a substitute — treat it as possibly biassed because it was written by the author of the work being reviewed."
   - List the prior findings and fixes faithfully, but label them as the *author's* claims, not as facts.
   - Ask the reviewer to judge each claim on its own merits after reading the current state.

   Without this, both reviewers inherit your framing and their "agreement" becomes an artefact of the brief rather than genuine independent judgement. This is not optional for review-of-review mode.

   For Mode B this is less urgent — the continuing reviewer already has their own reading from round 1 and won't accept your framing uncritically. But it's still worth reminding them to re-read any sections that changed since round 1.

6. **Strip bias from the brief.** Don't frame the question in a way that telegraphs your preferred answer. Present what was done, not whether it was good. Ask the reviewer to apply their own framework, not to rate yours.

Write the brief once and save it to a scratch file. Use `/tmp/second-opinion-prompt.md` on macOS/Linux, `%TEMP%\second-opinion-prompt.md` on Windows, or any writable path your OS provides. You'll access that file twice in Phase 2: once to extract its contents for the Claude reviewer, once to pipe to the CLI reviewer.

### Phase 2A: Launch a fresh panel (Mode A)

**Before launching: confirm Gemini is available** with `gemini --version` via Bash. If it errors out, the CLI isn't installed; use the single-reviewer fallback in step 3. If the version is older than 0.33, use the flag-less invocation in step 2.

Send the brief to both reviewers in a **single message** with concurrent tool calls:

1. **Fresh Claude** via the Agent tool. Use `subagent_type: general-purpose`. **Read the scratch file's contents and pass them verbatim as the Agent's `prompt` argument** — the identical string that the Gemini call receives. Do not paraphrase, summarise, or extract; the two reviewers must see the same text, byte for byte, or you've re-introduced framing asymmetry. Tell the Agent explicitly in the prompt: independent judgement, disagree where warranted, no sycophancy, no "looks good overall" hedging. If you skip the disagree directive, fresh Claude defaults to polite confirmation of whatever framing you gave it.

   **Record the Agent's returned ID** from the tool result — you'll need it for Mode B round 2.

2. **Gemini CLI** via Bash, in parallel with the Agent call. **Pass `timeout: 300000` (5 minutes) to the Bash tool call** — the default 120 s will kill Gemini mid-review on any non-trivial target. This is load-bearing; the runner won't intuit it from "budget 5 minutes" alone.

   Preferred invocation (gemini ≥ 0.33):
   ```
   cat /tmp/second-opinion-prompt.md | gemini -p "Follow the instructions in the piped input exactly." --approval-mode plan -o text
   ```
   `--approval-mode plan` gives Gemini read-only tool access — it can Read files but not edit them, matching the independent-review intent. `-o text` keeps the output pipe-friendly.

   Fallback if the flags aren't supported by the installed version:
   ```
   cat /tmp/second-opinion-prompt.md | gemini -p "Follow the instructions in the piped input exactly."
   ```

   Gemini's CLI auto-assigns a session index to the run; you can retrieve it later with `gemini --list-sessions` when you want to resume in Mode B.

3. **If a reviewer is unavailable** — Gemini not installed, API unreachable, quota hit, Agent tool error, subagent timeout — fall back to the single available reviewer and **say so explicitly in the synthesis**. Do not silently pretend the panel ran. A one-reviewer run isn't a panel; it's a single opinion with one extra pair of eyes, and the "cross-model signal" claim no longer applies.

### Phase 2B: Resume prior reviewers (Mode B)

Use this phase instead of 2A when you're iterating — the reviewers are already spun up from a previous round.

1. **Claude (resumed)** via the Agent tool's `SendMessage` form. Pass the prior Agent's ID (recorded in the Mode A run that surfaced the finding you're iterating on) as the `to` field, and the new message as the content. The resumed Agent keeps its full prior context — you do **not** re-brief from scratch. Instead, write the round-2 prompt as a *continuation*: "Round 1 of this review surfaced finding X. The author has now done Y in response. Please re-read [specific sections that changed] and judge whether Y resolves your original concern. If it doesn't, what's still wrong? If it does, say so plainly."

2. **Gemini (resumed)** via Bash, in parallel with the Claude SendMessage if you want both to iterate, or alone if only one reviewer's finding is under discussion. Resume with `--resume latest` for the most recent session, or `--resume N` for a specific session index (find it with `gemini --list-sessions`):
   ```
   echo "<round-2 prompt>" | gemini -p "Continue the prior review." --resume latest --approval-mode plan -o text
   ```
   Pass `timeout: 300000` to the Bash tool call, same as in 2A.

3. **Keep the round-2 prompt narrow.** Mode B's value is depth on a specific thread, not breadth across new findings. Ask one or two tight questions, not "review the whole thing again."

4. **If you want a second opinion on an iterating reviewer's revised judgement** — i.e. Claude just came back with a round-2 response and you want to stress-test it — that's a Mode A task, not a Mode B task. Run a fresh Gemini panel on the specific point, and attribute carefully in the synthesis.

### Phase 3: Tiebreak and synthesise

Once the reports come back, write the synthesis. **Tag every finding with attribution** — `[Opus+Gemini]` for shared finds, `[Opus]` or `[Gemini]` for unique ones, `[Opus r2]` or `[Gemini r2]` for points from a Mode B round-2 response. Attribution is not optional: without it, the panel's provenance is lost and the tiebreak becomes unreviewable. The user can't audit your reasoning if they can't see which reviewer raised what, or which round it came from.

1. **Confirmed by both `[Opus+Gemini]`** — findings both reviewers agree on. Highest-confidence action items, but *not* ground truth: correlated agreement is weak evidence, especially within a single model family. One line each.
2. **Disputed** — points where the reviewers disagree, or where a round-2 reviewer revised their round-1 position, or where one reviewer's critique conflicts with the prior work being reviewed. For each, state your decision and *why*. Pick a side and justify it. Don't hedge. Don't "both are valid."
3. **Uniquely flagged `[Opus]` or `[Gemini]`** — issues only one reviewer raised. Judge each on merit: a real issue, or a reviewer idiosyncrasy? Legitimate misses get promoted to the action list; shallow observations get dropped with a reason.
4. **Priority stack** — the full action list ordered by impact (critical → polish), attribution tags preserved. Be explicit about severity so nothing silently rides along on the coat-tails of something important.
5. **"I don't know" items** — if either reviewer flagged something you can't confidently adjudicate without verification (docs, tests, running code, reading source), list it separately. Do *not* act on unverified claims just because they sound plausible. Especially true for claims about tool behaviour, platform quirks, and version-sensitive APIs.

**Failure mode — nothing substantive.** If reviewers return generic praise ("looks good overall", "well-structured", "minor suggestions only"), treat it as weak evidence, not validation. Consider whether the brief was too narrow, whether both models share a training prior that isn't being challenged, or whether the Agent defaulted to polite confirmation despite the disagree directive. Options: re-invoke with a sharper prompt, read the work yourself and look for things the reviewers missed, or downgrade confidence and say so.

### Phase 4: Decide next steps

Present the verdict and priority stack, then confirm with the user what to act on. Default to asking before applying further fixes unless the user pre-authorised action. A critical finding (silent failure, data loss) may warrant a clearer "I strongly recommend applying X before shipping" nudge — but still the user's call.

After the user acts on findings, **consider a Mode B round 2** to verify the fixes against the reviewer who raised the concern. This is especially worth it for findings where the fix is non-obvious or where "does the fix land?" is itself a judgement call. For trivial fixes, skip round 2.

Executing the fixes is outside the scope of this skill. Hand off to direct edits, `/audit`'s fix-and-re-audit loop, or whatever workflow the work product normally lives in.

## Guidelines

- **Pick the mode by question type, not by habit.** Fresh panel (Mode A) for "is my understanding right?"; iterative (Mode B) for "does my fix land?" or "defend or revise this critique." Default to Mode A if the question is genuinely open; default to Mode B if you're coming back to a specific thread from a prior review.
- **Record Agent IDs and Gemini session indices.** You can't resume a reviewer in Mode B if you didn't capture their handle from round 1. Do it reflexively after every Phase 2A run.
- **Brief fresh reviewers like colleagues walking in cold.** Mode A reviewers have zero prior knowledge of the task, the conversation, or why this matters. The brief must stand on its own. Mode B reviewers already have context — don't re-send the whole brief, send a tight continuation.
- **Two reviewers is the default, not the ceiling.** Scale to three only if the first two agree on everything and you suspect they're correlating on a shared blind spot. Never run four — you're paying coordination cost for diminishing signal.
- **Cross-model, not cross-instance.** Two fresh Claudes will correlate more than one Claude plus one Gemini. Use different model families when you can — non-correlated error modes is the whole value proposition.
- **Report disagreement plainly.** When reviewers split, or when a Mode B reviewer revises a round-1 position, say so in the synthesis. That's often more useful than the individual verdicts.
- **Attribution is mandatory.** Every finding in the synthesis carries a `[Opus]`, `[Gemini]`, `[Opus+Gemini]`, or `[... r2]` tag. This lets the user audit your tiebreak and catches the laundering failure mode where reviewer claims get presented as your own conclusions.
- **Don't over-iterate in Mode B.** Three rounds on the same thread and still disagreeing means the disagreement is substantive, not procedural. Escalate to the user with both positions clearly stated; don't run round 4.
- **Scope discipline.** This is not `/audit` redone from scratch. Trust the reviewers to bring their own framework; your job is synthesis, not re-review.
- **Verify before acting on unique finds.** A single reviewer confidently flagging a bug is a hypothesis, not a fact. Check it (read the code, test the command, look up the docs, read the source) before editing anything. Especially true for claims about tool behaviour, platform quirks, and version-sensitive APIs — a reviewer that confidently asserts "X doesn't work on Windows" can be wrong, and acting on it without verification means you've shipped a regression to fix a non-issue.
