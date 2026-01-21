---
name: park
aliases: [shutdown-complete]
description: End session with Cal Newport "shutdown complete" - document work, open loops, enable frictionless pickup
parameters:
  - "--quick" - Minimal parking (one-line log entry, for trivial sessions)
  - "--full" - Comprehensive parking (default for anything worth documenting)
  - "--auto" - Auto-detect tier based on session characteristics (default)
---

# Park - Session Parking

You are ending a work session. Your task is to create a comprehensive session summary that enables confident rest and frictionless pickup.

## Tier Philosophy

**Two tiers only:**
- **Quick** - Genuinely trivial sessions (<5 min, no files touched, just a question answered). One line is enough.
- **Full** - Everything else. If it's worth documenting at all, do it properly. Includes bidirectional links, pickup context, key insights, open loops.

The old "standard" tier was a false economy - saving 30 seconds of processing time but losing context that might be valuable later is bad math.

## Instructions

### Phase 1: Setup and Verification

0. **Verify vault accessibility** before proceeding:
   - Check if the vault directory is accessible (especially if on network mount)
   - If vault is not available, display error and abort:
     ```
     ❌ ERROR: Vault directory not accessible
     Cannot park session - session summary would be lost.

     Troubleshooting:
     - Check if vault path exists
     - Verify network connection (if network mount)
     - Try remounting if applicable

     Session NOT parked. Try again once vault is accessible.
     ```
   - Only proceed if vault is confirmed accessible

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
   - Session number for today (check existing file at `06 Archive/Claude Sessions/YYYY-MM-DD.md` to find last session number, or start at 1)
   - Topic/name for this session (concise, descriptive)
   - Use current time from step 1 (already checked)
   - Related project (if applicable, check both locations):
     - `03 Projects/[Project Name].md` (active projects)
     - `03 Projects/Backlog/[Project Name].md` (backlog projects)
   - **Quick tier:** Skip project detection (just use topic)

6. **Find previous session and check for continuation** (conditional on tier):
   - **Quick tier:** Skip previous session linking (saves read overhead)
   - **Full tier:**
     - Check if this session is continuing a previous one (from `/pickup` context)
     - If continuing: Store continuation link for inclusion in summary
     - Find the most recent session by searching:
       1. Today's file: `06 Archive/Claude Sessions/YYYY-MM-DD.md`
       2. If no sessions today: Check yesterday, then up to 7 days back
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
   - **CRITICAL: Use Bash with flock, NOT the Edit tool** - Edit tool has no locking and causes race conditions
   - Lock file path: `06 Archive/Claude Sessions/.lock`
   - Wait up to 10 seconds for lock acquisition (network mounts can be slow)
   - If file doesn't exist, create it with header first

   **Implementation - use this exact pattern:**
   ```bash
   # First, read current file to determine next session number (do this BEFORE locking)
   # Then write with flock:
   flock -w 10 "06 Archive/Claude Sessions/.lock" -c 'cat >> "06 Archive/Claude Sessions/YYYY-MM-DD.md" << '\''EOF'\''

   ## Session N - [Topic] ([Time]) [Q]

   [Session content here]
   EOF'
   ```

   **If file doesn't exist yet:**
   ```bash
   flock -w 10 "06 Archive/Claude Sessions/.lock" -c 'cat > "06 Archive/Claude Sessions/YYYY-MM-DD.md" << '\''EOF'\''
   # Claude Session - YYYY-MM-DD

   ## Session 1 - [Topic] ([Time])

   [Session content here]
   EOF'
   ```

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

   **GUARD 3 - Scope to previous session only (REQUIRED):**
   The sed pattern MUST be constrained to the previous session's block only. A file contains multiple sessions, each with `**Project:**` lines. Matching globally will insert links into ALL sessions.

   **Implementation - Line-number scoped insertion (Full previous sessions):**
   ```bash
   # 1. Find previous session heading line number (use exact session number and title)
   PREV_HEADING=$(grep -n "^## Session $PREV_NUM - $PREV_TOPIC" "$PREV_FILE" | head -1 | cut -d: -f1)

   # 2. Find next session heading after it (or use EOF)
   NEXT_HEADING=$(tail -n +$((PREV_HEADING + 1)) "$PREV_FILE" | grep -n "^## Session " | head -1 | cut -d: -f1)
   if [ -n "$NEXT_HEADING" ]; then
     END_LINE=$((PREV_HEADING + NEXT_HEADING - 1))
   else
     END_LINE=$(wc -l < "$PREV_FILE")
   fi

   # 3. Find the last Pickup Context metadata line within that range
   # (Project > Continues > Previous session, in order of preference)
   INSERT_AFTER=$(sed -n "${PREV_HEADING},${END_LINE}p" "$PREV_FILE" | \
     grep -n "^\\*\\*\\(Project\\|Continues\\|Previous session\\):\\*\\*" | tail -1 | cut -d: -f1)
   INSERT_LINE=$((PREV_HEADING + INSERT_AFTER - 1))

   # 4. Insert at specific line number (scoped, not pattern-matched)
   flock -w 10 "06 Archive/Claude Sessions/.lock" -c "
     sed -i \"${INSERT_LINE}a\\**Next session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]\" \"$PREV_FILE\"
   "
   ```

   **Implementation for Quick tier previous sessions (no Pickup Context):**
   ```bash
   # Quick sessions are single-line. Find the specific session line and insert after content.
   # Still must scope to the specific session - don't match all [Q] sessions!
   PREV_LINE=$(grep -n "^## Session $PREV_NUM - .*\\[Q\\]$" "$PREV_FILE" | head -1 | cut -d: -f1)
   # Quick sessions may have content on next line, find where to insert
   flock -w 10 "06 Archive/Claude Sessions/.lock" -c "
     # Insert after the quick session's content line (line after heading, or heading if no content)
     sed -i \"$((PREV_LINE + 1))a\\**Next session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]\" \"$PREV_FILE\"
   "
   ```

   **GUARD 4 - Post-insertion validation:**
   After insertion, verify no duplicates were created:
   ```bash
   NEXT_COUNT=$(sed -n "${PREV_HEADING},${END_LINE}p" "$PREV_FILE" | grep -c "^\\*\\*Next session:\\*\\*")
   if [ "$NEXT_COUNT" -gt 1 ]; then
     echo "⚠ WARNING: Previous session has $NEXT_COUNT 'Next session:' links - manual review needed"
   fi
   ```

   **Error handling:** If forward link fails (file missing, lock timeout, sed error):
     - Log warning but don't fail the park
     - Set `forward_link_failed = true` for completion message

   - **If this session also continues a specific previous session** (from `/pickup`):
     - Add "Continued in:" link to the original session as well (if different from immediate previous)
     - Format: `**Continued in:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]] (DD Mon)`
     - Same scoped insertion pattern applies - MUST constrain to specific session block

