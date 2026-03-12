---
name: weekly-hygiene
description: Vault structural maintenance - broken links, stale items, tier mismatches, hygiene report
---

# Weekly Hygiene - Vault Structural Maintenance

You are running a vault hygiene pass. This is purely mechanical/structural maintenance — no reflection, no planning, no alignment checks. It can run independently (mid-week cleanup) or as a precursor to `/weekly-review`.

## Instructions

0. **Resolve Vault Path**

   ```bash
   if [[ -z "${VAULT_PATH:-}" ]]; then
     echo "VAULT_PATH not set"; exit 1
   elif [[ ! -d "$VAULT_PATH" ]]; then
     echo "VAULT_PATH=$VAULT_PATH not found"; exit 1
   else
     echo "VAULT_PATH=$VAULT_PATH OK"
   fi
   ```

   If ERROR, abort. **Use the resolved path for all file operations below.**

1. **WIP Metrics & Pruning**

   **Gather:**
   - WIP line count: `wc -l "$VAULT_PATH/01 Now/Works in Progress.md"`
   - WIP session links: `grep -c "06 Archive/Claude/Session Logs" "$VAULT_PATH/01 Now/Works in Progress.md"`
   - Count session links per WIP section (Big Rocks vs Active vs Backlog) — heaviest sections are pruning candidates
   - WIP completed/strikethrough items: `grep -cE "\[x\]|~~.*~~" "$VAULT_PATH/01 Now/Works in Progress.md"`
   - For each Active/Big Rock project, check the **Last:** date — flag any 14+ days stale

   **Auto-fix:**
   - Trim session links to **3–5 most recent per project** (session history lives in the archive, not WIP)
   - Remove completed/strikethrough checklist items (the `[x] ~~done thing~~ ✅` pattern)
   - Remove resolved open decisions (strikethrough decisions that were answered)

   **Confirm with user:**
   - Flag Active/Big Rock projects whose **Last:** date is 14+ days stale — recommend demote or nudge

2. **WIP ↔ This Week Reconciliation**

   WIP is the canonical project dashboard; This Week is the tactical weekly view with higher-frequency updates. Items completed in This Week but not reflected in WIP create stale priors for every session that reads WIP.

   **Gather:**
   - Read `$VAULT_PATH/01 Now/Works in Progress.md` (already loaded from step 1)
   - Read `$VAULT_PATH/01 Now/This Week.md`
   - For each `[x]` or `✅` item in This Week, check whether the corresponding WIP entry still shows it as pending, in a `**Next:**` action, or as an unchecked `[ ]` item
   - For each `**Next:**` action in WIP, check whether any date reference has passed (e.g., "train task Sat 7 Mar" when today is 14 Mar)
   - For relative-time framing in WIP Next actions ("sleep on it", "tomorrow", "tonight"), flag if 2+ days have elapsed since the `**Last:**` date

   **Auto-fix:**
   - Update WIP entries to reflect completions confirmed in This Week (strike through items, update status lines, remove from Next actions)
   - Remove stale date parentheticals from Next actions
   - Update relative-time framing to direct action framing when 2+ days have passed (e.g., "Sleep on draft then send" → "Send draft (ready, slept on since [date])")

   **Cross-reference sweep:**
   - For each status change (battery disconnect, order placed, task completed), grep the vault for other files containing the stale value
   - Update cross-references in live files (project pages, area files, vehicle docs, etc.)
   - Leave Archive/, Session Logs/, and .stversions/ untouched — those are historical records or Syncthing versions

   **Report:** List each reconciliation applied (file, old → new), plus any cross-reference updates in other files.

3. **Projects Folder Audit**

   **Gather:**
   - List top-level: `ls "$VAULT_PATH/03 Projects/"`
   - List Cold/: `ls "$VAULT_PATH/03 Projects/Cold/" 2>/dev/null`
   - List Backlog/: `ls "$VAULT_PATH/03 Projects/Backlog/" 2>/dev/null`
   - Cross-reference with WIP sections — flag tier mismatches (e.g., Active project with file in Cold/, Backlog WIP entry with file in root)

   **Confirm with user:**
   - Move project files to match their WIP tier
   - Archive completed project files to `06 Archive/`

4. **Tickler Hygiene**

   **Gather:**
   - Read `$VAULT_PATH/01 Now/Tickler.md` (if it exists)
   - Flag items with dates that have passed (past-due and unactioned)

   **Confirm with user:**
   - For each past-due item: recommend complete, reschedule (with new date), or drop

