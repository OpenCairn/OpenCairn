---
name: quarterly-hygiene
description: Quarterly deep vault maintenance — heavy structural checks too slow or too rarely-needed for weekly: full context-file re-read, CRM stale-entry review, oversized/near-empty files, session-log archiving recommendation
---

# Quarterly Hygiene - Deep Vault Maintenance

You are running the quarterly deep-maintenance pass. This is the mechanical companion to `/quarterly-review` (which handles strategy), exactly as `/weekly-hygiene` is to `/weekly-review`.

It does the heavy structural checks that are too slow or too rarely-needed for the weekly pass. **It does NOT repeat `/weekly-hygiene`'s work** — broken links, orphans, dead-ends, WIP/tier reconciliation, Tickler, Working Memory, and the *temporal* context-staleness scan all belong to weekly-hygiene. This command consumes weekly-hygiene's report and layers the quarterly-only deep passes on top.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check date and calculate quarter** using bash `date`:
   - Current date: `date +"%Y-%m-%d"`
   - Quarter: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec). File naming: `YYYY-QN.md`.

2. **Consume the latest weekly-hygiene report (do NOT re-run its checks):**
   - Find the latest file in `{VAULT}/06 Archive/Claude/Hygiene Reports/` (filename descending).
   - Compare its ISO week to the current week (`date +%G-W%V`):
     - **Current or last week:** read and carry its unresolved structural findings (broken links, orphans, tier mismatches, dead-ends) into this quarterly report's "Carried from weekly-hygiene" section.
     - **Older than last week, or absent:** warn — "Latest weekly-hygiene report is [week / none] — vault structural state may be stale. Recommend running `/weekly-hygiene` before this pass." Continue regardless; this command's own deep checks run independently and never require a fresh weekly run.

### Quarterly-only deep passes

3. **Deep context-file accuracy re-read (non-temporal drift).**
   `/weekly-hygiene` step 13 scans only *temporal* markers (dates, "currently", "soon"). This is the heavier pass that catches durable facts which never trip a temporal scan and so silently rot for years:
   - Read each `{VAULT}/07 System/Context - *.md` file end-to-end.
   - Check durable claims against this quarter's activity: job title / role, location, hardware specs and model numbers, active subscriptions, default tools and workflows, named collaborators/clinics.
   - **Guardrail (inherited from weekly-hygiene 13):** edit a context file ONLY with user-provided replacement text. Never rewrite, rephrase, or infer an update autonomously — these are high-trust prose documents; wrong corrections are worse than stale content. Present each flagged claim, ask, then edit only what the user supplies.

4. **CRM stale-entry review.** (if `{VAULT}/07 System/CRM/` exists)
   `/weekly-hygiene` step 7 scans for *new* names to add. This reviews *existing* entries for decay:
   - Read the CRM index and range files.
   - Flag entries with outdated roles, superseded contact details, or context that this quarter's events have overtaken.
   - **Don't auto-modify** — present findings and let the user decide.

5. **Oversized / near-empty files.**
   - Line-count detection needs a one-off tree walk (the Obsidian CLI reports file *count*, not line counts). Per `_shared-rules` (no recursive bash on the vault), **ask before running it.** On approval, scan the local vault copy (`{VAULT}`) — not a network or cloud mount, where bulk reads can stall — excluding archive and system dirs:
     ```bash
     find "{VAULT}" -name "*.md" -type f \
       -not -path "*/.stversions/*" -not -path "*/06 Archive/*" -not -path "*/.obsidian/*" \
       -exec wc -l {} + | awk '$2!="total" && ($1>500 || $1<5)'
     ```
   - Apply the `{VAULT}/.claude/hygiene-excludes` filter if it exists (same pattern as weekly-hygiene step 12) to drop large embedded doc sets (darktable, Hugo themes).
   - Oversized (>500 lines): split candidates. Near-empty (<5 lines): merge-or-delete candidates. Present candidates; the user triages. Splits/merges/deletes are confirmed, never automatic.

