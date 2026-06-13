---
name: quarterly-hygiene
description: Quarterly deep vault maintenance — heavy structural checks too slow or too rarely-needed for weekly: full context-file re-read, CRM stale-entry review, session-log archiving, skill-library flywheel audit
---

# Quarterly Hygiene - Deep Vault Maintenance

You are running the quarterly deep-maintenance pass. This is the mechanical companion to `/quarterly-review` (which handles strategy), exactly as `/weekly-hygiene` is to `/weekly-review`.

It does the heavy structural checks that are too slow or too rarely-needed for the weekly pass. **It does NOT repeat `/weekly-hygiene`'s work** — broken links, orphans, dead-ends, WIP/tier reconciliation, Tickler, Working Memory, and the *temporal* context-staleness scan all belong to weekly-hygiene. This command consumes weekly-hygiene's report and layers the quarterly-only deep passes on top.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check date and calculate quarter** using bash `date`:
   - Current date: `date +"%Y-%m-%d"`
   - Quarter: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec). File naming: `YYYY-QN.md`.
   - **Boundary rule:** if today falls in the first 2 weeks of a quarter, ask the user once whether this run covers the just-ended quarter or the current one — a quarterly pass run 2 Jul almost always covers Q2. Use the answer for the report filename and every "current quarter" comparison. (`/quarterly-review` carries the same rule; keep the two runs on the same quarter.)

