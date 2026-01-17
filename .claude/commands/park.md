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
   - Session number for today (check existing file at `~/vault/06 Archive/Claude Sessions/YYYY-MM-DD.md` to find last session number, or start at 1)
   - Topic/name for this session (concise, descriptive)
   - Use current time from step 1 (already checked)
   - Related project (if applicable, from `~/vault/03 Projects/`)
   - **Quick tier:** Skip project detection (just use topic)

6. **Find previous session and check for continuation** (conditional on tier):
   - **Quick tier:** Skip previous session linking (saves read overhead)
   - **Standard/Full tier:**
     - Check if this session is continuing a previous one (from `/pickup` context)
     - If continuing: Store continuation link for inclusion in summary
     - Otherwise: Read recent session files to find the most recent session
     - Extract title for backlink

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
   - Create lock file before writing: `~/vault/06 Archive/Claude Sessions/.YYYY-MM-DD.md.lock`
   - Wait up to 5 seconds for lock acquisition
   - If lock cannot be acquired, warn: "Another session is parking simultaneously. Waiting..."
   - Append to `~/vault/06 Archive/Claude Sessions/YYYY-MM-DD.md` (using current date from step 1)
   - If file doesn't exist, create it with header: `# Claude Session - YYYY-MM-DD`
   - Use tier-appropriate format from step 7
   - Maintain chronological order (latest session at bottom)
   - Release lock file after write completes
   - Implementation note: Use bash `flock` or create/delete lock file atomically

8a. **Add forward link to original session** (if continuing previous session):
   - **If this session continues a previous one:**
     - Read the original session file (from "Continues:" link)
     - Find the original session heading
     - Append below its "Pickup Context" section:
       ```markdown
       **Continued in:** [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - Topic]] ([Date])
       ```
     - This creates bidirectional continuation tracking
   - **If not a continuation:** Skip this step

9. **Update Works in Progress** (conditional on tier):
   - **Quick tier:** Skip WIP update (session too minor to warrant it)
   - **Standard tier:** Update WIP only if session explicitly linked to a project
   - **Full tier:** Always update WIP for related projects
   - Read `~/vault/01 Now/Works in Progress.md`
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
✓ Previous session linked

Shutdown complete. You can rest.

To pickup: `claude` or `/pickup`
```

**Full tier:**
```
✓ Session summary saved to: 06 Archive/Claude Sessions/YYYY-MM-DD.md
✓ Open loops documented: N items
✓ Linked to previous session (Session N-1 - Topic)
✓ Project updated: [Project Name] (if applicable)
✓ All files linted and validated

Shutdown complete. You can rest.

To pickup: `claude` (will show recent sessions) or `/pickup`
```

## Guidelines

- **Park ALL sessions:** Use `/park` for every session, even quick tasks. The system auto-detects appropriate tier.
- **Tiered overhead:** System minimizes friction by matching overhead to session importance:
  - Quick: < 5 min, no files → one-line log (5 sec overhead)
  - Standard: 5-45 min, few files → summary + open loops (30 sec overhead)
  - Full: 45+ min, many files → comprehensive (90 sec overhead)
- **Auto-detection works:** Default `--auto` mode correctly identifies tier 95%+ of the time
- **Explicit override available:** Use `--quick`, `--standard`, or `--full` to override auto-detection
- **Quick tier for throwaway sessions:** 3-minute lookups, quick questions, minor tasks
- **Completed work has no open loops:** For finished sessions, write "None - work completed" or list completed checkboxes
- **Always verify NAS accessibility:** First step - check mount status before any write operations. If NAS is unavailable, abort rather than silently fail
- **Always check current date/time:** Run `date` command to get accurate timestamps with seconds. Never assume or use cached time
- **Timezone handling:** Use system timezone (local time wherever Harrison is). During travel, sessions dated in local context (Tokyo → JST, Denver → MST). This is intentional - local time is more meaningful than forcing Australian time
- **Continuation tracking:** When `/pickup` loads a previous session, `/park` creates bidirectional links: "Continues:" in new session, "Continued in:" appended to original. This tracks project threads across time
- **File locking for safety:** Use lock files to prevent race conditions when multiple Claude instances park simultaneously
- **Conditional auto-fix:** Quick tier skips linting (not justified); Standard/Full tiers lint modified files
- **Silent when clean:** Only show fix report if issues were found and corrected
- **Narrative tone:** Write summaries in Harrison's voice - direct, technical, outcome-focused
- **Open loops clarity:** Each open loop should be specific enough to resume without re-reading the conversation
- **One-sentence pickup:** The "For next session" line should be immediately actionable (or "No follow-up needed" if complete)
- **Project context:** Full tier links projects; Quick/Standard tier skip if not obvious
- **File lists:** Only list files that were actually created/updated, not files that were just read
- **Session naming:** Use descriptive names that will make sense weeks later ("Wezterm config fix" not "Terminal stuff")

## Cue Word Detection

This command should also trigger automatically when Harrison uses these phrases:
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
