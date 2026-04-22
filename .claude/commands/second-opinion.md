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
- You just finished a first-pass review (e.g. `/audit`) and want an independent check before acting on the findings. This is *review-of-review* mode — the highest-value use of the skill, and also the most prone to bias-leaking. See Phase 1 step 5.
- You're stuck between two framings of a problem and want non-correlated voices.
- You've already run a panel, applied fixes, and want to verify the fixes against the reviewers who raised the concerns (iterative mode — see below).

**DO NOT use for:**
- Trivial bug fixes, typo corrections, obvious refactors. Running reviewers takes 2–5 minutes and burns model API calls; spending that on a one-line change is theatre, not verification.
- Exploratory questions where you haven't yet committed to a direction. This skill reviews *work*, not open-ended brainstorming.
- Work where you already know the answer and want confirmation. That's sycophancy-shopping — run reviewers only if you're willing to be wrong.

## The two modes

**Mode A — Independent panel (parallel, fresh reviewers).** Two reviewers from different model families, each seeing the work for the first time, running concurrently. Maximum non-anchoring; cross-model signal on agreement vs disagreement. Use when the question is "is my understanding of this right?" and you want judgement uncorrelated with the in-session conversation. This is the default mode and the one validated in real use.

**Mode B — Iterative deepening (sequential, resumed reviewers) — unverified, see Phase 2B warning.** Bring the *same* reviewer(s) back for round 2, 3, or more. They carry their prior context forward — you don't have to re-brief them on the work or the history. Use when:
- You've fixed the thing the reviewer flagged in round 1 and want to know whether the fix actually resolves their concern.
- The reviewer was uncertain in round 1 and you've gathered new evidence (docs, test results, source reads) that should shift the judgement.
- You want to push back on a critique and have the reviewer defend or revise it.
- You want depth on a specific finding the reviewer raised, rather than breadth across new ones.

**They compose.** The canonical workflow is panel-first, then iterate: run Mode A for round 1 to surface candidate findings, act on the findings the tiebreak selects, then run Mode B in round 2 to verify the fixes against the reviewers who raised them. Avoid running a fresh panel in round 2 — you pay the briefing cost again and lose continuity with the specific concerns that produced the fixes.

**Don't over-iterate.** If you've gone back to the same reviewer three times on the same issue and you still disagree, the problem isn't review cadence — it's a genuine substantive disagreement. Stop iterating, escalate to the user, and present both positions.

## Philosophy

**Fresh context is a tool, not a virtue.** A reviewer who walks in cold catches things the author has normalised — that's Mode A's value. A reviewer who already has context can go deeper on a specific thread without re-briefing cost — that's Mode B's value. But Mode A's freshness is conditional on the brief: if you brief a fresh reviewer with a summary written by the author of the work being reviewed, you've laundered your framing into their context and their judgement is no longer independent. This is the skill's single biggest failure mode; Phase 1 step 5 addresses it directly. Mode B doesn't suffer from this (the reviewer's context is their *own* prior reading, not the author's summary) — one reason Mode B is sometimes the better tool even for first-round questions.

**The tiebreak is the work.** You are not running a committee. You are not counting votes. When reviewers split, investigate the disagreement, decide which side is right, and say *why* — don't hedge, don't average. Correlated agreement is weak evidence, not ground truth: two models trained on similar data can confidently share a blind spot. And running the panel surfaces candidate findings, not verdicts — the user (plus you) decides what to act on. A second opinion that mechanically applies every suggestion is just a slower first pass.

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
   - **A "what the work gets right" section in the output format, capped at ~5 bullets.** Without this, a reviewer who only reports problems leaves the synthesis unable to distinguish "section X was approved" from "section X was not mentioned" — and silence is not endorsement. Forcing reviewers to name what they think works also makes disagreement more visible in Phase 3: if Opus lists something as a strength and Gemini lists the same thing as a problem, that's a load-bearing disagreement you'd otherwise miss.
   - **Severity-stratified output with explicit maxes** (e.g. "load-bearing: max 5 / worth-fixing: max 8 / polish: max 5"). Uncapped lists invite reviewers to pad with shallow observations to look thorough; explicit caps force them to rank and drop the weak ones.

