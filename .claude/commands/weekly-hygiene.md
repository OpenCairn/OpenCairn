---
name: weekly-hygiene
description: Vault structural maintenance - broken links, stale items, tier mismatches, hygiene report
---

# Weekly Hygiene - Vault Structural Maintenance

You are running a vault hygiene pass. This is purely mechanical/structural maintenance — no reflexion, no planning, no alignment checks. It can run independently (mid-week cleanup) or as a precursor to `/weekly-review`.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **WIP Metrics & Pruning**

   **Gather:**
   - WIP line count: `wc -l "{VAULT}/01 Now/Works in Progress.md"`
   - WIP session links: `grep -c "06 Archive/Claude/Session Logs" "{VAULT}/01 Now/Works in Progress.md"`
   - Count session links per WIP section (Big Rocks vs Active vs Backlog) — heaviest sections are pruning candidates
   - WIP completed/strikethrough items: `grep -cE "\[x\]|~~.*~~" "{VAULT}/01 Now/Works in Progress.md"`
   - For each Active/Big Rock project, check the **Last:** date — flag any 14+ days stale
   - Per-entry line count (excluding session link lines starting with →): flag entries exceeding 30 lines

   **Auto-fix:**
   - Trim session log links to **2 most recent per entry** — only lines matching `→ [[06 Archive/Claude/Session Logs/`. **Preserve all other reference links** (`→ [[03 Projects/`, `→ [[04 Areas/`, etc.) — these are navigation pointers, not session history. Session history lives in the archive and project hub pages, not WIP.
   - Remove completed/strikethrough checklist items (the `[x] ~~done thing~~ ✅` pattern)
   - Remove resolved open decisions (strikethrough decisions that were answered)
   - Collapse resolved inline narratives: when a paragraph or sub-section contains 3+ items all marked ✅/resolved/completed, replace with a single summary line referencing the linked project/area file
   - Per-entry line budget: when a single WIP entry exceeds 30 lines (excluding session links), collapse verbose sub-sections to summary + link. Prioritise collapsing: duplicated detail (confirmation numbers, prices, addresses already in linked files), resolved narratives, sub-topics that have their own WIP entry
   - Detect sub-entry sprawl: when a WIP entry contains dedicated sub-topic headings, per-sub-topic session links, or content that duplicates a separate WIP entry, collapse to a cross-reference

   **Confirm with user:**
   - Flag Active/Big Rock projects whose **Last:** date is 14+ days stale — recommend demote or nudge

   **If not resolved in-session:** For each stale entry the user doesn't address, append `⚠ Hygiene Wnn: Nd stale — demote?` after the entry's `**Status:**` line in WIP. Note in report as `→ routed to WIP entry`.

2. **WIP ↔ This Week Reconciliation**

   WIP is the canonical project dashboard; This Week is the tactical weekly view with higher-frequency updates. Items completed in This Week but not reflected in WIP create stale priors for every session that reads WIP.

   **Gather:**
   - Read `{VAULT}/01 Now/Works in Progress.md` (already loaded from step 1)
   - Read `{VAULT}/01 Now/This Week.md`
   - For each `[x]` or `✅` item in This Week, check whether the corresponding WIP entry still shows it as pending or as an unchecked `[ ]` item
   - WIP `**Next:**` fields: flag any that contain **multiple actions** (queue) — these always need migration. Also flag entries with task content where a project/area doc exists — should be a pointer instead. A single next action is acceptable for lightweight entries that have no project doc.

   **Auto-fix:**
   - Update WIP entries to reflect completions confirmed in This Week (strike through items, update status lines)
   - For Next fields with queued actions: migrate to the project doc, replace with a pointer
   - For Next fields with task content where a project doc exists: replace with a pointer (`→ [[03 Projects/...]]`)

   **Cross-reference sweep:**
   - For each status change (battery disconnect, order placed, task completed), grep the vault for other files containing the stale value
   - Update cross-references in live files (project pages, area files, vehicle docs, etc.)
   - Leave Archive/, Session Logs/, and .stversions/ untouched — those are historical records or Syncthing versions

   **Report:** List each reconciliation applied (file, old → new), plus any cross-reference updates in other files.

