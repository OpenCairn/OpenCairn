---
name: weekly-hygiene
description: Vault structural maintenance - broken links, stale items, tier mismatches, hygiene report
---

# Weekly Hygiene - Vault Structural Maintenance

You are running a vault hygiene pass. This is purely mechanical/structural maintenance — no reflexion, no planning, no alignment checks. It can run independently (mid-week cleanup) or as a precursor to `/weekly-review`.

## Instructions

**Write mechanism (F1) — applies to every step below.** All mutations of `Works in Progress.md`, `This Week.md`, `Tickler.md`, and project/area hub files (WIP pruning/strike-through, WIP↔This Week reconciliation, Tickler past-due edits, This Week purges, hub `**Status:**` propagation) go through `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5).

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **WIP Metrics & Pruning**

   **Gather:**
   - WIP line count: `wc -l "{VAULT}/01 Now/Works in Progress.md"`
   - WIP session links: `grep -c "06 Archive/Claude/Session Logs" "{VAULT}/01 Now/Works in Progress.md"`
   - Count session links per WIP section (Big Rocks vs Active vs Backlog) — heaviest sections are pruning candidates
   - WIP completed/strikethrough items: `grep -cE "\[x\]|~~.*~~" "{VAULT}/01 Now/Works in Progress.md"`
   - For each Active/Big Rock project, check the **Last:** date — flag any 14+ days stale
   - Per-entry line count (excluding session link lines starting with →): flag entries exceeding 30 lines

   **Auto-fix:**
   - Trim session log links to **3 most recent per entry** (matching the `_shared-rules.md` §6 / `/park` FIFO cap — one number everywhere, so weekly trims don't churn against park's cap) — only lines matching `→ [[06 Archive/Claude/Session Logs/`. **Preserve all other reference links** (`→ [[03 Projects/`, `→ [[04 Areas/`, etc.) — these are navigation pointers, not session history. Session history lives in the archive and project hub pages, not WIP.
   - Remove completed/strikethrough checklist items (the `[x] ~~done thing~~ ✅` pattern)
   - Remove resolved open decisions (strikethrough decisions that were answered)
   - Collapse resolved inline narratives: when a paragraph or sub-section contains 3+ items all marked ✅/resolved/completed, replace with a single summary line referencing the linked project/area file
   - Per-entry line budget: when a single WIP entry exceeds 30 lines (excluding session links), collapse verbose sub-sections to summary + link. Prioritise collapsing: duplicated detail (confirmation numbers, prices, addresses already in linked files), resolved narratives, sub-topics that have their own WIP entry
   - Detect sub-entry sprawl: when a WIP entry contains dedicated sub-topic headings, per-sub-topic session links, or content that duplicates a separate WIP entry, collapse to a cross-reference

   **Confirm with user:**
   - Flag Active/Big Rock projects whose **Last:** date is 14+ days stale — recommend demote or nudge
   - **When a demote/promote is actioned in-session, propagate the tier change to the project's hub `**Status:**` field** (`03 Projects/<name>.md` or the relevant area hub), not just the WIP entry. The WIP tier and the hub's own Status line are the same fact in two places; moving the WIP entry while leaving the hub reading "Active" leaves a stale cross-reference.

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
   - **Also for each NEW option/alternative added to a pre-existing decision/record** (surfaced while reconciling WIP/This Week, or from live docs modified since the last hygiene pass — a new option is not a "status change," so it slips the status-only sweep above): grep the decision's **anchor** (route/decision/record key) — NOT the new option text, which sibling docs that lack the option won't contain — across sibling docs (hubs, timelines, tables, indexes), and propagate the new entry into each, including parallel table rows a prose-only edit misses
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

   **After any file moves:** Grep for the old path (`[[03 Projects/Old Name]]`) in live vault files (exclude `06 Archive/` and `.stversions/`). Triage each hit per `_shared-rules.md §12` (grep-hit triage): fix stale wikilinks/locators in non-archive files; leave archive/session-log references as historical records; for a hash/provenance-log path, update the locator on the move, never the content hash/timestamp/proof.

4. **Tickler Hygiene**

   **Gather:**
   - Read `{VAULT}/01 Now/Tickler.md` (if it exists)
   - Flag items with dates that have passed (past-due and unactioned)
   - Flag completed (`- [x]`) or struck-through (`~~…~~`) items in **any** section — including non-dated, trigger-contingent holding-pen sections (e.g. a "## When I'm back" / "## On return" list). The past-due-date scan above only covers dated sections, so done items parked in an undated section accumulate invisibly.

   **Resolve in-session:**
   - For each past-due item: present and ask user to choose — complete (remove from Tickler), reschedule (user provides the new date), or drop (remove). Execute the chosen action during the sweep. No default rescheduling — the user must provide a real date.
   - For each completed/struck item: confirm it's genuinely done, then remove it during the sweep (per the Tickler "delete if done" convention). When removing a mid-list item, match its **trailing** newline (not a leading one) so its neighbours don't join onto one line; re-grep for a join defect after.
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

   **At-risk work-product detection (before triage).** Grep each non-empty scratchpad for `/reply` draft headings (`**Reply to `). For each match:
   - Flag as "unsent `/reply` draft — at-risk work product"
   - Present file path, heading, and first non-empty body line to user
   - Per-draft confirmation required: "sent" (→ remove section per §11 boundary rules via `locked-edit.sh`), "still needed" (→ route to durable location), or "discard" (→ remove section)
   - **Routing for "still needed":** CRM dossier if one exists for the recipient; else relevant project/area doc; else `01 Now/Tasks.md` as fallback with a backlink
   - Protected draft sections are excluded from general scratchpad triage below — handle them here first
   - See `_shared-rules.md` §11 for section boundary rules and cleanup ownership

   **Resolve in-session (non-draft content):**
   - After draft sections are resolved above, present remaining non-empty scratchpad content to user and offer to triage during the sweep. Do NOT offer blanket scratchpad clearing while unresolved draft sections remain.
   - **If user declines:** add `⚠ Hygiene Wnn: NL, Nd since last edit — triage needed` at the top of each non-empty scratchpad file.

7. **CRM Name Scan** (if `{VAULT}/07 System/CRM/` exists)

   - Read CRM index to get list of known names
   - Extract names from recent session files. Drop heading lines and the standard session-log/planning **section names** before counting — otherwise structural headings (`### Files Updated`, `## This Week`, …) dominate the frequency list and bury real people:
     ```bash
     find "{VAULT}/06 Archive/Claude/Session Logs/" -name "*.md" -mtime -7 -exec cat {} + \
       | grep -vE '^[[:space:]]*#' \
       | grep -oEh '[A-Z][a-z]+ [A-Z][a-z]+' \
       | grep -vxE 'This Week|Pickup Context|Open Loops|Key Insights|Next Steps|Files Updated|Files Created|Files Deleted|Session History|Resumption Brief|Session Logs|Daily Reports|Working Memory' \
       | sort | uniq -c | sort -rn | head -20
     ```
   - Flag names that appear 2+ times but aren't in CRM. A two-word capitalised bigram is a weak name signal — discard obvious non-people that slip the denylist (topic phrases, place names, product names) before presenting candidates.

   **Resolve in-session:**
   - Present candidates to user. For confirmed names, create CRM entries in the appropriate range file (A-F, G-L, M-R, S-Z) during the sweep.
   - **If user disengages:** route unresolved candidates to Tasks.md with a hygiene report back-reference.

8. **This Week.md Hygiene**

   **Auto-fix:**
   - Read `{VAULT}/01 Now/This Week.md`
   - Purge completed items: delete all `- [x]` lines from **past** day sections in This Week.md (date < today) and from Tasks.md. **Do not purge today's day section** — completed items there are at-a-glance context until `/goodnight` archives them to the daily report. Future day sections shouldn't have `[x]` items, but if they do, leave them. `- [ ]` items are always untouched.

   **Confirm with user:**
   - Audit trailing sections for staleness: scan sections after the last day section. Flag sections where >75% of content is resolved/done/strikethrough. Recommend deletion.
   - Update header metadata: check the `**Location:**` line against the most recent daily report. Flag if stale. (The `**Status:**` line has been deprecated — if one is still present as legacy, flag it for removal rather than staleness.)

9. **Claude Memory Audit**

   Claude Code's auto-memory (`~/.claude/projects/*/memory/` — the topic files plus the `MEMORY.md` index) holds behavioural corrections, user preferences, and technical reference notes. Topic files are surfaced by **relevance matching** (loaded only when semantically relevant); the `MEMORY.md` index is loaded **in full every session** and is hard-capped.

   **Doctrine: memory is a legitimate thin layer, not a silo to drain.** Most behavioural corrections belong *in memory* — relevance-matching fires them whenever the situation resembles the original, including cases no routing keyword would predict. Migrating such a rule to a keyword-routed context file (or into always-loaded `CLAUDE.md`) changes *when it fires* and can silently weaken it. So the weekly job is to keep memory **lean and the index under cap** — primarily by trimming bloated index hooks in place — *not* to relocate rules by default. Migration is the **exception**, reserved for entries that are genuinely mis-homed (below).

   **Gather:**
   - Locate the active memory directory: `ls ~/.claude/projects/*/memory/` — find the one matching the current working directory's path encoding
   - Read all `.md` files in that directory
   - Read `CLAUDE.md` from the vault root (needed for duplicate detection)
   - Count total entries/lines across all memory files

   **Index health (mechanical — check every week):**
   - `wc -lc` the `MEMORY.md` index. The hard cap is **200 lines OR 25 KB, whichever first** — entries past it are *silently dropped* from the system prompt with no warning. (Undocumented internals, observed as of 2026-06 — treat the numbers as approximate and re-verify if memory behaviour seems off after a Claude Code update.) Flag for action at **≥150 lines or ≥22 KB** (proactive, before the cap trips).
   - Flag any index **hook** (the text after ` — `) longer than ~160 chars: that's a hook that has bloated into a duplicate of its topic-file body. **The remedy is to trim the hook in place** — compress it to a one-line pointer; the detail already lives in the topic file. This is *not* a reason to migrate the entry. (A whole *line* over ~200 chars is usually just a long title/filename — that's fine; measure the hook, not the line.)

   **For each memory entry, classify (migration is the exception, not the default):**
   - **Trim (the usual index fix):** the index hook has bloated into a duplicate of its topic-file body. Compress the hook back to a one-line pointer and keep the entry — the detail stays in the topic file. This is the first remedy whenever the index is over (or near) cap; see *Index health* above.
   - **Keep in memory (the default for behaviour rules):** a behavioural correction whose trigger is contextual or unpredictable. Relevance-matching is the correct mechanism — leave it. Keeps are common, not rare.
   - **Migrate — only if genuinely mis-homed, and only if the destination actually loads on the entry's trigger:**
     - *Pure technical reference* (knowledge content, not a behaviour rule) → a vault doc near the relevant content, so it's visible to Obsidian search/backlinks. Verify the target file exists.
     - *A rule that genuinely fires in almost every session* → `CLAUDE.md`'s "Working With Me" section (accept the per-session token cost).
     - Before moving any rule to a routing-matched context file, confirm `CLAUDE.md`'s routing table actually loads that file for the rule's trigger — otherwise the rule goes dark. If it won't reliably load there, keep it in memory.
   - **Delete:** Stale (completed project, resolved decision), duplicated in vault/CLAUDE.md, vague/unactionable, or contradicts current vault content.

   **Resolve in-session:**
   - Present each entry with its classification and recommended action
   - For trims: show the compressed hook. For migrations: show the destination and confirm it loads on the entry's trigger before moving.
   - Execute confirmed trims, deletions, and (rare) migrations during the sweep. Update the `MEMORY.md` index; delete memory files only for migrated or deleted entries.
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
   # Non-plan directories: safe to delete unconditionally
   for dir in debug paste-cache shell-snapshots telemetry; do
     find ~/.claude/$dir/ -type f -mtime +7 -delete 2>/dev/null
   done
   ```

   **Plans directory — guarded deletion.** Plan files may be referenced by open work (WIP entries, Tasks). Before deleting each stale plan, grep its filename against `01 Now/Works in Progress.md` and `01 Now/Tasks.md`. Exclude matches — report them as "retained (referenced by open work)" instead.
   ```bash
   find ~/.claude/plans/ -type f -mtime +7 2>/dev/null | while read -r f; do
     base=$(basename "$f")
     if grep -qF "$base" "{VAULT}/01 Now/Works in Progress.md" "{VAULT}/01 Now/Tasks.md" 2>/dev/null; then
       echo "RETAINED (referenced): $base"
     else
       rm "$f" && echo "DELETED: $base"
     fi
   done
   ```
   Report per-directory counts (deleted, retained, and remaining).

11. **Session Transcript Export**

   Backstop for `/park` step 16 and `/goodnight` step 16, which export daily. This catches any days missed (skipped park/goodnight, crashed session, etc.). Claude Code auto-deletes JSONL session files after 30 days — this ensures nothing slips through.

   **Auto-fix:**
   ```bash
   python3 "{VAULT}/.claude/scripts/export-session-transcripts.py" "{VAULT}" --days 7 --all-projects
   ```
   (`--all-projects` makes this backstop sweep **every** project directory under `~/.claude/projects/`, not just the launch project — so it catches sessions run from any directory, which is the whole point of a backstop. No `cd` needed: `--all-projects` is cwd-independent, so it can't be defeated by a wrong launch-dir guess the way the per-session export can.)

   The script:
   - Finds JSONL session files modified in the last 7 days across **all** project directories under `~/.claude/projects/` (via `--all-projects`) — so the weekly backstop covers sessions launched from any directory, not just the vault-launched project
   - Extracts user messages, assistant text blocks, and Write/Edit/Agent tool inputs
   - Writes one file per day to `{VAULT}/06 Archive/Claude/.Session Transcripts/YYYY-MM-DD.md`
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
   If CLI unavailable, fall back to a find+grep pipeline (also apply `filter` here). The `find` predicates do the path exclusion — don't pass `-not -path` to grep (not a grep option), and keep the link pattern non-greedy (`[^]]*`) so multiple links on one line extract separately:
   ```bash
   find "{VAULT}" -name '*.md' -not -path '*/.stversions/*' -not -path '*/06 Archive/*' -print0 \
     | xargs -0 grep -ohE '\[\[[^]]*\]\]' 2>/dev/null \
     | sed 's/\[\[//;s/\]\]//;s/|.*//;s/#.*//' \
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

   **Shared-patterns pointer check** (if `_shared-patterns.md` exists in the commands directory). The pattern index points each entry at a reference (`→ ` + backtick-quoted skill name, or `_shared-rules.md §N` for shared-rules sections). Verify every pointer still resolves to a live file; a dangling pointer means the reference was renamed or removed. The `sed` normalisation strips a trailing ` §N` and `.md` so both pointer forms reduce to a file test.
   ```bash
   CMDS=~/.claude/commands; [ -f "$CMDS/_shared-patterns.md" ] || CMDS="{VAULT}/.claude/commands"
   PF="$CMDS/_shared-patterns.md"
   if [ -f "$PF" ]; then
     awk '/^## Patterns/{f=1;next} f' "$PF" | grep -oP '→ \K.*' | grep -oP '`[^`]+`' | tr -d '`' | sed 's/ §[0-9]*$//; s/\.md$//' | sort -u | while read -r s; do
       [ -f "$CMDS/$s.md" ] || echo "STALE pointer: $s (no $CMDS/$s.md)"
     done
   fi
   ```
   Any `STALE pointer` lines are tier-2 findings: fix the pointer (renamed skill) or drop the entry (removed skill) in `_shared-patterns.md`. Per its staleness contract, this check is what keeps the index drift-proof.

   **Obsidian Sync ghost detection** (optional, user-supplied script — not shipped with the template; if `~/repos/scripts/obsidian-ghost-check.sh` exists):
   ```bash
   if [ -x ~/repos/scripts/obsidian-ghost-check.sh ]; then
     bash ~/repos/scripts/obsidian-ghost-check.sh --since "8 days ago" "{VAULT}"
   fi
   ```
   Report any ghosts found. **Conflict files are owned by the built-in check below, not this script** — so don't run the script in `-d` mode against conflict files (that auto-removal bypasses the per-file confirmation the built-in enforces, and `rm`'ing an Obsidian Sync copy can resurrect it). Use the script for the ghost/duplicate/orphan detection the built-in doesn't do: in `-d`, duplicates are auto-removed and orphans listed for review. This catches files silently re-uploaded by a reconnecting phone via Obsidian Sync (known bug — Sync doesn't propagate deletions to offline devices). Skip silently if the script isn't installed.

   **Sync conflict files** (built-in — always runs, and owns conflict-file handling regardless of the optional ghost-check above). When two devices edit the same note while offline, both Syncthing and Obsidian Sync write a conflict file beside the original rather than overwriting. These hold divergent content and are silent data-divergence — they accumulate unnoticed until someone goes looking. Treat them as **tier-2 findings**: present and resolve in-session if the user engages, else route per the disengage rule below.
   ```bash
   # define `filter` in this same Bash call first, per the excludes block above
   find "{VAULT}" \( -name '*.sync-conflict-*' -o -iname '*conflicted copy*' \) \
     -not -path '*/.stversions/*' -type f 2>/dev/null | filter
   ```
   `*.sync-conflict-*` is Syncthing's pattern; a filename containing `conflicted copy` is Obsidian Sync's. (`06 Archive/` is deliberately **not** excluded — a conflict file beside an archived note is still live data-divergence.) For each hit, derive the base note and `diff` against it — the two schemes derive differently:
   - Syncthing `notes.sync-conflict-<date>-<time>-<id>.md` → remove the `.sync-conflict-<date>-<time>-<id>` infix, **keeping the real extension** → `notes.md`. The extension stays at the end and the infix sits before it (`document.txt` → `document.sync-conflict-20210507-080621-CEIVOCO.txt`), so do *not* strip to end-of-string — that drops the `.md`.
   - Obsidian `notes (Conflicted copy <device> <ts>).md` → strip the ` (Conflicted copy …)` segment, keep the extension → `notes.md`.
   - **Base note missing** (renamed or deleted since the conflict was written): treat as an orphaned conflict file — present it, don't assume a base, route to Tasks.md if unresolved.

   The diff decides the resolution — two real shapes:
   - **Strict subset / redundant** (the conflict copy adds nothing the base lacks) → delete the copy, base unchanged.
   - **Divergent fork** (each side carries unique content — e.g. two devices appended different work offline): do *not* "keep newer" — a parallel fork looks like a stale pair but newest-wins silently drops the other side's real work. A union-merge that preserves *all* unique content (and repoints inbound wikilinks if it renumbers/moves headings) is reflective work beyond this mechanical sweep — **route it to the user / Tasks.md as a manual merge**; never summarise, rewrite, or choose between the two sides autonomously.
   **Confirm per file — never auto-delete.** Deletion mechanism by source: a Syncthing `*.sync-conflict-*` file is safe to `rm` once its content is confirmed merged or redundant; an Obsidian Sync "conflicted copy" must be deleted *inside Obsidian* (via the app or the Obsidian delete tool, never `rm` — delete-on-disk can resurrect it via Sync).
   **If user disengages:** route to Tasks.md with a hygiene report back-reference — don't let it go undetected until next week.

   **Terminology consistency** (if `_terminology-checks.md` exists in the commands directory):
   Read the file for domain-specific ambiguous terms. Scan recently modified vault files (last 7 days) for each pattern. For each match, write an HTML comment near the ambiguous term in the flagged file: `<!-- ⚠ Hygiene Wnn: ambiguous term "[term]" — disambiguate -->`. This surfaces when the user next edits that file. Report instances in the hygiene report.

   **Concatenated list items** (planning-doc structural integrity):
   Item removals can eat the separator newline and join two list items onto one line — a leading-`\n` deletion that consumes the preceding line's terminator. Scan the planning docs:
   ```bash
   for f in "Works in Progress.md" "This Week.md" "Tasks.md" "Tickler.md"; do
     grep -nHE '[^[:space:]]- \[[ x]\]' "{VAULT}/01 Now/$f" 2>/dev/null
   done
   ```
   Any non-space immediately before a `- [ ]`/`- [x]` is a join defect (legit nested items are space- or tab-indented, so they don't match). Split the two items onto separate lines via `locked-edit.sh` and report each fix.

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
   - Hash the session transcript for that date (if exported): `{VAULT}/06 Archive/Claude/.Session Transcripts/YYYY-MM-DD.md`
   - Hash the session log for that date: `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`
   - OTS stamp all newly hashed files
   - Append entries to `07 System/AI Provenance Log.md`
   - Delete the processed flag file

   **14b. Verify existing provenance entries:**

   Read `{VAULT}/07 System/AI Provenance Log.md`. For each entry:

   **Resolve file path** from the File column:
   - `*-transcript.md` → `{VAULT}/06 Archive/Claude/.Session Transcripts/YYYY-MM-DD.md`
   - `YYYY-MM-DD.md` → `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`; if absent there, try `{VAULT}/06 Archive/Claude/Session Logs/YYYY/YYYY-MM-DD.md` (logs older than ~90 days are rolled into year subfolders by `/quarterly-hygiene` — the `YYYY` is the date's year)
   - Paths containing `/` → `{VAULT}/relative/path`. **Self-heal on move:** if that literal path is absent (the file was moved/renamed since logging — e.g. a folder dot-prefixed), fall back to `find "{VAULT}" -name "<basename>" -not -path "*/.stversions/*" -type f -print -quit` (note: do NOT exclude `06 Archive/` here — relocated transcripts live there) and accept the hit **only if** its content hash matches the logged hash. A hash match confirms it's the same file at a new location → use it for verification and update the log's path to the found location. No hit, or a hit whose hash differs → record MISSING (never repoint to a non-matching file). This keeps the verify pass robust to moves without depending on `/park` having caught every path reference.
   - Other (legacy bare filename) → try Session Logs, then vault root, then fall back to `find "{VAULT}" -name "<basename>" -not -path "*/.stversions/*" -not -path "*/06 Archive/*" -type f -print -quit`. Bare filenames in the log predate path-prefixing; the file may live in any project/area folder, so the fallback search is required.

   **Re-hash and compare:**
   ```bash
   # cut, not awk '{print ...}' — the slash-command loader substitutes bare $0-$9 as argument placeholders
   CURRENT_HASH=$(sha256sum "$RESOLVED_FILE" | cut -d' ' -f1)
   CURRENT_SHORT="${CURRENT_HASH:0:16}"
   ```
   Compare against logged hash. Record as MATCH, MISMATCH, or MISSING.

   **Superseded rows:** rows whose OTS column reads `superseded` are historical attestations replaced by a later row (`/provenance`'s append-only re-hash). Don't hash-compare them against the current file — a mismatch is expected by design; verify the superseding row instead. Their snapshot/proof files (if present in `07 System/Provenance/`) can still be verified against each other.

   **OTS availability guard:** if `ots` is not on PATH (`command -v ots`), skip the two OTS sub-steps below and record OTS status for affected entries as "skipped — ots CLI unavailable". Hash verification above still runs.

   **Upgrade OTS proofs:**
   For entries with OTS status "pending", try `ots upgrade` on the corresponding `.ots` file in `07 System/Provenance/`. If upgrade succeeds, update the provenance log entry to "confirmed".

   **Verify OTS proofs:**
   For entries with `.ots` files, run `ots verify -f "<resolved_target_file>" "<ots_file>"`. The `-f` flag is required whenever the target file lives in a different directory from the `.ots` proof — without it, `ots verify` looks for `<basename minus .ots>` alongside the proof and reports a misleading "could not open target" failure. Record as CONFIRMED, PENDING, FAILED, or MISSING.

   **Note:** Work product mismatches are informational, not failures — living documents evolve. Transcript mismatches would be suspicious. Session log mismatches are expected for entries created before the flag-based architecture (legacy mid-day hashes).

15. **Supply-chain config tripwire** (AI-assistant hook integrity)

   A 2026 class of npm/PyPI worm (Shai-Hulud / "Miasma" / "Hades" family) persists by writing `SessionStart` hooks into AI-assistant config files (`.claude/`, `.cursor/`, `.gemini/`) so the payload re-executes on every project open — uninstalling the offending package does **not** remove it. This weekly tripwire surfaces such hooks for a human eyeball; it does not auto-judge.

   ```bash
   # User-level AI-assistant configs (fixed paths — no recursive vault walk)
   for f in ~/.claude/settings.json ~/.claude/settings.local.json ~/.cursor/*.json ~/.gemini/settings.json; do
     [ -e "$f" ] && grep -lEi 'SessionStart|preinstall|postinstall|binding\.gyp' "$f" 2>/dev/null
   done
   # Vault-local Claude config, if present (single file, not a tree walk)
   ls "{VAULT}/.claude/settings.json" "{VAULT}/.claude/settings.local.json" 2>/dev/null
   # Python interpreter-startup hooks (the .pth vector): files that run code on import
   python3 -c "import site,glob,os; [print(p) for d in site.getsitepackages()+[site.getusersitepackages()] for p in glob.glob(os.path.join(d,'*.pth'))]" 2>/dev/null
   ```

   For each hit, read the hook / `.pth` and confirm it's expected (a known editor hook, a template's own hook, a setuptools/distutils `.pth`). The malicious signature: shells out to `curl`/`wget`/`node`/`python` against an unfamiliar URL or path, base64-decodes a blob, or touches `~/.ssh`, a password-manager store, or a wallet keystore. **Three outcomes, not one:**
   - **Clean** (no hits, or every hit is known-legit) → record "config tripwire: clean" and move on.
   - **Unexplained hit you can't classify** → surface it to the user *in this session, now* — don't bury it in the report or defer it.
   - **Hit matching the malicious signature** → treat as an **active compromise, not a hygiene item.** Do NOT route it to Tasks.md as a backlog line — that is the wrong severity channel. Halt: stop opening projects in the affected directory, tell the user immediately and in plain language, and run incident response — assume everything reachable during the exposure window was already exfiltrated (1Password items unlocked in that window, SSH keys, API tokens, `.claude`/`.cursor`/`.gemini` configs), so rotate/revoke those, remove the hook from the config file, and trace which package introduced it. The weekly cadence is the *detection* budget; the *response* to a true positive is immediate, not weekly.

16. **Write Hygiene Report**

   Determine the current ISO week: `date +%G-W%V` (e.g., `2026-W10`).
   Ensure the directory exists (`mkdir -p "{VAULT}/06 Archive/Claude/Hygiene Reports"` — prevents first-run failures), then write all findings to `{VAULT}/06 Archive/Claude/Hygiene Reports/YYYY-Wnn.md`:

   **⛔ Cite report/flag items by stable identifier, not line number** — see `_shared-rules.md` §13. Acute here: step 8's completed-`[x]` purge mutates Tasks.md *within this same run*, so any `Tasks.md Lnn` written into the report or a routed `⚠ Hygiene Wnn:` flag afterward is stale on write. Name items by title/heading/content.

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
   - Protected /reply drafts: N [paths, or "none"]
   - Drafts resolved this sweep: N (sent / routed / discarded)
   - Ordinary unprocessed content: [list or "none"]

   ## CRM Candidates
   - New names (not in CRM, 2+ mentions): [list or "none"]

   ## This Week.md
   - Completed backlog items purged: N
   - Stale trailing sections: [list or "none"]
   - Header metadata: [current / flagged]

   ## Claude Memory
   - Total entries/lines: N across M files
   - Index health: `MEMORY.md` at N lines / N KB (cap 200 lines / 25 KB; flag ≥150 lines or ≥22 KB)
   - Trimmed this sweep: [list of hooks compressed in place, or "none"]
   - Keep in memory: [list with reason, or "none"]
   - Migrate to vault (exception): [list with destination, or "none"]
   - Delete: [list with reason, or "none"]
   - Migrated this sweep: [list of entry → vault path, or "none"]

   ## Config Tripwire (supply-chain)
   - SessionStart / install hooks found: [list files, or "none"]
   - Suspicious `.pth` or hooks flagged: [list with reason, or "clean"]

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
   - Shared-patterns pointers: [stale list or "all resolve"] (if _shared-patterns.md exists)
   - List-item joins fixed: N [file + line per fix, or "none"]
   - Sync conflict files: N [list paths, or "none"] (Syncthing `*.sync-conflict-*` + Obsidian "conflicted copy")

   ## Obsidian Sync Ghost Check
   *(omit this section if the ghost-check script is not installed)*
   - Ghosts found: N (N duplicates, N orphans)
   - Conflict files: counted under *Sync conflict files* (Vault Consistency) — handled by the built-in check, not double-counted here
   - Auto-deleted: N (duplicates only)
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

17. **Route unresolved findings**

    For each finding not resolved during the sweep:

    - **Tier 3 items (project-level judgement):** Write the finding to the destination file per the routing rules in each step above. Format: `⚠ Hygiene Wnn: [description]` — placed after the entry's `**Status:**` line (for WIP entries), at the top of the relevant section (for Working Memory), or at the top of the file (for scratchpads).
    - **Tier 2 items the user declined to engage with:** Write to Tasks.md: `- [ ] [Description] → [[06 Archive/Claude/Hygiene Reports/YYYY-Wnn|Hygiene Wnn]]`
    - Update the hygiene report's "Actions Routed" section to note where each item was sent.
    - **Idempotent:** Before writing, check if a `⚠ Hygiene Wnn:` marker for the same week number already exists in the target file. If so, replace it rather than duplicating.
    - **Cleanup lifecycle:** When a user resolves a hygiene-flagged item in any future session, strike through the marker: `~~⚠ Hygiene Wnn: ...~~`. The next `/weekly-hygiene` run removes struck markers — in WIP via the step 1 pruning sweep; in the other routing destinations (Tasks.md, Working Memory, scratchpads) via this step's idempotency scan: while checking for existing `⚠ Hygiene` markers, delete any struck-through ones encountered.

18. **Display confirmation:**

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
- **Portability note.** Code snippets assume GNU coreutils (`stat -c`, `grep -P`, `sha256sum`, GNU `date`) — same caveat as `_shared-rules.md` §5's Linux-specific diagnostics. On macOS/BSD, substitute equivalents (`stat -f`, `perl -ne`/`sed -E` for `-P` extractions, `shasum -a 256`, `date -v`/`-j`).

## Integration

- **Standalone:** Run mid-week for a quick cleanup
- **Pre-review:** Run before `/weekly-review` — the review will consume the hygiene report
- **Weekly-review fallback:** If `/weekly-review` finds no hygiene report, it suggests running `/weekly-hygiene` first