5. **For review-of-review mode in Mode A (second opinion on a prior audit, code review, or decision memo written by the current session), add this explicitly:**
   - **Require the reviewers to read the original work product from source.** The brief gives them the path; their job is to go read it, not to take your word for what it says. Include a sentence like: "Read the work yourself before forming opinions. The summary below is supplementary context, not a substitute — treat it as possibly biassed because it was written by the author of the work being reviewed."
   - List the prior findings and fixes faithfully, but label them as the *author's* claims, not as facts.
   - Ask the reviewer to judge each claim on its own merits after reading the current state.

   Without this, both reviewers inherit your framing and their "agreement" becomes an artefact of the brief rather than genuine independent judgement. This is not optional for review-of-review mode. For Mode B this is less urgent — the continuing reviewer already has their own reading from round 1 — but it's still worth reminding them to re-read sections that changed since round 1.

6. **Strip bias from the brief.** Don't frame the question in a way that telegraphs your preferred answer. Present what was done, not whether it was good. Ask the reviewer to apply their own framework, not to rate yours.

Write the brief once and save it to a scratch file with a unique name — e.g. `mktemp -t second-opinion-prompt.XXXXXX.md` on macOS/Linux, or a timestamped path like `%TEMP%\second-opinion-prompt-<timestamp>.md` on Windows. Record the path; you'll reuse it twice in Phase 2 (once to extract its contents for the Claude reviewer, once to pipe to the CLI reviewer). Unique names matter because two concurrent `/second-opinion` runs on the same machine would otherwise clobber a shared hard-coded path silently.

### Phase 2A: Launch a fresh panel (Mode A)

**Before launching: confirm Gemini is available** with `gemini --version` via Bash. If it errors out, the CLI isn't installed; use the single-reviewer fallback in step 3. If the version is older than 0.33, use the flag-less invocation in step 2.

Send the brief to both reviewers in a **single message** with concurrent tool calls:

1. **Fresh Claude** via the Agent tool. Use `subagent_type: general-purpose`. **Read the scratch file's contents and pass them verbatim as the Agent's `prompt` argument** — the identical string that the Gemini call receives. Do not paraphrase, summarise, or extract; the two reviewers must see the same text, byte for byte, or you've re-introduced framing asymmetry. Tell the Agent explicitly in the prompt: independent judgement, disagree where warranted, no sycophancy, no "looks good overall" hedging. If you skip the disagree directive, fresh Claude defaults to polite confirmation of whatever framing you gave it.

   **After the tool call completes, surface the Agent ID in your user-visible response text** — e.g. `Panel spawned: Opus agent a5abc789520b0879a`. This makes the ID recoverable from the conversation transcript even after the raw tool result scrolls out of context, which matters for Mode B round 2. Don't rely on re-reading the tool result hours later.

2. **Gemini CLI** via Bash, in parallel with the Agent call. **Pass `timeout: 300000` (5 minutes) to the Bash tool call** — the default 120 s will kill Gemini mid-review on any non-trivial target. This is load-bearing; the runner won't intuit it from "budget 5 minutes" alone.

   Preferred invocation (gemini ≥ 0.33) — substitute `<prompt-path>` with the path recorded in Phase 1:
   ```
   cat <prompt-path> | gemini -p "Follow the instructions in the piped input exactly." --approval-mode plan -o text
   ```
   `--approval-mode plan` gives Gemini read-only tool access — it can Read files but not edit them, matching the independent-review intent. `-o text` keeps the output pipe-friendly.

   Fallback if the flags aren't supported by the installed version:
   ```
   cat <prompt-path> | gemini -p "Follow the instructions in the piped input exactly."
   ```

   **After the call completes, capture and surface the Gemini session index.** Run `gemini --list-sessions | tail -3`; sessions are listed in ascending chronological order, so the **last/highest-numbered row** is the most recent. The leading numeric column (the `N.` before the prompt preview) is the index you want. Record it and surface it in the user-visible response text alongside the Agent ID (e.g. `Panel spawned: Opus agent a5abc789, Gemini session #12`). You'll need this for Mode B round 2, and "latest" is not a safe shortcut (see Phase 2B step 2). Verified against gemini 0.38.2; if the output format ever diverges (no header, different column layout, reversed ordering), note what you saw and flag it back to this file — gemini's `--resume` only accepts an index number or the string `"latest"`, so if index parsing breaks, Mode B round 2 isn't recoverable and you fall back to a fresh Mode A panel.

