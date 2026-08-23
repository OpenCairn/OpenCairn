---
name: quarterly-hygiene
description: "Quarterly deep vault maintenance: context-file review, CRM staleness, session-log archiving, skill-library flywheel audit, and panel model-currency checks."
---

# Quarterly Hygiene - Deep Vault Maintenance

You are running the quarterly deep-maintenance pass. This is the mechanical companion to `$quarterly-review` (which handles strategy), exactly as `$weekly-hygiene` is to `$weekly-review`.

It does the heavy structural checks that are too slow or too rarely-needed for the weekly pass. **It does NOT repeat `$weekly-hygiene`'s work** — broken links, orphans, dead-ends, project-doc health, Tickler, Working Memory, and the *temporal* context-staleness scan all belong to weekly-hygiene. This skill consumes weekly-hygiene's report and layers the quarterly-only deep passes on top.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   "$VAULT_PATH/.claude/scripts/check-archive-layout.sh" --enforce "$VAULT_PATH"
   ```

   If error, abort. Read `${CODEX_HOME:-$HOME/.codex}/skills/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check date and calculate quarter** using bash `date`:
   - Current date: `date +"%Y-%m-%d"`
   - Quarter: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec). File naming: `YYYY-QN.md`.
   - **Boundary rule:** if today falls in the first 2 weeks of a quarter, ask the user once whether this run covers the just-ended quarter or the current one — a quarterly pass run 2 Jul almost always covers Q2. Use the answer for the report filename and every "current quarter" comparison. If no interactive reply can be obtained, use the just-ended quarter and record `unattended boundary default` in the report's Quarter selection line. (`$quarterly-review` carries the same interactive rule; keep the two runs on the same quarter when both run interactively.)

