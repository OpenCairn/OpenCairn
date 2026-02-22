---
name: park
aliases: [shutdown-complete]
description: End session with Cal Newport "shutdown complete" - document work, open loops, enable frictionless pickup
parameters:
  - "--quick" - Minimal parking (one-line log entry, for trivial sessions)
  - "--full" - Comprehensive parking (default for anything worth documenting)
  - "--auto" - Auto-detect tier based on session characteristics (default)
  - "--compact" - Run /compact after parking (Full tier only, for heavy context sessions)
---

# Park - Session Parking

You are ending a work session. Your task is to create a comprehensive session summary that enables confident rest and frictionless pickup.

**⚠ One park at a time.** Do not run `/park` in parallel across multiple sessions. The write-session script uses `--create` (truncate) for the first session of the day, which will destroy a parallel session's content. Session numbering also can't be resolved correctly when two sessions race. Park one session, wait for completion, then park the next.

## Tier Philosophy

**Two tiers only:**
- **Quick** - Genuinely trivial sessions (<5 min, no files touched, just a question answered). One line is enough.
- **Full** - Everything else. If it's worth documenting at all, do it properly. Includes bidirectional links, pickup context, key insights, open loops.

The old "standard" tier was a false economy - saving 30 seconds of processing time but losing context that might be valuable later is bad math.

## Instructions

### Phase 1: Setup and Verification

0. **Resolve vault path** before proceeding:
   ```bash
   if [[ -z "${VAULT_PATH:-}" ]]; then
     echo "VAULT_PATH not set. Set it in your shell profile (e.g., export VAULT_PATH=/path/to/vault)"
     exit 1
   elif [[ ! -d "$VAULT_PATH" ]]; then
     echo "VAULT_PATH=$VAULT_PATH does not exist"
     exit 1
   else
     echo "VAULT_PATH=$VAULT_PATH"
   fi
   ```
   If error, abort. **Use `$VAULT_PATH` for all file operations below.**

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"` (for session file naming)
   - Get current time with seconds: `date +"%I:%M:%S%p" | tr '[:upper:]' '[:lower:]'` (for session timestamp)
   - Store these for use in metadata and file paths
   - Note: Including seconds prevents session numbering collisions if multiple sessions park in the same minute

2. **Detect session tier** (unless explicit parameter provided):
   - **Quick tier** triggers when ALL of:
     - Conversation < 10 turns AND
     - No files created/updated AND
     - Session < 5 minutes duration AND
     - No decisions made, just information lookup
   - **Full tier** triggers when ANY of:
     - Files created/updated OR
     - Decisions made OR
     - Open loops generated OR
     - Session involved any substantive work
   - If `--auto` (default): Auto-detect based on above
   - If `--quick` or `--full`: Use explicit tier
   - Display tier selection:
     ```
     Parking tier: [Quick/Full] (auto-detected)
     ```

3. **Read the conversation transcript** to understand what was accomplished, decisions made, and what remains open.

### Phase 2: Quality Assurance

