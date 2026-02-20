---
name: oops
aliases: [lesson, mistake, catch]
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

2. **If unclear, ask concisely:**
   - "What was the mistake?" (if not obvious from context)
   - "What should have happened instead?" (if correction unclear)

### Phase 2: Structure the Lesson

3. **Extract three components:**
   - **Mistake:** What went wrong (factual, specific, no hedging)
   - **Correction:** What the right approach was
   - **Lesson:** Transferable principle for future sessions (this is the valuable part)

4. **Generate a short title** (3-6 words) that captures the error type, e.g.:
   - "Edited File Without Reading First"
   - "Assumed Config Without Checking"
   - "Missed Existing Helper Function"

### Phase 3: Write to Corrections Log

5. **Resolve paths and date:**
   - VAULT_PATH is available from environment
   - Corrections log: `$VAULT_PATH/07 System/Claude Corrections Log.md`
   - Get date: `date +"%Y-%m-%d"`

6. **Append to the corrections log** using the Edit tool:
   - Read the current end of `$VAULT_PATH/07 System/Claude Corrections Log.md`
   - Use Edit tool to append the new entry after the last line
   - Entry format (substitute actual values):

   ```markdown

   ### YYYY-MM-DD - Short Title Here
   **Mistake:** Actual description of what went wrong.
   **Correction:** What the right approach was.
   **Lesson:** Transferable principle for the future.
   ```

### Phase 4: Consider Promotion

7. **Check if this is a pattern.** Use Grep tool to search for similar mistakes:
   - Search for key nouns from the mistake (e.g., tool names, error types, assumption categories)
   - Search the corrections log file

8. **If pattern detected** (2+ similar mistakes), suggest promotion:
   - **Default target: `07 System/` context files** — specific operational rules belong near the system they govern (e.g., NAS path rules → `Context - Technical Infrastructure.md`)
   - **CLAUDE.md only for truly cross-cutting patterns** — habits-of-mind that apply regardless of which system you're working with
   ```
   This appears to be a recurring pattern. Consider promoting:

   Target: [07 System/Context - X.md] or [CLAUDE.md if cross-cutting]
   [Suggested addition]
   ```

9. **Confirm capture:**
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
**Lesson:** Transferable principle that applies beyond this specific instance.
```

## Guidelines

- **Be specific:** "Assumed X" not "Made an assumption"
- **No hedging:** "Forgot to use tool" not "Perhaps could have used tool"
- **Lessons must generalise.** The lesson is the valuable part — it's what makes future sessions smarter. Apply the "different domain" test: would this lesson help in a completely unrelated situation? If it only makes sense in the original context, it's a restatement of the correction, not a principle. Go one level more abstract than the specific mistake. Example: "don't use booking form estimates for arrival times" → "when a cached approximate value and the raw inputs to compute the exact answer are both available, compute from the inputs." The first is a travel tip; the second is a reasoning principle.
- **Keep it short:** Each field should be 1-2 sentences max. The lesson can be 2-3 sentences if the generalisation needs a concrete anchor.
- **Title is searchable:** Choose words you'd grep for later. Prefer the abstract pattern over the specific instance: "Grabbed Cached Estimate Instead of Computing From Inputs" over "Used Booking Estimate Instead of Train Schedule"

## Setup

This command requires a corrections log file. Create it if it doesn't exist:

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
