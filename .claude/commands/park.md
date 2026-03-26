---
name: park
aliases: [shutdown-complete]
description: Capture session — end it, or checkpoint and keep working. Full bookkeeping either way.
parameters:
  - "--quick" - Minimal parking (one-line log entry, for trivial sessions)
  - "--full" - Comprehensive parking (default for anything worth documenting)
  - "--auto" - Auto-detect tier based on session characteristics (default)
  - "--compact" - Run /compact after saving, then continue working (Full tier only)
---

# Park - Session Capture

You are capturing a work session — either ending it or saving a mid-session checkpoint. The bookkeeping is identical either way: quality gate, WIP update, continuation links, reference graph tracing, stranded work product check, tickler. The only difference is the closing message.

**Checkpoint mode:** If triggered by checkpoint/save/waypoint phrases, or with `--compact`, the session continues after capture. Checkpoint cue words also imply `--compact`. Closing message says "Progress saved. Session continues." instead of "Parked. Pick up when ready."

**⚠ One capture at a time.** Do not run `/park` or `/checkpoint` in parallel across multiple sessions. The write-session script uses `--create` (truncate) for the first session of the day, which will destroy a parallel session's content. Session numbering also can't be resolved correctly when two sessions race. Capture one session, wait for completion, then capture the next.

## Tier Philosophy

**Two tiers only:**
- **Quick** - Genuinely trivial sessions (<5 min, minimal file interaction, just a question answered). One line is enough.
- **Full** - Everything else. If it's worth documenting at all, do it properly. Includes pickup context, key insights, open loops, continuation links.

The old "standard" tier was a false economy - saving 30 seconds of processing time but losing context that might be valuable later is bad math.

## Instructions

### Phase 1: Setup and Verification

0. **Resolve vault path** before proceeding:
   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```
   If error, abort. Read `.claude/commands/_shared-rules.md` and apply its rules throughout this command. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"` (for session file naming)
   - Get current time with seconds: `date +"%I:%M:%S%p" | tr '[:upper:]' '[:lower:]'` (for session timestamp)
   - Store these for use in metadata and file paths
   - Note: Including seconds prevents session numbering collisions if multiple sessions park in the same minute