3. **Projects Folder Audit**

   **Gather:**
   - List top-level: `ls "{VAULT}/03 Projects/"`
   - List Cold/: `ls "{VAULT}/03 Projects/Cold/" 2>/dev/null`
   - List Backlog/: `ls "{VAULT}/03 Projects/Backlog/" 2>/dev/null`
   - Cross-reference with WIP sections — flag tier mismatches (e.g., Active project with file in Cold/, Backlog WIP entry with file in root)

   **Confirm with user:**
   - Move project files to match their WIP tier
   - Archive completed project files to `06 Archive/`

   **If not resolved in-session:** For each tier mismatch the user doesn't address, append `⚠ Hygiene Wnn: file in wrong tier — move to Cold/?` to the WIP entry (if one exists) or add to Tasks.md with a hygiene report back-reference (if no WIP entry).

   **After any file moves:** Grep for the old path (`[[03 Projects/Old Name]]`) in live vault files (exclude `06 Archive/` and `.stversions/`). Fix broken wikilinks in non-archive files. Leave archive/session log references as historical records.

4. **Tickler Hygiene**

   **Gather:**
   - Read `{VAULT}/01 Now/Tickler.md` (if it exists)
   - Flag items with dates that have passed (past-due and unactioned)

   **Resolve in-session:**
   - For each past-due item: present and ask user to choose — complete (remove from Tickler), reschedule (user provides the new date), or drop (remove). Execute the chosen action during the sweep. No default rescheduling — the user must provide a real date.
   - **If user disengages:** route unresolved past-due items to Tasks.md with a hygiene report back-reference.

5. **Working Memory Sweep**

   **Gather:**
   - Read `{VAULT}/01 Now/Working memory.md`
   - Count items in each section (Fresh Captures, To Review, etc.)
   - Flag sections with 10+ unprocessed items
   - Identify any items that appear to be actionable tasks that should be in WIP or project files
   - Note items that have routing guidance but haven't been moved yet

   **If not resolved in-session:** For oversized sections (10+ items), add `⚠ Hygiene Wnn: N items, 10+ unprocessed — triage needed` at the top of that section in Working Memory.

6. **Scratchpad Sweep**

   **Gather:**
   - Find all Scratchpad.md files: `find "{VAULT}" -name "Scratchpad.md" -type f -not -path "*/.stversions/*" -not -path "*/06 Archive/*"`
   - For each non-empty scratchpad, note line count and days since last modified

   **Resolve in-session:**
   - Present all non-empty scratchpads to user and offer to triage during the sweep.
   - **If user declines:** add `⚠ Hygiene Wnn: NL, Nd since last edit — triage needed` at the top of each non-empty scratchpad file.

7. **CRM Name Scan** (if `{VAULT}/07 System/CRM/` exists)

   - Read CRM index to get list of known names
   - Extract names from recent session files:
     ```bash
     find "{VAULT}/06 Archive/Claude/Session Logs/" -name "*.md" -mtime -7 -exec \
       grep -oEh '[A-Z][a-z]+ [A-Z][a-z]+' {} + | sort | uniq -c | sort -rn | head -20
     ```
   - Flag names that appear 2+ times but aren't in CRM

   **Resolve in-session:**
   - Present candidates to user. For confirmed names, create CRM entries in the appropriate range file (A-F, G-L, M-R, S-Z) during the sweep.
   - **If user disengages:** route unresolved candidates to Tasks.md with a hygiene report back-reference.

8. **This Week.md Hygiene**

   **Auto-fix:**
   - Read `{VAULT}/01 Now/This Week.md`
   - Purge completed items: delete all `- [x]` lines from day sections in This Week.md and from Tasks.md. `- [ ]` items are untouched.

   **Confirm with user:**
   - Audit trailing sections for staleness: scan sections after the last day section. Flag sections where >75% of content is resolved/done/strikethrough. Recommend deletion.
   - Update header metadata: check `**Status:**` and `**Location:**` lines against the most recent daily report. Flag if stale.