5. **Working Memory Sweep**

   **Gather:**
   - Read `$VAULT_PATH/01 Now/Working memory.md`
   - Count items in each section (Fresh Captures, To Review, etc.)
   - Flag sections with 10+ unprocessed items
   - Identify any items that appear to be actionable tasks that should be in WIP or project files
   - Note items that have routing guidance but haven't been moved yet

6. **Scratchpad Sweep**

   **Gather:**
   - Find all Scratchpad.md files: `find "$VAULT_PATH" -name "Scratchpad.md" -type f -not -path "*/.stversions/*" -not -path "*/06 Archive/*"`
   - Flag items that have been sitting unprocessed (14+ days old or grown stale)

7. **CRM Name Scan** (if `$VAULT_PATH/07 System/CRM/` exists)

   - Read CRM index to get list of known names
   - Extract names from recent session files:
     ```bash
     find "$VAULT_PATH/06 Archive/Claude/Session Logs/" -name "*.md" -mtime -7 -exec \
       grep -oEh '[A-Z][a-z]+ [A-Z][a-z]+' {} + | sort | uniq -c | sort -rn | head -20
     ```
   - Flag names that appear 2+ times but aren't in CRM — **don't auto-add**, present candidates to user

8. **This Week.md Hygiene**

   **Auto-fix:**
   - Read `$VAULT_PATH/01 Now/This Week.md`
   - Purge completed backlog items: delete all `- [x]` lines from the Backlog section. `- [ ]` items are untouched.

   **Confirm with user:**
   - Audit trailing sections for staleness: scan sections after the last day section. Flag sections where >75% of content is resolved/done/strikethrough. Recommend deletion.
   - Update header metadata: check `**Status:**` and `**Location:**` lines against the most recent daily report. Flag if stale.

9. **Claude Memory Audit**

   Claude Code's auto-memory (`~/.claude/projects/*/memory/MEMORY.md` and any topic files alongside it) accumulates observations across sessions. Left unchecked, it drifts — stale entries, duplicated context already in the vault, vague impressions that degrade Claude's focus.

   **Gather:**
   - Locate the active memory directory: `ls ~/.claude/projects/*/memory/` — find the one matching the current working directory's path encoding
   - Read all `.md` files in that directory
   - Read `CLAUDE.md` from the vault root (needed for duplicate detection)
   - Count total entries/lines across all memory files

   **Flag for user review:**
   - **Stale entries:** Memories about completed projects, resolved decisions, or outdated state
   - **Vault duplicates:** Memories that restate what's already in CLAUDE.md or files loaded in earlier hygiene steps (WIP, Tickler, This Week, Working Memory) — the vault is the source of truth, not memory
   - **Vague impressions:** Entries that lack specificity ("user prefers X" without concrete mechanism) — these waste context window without adding value
   - **Contradictions:** Entries that conflict with current vault content or CLAUDE.md

   **Confirm with user:**
   - Present each flagged entry with recommendation (delete / update / keep)
   - Don't auto-delete — memory entries may contain context the user values that isn't obvious from vault content alone

10. **Claude Plan File Cleanup**

   Claude Code generates ephemeral plan files in `~/.claude/plans/`. Work product should be migrated to the vault by `/park` or `/goodnight` before session end — old plan files are structural clutter. Auto-fix is appropriate here despite the general "deletions require confirmation" guideline — these are ephemeral Claude internals, not vault content.

   **Gather:**
   ```bash
   # Total before cleanup
   find ~/.claude/plans/ -name "*.md" -type f 2>/dev/null | wc -l
   # Stale (7+ days old)
   find ~/.claude/plans/ -name "*.md" -type f -mtime +7 2>/dev/null | wc -l
   find ~/.claude/plans/ -name "*.md" -type f -mtime +7 -exec ls -la {} + 2>/dev/null
   ```

   **Auto-fix:**
   - Delete plan files older than 7 days
   ```bash
   find ~/.claude/plans/ -name "*.md" -type f -mtime +7 -delete 2>/dev/null
   ```
   - Remaining count = total minus deleted

