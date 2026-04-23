---
name: park
aliases: [shutdown-complete]
description: Capture session with full bookkeeping — quality gate, WIP update, open loop routing, session log.
parameters:
  - "--quick" - Minimal parking (one-line log entry, for trivial sessions)
  - "--full" - Comprehensive parking (default for anything worth documenting)
  - "--auto" - Auto-detect tier based on session characteristics (default)
---

# Park - Session Capture

You are capturing a work session. Full bookkeeping: quality gate, WIP update, continuation links, reference graph tracing, conversation draft check, tickler.

**⚠ One capture at a time.** Do not run `/park`, `/checkpoint`, or `/goodnight` in parallel across multiple sessions. The write-session script uses `--create` (truncate) for the first session of the day, which will destroy a parallel session's content. Session numbering also can't be resolved correctly when two sessions race. `/goodnight` also writes to WIP, This Week.md, and project files via the Edit tool, which has no locking — concurrent parks will silently clobber each other's edits. Park all sessions before starting goodnight, and capture one session at a time.

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
   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"` (for session file naming)
   - Get current time with seconds: `date +"%I:%M:%S%p" | tr '[:upper:]' '[:lower:]'` (for session timestamp)
   - Store these for use in metadata and file paths
   - Note: Including seconds prevents session numbering collisions if multiple sessions park in the same minute

