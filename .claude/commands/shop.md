---
name: shop
description: Purchase decision support — clarify what the user actually needs and why via an interactive quiz, then research fresh candidates and recommend
---

# Shop — Purchase Guidance

Decision support for buying a thing: clarify the *why* first, sharpen the *what* through a structured quiz, then research current candidates and recommend. Works standalone — no vault required (vault context, if present, only informs questions).

**Args:** optionally the thing being considered (e.g. `/shop standing desk`), plus optional `--quick` — collapses the flow for low-stakes buys: skip Phase 1 probing, single quiz call (budget + hard requirements, always including compatibility/ecosystem — for spec-defined categories like cables and chargers, compatibility IS the purchase), lighter research (3-4 candidates, one solid source each). Default is always the full flow; the skill does not silently downgrade on its own judgement. Precedence: if an exact model is named alongside `--quick`, the fully-specified shortcut (Phase 1) governs the questioning; `--quick` then only trims research depth. If invoked bare, open with "What are you looking to buy?"

## 1. Frame — the why before the what

Before any specs, understand the job. Ask open questions, 1-2 at a time (not a questionnaire):

- What prompted this now? (something broke, new need, upgrade itch, saw a recommendation)
- What job will it actually do? Concrete usage scenarios, not abstract categories.
- What is it replacing, and what specifically is wrong with the incumbent?
- What does success look like — three months in, what would make this a clearly good purchase?

**Fully-specified item shortcut:** if the user names an exact model ("/shop [brand] [model]"), don't run full probing — ask one sanity question ("what's the job, and what's it replacing?") to catch a wrong-category buy, plus only the missing load-bearing constraints a defensible comparison needs (budget ceiling, compatibility/ecosystem), then go straight to research/verification of that item against its nearest rivals.

**Respect de-emphasis:** when the user signals a thread is settled ("that's fine", "not the point"), stop probing it — don't circle back from another angle.

**Challenge the category if the job suggests it.** The stated product may not be the right solution for the underlying need — a different category, a repair, borrowing/renting, or not buying at all can be the honest answer. Zoom out before optimising within the stated frame. If the frame survives, proceed.

## 2. Quiz — structured clarification (AskUserQuestion)

Once the why is clear, run the quiz. Up to 2 calls, ≤4 questions each; **skip anything Phase 1 already answered.** If loaded context (vault notes, earlier conversation) already records a prior decision on a question, state it as the working assumption ("you previously wanted X — still true?") rather than re-asking from scratch. Options must be concrete and mutually exclusive — if you can't name the category's real forks from knowledge, do a quick web search *first* so the quiz offers named sub-types, not vague tiers.

**Shape call:**
- **Sub-type fork** — the category's genuine variants, each mapped to a use-case ("X suits A; Y suits B")
- **Budget bracket** — 3 concrete brackets with what each realistically buys in this category
- **Timeline** — need it by a date vs happy to wait for the right one / a sale cycle
- **Usage intensity** — daily workhorse vs occasional; expected lifespan

**Constraints call:**
- **Hard requirements** — multiSelect collects the set; the quiz tool can't capture order, so follow up with one conversational line asking the user to rank their selections firmest → negotiable
- **Compatibility/ecosystem** — existing gear, platform, sizing, region/voltage/standards
- **Condition openness** — new only vs refurb/used acceptable
- **Deal-breakers** — anything that instantly disqualifies a candidate

## 3. Research — fresh and external

- **Comparative verdicts need fresh research.** Search the current market — models refresh, prices move, last year's "best X" is stale. Never recommend from memory alone.
- Check availability and pricing in the user's region (locale from CLAUDE.md or ask).
- **Verify decision-bearing claims against primary sources** — manufacturer spec sheets and measured/tested reviews, not aggregator listicles or marketing copy. Note where a load-bearing claim is marketing-only.
- **Check whether a hard requirement is a platform behaviour, not a product differentiator.** Some stated requirements are governed by the user's phone/OS/ecosystem rather than the product itself. Verify the mechanism before filtering candidates on it — if it's platform-level, say so and stop using it as a filter.
- Generate 5-8 candidates → filter to 2-3 finalists against the ranked hard requirements, checking recent-review red flags.
- **High-stakes escalation:** for expensive or hard-to-reverse purchases, offer to run the research through a deep-research harness (multi-source fan-out with adversarial verification — e.g. a `deep-research` skill) instead of inline searching. Check such a skill is actually available in this install *before* offering it; if none is, offer a deeper inline pass instead (more sources, cross-checked claims). The user accepts or declines; don't escalate silently.

## 4. Recommend

- Compact comparison table: price, the ranked requirements, key deltas. Keep prose reasoning outside the cells.
- **One recommendation**, with reasoning tied explicitly back to the Phase 1 why (where Phase 1 ran; on `--quick`, tie it to the quiz answers instead).
- Explicit "Ruled out" lines for transparency.
- Verbatim source quotes for load-bearing facts (specs, measured results) — protects against quick-read errors.
- **"Don't buy" is a valid verdict.** If the incumbent is fine, a model refresh is imminent, or nothing justifies the price, say so.
- **"Buy later" needs a dated backstop.** A wait verdict (sale cycle, imminent refresh) with no trigger is a revisit that silently evaporates. On vault installs — meaning `_shared-rules.md` §1 vault resolution succeeds; if it fails or the file is absent, skip this without asking — offer to write one dated line ("revisit [item] — [trigger]") to `{VAULT}/01 Now/Tickler.md`; derive the date from the trigger event, and skip if the user declines. The Tickler is a shared planning file — write via the `_shared-rules.md` §5 locking mechanism, not the Edit tool.
- If no candidate clears the bar: name which constraint failed and ask which to relax — budget → nice-to-haves → hard requirements last.

## 5. Handoff

- Purchase channel advice: direct vs marketplace, warranty implications, price-tracking if timing is flexible.
- The user executes the purchase.
- **Finish in-conversation.** Don't persist shortlists, carts, or prices to the vault — pricing rots in days and the notes become maintenance liability. Only write a vault note if the user asks, or the purchase is a major, revisitable decision — and then record the decision and reasoning, not the price table.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and log observations at the end per that file.
