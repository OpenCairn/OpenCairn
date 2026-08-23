---
name: weekly-hygiene
description: Vault structural maintenance - broken links, stale items, folder mismatches, hygiene report
---


# Weekly Hygiene - Vault Structural Maintenance

You are running a vault hygiene pass. This is purely mechanical/structural maintenance — no reflexion, no planning, no alignment checks. It can run independently (mid-week cleanup) or as a precursor to `$weekly-review`.

## Instructions

**Write mechanism (F1) — applies to every step below.** All mutations of `This Week.md`, `Tickler.md`, `07 System/AI Provenance Log.md`, `07 System/Skill Monitor Log.md`, and project/area docs (Tickler past-due edits, This Week purges, routed-finding appends into an existing project task/action section, provenance log appends and path self-heals, skill-monitor log processing) go through `locked-edit.sh`, never a raw edit — except Tickler-routed findings, which go through `write-tickler.sh` (it owns dated-section placement). The list is illustrative, not exhaustive — `_shared-rules.md` §5 is canonical for which files are under the lock.

**Disengage routing — applies to every "user disengages" branch below.** A finding the user declines to resolve in-session routes to an existing task/action section in the relevant project/area doc where one is identifiable, else to the Tickler dated 7 days out — always with a hygiene-report back-reference, never to the Whimsy sink, never silently dropped. Write formats and mechanisms: step 17.

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   "$VAULT_PATH/.claude/scripts/check-archive-layout.sh" --enforce "$VAULT_PATH"
   ```

   If error, abort. Read `~/.codex/skills/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Project-Doc Health**

   Project docs in `03 Projects/` are the task SSOT: root = active, `Cold/` = paused, `Backlog/` = someday — the folder is the status. Each root doc carries `bucket:` frontmatter. `## Current Objective` and `## Next Actions` are optional conventions, not required schema.

   **Gather:**
   - List root docs: `ls "{VAULT}/03 Projects/"*.md`
   - For each root doc, check for `bucket:` in the frontmatter — list violations. Do not flag missing `## Current Objective` or `## Next Actions` headings.
   - Root-doc count (excluding `Cold/` and `Backlog/`): flag if it exceeds the **active project cap** (resolve it first: `rg -F '**Active project cap:'` over `{VAULT}/07 System/Vault Organisation Principles.md` → *Project Doc Format*, and state the value found. **`-F` is required** — the needle is literal. Exit 1, or a line yielding no number, means state `cap line unreadable — using default 5` and proceed on 5, so a failed read is never mistaken for a vault that states no cap. **Any other non-zero exit is a tool error, not an absent line** — report it and stop, rather than falling through to the default, which is the failure this branch exists to prevent)
   - Staleness candidates: where a root doc has an explicit task/action section, flag it when all tasks are ticked (no open `- [ ]`); also flag explicit current-state text that reads as completed. Missing conventional sections are not a staleness signal. Candidates may belong in `Cold/` or `$complete-project` (moves are executed in step 2's folder audit).

   **Confirm with user:**
   - Structure violations: fix a missing `bucket:` frontmatter key in-session via `locked-edit.sh`, with the user's confirmation
   - Staleness candidates: recommend `Cold/` or `$complete-project`

   **If not resolved in-session:** route each finding per the disengage-routing rule — use the doc's existing task/action section where one is identifiable; otherwise use the Tickler dated 7 days out via `write-tickler.sh`.

2. **Projects Folder Audit**

   **Gather:**
   - List top-level: `ls "{VAULT}/03 Projects/"`
   - List Cold/: `ls "{VAULT}/03 Projects/Cold/" 2>/dev/null`
   - List Backlog/: `ls "{VAULT}/03 Projects/Backlog/" 2>/dev/null`
   - A project's tier IS its folder — there is no separate dashboard to reconcile. Flag folder mismatches: root docs that look dead (step 1's staleness candidates), and Cold/ docs that look active (open dated commitments, or content contradicting "paused")

   **Confirm with user:**
   - Move mismatched docs to the folder matching their actual state (dead-looking root doc → `Cold/` or `$complete-project`; active-looking Cold/ doc → root)
   - Completed/abandoned projects with reference value → `04 Areas/[Area]/Archive/`; revivable-someday → `03 Projects/Cold/`. `06 Archive/` holds immutable write-once records only — never park project files there.

   **If not resolved in-session:** for each folder mismatch, route per the disengage-routing rule — `⚠ Hygiene Wnn: looks [dead/active] for its folder — move? → [[06 Archive/OpenCairn/Hygiene Reports/YYYY-Wnn|Hygiene Wnn]]` under an existing task/action section, else Tickler +7 days.

   **After any file moves:** Grep for the old path (`[[03 Projects/Old Name]]`) in live vault files (exclude `06 Archive/` and `.stversions/`). Triage each hit per `_shared-rules.md §12` (grep-hit triage): fix stale wikilinks/locators in non-archive files; leave archive/session-log references as historical records; for a hash/provenance-log path, update the locator on the move, never the content hash/timestamp/proof.

3. **Tickler Hygiene**

   **Gather:**
   - Read `{VAULT}/01 Now/Tickler.md` (if it exists)
   - Flag items with dates that have passed (past-due and unactioned)
   - Flag completed (`- [x]`) items in **any** section — including non-dated, trigger-contingent holding-pen sections (e.g. a "## When I'm back" / "## On return" list). The past-due-date scan above only covers dated sections, so done items parked in an undated section accumulate invisibly.
   - **Strikethrough is not a completion signal and not a delete directive.** `~~…~~` in the user's own files is content they chose to leave visible; if they wanted it gone they would have deleted it. Never treat it as "done", never sweep it, and never count it toward a deletion recommendation. If struck text looks like it wants an action, surface it as a question. (The sole exception is this skill's own `~~⚠ Hygiene Wnn: …~~` markers — Claude-authored machinery with a defined lifecycle, handled separately below.)

   **Resolve in-session:**
   - For each past-due item: present and ask user to choose — complete (remove from Tickler), reschedule (user provides the new date), or drop (remove). Execute the chosen action during the sweep. No default rescheduling — the user must provide a real date.
   - For each completed (`- [x]`) item: confirm it's genuinely done, then remove it during the sweep (per the Tickler "delete if done" convention). When removing a mid-list item, match its **trailing** newline (not a leading one) so its neighbours don't join onto one line; re-grep for a join defect after. Struck-through items are not in this set — leave them.
   - **If user disengages:** route each unresolved past-due item per the disengage-routing rule (an existing task/action section in its project/area doc where identifiable, else re-date it in the Tickler 7 days out via `write-tickler.sh`).

4. **Working Memory Sweep**

   **Gather:**
   - Read `{VAULT}/01 Now/Working memory.md`
   - Count items in each section (Fresh Captures, To Review, etc.)
   - Flag sections with 10+ unprocessed items
   - Identify any items that appear to be actionable tasks that should be in an existing project task/action section
   - Note items that have routing guidance but haven't been moved yet

   **If not resolved in-session:** For oversized sections (10+ items), add `⚠ Hygiene Wnn: N items, 10+ unprocessed — triage needed → [[06 Archive/OpenCairn/Hygiene Reports/YYYY-Wnn|Hygiene Wnn]]` at the top of that section in Working Memory.