2. **Check for merge-continuation** before creating a new session:
   - Determine from context whether this is a direct continuation of a recently parked session (same task, just finishing a loose end). Indicators: `/pickup` loaded a specific session, topic is identical, work is completing an open loop from that session (especially: a `/audit the /park` that produced fixes — that's the canonical merge case since the audit is explicitly recommended by the prior park). Only ask the user if genuinely ambiguous.
   - **Script lock timeout — diagnose, don't work around:** If `update-session-section.sh`, `backfill-files-updated.sh`, `write-session.sh`, or `add-forward-link.sh` fails with "Lock timeout after 10s / Failed to acquire lock," the most likely cause is a hung prior invocation of the same script holding the flock. This happens when the Bash tool backgrounded an earlier heredoc-fed invocation (`cat <<EOF | script.sh ... EOF`) and the script got stuck in `anon_pipe_read` waiting for stdin that never closed. **Diagnose first, then kill the hung process** — don't immediately jump to a Python workaround. Full diagnosis and remediation (fuser, ps, kill, wchan inspection) is in `_shared-rules.md` §5 Failure mode B. Python+flock is a *secondary* fallback only — it bypasses the hung script by locking a different file, which does not coordinate with the script's `.lock` and is unsafe against a genuine concurrent writer. Kill the zombies first, then re-run the dedicated script.
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
   - **After merging, run Steps 5, 11, 12, 13, 14, 14a, 14b, 15, 16, 17** (quality gate, conversation draft persistence, WIP update, reference graph, open loop routing, backfill, transcript export, completion, audit recommendation, skill monitor — all using the merged session's number). Skip Steps 3-4, 6-10 (no new session entry needed).
   - **Steps 11, 13, 14, 17 typically produce their clean-pass checkpoint output in a merge** — `✓ No at-risk work product to persist`, `✓ Reference graph: No identifier values changed`, `✓ No open loops to route`, `✓ Skill monitor: No gaps detected` — because the remediation already did the routing/graphing inline as it ran. Run the mechanical checks anyway (Scratchpad `find`, enumerate-before-grepping, loop scan) — the checkpoint emission is mandatory either way — but don't fabricate findings to fill the slots if the checks come up clean. Steps 5, 12, 14a, 14b, 14c, 15, 16 typically still have at least a small amount of real work (quality gate on the remediation edits, backfill, transcript re-export, WIP timestamp bump, completion reporting), but may also come up clean — in which case their normal success outputs apply.
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
   - **Hot-capture habit check (nudge, not enumeration):** If substantive insights, frameworks, or content-level corrections surfaced during the session but weren't routed in the moment via a mid-session "save that to [file]" interjection, name the habit gap in one line so the user can notice it. **Do not cold-read the transcript to enumerate, classify, or route those items here.** That's the failure mode hot-capture interjection is designed to avoid, and cold-running it at park time re-introduces the problem. The check is metacognitive only: surface when the habit slipped, don't substitute tooling for the habit.
   - **Why this exists:** Cold-capture routing at session end has failure modes (misclassification, incorrect content extraction, cascading write errors) that hot-capture interjection avoids. This check is deliberately a nudge only, not a catch-up mechanism. Hot capture is primary; /park's role is to make habit gaps visible, not to substitute for the habit.

   **VERIFY** - Session summary accuracy (if updating an already-parked session):
   - Do open loops still reflect reality? (If user completed something mid-conversation, remove it from the list)
   - Does pickup context still match? (If "ready for upload" is now uploaded, update the line)
   - Were any "Next Steps" completed during the session? Remove them from the list (they're no longer open)

   **PROOFREAD** - Language and consistency:
   - **Spelling localisation:** Skip if a PostToolUse spelling hook (e.g. britfix) already normalises spelling at write time. Otherwise: use the locale from the user's CLAUDE.md (`**Locale:**` line). If `en_AU` or `en_GB`: normalise to British/Australian spelling (organise, categorise, prioritise, realise, analyse, summarise, colour, favour). If `en_US`: normalise to American spelling. If no locale set: skip spelling normalisation.
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
   - **Display the determination explicitly** — this is the single source for the project link used in Steps 8 and 12:
     ```
     Session N: [Topic] | Project: [[03 Projects/Name]] (or "None")
     ```

   **⛔ CHECKPOINT:** You cannot proceed to Step 7 until the `Session N: [Topic] | Project: [[...]]` line appears in your response. Step 9b's Project check compares against this output — if Step 6 never emitted it, Step 9b is auditing internal memory rather than observable state. Small deviations here cascade. If you find yourself writing session content without having displayed this line, STOP and return to this step.

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
**Project:** [use exact link from Step 6 — do not rewrite]
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

9a. **⛔ Pickup Context section verification** (Full tier only):
   After writing the session, verify the `### Pickup Context` section actually exists in the just-written entry. The write-session script writes whatever stdin you give it without validating that all required sections are present — it's possible to write a session entry that's missing sections entirely. The Pickup Context section is the load-bearing one because it carries both the next-session pointer AND the Project link.

   **Scope the check to the just-written session block** (N = session number from Step 6), not the global file count. A global `grep -c` across the whole day's log can pass when the session being verified is the one missing — e.g. if an earlier Full-tier session already has Pickup Context and Session N doesn't, the count is still ≥1 and passes. The check must verify the specific block:
   ```bash
   # `-v z=0 $z` workaround: slash-command loader strips bare $0 (positional-arg shorthand per Skills docs)
   awk -v n="$N" -v z=0 '$z ~ "^## Session " n " "{p=1; next} p && /^## Session /{exit} p' "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" | grep -c '^### Pickup Context'
   ```
   Expected: exactly 1. If 0, Session N is missing Pickup Context — add it via the Edit tool (the script can't append a new section that doesn't exist). Display: `Pickup Context check: present ✓` or, if fixed: `Pickup Context check: section was missing, added via Edit`.

   **⛔ CHECKPOINT:** You cannot proceed to Step 9b until `Pickup Context check:` output appears in your response.

9b. **⛔ Project link verification** (Full tier only):
   After confirming the Pickup Context section exists, verify the `**Project:**` line inside it matches Step 6's determination. Extract mechanically:
   ```bash
   grep '^\*\*Project:\*\*' "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" | tail -1
   ```
   Compare against Step 6 output. If they differ, fix the session log before proceeding.
   Display: `Project check: [link] ✓` or, if fixed: `Project check: fixed [old] → [new]`

   **⛔ CHECKPOINT:** You cannot proceed to Step 10 until `Project check:` output appears in your response. If you find yourself writing continuation links without having displayed a project check result, STOP and return to this step.

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

11. **Check for at-risk work product** (Full tier only):
   - **Quick tier:** Skip
   - **Full tier:** Two failure modes to check.

     **(a) Conversation-only drafts.** Scan the conversation for drafts composed inline that only exist as text output — emails, messages, analysis, plans. Common triggers: `/reply` drafts, email compositions, multi-paragraph analysis. If found, write each to its semantic home in the vault (correspondence file, project doc, area file).

     **(b) Work product persisted to transient capture surfaces.** Scratchpad, Inbox, and daily notes are designed to be cleared on a regular cadence — they are *not* durable homes.

     **Scope:** this-session contributions only. Pre-existing content sitting in a transient surface across multiple sessions is the user's intentional working buffer, not at-risk material from this session. Cross-session cleanup is `/weekly-hygiene` Step 6's job, not /park's.

     **Detection:** Use `find` with `mtime` filtering, **scoped to transient-surface parent directories** — never from `{VAULT}` itself. Finding from vault root crawls `.git` auto-save history, which on a long-lived vault can take minutes. Transient surfaces live in known top-level directories (`01 Now`, `02 Inbox`, daily-note folders) that don't contain `.git`, so scoping the find to those parents avoids the crawl cost entirely while keeping the check mechanical (filesystem fact, not Claude's memory) and proportionate. Do not gate on "I don't think I wrote there" — memory-based gating is the failure mode this check exists to prevent.

     For a session of N minutes, use `-mmin -N` (a generous default for typical sessions is `-mmin -120`):

     ```bash
     # Scope the find to transient-surface parent directories.
     # NEVER pass {VAULT} itself as a find root — it crawls .git auto-save history.
     # Add vault-specific transient locations (daily-note folders, etc.) as additional roots.
     find "{VAULT}/01 Now" "{VAULT}/02 Inbox" -maxdepth 2 -type f -name "*.md" -mmin -120 2>/dev/null
     ```

     For each result, judge whether it's a transient surface (Scratchpad.md, inbox capture, daily note) — skip durable files in the same directories that happen to have recent mtimes (e.g. `01 Now/Works in Progress.md`, `01 Now/This Week.md`, `01 Now/Tickler.md`). For each transient-surface hit, read it and judge whether new content from this session is durable work product (a draft for a forthcoming submission, message, or document; anything a future session would need to retrieve). If yes, move it to its semantic home, remove it from the transient surface, and update This Week.md or project hubs that pointed at the old location.

     - **⛔ CHECKPOINT:** Display exactly one of:
       ```
       ✓ No at-risk work product to persist
       ```
       ```
       🔧 Persisted N item(s): [paths]
       ```

   - **Why this exists:** Added 2026-04-09 after a peer-review COI disclosure was persisted to Scratchpad in one session and silently destroyed by a later session's cleanup pass before the user needed it. The unconditional-read requirement prevents the "I don't remember writing there" failure from recurring.

12. **Update Works in Progress** (conditional on tier):
   - **Quick tier:** Skip WIP update (session too minor to warrant it)
   - **Full tier:** Update WIP for related projects
   - **"Last updated" timestamp bump is handled at Step 14c**, not here. Moved after Step 14 so bumping doesn't depend on predicting whether loop routing will modify planning files.
   - **If there is no related project to update at all, skip the rest of Step 12** (proceed to Step 13).
   - **Shipped one-shot work (published post, completed migration, resolved bug):** Do not create a new WIP entry or a new project file. Point the session log's `**Project:**` field at an existing area hub per the Shipped-one-shot-work rule in `_shared-rules.md` §2. Skip the rest of Step 12 (timestamp bump handled at Step 14c).
   - **Multi-project operational sessions — link only entries that received a content write.** When this session is itself an operational pass (e.g. /goodnight, /morning, /weekly-review running inside another session — any session that touches several projects' state without being scoped to one), iterate the rest of Step 12 across each touched project, but only add a session link to entries where **this session wrote new content into the entry's section**. Reading/summarising the entry in a landscape pass does not count. The file-level "Last updated" bump at Step 14c does not count either — that's unconditional for Full tier and carries no per-entry signal. **The check is mechanism-independent** — it includes the Edit tool, the Write tool, Bash heredoc/sed/awk targeting WIP, and any `mcp__obsidian__*` tool (e.g. `mcp__obsidian__obsidian_update_note`, `mcp__obsidian__obsidian_search_replace`) that wrote to WIP. **Observable verification:** scan the conversation for tool calls whose target file is `01 Now/Works in Progress.md` — *regardless of which tool* — and for each one, check whether the change fell inside a project entry's heading-to-next-heading slice (Status / Last / Next / narrative content under `### Project Name`). Entries with no such write get no session link from this session; the file-level "Last updated" bump is their only signal. The 3-link FIFO cap is precious — don't burn slots on operational sessions that only traversed an entry.
   - Read `{VAULT}/01 Now/Works in Progress.md`
   - Find the relevant project section (or sections — multi-project sessions iterate this routine across each touched project)
   - Update status with:
     - **Last:** [Today's date and time from step 1] - [Brief description of progress]
     - **Last-field cap:** Single current entry — replace, don't chain. The Last field carries only the most recent session's update. **Do NOT prepend "Earlier [date]..." blocks for prior entries** — when updating Last, replace the prior value outright. Prior Last content is already preserved verbatim in the session-log archive and referenced by the 3-link session FIFO below; duplicating it inline as "Earlier" chains is the Last-field accretion anti-pattern. This is the prose-side parallel to the FIFO cap on session links: both rules keep WIP as a current-state dashboard, not a running log. If a prior entry contained durable thinking/lessons/decisions that belong in a project or area doc, migrate those to their natural home *before* replacing the Last field — the trimming check is "has the content been captured in an SSOT elsewhere?", not "does Last look tidy?"
     - **Next:** Three cases:
       1. **Has project/area doc:** `→ [[03 Projects/Project Name]]` — pointer only, project doc is SSOT for its task queue
       2. **No doc, has next action:** Single next action (one line max — if it needs more, create a project doc)
       3. **No doc, work complete:** Omit Next
       Never a queue — one pointer or one action.
     - Add link to session: `→ [[06 Archive/Claude/Session Logs/YYYY-MM-DD#Session N]]`
     - **FIFO cap at 3:** After adding the new link, count standalone session link lines (lines matching `→ [[06 Archive/Claude/Session Logs/`) in this WIP entry. If there are more than 3, remove the oldest by date until exactly 3 remain. Session history lives in the archive and project hub pages; WIP links are convenience pointers, not the record of truth. **Do not trim non-session-log reference links** (`→ [[03 Projects/`, `→ [[04 Areas/`, etc.) — these are navigation pointers.
     - **⛔ FIFO verification:** After the WIP edit, mechanically verify the count. Do NOT trust your edit — count the actual lines in the file:
       ```bash
       # Extract the WIP entry for this project and count session links
       # Substitute the heading text (e.g. "Claude Code Learning / OpenCairn")
       # Uses awk index() for fixed-string matching (headings often contain / and &)
       # `-v z=0 $z` workaround: slash-command loader strips bare $0 (positional-arg shorthand per Skills docs)
       awk -v z=0 'f && /^### /{exit} index($z, "### HEADING_TEXT") == 1 {f=1} f' "{VAULT}/01 Now/Works in Progress.md" | grep -c '^→ \[\[06 Archive/Claude/Session Logs/'
       ```
       Display: `FIFO check: N/3 session links`. If more than 3, fix before proceeding.
   - **Check CURRENT line:** If the WIP entry has a CURRENT line (date, location, or status), verify it's accurate as of today. Run `date +"%a %d %b"` to confirm the day-of-week — don't trust internal computation. Update if stale.

13. **Trace reference graph for status changes** (Full tier only):
   - **Quick tier:** Skip
   - **Full tier:** Review the session for any status changes. A "status change" includes: tasks completed, bookings made/cancelled, decisions finalised, items purchased, accounts set up, **and any cross-referenced value that changed** (counts, dates, amounts, names, event lists).
   - **⛔ CHECKPOINT — Enumerate before grepping.** List every identifier value that changed during the session as `old → new` pairs. This enumeration must appear in your response before any grep runs. If no values changed, state "No identifier values changed" explicitly. "Already traced during session" is not valid — the session edits targeted specific files, but the same identifiers appear in files you didn't edit.
     ```
     Changed values:
     - "6 events" → "7 events"
     - "status: pending" → "status: done"
     [OR] No identifier values changed.
     ```
     - **⛔ No regex alternation from memory when N>3.** When enumeration produces more than three identifiers (e.g. a batch file move), do NOT hand-construct a `foo|bar|baz` alternation pattern from memory for the grep step below — typed-from-memory alternation silently drops entries and you won't notice because the grep still returns results. Instead: iterate each identifier as a separate grep call, or mechanically construct the pattern from the enumeration you just wrote down. The enumeration is the authoritative list; the grep pattern must be built from it, not re-remembered.
     - **For file moves specifically, add plain-text path strings to the enumeration, not just filenames.** Companion docs (transcripts, notes, metadata sidecars) often embed full `**Source:** /path/to/file.ext` references that won't match a filename-only grep or wikilink-shaped queries. When a file moves, both the filename and the full old path go in the enumeration as separate identifiers.
   - For each enumerated identifier:
     1. Grep the vault for the **old** value, excluding archive/session files (historical records, not living docs):
        ```bash
        grep -r "old value" "{VAULT}/" --include="*.md" -l --exclude-dir="06 Archive"
        ```
     2. Display the grep results (even if empty — the output proves the grep ran)
     3. Read and update every living document that still references the old value
   - **For file-path identifier changes specifically (rename, move, delete):** after the grep pass, run the vault's structural link-integrity query as a post-check (e.g. `obsidian unresolved` for an Obsidian vault; see /audit §Layer 3 for equivalent tools in other systems — `git grep` + LSP find-references for code repos, broken-link reports for wikis). If the vault has no such tool, skip the post-check and rely on the grep pass. The grep enumerates what-you-expect-to-find from your own memory of what changed; the structural query surfaces what's-actually-broken in the live link graph — catching cases enumeration missed (short-path wikilinks, display-text mismatches, historical/archive refs that rename-propagation mechanisms didn't reach). Text grep is sensitive to format/encoding/hidden-dir exclusions; the structural query isn't. Not a replacement for the grep pass — a cheap post-check for a specific failure mode.
   - **This step exists because:** WIP is one file. Status changes typically touch WIP, the project hub, area detail files, the tickler, This Week.md, and potentially other planning docs. Updating only WIP leaves stale state everywhere else. Without this step, the user has to manually ask for a full update pass after every status change.
   - Display result:
     ```
     ✓ Reference graph: No identifier values changed
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

      **Exception — trigger-contingent loops fall through to rule 4.** If the loop fires on a downstream trigger event rather than calendar time (e.g. "next time X runs, verify Y" or "test Z when next encountering W"), skip rule 3 and fall through to rule 4 (project file). Rule 3 assumes loops are actionable on a specific day; trigger-contingent loops aren't, and surfacing them on tomorrow's plan creates false urgency for work that shouldn't be date-bound at all. If the session has no Project link either, route directly to the Tickler with the date `today + 10 days` (computed via `date -d '+10 days' +"%Y-%m-%d"`) via write-tickler.sh — not rule 5, because rule 5's condition requires This Week.md to be stale, which isn't the trigger case here.

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
   - **Dedup check:** Before calling the backfill script, grep the session's "Files Updated" section for each file path. If already listed (from a prior park/audit backfill of the same session), skip it. This matters when a session is parked, audited, and re-merged — multiple backfill passes target the same session.
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

14b. **Export session transcript** (Full tier only):
   - **Quick tier:** Skip
   - Export today's verbatim session transcripts to the vault:
     ```bash
     python3 ~/.claude/scripts/export-session-transcripts.py "{VAULT}" --days 1
     ```
   - Output goes to `{VAULT}/06 Archive/Claude/Session Transcripts/YYYY-MM-DD.md`. Report the count briefly.
   - Each park re-exports (capturing all sessions up to this point in the day). `/goodnight` skips this step if a transcript already exists.
   - **Why at park time:** Ensures transcripts exist for `/goodnight` provenance processing (step 16) and as a backstop against session data loss.

14c. **Bump WIP "Last updated" timestamp** (Full tier only):
   - **Quick tier:** Skip
   - **Full tier: unconditional bump.** Use the Edit tool to replace the existing `Last updated: ...` line at the top of `01 Now/Works in Progress.md` with the current timestamp (e.g. `Last updated: YYYY-MM-DD HH:MM TZ`). No "did we modify planning files?" check — by Full-tier definition something was captured; the imperceptible cost of an over-bumped timestamp on a pure no-write session is preferable to the prediction-failure mode the old conditional produced.
   - **⛔ CHECKPOINT:** Display `✓ WIP timestamp bumped: YYYY-MM-DD HH:MM TZ`. Do not proceed to Step 15 without this line.

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
✓ At-risk work product: No at-risk work product to persist [OR "Persisted N item(s): [paths]"]
✓ Open loops documented: N items
✓ Continuation link added: [Original Session] (only if this session continues previous work)
✓ Project updated: [Project Name] (if applicable)
✓ Reference graph: N files updated for [identifier] (if any status changes traced)
  [OR "No status changes to trace" if none]
✓ Open loops routed: N items (This Week: X, Tickler: Y, Project: Z)
  [OR "✓ No open loops to route" if none]
✓ Transcript exported: N sessions → 06 Archive/Claude/Session Transcripts/YYYY-MM-DD.md
⚠️ Post-park audit recommended. `/audit the /park` to check cross-file consistency.

Parked. Pick up when ready.

To pickup later: `claude` then `/pickup`
```

**IMPORTANT:** The "Quality check" line is REQUIRED in all completion messages. If you cannot produce this line, you skipped Step 5 - go back and complete it before finishing the park.

16. **Audit recommendation** (Full tier only):
   - **Quick tier:** Skip
   - Always recommend a post-park audit. No trigger evaluation — the default is "audit." The park's quality gate (Step 5) and reference graph (Step 13) catch many issues, but edits made *during* the park itself (WIP updates, scratchpad cleanup, status propagation) don't get cross-reference checked. Experience shows post-park audits reliably catch sync gaps even after a clean quality gate.
   - Display:
     ```
     ⚠️ Post-park audit recommended. `/audit the /park` to check cross-file consistency.
     ```

17. **Skill monitor** (per shared rules §8):
   - Review the park execution just completed. Did you improvise any step not documented here? Did a documented step turn out unnecessary? Did you skip a step that should have a stronger gate?
   - If gaps found: propose specific edits to this skill file. Display proposed changes for user approval before editing.
   - If clean: `✓ Skill monitor: No gaps detected`

## Guidelines

- **Merge continuations, don't fork sessions:** If the current session is a trivial continuation of a recently parked session (same task, <5 minutes, just finishing a loose end), update that session's entry instead of creating a new one. Use `update-session-section.sh` for all section edits (never ad-hoc sed — multiline sed fails silently). This applies even if the session to update isn't the most recent — with parallel sessions, the relevant session may be the penultimate or earlier entry. Step 2 handles this procedurally.
- **Capture ALL sessions:** Use `/park` for every session, even quick tasks. The system auto-detects appropriate tier.
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
- **Four-part quality check:** Lint (syntax), Refactor (content quality), Verify (session accuracy, when updating), Proofread (language). All four categories checked for Full tier.
- **Narrative tone:** Write summaries in the user's voice - direct, technical, outcome-focused
- **Open loops clarity:** Each open loop should be specific enough to resume without re-reading the conversation
- **SSOT routing:** All open loops are routed to canonical locations at park time (This Week.md, Tickler, or project files). Session docs contain plain-text records only — they are never task trackers. This ensures /morning, /goodnight, and /pickup read from authoritative sources, not stale session copies.
- **No checkboxes in session logs:** Open loops in "Next Steps / Open Loops" use plain bullets (`- `), never checkboxes (`- [ ]`). Checkboxes belong in files where items are tracked and checked off (This Week.md, Tasks.md, project files). Session logs are write-once records — the format signals the function.
- **One-sentence pickup:** The "For next session" line should be immediately actionable (or "No follow-up needed" if complete)
- **Project context:** Full tier links projects; Quick tier skips
- **Project linking:** Follow the rules in `_shared-rules.md` Section 2.
- **File lists:** Only list files that were actually created/updated, not files that were just read. Step 14a backfills files modified during the park itself (steps 12-14) into the session log — don't try to predict these at step 9. For empty sections, write bare `None` on its own line (not `- None`, not `None (explanation)` — just `None`). The backfill script tolerates variations, but bare `None` is the canonical form.
- **Session naming:** Use descriptive names that will make sense weeks later ("Wezterm config fix" not "Terminal stuff")

## Shutdown Philosophy

The goal is a clean "shutdown complete" — explicit acknowledgement of open loops so the mind can truly rest, or so you can keep working without losing track of anything. Every incomplete task is captured in a trusted system, eliminating mental residue whether you're closing for the night or reclaiming context window space mid-session.

**For completed work:** Capture it anyway. The psychological closure ("this is done, documented, and archived") is valuable. Plus six months later you'll want to know "when did I make that decision?" The session archive answers that.