9. **Claude Memory Audit & Migration**

   Claude Code's auto-memory (`~/.claude/projects/*/memory/MEMORY.md` and any topic files alongside it) accumulates observations across sessions. The vault is the canonical home for persistent knowledge — memory should be a temporary landing zone, not a permanent silo. Left unchecked, valuable lessons get trapped in a Claude-internal folder invisible to Obsidian search, backlinks, and the user's normal workflows.

   **Gather:**
   - Locate the active memory directory: `ls ~/.claude/projects/*/memory/` — find the one matching the current working directory's path encoding
   - Read all `.md` files in that directory
   - Read `CLAUDE.md` from the vault root (needed for duplicate detection)
   - Count total entries/lines across all memory files

   **For each memory entry, classify:**
   - **Migrate to vault:** The memory contains a lesson, workflow insight, or reference that belongs near the relevant vault content (e.g., a workflow correction belongs near the workflow doc, a project lesson belongs in the project file). Propose the specific vault destination — verify the target file exists before proposing (if it's been moved/deleted, find the current location or flag for user).
   - **Keep in memory:** The memory is about Claude's behaviour but too granular or context-dependent for CLAUDE.md (e.g., "when user says X, they mean Y in this repo"). If it's a general behaviour rule, it belongs in CLAUDE.md's "Working With Me" section, not memory. Genuine keeps should be rare.
   - **Delete:** Stale (completed project, resolved decision), duplicated in vault/CLAUDE.md, vague/unactionable, or contradicts current vault content.

   **Resolve in-session:**
   - Present each entry with its classification and recommended action
   - For migrations: show the proposed vault destination and how the content would be integrated (appended to existing doc, new section, etc.)
   - Execute confirmed deletions and migrations during the sweep. Delete memory files, update MEMORY.md index.
   - **If user disengages:** route unresolved entries to Tasks.md with a hygiene report back-reference.

10. **Claude Internal File Cleanup**

   Claude Code generates ephemeral files across several internal directories. These accumulate indefinitely with no built-in retention. Work product in plans should be migrated to the vault by `/park` or `/goodnight` before session end. Other directories (`debug/`, `paste-cache/`, `shell-snapshots/`, `telemetry/`) contain session logs, clipboard caches, environment snapshots, and failed telemetry events — none are read back after the session that created them.

   Auto-fix is appropriate here despite the general "deletions require confirmation" guideline — these are ephemeral Claude internals, not vault content.

   **Gather:**
   ```bash
   # Count total and stale (7+ days) for each directory
   for dir in plans debug paste-cache shell-snapshots telemetry; do
     total=$(find ~/.claude/$dir/ -type f 2>/dev/null | wc -l)
     stale=$(find ~/.claude/$dir/ -type f -mtime +7 2>/dev/null | wc -l)
     echo "$dir: $total total, $stale stale (7+ days)"
   done
   ```

   **Auto-fix:**
   ```bash
   for dir in plans debug paste-cache shell-snapshots telemetry; do
     find ~/.claude/$dir/ -type f -mtime +7 -delete 2>/dev/null
   done
   ```
   Report per-directory counts (deleted and remaining).

11. **Session Transcript Export**

   Backstop for `/park` step 14b and `/goodnight` step 16, which export daily. This catches any days missed (skipped park/goodnight, crashed session, etc.). Claude Code auto-deletes JSONL session files after 30 days — this ensures nothing slips through.

   **Auto-fix:**
   ```bash
   python3 ~/.claude/scripts/export-session-transcripts.py "{VAULT}" --days 7
   ```

   The script:
   - Finds all JSONL files modified in the last 7 days in `~/.claude/projects/`
   - Extracts user messages, assistant text blocks, and Write/Edit/Agent tool inputs
   - Writes one file per day to `{VAULT}/06 Archive/Claude/Session Transcripts/YYYY-MM-DD.md`
   - Overwrites existing files for the same date (idempotent)

   Report the script's stdout summary in the hygiene report.

12. **Vault Consistency Checks**

   If the Obsidian CLI is available and Obsidian is running (`obsidian version 2>/dev/null` returns output), use it — it queries Obsidian's live index and is orders of magnitude faster than bash pipelines.

   **Excludes filter:** If `{VAULT}/.claude/hygiene-excludes` exists, pipe all CLI output through `grep -vf` to remove noise from large embedded doc sets (darktable, Hugo themes, etc.). One grep pattern per line, `#` comments. Example file:
   ```
   # Patterns to exclude from vault consistency checks
   darktable
   hugo-theme
   ```
   Define the filter in each Bash call that uses it (shell state doesn't persist between calls):
   ```bash
   HYGIENE_EXCLUDES="{VAULT}/.claude/hygiene-excludes"
   if [ -f "$HYGIENE_EXCLUDES" ]; then
     filter() { grep -vf <(grep -v '^#' "$HYGIENE_EXCLUDES" | grep -v '^$') ; }
   else
     filter() { cat ; }
   fi
   ```

   **Unresolved (broken) links:**
   ```bash
   # CLI (preferred): queries Obsidian's index directly
   obsidian unresolved counts format=tsv 2>/dev/null | filter
   ```
   If CLI unavailable, fall back to grep (also apply `filter` here):
   ```bash
   grep -roh '\[\[.*\]\]' "{VAULT}" --include="*.md" \
     -not -path "*/.stversions/*" -not -path "*/06 Archive/*" \
     | sed 's/\[\[//;s/\]\]//' | sed 's/|.*//' | sed 's/#.*//' \
     | sort -u | filter
   ```
   For each link target, check whether a matching .md file exists in the vault.

   **Orphaned files** (no incoming links):
   ```bash
   # CLI (preferred)
   obsidian orphans 2>/dev/null | filter | grep -E "^(03 Projects|04 Areas)/"
   ```
   If CLI unavailable, find files in `03 Projects/` and `04 Areas/` not linked from any other .md file (excluding Archives, .stversions, system files).

   **Dead-end files** (no outgoing links — CLI only, skip if unavailable):
   ```bash
   obsidian deadends 2>/dev/null | filter | grep -E "^(03 Projects|04 Areas)/" | head -20
   ```
   Files with content but no links to anything else — may need connecting to the graph.

   **Vault structural metrics** (CLI only, report in hygiene output):

   For totals, the CLI doesn't support exclude filters natively. Pipe through `wc -l` after filtering to get accurate counts:
   ```bash
   obsidian tasks todo total 2>/dev/null      # open tasks vault-wide (no exclude needed)
   obsidian tags counts sort=count 2>/dev/null | head -10  # top tags
   obsidian orphans 2>/dev/null | filter | wc -l           # filtered orphan count
   obsidian unresolved 2>/dev/null | filter | wc -l        # filtered broken link count
   obsidian deadends 2>/dev/null | filter | wc -l          # filtered dead-end count
   ```

   **Obsidian Sync ghost detection** (if `~/repos/scripts/obsidian-ghost-check.sh` exists):
   ```bash
   if [ -x ~/repos/scripts/obsidian-ghost-check.sh ]; then
     bash ~/repos/scripts/obsidian-ghost-check.sh --since "8 days ago" "{VAULT}"
   fi
   ```
   If ghosts or conflict files are found, report them. In delete mode (`-d`), duplicates and conflict files are auto-removed; orphans are listed for user review. This catches files silently re-uploaded by a reconnecting phone via Obsidian Sync (known bug — Sync doesn't propagate deletions to offline devices). Skip silently if the script isn't installed.

   **Terminology consistency** (if `~/.claude/commands/_terminology-checks.md` exists):
   Read the file for domain-specific ambiguous terms. Scan recently modified vault files (last 7 days) for each pattern. For each match, write an HTML comment near the ambiguous term in the flagged file: `<!-- ⚠ Hygiene Wnn: ambiguous term "[term]" — disambiguate -->`. This surfaces when the user next edits that file. Report instances in the hygiene report.

13. **Context File Staleness Detection**

   Context files (`{VAULT}/07 System/Context - *.md`) shape every session's priors. They are event-driven, not time-driven — some are valid for years without edits, others contain temporal claims that expire. This step scans for temporal content that may have gone stale, rather than naively flagging files by modification date.

   **Gather:**
   - List all context files and their last-modified dates:
     ```bash
     find "{VAULT}/07 System/" -name "Context - *.md" -type f -exec stat -c '%Y %n' {} +
     ```
   - For each file found above, scan for temporal markers in three categories. Grep extracts candidate lines; **Claude classifies contextually** (bash can't distinguish historical facts from stale future claims).

     **Category A — Explicit dates:**
     ```bash
     grep -nE "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+20[2-3][0-9]|20[2-3][0-9]-(0[1-9]|1[0-2])" "$FILE"
     ```
     Claude flags lines where the date is past AND the framing is forward-looking ("upcoming", "planned", "starting", "will"). Historical references ("Started September 2025") are not flagged.

     **Category B — Relative-time markers:**
     ```bash
     grep -niE "\b(currently|right now|at the moment|these days|lately|recently|about to|planning to|transitioning|in progress|waiting for|not yet|haven't yet|still [a-z]+ing|upcoming|soon)\b" "$FILE"
     ```
     Flag all matches every week as a low-priority verification checklist — no file-age threshold. Present as: "These claims exist in your context files — still true?"

     **Category C — Dates approaching expiry:**
     Reuse Category A's output. Filter for dates within 30 days of today — early warning for content about to need updating.

   - Skip files with zero temporal markers across all categories (inherently stable).

   **Classify each flagged file:**
   - **Expired:** Category A markers where the date is past and framing is forward-looking.
   - **Verify:** Category B markers — quick confirmation checklist.
   - **Approaching expiry:** Category A/C markers with dates in the next 30 days.

   **Resolve in-session:**
   - Present each flagged file with its classification and the specific lines triggering the flag
   - For Expired: ask user for the updated text, then edit the context file. Never rewrite, rephrase, or infer updates autonomously — only write what the user provides.
   - For Verify: present as a quick scan checklist — "still true?" For each claim the user confirms is stale, ask for replacement text and edit. For claims still true, no action.
   - For Approaching expiry: ask user — update now (provide text) or add to Tickler under the expiry date? If Tickler: `- [ ] Update Context - [Name].md: [specific stale claim]`
   - **If user disengages:** route unresolved items to Tasks.md with a hygiene report back-reference.
   - **Guardrail:** Edit context files only with user-provided replacement text. These are high-value prose documents — never rewrite, rephrase, or infer updates autonomously.

14. **Provenance: Process Stale Flags & Verify Hashes**

   This step absorbs the former `/verify-provenance` skill. Two jobs: catch missed flags, then verify existing entries.

   **14a. Process stale provenance flags:**
   ```bash
   ls "{VAULT}/07 System/Provenance/pending/"*.md 2>/dev/null
   ```
   If any flag files exist (these are sessions where `/provenance` was invoked but `/goodnight` didn't process them — missed goodnight, crashed session, etc.):
   - Read each flag to get the tag and work product list
   - Hash any work products not already hashed
   - Hash the session transcript for that date (if exported): `{VAULT}/06 Archive/Claude/Session Transcripts/YYYY-MM-DD.md`
   - Hash the session log for that date: `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`
   - OTS stamp all newly hashed files
   - Append entries to `07 System/AI Provenance Log.md`
   - Delete the processed flag file

   **14b. Verify existing provenance entries:**

   Read `{VAULT}/07 System/AI Provenance Log.md`. For each entry:

   **Resolve file path** from the File column:
   - `*-transcript.md` → `{VAULT}/06 Archive/Claude/Session Transcripts/YYYY-MM-DD.md`
   - `YYYY-MM-DD.md` → `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`
   - Paths containing `/` → `{VAULT}/relative/path`
   - Other (legacy) → try Session Logs, then vault root

   **Re-hash and compare:**
   ```bash
   CURRENT_HASH=$(sha256sum "$RESOLVED_FILE" | awk '{print $1}')
   CURRENT_SHORT="${CURRENT_HASH:0:16}"
   ```
   Compare against logged hash. Record as MATCH, MISMATCH, or MISSING.

   **Upgrade OTS proofs:**
   For entries with OTS status "pending", try `ots upgrade` on the corresponding `.ots` file in `07 System/Provenance/`. If upgrade succeeds, update the provenance log entry to "confirmed".

   **Verify OTS proofs:**
   For entries with `.ots` files, run `ots verify`. Record as CONFIRMED, PENDING, FAILED, or MISSING.

   **Note:** Work product mismatches are informational, not failures — living documents evolve. Transcript mismatches would be suspicious. Session log mismatches are expected for entries created before the flag-based architecture (legacy mid-day hashes).

15. **Write Hygiene Report**

   Determine the current ISO week: `date +%G-W%V` (e.g., `2026-W10`).
   Write all findings to `{VAULT}/06 Archive/Claude/Hygiene Reports/YYYY-Wnn.md`:

   ```markdown
   # Vault Hygiene Report

   **Generated:** YYYY-MM-DD HH:MM
   **Status:** [Clean / N issues found]

   ## WIP Health
   - Line count: N lines (target: <300)
   - Session links: N total (heaviest: [Project] with M links)
   - Completed items removed: N
   - Session links trimmed: N
   - Stale Active projects (Last: 14+ days ago): [list or "none"]
   - Entries exceeding 30-line budget: [list or "none"]
   - Narratives collapsed: N

   ## WIP ↔ This Week Reconciliation
   - Stale WIP items updated: N
   - Cross-reference updates: N files
   - [List each: file, old → new]

   ## Projects Folder
   - Tier mismatches: [list or "none"]
   - Recommended moves: [list or "none"]

   ## Tickler
   - Past-due items: N
   - [List each with original date and recommendation]

   ## Working Memory
   - Total items: N across M sections
   - Oversized sections (10+): [list or "none"]
   - Items needing routing: [list or "none"]

   ## Scratchpads
   - Files with unprocessed items: [list or "none"]

   ## CRM Candidates
   - New names (not in CRM, 2+ mentions): [list or "none"]

   ## This Week.md
   - Completed backlog items purged: N
   - Stale trailing sections: [list or "none"]
   - Header metadata: [current / flagged]

   ## Claude Memory
   - Total entries/lines: N across M files
   - Migrate to vault: [list with destination, or "none"]
   - Keep in memory: [list with reason, or "none"]
   - Delete: [list with reason, or "none"]
   - Migrated this sweep: [list of entry → vault path, or "none"]

   ## Claude Internal Files
   - Plans: N stale deleted, M remaining
   - Debug logs: N stale deleted, M remaining
   - Paste cache: N stale deleted, M remaining
   - Shell snapshots: N stale deleted, M remaining
   - Telemetry: N stale deleted, M remaining

   ## Session Transcript Export
   - Sessions exported: N
   - Sessions skipped (empty): N
   - Transcript files written: N
   - [Per-date breakdown]

   ## Vault Consistency
   - Unresolved (broken) links: N total — [list top 10 or "none"]
   - Orphaned files (03 Projects/ & 04 Areas/): [list or "none"]
   - Dead-end files (03 Projects/ & 04 Areas/): [list top 10 or "none"]
   - Terminology flags: [list or "none"] (if _terminology-checks.md exists)

   ## Obsidian Sync Ghost Check
   - Ghosts found: N (N duplicates, N orphans)
   - Conflict files: N
   - Auto-deleted: N
   - Orphans for review: [list or "none"]

   ## Vault Structural Metrics (CLI)
   - Open tasks: N
   - Orphan count: N [filtered / unfiltered]
   - Unresolved link count: N [filtered / unfiltered]
   - Dead-end count: N [filtered / unfiltered]
   - Top tags: [top 5 with counts]
   - Excludes active: [yes — N patterns from hygiene-excludes / no excludes file]

   ## Provenance
   - Stale flags processed: N [OR "none"]
   - Entries verified: N
   - Hash matches: N
   - Hash mismatches: N (files edited after logging)
   - Missing files: N
   - OTS confirmed: N
   - OTS pending: N
   - OTS upgraded this sweep: N

   ## Context File Staleness
   - Files scanned: N
   - Inherently stable (no temporal markers): N
   - Expired (past-date forward-looking claims): [list with file, line, and marker, or "none"]
   - Verify (relative-time claims): [list with file, line, and marker, or "none"]
   - Approaching expiry (dates within 30 days): [list with file, line, and date, or "none"]

   ## Actions Taken (Auto-fix)
   - [List all automatic fixes applied]

   ## Resolved In-Session
   - [List items resolved during the sweep: CRM additions, memory cleanup, context updates, tickler actions, scratchpad triage]

   ## Actions Routed
   - [For each routed item: description → destination file]
   - Routed to WIP entries: N
   - Routed to SSOT files (Working Memory, scratchpads, terminology): N
   - Routed to Tasks.md (fallback): N
   - Routed to Tickler: N
   ```

16. **Route unresolved findings**

    For each finding not resolved during the sweep:

    - **Tier 3 items (project-level judgement):** Write the finding to the destination file per the routing rules in each step above. Format: `⚠ Hygiene Wnn: [description]` — placed after the entry's `**Status:**` line (for WIP entries), at the top of the relevant section (for Working Memory), or at the top of the file (for scratchpads).
    - **Tier 2 items the user declined to engage with:** Write to Tasks.md: `- [ ] [Description] → [[06 Archive/Claude/Hygiene Reports/YYYY-Wnn|Hygiene Wnn]]`
    - Update the hygiene report's "Actions Routed" section to note where each item was sent.
    - **Idempotent:** Before writing, check if a `⚠ Hygiene Wnn:` marker for the same week number already exists in the target file. If so, replace it rather than duplicating.
    - **Cleanup lifecycle:** When a user resolves a hygiene-flagged item in any future session, strike through the marker: `~~⚠ Hygiene Wnn: ...~~`. The next `/weekly-hygiene` run auto-removes strikethrough content (existing WIP pruning step).

17. **Display confirmation:**

    ```
    ✓ Hygiene report saved to: 06 Archive/Claude/Hygiene Reports/YYYY-Wnn.md
    ✓ Auto-fixes applied: N (session link trimming, completed item removal, backlog purge, internal file cleanup)
    ✓ Resolved in-session: N (CRM, memory, context, tickler, scratchpad)
    ✓ Routed to SSOT: M (N to WIP entries, M to files, P to Tasks.md)

    Vault hygiene complete. Run /weekly-review to incorporate findings into your weekly reflection.
    ```

## Guidelines

- **Mechanical, not reflective.** This command fixes structural issues and flags potential staleness. `/weekly-review` handles patterns, alignment, and planning. Context staleness detection (step 13) straddles this boundary — the gather is mechanical (grep), the classification requires judgement, but the output is a checklist to confirm, not a reflexion to act on.
- **Three tiers of findings.** (1) Auto-fix: safe mechanical changes. (2) Resolve in-session: CRM additions, memory cleanup, context file updates, Tickler past-due, scratchpad triage — present to user and execute during the sweep. (3) Route to SSOT: project-level judgement calls (stale entries, tier mismatches, Working Memory overflow) get `⚠ Hygiene Wnn:` markers written to the relevant file. If the user declines to engage with tier-2 items, route to Tasks.md as fallback — never drop findings silently.
- **Hygiene markers clean up automatically.** When resolved, markers are struck through (`~~⚠ Hygiene Wnn: ...~~`). The next hygiene run auto-removes strikethrough content.
- **Idempotent.** Running twice should produce the same result. The report overwrites each run. `⚠ Hygiene Wnn:` markers for the same week are replaced, not duplicated.
- **Report is consumable.** `/weekly-review` reads the hygiene report if it exists, so findings flow into the weekly review without re-gathering.

## Integration

- **Standalone:** Run mid-week for a quick cleanup
- **Pre-review:** Run before `/weekly-review` — the review will consume the hygiene report
- **Weekly-review fallback:** If `/weekly-review` finds no hygiene report, it suggests running `/weekly-hygiene` first