2. **Consume the latest weekly-hygiene report (do NOT re-run its checks):**
   - Find the latest file in `{VAULT}/06 Archive/OpenCairn/Hygiene Reports/` (filename descending).
   - Compare its ISO week to the current week (`date +%G-W%V`; last week is `date -d "7 days ago" +%G-W%V` — compare the strings, don't reason about week-53 year-boundary cases yourself):
     - **Current or last week:** read and carry its unresolved structural findings into this quarterly report's "Carried from weekly-hygiene" section. Mapping: `Vault Consistency` → broken links / orphans / dead-ends; `Projects Folder` → tier mismatches; `Actions Routed` → unresolved routed items. Counts-only metrics (`Vault Structural Metrics`) are not carried — snapshots, not open work.
     - **Older than last week, or absent:** warn — "Latest weekly-hygiene report is [week / none] — vault structural state may be stale. Recommend running `$weekly-hygiene` before this pass." If a stale report exists, still carry its findings per the same mapping, labelled stale in the report's source line. Continue regardless; this skill's own deep checks run independently and never require a fresh weekly run.

### Quarterly-only deep passes

3. **Deep context-file accuracy re-read (non-temporal drift).**
   `$weekly-hygiene` step 12 scans only *temporal* markers (dates, "currently", "soon"). This is the heavier pass that catches durable facts which never trip a temporal scan and so silently rot for years:
   - Read each `{VAULT}/07 System/Context - *.md` file end-to-end.
   - Check durable claims for drift: job title / role, location, hardware specs and model numbers, active subscriptions, default tools and workflows, named collaborators/clinics. **Evidence source:** skim the weekly reviews inside the evidence window (Synthesis + Projects Active sections) for events that contradict a claim. Flag a claim only when that evidence contradicts it or another concrete inconsistency makes it suspect. Absence from the reviews is not a flag and does not trigger a claim-by-claim "still true?" quiz; record those claims collectively as not independently revalidated — this skill gathers no other activity data, and `$quarterly-review`'s full gather runs after it.
   - **Evidence window** — the run cadence is not the calendar quarter (mid-quarter and standalone runs are expected), so anchoring on the quarter start leaves reviews between the last pass and the boundary permanently unread. Window start = the `**Generated:**` date in the latest `{VAULT}/06 Archive/OpenCairn/Quarterly Hygiene Reports/*.md` (filename descending; take the date from that content header, never from mtime — `_shared-rules.md` §22), falling back to the quarter start when no prior report exists. Window end = today. State the window in the report so the next run's start is unambiguous.
   - **Guardrail (inherited from `$weekly-hygiene`'s context-file staleness step):** edit a context file ONLY with user-provided replacement text. Never rewrite, rephrase, or infer an update autonomously — these are high-trust prose documents; wrong corrections are worse than stale content. Present each flagged claim, ask, then edit only what the user supplies, using `locked-edit.sh --replace` after re-reading a unique literal OLD block.

4. **CRM stale-entry review.** (if `{VAULT}/07 System/CRM/` exists)
   `$weekly-hygiene` step 6 scans for *new* names to add. This reviews *existing* entries for decay:
   - Read the CRM index and range files.
   - Flag entries with outdated roles, superseded contact details, or context that this quarter's events have overtaken.
   - **Don't auto-modify** — present findings and let the user decide.

5. **Corrections-log fold.** (if `{VAULT}/07 System/Claude Corrections Log.md` carries distilled rules above a `## Log` tail)
   `$oops` appends verbatim entries without re-classifying them, so the log grows unboundedly and the rules above it go stale. The per-entry append is deliberately kept cheap, so the fold is a synthesis pass that belongs here, once a quarter:
   - Read the entries under `## Log`.
   - Fold each upward: another instance of a known pattern joins that rule's bracketed date list; a genuinely new failure mode becomes a proposed rule line under the right domain heading. Mark a rule proposed for supersession only when the system has since made the failure structurally impossible.
   - **Recoverability is per entry, not per repository.** Before proposing removal of a verbatim entry, verify that one Git commit for `07 System/Claude Corrections Log.md` contains that exact entry block; record the commit hash beside the proposal. A tracked file or matching heading alone is not proof. If no committed blob contains the complete block, keep the entry.
   - Present the complete proposed fold — every rule/date-list change, new rule, supersession and verbatim entry removal — and get explicit user approval before writing. Re-read the file, then apply the approved fold through one `locked-edit.sh --replace` operation against the unique literal OLD block; never edit the log directly.
   - Bump the "Last fold" date only in the approved write. Add a domain heading only when several rules cluster outside the current set; include that taxonomy change in the same approval — the buckets are a high-trust curation.

6. **Session-log archiving (90-day rolling).**
   Keep only the last ~90 days of session logs flat; roll older ones into `Session Logs/YYYY/` subfolders each quarter so the flat directory never piles into a mountain. Both consumers that resolve a log by date are subfolder-aware: `pickup-scan.sh` scans `-maxdepth 2`, and the provenance verifier (`$weekly-hygiene` 13b) falls back to `Session Logs/YYYY/YYYY-MM-DD.md` — so archived logs stay discoverable and hash-verifiable.
   - **Identify candidates once, partitioned by collision** (single-dir `ls` + date compare — not a tree walk). Cutoff is 90 days ago. List flat date-named logs older than the cutoff; skip non-date files (e.g. an Obsidian Sync "Conflicted copy"). A flat log whose destination year folder already holds that basename is a **duplicate**, not a move candidate. Persist the exact result outside the vault and reuse it for the dry-run, confirmation, move/drag set and report — never recompute after confirmation. Keep the snippet free of bare dollar-digit awk fields so its Claude sibling is not mangled by the slash-command loader; ISO date names make plain string comparison correct:
     ```bash
     CUTOFF=$(date -d "90 days ago" +%F)   # BSD/macOS: date -v-90d +%F
     LOGS="{VAULT}/06 Archive/OpenCairn/Session Logs"
     ARCHIVE_PLAN=$(mktemp -t quarterly-hygiene-archive.XXXXXX)
     ls -1 "$LOGS" | rg '^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$' | while read -r f; do
       [ "${f%.md}" \< "$CUTOFF" ] || continue
       y=${f%%-*}
       if [ -e "$LOGS/$y/$f" ]; then printf 'DUPLICATE|%s|%s\n' "$f" "$y"; else printf 'MOVE|%s|%s\n' "$f" "$y"; fi
     done > "$ARCHIVE_PLAN"
     printf 'ARCHIVE_PLAN=%s\n' "$ARCHIVE_PLAN"
     python3 -c 'import hashlib,sys; print("ARCHIVE_PLAN_SHA256=" + hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$ARCHIVE_PLAN"
     while IFS='|' read -r kind f y; do printf '%s: %s -> %s/\n' "$kind" "$f" "$y"; done < "$ARCHIVE_PLAN"
     ```
     Record the printed plan path and hash and substitute them for `<ARCHIVE_PLAN>` and `<ARCHIVE_PLAN_SHA256>` below; shell variables do not survive between tool calls. If the plan disappears or its hash changes before execution, regenerate the dry-run and reconfirm the new exact list.
   - **Dry-run and gates first:** present the persisted `MOVE` list grouped by destination year — "would move N logs → `Session Logs/2025/`, M → `Session Logs/2026/`" (real years derived from the filenames; never a literal `YYYY` folder) — and the `DUPLICATE` count alongside it, by name if few. Confirm the vault's sync client is ON (or that the vault has none), then get explicit confirmation to move this exact list. If no interactive reply can be obtained, the run is unattended: report both lists, move nothing and continue to the report; the confirmation gate cannot be waived.
   - **Duplicates are a finding, not a cleanup.** Never delete or overwrite either copy to resolve a collision — surface the on-disk duplication in the report and leave the files alone (same contract `$weekly-hygiene` holds for duplicate detection). If the user does ask for a resolution, the safe order is: byte-compare the pair and **refuse on any difference**, delete the *archived* copy, then move the flat copy into place with a link-aware move — the flat copy is the one inbound links resolve to, so it must be the survivor. Treat a refusal per `_shared-rules.md` §24 before calling it genuine. The user decides.
   - **Move each confirmed file through `locked-edit.sh --move`.** Drive the persisted `MOVE` rows per **`_shared-rules.md` §24**, which owns the locks, Obsidian CLI behaviour and verification. Create each required destination-year folder in that list, then move each file; treat the first as a canary and abort the batch on any refusal:
     ```bash
     LOGS="{VAULT}/06 Archive/OpenCairn/Session Logs"
     actual_plan_sha256="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "<ARCHIVE_PLAN>")"
     [ "$actual_plan_sha256" = "<ARCHIVE_PLAN_SHA256>" ] || { echo "ABORT: archive plan changed; regenerate and reconfirm"; exit 1; }
     while IFS='|' read -r kind f y; do
       [ "$kind" = "MOVE" ] || continue
       mkdir -p "$LOGS/$y"
       if [ -e "$LOGS/$y/$f" ]; then echo "SKIP (exists): $f"; continue; fi
       source_path="$LOGS/$f"
       destination_path="$LOGS/$y/$f"
       source_sha256="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$source_path")"
       if "{VAULT}/.claude/scripts/locked-edit.sh" "$source_path" --move "$destination_path" "$source_sha256" </dev/null; then
         echo "MOVED: $f -> $y/"
       else
         echo "ABORT: verified move failed for $f"
         exit 1
       fi
     done < "<ARCHIVE_PLAN>"
     ```
     The wrapper's expected hash is the source snapshot for that invocation. See **`_shared-rules.md` §24** for the failure contract; do not reproduce its internal CLI mechanics here.
   - **Obsidian GUI drag-and-drop is an equivalent alternative** if the user would rather do it by hand: have them multi-select **only the `MOVE` files** and drag each year's batch into its folder — colliding basenames stay out of the drag set, since Obsidian's behaviour on a name clash (rename vs refuse) is not something this skill should gamble the original on. Report the count once the user confirms the drag is done.
   - **⛔ Never fall back to raw `mv`** — per **`_shared-rules.md` §24**, which also explains why a "globally unique basename" exception does not exist. If a link-aware move is unavailable, **move nothing**: report the `MOVE` list and defer the roll. Session logs cross-link each other densely, so one moved date can strand dozens of inbound links, and a roll that relocates the files while orphaning their links is worse than a roll not run.
     Count the `SKIP (exists)` lines and carry the number into the report's skipped bullet — a silent skip is how duplication survives a pass that claims to be clean.
   - **Verify link integrity and put the numbers in the report** — §24's before/after unresolved-link counts, plus a confirmation that no moved date appears as an unresolved target. Record both totals in the report's link-integrity bullet; a roll reporting no numbers has verified nothing.
   - Record the confirmed sync state in the report. A structural batch run with sync off gets silently resurrected on the next reconnect — mechanism in §24.
   - **Idempotent for moves, not for duplicates:** files already inside a `YYYY/` subfolder are never re-listed by the flat `ls`, so re-running only moves newly-aged logs. A skipped collision is the exception — the flat copy stays flat and older than every future cutoff, so it resurfaces each run. The `MOVE`/`DUPLICATE` partition is what keeps it distinguishable from a newly-aged log rather than padding the move count forever.

7. **Skill-library flywheel audit (DRAFT SPEC — heuristics unvalidated; propose, never auto-apply; optional — skip freely on first runs or when time-boxed, noting "flywheel audit skipped" in the report).**
   The library-level layer of the cross-pollination system uses `${CODEX_HOME:-$HOME/.codex}/skills/_shared-patterns.md` as its index. Some installations also maintain a Claude-side skill-edit Stop hook and `~/.claude/cross-pollination.log`; treat those as optional evidence, not Codex prerequisites. Once a quarter, look across the **user-authored skill library** for infrastructure that's been reinvented rather than shared. System skills under `.system/` and versioned plugin-cache skills are vendor-owned and explicitly out of scope; proposing their consolidation into a personal index would create unstable pointers. Borrowed from Voyager's automatic-curriculum idea: the system proposes its own next consolidation. **Status: spec — the grep heuristics below are untested; treat every finding as a lead to confirm, not a verdict.**
   - **Inventory** first-level personal `${CODEX_HOME:-$HOME/.codex}/skills/*/SKILL.md` files and any project-local `.agents/skills/*/SKILL.md` files. State this scope in the report. Derive the search targets rather than working a fixed list — a hardcoded list drifts into naming only mechanisms already indexed, which makes the "unindexed" branch unreachable and the audit a no-op:
     - Extract the already-indexed mechanisms from `_shared-patterns.md` (its entry headings / `→` reference targets). These are the *divergence* candidates.
     - Then grep the skills for repeated constructs **not** on that list — recurring bash idioms, repeated prose contracts, shared prereq/estimation/progress/despatch shapes, any block that reads as copied between skills — and count distinct skills implementing each. These are the *discovery* candidates, and they are the point of the pass.
   - **Cross-reference `_shared-patterns.md`:** a mechanism in **≥2 skills but unindexed** → propose a pointer entry (it passes the proven-twice gate); **indexed but reimplemented divergently** → flag for reconciliation.
   - **Read `~/.claude/cross-pollination.log` only if it exists** (`[ -f ~/.claude/cross-pollination.log ]`): index entries that never surface in any survey are prune candidates; frequently-ported patterns confirm hot ones. If absent, record "cross-pollination log not found — cold-entry/prune analysis skipped" and run only the inventory + divergence checks. Never propose prunes without survey data — no log means no evidence of coldness, and treating absence as coldness would nominate the entire healthy index for deletion.
   - **Report, don't apply.** Emit proposed new entries, divergence flags, and dead entries — each a human-confirmed decision.

8. **Cross-model panel model-currency check.** (if any of the panel seats from `_shared-rules.md` §10 are installed; if none are, note "no cross-model panel configured — model-currency check skipped" in the report)
   Panel seats resolve their models in three different ways — a session-inherited seat floats with the session, a CLI-default seat moves with CLI updates, and a config/script pin stays put until edited — so pinned seats silently fall behind frontier releases with no signal. Once a quarter, resolve each installed seat's *actual* model and compare it against the provider's current lineup:
   - **Resolve, don't recall.** Read each seat's actual model per §10's *seat model resolution* bullet — the single source of truth for where each seat's pin lives and how to probe an unpinned CLI default; do not recite config paths from memory or from this file.
   - **Compare against the provider's current lineup, fetched fresh this run:** the provider's models endpoint where a key is available (per §10), otherwise current official provider documentation via Codex web tooling. Never judge currency from memory — training-data staleness is exactly the failure this check exists to catch.
   - **Flag two conditions:** (a) a pin that is no longer the provider's strongest reasoning model; (b) a pin on an unstable alias (`-preview`, `-exp`, an undated "latest" alias) — providers deprecate and repoint these without notice, so propose the stable id even when the underlying model is current.
   - **Present, don't auto-bump.** A model bump can invalidate verified seat behaviour — read-only policy guarantees, tool-call guards, context-size and pricing caps tuned to a specific model (see §10). Propose each bump as a one-line config change; on user confirmation, apply it and run a one-line smoke test of that seat before reporting it done.

### Output

9. **Write the quarterly hygiene report:**
   ```bash
   mkdir -p "{VAULT}/06 Archive/OpenCairn/Quarterly Hygiene Reports"
   ```
   Draft outside the vault, then write `{VAULT}/06 Archive/OpenCairn/Quarterly Hygiene Reports/YYYY-QN.md` through `"{VAULT}/.claude/scripts/locked-edit.sh"`. When missing, immediately confirm the path is absent and create it with `--replace-whole MISSING`; exit 2 means another writer created it, so re-read that file and continue through the existing-report path. When the file already exists, it remains the quarter's canonical mutable hand-off: before replacement, carry every unresolved report-only corrections-fold proposal, flywheel proposal and pending panel-model action into the new draft unless the user resolved or rejected it this run; routed items stay in their destination SSOTs. Re-read the old report and use its full contents as literal OLD with `--replace`. Never create the report with `--append` or write it directly.

   **⛔ Cite report items by stable identifier, not line number** — see `_shared-rules.md` §13. Reference any project-doc / `Tickler.md` item by title/heading/content, never by line number; structural maintenance this run shifts line numbers, so an `Lnn` reference is stale on write.

   ```markdown
   # Quarterly Hygiene Report - YYYY QN

   **Generated:** YYYY-MM-DD
   **Quarter selection:** [calendar current quarter / user-confirmed just-ended or current / unattended boundary default: just-ended]
   **Status:** [Clean / N issues found]

   ## Carried from Weekly-Hygiene
   *Source: Hygiene Reports/YYYY-Wnn (current / stale — re-run recommended / not found)*
   - [Unresolved broken links, orphans, dead-ends, tier mismatches from the weekly report — not re-derived]

   ## Context Files (deep, non-temporal)
   *Evidence window: YYYY-MM-DD → YYYY-MM-DD (previous report's Generated date / quarter start — no prior report)*
   | File | Status | Durable claim flagged | Resolution |
   |------|--------|----------------------|------------|
   | Context - X.md | Stale | [claim] | [user-provided fix / pending] |

   ## CRM Stale Entries
   - [Entry — what's outdated]

   ## Corrections-Log Fold
   - Entries folded into rules since last fold: N (or "no distilled rules section present")
   - New rules added: N · merged into existing: N · marked superseded: N
   - "Last fold" date bumped: [YYYY-MM-DD / n/a]
   - Fold pending approval: [summary of proposed changes / none]

   ## Session-Log Archiving
   - Flat session logs: N (keeping last ~90 days flat)
   - Archived this run: N logs → YYYY/ subfolders (or "none — nothing older than 90 days")
   - Skipped (already archived): N — flat copies whose year folder already holds that basename; duplication surfaced, nothing deleted [list or "none"]
   - Link integrity: before N → after M; moved dates unresolved: [none / list / n/a — nothing moved]

   ## Skill-Library Flywheel (draft)
   - Proposed new index entries (≥2 reuses, unindexed): [list or "none"]
   - Divergent reimplementations of indexed patterns: [list or "none"]
   - Dead/cold index entries (never surfaced): [list or "none"]

   ## Panel Model Currency
   | Seat | Resolved model | Pin source | Current? | Proposed action |
   |------|---------------|------------|----------|-----------------|
   | [seat] | [model id] | [config path / CLI default / session] | [yes / stale / unstable alias] | [bump to X — pending / applied + smoke-tested / none] |

   (or "no cross-model panel configured — model-currency check skipped")

   ## Actions Taken / Routed
   - [Confirmed edits applied this run]
   - [Unresolved items the user didn't engage with → the relevant project/area doc, else Tickler +7d via `write-tickler.sh`, back-linked: `[description] → [[06 Archive/OpenCairn/Quarterly Hygiene Reports/YYYY-QN|Quarterly QN]]`]
   - [Flywheel proposals stay in this report as pending user decisions — they are not routed]
   ```

   **Routing is an upsert.** Key each routed item by its normalised description plus quarterly-report backlink. Search the destination before writing; update an existing matching item through `locked-edit.sh`, or create it once. Never append a second copy on a same-quarter rerun. Tickler additions always use `write-tickler.sh`.

10. **Skill self-review (quarterly cadence — explicit instantiation of `_shared-rules.md` §8 Skill Monitor / `_skill-monitor.md`).**
   The §8 skill-monitor already applies to every command, but this one runs ~4×/year, so the implicit watch is easy to skip and per-run friction evaporates between invocations. Make it an emitted checkpoint: before the final display, run the §8 / `_skill-monitor.md` review against *this* run end-to-end — did any step misfire, produce mostly noise, mandate a tool that didn't work, or require an undocumented improvisation? If so, log observations per `_skill-monitor.md` for weekly processing. If clean, state `✓ Skill self-review: no gaps this run`.

11. **Display confirmation:**
   ```
   ✓ Quarterly hygiene report: 06 Archive/OpenCairn/Quarterly Hygiene Reports/YYYY-QN.md
   ✓ Weekly-hygiene report: [carried / carried (stale — re-run recommended) / not found]
   ✓ Context files re-read: N, M durable-drift flags
   ✓ CRM stale entries: N flagged
   ✓ Corrections-log fold: [applied (N entries folded) / pending approval / no distilled rules section / no log]
   ✓ Session logs: N flat; archived M → YYYY/ (or "none aged out"); K skipped as duplicates
   ✓ Link integrity: before N → after M; moved dates unresolved: [none / list / n/a — nothing moved]
   ✓ Flywheel audit (draft): [N proposed entries, M divergences, K dead / skipped]
   ✓ Panel model currency: [N seats checked, M stale/unstable pins flagged / no panel configured]
   ✓ Skill self-review: [no gaps / N observations logged]

   Quarterly hygiene complete. Run $quarterly-review to fold these findings into the strategic review.
   ```

## Guidelines

- **Mechanical, not reflective.** Structural checks and flags only. `$quarterly-review` handles strategy, alignment, and planning.
- **No re-doing weekly-hygiene.** Broken links, orphans, dead-ends, tier reconciliation, temporal context-staleness — all weekly's job. This command reads weekly's report; it does not re-scan.
- **User confirmation for context files and CRM.** High-trust; wrong corrections beat stale content only if the user supplied them. Never infer an update.
- **Bound tree-walk cost on the vault — don't ban tools by name.** The expensive case is reading *content* across untracked mass (an unbounded `--no-ignore` sweep at the vault root, an unfiltered `grep -r`); an ignore-respecting `rg` or a metadata-only `find` usually is not. Structural queries still route to the Obsidian CLI. Check the vault's search-routing doc for the permitted/prohibited split before assuming any tool is barred outright.
- **Portability note.** `date -d` is GNU-only — on macOS/BSD substitute `date -v-90d +%F` (same caveat family as weekly-hygiene's Guidelines).
- **Report is consumable.** `$quarterly-review` reads this report so findings flow into the strategic review without re-gathering — the same contract `$weekly-review` has with `$weekly-hygiene`.

## Frequency

Quarterly (last week of March, June, September, December), or as a precursor to `$quarterly-review`. Can also run standalone for a mid-quarter deep clean.

## Integration

- **Feeds `$quarterly-review`:** the strategic review consumes this report for its Vault Health section.
- **Consumes `$weekly-hygiene`:** carries forward unresolved structural findings rather than re-scanning.
- **Archives session logs:** inventories logs older than 90 days and rolls confirmed files into `Session Logs/YYYY/` through `locked-edit.sh --move`; unattended runs stop after the dry run.