5. **Scratchpad Sweep**

   **Gather:**
   - Find all Scratchpad.md files: `find "{VAULT}" -name "Scratchpad.md" -type f -not -path "*/.stversions/*" -not -path "*/06 Archive/*"`
   - For each non-empty scratchpad, note line count, and read any existing `⚠ Hygiene` marker for its **first-flagged week**. Note mtime only as a rough signal for files with no marker yet — once a marker exists, mtime reflects this check's own writes, not the user's (see the mtime warning below).

   **At-risk work-product detection (before triage).** Grep each non-empty scratchpad for `$reply` draft headings (`**Reply to `). For each match:
   - Flag as "unsent `$reply` draft — at-risk work product"
   - Present file path, heading, and first non-empty body line to user
   - Per-draft confirmation required: "sent" (→ remove section per §11 boundary rules via `locked-edit.sh`), "still needed" (→ route to durable location), or "discard" (→ remove section)
   - **Routing for "still needed":** CRM dossier if one exists for the recipient; else relevant project/area doc; else the Tickler dated 7 days out via `write-tickler.sh`, with a backlink
   - Protected draft sections are excluded from general scratchpad triage below — handle them here first
   - See `_shared-rules.md` §11 for section boundary rules and cleanup ownership

   **Resolve in-session (non-draft content):**
   - After draft sections are resolved above, present remaining non-empty scratchpad content to user and offer to triage during the sweep. Do NOT offer blanket scratchpad clearing while unresolved draft sections remain.
   - **If user declines:** add `⚠ Hygiene Wnn: NL, first flagged Wnn — triage needed → [[06 Archive/OpenCairn/Hygiene Reports/YYYY-Wnn|Hygiene Wnn]]` at the top of each non-empty scratchpad file.

   **⛔ Never derive the staleness figure from mtime** (`_shared-rules.md` §22 — this is its marker-specific case). Writing the marker rewrites the file, which resets its mtime — so a "days since last edit" number computed from `stat` measures *the last time this check wrote a marker*, not the last time the user touched the file. It resets to ~0 every sweep and shrinks as the file gets staler, inverting the metric it exists to report. Sibling of the auto-date reflex: the timestamp is available, plausible, and measuring the wrong event.

   Carry the **first-flagged week** instead — it is monotonic and self-evidencing:
   - No existing marker → this is the first flag. Write `first flagged W<current>`.
   - Existing marker → **preserve its original week verbatim** when refreshing; update only the line count and the current-week prefix. Never recompute the first-flagged value.

   A marker reading `⚠ Hygiene W30: 195L, first flagged W18` says the file has gone untouched across twelve sweeps — the fact worth acting on, and one no mtime-derived figure can express once the marker itself has been written. (Applies to any recurring marker that reports elapsed time on a file the marker is written into: same defect, same fix.)

6. **CRM Name Scan** (if `{VAULT}/07 System/CRM/` exists)

   - Read CRM index to get list of known names
   - Extract names from recent session files. Drop heading lines and the standard session-log/planning **section names** before counting — otherwise structural headings (`### Files Updated`, `## This Week`, …) dominate the frequency list and bury real people:
     ```bash
     # Self-contained block: shell vars don't survive between tool calls, so derive and use in one go.
     # Window = since the LAST hygiene run, by the log's OWN date (its filename). Never -mtime. See notes below.
     REPORTS="{VAULT}/06 Archive/OpenCairn/Hygiene Reports"
     LAST=$(ls -1 "$REPORTS" 2>/dev/null | rg '^[0-9]{4}-W[0-9]{2}\.md$' | LC_ALL=C sort -r | head -1)
     [ -n "$LAST" ] && LAST="$REPORTS/$LAST"
     CUTOFF=$(rg -m1 '^\*\*Generated:\*\*' "$LAST" 2>/dev/null | rg -o '[0-9]{4}-[0-9]{2}-[0-9]{2}')
     [ -z "$CUTOFF" ] && CUTOFF=$(date -d '7 days ago' +%Y-%m-%d)   # BSD/macOS: date -v-7d +%Y-%m-%d
     echo "CRM scan window: sessions dated ${CUTOFF}..today | source: ${LAST:-none — 7-day fallback}"
     find "{VAULT}/06 Archive/OpenCairn/Session Logs/" -name '[0-9]*-[0-9]*-[0-9]*.md' \
       | awk -v c="$CUTOFF" -F/ '{d=$NF; sub(/\.md$/,"",d); if (d >= c) print}' \
       | awk -F/ '!seen[$NF]++' \
       | tr '\n' '\0' | xargs -0 cat \
       | rg -v '^[[:space:]]*#' \
       | rg -o '[A-Z][a-z]+ [A-Z][a-z]+' \
       | rg -v -x 'This Week|Pickup Context|Open Loops|Key Insights|Next Steps|Files Updated|Files Created|Files Deleted|Session History|Resumption Brief|Session Logs|Daily Reports|Working Memory' \
       | sort | uniq -c | sort -rn | head -20
     ```

     **Window derivation and the mtime ban are governed by `_shared-rules.md` §22** (already in context — Step 0 reads it in full): the boundary comes from the previous report's `**Generated:**` header, the log's own filename supplies each session's date, and the resolved window is printed. Two specifics for this step: ISO dates compare correctly as plain strings, so the `awk` comparison needs no date parsing; and the newest report may be *this same week's*, written by an earlier run — that is the right boundary, not a bug.

     **Dedupe by basename.** Old logs are rolled into `Session Logs/YYYY/` subfolders, so the same log can be reachable at two paths. Without the `!seen[$NF]++` pass every name in a rolled log is counted twice and the frequency ranking is skewed toward whichever period happens to be duplicated. Which copy survives does not matter for counting; the pass exists so each *session* contributes once. **Deduping the scan is not a licence to delete either copy on disk** — surface on-disk duplication as a finding and leave the files alone.
   - Flag names that appear 2+ times but aren't in CRM. A two-word capitalised bigram is a weak name signal — discard obvious non-people that slip the denylist (topic phrases, place names, product names) before presenting candidates.

   **Resolve in-session:**
   - Present candidates to user. For confirmed names, create CRM entries in the appropriate range file (A-F, G-L, M-R, S-Z) during the sweep.
   - **If user disengages:** route unresolved candidates per the disengage-routing rule (a CRM candidate rarely has a project doc — the Tickler +7 days via `write-tickler.sh` is the usual destination).

7. **This Week.md Hygiene**

   **Auto-fix:**
   - Read `{VAULT}/01 Now/This Week.md`
   - Purge completed items: delete all `- [x]` lines from **past** day sections in This Week.md (date < today). **Do not purge today's day section** — completed items there are at-a-glance context until `$goodnight` archives them to the daily report. Future day sections shouldn't have `[x]` items, but if they do, leave them. `- [ ]` items are always untouched.

   **Confirm with user:**
   - Audit trailing sections for staleness: scan sections after the last day section. Flag sections where >75% of content is resolved or done (`- [x]`). Recommend deletion. Strikethrough does not count toward that share — see the Tickler step's rule; struck text is content the user kept.
   - Update header metadata: check the `**Location:**` line against the most recent daily report. Flag if stale. (The `**Status:**` line has been deprecated — if one is still present as legacy, flag it for removal rather than staleness.)

