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

   If error, abort — the usual cause is `VAULT_PATH` unset (a required install precondition; `/setup` documents how to set it per-OS). Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`; if both exist, prefer the copy in the same directory as this command file) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Analyse the text:**
   - Identify AI patterns (see checklist below)
   - Note structural issues (generic intro/conclusion, listicles, etc.)
   - Find ideas worth keeping

2. **Load voice profile:**

Read `{VAULT}/07 System/Context - Voice & Writing Style.md` — concrete before/after examples, and the source of truth for voice patterns (sentence structure, vocabulary, tone, hedging style, examples, structure).

- **If it exists and is populated:** use it alone. Do NOT trawl secondary sources on a routine run — the profile already distils them.
- **If it's missing or thin:** say so, offer the first-run profile build (see Voice Training Sources below), and rewrite using this file's defaults — or user-supplied samples — in the meantime.
- **Secondary sources are for profile building/refinement only**, not per-run reads: archived AI-chat exports (the user's own prompts, not AI responses), published writing (blog posts, essays), and the user's Obsidian notes (especially in `07 System/` and `03 Projects/`).

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

4. **Rewrite the text:**

Present two versions:

**Original:**
```
[Original text]
```

**De-AI-ified (the user's voice):**
```
[Rewritten text]
```

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
2. The user's messages in archived AI-chat exports (their prompts, not AI responses)
3. Personal writing in note-app exports (their words, not captures)
4. Obsidian project files and context files (their documentation)

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
- **With /thinking-partner:** Generate ideas in thinking mode, then de-AI-ify the write-up
- **With /reply:** `/reply` invokes `/de-ai-ify` via the Skill tool after drafting, with invocation constraints defined in `reply.md` step 4 — that file owns the contract (marker preservation, register handling, step 5/6 deferral); follow the constraints as passed at invocation rather than this summary. The before/after presentation still applies. `/de-ai-ify` can also be used standalone on any text outside of `/reply`.

This ensures **the user's authentic voice in all published work**.