11. **Vault Consistency Checks**

   If the Obsidian CLI is available and Obsidian is running (`obsidian version 2>/dev/null` returns output), use it — it queries Obsidian's live index and is orders of magnitude faster than bash pipelines.

   **Unresolved (broken) links:**
   ```bash
   # CLI (preferred): queries Obsidian's index directly
   obsidian unresolved counts format=tsv 2>/dev/null
   ```
   If CLI unavailable, fall back to grep:
   ```bash
   grep -roh '\[\[.*\]\]' "$VAULT_PATH" --include="*.md" \
     -not -path "*/.stversions/*" -not -path "*/06 Archive/*" \
     | sed 's/\[\[//;s/\]\]//' | sed 's/|.*//' | sed 's/#.*//' \
     | sort -u
   ```
   For each link target, check whether a matching .md file exists in the vault.

   **Orphaned files** (no incoming links):
   ```bash
   # CLI (preferred)
   obsidian orphans 2>/dev/null | grep -E "^(03 Projects|04 Areas)/"
   ```
   If CLI unavailable, find files in `03 Projects/` and `04 Areas/` not linked from any other .md file (excluding Archives, .stversions, system files).

   **Dead-end files** (no outgoing links — CLI only, skip if unavailable):
   ```bash
   obsidian deadends 2>/dev/null | grep -E "^(03 Projects|04 Areas)/" | head -20
   ```
   Files with content but no links to anything else — may need connecting to the graph.

   **Vault structural metrics** (CLI only, report in hygiene output):
   ```bash
   obsidian tasks todo total 2>/dev/null      # open tasks vault-wide
   obsidian tags counts sort=count 2>/dev/null | head -10  # top tags
   obsidian orphans total 2>/dev/null          # total orphan count
   obsidian unresolved total 2>/dev/null       # total broken link count
   obsidian deadends total 2>/dev/null         # total dead-end count
   ```

   **Terminology consistency** (if `~/.claude/commands/_terminology-checks.md` exists):
   Read the file for domain-specific ambiguous terms. Scan recently modified vault files (last 7 days) for each pattern. Report instances for user review — don't auto-fix.

12. **Write Hygiene Report**

   Determine the current ISO week: `date +%G-W%V` (e.g., `2026-W10`).
   Write all findings to `$VAULT_PATH/06 Archive/Claude/Hygiene Reports/YYYY-Wnn.md`:

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
   - Stale entries: [list or "none"]
   - Vault duplicates: [list or "none"]
   - Vague/low-value entries: [list or "none"]
   - Contradictions: [list or "none"]

   ## Claude Plan Files
   - Stale files deleted (7+ days old): N
   - Remaining files: M

   ## Vault Consistency
   - Unresolved (broken) links: N total — [list top 10 or "none"]
   - Orphaned files (03 Projects/ & 04 Areas/): [list or "none"]
   - Dead-end files (03 Projects/ & 04 Areas/): [list top 10 or "none"]
   - Terminology flags: [list or "none"] (if _terminology-checks.md exists)

   ## Vault Structural Metrics (CLI)
   - Open tasks: N
   - Orphan count (vault-wide): N
   - Unresolved link count: N
   - Dead-end count: N
   - Top tags: [top 5 with counts]

   ## Actions Taken (Auto-fix)
   - [List all automatic fixes applied]

   ## Actions Pending (User Decision)
   - [ ] [Each item requiring user confirmation]
   ```

13. **Display confirmation:**

    ```
    ✓ Hygiene report saved to: 06 Archive/Claude/Hygiene Reports/YYYY-Wnn.md
    ✓ Auto-fixes applied: N (session link trimming, completed item removal, backlog purge, plan file cleanup)
    ✓ Items needing user decision: M

    Vault hygiene complete. Run /weekly-review to incorporate findings into your weekly reflection.
    ```

## Guidelines

- **Mechanical, not reflective.** This command fixes structural issues. `/weekly-review` handles patterns, alignment, and planning.
- **Auto-fix only safe operations.** Pruning session links, removing completed items, and purging done backlog are safe. File moves, deletions, tickler actions, and stale project demotion require user confirmation.
- **Idempotent.** Running twice should produce the same result. The report overwrites each run.
- **Report is consumable.** `/weekly-review` reads the hygiene report if it exists, so findings flow into the weekly review without re-gathering.

## Integration

- **Standalone:** Run mid-week for a quick cleanup
- **Pre-review:** Run before `/weekly-review` — the review will consume the hygiene report
- **Weekly-review fallback:** If `/weekly-review` finds no hygiene report, it suggests running `/weekly-hygiene` first

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
