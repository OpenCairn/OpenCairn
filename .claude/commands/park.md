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

0. **Verify vault is accessible** before proceeding:
   - Check that the session archive directory exists: `06 Archive/Claude Sessions/`
   - If the directory doesn't exist or isn't writable, warn the user
   - Only proceed if vault is confirmed accessible

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

4. **Automatic lint, refactor, proofread** (conditional on tier):
   - **Quick tier:** Skip linting (overhead not justified for quick tasks)
   - **Standard tier:** Lint only files modified this session (not all files)
   - **Full tier:** Lint all modified files + check for broken links across vault
   - Linting checks:
     - American English → British English (organise, categorise, prioritise, realise, analyse, summarise)
     - Inconsistent terminology (ensure park/pickup not parking/resume/restore)
     - YAML frontmatter syntax errors
     - Broken file paths or links
   - Fix any issues found automatically
   - If fixes were made, display brief report:
     ```
     🔧 Auto-fixed before parking:
     - Fixed 3 American English spellings in command files
     - Updated terminology in CLAUDE.md (resume → pickup)
     ```
   - If nothing to fix, skip this output entirely

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
   - Use file locking to prevent race conditions if multiple Claude instances are running
   - Create lock file before writing: `06 Archive/Claude Sessions/.YYYY-MM-DD.md.lock`
   - Wait up to 5 seconds for lock acquisition
   - If lock cannot be acquired, warn: "Another session is parking simultaneously. Waiting..."
   - Append to `06 Archive/Claude Sessions/YYYY-MM-DD.md` (using current date from step 1)
   - If file doesn't exist, create it with header: `# Claude Session - YYYY-MM-DD`
   - Use tier-appropriate format from step 7
   - Maintain chronological order (latest session at bottom)
   - Release lock file after write completes
   - Implementation note: Use bash `flock` or create/delete lock file atomically

8a. **Add forward link to previous session** (standard/full tier):
   - **Quick tier:** Skip (no previous session linking done)
   - **Standard/Full tier:**
     - If no previous session found in step 6, skip forward linking (first session ever)
     - Acquire file lock on previous session's file (same pattern as step 8)
     - Read the previous session's file
     - **Idempotency check:** If "Next session:" already exists for this session heading, skip (prevents duplicates on re-park)
     - **Handle Quick tier previous sessions:** Quick format has no "Pickup Context" section
       - If previous session is Quick tier (ends with `[Q]`): Append forward link after the one-line summary
       - If previous session is Standard/Full tier: Add below "Pickup Context" section
     - Add forward link:
       ```markdown
       **Next session:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]]
       ```
     - Release file lock
     - **Error handling:** If forward link fails (file missing, lock timeout):
       - Log warning but don't fail the park
       - Set `forward_link_failed = true` for completion message
   - **If this session also continues a specific previous session** (from `/pickup`):
     - Add "Continued in:" link to the original session as well (if different from immediate previous)
     - Format: `**Continued in:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]] (YYYY-MM-DD)`
     - Same file locking and error handling applies

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
✓ Session logged: 06 Archive/Claude Sessions/YYYY-MM-DD.md (Quick park)

Quick park complete. Minimal overhead for minor task.
```

**Standard tier:**
```
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
✓ Session summary saved to: 06 Archive/Claude Sessions/YYYY-MM-DD.md
✓ Open loops documented: N items
✓ Bidirectional links added (previous ↔ next)
  [OR if forward_link_failed: "⚠ Forward link to previous session failed (session still saved)"]
  [OR if no previous session: "✓ No previous session to link (first session)"]
✓ Project updated: [Project Name] (if applicable)
✓ All files linted and validated

Shutdown complete. You can rest.

To pickup: `claude` (will show recent sessions) or `/pickup`
```

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
- **Always verify vault accessibility:** First step - check that session archive directory exists before writing. If vault is unavailable, warn the user
- **Always check current date/time:** Run `date` command to get accurate timestamps with seconds. Never assume or use cached time
- **Timezone handling:** Use system timezone (local time wherever the user is). During travel, sessions dated in local context (Tokyo → JST, Denver → MST). This is intentional - local time is more meaningful than forcing Australian time
- **Bidirectional linking:** Standard/Full tiers add "Next session:" to the previous session when parking, creating true bidirectional session chains. Additionally, when `/pickup` loads a specific session to continue, "Continues:" appears in new session and "Continued in:" is appended to original - tracking project threads across time
- **File locking for safety:** Use lock files to prevent race conditions when multiple Claude instances park simultaneously. Applies to both step 8 (writing new session) and step 8a (editing previous session for forward link)
- **Conditional auto-fix:** Quick tier skips linting (not justified); Standard/Full tiers lint modified files
- **Silent when clean:** Only show fix report if issues were found and corrected
- **Narrative tone:** Write summaries in the user's voice - direct, technical, outcome-focused
- **Open loops clarity:** Each open loop should be specific enough to resume without re-reading the conversation
- **One-sentence pickup:** The "For next session" line should be immediately actionable (or "No follow-up needed" if complete)
- **Project context:** Full tier links projects; Quick/Standard tier skip if not obvious
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
