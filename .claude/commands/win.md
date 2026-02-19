---
name: win
aliases: [nice, nailed-it, worked]
description: Capture what went well and why - build a library of effective patterns
---

# Win - Pattern Capture

You are capturing something that just went well so the pattern isn't lost. This implements the principle: **do more of what works.**

## Philosophy

The counterpart to `/oops`. Mistakes are captured to avoid repetition; wins are captured to enable repetition. Most people only log failures — but knowing *why* something worked is equally valuable for systematic improvement.

The goal isn't celebration — it's pattern extraction. What specifically worked, why, and how to reproduce it.

## Instructions

### Phase 1: Understand What Happened

1. **Scan recent conversation** for what went well. Look for:
   - User praise or satisfaction ("nice", "perfect", "that's exactly right")
   - Approaches that worked on the first try
   - Elegant solutions to complex problems
   - Effective communication or framing
   - Good decisions validated by outcomes
   - Efficient workflows or shortcuts discovered

2. **If unclear, ask concisely:**
   - "What was the win?" (if not obvious from context)
   - "What made this work?" (if the mechanism isn't clear)

### Phase 2: Structure the Pattern

3. **Extract three components:**
   - **Win:** What happened (factual, specific)
   - **Why it worked:** The mechanism or principle behind the success
   - **Pattern:** Transferable approach for future sessions (this is the valuable part)

4. **Generate a short title** (3-6 words) that captures the pattern, e.g.:
   - "SSOT Eliminated Logic Drift"
   - "Pre-Verification Prevented Stale Data"
   - "Scoped Insertion Avoided Duplicates"

### Phase 3: Write to Wins Log

5. **Resolve paths and date:**
   - VAULT_PATH is available from environment
   - Wins log: `$VAULT_PATH/07 System/Claude Wins Log.md`
   - Get date: `date +"%Y-%m-%d"`

6. **Append to the wins log** using the Edit tool:
   - Read the current end of `$VAULT_PATH/07 System/Claude Wins Log.md`
   - Use Edit tool to append the new entry after the last line
   - Entry format (substitute actual values):

   ```markdown

   ### YYYY-MM-DD - Short Title Here
   **Win:** What happened and what the outcome was.
   **Why it worked:** The mechanism or principle that made it succeed.
   **Pattern:** Transferable approach to apply in similar future situations.
   ```

### Phase 4: Consider Promotion

7. **Check if this is a recurring pattern.** Use Grep tool to search for similar wins:
   - Search for key nouns from the win (e.g., tool names, approaches, design patterns)
   - Search the wins log file

8. **If pattern detected** (2+ similar wins), suggest promotion:
   - **Default target: `07 System/` context files** — specific operational patterns belong near the system they govern
   - **CLAUDE.md only for truly cross-cutting patterns** — approaches that apply regardless of domain
   ```
   This pattern keeps working. Consider promoting to standard practice:

   Target: [07 System/Context - X.md] or [CLAUDE.md if cross-cutting]
   [Suggested addition]
   ```

9. **Confirm capture:**
   ```
   Logged: [Short Title]
   Pattern: [One-line pattern]
   ```

## Output Format

The wins log entry follows this exact structure:

```markdown
### YYYY-MM-DD - Short Descriptive Title
**Win:** Specific description of what went well. Factual, not inflated.
**Why it worked:** The mechanism or principle behind the success.
**Pattern:** Transferable approach that applies beyond this specific instance.
```

## Guidelines

- **Be specific:** "Used SSOT to prevent drift across 4 files" not "Good architecture"
- **No inflation:** "Saved 20 minutes" not "Revolutionary breakthrough"
- **Transferable patterns:** The pattern should help in future similar situations, not just this exact case
- **Keep it short:** Each field should be 1-2 sentences max
- **Title is searchable:** Choose words you'd grep for later
- **Both human and Claude wins:** Log effective approaches from either party — the goal is building a shared playbook

## Setup

This command requires a wins log file. Create it if it doesn't exist:

```markdown
# Claude Wins Log

When something works well, say "win" or "nice one, log that." Periodically review and promote recurring patterns to context files or CLAUDE.md.

---

## Log

```

## Triggers

This command should trigger when the user says:
- "win"
- "nice, log that"
- "that worked well"
- "capture this pattern"
- "log this win"
- "nailed it"
