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

2. **Projects Folder Audit**

   **Gather:**
   - List top-level: `ls "$VAULT_PATH/03 Projects/"`
   - List Cold/: `ls "$VAULT_PATH/03 Projects/Cold/" 2>/dev/null`
   - List Backlog/: `ls "$VAULT_PATH/03 Projects/Backlog/" 2>/dev/null`
   - Cross-reference with WIP sections — flag tier mismatches (e.g., Active project with file in Cold/, Backlog WIP entry with file in root)

   **Confirm with user:**
   - Move project files to match their WIP tier
   - Archive completed project files to `06 Archive/`

3. **Tickler Hygiene**

   **Gather:**
   - Read `$VAULT_PATH/01 Now/Tickler.md` (if it exists)
   - Flag items with dates that have passed (past-due and unactioned)

   **Confirm with user:**
   - For each past-due item: recommend complete, reschedule (with new date), or drop

4. **Working Memory Sweep**

   **Gather:**
   - Read `$VAULT_PATH/01 Now/Working memory.md`
   - Count items in each section (Fresh Captures, To Review, etc.)
   - Flag sections with 10+ unprocessed items
   - Identify any items that appear to be actionable tasks that should be in WIP or project files
   - Note items that have routing guidance but haven't been moved yet

5. **Scratchpad Sweep**

   **Gather:**
   - Find all Scratchpad.md files: `find "$VAULT_PATH" -name "Scratchpad.md" -type f -not -path "*/.stversions/*" -not -path "*/06 Archive/*"`
   - Flag items that have been sitting unprocessed (14+ days old or grown stale)

6. **CRM Name Scan** (if `$VAULT_PATH/07 System/CRM/` exists)

   - Read CRM index to get list of known names
   - Extract names from recent session files:
     ```bash
     find "$VAULT_PATH/06 Archive/Claude/Session Logs/" -name "*.md" -mtime -7 -exec \
       grep -oEh '[A-Z][a-z]+ [A-Z][a-z]+' {} + | sort | uniq -c | sort -rn | head -20
     ```
   - Flag names that appear 2+ times but aren't in CRM — **don't auto-add**, present candidates to user

7. **This Week.md Hygiene**

   **Auto-fix:**
   - Read `$VAULT_PATH/01 Now/This Week.md`
   - Purge completed backlog items: delete all `- [x]` lines from the Backlog section. `- [ ]` items are untouched.

   **Confirm with user:**
   - Audit trailing sections for staleness: scan sections after the last day section. Flag sections where >75% of content is resolved/done/strikethrough. Recommend deletion.
   - Update header metadata: check `**Status:**` and `**Location:**` lines against the most recent daily report. Flag if stale.

8. **Claude Memory Audit**

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

9. **Vault Consistency Checks**

   **Broken wikilinks:**
   ```bash
   grep -roh '\[\[.*\]\]' "$VAULT_PATH" --include="*.md" \
     -not -path "*/.stversions/*" -not -path "*/06 Archive/*" \
     | sed 's/\[\[//;s/\]\]//' | sed 's/|.*//' | sed 's/#.*//' \
     | sort -u
   ```
   For each link target, check whether a matching .md file exists in the vault. Report broken links with their source files.

   **Orphaned .md files:**
   Find files in `03 Projects/` and `04 Areas/` not linked from any other .md file (excluding Archives, .stversions, system files). These may be forgotten or need linking from a hub.

   **Terminology consistency (lightweight):**
   Check for known ambiguous terms in recently modified files (last 7 days):
   - "PGS" without context qualifier → should specify genomics vs IVF
   - "PGD" → deprecated, should be PGT-M
   Report instances for user review — don't auto-fix terminology.

10. **Write Hygiene Report**

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

   ## Vault Consistency
   - Broken wikilinks: [list or "none"]
   - Orphaned files: [list or "none"]
   - Terminology flags: [list or "none"]

   ## Actions Taken (Auto-fix)
   - [List all automatic fixes applied]

   ## Actions Pending (User Decision)
   - [ ] [Each item requiring user confirmation]
   ```

11. **Display confirmation:**

    ```
    ✓ Hygiene report saved to: 06 Archive/Claude/Hygiene Reports/YYYY-Wnn.md
    ✓ Auto-fixes applied: N (session link trimming, completed item removal, backlog purge)
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