3. **If a reviewer is unavailable** — Gemini not installed, API unreachable, quota hit, Agent tool error, subagent timeout — fall back to the single available reviewer and **say so explicitly in the synthesis**. Do not silently pretend the panel ran. A one-reviewer run isn't a panel; it's a single opinion with one extra pair of eyes, and the "cross-model signal" claim no longer applies.

### Phase 2B: Resume prior reviewers (Mode B)

> ⚠️ **Mode B has not yet been executed end-to-end in anger.** The steps below are a first-pass specification derived from Claude Code and Gemini CLI documentation, not from observed behaviour. Operational gaps may surface on first use — specifically around Agent ID lifetime across session boundaries, SendMessage tool availability, and gemini session indexing under concurrent use. Treat Mode B as a specification you are helping to validate: when you hit a gap, surface it back to this skill file rather than working around it silently. The whole point of the re-audit that produced this warning was to avoid pretending Mode B is production-ready when it hasn't been proven.

Use this phase instead of 2A when you're iterating — the reviewers are already spun up from a previous round.

0. **Load SendMessage first.** SendMessage is typically a deferred tool in Claude Code — if it's not in your base tool set, call `ToolSearch` with `select:SendMessage` to fetch its schema before proceeding. Calling SendMessage before its schema is loaded fails with an input-validation error. You cannot skip this step. **If `ToolSearch` returns nothing for SendMessage**, the tool may be gated on an Agent being in flight in the current session — confirm the Phase 2A Agent is still alive before concluding SendMessage is simply unavailable. If the Agent is genuinely gone, Mode B isn't recoverable; fall back to a fresh Mode A panel (step 1 covers this).

1. **Check the Agent ID is still alive.** Mode B requires the Agent spawned in Phase 2A to still be resumable. Agent ID lifetime across session boundaries (`/park` + `/pickup`, session reload, context compaction) is not currently verified — assume session-scoped until proven otherwise. If you've parked and unparked since round 1, or if /compact has run, or if you can't find the Agent ID in the conversation transcript, the Agent is likely gone. Fall back to a fresh Mode A panel and accept the briefing cost.

2. **Write the round-2 prompt to a scratch file**, same pattern as Phase 1 — `mktemp -t second-opinion-round2.XXXXXX.md` or your OS equivalent (unique per invocation; record the path). Keep it narrow: one or two tight questions, not "review the whole thing again." Mode B's value is depth on a specific thread, not breadth. Write the prompt as a continuation: "Round 1 of this review surfaced finding X. The author has now done Y in response. Please re-read [specific sections that changed] and judge whether Y resolves your original concern. If it doesn't, what's still wrong? If it does, say so plainly." Using a scratch file (rather than inline `echo`) avoids shell-escaping problems when the prompt contains backticks, `$`, or quotes — exactly the same reason Phase 2A uses a scratch file.

3. **Look up the Gemini session index deterministically.** If you surfaced the index in Phase 2A (as instructed), use that. If not, run `gemini --list-sessions` and identify the right session by timestamp and project. **Do not use `--resume latest`** — "latest" resolves to the most recent gemini session for the project, so if you or any other process has run gemini for anything in between (even a quick one-shot), `latest` resumes the wrong session. Always resume by numeric index.