8. **Claude Memory Audit**

   This is dual-harness maintenance of Claude Code's memory tree. If no matching `~/.claude/projects/*/memory/` directory exists, record `Claude Code memory: not present` and continue to step 9; do not infer or invent a Codex memory path.

   Claude Code's auto-memory (`~/.claude/projects/*/memory/` — the topic files plus the `MEMORY.md` index) holds behavioural corrections, user preferences, and technical reference notes. Topic files are surfaced by **relevance matching** (loaded only when semantically relevant); the `MEMORY.md` index is loaded **in full every session** and is hard-capped.

   **Doctrine: memory is a legitimate thin layer, not a silo to drain.** Most behavioural corrections belong *in memory* — relevance-matching fires them whenever the situation resembles the original, including cases no routing keyword would predict. Migrating such a rule to a keyword-routed context file (or into always-loaded `CLAUDE.md`) changes *when it fires* and can silently weaken it. So the weekly job is to keep memory **lean and the index under cap** — primarily by trimming bloated index hooks in place — *not* to relocate rules by default. Migration is the **exception**, reserved for entries that are genuinely mis-homed (below).

   **Gather:**
   - Locate the active memory directory. The project directory name is the absolute cwd with every `/` **and** `.` replaced by `-` (so a dot-prefixed folder yields a doubled `-`), which resolves without guessing:
     ```bash
     M=~/.claude/projects/$(pwd | sed 's#[/.]#-#g')/memory
     [ -d "$M" ] || ls -d ~/.claude/projects/*/memory/   # fall back to listing if the derived path is absent
     ```
   - Read `MEMORY.md`. **Do not read the topic files wholesale** — the directory grows to hundreds of files and its full text dwarfs the index; every mechanical check below operates on the index alone. Read an individual topic file only when its index line is a Migrate or Delete candidate and the decision needs its body.
   - Read `CLAUDE.md` from the vault root (needed for duplicate detection)
   - Count the index's entries/lines, and the topic-file count (`ls "$M"/*.md | wc -l`) — not their combined line count

   **Index health (mechanical — check every week):**
   - `wc -lc` the `MEMORY.md` index. Two independent limits apply, and **the harness limit binds first — size the sweep to it, not to the line cap:**
     - **A harness-enforced size budget.** Claude Code emits a `PostToolUse` warning on any edit to `MEMORY.md` once the index approaches its read limit, and names an explicit compaction target in the warning text. Observed 2026-07: warned at 19.6 KB, read limit quoted as 24.4 KB, compaction target quoted as **under 17.1 KB**. **Treat the target quoted in the live warning as authoritative** — it is the harness's own number and supersedes anything written here.
     - **A line cap of ~200 lines**, past which entries are silently dropped from the system prompt with no warning.
   - Flag for action at **≥150 lines or ≥17 KB**. Do not use a KB threshold looser than the harness's compaction target: a 22 KB flag passes an index the harness is already warning about, which is exactly how a bloated index survives a sweep that reports it healthy. (Undocumented internals — re-verify after a Claude Code update, and prefer an observed warning over these figures.)
   - **When the index is over budget, compaction is a whole-file rewrite, not a few edits.** Shedding several KB across 100+ entries means every over-long hook, not the worst three. Rewrite the index in one pass, then verify: entry count unchanged, and every `](file.md)` link still resolves.
   - Flag any index **hook** (the text after ` — `) longer than ~120 chars: that's a hook that has bloated into a duplicate of its topic-file body. **The remedy is to trim the hook in place** — compress it to a one-line pointer; the detail already lives in the topic file. This is *not* a reason to migrate the entry. (A whole *line* over ~200 chars is usually just a long title/filename — that's fine; measure the hook, not the line.) Don't set this threshold so high that the flagged set can't close the gap to the size budget: an index needing several KB shed has dozens of over-long hooks, not three.
   - **Orphan check — topic files missing from the index.** Every `.md` in the memory directory except `MEMORY.md` must have an index line; a topic file with none is invisible to relevance matching and can never fire, however good the rule is. Nothing warns about this, and it survives every sweep that only reads the index.
     ```bash
     M=~/.claude/projects/$(pwd | sed 's#[/.]#-#g')/memory   # re-derive: shell state doesn't persist between calls
     for f in "$M"/*.md; do b=$(basename "$f"); [ "$b" = "MEMORY.md" ] && continue; rg -q -F "($b)" "$M/MEMORY.md" || echo "ORPHAN $b"; done
     rg -o -P '\]\(\K[^)]+' "$M/MEMORY.md" | while read -r f; do [ -f "$M/$f" ] || echo "DANGLING $f"; done
     ```
     An `ORPHAN` is triaged like any entry — index it if the fact is still live, delete the file if it isn't. A `DANGLING` index line points at a file that no longer exists: drop the line. Run both directions after any index rewrite.

   **For each memory entry, classify (migration is the exception, not the default):**
   - **Trim (the usual index fix):** the index hook has bloated into a duplicate of its topic-file body. Compress the hook back to a one-line pointer and keep the entry — the detail stays in the topic file. This is the first remedy whenever the index is over (or near) cap; see *Index health* above.
   - **Keep in memory (the default for behaviour rules):** a behavioural correction whose trigger is contextual or unpredictable. Relevance-matching is the correct mechanism — leave it. Keeps are common, not rare.
   - **Migrate — only if genuinely mis-homed, and only if the destination actually loads on the entry's trigger:**
     - *Pure technical reference* (knowledge content, not a behaviour rule) → a vault doc near the relevant content, so it's visible to Obsidian search/backlinks. Verify the target file exists.
     - *A rule that genuinely fires in almost every session* → `CLAUDE.md`'s "Working With Me" section (accept the per-session token cost).
     - Before moving any rule to a routing-matched context file, confirm `CLAUDE.md`'s routing table actually loads that file for the rule's trigger — otherwise the rule goes dark. If it won't reliably load there, keep it in memory.
   - **Delete:** Stale (completed project, resolved decision), duplicated in vault/CLAUDE.md, vague/unactionable, or contradicts current vault content.
     - **Retire at promotion.** When a lesson has been promoted into a `CLAUDE.md` rule *or written into this skill's own steps*, delete the originating memory in the same pass. Unretired promotions sit redundant for weeks and, worse, drift — the memory keeps asserting the old numbers after the skill has been corrected.
     - **A memory that only restates a harness behaviour the harness itself announces at the time is not worth keeping.** If a hook, warning, or error message states the fact when it matters, the memory adds nothing and can only go stale relative to it.

   **Resolve in-session:**
   - Present each entry with its classification and recommended action
   - For trims: show the compressed hook. For migrations: show the destination and confirm it loads on the entry's trigger before moving.
   - Execute confirmed trims, deletions, and (rare) migrations during the sweep. Update the `MEMORY.md` index; delete memory files only for migrated or deleted entries.
   - **If user disengages:** route unresolved entries per the disengage-routing rule (memory entries rarely map to a project doc — the Tickler +7 days via `write-tickler.sh` is the usual destination).

9. **Claude Internal File Cleanup**

   This is dual-harness maintenance of Claude Code's internal files. If none of the named `~/.claude/` directories exists, record `Claude Code internal files: not present` and continue to step 10.

   Claude Code generates ephemeral files across several internal directories. These accumulate indefinitely with no built-in retention. Work product in plans should be migrated to the vault by `$park` or `$goodnight` before session end. Other directories (`debug/`, `paste-cache/`, `shell-snapshots/`, `telemetry/`) contain session logs, clipboard caches, environment snapshots, and failed telemetry events — none are read back after the session that created them.

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

   **Plans directory — guarded deletion.** Plan files may be referenced by open work (project docs, This Week, Tickler). Before deleting each stale plan, grep its filename against `03 Projects/`, `01 Now/This Week.md`, and `01 Now/Tickler.md`. Exclude matches — report them as "retained (referenced by open work)" instead.
   ```bash
   find ~/.claude/plans/ -type f -mtime +7 2>/dev/null | while read -r f; do
     base=$(basename "$f")
     if rg -q -F "$base" "{VAULT}/03 Projects" "{VAULT}/01 Now/This Week.md" "{VAULT}/01 Now/Tickler.md" 2>/dev/null; then
       echo "RETAINED (referenced): $base"
     else
       rm "$f" && echo "DELETED: $base"
     fi
   done
   ```
   Report per-directory counts (deleted, retained, and remaining).

