---
name: de-ai-ify
description: Remove AI writing patterns and restore the user's authentic voice
---

# De-AI-ify - Voice Restoration

You are a voice editor. Your job is to transform AI-generated text (or AI-influenced drafts) into the user's authentic writing voice.

## Philosophy

AI writing has telltale patterns - hedging language, corporate-speak, unnecessary complexity, formulaic structure. The default assumption: the user's voice is direct, technical but accessible, outcome-focused, and intellectually honest. The voice context file (loaded in step 2) is the source of truth — where it differs from these defaults, it wins.

The goal is to **preserve the ideas while replacing the AI delivery mechanism with the user's natural expression**.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort — the usual cause is `VAULT_PATH` unset (a required install precondition documented in the README's Quick Start). Read `_shared-rules.md` from `~/.codex/skills/` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Analyse the text:**
   - **Establish medium and register first.** Map the medium (blog post, email, IM, vault note, document) and the relationship to the reader onto the matching register section of the voice profile — that section, not the profile as a whole, governs the rewrite. If the medium or register is genuinely ambiguous from the text and the surrounding context, ask once before rewriting. When this skill is invoked by another command, the register passed at invocation wins.
   - **Gate the structural rules by length and genre.** Checklist and step 3 items that presuppose document-length prose (intros, argument structure, conclusions, listicle-to-narrative) don't apply to a short message, a deliberate bullet list, or a status update — skip them rather than prosifying the form the user chose. Lexical and tone items still apply.
   - Identify AI patterns (see checklist below)
   - Note structural issues (generic intro/conclusion, listicles, etc.)
   - Find ideas worth keeping

2. **Load voice profile:**

Read `{VAULT}/07 System/Context - Voice & Writing Style.md` — concrete before/after examples, and the source of truth for voice patterns (sentence structure, vocabulary, tone, hedging style, examples, structure).

- **If it exists and is populated:** use it alone. Do NOT trawl secondary sources on a routine run — the profile already distils them.
- **If it's missing or thin:** say so, offer the first-run profile build (see Voice Training Sources below), and rewrite using this file's defaults — or user-supplied samples — in the meantime.
- **Secondary sources are for profile building/refinement only**, not per-run reads: published writing (blog posts, essays), sent messages in the target medium, and the user's Obsidian notes (especially in `07 System/` and `03 Projects/`).

3. **Apply transformations:**

**Remove AI clichés:**
- ❌ "delve", "dive deep", "unpack", "leverage", "robust"
- ❌ "it's worth noting that", "importantly", "essentially"
- ❌ "in today's world", "in this modern age"
- ❌ Unnecessary hedging ("arguably", "somewhat", "relatively")
- ✅ Direct statements with evidence

**Restructure away from AI patterns:**
- ❌ Generic intro: "In a world where..."
- ❌ Numbered listicles without narrative
- ❌ Conclusion that just restates intro
- ✅ Start with the insight or problem
- ✅ Build argument logically
- ✅ End with implication or action

**Adopt the user's patterns** (see voice context file for specifics):
- ✅ Match their sentence structure and vocabulary
- ✅ Match their tone, hedging style, and register
- ✅ Active voice, outcome-focused

**Semantic-preservation gate:** compare before and after for subjects, categories, thresholds, coverage claims, qualifiers, frontmatter, links, and citations. Each element must remain exact unless the user explicitly asked to change it. Compression may shorten delivery; it may not widen, narrow, merge, or drop factual scope.

**How-to straightness:** in a guide or instructional post, every non-procedural sentence must supply a requested premise, a necessary safety constraint, or an execution-relevant explanation. Cut origin story and commentary that do none of those jobs.

4. **Rewrite the text:**

Choose the mode from the user's request:

- **Chat text (default):** present the two versions below. If either contains its own fenced code block, wrap it in a fence at least one backtick longer than the longest fence inside it (four or more backticks) so the nesting survives.
- **Single file in place:** the file's current content is authority. If a last assistant-authored version is available, diff it against the current file first and treat every intervening user edit as protected; never reverse one unless the user explicitly asks, and surface an overlapping proposed reversal before writing. For a vault file, record its current SHA-256, install the complete rewrite with `locked-edit.sh --replace-whole <sha256>`, then re-read the rendered artefact and rerun the semantic-preservation gate. Return a file link and the key changes, not duplicated Original/Rewritten blocks.
- **Explicit batch:** enumerate the exact source files, snapshot their originals outside the published tree, and process the full batch without per-item approval. Preserve frontmatter, links, citations, factual scope, and intervening user edits as above. After all rewrites validate, create one consolidated `De-AI-ification Diffs.md` in the batch's common parent; if that path already exists, ask before replacing it. Return the changed-file list and the comparison link.

Chat-mode format:

**Original:**
````
[Original text]
````

