---
name: park
aliases: [shutdown-complete]
description: End session with Cal Newport "shutdown complete" - document work, open loops, enable frictionless pickup
parameters:
  - "--quick" - Minimal parking (one-line log entry, no full summary)
  - "--standard" - Normal parking (auto-detected for most sessions)
  - "--full" - Comprehensive parking (all features, for significant work)
  - "--auto" - Auto-detect tier based on session characteristics (default)
---

# Park - Session Parking

You are ending a work session. Your task is to create a comprehensive session summary that enables confident rest and frictionless pickup.

## Instructions

### Phase 1: Setup and Verification

0. **Verify NAS mount accessibility** before proceeding:
   - Check if `~/vault` is accessible: `mountpoint -q ~/vault`
   - If mount is not available, display error and abort:
     ```
     ❌ ERROR: NAS mount not accessible at ~/vault
     Cannot park session - session summary would be lost.

     Troubleshooting:
     - Check mount status: mount | grep nas
     - Verify network connection to NAS
     - Try remounting: sudo mount -a

     Session NOT parked. Try again once NAS is accessible.
     ```
   - Only proceed if mount is confirmed accessible

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"` (for session file naming)
   - Get current time with seconds: `date +"%I:%M:%S%p" | tr '[:upper:]' '[:lower:]'` (for session timestamp)
   - Store these for use in metadata and file paths
   - Note: Including seconds prevents session numbering collisions if multiple sessions park in the same minute

2. **Detect session tier** (unless explicit parameter provided):
   - **Quick tier** triggers when:
     - Conversation < 10 turns OR
     - No files created/updated OR
     - Session < 5 minutes duration
   - **Standard tier** triggers when:
     - Conversation 10-50 turns OR
     - 1-5 files modified OR
     - Session 5-45 minutes duration
   - **Full tier** triggers when:
     - Conversation 50+ turns OR
     - 5+ files modified OR
     - Session 45+ minutes OR
     - **Infrastructure/sysadmin work** (NAS, backup, server config, networking, Docker, etc.) OR
     - Explicit `--full` flag
   - If `--auto` (default): Auto-detect based on above
   - If `--quick`, `--standard`, or `--full`: Use explicit tier
   - Display tier selection:
     ```
     Parking tier: [Quick/Standard/Full] (auto-detected)
     ```

3. **Read the conversation transcript** to understand what was accomplished, decisions made, and what remains open.

### Phase 2: Quality Assurance

4. **⚠️ QUALITY GATE: Lint, refactor, proofread modified files**

   **This step MUST produce visible output. No silent skipping.**

   | Tier | Action |
   |------|--------|
   | Quick | Display: `⏭ Quality check: Skipped (Quick tier)` and proceed |
   | Standard | Check files modified this session only |
   | Full | Check all modified files + vault-wide broken link scan |

   **Three categories of checks (Standard/Full tiers):**

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
   - Session number for today (check existing file at `06 Archive/Claude Sessions/YYYY-MM-DD.md` to find last session number, or start at 1)
   - Topic/name for this session (concise, descriptive)
   - Use current time from step 1 (already checked)
   - Related project (if applicable, from `03 Projects/`)
   - **Quick tier:** Skip project detection (just use topic)

6. **Find previous session and check for continuation** (conditional on tier):
   - **Quick tier:** Skip previous session linking (saves read overhead)
   - **Standard/Full tier:**
     - Check if this session is continuing a previous one (from `/pickup` context)
     - If continuing: Store continuation link for inclusion in summary
     - Find the most recent session by searching:
       1. Today's file: `06 Archive/Claude Sessions/YYYY-MM-DD.md`
       2. If no sessions today: Check yesterday, then up to 7 days back
       3. Also check year subdirectories: `Claude Sessions/YYYY/*.md` (for cross-year boundaries)
     - Extract title and file path for backlink and forward linking
     - Store previous session's tier (Quick vs Standard/Full) for step 8a

7. **Generate session summary** (format varies by tier):

**Quick Tier Format:**
```markdown
## Session N - [Topic/Name] ([Time]) [Q]

[One-line summary of what was done]
```