10. **Session Transcript Export**

   Backstop for `$park` step 11 and `$goodnight` step 16, which export daily. This catches any days missed (skipped park/goodnight, crashed session, etc.). The exporter reads both Claude Code JSONL and Codex rollout JSONL; Claude Code auto-deletes its session files after `cleanupPeriodDays` (30 by default), so the backstop also prevents those from slipping through.

   **Auto-fix:**
   ```bash
   python3 "{VAULT}/.claude/scripts/export-session-transcripts.py" "{VAULT}" --days 7 --all-projects
   ```
   (`--all-projects` makes this backstop sweep **every** project directory under `~/.claude/projects/`, not just the launch project — so it catches sessions run from any directory, which is the whole point of a backstop. No `cd` needed: `--all-projects` is cwd-independent, so it can't be defeated by a wrong launch-dir guess the way the per-session export can.)

   The script:
   - Finds Claude Code JSONL under `~/.claude/projects/` and Codex rollout JSONL under `~/.codex/sessions/`, modified in the last 7 days; `--all-projects` makes the sweep cwd-independent
   - Extracts user/assistant messages and recorded tool calls from both formats
   - Writes one file per day to `{VAULT}/06 Archive/OpenCairn/.Session Transcripts/YYYY-MM-DD.md`
   - Overwrites existing files for the same date (idempotent)

   Report the script's stdout summary in the hygiene report.

11. **Vault Consistency Checks**

   If the Obsidian CLI is available and Obsidian is running (`obsidian version 2>/dev/null` returns output), use it — it queries Obsidian's live index and is orders of magnitude faster than bash pipelines.

   **Excludes filter:** If `{VAULT}/.claude/hygiene-excludes` exists and carries at least one pattern, pipe all consistency-check output through `grep -vf` to remove noise from large embedded doc sets (darktable, Hugo themes, etc.). One grep pattern per line, `#` comments. Example file:
   ```
   # Patterns to exclude from vault consistency checks
   darktable
   hugo-theme
   ```
   Define the filter in each shell call that uses it (shell state doesn't persist between calls). **Gate on the surviving pattern count, not on the file existing** — `grep -vf` with an empty pattern file drops *every* line, so an excludes file that is empty or all comments would silently blank the entire consistency report:
   ```bash
   HYGIENE_EXCLUDES="{VAULT}/.claude/hygiene-excludes"
   EXC=$(mktemp)
   [ -f "$HYGIENE_EXCLUDES" ] && rg -v '^#' "$HYGIENE_EXCLUDES" | rg -v '^$' > "$EXC"
   if [ -s "$EXC" ]; then
     filter() { command grep -vf "$EXC"; }
   else
     filter() { cat ; }
   fi
   ```

   **Unresolved (broken) links:**
   ```bash
   # CLI (preferred): queries Obsidian's index directly
   obsidian unresolved counts format=tsv 2>/dev/null | filter
   ```
   If CLI unavailable, fall back to a basename-index comparison (also apply `filter` here). The `find` predicates do the path exclusion — don't pass `-not -path` to grep (not a grep option), and keep the link pattern non-greedy (`[^]]*`) so multiple links on one line extract separately. Wikilink targets may be bare note names or full paths, so both sides reduce to a basename before the comparison; the note index spans the whole vault (a live link into `06 Archive/` still resolves):
   ```bash
   # define `filter` in this same shell call first, per the excludes block above
   NOTES=$(mktemp); LINKS=$(mktemp)
   find "{VAULT}" -name '*.md' -not -path '*/.stversions/*' -print0 \
     | xargs -0 -n1 basename | sed 's/\.md$//' | sort -u > "$NOTES"
   find "{VAULT}" -name '*.md' -not -path '*/.stversions/*' -not -path '*/06 Archive/*' -print0 \
     | xargs -0 rg -o --no-filename '\[\[[^]]*\]\]' 2>/dev/null \
     | sed 's/\[\[//;s/\]\]//;s/|.*//;s/#.*//;s#.*/##;s/[[:space:]]*$//' \
     | rg -v '^$' | sort -u > "$LINKS"
   comm -23 "$LINKS" "$NOTES" | filter    # link targets with no matching note = unresolved
   rm -f "$NOTES" "$LINKS"
   ```

   **Orphaned files** (no incoming links):
   ```bash
   # CLI (preferred)
   obsidian orphans 2>/dev/null | filter | rg "^(03 Projects|04 Areas)/"
   ```
   If CLI unavailable, fall back to the same basename index — a note whose basename appears in no wikilink anywhere in the vault is an orphan:
   ```bash
   # define `filter` in this same shell call first, per the excludes block above
   LINKED=$(mktemp)
   find "{VAULT}" -name '*.md' -not -path '*/.stversions/*' -print0 \
     | xargs -0 rg -o --no-filename '\[\[[^]]*\]\]' 2>/dev/null \
     | sed 's/\[\[//;s/\]\]//;s/|.*//;s/#.*//;s#.*/##;s/[[:space:]]*$//' \
     | sort -u > "$LINKED"
   find "{VAULT}/03 Projects" "{VAULT}/04 Areas" -name '*.md' -type f 2>/dev/null \
     | while read -r f; do rg -q -x -F "$(basename "$f" .md)" "$LINKED" || echo "$f"; done | filter
   rm -f "$LINKED"
   ```

   **Dead-end files** (no outgoing links — CLI only, skip if unavailable):
   ```bash
   obsidian deadends 2>/dev/null | filter | rg "^(03 Projects|04 Areas)/" | head -20
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

   **⛔ Empty-output guard (`orphans` / `deadends` / `tags`):** on some setups these subcommands return zero rows even when the vault plainly has matches, and their `total` forms can return an implausible number or an empty string. An empty result piped through `wc -l` prints `0` — an absence of evidence the report would then record as evidence of absence. Before writing a 0 for any of these metrics, cross-check the row form against the `total` form (`obsidian orphans total`, `obsidian deadends total`; for tags, non-empty `obsidian tags` output). Record 0 only when both forms agree. If rows are empty but the total is non-zero, empty, or implausible (a sanity ceiling: it can't exceed the vault's file count), the CLI is unreliable for that metric on this setup → record it as **"unavailable (CLI returned no rows)"**, never 0. This applies equally to the orphan/dead-end listing checks above.

   **⛔ Distinguish a crash from an empty result — then stop calling it.** The guard above prevents a bad *number*; it does not ask *why* the command produced nothing, so a subcommand that **crashes** looks identical to one that quietly returns nothing, and the skill cheerfully re-invokes it every week. That is not free: where the CLI is a thin wrapper around a running desktop application, a crashing subcommand kills a child of the user's live editor on every call, and a diagnostic loop multiplies the damage. Before re-running a subcommand that returned nothing, check the platform's crash log:
   ```bash
   coredumpctl list --since "10 min ago" 2>/dev/null | tail -5              # Linux (systemd)
   ls -t ~/Library/Logs/DiagnosticReports 2>/dev/null | head -5             # macOS
   # Windows: Event Viewer → Windows Logs → Application, or `Get-EventLog -LogName Application -Newest 5`
   ```
   A coredump naming the editor or its helper means **crash, not emptiness** → record the metric as *"unavailable (subcommand crashes — do not re-invoke)"*, note the signal and the coredump path in the report, and **do not run it again this sweep**, including for diagnosis. One confirming run is evidence; a determinism loop is repeated harm to a live process.

   **Record *which* subcommands are broken in the tool-routing doc, not here.** Per-subcommand reliability is environment-specific and changes when the tool is updated — a volatile fact, so it gets one home and pointers from everywhere else. Its home is the vault's tool-routing doc (the one this skill's own guidance on search-tool selection points at); this skill carries only the durable mechanism above. A skill file that names which subcommand is currently broken will still be asserting it a year after the fix.

   **Shared-patterns pointer check** (if `_shared-patterns.md` exists in the commands directory). The pattern index points each entry at a reference (`→ ` + backtick-quoted skill name, or `_shared-rules.md §N` for shared-rules sections). Verify every pointer still resolves to a live file; a dangling pointer means the reference was renamed or removed. The `sed` normalisation strips a trailing ` §N` and `.md` so both pointer forms reduce to a file test. The extraction anchors on the **final** `→` on each line (`.*→ \K[^→]*$`) — entry titles may themselves contain arrows, and capturing from the first `→` misreads those titles as stale pointers.
   **Scan every commands tree present, not the first one found.** A pointer can resolve in one copy and dangle in another — a skill that exists only in the personal tree makes any pointer to it look live from a personal run, while breaking for everyone installing from the template. Binding to the first tree found therefore makes single-tree breakage structurally undetectable. Set `OPENCAIRN_TEMPLATE_DIR` to a template checkout's root to include it; without it the sweep covers the two standard locations and **says so in its output**, so a narrowed scan is visible rather than silent (see the emitted-count rule below).
   ```bash
   TREES=""
   for d in ~/.claude/commands "{VAULT}/.claude/commands" \
            "${OPENCAIRN_TEMPLATE_DIR:-/nonexistent}/.claude/commands"; do
     [ -f "$d/_shared-patterns.md" ] || continue
     r=$(realpath "$d" 2>/dev/null) || continue
     case " $TREES " in *" $r "*) continue ;; esac      # dedupe: symlinked/duplicate paths
     TREES="$TREES $r"
   done
   [ -n "$TREES" ] && echo "Pointer check: scanning $(echo $TREES | wc -w) tree(s)" \
                   || echo "Pointer check: NO commands tree found (check unusable)"
   for CMDS in $TREES; do
     PF="$CMDS/_shared-patterns.md"; n=0; bad=0
     while read -r s; do
       n=$((n+1))
       [ -f "$CMDS/$s.md" ] || { echo "  STALE pointer: $s (no $CMDS/$s.md)"; bad=$((bad+1)); }
     done < <(awk '/^## Patterns/{f=1;next} f' "$PF" | rg -o -P '.*→ \K[^→]*$' | rg -o -P '`[^`]+`' | tr -d '`' | sed 's/ §[0-9]*$//; s/\.md$//' | sort -u)
     echo "Pointer check [$CMDS]: $n pointers, $bad stale"
   done
   ```

   **⛔ Emit the tree count and the per-tree line even when clean** — the *Empty CLI output is not zero* and *Gate emits an observable* patterns applied to this check. A clean result and a scan that never ran are indistinguishable in silent output, so the count is what makes a narrowed sweep visible. A run reporting no tree count has verified nothing, however many zeroes it prints.

   **Anchor drift is NOT checked, deliberately — don't re-propose a grep for it.** Many entries point at a sub-step, but only the filename half is tested, so such a pointer survives a renumber intact (`_shared-patterns.md`'s staleness contract states this limit). A text grep cannot close it, for two reasons that hold regardless of the library's current contents: sub-step identity is **structural** — a lettered child nested under a numbered step — so a valid sub-step reference need not appear anywhere in the target as literal text; and step-heading notation is not normalised across skills, so any pattern loose enough to match the variants matches unrelated prose too. Measured variants produced only false positives. Closing this needs a markdown structure parser that walks a step's body for its children, which is disproportionate to an advisory check. Until then anchors are verified by the reviewer, not the sweep.

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
   # define `filter` in this same shell call first, per the excludes block above
   find "{VAULT}" \( -name '*.sync-conflict-*' -o -iname '*conflicted copy*' \) \
     -not -path '*/.stversions/*' -type f 2>/dev/null | filter
   ```
   `*.sync-conflict-*` is Syncthing's pattern; a filename containing `conflicted copy` is Obsidian Sync's. (`06 Archive/` is deliberately **not** excluded — a conflict file beside an archived note is still live data-divergence.) For each hit, derive the base note and `diff` against it — the two schemes derive differently:
   - Syncthing `notes.sync-conflict-<date>-<time>-<id>.md` → remove the `.sync-conflict-<date>-<time>-<id>` infix, **keeping the real extension** → `notes.md`. The extension stays at the end and the infix sits before it (`document.txt` → `document.sync-conflict-20210507-080621-CEIVOCO.txt`), so do *not* strip to end-of-string — that drops the `.md`.
   - Obsidian `notes (Conflicted copy <device> <ts>).md` → strip the ` (Conflicted copy …)` segment, keep the extension → `notes.md`.
   - **Base note missing** (renamed or deleted since the conflict was written): treat as an orphaned conflict file — present it, don't assume a base, route per the disengage-routing rule if unresolved.

   The diff decides the resolution — two real shapes:
   - **Strict subset / redundant** (the conflict copy adds nothing the base lacks) → delete the copy, base unchanged.
   - **Divergent fork** (each side carries unique content — e.g. two devices appended different work offline): do *not* "keep newer" — a parallel fork looks like a stale pair but newest-wins silently drops the other side's real work. A union-merge that preserves *all* unique content (and repoints inbound wikilinks if it renumbers/moves headings) is reflective work beyond this mechanical sweep — **route it to the user as a manual merge** (per the disengage-routing rule if not done in-session); never summarise, rewrite, or choose between the two sides autonomously.
   **Confirm per file — never auto-delete.** Deletion mechanism by source: a Syncthing `*.sync-conflict-*` file is safe to `rm` once its content is confirmed merged or redundant; an Obsidian Sync "conflicted copy" must be deleted *inside Obsidian* (via the app or the Obsidian delete tool, never `rm` — delete-on-disk can resurrect it via Sync).
   **If user disengages:** route per the disengage-routing rule (the doc the conflicted note belongs to where identifiable, else Tickler +7 days) — don't let it go undetected until next week.

   **Terminology consistency** (if `_terminology-checks.md` exists in the commands directory):
   Read the file for domain-specific ambiguous terms. Scan recently modified vault files (last 7 days) for each pattern. For each match, write an HTML comment near the ambiguous term in the flagged file: `<!-- ⚠ Hygiene Wnn: ambiguous term "[term]" — disambiguate -->`. This surfaces when the user next edits that file. Report instances in the hygiene report.

   **Concatenated list items** (planning-doc structural integrity):
   Item removals can eat the separator newline and join two list items onto one line — a leading-`\n` deletion that consumes the preceding line's terminator. Scan the planning docs:
   ```bash
   for f in "This Week.md" "Tickler.md"; do
     rg -n --with-filename '[^[:space:]]- \[[ x]\]' "{VAULT}/01 Now/$f" 2>/dev/null
   done
   ```
   Any non-space immediately before a `- [ ]`/`- [x]` is a join defect (legit nested items are space- or tab-indented, so they don't match). Split the two items onto separate lines via `locked-edit.sh` and report each fix.

12. **Context File Staleness Detection**

   Context files (`{VAULT}/07 System/Context - *.md`) shape every session's priors. They are event-driven, not time-driven — some are valid for years without edits, others contain temporal claims that expire. This step scans for temporal content that may have gone stale, rather than naively flagging files by modification date.

   **Gather:**
   - List all context files and their last-modified dates:
     ```bash
     find "{VAULT}/07 System/" -name "Context - *.md" -type f -exec stat -c '%Y %n' {} +
     ```
   - For each file found above, scan for temporal markers in three categories. Grep extracts candidate lines; **Claude classifies contextually** (bash can't distinguish historical facts from stale future claims).

     **Category A — Explicit dates:**
     ```bash
     rg -n "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+20[2-3][0-9]|20[2-3][0-9]-(0[1-9]|1[0-2])" "$FILE"
     ```
     Claude flags lines where the date is past AND the framing is forward-looking ("upcoming", "planned", "starting", "will"). Historical references ("Started September 2025") are not flagged.

     **Category B — Relative-time markers:**
     ```bash
     rg -n -i "\b(currently|right now|at the moment|these days|lately|recently|about to|planning to|transitioning|in progress|waiting for|not yet|haven't yet|still [a-z]+ing|upcoming|soon)\b" "$FILE"
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
   - **If user disengages:** route unresolved items per the disengage-routing rule (context files have no project doc — the Tickler +7 days via `write-tickler.sh` is the usual destination).
   - **Guardrail:** Edit context files only with user-provided replacement text. These are high-value prose documents — never rewrite, rephrase, or infer updates autonomously.

13. **Provenance: Process Stale Flags & Verify Hashes**

   This step absorbs the former `$verify-provenance` skill. Two jobs: catch missed flags, then verify existing entries.

   **13a. Process stale provenance flags:**
   ```bash
   ls "{VAULT}/07 System/.Provenance/pending/"*.md 2>/dev/null
   ```
   If any flag files exist (these are sessions where `$provenance` was invoked but `$goodnight` didn't process them — missed goodnight, crashed session, etc.):
   - Read each flag to get the tag and work product list
   - Hash any work products not already hashed
   - Hash the session transcript for that date (if exported): `{VAULT}/06 Archive/OpenCairn/.Session Transcripts/YYYY-MM-DD.md`
   - Hash the session log for that date: `{VAULT}/06 Archive/OpenCairn/Session Logs/YYYY-MM-DD.md`
   - OTS stamp all newly hashed files
   - Append entries to `07 System/AI Provenance Log.md`
   - Delete the processed flag file

   **13b. Verify existing provenance entries:**

   Read `{VAULT}/07 System/AI Provenance Log.md`. For each entry:

   **Resolve file path** from the File column:
   - `*-transcript.md` → `{VAULT}/06 Archive/OpenCairn/.Session Transcripts/YYYY-MM-DD.md`
   - `YYYY-MM-DD.md` → `{VAULT}/06 Archive/OpenCairn/Session Logs/YYYY-MM-DD.md`; if absent there, try `{VAULT}/06 Archive/OpenCairn/Session Logs/YYYY/YYYY-MM-DD.md` (logs older than ~90 days are rolled into year subfolders by the quarterly-hygiene workflow — the `YYYY` is the date's year)
   - Paths containing `/` → `{VAULT}/relative/path`. **Self-heal on move:** if that literal path is absent (the file was moved/renamed since logging — e.g. a folder dot-prefixed), fall back to `find "{VAULT}" -name "<basename>" -not -path "*/.stversions/*" -type f -print -quit` (note: do NOT exclude `06 Archive/` here — relocated transcripts live there) and accept the hit **only if** its content hash matches the logged hash. A hash match confirms it's the same file at a new location → use it for verification and update the log's path to the found location. No hit, or a hit whose hash differs → record MISSING (never repoint to a non-matching file), **then run the snapshot fallback below before reporting the row** — MISSING is precisely the case where the live file is unresolvable *and* the attested bytes may still be sitting in `.Provenance`. This keeps the verify pass robust to moves without depending on `$park` having caught every path reference.
   - Other (legacy bare filename) → try Session Logs, then vault root, then fall back to `find "{VAULT}" -name "<basename>" -not -path "*/.stversions/*" -not -path "*/06 Archive/*" -type f -print -quit`. Bare filenames in the log predate path-prefixing; the file may live in any project/area folder, so the fallback search is required.

   **Re-hash and compare:**
   ```bash
   # cut, not awk '{print ...}' — the slash-command loader substitutes bare $0-$9 as argument placeholders
   CURRENT_HASH=$(sha256sum "$RESOLVED_FILE" | cut -d' ' -f1)
   CURRENT_SHORT="${CURRENT_HASH:0:16}"
   ```
   Compare against logged hash. Record as MATCH, MISMATCH, or MISSING.

   **Snapshot fallback for MISMATCH *or* MISSING — try this first.** It keys on the logged hash, not on the file's current location, so it is independent of whether the live file resolved at all. Scoping it to MISMATCH alone strands the MISSING rows permanently: a file that both moved *and* evolved fails the self-heal hash gate above, lands on MISSING, and never reaches the one check that could verify it. `$provenance` writes a preimage snapshot beside the proof at `07 System/.Provenance/<date>-<name>-<short8>.snapshot<ext>`, where `<short8>` is the first 8 characters of the logged hash. A living work product edited after hashing therefore MISMATCHes the live file while its attested bytes sit on disk unread. The logged hash is the key, so no log schema change is needed to find it:
   ```bash
   # LOGGED = logged 16-hex short hash
   SNAP=$(ls "{VAULT}/07 System/.Provenance/"*-"${LOGGED:0:8}".snapshot.* 2>/dev/null | head -1)
   if [ -n "$SNAP" ] && [ "$(sha256sum "$SNAP" | cut -c1-16)" = "$LOGGED" ]; then
     echo "VERIFIED via snapshot: $SNAP"
   fi
   ```
   A hit upgrades the row to **"verified via snapshot"**. Fall through to the git-history walk only when no snapshot resolves: the snapshot is both the cheaper check and the stronger evidence, being the exact attested bytes written at hash time rather than a blob inferred from history. Reporting MISMATCH/FAILED without running this is a false negative, not an integrity signal.

   **Report the two MISSING outcomes separately — do not collapse them.** A snapshot hit on a MISSING row upgrades it to **"verified via snapshot — locator stale"**, never to a bare "verified via snapshot". Untriaged MISSING conflates two states that call for opposite responses: *the attested bytes are gone and this row is now unverifiable* (a real integrity signal, escalate) versus *the bytes are intact and only the path rotted* (bookkeeping, fix the pointer). Flattening them hides the second class, and the pointer then never gets fixed because nothing reports it. This is `_shared-rules.md` §12's **Live locator** category arriving in an automated verify pass — same distinction, same remedy (repair the locator, never the attested content); reuse that vocabulary rather than coining a parallel one.

   **Never auto-repoint a stale locator on the strength of a snapshot.** The self-heal at the top of this step is licensed by a hash match against the *live* file, which proves it is the same artefact relocated. A snapshot match proves only that the attested bytes survive somewhere — it says nothing about which live file, if any, is the row's subject. Report `verified via snapshot — locator stale` with the resolved snapshot path and leave the row alone; where the log declares itself append-only, rewriting the File column would breach that contract anyway, and the correct repair is an appended annotation the human writes.

   **Git-history fallback for MISMATCH** (if the vault is a git repo): a mismatch usually means the file evolved after hashing — the attested bytes may still exist as a historical git blob. Walk the file's history for a blob whose hash matches the logged one:
   ```bash
   cd "{VAULT}"
   # REL = vault-relative path, LOGGED = logged 16-hex short hash
   while read -r C; do
     B=$(git rev-parse -q --verify "$C:$REL") || continue
     H=$(git cat-file blob "$B" | sha256sum | cut -c1-16)
     [ "$H" = "$LOGGED" ] && { echo "VERIFIED via git history: ${C:0:7} ($(git show -s --format=%ci "$C"))"; break; }
   done < <(git log --format=%H -- "$REL")
   ```
   A hit upgrades the row from MISMATCH to **"verified via git history (commit, date)"** — the attested content demonstrably existed; the current mismatch is post-hash evolution, not tampering. No hit leaves it a MISMATCH, but with known limits: git can't clear a state that never landed in a commit (e.g. a hash taken between auto-save commits and appended to minutes later) or that predates git tracking of that path — assess those against mtime and known tooling behaviour, and say which case applies.

   **Superseded rows:** rows whose OTS column reads `superseded` are historical attestations replaced by a later row (`$provenance`'s append-only re-hash). Don't hash-compare them against the current file — a mismatch is expected by design; verify the superseding row instead. Their snapshot/proof files (if present in `07 System/.Provenance/`) can still be verified against each other.

   **OTS availability guard:** `command -v ots` is necessary but not sufficient — stamping and upgrading only need the Python `ots` client (calendar servers), but *verifying* needs an attestation source, and the Python client supports only a local Bitcoin node (no explorer fallback). Pick the verify path in order:
   1. **Local node present** (`~/.bitcoin/.cookie` exists, or `bitcoin-cli getblockcount` succeeds) → Python `ots verify`.
   2. **No node** → the JS OpenTimestamps client (`ots-cli.js`, npm package `opentimestamps`; install with `npm install -g opentimestamps`), whose verify does lite-client verification against public block headers via explorers — no node needed. Trust model: public explorers instead of a local node; fine for personal provenance.
   3. **Neither** → skip verification and record OTS status for affected entries as "skipped — no verifier available". Never let an unrunnable verify be recorded as anything but skipped. Stamping/upgrading still run if `ots` is on PATH; hash verification above always runs.

   **Upgrade OTS proofs:**
   For entries with OTS status "pending", try `ots upgrade` on the corresponding `.ots` file in `07 System/.Provenance/` (calendar servers — works without a node). If upgrade succeeds, update the provenance log entry to "confirmed".

   **Verify OTS proofs:**
   For entries with `.ots` files, run `ots verify -f "<resolved_target_file>" "<ots_file>"` (path 1) or `ots-cli.js verify -f "<resolved_target_file>" "<ots_file>"` (path 2). The `-f` flag is required whenever the target file lives in a different directory from the `.ots` proof — without it, verify looks for `<basename minus .ots>` alongside the proof and reports a misleading "could not open target" failure. The JS client's success line reads `Success! Bitcoin block N attests existence as of <date>` after "Lite-client verification" warnings — that is a pass. Record as CONFIRMED (note "lite" when via explorer), PENDING, FAILED, or MISSING.

   **Note:** Work product mismatches are informational, not failures — living documents evolve. Transcript mismatches would be suspicious. Session log mismatches are expected for entries created before the flag-based architecture (legacy mid-day hashes).

14. **Supply-chain config tripwire** (AI-assistant hook integrity)

   A 2026 class of npm/PyPI worm (Shai-Hulud / "Miasma" / "Hades" family) persists by writing `SessionStart` hooks into AI-assistant config files (`.claude/`, `.cursor/`, `.gemini/`) so the payload re-executes on every project open — uninstalling the offending package does **not** remove it. This weekly tripwire surfaces such hooks for a human eyeball; it does not auto-judge.

   ```bash
   # User-level AI-assistant configs (fixed paths — no recursive vault walk)
   for f in ~/.claude/settings.json ~/.claude/settings.local.json ~/.codex/config.toml ~/.cursor/*.json ~/.gemini/settings.json; do
     [ -e "$f" ] && rg -l -i 'SessionStart|hooks?[[:space:]]*=|preinstall|postinstall|binding\.gyp' "$f" 2>/dev/null
   done
   # Vault-local assistant configs, if present (fixed files, not a tree walk)
   for f in "{VAULT}/.claude/settings.json" "{VAULT}/.claude/settings.local.json" "{VAULT}/.codex/config.toml"; do
     [ -e "$f" ] && rg -l -i 'SessionStart|hooks?[[:space:]]*=|preinstall|postinstall|binding\.gyp' "$f" 2>/dev/null
   done
   # Python interpreter-startup hooks (the .pth vector): files that run code on import
   python3 -c "import site,glob,os; [print(p) for d in site.getsitepackages()+[site.getusersitepackages()] for p in glob.glob(os.path.join(d,'*.pth'))]" 2>/dev/null
   ```

   For each hit, read the hook / `.pth` and confirm it's expected (a known editor hook, a template's own hook, a setuptools/distutils `.pth`). The malicious signature: shells out to `curl`/`wget`/`node`/`python` against an unfamiliar URL or path, base64-decodes a blob, or touches `~/.ssh`, a password-manager store, or a wallet keystore. **Three outcomes, not one:**
   - **Clean** (no hits, or every hit is known-legit) → record "config tripwire: clean" and move on.
   - **Unexplained hit you can't classify** → surface it to the user *in this session, now* — don't bury it in the report or defer it.
   - **Hit matching the malicious signature** → treat as an **active compromise, not a hygiene item.** Do NOT bury it in a project doc's `## Next Actions` or the Tickler as a backlog line — that is the wrong severity channel. Halt: stop opening projects in the affected directory, tell the user immediately and in plain language, and run incident response — assume everything reachable during the exposure window was already exfiltrated (1Password items unlocked in that window, SSH keys, API tokens, `.claude`/`.cursor`/`.gemini` configs), so rotate/revoke those, remove the hook from the config file, and trace which package introduced it. The weekly cadence is the *detection* budget; the *response* to a true positive is immediate, not weekly.

   **Package drift review (routine awareness — separate from the tripwire outcomes above).** If the host runs a package-drift reporter (check `~/.local/state/package-drift-report.txt`, or the user's tech-infra context for its report path), read the latest report. Surface READY items for the user to apply manually; do not auto-apply. Items tagged `SELF` sit in the AI agent's own request path (the CLI itself, a router/proxy in front of it) — those are applied only from a plain shell outside the agent, never from within a session (an agent updating its own transport kills the session mid-update). No reporter → skip silently in execution but still record the report line in the hygiene report.

15. **Skill-Monitor Log Processing**

   Skills log self-improvement observations to `{VAULT}/07 System/Skill Monitor Log.md` per `_skill-monitor.md` instead of proposing edits in-session. This step is the weekly processing point.

   - Log missing or empty → record "skill-monitor log: empty" and move on (the report section is still emitted, with zeros — omission reads as "forgot to run").
   - **Sweep any tombstoned former location first**, via `rg -l --hidden 'TOMBSTONE — this is not the skill monitor log' "{VAULT}"` (`--hidden`, because an abandoned append target is often a dot-file and is invisible to a default `rg`). For each hit: merge any block not already marked as merged into the canonical log, then mark it merged in place. This runs on the *reader's* side, which is the point — when the log moves, sessions already in flight keep appending to the old path from the `_skill-monitor.md` they loaded before the move, and no edit to any skill can reach a session that already holds the old copy.
   - **Tombstone only where a stale writer is demonstrated; otherwise delete.** `locked-edit.sh --append` creates a missing file, so deleting a path something still writes to does not stop the writes — it removes the banner and lets the next append look like a fresh log. But that reasoning only applies where a writer actually exists. Test it: does any skill, script or repo reference the old path, and has anything written there recently? If both are no, the observations belong in the canonical log and the file itself is clutter — merge and delete, leaving the content recoverable in vault git. Tombstoning an orphan nothing points at is unrequested residue.
   - Read the log. Group observations by the file the suggested edit targets — a bullet naming another file (e.g. a `_shared-rules.md` section) routes to that file, with the logging skill kept as evidence; only default to the skill's own file when no other target is named. The same gap observed across sessions is one finding with a recurrence count (recurrence = priority signal), listing the dates it covers.
   - **Escalate anything seen 3+ times.** Count the recurrences per finding and say the number. A suggestion logged three or more times is not a finding awaiting disposition — it is evidence that the log is absorbing effort a fix should be absorbing, and that "defer" has already been chosen and has already failed. Promote it to the work-queue doc that owns the skill library as an explicit fix task, and record it as promoted rather than deferring it a fourth time. Deferring a 3+ recurrence is a disposition this step does not offer.
   - **A recurrence count is a floor, not a total.** Independent sessions describe the same defect in different words, so grouping by wording undercounts. Before assigning a count, grep the log for the artefact (script name, step number, file path), not for the phrasing.
   - Present grouped findings with a recommended disposition each: **apply** (show the specific edit for approval), **reject**, or **defer**. Never auto-apply.
   - Approved edits go to the canonical copy. If the skill exists in an OpenCairn template repo, update the applicable Claude source and/or Codex rendering there first; when a finding applies to both mapped versions, keep them aligned, regenerate `agents/openai.yaml` if its metadata changes, acknowledge and check the render map, then copy the Codex skill directory to the live `~/.codex/skills/` tree and `diff` the pair. Preserve unrelated dirty work. If no canonical copy exists, edit only the personal installation. No git commit unless asked.
   - After processing: remove the blocks belonging to applied and rejected findings; blocks for deferred findings stay. Disposition is per observation, not per block — when one block's bullets got different dispositions, rewrite the block keeping only the deferred bullets. The removal is a read-modify-write racing possible concurrent appends — rewrite via `locked-edit.sh --replace` per block, never a raw edit. Match each block including its trailing blank line (mid-file removals otherwise join adjacent entries); on exit 2 (no match) re-read the log and retry; on exit 3 (identical duplicate blocks — same skill, same day, same bullet) use `--replace-all`. After removals, re-read the log and check for joined headings.
   - **If user disengages:** leave the log untouched; entries persist to next week.

16. **Write Hygiene Report**

   Determine the current ISO week: `date +%G-W%V` (e.g., `2026-W10`).
   Ensure the directory exists (`mkdir -p "{VAULT}/06 Archive/OpenCairn/Hygiene Reports"` — prevents first-run failures), then render all findings for `{VAULT}/06 Archive/OpenCairn/Hygiene Reports/YYYY-Wnn.md`. Draft the complete report outside the vault and write it through `"{VAULT}/.claude/scripts/locked-edit.sh"`. When missing, immediately confirm the path is absent and create it with `--replace-whole MISSING`; exit 2 means another writer created it, so re-read that file and continue through the existing-report path. When it already exists, preserve every unresolved routed action in the new draft, re-read the old report, and use its complete contents as literal OLD with `--replace`. Never create the report with `--append` or write it directly.

   **⛔ Cite report/flag items by stable identifier, not line number** — see `_shared-rules.md` §13. Acute here: step 7's completed-`[x]` purge mutates This Week.md *within this same run*, so any `This Week.md Lnn` written into the report or a routed `⚠ Hygiene Wnn:` flag afterward is stale on write. Name items by title/heading/content.

   ```markdown
   # Vault Hygiene Report

   **Generated:** YYYY-MM-DD HH:MM
   **Status:** [Clean / N issues found]

   ## Project-Doc Health
   - Root docs: N against the active project cap M (flag if over; Cold/: N, Backlog/: N)
   - Structure violations (missing bucket): [list or "none"]
   - Staleness candidates (explicit tasks all ticked / current-state text reads completed): [list or "none"]

   ## Projects Folder
   - Folder mismatches: [list or "none"]
   - Recommended moves: [list or "none"]

   ## Tickler
   - Past-due items: N
   - [List each with original date and recommendation]

   ## Working Memory
   - Total items: N across M sections
   - Oversized sections (10+): [list or "none"]
   - Items needing routing: [list or "none"]

   ## Scratchpads
   - Protected $reply drafts: N [paths, or "none"]
   - Drafts resolved this sweep: N (sent / routed / discarded)
   - Ordinary unprocessed content: [list or "none"]

   ## CRM Candidates
   - New names (not in CRM, 2+ mentions): [list or "none"]

   ## This Week.md
   - Completed backlog items purged: N
   - Stale trailing sections: [list or "none"]
   - Header metadata: [current / flagged]

   ## Claude Memory
   - Index entries: N (topic files on disk: M)
   - Index health: `MEMORY.md` at N lines / N KB (flag ≥150 lines or ≥17 KB; harness compaction target ~17.1 KB, line cap ~200)
   - Trimmed this sweep: [list of hooks compressed in place, or "none"]
   - Orphaned topic files (no index line): [list with disposition, or "none"]
   - Dangling index lines (file missing): [list, or "none"]
   - Keep in memory: [list with reason, or "none"]
   - Migrate to vault (exception): [list with destination, or "none"]
   - Delete: [list with reason, or "none"]
   - Migrated this sweep: [list of entry → vault path, or "none"]

   ## Config Tripwire (supply-chain)
   - SessionStart / install hooks found: [list files, or "none"]
   - Suspicious `.pth` or hooks flagged: [list with reason, or "clean"]
   - Package drift report: [not present / N READY, N SELF-held, M current]

   ## Skill Monitor
   - Log entries processed: N across M skills
   - Applied: [skill: edit summary, or "none"]
   - Rejected: N / Deferred (left in log): N

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
   - Orphaned files (03 Projects/ & 04 Areas/): [list, "none", or "unavailable (CLI returned no rows)" per the empty-output guard]
   - Dead-end files (03 Projects/ & 04 Areas/): [list top 10, "none", or "unavailable" per the empty-output guard]
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
   - Orphan count: N [filtered / unfiltered] or "unavailable" (empty-output guard)
   - Unresolved link count: N [filtered / unfiltered]
   - Dead-end count: N [filtered / unfiltered] or "unavailable" (empty-output guard)
   - Top tags: [top 5 with counts, or "unavailable" (empty-output guard)]
   - Excludes active: [yes — N patterns from hygiene-excludes / no — file absent or carries no patterns]

   ## Provenance
   - Stale flags processed: N [OR "none"]
   - Entries verified: N
   - Hash matches: N
   - Verified via git history: N (mismatch cleared by a historical blob matching the logged hash)
   - Hash mismatches: N (files edited after logging; git fallback found no matching blob)
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
   - Routed to project docs (task/action sections): N
   - Routed to SSOT files (Working Memory, scratchpads, terminology): N
   - Routed to Tickler (+7d): N
   ```

17. **Route unresolved findings**

    For each finding not resolved during the sweep:

    - **Tier 3 items (project-level judgement):** Write the finding to the destination file per the routing rules in each step above. Format: `⚠ Hygiene Wnn: [description] → [[06 Archive/OpenCairn/Hygiene Reports/YYYY-Wnn|Hygiene Wnn]]` — under an existing task/action section (for project docs), at the top of the relevant section (for Working Memory), or at the top of the file (for scratchpads).
    - **Tier 2 items the user declined to engage with** (the disengage-routing rule) — two destinations:
      - **Project/area doc with an existing task/action section identifiable:** append `- [ ] [Description] → [[06 Archive/OpenCairn/Hygiene Reports/YYYY-Wnn|Hygiene Wnn]]` there via `locked-edit.sh`.
      - **No doc identifiable:** write a Tickler entry dated 7 days out via `write-tickler.sh`, same line format.
      Findings never go to the Whimsy sink and are never silently dropped.
    - Update the hygiene report's "Actions Routed" section to note where each item was sent. Re-read the report, then update that section through `locked-edit.sh --replace`; never mutate it directly.
    - **Routing is an upsert.** Key each routed item by its destination plus normalised finding identity; ignore volatile week numbers, counts and first-flagged metadata during matching. Its provenance marker must be the exact current hygiene-report backlink. Search the destination first; a match carrying any `Hygiene Reports/YYYY-Wnn` backlink is the same recurring finding, so update its text/backlink through the owning locked writer rather than appending. Otherwise create it once. The week number alone is not a key — several distinct findings may route to the same file in one run.
    - **Cleanup lifecycle:** When a user resolves a hygiene-flagged item in any future session, strike through the marker: `~~⚠ Hygiene Wnn: ...~~`. The next `$weekly-hygiene` run removes struck markers in every routing destination (project docs, Working Memory, scratchpads, Tickler) via this step's idempotency scan: while checking for existing `⚠ Hygiene` markers, delete any struck-through ones encountered.

18. **Display confirmation:**

    ```
    ✓ Hygiene report saved to: 06 Archive/OpenCairn/Hygiene Reports/YYYY-Wnn.md
    ✓ Auto-fixes applied: N (completed-item purge, list-join fixes, internal file cleanup)
    ✓ Resolved in-session: N (CRM, memory, context, tickler, scratchpad)
    ✓ Routed to SSOT: M (N to project docs, M to files, P to Tickler)

    Vault hygiene complete. Run $weekly-review to incorporate findings into your weekly reflection.
    ```

## Guidelines

- **Mechanical, not reflective.** This command fixes structural issues and flags potential staleness. `$weekly-review` handles patterns, alignment, and planning. Context staleness detection (step 12) straddles this boundary — the gather is mechanical (grep), the classification requires judgement, but the output is a checklist to confirm, not a reflexion to act on.
- **Three tiers of findings.** (1) Auto-fix: safe mechanical changes. (2) Resolve in-session: CRM additions, memory cleanup, context file updates, Tickler past-due, scratchpad triage — present to user and execute during the sweep. (3) Route to SSOT: project-level judgement calls (stale project docs, folder mismatches, Working Memory overflow) get `⚠ Hygiene Wnn:` markers written to the relevant file. If the user declines to engage with tier-2 items, route per the disengage-routing rule — an existing task/action section in the relevant project/area doc where one exists, else the Tickler dated 7 days out — never to Whimsy, never dropped silently.
- **Hygiene markers clean up automatically.** When resolved, markers are struck through (`~~⚠ Hygiene Wnn: ...~~`). The next hygiene run removes struck **`⚠ Hygiene` markers only** — never struck user content, which is left in place (see the Tickler step's strikethrough rule).
- **Idempotent.** Running twice should produce the same result. The report overwrites each run. Routed markers are upserted by destination plus normalised finding identity, with the backlink refreshed to the current hygiene report, so distinct findings coexist and reruns do not duplicate them.
- **Report is consumable.** `$weekly-review` reads the hygiene report if it exists, so findings flow into the weekly review without re-gathering.
- **Portability note.** Code snippets assume GNU coreutils (`stat -c`, `sha256sum`, GNU `date`) and ripgrep with PCRE2 support for `rg -P` — same caveat as `_shared-rules.md` §5's Linux-specific diagnostics. On macOS/BSD, substitute equivalents (`stat -f`, `shasum -a 256`, `date -v`/`-j`) and use `perl` if the installed ripgrep lacks PCRE2.

## Integration

- **Standalone:** Run mid-week for a quick cleanup
- **Pre-review:** Run before `$weekly-review` — the review will consume the hygiene report
- **Weekly-review fallback:** If `$weekly-review` finds no hygiene report, it suggests running `$weekly-hygiene` first