4. **⚠️ QUALITY GATE: Lint, refactor, proofread modified files**

   **This step MUST produce visible output. No silent skipping.**

   | Tier | Action |
   |------|--------|
   | Quick | Display: `⏭ Quality check: Skipped (Quick tier)` and proceed |
   | Full | Check all modified files + vault-wide broken link scan |

   **Four categories of checks (Full tier):**

   **LINT** - Syntax and structure:
   - YAML frontmatter syntax errors
   - Broken file paths or internal links
   - Markdown syntax issues (unclosed code blocks, malformed lists)
   - Broken Obsidian wikilinks

   **REFACTOR** - Content quality:
   - Consolidate redundant content (did I repeat myself across files?)
   - Update stale references (outdated info, old dates, deprecated approaches)
   - Fix broken structure (illogical heading hierarchy, orphaned sections)
   - Remove dead/orphaned content created then abandoned

   **VERIFY** - Session summary accuracy (if updating an already-parked session):
   - Do open loops still reflect reality? (If user completed something mid-conversation, tick it off)
   - Does pickup context still match? (If "ready for upload" is now uploaded, update the line)
   - Were any "Next Steps" completed during the session that need marking done?

   **PROOFREAD** - Language and consistency:
   - American → Australian/British English (organise, categorise, prioritise, realise, analyse, summarise, colour, favour)
   - Terminology consistency (park/pickup not parking/resume/restore)
   - Typos, grammar, unclear phrasing
   - Tone consistency with the user's voice

   **Fix any issues found automatically.**

   **REQUIRED OUTPUT (exactly one of these MUST appear):**

   ```
   ⏭ Quality check: Skipped (Quick tier)
   ```

   ```
   ✓ Quality check: N files checked, no issues found
   ```

   ```
   🔧 Quality check: Fixed N issues
   - [specific fix 1]
   - [specific fix 2]
   ```

   **⛔ CHECKPOINT:** You cannot proceed to Step 5 until one of the above outputs appears in your response. If you find yourself writing session metadata without having displayed a quality check result, STOP and return to this step.

### Phase 3: Document and Archive

5. **Determine session metadata:**
   - Session number for today (check existing file at `$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md` to find last session number, or start at 1)
   - Topic/name for this session (concise, descriptive)
   - Use current time from step 1 (already checked)
   - Related project (if applicable):
     - **Finite work** → `$VAULT_PATH/03 Projects/[Project Name].md` (or `Backlog/`)
     - **Ongoing area work** → `$VAULT_PATH/04 Areas/[path]/[name].md`
     - **Never link to:** WIP sections, Resources, or Archive (see Guidelines for rationale)
   - **Quick tier:** Skip project detection (just use topic)

6. **Find previous session and check for continuation** (conditional on tier):
   - **Quick tier:** Skip previous session linking (saves read overhead)
   - **Full tier:**
     - Check if this session is continuing a previous one (from `/pickup` context)
     - If continuing: Store continuation link for inclusion in summary
     - Find the most recent session by searching:
       1. Today's file: `$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md`
       2. If no sessions today: Check yesterday, then up to 10 days back
       3. Also check year subdirectories: `Claude Sessions/YYYY/*.md` (for cross-year boundaries)
     - Extract title and file path for backlink and forward linking
     - Store previous session's tier (Quick vs Full) for step 8a

7. **Generate session summary** (format varies by tier):

**Quick Tier Format:**
```markdown
## Session N - [Topic/Name] ([Time]) [Q]

[One-line summary of what was done]
```

**Full Tier Format:**
```markdown
## Session N - [Topic/Name] ([Time with seconds - HH:MM:SSam/pm])

### Summary
[2-4 sentence narrative of what was accomplished. Focus on outcomes and decisions.]

### Key Insights / Decisions
[Bullet list of important realisations, architectural choices, or decisions made]

### Next Steps / Open Loops
- [ ] Specific actionable item with clear next action
- [ ] Another open loop that needs attention
[Each item should be actionable and specific enough to resume without re-reading entire conversation]

### Files Created
- path/to/file.md - [purpose/description]

### Files Updated
- path/to/file.md - [what changed and why]

### Pickup Context
**For next session:** [One clear sentence about where to pick up - the very next action to take]
**Previous session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N-1 - Topic]]
**Continues:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session X - Topic]] (if this session continues previous work)
**Project:** [[03 Projects/Project Name]] (if applicable)
```

