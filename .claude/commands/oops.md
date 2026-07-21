---
name: oops
description: Capture a mistake and its lesson - "only get something wrong once"
---

# Oops - Mistake Capture

You are capturing a mistake that just happened so the lesson isn't lost. This implements the principle: **only get something wrong once.**

## Philosophy

Mistakes are valuable if captured, worthless if repeated. The friction of logging must be near-zero or it won't happen. This command makes capture effortless - you identify the mistake, Claude structures the lesson.

The goal isn't blame or shame - it's systematic improvement. Every logged mistake makes future sessions smarter.

## Instructions

### Phase 1: Understand What Happened

1. **Scan recent conversation** for what went wrong. Look for:
   - User corrections ("no, that's wrong", "actually...", "you should have...")
   - Failed approaches that needed revision
   - Wasted effort or context
   - Assumptions that proved incorrect

   **If several mistakes surfaced, write one entry per *failure mode*, not per symptom.** Errors sharing a root cause — the same bad assumption expressed twice, or one mistake cascading into another — belong in a single entry, because the lesson is one lesson and splitting it produces two half-lessons that each look minor. Errors with independent causes need separate entries, because a merged lesson generalises to neither. **Test:** would one fix have prevented both? Same entry. Otherwise, separate. Run this test explicitly when a session produced more than one correction; the default of logging whatever was most recently discussed silently drops the rest.

   **⛔ Display the test's result before writing any entry** — one line per merge, per split, and per correction you decided not to log at all:

   ```
   Failure-mode test: N corrections surfaced → M entries
   - "[correction A]" + "[correction B]" → merged: [shared root cause]
   - "[correction C]" → separate: [independent cause]
   - "[correction D]" → not logged: [why]
   ```

   Without this, the skill can log a defensible-looking set of entries while quietly dropping the corrections that didn't make the cut — which is the exact failure the paragraph above warns about, arriving through the skill rather than around it. The count `N` is the observable: it must come from a scan of the session, not from the entries you have already decided to write.

2. **If unclear, ask concisely:**
   - "What was the mistake?" (if not obvious from context)
   - "What should have happened instead?" (if correction unclear)

### Phase 2: Check for Rule Collision