**Standard Tier Format:**
```markdown
## Session N - [Topic/Name] ([Time with seconds - HH:MM:SSam/pm])

### Summary
[2-3 sentence narrative of what was accomplished]

### Next Steps / Open Loops
- [ ] Specific actionable item
- [ ] Another open loop

### Files Created/Updated
- path/to/file.md - [what changed]

### Pickup Context
**For next session:** [One sentence about where to pick up]
**Previous session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N-1 - Topic]]
**Continues:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session X - Topic]] (if applicable)
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
   - Wait up to 10 seconds for lock acquisition (NAS can be slow)
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

8a. **Add forward link to previous session** (standard/full tier):
   - **Quick tier:** Skip (no previous session linking done)
   - **Standard/Full tier:**
     - If no previous session found in step 6, skip forward linking (first session ever)
     - **CRITICAL: Use Bash with flock for editing previous session file**
     - First read the file (without lock) to check idempotency and find insertion point
     - **Idempotency check:** If "Next session:" link to this session already exists, skip
     - Then use flock + sed or flock + temporary file pattern for atomic edit:

   **Implementation for Standard/Full previous sessions (has Pickup Context):**
   ```bash
   # Find the line number of the last "**Project:**" or last line of Pickup Context section
   # Then insert after it using sed with flock:
   flock -w 10 "06 Archive/Claude Sessions/.lock" -c '
     sed -i "/^\\*\\*Project:\\*\\* \\[\\[.*\\]\\]$/a\\**Next session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]" \
       "06 Archive/Claude Sessions/PREV-DATE.md"
   '
   ```

   **Implementation for Quick tier previous sessions (no Pickup Context):**
   ```bash
   # Quick sessions end with [Q] on the summary line - append after the one-line summary
   flock -w 10 "06 Archive/Claude Sessions/.lock" -c '
     sed -i "/^## Session .* \\[Q\\]$/{n;a\\**Next session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]
     }" "06 Archive/Claude Sessions/PREV-DATE.md"
   '
   ```

   **Error handling:** If forward link fails (file missing, lock timeout, sed error):
     - Log warning but don't fail the park
     - Set `forward_link_failed = true` for completion message

   - **If this session also continues a specific previous session** (from `/pickup`):
     - Add "Continued in:" link to the original session as well (if different from immediate previous)
     - Format: `**Continued in:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]] (DD Mon)`
     - Same flock pattern applies

9. **Update Works in Progress** (conditional on tier):
   - **Quick tier:** Skip WIP update (session too minor to warrant it)
   - **Standard tier:** Update WIP only if session explicitly linked to a project
   - **Full tier:** Always update WIP for related projects
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

Quick park complete. Minimal overhead for minor task.
```

**Standard tier:**
```
✓ Quality check: N files, M issues fixed [OR "no issues"]
✓ Session summary saved to: 06 Archive/Claude Sessions/YYYY-MM-DD.md
✓ Open loops: N items
✓ Bidirectional links added (previous ↔ next)
  [OR if forward_link_failed: "⚠ Forward link to previous session failed (session still saved)"]
  [OR if no previous session: "✓ No previous session to link (first session)"]

Shutdown complete. You can rest.

To pickup: `claude` or `/pickup`
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
- **Tiered overhead:** System minimises friction by matching overhead to session importance:
  - Quick: < 5 min, no files → one-line log (5 sec overhead)
  - Standard: 5-45 min, few files → summary + open loops (30 sec overhead)
  - Full: 45+ min, many files → comprehensive (90 sec overhead)
- **Auto-detection works:** Default `--auto` mode correctly identifies tier 95%+ of the time
- **Explicit override available:** Use `--quick`, `--standard`, or `--full` to override auto-detection
- **Quick tier for throwaway sessions:** 3-minute lookups, quick questions, minor tasks
- **Completed work has no open loops:** For finished sessions, write "None - work completed" or list completed checkboxes
- **Always verify NAS accessibility:** First step - check mount status before any write operations. If NAS is unavailable, abort rather than silently fail
- **Always check current date/time:** Run `date` command to get accurate timestamps with seconds. Never assume or use cached time
- **Timezone handling:** Use system timezone (local time wherever the user is). During travel, sessions dated in local context (Tokyo → JST, Denver → MST). This is intentional - local time is more meaningful than forcing Australian time
- **Bidirectional linking:** Standard/Full tiers add "Next session:" to the previous session when parking, creating true bidirectional session chains. Additionally, when `/pickup` loads a specific session to continue, "Continues:" appears in new session and "Continued in:" is appended to original - tracking project threads across time
- **File locking is mandatory:** Use `flock` via Bash tool, NOT the Edit tool. Edit tool has no locking and WILL cause race conditions when multiple Claude instances park simultaneously. Single lock file (`06 Archive/Claude Sessions/.lock`) protects both writes and edits
- **Quality gate is mandatory:** Step 4 MUST produce visible output for ALL tiers. Quick tier shows "Skipped", Standard/Full show results. This prevents silent skipping.
- **Three-part quality check:** Lint (syntax), Refactor (content quality), Proofread (language). All three categories checked for Standard/Full tiers.
- **Narrative tone:** Write summaries in the user's voice - direct, technical, outcome-focused
- **Open loops clarity:** Each open loop should be specific enough to resume without re-reading the conversation
- **One-sentence pickup:** The "For next session" line should be immediately actionable (or "No follow-up needed" if complete)
- **Project context:** Full tier links projects; Quick/Standard tier skip if not obvious
- **File lists:** Only list files that were actually created/updated, not files that were just read
- **Session naming:** Use descriptive names that will make sense weeks later ("Wezterm config fix" not "Terminal stuff")

## Cue Word Detection

This command should also trigger automatically when the user says these phrases:
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