2. **Consume the latest weekly-hygiene report (do NOT re-run its checks):**
   - Find the latest file in `{VAULT}/06 Archive/Claude/Hygiene Reports/` (filename descending).
   - Compare its ISO week to the current week (`date +%G-W%V`; last week is `date -d "7 days ago" +%G-W%V` — compare the strings, don't reason about week-53 year-boundary cases yourself):
     - **Current or last week:** read and carry its unresolved structural findings into this quarterly report's "Carried from weekly-hygiene" section. Mapping: `Vault Consistency` → broken links / orphans / dead-ends; `Projects Folder` → tier mismatches; `Actions Routed` → unresolved routed items. Counts-only metrics (`Vault Structural Metrics`) are not carried — snapshots, not open work.
     - **Older than last week, or absent:** warn — "Latest weekly-hygiene report is [week / none] — vault structural state may be stale. Recommend running `/weekly-hygiene` before this pass." If a stale report exists, still carry its findings per the same mapping, labelled stale in the report's source line. Continue regardless; this command's own deep checks run independently and never require a fresh weekly run.

### Quarterly-only deep passes

3. **Deep context-file accuracy re-read (non-temporal drift).**
   `/weekly-hygiene` step 13 scans only *temporal* markers (dates, "currently", "soon"). This is the heavier pass that catches durable facts which never trip a temporal scan and so silently rot for years:
   - Read each `{VAULT}/07 System/Context - *.md` file end-to-end.
   - Check durable claims for drift: job title / role, location, hardware specs and model numbers, active subscriptions, default tools and workflows, named collaborators/clinics. **Evidence source:** skim the quarter's weekly reviews (Synthesis + Projects Active sections) for events that contradict a claim; for claims not covered there, present to the user as a "still true?" check rather than asserting drift — this skill gathers no other activity data, and `/quarterly-review`'s full gather runs after it.
   - **Guardrail (inherited from weekly-hygiene 13):** edit a context file ONLY with user-provided replacement text. Never rewrite, rephrase, or infer an update autonomously — these are high-trust prose documents; wrong corrections are worse than stale content. Present each flagged claim, ask, then edit only what the user supplies.

4. **CRM stale-entry review.** (if `{VAULT}/07 System/CRM/` exists)
   `/weekly-hygiene` step 7 scans for *new* names to add. This reviews *existing* entries for decay:
   - Read the CRM index and range files.
   - Flag entries with outdated roles, superseded contact details, or context that this quarter's events have overtaken.
   - **Don't auto-modify** — present findings and let the user decide.

5. **Session-log archiving (90-day rolling).**
   Keep only the last ~90 days of session logs flat; roll older ones into `Session Logs/YYYY/` subfolders each quarter so the flat directory never piles into a mountain. Both consumers that resolve a log by date are subfolder-aware: `pickup-scan.sh` scans `-maxdepth 2`, and the provenance verifier (`/weekly-hygiene` 14b) falls back to `Session Logs/YYYY/YYYY-MM-DD.md` — so archived logs stay discoverable and hash-verifiable.
   - **Identify candidates** (single-dir `ls` + date compare — not a tree walk). Cutoff is 90 days ago. List flat date-named logs older than the cutoff; skip non-date files (e.g. an Obsidian Sync "Conflicted copy"). Written without bare dollar-digit awk fields — the slash-command loader substitutes `$0`–`$9` as argument placeholders and would mangle them before the executor sees the snippet; ISO date names make plain string comparison correct:
     ```bash
     CUTOFF=$(date -d "90 days ago" +%F)   # BSD/macOS: date -v-90d +%F
     ls -1 "{VAULT}/06 Archive/Claude/Session Logs/" \
       | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$' \
       | while read -r f; do [ "${f%.md}" \< "$CUTOFF" ] && echo "$f"; done
     ```
   - **Dry-run first:** present the candidate list grouped by destination year — "would move N logs → `Session Logs/2025/`, M → `Session Logs/2026/`" (real years derived from the filenames; never a literal `YYYY` folder). Get explicit confirmation before moving anything. **Unattended runs (cron, headless automation) stop here** — report the candidate list and move nothing; the confirmation gate cannot be waived.
   - **Move via Obsidian GUI drag-and-drop (preferred — heals wikilinks instantly).** Create one year folder per destination year in the candidate list (single-dir `mkdir -p ".../Session Logs/2025"` etc.), then hand off to the user: have them multi-select the aged logs in Obsidian's file explorer and drag each year's batch into its folder. Obsidian rewrites every inbound wikilink in one pass — a few seconds for the whole set. Report the count once the user confirms the drag is done.
     **Do NOT use the `obsidian move` CLI for batches** — it boots a fresh Electron instance per call (loading the entire vault index) and deadlocks on the single-instance lock after a handful of files. Fine for a one-off move, unusable for a batch.
   - **Fallback for interactive sessions without the Obsidian GUI: raw `mv`, after the dry-run confirmation.** Session logs have globally-unique `YYYY-MM-DD.md` basenames, so Obsidian resolves a stale-path wikilink by basename fallback — a *scoped* exception to the general "never raw `mv`" rule. One loop does year-derivation, folder creation, collision refusal, and reporting:
     ```bash
     CUTOFF=$(date -d "90 days ago" +%F)   # BSD/macOS: date -v-90d +%F
     LOGS="{VAULT}/06 Archive/Claude/Session Logs"
     ls -1 "$LOGS" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$' | while read -r f; do
       [ "${f%.md}" \< "$CUTOFF" ] || continue
       y=${f%%-*}
       mkdir -p "$LOGS/$y"
       if [ -e "$LOGS/$y/$f" ]; then echo "SKIP (exists): $f"
       else mv "$LOGS/$f" "$LOGS/$y/$f" && echo "MOVED: $f -> $y/"; fi
     done
     ```
     Full CLI link-verification is still skipped (`obsidian unresolved`/`backlinks` time out mid-reindex on a large vault) — but the basename-fallback claim is GUI behaviour this repo can't prove, so **spot-check once per run**: pick one moved log with a known inbound link and confirm it resolves (in the GUI next session, or `obsidian unresolved` filtered to that basename once reindex settles). Record the result in the report.
   - **Idempotent:** files already inside a `YYYY/` subfolder are never re-listed by the flat `ls`, so re-running only moves newly-aged logs.

6. **Skill-library flywheel audit (DRAFT SPEC — heuristics unvalidated; propose, never auto-apply; optional — skip freely on first runs or when time-boxed, noting "flywheel audit skipped" in the report).**
   The library-level layer of the cross-pollination system — the per-edit layer is the skill-edit Stop hook (not yet shipped with the template — personal installs only; see `_shared-patterns.md`), the index is `_shared-patterns.md` (commands directory). Once a quarter, look across *all* skills for infrastructure that's been reinvented rather than shared. Borrowed from Voyager's automatic-curriculum idea: the system proposes its own next consolidation. **Status: spec — the grep heuristics below are untested; treat every finding as a lead to confirm, not a verdict.**
   - **Inventory** the commands directory (`~/.claude/commands/*.md` or `{VAULT}/.claude/commands/*.md`); grep for recurring mechanisms (manifest/JSONL + resume, `[i/N]` progress strings, parallel `gemini`/`codex` despatch, file-size + resize loops, `command -v` prereq blocks, cost estimation) and count distinct skills implementing each.
   - **Cross-reference `_shared-patterns.md`:** a mechanism in **≥2 skills but unindexed** → propose a pointer entry (it passes the proven-twice gate); **indexed but reimplemented divergently** → flag for reconciliation.
   - **Read `~/.claude/cross-pollination.log` — only if it exists** (`[ -f ~/.claude/cross-pollination.log ]`): index entries that never surface in any survey are prune candidates; frequently-ported patterns confirm hot ones. **If absent** (every template install without the Stop hook), record "cross-pollination log not found — cold-entry/prune analysis skipped" and run only the inventory + divergence checks. Never propose prunes without survey data — no log means no evidence of coldness, and treating absence as coldness would nominate the entire healthy index for deletion.
   - **Report, don't apply.** Emit proposed new entries, divergence flags, and dead entries — each a human-confirmed decision.

### Output

7. **Write the quarterly hygiene report:**
   ```bash
   mkdir -p "{VAULT}/06 Archive/Claude/Quarterly Hygiene Reports"
   ```
   Write to `{VAULT}/06 Archive/Claude/Quarterly Hygiene Reports/YYYY-QN.md`:

   **⛔ Cite report items by stable identifier, not line number** — see `_shared-rules.md` §13. Reference any `Tasks.md` / WIP / `Tickler.md` item by title/heading/content, never by line number; structural maintenance this run shifts line numbers, so an `Lnn` reference is stale on write.

   ```markdown
   # Quarterly Hygiene Report - YYYY QN

   **Generated:** YYYY-MM-DD
   **Status:** [Clean / N issues found]

   ## Carried from Weekly-Hygiene
   *Source: Hygiene Reports/YYYY-Wnn (current / stale — re-run recommended / not found)*
   - [Unresolved broken links, orphans, dead-ends, tier mismatches from the weekly report — not re-derived]

   ## Context Files (deep, non-temporal)
   | File | Status | Durable claim flagged | Resolution |
   |------|--------|----------------------|------------|
   | Context - X.md | Stale | [claim] | [user-provided fix / pending] |

   ## CRM Stale Entries
   - [Entry — what's outdated]

   ## Session-Log Archiving
   - Flat session logs: N (keeping last ~90 days flat)
   - Archived this run: N logs → YYYY/ subfolders (or "none — nothing older than 90 days")

   ## Skill-Library Flywheel (draft)
   - Proposed new index entries (≥2 reuses, unindexed): [list or "none"]
   - Divergent reimplementations of indexed patterns: [list or "none"]
   - Dead/cold index entries (never surfaced): [list or "none"]

   ## Actions Taken / Routed
   - [Confirmed edits applied this run]
   - [Unresolved items the user didn't engage with → Tasks.md, weekly-hygiene's tier-2 fallback form: `- [ ] [description] → [[06 Archive/Claude/Quarterly Hygiene Reports/YYYY-QN|Quarterly QN]]`]
   - [Flywheel proposals stay in this report as pending user decisions — they are not routed]
   ```

8. **Skill self-review (quarterly cadence — explicit instantiation of `_shared-rules.md` §8 Skill Monitor / `_skill-monitor.md`).**
   The §8 skill-monitor already applies to every command, but this one runs ~4×/year, so the implicit watch is easy to skip and per-run friction evaporates between invocations. Make it an emitted checkpoint: before the final display, run the §8 / `_skill-monitor.md` review against *this* run end-to-end — did any step misfire, produce mostly noise, mandate a tool that didn't work, or require an undocumented improvisation? If so, propose specific edits to this skill file (display for user approval — never auto-apply; edit the template copy if template-synced). If clean, state `✓ Skill self-review: no gaps this run`.

9. **Display confirmation:**
   ```
   ✓ Quarterly hygiene report: 06 Archive/Claude/Quarterly Hygiene Reports/YYYY-QN.md
   ✓ Weekly-hygiene report: [carried / carried (stale — re-run recommended) / not found]
   ✓ Context files re-read: N, M durable-drift flags
   ✓ CRM stale entries: N flagged
   ✓ Session logs: N flat; archived M → YYYY/ (or "none aged out")
   ✓ Flywheel audit (draft): [N proposed entries, M divergences, K dead / skipped]
   ✓ Skill self-review: [no gaps / N edits proposed]

   Quarterly hygiene complete. Run /quarterly-review to fold these findings into the strategic review.
   ```

## Guidelines

- **Mechanical, not reflective.** Structural checks and flags only. `/quarterly-review` handles strategy, alignment, and planning.
- **No re-doing weekly-hygiene.** Broken links, orphans, dead-ends, tier reconciliation, temporal context-staleness — all weekly's job. This command reads weekly's report; it does not re-scan.
- **User confirmation for context files and CRM.** High-trust; wrong corrections beat stale content only if the user supplied them. Never infer an update.
- **No recursive bash on the vault.** Use the Obsidian CLI for structural queries; single-directory `ls` is fine, tree walks are not.
- **Portability note.** `date -d` is GNU-only — on macOS/BSD substitute `date -v-90d +%F` (same caveat family as weekly-hygiene's Guidelines).
- **Report is consumable.** `/quarterly-review` reads this report so findings flow into the strategic review without re-gathering — the same contract `/weekly-review` has with `/weekly-hygiene`.

## Frequency

Quarterly (last week of March, June, September, December), or as a precursor to `/quarterly-review`. Can also run standalone for a mid-quarter deep clean.

## Integration

- **Feeds `/quarterly-review`:** the strategic review consumes this report for its Vault Health section.
- **Consumes `/weekly-hygiene`:** carries forward unresolved structural findings rather than re-scanning.
- **Archives session logs:** rolls logs older than 90 days into `Session Logs/YYYY/` each quarter (dry-run-then-confirm, then Obsidian GUI drag-and-drop; raw `mv` fallback for interactive no-GUI sessions — unattended runs stop at the dry-run); keeps the flat directory to ~one quarter of logs.