6. **Session-log archiving (90-day rolling).**
   Keep only the last ~90 days of session logs flat; roll older ones into `Session Logs/YYYY/` subfolders each quarter so the flat directory never piles into a mountain. Both consumers that resolve a log by date are subfolder-aware: `pickup-scan.sh` scans `-maxdepth 2`, and the provenance verifier (`/weekly-hygiene` 14b) falls back to `Session Logs/YYYY/YYYY-MM-DD.md` — so archived logs stay discoverable and hash-verifiable.
   - **Identify candidates** (single-dir `ls` + date compare — not a tree walk). Cutoff is 90 days ago (`date -d "90 days ago" +%F`). List flat date-named logs older than the cutoff; skip non-date files (e.g. an Obsidian Sync "Conflicted copy"):
     ```bash
     CUTOFF=$(date -d "90 days ago" +%F)
     ls -1 "{VAULT}/06 Archive/Claude/Session Logs/" \
       | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$' \
       | awk -F. -v c="$CUTOFF" '$1 < c {print}'
     ```
   - **Dry-run first:** present the candidate list grouped by destination year — "would move N logs → `Session Logs/YYYY/`". Get explicit confirmation before moving anything.
   - **On confirm, move with `obsidian move`** (heals wikilinks — never raw `mv`). Create the year folder first (single-dir `mkdir`, not a tree walk), then move each log; the destination year is the log date's year:
     ```bash
     mkdir -p "{VAULT}/06 Archive/Claude/Session Logs/2025"
     obsidian move path="06 Archive/Claude/Session Logs/2025-01-15.md" \
                   to="06 Archive/Claude/Session Logs/2025/2025-01-15.md"
     ```
   - **Idempotent:** files already inside a `YYYY/` subfolder are never re-listed by the flat `ls`, so re-running only moves newly-aged logs.
   - Report the count moved per year in the hygiene report.

### Output

7. **Write the quarterly hygiene report:**
   ```bash
   mkdir -p "{VAULT}/06 Archive/Claude/Quarterly Hygiene Reports"
   ```
   Write to `{VAULT}/06 Archive/Claude/Quarterly Hygiene Reports/YYYY-QN.md`:

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

   ## Oversized / Near-Empty Files
   - Oversized (>500 lines): [list or "none"]
   - Near-empty (<5 lines): [list or "none"]

   ## Session-Log Archiving
   - Flat session logs: N (keeping last ~90 days flat)
   - Archived this run: N logs → YYYY/ subfolders (or "none — nothing older than 90 days")

   ## Actions Taken / Routed
   - [Confirmed edits applied; everything else routed with ⚠ markers per weekly-hygiene's three-tier model]
   ```

8. **Display confirmation:**
   ```
   ✓ Quarterly hygiene report: 06 Archive/Claude/Quarterly Hygiene Reports/YYYY-QN.md
   ✓ Weekly-hygiene report: [carried / stale — re-run / not found]
   ✓ Context files re-read: N, M durable-drift flags
   ✓ CRM stale entries: N flagged
   ✓ Oversized/near-empty: N / M
   ✓ Session logs: N flat; archived M → YYYY/ (or "none aged out")

   Quarterly hygiene complete. Run /quarterly-review to fold these findings into the strategic review.
   ```

## Guidelines

- **Mechanical, not reflective.** Structural checks and flags only. `/quarterly-review` handles strategy, alignment, and planning.
- **No re-doing weekly-hygiene.** Broken links, orphans, dead-ends, tier reconciliation, temporal context-staleness — all weekly's job. This command reads weekly's report; it does not re-scan.
- **User confirmation for context files and CRM.** High-trust; wrong corrections beat stale content only if the user supplied them. Never infer an update.
- **No recursive bash on the vault.** Use the Obsidian CLI for structural queries; single-directory `ls` is fine, tree walks are not.
- **Report is consumable.** `/quarterly-review` reads this report so findings flow into the strategic review without re-gathering — the same contract `/weekly-review` has with `/weekly-hygiene`.

## Frequency

Quarterly (last week of March, June, September, December), or as a precursor to `/quarterly-review`. Can also run standalone for a mid-quarter deep clean.

## Integration

- **Feeds `/quarterly-review`:** the strategic review consumes this report for its Vault Health section.
- **Consumes `/weekly-hygiene`:** carries forward unresolved structural findings rather than re-scanning.
- **Archives session logs:** rolls logs older than 90 days into `Session Logs/YYYY/` each quarter (dry-run-then-confirm, `obsidian move`); keeps the flat directory to ~one quarter of logs.