4. **Invoke both reviewers in a single message with concurrent tool calls**, same as Phase 2A — parallel, not sequential:

   - **SendMessage to the resumed Claude Agent**: `to` = the Agent ID recorded in Phase 2A, `content` = the round-2 prompt (read from the scratch file). The resumed Agent keeps its full prior context; you do **not** re-brief from scratch.

   - **Gemini CLI via Bash** with `timeout: 300000` — substitute `<round2-path>` with the path recorded in step 2:
     ```
     cat <round2-path> | gemini -p "Continue the prior review." --resume 12 --approval-mode plan -o text
     ```
     Replace `12` with your actual session index. If gemini's resume semantics don't round-trip cleanly (session state missing, prompt interpreted as fresh), fall back to running gemini fresh with a brief that quotes the round-1 reviewer output verbatim as context — not ideal, but recoverable. **In the Phase 3 synthesis, annotate this case explicitly** (e.g. `[Gemini r2, fresh-with-replay]`) so the reader can distinguish a true resume from a replayed brief — they're not equivalent signals.

5. **If only one reviewer is being iterated** (you only care about one reviewer's finding in round 2), run that one in Phase 2B and skip the other. Note clearly in the synthesis that round 2 is single-reviewer.

### Phase 3: Tiebreak and synthesise

Once the reports come back, write the synthesis. **Tag every finding with attribution** — `[Opus+Gemini]` for shared finds, `[Opus]` or `[Gemini]` for unique ones, `[Opus r2]` or `[Gemini r2]` for points from a single reviewer's Mode B round-2 response, `[Opus+Gemini r2]` when both iterated reviewers land on the same round-2 finding. Attribution is not optional: without it, the panel's provenance is lost and the tiebreak becomes unreviewable. The user can't audit your reasoning if they can't see which reviewer raised what, or which round it came from.

1. **Confirmed by both `[Opus+Gemini]`** — findings both reviewers agree on. Highest-confidence action items, but *not* ground truth: correlated agreement is weak evidence, especially within a single model family. One line each.
2. **Disputed** — points where the reviewers disagree, or where a round-2 reviewer revised their round-1 position, or where a reviewer's critique contradicts a claim the brief asserted on the author's behalf. For each, state your decision and *why*. Pick a side and justify it. Don't hedge. Don't "both are valid."
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
- **Surface Agent IDs and Gemini session indices in visible response text after Phase 2A.** Raw tool results scroll out of context; visible transcript text persists. You can't resume a reviewer in Mode B if you can't find their handle.
- **Brief fresh reviewers like colleagues walking in cold.** Mode A reviewers have zero prior knowledge of the task, the conversation, or why this matters. The brief must stand on its own. Mode B reviewers already have context — don't re-send the whole brief, send a tight continuation.
- **Two reviewers is the default, not the ceiling.** Scale to three only if the first two agree on everything and you suspect they're correlating on a shared blind spot. Never run four — you're paying coordination cost for diminishing signal.
- **Cross-model, not cross-instance.** Two fresh Claudes will correlate more than one Claude plus one Gemini. Use different model families when you can — non-correlated error modes is the whole value proposition.
- **Report disagreement plainly.** When reviewers split, or when a Mode B reviewer revises a round-1 position, say so in the synthesis. That's often more useful than the individual verdicts.
- **Attribution is mandatory.** Every finding in the synthesis carries a `[Opus]`, `[Gemini]`, `[Opus+Gemini]`, or `[... r2]` tag. This lets the user audit your tiebreak and catches the laundering failure mode where reviewer claims get presented as your own conclusions.
- **Don't over-iterate in Mode B.** Three rounds on the same thread and still disagreeing means the disagreement is substantive, not procedural. Escalate to the user with both positions clearly stated; don't run round 4.
- **Scope discipline.** This is not `/audit` redone from scratch. Trust the reviewers to bring their own framework; your job is synthesis, not re-review.
- **Verify before acting on unique finds.** A single reviewer confidently flagging a bug is a hypothesis, not a fact. Check it (read the code, test the command, look up the docs, read the source) before editing anything. Especially true for claims about tool behaviour, platform quirks, and version-sensitive APIs — a reviewer that confidently asserts "X doesn't work on Windows" can be wrong, and acting on it without verification means you've shipped a regression to fix a non-issue.
- **Mode B is a first-pass specification, not a validated workflow.** Until it's been executed end-to-end at least once, treat it with the same scepticism you'd apply to any untested procedure. Surface gaps back to this file rather than working around them silently — the skill gets sharper with every real use.