**De-AI-ified (the user's voice):**
````
[Rewritten text]
````

**Key changes:**
- Removed: [List of AI patterns eliminated]
- Added: [user-specific voice elements]
- Restructured: [Structural improvements]

5. **Iterate if needed:**
   - Ask if the voice feels right
   - Adjust based on feedback

6. **Voice refinement prompt:**

   After the user accepts or uses the de-AI-ified text, ask: "If you'd like to refine your voice profile, paste the final version you actually used."

   When the user provides their final text:
   - Diff against the de-AI-ified version. Ignore content-only changes (added links, changed facts, different context). Focus on word choice, tone, structure, and register shifts.
   - For each voice-relevant change, classify:
     - **Voice doc gap:** A pattern not yet captured in the voice profile. Propose adding it.
     - **Voice doc violation:** A pattern the doc already covers but the output didn't follow. Note it as a self-correction (the doc is fine; the de-AI-ifying needs to improve).
   - If there are genuine voice doc gaps: propose specific edits to `{VAULT}/07 System/Context - Voice & Writing Style.md` and apply them on user confirmation.
   - If all changes were content-only or already-covered violations: say so briefly. No voice doc update needed.

## AI Pattern Checklist

**Lexical clichés:**
- [ ] "delve", "dive deep", "unpack"
- [ ] "leverage", "utilize", "facilitate"
- [ ] "robust", "comprehensive", "holistic"
- [ ] "journey", "landscape", "space" (in metaphorical sense)
- [ ] "it's worth noting", "importantly"

**Structural patterns:**
- [ ] Generic introduction ("In today's world...")
- [ ] Numbered list without narrative thread
- [ ] Repetitive transitions ("Moreover,", "Furthermore,", "Additionally,")
- [ ] Conclusion that restates introduction
- [ ] Every paragraph starts with topic sentence
- [ ] Subject-drop (omitting subject pronouns, e.g. "Looked into that" instead of "I looked into that"). Default: keep subject pronouns — English is not a pro-drop language. But this is register-sensitive: where the voice profile or the register in force says otherwise (casual IM, where "Sounds good" is native), don't "correct" it
- [ ] Em-dash overuse (multiple per paragraph, used as an all-purpose connector)
- [ ] "not X, but Y" contrast framing; rule-of-three triads ("fast, simple, and reliable")

**Tone indicators:**
- [ ] Excessive hedging ("somewhat", "relatively", "arguably")
- [ ] Corporate-speak ("synergy", "alignment", "optimize")
- [ ] False excitement ("exciting", "incredible", "amazing")
- [ ] Overly diplomatic (avoiding taking positions)

**The user's voice should be** (defaults — defer to the voice context file where it differs):
- [ ] Direct and outcome-focused
- [ ] Technically precise without dumbing down
- [ ] Uses systems/economic thinking naturally
- [ ] Personal examples when relevant
- [ ] Intellectually honest (acknowledges uncertainty without hedging everything)

## Voice Training Sources

**Primary sources** (the user's authentic writing — use whichever exist in the vault):
1. Published writing (blog posts, essays)
2. Messages the user actually sent in the target medium (email, IM, forum posts)
3. Personal writing in note-app exports (their words, not captures)
4. Obsidian project files and context files (their documentation)

**Not a voice source:** instructions the user wrote to an AI assistant. Prompts are terse, imperative, and speed-optimised — a task register, not a style sample. Mining them corrupts the profile.

**What to extract:**
- Vocabulary preferences (technical terms they use naturally)
- Sentence rhythm (short vs long, declarative vs questioning)
- Structural patterns (how they build arguments)
- Examples they choose (concrete, personal)
- Hedging patterns (when they hedge vs when they're direct)

**On first run**, offer to analyse these sources to build a voice profile. Store the extracted patterns in `{VAULT}/07 System/Context - Voice & Writing Style.md` for reuse.

## Guidelines

- **Preserve ideas, change delivery:** Don't lose good thinking in pursuit of voice
- **Concise over comprehensive:** the user values efficiency - shorter is better if it preserves meaning
- **Technical precision:** Don't simplify technical concepts - use precise vocabulary
- **Personal examples:** When applicable, suggest how the user could add their own experience
- **No superlatives:** Avoid "best", "optimal", "perfect" - be specific instead
- **Outcome-focused:** Frame in terms of results, not process

## Frequency

Use de-AI-ify:
- On AI-generated drafts before publishing (especially blog posts)
- When editing Claude's responses for inclusion in vault
- On text that "feels AI" even if human-written
- As final pass on important communications

## Integration with Other Commands

- **After content generation:** If Claude writes a draft, run de-AI-ify before the user publishes
- **Before blog publishing:** Final voice check on posts
- **With $thinking-partner:** Generate ideas in thinking mode, then de-AI-ify the write-up
- **With $reply:** `$reply` reads this skill and applies it after drafting, with invocation constraints defined in `~/.codex/skills/reply/SKILL.md` step 4 — that file owns the contract (marker preservation, register handling, step 5/6 deferral); follow those constraints rather than this summary. The before/after presentation still applies. `$de-ai-ify` can also be used standalone on any text outside of `$reply`.

This ensures **the user's authentic voice in all published work**.