9. **Update Works in Progress** (conditional on tier):
   - **Quick tier:** Skip WIP update (session too minor to warrant it)
   - **Full tier:** Update WIP for related projects
   - Read `01 Now/Works in Progress.md`
   - Find the relevant project section
   - Update status with:
     - **Last:** [Today's date and time from step 1] - [Brief description of progress]
     - **Next:** [Next action from open loops]
     - Add link to session: `→ [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N]]`
   - Update "Last updated" timestamp at top of file with current date/time

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

Shutdown complete. You can rest.

To pickup: `claude` (will show recent sessions) or `/pickup`
```

**IMPORTANT:** The "Quality check" line is REQUIRED in all completion messages. If you cannot produce this line, you skipped Step 4 - go back and complete it before finishing the park.

## Guidelines

- **Park ALL sessions:** Use `/park` for every session, even quick tasks. The system auto-detects appropriate tier.
- **Two tiers only:** Quick (trivial) vs Full (everything else). If it's worth documenting, do it properly.
- **Quick is rare:** Most sessions are Full. Quick is for 3-minute lookups where you literally just answered a question.
- **Explicit override available:** Use `--quick` or `--full` to override auto-detection
- **Completed work has no open loops:** For finished sessions, write "None - work completed" or list completed checkboxes
- **Always verify vault accessibility:** First step - check directory/mount status before any write operations. If vault is unavailable, abort rather than silently fail
- **Always check current date/time:** Run `date` command to get accurate timestamps with seconds. Never assume or use cached time
- **Timezone handling:** Use system timezone (local time wherever the user is). During travel, sessions dated in local context. This is intentional - local time is more meaningful than forcing a fixed timezone
- **Bidirectional linking:** Full tier adds "Next session:" to the previous session when parking, creating true bidirectional session chains. Additionally, when `/pickup` loads a specific session to continue, "Continues:" appears in new session and "Continued in:" is appended to original - tracking project threads across time
- **Scoped forward linking is critical:** When adding "Next session:" links, ALWAYS scope the insertion to the specific previous session's block. Never use global sed patterns that match all `**Project:**` lines in the file - this causes duplicate insertions across all sessions. Use line-number-based insertion with explicit session heading anchoring.
- **File locking is mandatory:** Use `flock` via Bash tool, NOT the Edit tool. Edit tool has no locking and WILL cause race conditions when multiple Claude instances park simultaneously. Single lock file (`06 Archive/Claude Sessions/.lock`) protects both writes and edits
- **Quality gate is mandatory:** Step 4 MUST produce visible output for ALL tiers. Quick tier shows "Skipped", Full shows results. This prevents silent skipping.
- **Three-part quality check:** Lint (syntax), Refactor (content quality), Proofread (language). All three categories checked for Full tier.
- **Narrative tone:** Write summaries in the user's voice - direct, technical, outcome-focused
- **Open loops clarity:** Each open loop should be specific enough to resume without re-reading the conversation
- **One-sentence pickup:** The "For next session" line should be immediately actionable (or "No follow-up needed" if complete)
- **Project context:** Full tier links projects; Quick tier skips
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