8. **Write the summary** (with file locking for concurrent safety):
   - **CRITICAL: Use the write-session script, NOT inline flock or the Edit tool**
   - Inline flock commands corrupt `settings.local.json` (the entire command including session content gets saved as a permission pattern)
   - The script handles locking, file creation, and atomic writes

   **✓ USE THE WRITE-SESSION SCRIPT:**

   Use the dedicated script instead of inline bash (prevents permission system corruption):

   **Appending to existing file:**
   ```bash
   cat << 'EOF' | "$VAULT_PATH/.claude/scripts/write-session.sh" "$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md"
   ## Session N - [Topic] ([Time])

   [Session content here]
   EOF
   ```

   **Creating new file (first session of the day):**
   ```bash
   cat << 'EOF' | "$VAULT_PATH/.claude/scripts/write-session.sh" "$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md" --create
   ## Session 1 - [Topic] ([Time])

   [Session content here]
   EOF
   ```

   The script handles:
   - File locking (flock) for concurrent safety
   - Lock timeout (10 seconds for NAS)
   - Date header generation (--create mode)
   - Directory creation if needed

   **If lock times out (exit code 1):** Display warning and retry once, then fail gracefully:
   ```
   ⚠ Lock acquisition timed out - another session may be parking. Retrying...
   ```

8a. **Add forward link to previous session** (full tier only):
   - **Quick tier:** Skip (no previous session linking done)
   - **Full tier:**
     - If no previous session found in step 6, skip forward linking (first session ever)
     - **CRITICAL: Use Bash with flock for editing previous session file**

   **GUARD 1 - Self-reference check (REQUIRED):**
   Before any forward linking, verify we're not linking a session to itself:
   - If previous session heading == current session heading, skip with warning:
     `⚠ Detected self-reference attempt, skipping forward link`
   - This can occur when context compaction causes session number confusion

   **GUARD 2 - Idempotency check (REQUIRED):**
   Before inserting, check if a "Next session:" link already exists in the previous session's Pickup Context:
   ```bash
   # Check if forward link to this specific session already exists
   if grep -q "\\*\\*Next session:\\*\\*.*#Session $CURRENT_NUM - " "$PREV_FILE"; then
     echo "Forward link already exists, skipping"
     # Skip insertion entirely - do NOT proceed to sed
   fi
   ```

   **✓ USE THE FORWARD-LINK SCRIPT:**

   Use the dedicated script instead of inline bash (prevents permission system corruption):
   ```bash
   # Same-day link:
   "$VAULT_PATH/.claude/scripts/add-forward-link.sh" "<session-file>" <prev-num> <new-num> "<new-topic>"
   # Cross-day link (previous session on different day than new session):
   "$VAULT_PATH/.claude/scripts/add-forward-link.sh" "<session-file>" <prev-num> <new-num> "<new-topic>" "<target-date>.md"
   ```

   **Examples:**
   ```bash
   # Same-day: Session 39 → Session 40, both on Jan 26
   "$VAULT_PATH/.claude/scripts/add-forward-link.sh" \
     "$VAULT_PATH/06 Archive/Claude Sessions/2026-01-26.md" \
     39 40 "Sarath Task Capture"

   # Cross-day: Session 29 on Feb 11 → Session 1 on Feb 12
   "$VAULT_PATH/.claude/scripts/add-forward-link.sh" \
     "$VAULT_PATH/06 Archive/Claude Sessions/2026-02-11.md" \
     29 1 "Morning Check-in" "2026-02-12.md"
   ```

   **IMPORTANT:** When the new session is on a different day than the previous session,
   you MUST pass the 5th argument (target date file). Without it, the link points to
   the wrong day's file.

   The script handles:
   - File locking (flock) for concurrent safety
   - Idempotency (skips if link already exists)
   - Quick vs Full session detection
   - Correct insertion point finding
   - Cross-day links via optional 5th argument
   - All guards and validation

   **Error handling:** If script fails (file missing, lock timeout, session not found):
     - Log warning but don't fail the park
     - Set `forward_link_failed = true` for completion message

   - **If this session also continues a specific previous session** (from `/pickup`):
     - Add "Continued in:" link to the original session as well (if different from immediate previous)
     - Format: `**Continued in:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]] (DD Mon)`
     - Use the same script with appropriate arguments