2. **Check for merge-continuation** before creating a new session:
   - Determine from context whether this is a direct continuation of a recently parked session (same task, just finishing a loose end). Indicators: `/pickup` loaded a specific session, topic is identical, work is completing an open loop from that session. Only ask the user if genuinely ambiguous.
   - If yes: **don't create a new session entry.** Instead, update the existing session using the update-session-section script (not the Edit tool — race condition risk with parallel parks):
     ```bash
     # Append to Summary (leading blank line creates paragraph break)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Summary"

     Merge addendum: [description]
     EOF

     # Append to Files Created (handles None→list automatically)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Files Created"
     - path/to/file - description
     EOF

     # Append to Files Updated (handles None→list automatically)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Files Updated"
     - path/to/file - description
     EOF

     # Replace Next Steps / Open Loops (when changed)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Next Steps / Open Loops" --replace
     - Updated loop
     EOF

     # Replace Pickup Context (always replaced on merge)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Pickup Context" --replace
     **For next session:** ...
     **Project:** ...
     EOF
     ```
   - **After merging, run Steps 5, 12, 13, 14, 14a, 15** (quality gate, WIP update, reference graph, open loop routing, backfill — all using the merged session's number). Skip Steps 3-4, 6-11 (no new session entry needed).
   - This applies even if the session to merge into isn't the most recent — with parallel sessions, the relevant session may be the penultimate or earlier entry.
   - Completion message: `✓ Merged into Session N — [what was added]`
   - If not a continuation, proceed normally:

3. **Detect session tier** (unless explicit parameter provided):
   - **Quick tier** triggers when ALL of:
     - Conversation < 10 turns AND
     - No files created/updated AND
     - Few non-context files read (< 3 distinct files, excluding routine context loads like `07 System/Context -` files and CLAUDE.md) AND
     - Session < 5 minutes duration AND
     - No decisions or status changes — just information lookup
   - **Full tier** triggers when ANY of:
     - Files created/updated OR
     - Significant reading breadth (3+ distinct non-context files read) OR
     - Decisions made OR
     - Status changes identified (task completed, booking confirmed/cancelled, item resolved) OR
     - Open loops generated OR
     - Session involved any substantive work
   - If `--auto` (default): Auto-detect based on above
   - If `--quick` or `--full`: Use explicit tier
   - Display tier selection:
     ```
     Capture tier: [Quick/Full] (auto-detected)
     ```

4. **Read the conversation transcript** to understand what was accomplished, decisions made, and what remains open.

### Phase 2: Quality Assurance

5. **⚠️ QUALITY GATE: Lint, refactor, proofread modified files**

   **This step MUST produce visible output. No silent skipping.**

   | Tier | Action |
   |------|--------|
   | Quick | Display: `⏭ Quality check: Skipped (Quick tier)` and proceed |
   | Full | Check all modified files (vault AND repo) + vault-wide broken link scan |

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
   - **Mid-session direction changes:** If the session's conclusion diverges from its starting position (e.g. an item went from "moot" to "live option", or a decision was reversed), re-read files edited earlier in the session and verify they reflect the final state, not the interim state. This is distinct from general staleness — these files were correct when written but became stale because the conversation changed direction.
   - **Research persistence:** Did this session produce research (subagent findings, web searches, analysis) that should be captured in a reference/area file, not just narrated in the session summary? If a stub entry exists for the researched topic, update it with the findings.

   **VERIFY** - Session summary accuracy (if updating an already-parked session):
   - Do open loops still reflect reality? (If user completed something mid-conversation, remove it from the list)
   - Does pickup context still match? (If "ready for upload" is now uploaded, update the line)
   - Were any "Next Steps" completed during the session? Remove them from the list (they're no longer open)

   **PROOFREAD** - Language and consistency:
   - **Spelling localisation:** Use the locale from the user's CLAUDE.md (`**Locale:**` line). If `en_AU` or `en_GB`: normalise to British/Australian spelling (organise, categorise, prioritise, realise, analyse, summarise, colour, favour). If `en_US`: normalise to American spelling. If no locale set: skip spelling normalisation.
   - Terminology consistency (park/pickup not parking/resume/restore)
   - Typos, grammar, unclear phrasing
   - Tone consistency with the user's voice

   **Scope:** Check ALL files modified during the session, not just vault files. If the session touched repo files (e.g. `~/repos/OpenCairn/`), command files (`~/.claude/commands/`), or scripts, include those in the quality gate. Spelling localisation applies primarily to vault prose; command/script files get lint and refactor checks but spelling is less critical there.

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

   **⛔ CHECKPOINT:** You cannot proceed to Step 6 until one of the above outputs appears in your response. If you find yourself writing session metadata without having displayed a quality check result, STOP and return to this step.

### Phase 3: Document and Archive

6. **Determine session metadata:**
   - Session number for today — extract mechanically, do NOT count by reading:
     ```bash
     NEW_NUM=$("{VAULT}/.claude/scripts/next-session-number.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md")
     echo "Session number: $NEW_NUM"
     ```
   - Topic/name for this session (concise, descriptive)
   - Use current time from step 1 (already checked)
   - Related project (if applicable) — follow Project Linking Rules in `_shared-rules.md` Section 2
   - **Quick tier:** Skip project detection (just use topic)

7. **Check for continuation** (conditional on tier):
   - **Quick tier:** Skip
   - **Full tier:**
     - Check if this session is continuing a previous one (from `/pickup` context)
     - If continuing: Store continuation link for inclusion in summary (the `**Continues:**` line in Pickup Context)

8. **Generate session summary** (format varies by tier):

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
- Specific actionable item with clear next action
- Another open loop that needs attention
[Each item should be actionable and specific enough to resume without re-reading entire conversation]

### Files Created
- path/to/file.md - [purpose/description]

### Files Updated
- path/to/file.md - [what changed and why]

### Pickup Context
**For next session:** [One clear sentence about where to pick up - the very next action to take]
**Continues:** [[06 Archive/Claude/Session Logs/YYYY-MM-DD#Session X - Topic]] (if this session continues previous work)
**Project:** [[03 Projects/Project Name]] (if applicable)
```

9. **Write the summary** (with file locking for concurrent safety):
   - **CRITICAL: Use the write-session script, NOT inline flock or the Edit tool**
   - Inline flock commands corrupt `settings.local.json` (the entire command including session content gets saved as a permission pattern)
   - The script handles locking, file creation, and atomic writes

   **✓ USE THE WRITE-SESSION SCRIPT:**

   Use the dedicated script instead of inline bash (prevents permission system corruption):

   **Appending to existing file:**
   ```bash
   cat << 'EOF' | "{VAULT}/.claude/scripts/write-session.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md"
   ## Session N - [Topic] ([Time])

   [Session content here]
   EOF
   ```

   **Creating new file (first session of the day):**
   ```bash
   cat << 'EOF' | "{VAULT}/.claude/scripts/write-session.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" --create
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

10. **Add continuation link** (full tier only, only if continuing previous work):
   - **Quick tier:** Skip
   - **Only fires if this session continues a specific previous session** (from `/pickup` context). If not a continuation, skip this step entirely.
   - Do NOT add chronological "Next session:" links — sessions are already in order in the file. Only topical continuation links carry information.
   - Add "Continued in:" link to the original session being continued:
     - Format: `**Continued in:** [[06 Archive/Claude/Session Logs/YYYY-MM-DD#Session N - Topic]] (DD Mon)`
     - Use the forward-link script with `--continued-in`:
       ```bash
       # Same-day:
       "{VAULT}/.claude/scripts/add-forward-link.sh" --continued-in "<session-file>" <orig-num> <new-num> "<new-topic>"
       # Cross-day:
       "{VAULT}/.claude/scripts/add-forward-link.sh" --continued-in "<session-file>" <orig-num> <new-num> "<new-topic>" "<target-date>.md"
       ```
   - **Error handling:** If script fails (file missing, lock timeout, session not found), log warning but don't fail the park.

11. **Check for stranded work product in Claude-internal files** (Full tier only):
   - **Quick tier:** Skip
   - **Full tier:** Check whether any Claude-internal files were created or modified during this session. Pass the session start time (from step 1) so only files from this session are flagged:
     ```bash
     "{VAULT}/.claude/scripts/check-stranded-plans.sh" "HH:MM:SS"
     ```
   - If any files found, **individually assess each file** — do not batch-dismiss:
     - Read each plan file
     - **Subagent files** (pattern `*-agent-*.md`) often contain standalone reference material distinct from the main plan — assess separately, not as "part of" the main plan's migration
     - Compare each file's content against the relevant vault project doc
     - If the vault doc is stale or missing the content: **migrate it now** (update the vault file before completing the park)
   - Display result:
     ```
     ✓ No stranded work product in ~/.claude/plans/
     ```
     or:
     ```
     🔧 Migrated plan content to vault: [vault file path]
     ```
   - **Why this exists:** Work product written to `~/.claude/plans/` has been stranded there multiple times. These files don't sync, aren't visible in Obsidian, and effectively don't exist outside the session.

12. **Update Works in Progress** (conditional on tier):
   - **Quick tier:** Skip WIP update (session too minor to warrant it)
   - **Full tier:** Update WIP for related projects
   - Read `{VAULT}/01 Now/Works in Progress.md`
   - Find the relevant project section
   - Update status with:
     - **Last:** [Today's date and time from step 1] - [Brief description of progress]
     - **Next:** Three cases:
       1. **Has project/area doc:** `→ [[03 Projects/Project Name]]` — pointer only, project doc is SSOT for its task queue
       2. **No doc, has next action:** Single next action (one line max — if it needs more, create a project doc)
       3. **No doc, work complete:** Omit Next
       Never a queue — one pointer or one action.
     - Add link to session: `→ [[06 Archive/Claude/Session Logs/YYYY-MM-DD#Session N]]`
     - **FIFO cap at 2:** After adding the new link, count standalone session link lines (lines matching `→ [[06 Archive/Claude/Session Logs/`) in this WIP entry. If there are more than 2, remove the oldest by date until exactly 2 remain. Session history lives in the archive and project hub pages; WIP links are convenience pointers, not the record of truth. **Do not trim non-session-log reference links** (`→ [[03 Projects/`, `→ [[04 Areas/`, etc.) — these are navigation pointers.
     - **⛔ FIFO verification:** After the WIP edit, mechanically verify the count. Do NOT trust your edit — count the actual lines in the file:
       ```bash
       # Extract the WIP entry for this project and count session links
       # Substitute the heading text (e.g. "Claude Code Learning / OpenCairn")
       # Uses awk index() for fixed-string matching (headings often contain / and &)
       awk 'f && /^### /{exit} index($0, "### HEADING_TEXT") == 1 {f=1} f' "{VAULT}/01 Now/Works in Progress.md" | grep -c '^→ \[\[06 Archive/Claude/Session Logs/'
       ```
       Display: `FIFO check: N/2 session links`. If more than 2, fix before proceeding.
   - **Check CURRENT line:** If the WIP entry has a CURRENT line (date, location, or status), verify it's accurate as of today. Run `date +"%a %d %b"` to confirm the day-of-week — don't trust internal computation. Update if stale.
   - Update "Last updated" timestamp at top of file with current date/time

13. **Trace reference graph for status changes** (Full tier only):
   - **Quick tier:** Skip
   - **Full tier:** Review the session for any status changes — tasks completed, bookings made/cancelled, decisions finalised, items purchased, accounts set up, etc.
   - For each status change identified:
     1. Identify the key identifier (project name, booking number, feature name, account name, etc.)
     2. Grep the vault for that identifier, excluding archive/session files (historical records, not living docs):
        ```bash
        grep -r "identifier" "{VAULT}/" --include="*.md" -l --exclude-dir="06 Archive"
        ```
     3. Read and update every living document in the results that references the changed item
   - **This step exists because:** WIP is one file. Status changes typically touch WIP, the project hub, area detail files, the tickler, This Week.md, and potentially other planning docs. Updating only WIP leaves stale state everywhere else. Without this step, the user has to manually ask for a full update pass after every status change.
   - Display result:
     ```
     ✓ Reference graph: No status changes to trace
     ```
     or:
     ```
     ✓ Reference graph: [N] files updated for [identifier] status change
     - [file1] - [what changed]
     - [file2] - [what changed]
     ```

14. **Route ALL open loops to SSOT** (Full tier only):
   - **Quick tier:** Skip
   - Every open loop from the session must land in a canonical location. Session docs are plain-text records, not task trackers. Route automatically (no per-item prompting):

   **Routing logic (applied to each open loop):**

   1. **Parse for date patterns** (reuse existing date parsing):
      - "week of [date]" → that Monday
      - "after [date]" / "from [date]" → that date
      - "[month] [day]" or "[day] [month]" → YYYY-MM-DD
      - "next week" → next Monday
      - "next month" → 1st of next month

   2. **If explicit future date found** → Tickler via write-tickler script:
      ```bash
      "{VAULT}/.claude/scripts/write-tickler.sh" "{VAULT}/01 Now/Tickler.md" "YYYY-MM-DD" "- [ ] [Loop text] → [[06 Archive/Claude/Session Logs/YYYY-MM-DD#Session N - Topic]]"
      ```

   3. **If no date + This Week.md is current** (today falls within date range) → add to tomorrow's section in This Week.md (or today's if morning session). Use the Edit tool. Format: `- [ ] [Loop text] → [[project/area doc]]`. Append a project/area link: `→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`, or `→ [[01 Now/Works in Progress#Heading]]` if tracked in WIP. The session's Project link (Step 6) identifies the target. No link for items with no project context.

   4. **If no date + session has a Project link** → update that project file's next action section

   5. **If no date + no project + This Week.md stale/missing** → Tickler with tomorrow's date via write-tickler script

   **Dedup check:** Before writing to any target file, grep for the item text (or a distinctive substring). If already present, skip. Items may have been manually added during the session.

   **After routing, display brief summary:**
   ```
   ✓ Routed: [item] → This Week (Thu)
   ✓ Routed: [item] → Tickler (2026-03-15)
   ✓ Routed: [item] → Project: [Name]
   ✓ Skipped (already present): [item]
   ```

14a. **Backfill "Files Updated" in session log** (Full tier only):
   - **Quick tier:** Skip
   - Steps 12-14 modify vault files (WIP, This Week, Tickler, project hubs) that aren't known at step 9 when the session log is written. Backfill these into the session log's "### Files Updated" section.
   - Collect all files modified during steps 12-14 (WIP update, reference graph tracing, open loop routing)
   - Use the backfill-files-updated script:
     ```bash
     cat << 'EOF' | "{VAULT}/.claude/scripts/backfill-files-updated.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N
     - 01 Now/Works in Progress.md - [what changed]
     - 01 Now/This Week.md - [what changed]
     EOF
     ```
     Where `N` is the current session number. The script handles:
     - File locking (flock) for concurrent safety
     - Replacing placeholder "None" lines (bare `None`, `- None`, `- None (explanation)`) or appending after existing entries
     - Finding the correct section boundary within the session block
   - Only include files actually modified — if steps 12-14 didn't touch a file, don't list it
   - **Why this exists:** The session log is written at step 9 before steps 12-14 run, so "Files Updated" is always incomplete without this backfill. This was caught by audit — sessions were reporting "Files Updated: None" when WIP, This Week, and project files had all been modified.

15. **Display completion message** (tier-appropriate):

**Quick tier:**
```
⏭ Quality check: Skipped (Quick tier)
✓ Session logged: 06 Archive/Claude/Session Logs/YYYY-MM-DD.md

Quick park complete. Minimal overhead for trivial task.
```

**Full tier:**
```
✓ Quality check: N files, M issues fixed [OR "no issues"]
✓ Session summary saved to: 06 Archive/Claude/Session Logs/YYYY-MM-DD.md
✓ Open loops documented: N items
✓ Continuation link added: [Original Session] (only if this session continues previous work)
✓ Project updated: [Project Name] (if applicable)
✓ Reference graph: N files updated for [identifier] (if any status changes traced)
  [OR "No status changes to trace" if none]
✓ Open loops routed: N items (This Week: X, Tickler: Y, Project: Z)
  [OR "✓ No open loops to route" if none]

**Closing (session ending):** "Parked. Pick up when ready."
**Closing (checkpoint / --compact):** "Progress saved. Session continues."

To pickup later: `claude` (will show recent sessions) or `/pickup`
```

**IMPORTANT:** The "Quality check" line is REQUIRED in all completion messages. If you cannot produce this line, you skipped Step 5 - go back and complete it before finishing the park.

16. **Handle --compact flag** (if specified):
   - Only applies to Full tier (Quick sessions don't need compacting)
   - After displaying completion message, run the built-in `/compact` command
   - The session summary becomes part of the compact summary, providing continuity
   - Session continues — user keeps working in the compacted conversation

## Guidelines

- **Merge continuations, don't fork sessions:** If the current session is a trivial continuation of a recently parked session (same task, <5 minutes, just finishing a loose end), update that session's entry instead of creating a new one. Use `update-session-section.sh` for all section edits (never ad-hoc sed — multiline sed fails silently). This applies even if the session to update isn't the most recent — with parallel sessions, the relevant session may be the penultimate or earlier entry. Step 2 handles this procedurally.
- **Capture ALL sessions:** Use `/park` (or `/checkpoint` mid-session) for every session, even quick tasks. The system auto-detects appropriate tier.
- **Two tiers only:** Quick (trivial) vs Full (everything else). If it's worth documenting, do it properly.
- **Quick is rare:** Most sessions are Full. Quick is for 3-minute lookups where you literally just answered a question.
- **Explicit override available:** Use `--quick` or `--full` to override auto-detection
- **Completed work has no open loops:** For finished sessions, write "None - work completed" (no bullets needed)
- **Always resolve vault path first:** Step 0 determines whether to use NAS mount or local fallback. If neither is accessible, abort rather than silently fail
- **Always check current date/time:** Run `date` command to get accurate timestamps with seconds. Never assume or use cached time
- **Timezone:** Per `_shared-rules.md` Section 7. Use system timezone.
- **Continuation linking only:** Do NOT add chronological "Next session:" or "Previous session:" links — sessions are in chronological order in the file, so these are redundant. The only cross-session links that carry information are topical: `**Continues:**` (in the new session, pointing to the session being continued) and `**Continued in:**` (added to the original session, pointing forward to the continuation). These are triggered by `/pickup` loading a specific session to continue.
- **File locking:** Per `_shared-rules.md` Section 5. Use scripts, not Edit tool.
- **Quality gate is mandatory:** Step 5 MUST produce visible output for ALL tiers. Quick tier shows "Skipped", Full shows results. This prevents silent skipping.
- **Three-part quality check:** Lint (syntax), Refactor (content quality), Proofread (language). All three categories checked for Full tier.
- **Compact integration:** Use `--compact` (or `/checkpoint`) when context is heavy and you want to continue working. Full bookkeeping persisted to vault, then compact to reclaim context. The session summary in the compacted conversation provides continuity without needing /pickup.
- **Narrative tone:** Write summaries in the user's voice - direct, technical, outcome-focused
- **Open loops clarity:** Each open loop should be specific enough to resume without re-reading the conversation
- **SSOT routing:** All open loops are routed to canonical locations at park time (This Week.md, Tickler, or project files). Session docs contain plain-text records only — they are never task trackers. This ensures /morning, /goodnight, and /pickup read from authoritative sources, not stale session copies.
- **One-sentence pickup:** The "For next session" line should be immediately actionable (or "No follow-up needed" if complete)
- **Project context:** Full tier links projects; Quick tier skips
- **Project linking:** Follow the rules in `_shared-rules.md` Section 2.
- **File lists:** Only list files that were actually created/updated, not files that were just read. Step 14a backfills files modified during the park itself (steps 12-14) into the session log — don't try to predict these at step 9. For empty sections, write bare `None` on its own line (not `- None`, not `None (explanation)` — just `None`). The backfill script tolerates variations, but bare `None` is the canonical form.
- **Session naming:** Use descriptive names that will make sense weeks later ("Wezterm config fix" not "Terminal stuff")

## Cue Word Detection

This command should also trigger automatically when the user uses these phrases:

**Session ending:**
- "bedtime"
- "wrapping up"
- "done for tonight"
- "packing up"
- "shutdown complete"
- "park"

**Checkpoint (session continues + compact):**
- "checkpoint"
- "save progress"
- "plant a flag"
- "capture this"
- "don't want to lose this"

When triggered by cue words, acknowledge and proceed with session capture. Use the cue word category to determine behaviour: session-ending cue words close out; checkpoint cue words imply `--compact` (full bookkeeping, compact context, session continues).

## Shutdown Philosophy

The goal is a clean "shutdown complete" — explicit acknowledgement of open loops so the mind can truly rest, or so you can compact context and keep working without losing track of anything. Every incomplete task is captured in a trusted system, eliminating mental residue whether you're closing for the night or reclaiming context window space mid-session.

**For completed work:** Capture it anyway. The psychological closure ("this is done, documented, and archived") is valuable. Plus six months later you'll want to know "when did I make that decision?" The session archive answers that.