3. **Before writing the lesson, check whether an existing rule should have prevented this mistake.** Search CLAUDE.md, auto-memory files (`MEMORY.md` and its topic files, if present), and any loaded context files for rules that cover this situation.

   **If a matching rule exists**, the lesson isn't "follow the rule" — the rule already failed to fire. Diagnose why:
   - **Was the rule in context?** (Was CLAUDE.md or the relevant context file loaded when the mistake happened?)
   - **Was the context window too large?** (Rule present but buried/forgotten due to conversation length?)
   - **Is the rule coherent?** (Is it clear enough to follow, or ambiguous in this situation?)
   - **Does the rule need a better trigger?** (Rule is correct but doesn't activate in this scenario — needs a more specific cue?)

   The correction entry must address the diagnosis, not just restate the existing rule. Either:
   - **Refine the existing rule** with a more specific trigger or mechanism
   - **Add a new rule** that covers the gap the existing rule missed
   - **Note that the rule was absent from context** (if that's the diagnosis — the fix is ensuring it loads, not writing a duplicate rule)

   These are **proposals** — do not edit CLAUDE.md or context files without the user's explicit approval. The log entry records what was proposed (or, if approved this session, what was changed).

   Display:
   ```
   ⚠ Rule collision: [existing rule summary]
   Diagnosis: [why it didn't fire]
   Proposed fix: [refine trigger / add new rule / ensure context loading]
   ```

   **If no matching rule exists**, proceed normally — this is a genuinely new lesson.

### Phase 3: Structure the Lesson

4. **Extract three components:**
   - **Mistake:** What went wrong (factual, specific, no hedging)
   - **Correction:** What the right approach was
   - **Lesson:** Transferable principle for future sessions (this is the valuable part)

5. **Generate a short title** (3-6 words) that captures the error type, e.g.:
   - "Edited File Without Reading First"
   - "Assumed Config Without Checking"
   - "Missed Existing Helper Function"

### Phase 4: Write to Corrections Log

6. **Resolve paths and date:**
   - Run `"$VAULT_PATH/.claude/scripts/resolve-vault.sh"` — if it errors, abort (no vault accessible; don't fall back to a guessed path). Substitute the resolved path wherever `{VAULT}` appears below
   - Corrections log: `{VAULT}/07 System/Claude Corrections Log.md`
   - Get date: `date +"%Y-%m-%d"`

7. **Append to the corrections log** using the Edit tool:
   - **First run:** if `{VAULT}/07 System/Claude Corrections Log.md` doesn't exist, create it from the template in **Setup** below, then continue
   - Read the current end of `{VAULT}/07 System/Claude Corrections Log.md`
   - Use Edit tool to append the new entry after the last line
   - Entry format (substitute actual values):

   ```markdown

   ### YYYY-MM-DD - Short Title Here
   **Mistake:** Actual description of what went wrong.
   **Correction:** What the right approach was.
   **Rule collision:** [Only if Phase 2 detected one] Existing rule, why it didn't fire, the proposed fix (or the change made, if the user approved one).
   **Lesson:** Transferable principle for the future.
   ```

### Phase 5: Consider Promotion

8. **Check if this is a pattern.** Use Grep tool to search for similar mistakes:
   - Search for key nouns from the mistake (e.g., tool names, error types, assumption categories)
   - Search the corrections log file

9. **If pattern detected** (2+ similar mistakes — count distinct `### ` entry headings whose entries match, not raw grep hits: the just-added entry plus at least one distinct prior entry), suggest promotion. If Phase 2 identified a rule collision, specify whether to refine the existing rule's trigger or add a new rule — these are different actions.
   - **Default target: `07 System/` context files** — specific operational rules belong near the system they govern (e.g., NAS path rules → `Context - Technical Infrastructure.md`)
   - **CLAUDE.md only for truly cross-cutting patterns** — habits-of-mind that apply regardless of which system you're working with
   ```
   This appears to be a recurring pattern. Consider promoting:

   Target: [07 System/Context - X.md] or [CLAUDE.md if cross-cutting]
   [Suggested addition]
   ```

10. **Confirm capture:**
   ```
   Logged: [Short Title]
   Lesson: [One-line lesson]
   ```

## Output Format

The corrections log entry follows this exact structure:

```markdown
### YYYY-MM-DD - Short Descriptive Title
**Mistake:** Specific description of what went wrong. No hedging or softening.
**Correction:** What the right approach was. What actually fixed it.
**Rule collision:** [Only if Phase 2 detected one] Existing rule, why it didn't fire, and the proposed fix (trigger refinement / new rule / context loading) — or the change made, if the user approved one.
**Lesson:** Transferable principle that applies beyond this specific instance.
```

## Guidelines

- **Be specific:** "Assumed X" not "Made an assumption"
- **No hedging:** "Forgot to use tool" not "Perhaps could have used tool"
- **Transferable lessons:** The lesson should help in future similar situations, not just this exact case
- **Keep it short:** Each field should be 1-2 sentences max
- **Title is searchable:** Choose words you'd grep for later

## Setup

This command requires a corrections log file. Phase 4 step 7 creates it on first run from this template:

```markdown
# Claude Corrections Log

When Claude makes a mistake I correct, I say "oops" or "log this mistake." Periodically review and promote important lessons to CLAUDE.md.

---

## Log

```

## Triggers

This command should trigger when the user says:
- "oops"
- "log this mistake"
- "add to corrections"
- "lesson learned"
- "don't do that again"
- "capture this lesson"

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and propose specific edits to this skill at the end.