8b. **Check for stranded work product in Claude-internal files** (Full tier only):
   - **Quick tier:** Skip
   - **Full tier:** Check whether any Claude-internal files were created or modified during this session:
     ```bash
     # Check for plan files modified today
     find ~/.claude/plans/ -type f -newermt "$(date +%Y-%m-%d)" 2>/dev/null
     ```
   - If any files found, check whether their content has been migrated to the vault:
     - Read the plan file(s)
     - Compare against the relevant vault project doc
     - If the vault doc is stale or missing the plan content: **migrate it now** (update the vault file with the plan content before completing the park)
   - Display result:
     ```
     ✓ No stranded work product in ~/.claude/plans/
     ```
     or:
     ```
     🔧 Migrated plan content to vault: [vault file path]
     ```
   - **Why this exists:** Work product written to `~/.claude/plans/` has been stranded there multiple times. These files don't sync, aren't visible in Obsidian, and effectively don't exist outside the session.

9. **Update Works in Progress** (conditional on tier):
   - **Quick tier:** Skip WIP update (session too minor to warrant it)
   - **Full tier:** Update WIP for related projects
   - Read `$VAULT_PATH/01 Now/Works in Progress.md`
   - Find the relevant project section
   - Update status with:
     - **Last:** [Today's date and time from step 1] - [Brief description of progress]
     - **Next:** [Next action from open loops]
     - Add link to session: `→ [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N]]`
   - Update "Last updated" timestamp at top of file with current date/time

9a. **Offer Tickler for date-deferred loops** (Full tier only):
   - Scan open loops for explicit future dates. Common patterns:
     - "week of [date]" → use that date (if it's a Monday) or the Monday of that week
     - "after [date]" / "from [date]" → use that date
     - "[month] [day]" or "[day] [month]" → parse to YYYY-MM-DD
     - "next week" → use next Monday
     - "next month" → use 1st of next month
   - If any loops have future dates:
     - List them with parsed dates
     - Ask: "Add these to Tickler for auto-resurface?"
     - If yes: Use the write-tickler script for each item:
       ```bash
       "$VAULT_PATH/.claude/scripts/write-tickler.sh" "$VAULT_PATH/01 Now/Tickler.md" "YYYY-MM-DD" "- [ ] [Loop text] → [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]"
       ```
       The script handles: file creation, date header creation/ordering, flock-based locking
     - If no: Skip (items remain in session only)
   - **Don't prompt if:** No date-tagged loops found, or Quick tier

10. **Display completion message** (tier-appropriate):

**Quick tier:**
```
⏭ Quality check: Skipped (Quick tier)
✓ Session logged: 06 Archive/Claude Sessions/YYYY-MM-DD.md

Quick park complete. Minimal overhead for trivial task.
```

**Full tier:**
```
✓ Quality check: N files, M issues fixed [OR "no issues"]
✓ Session summary saved to: 06 Archive/Claude Sessions/YYYY-MM-DD.md
✓ Open loops documented: N items
✓ Bidirectional links added (previous ↔ next)
  [OR if forward_link_failed: "⚠ Forward link to previous session failed (session still saved)"]
  [OR if no previous session: "✓ No previous session to link (first session)"]
✓ Project updated: [Project Name] (if applicable)
✓ Tickler: N items added for [dates] (if any date-deferred loops were added)
  [OR omit this line if no tickler items added]

**Closing:** "Parked. Pick up when ready."

To pickup: `claude` (will show recent sessions) or `/pickup`
```

**IMPORTANT:** The "Quality check" line is REQUIRED in all completion messages. If you cannot produce this line, you skipped Step 4 - go back and complete it before finishing the park.

12. **Handle --compact flag** (if specified):
   - Only applies to Full tier (Quick sessions don't need compacting)
   - After displaying completion message, run the built-in `/compact` command
   - The park completion message becomes part of the compact summary, providing continuity
   - User can then continue typing in the compacted conversation

## Guidelines

- **Park ALL sessions:** Use `/park` for every session, even quick tasks. The system auto-detects appropriate tier.
- **Two tiers only:** Quick (trivial) vs Full (everything else). If it's worth documenting, do it properly.
- **Quick is rare:** Most sessions are Full. Quick is for 3-minute lookups where you literally just answered a question.
- **Explicit override available:** Use `--quick` or `--full` to override auto-detection
- **Completed work has no open loops:** For finished sessions, write "None - work completed" or list completed checkboxes
- **Always resolve vault path first:** Step 0 determines whether to use NAS mount or local fallback. If neither is accessible, abort rather than silently fail
- **Always check current date/time:** Run `date` command to get accurate timestamps with seconds. Never assume or use cached time
- **Timezone handling:** Use system timezone (local time wherever the user is). During travel, sessions dated in local context (Tokyo → JST, Denver → MST). This is intentional - local time is more meaningful than forcing Australian time
- **Bidirectional linking:** Full tier adds "Next session:" to the previous session when parking, creating true bidirectional session chains. Additionally, when `/pickup` loads a specific session to continue, "Continues:" appears in new session and "Continued in:" is appended to original - tracking project threads across time
- **Scoped forward linking is critical:** When adding "Next session:" links, ALWAYS scope the insertion to the specific previous session's block. Never use global sed patterns that match all `**Project:**` lines in the file - this causes duplicate insertions across all sessions. Use line-number-based insertion with explicit session heading anchoring. **The shortcut sed pattern is ALWAYS wrong** - if you find yourself writing `sed '/pattern/a ...'` without line number constraints, stop and use the documented flock+line-number approach instead.
- **File locking is mandatory:** Use `flock` via Bash tool, NOT the Edit tool. Edit tool has no locking and WILL cause race conditions when multiple Claude instances park simultaneously. Single lock file (`$VAULT_PATH/06 Archive/Claude Sessions/.lock`) protects both writes and edits
- **Quality gate is mandatory:** Step 4 MUST produce visible output for ALL tiers. Quick tier shows "Skipped", Full shows results. This prevents silent skipping.
- **Three-part quality check:** Lint (syntax), Refactor (content quality), Proofread (language). All three categories checked for Full tier.
- **Compact integration:** Use `--compact` when context is heavy and you want to continue working. Parks the session, then compacts. The park summary in the compacted conversation provides continuity without needing /pickup.
- **Narrative tone:** Write summaries in the user's voice - direct, technical, outcome-focused
- **Open loops clarity:** Each open loop should be specific enough to resume without re-reading the conversation
- **Tickler integration:** When open loops have explicit future dates ("week of Feb 9", "after travel"), offer to add them to `01 Now/Tickler.md`. This ensures date-deferred work resurfaces automatically via /morning and /pickup. Don't add everything — only loops with clear "not now, but on X date" intent.
- **One-sentence pickup:** The "For next session" line should be immediately actionable (or "No follow-up needed" if complete)
- **Project context:** Full tier links projects; Quick tier skips
- **Project linking rules:**
  - **Finite work** → link to `03 Projects/[name].md`
  - **Ongoing area work** → link to `04 Areas/[path]/[name].md`
  - **Never link to:** WIP sections (`01 Now/Works in Progress#...`), Resources, or Archive
  - **No canonical home?** Create a project or area file rather than linking to WIP
  - **Working in Resources?** That's a signal it should graduate to an Area
  - **Why:** WIP is for status tracking, not session clustering. Consistent project links enable reliable pickup grouping.
- **File lists:** Only list files that were actually created/updated, not files that were just read
- **Session naming:** Use descriptive names that will make sense weeks later ("Wezterm config fix" not "Terminal stuff")

## Cue Word Detection

This command should also trigger automatically when the user uses these phrases:
- "bedtime"
- "wrapping up"
- "done for tonight"
- "packing up"
- "shutdown complete"
- "park"

When triggered by cue words, acknowledge and proceed with session summary generation.

## Cal Newport Philosophy

The goal is Cal Newport's "shutdown complete" ritual - explicit acknowledgement of open loops so the mind can truly rest. Every incomplete task is captured in a trusted system, eliminating mental residue.

**For completed work:** Park it anyway. The psychological closure ("this is done, documented, and archived") is valuable. Plus six months later you'll want to know "when did I make that decision?" The session archive answers that.
