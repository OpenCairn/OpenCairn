---
name: goodnight
description: End-of-day close-out - accountability, route undone items, daily report
---

# Goodnight - End-of-Day Status Report

You are running the user's end-of-day operational close-out. This is a technical/PM-focused review - think engineering standup for yourself, not therapy session.

## Philosophy

The goal is clean handoff to tomorrow-you:
- **Inventory** - what's the state of everything?
- **Accountability** - what got done?
- **Context** - what would tomorrow-you need to know to hit the ground running?

This is the complement to `/morning` - morning surfaces the landscape, goodnight closes the books.

## Instructions

### 0. Resolve Vault Path

Determine the vault base path. Run:

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

### 1. Check current date/time and concurrent sessions

```bash
date +"%A, %d %b %Y — %H:%M %Z"  # friendly display with time and timezone
date +"%Y-%m-%d"                   # for file paths and session timestamp
```

**Concurrent session check:** Count active Claude instances (excluding this one):

```bash
OTHER_CLAUDE=$(( $(pgrep -c -x claude) - 1 ))
echo "Other active Claude sessions: $OTHER_CLAUDE"
```

If `pgrep` is unavailable (e.g. Git Bash on Windows), skip this check silently. If `OTHER_CLAUDE > 0`, display a non-blocking notice and proceed:

```
ℹ N other active Claude session(s). Concurrent writes are safe (locked per _shared-rules.md §5), and sessions parked after this point are caught by Step 14's post-write reconciliation. Parking them first keeps the daily report most coherent — say so now if you'd rather do that.
```

Do not block waiting for a reply — the reconciliation machinery (Steps 2 and 14) exists precisely so goodnight can proceed safely. Pause only if the user actually interjects.

### 2. Gather Today's Activity (auto)

Read and compile:
- **This Week.md:** Read `{VAULT}/01 Now/This Week.md` (if it exists and today falls within the date range) — find today's day section. Checked items (`[x]`) are completed, unchecked (`[ ]`) are open. This is the richest single source for what was planned vs what happened
- **Today's sessions:** Check `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md` for today's date
- **Works in Progress:** Read `{VAULT}/01 Now/Works in Progress.md` for project states
- **Session outcomes:** Note what each session accomplished (for the Sessions list)
- **Candidate open loops:** Extract unchecked items (`- [ ]`) from today's day section in This Week.md, plus due items from Tickler.md. Session files are historical records — open loops were routed to SSOT at park time

**Capture session-file baseline** (load-bearing for Step 14's post-write concurrent-session reconciliation — do NOT rely on remembering this later):

```bash
STEP2_NEXT=$("{VAULT}/.claude/scripts/next-session-number.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md")
STEP2_LAST_N=$((STEP2_NEXT - 1))
echo "Step 2 baseline: $STEP2_LAST_N session(s) present (next would be $STEP2_NEXT)"
```

**⛔ CHECKPOINT:** Display the literal line `Step 2 baseline: N session(s) present (next would be M)` in your response. Step 14's reconciliation compares against this number — if it's not on the page, the comparison is being done from internal memory rather than observable state. Shell variables don't persist between Bash tool calls; the displayed number is the source of truth for Step 14.

**Important:** Store the rest of the gathered data in working memory - it's a DRAFT inventory, not ground truth.

### 3. Pre-Verification Debrief (BEFORE presenting report)

**This step happens BEFORE presenting the status report.** The goal is to update your working model with reality before presenting outdated information.

Ask:
> "Before I show today's report, let me check: did you complete anything outside Claude today? Any tasks from earlier sessions that are now done?"

Wait for response.

**If the user provides completions:**
1. Update your working memory (mark those items as completed in your draft)
2. **Update SSOT files immediately** (see Step 4) — This Week.md, Tickler, project files
3. Then proceed to Step 5 with the corrected data

**If the user says "no" or "nothing":** Proceed to Step 5 with original data.

### 4. Update SSOT Files for Completed Loops

When the user reports a loop is complete, update the SSOT files (not session docs — those are historical records with plain bullets):

1. **Update This Week.md:** If This Week.md is current and the completed item appears as unchecked in today's day section, mark it `[x]` via `locked-edit.sh --replace` (not the Edit tool — This Week.md is a shared planning file, see `_shared-rules.md` §5).
2. **Update Tickler.md:** If the completed item appears in Tickler, delete the line.
3. **Update project file:** If the item is scoped to a project, mark it complete in the project file.
4. **Confirm the update:** Display brief acknowledgement:
   ```
   ✓ Marked complete: "LOOP_TEXT" (in This Week.md / Tickler / Project)
   ```

**Why update immediately:** Prevents the same loop from appearing as open in future `/morning`, `/goodnight`, `/pickup`, or `/weekly-review` runs.

### 5. Present Status Report

**Now** display the report using your corrected working memory:

```
## Today's Report — [Day], [DD] [Mon] [YYYY] — [HH:MM TZ]

**Projects touched:** [list]
**Sessions:** [count]

### Sessions
1. [Topic] — [outcome]
2. [Topic] — [outcome]
...

### Blockers
- [Item] — waiting on [what]
```

### 6. Mid-Flow Corrections

**If the user corrects you during the report** ("actually that's done", "I finished that earlier"):

1. **Acknowledge immediately:** "Got it, marking that complete."
2. **Update SSOT files** (same process as Step 4) — This Week.md, Tickler, project files
3. **Update your working memory** - do NOT re-read session files (you'll get stale data)
4. **Continue with corrected state** - don't re-display the whole report

**Critical:** Once the user tells you something is done, treat it as done for the rest of this session. Do not pull from files again.

### 7. Additional Captures (brief, optional)

Ask:
> "Anything else not captured? New blockers, decisions made, or items to add?"

- If yes: add to inventory. Don't add to session files — captures route as follows:
  - Off-Claude activity (wander/exercise/social/admin/errands) → daily report's `## Outside-Claude` section
  - New blockers → daily report's `## Blockers` section
  - New decisions / actionable items → relevant SSOT (This Week.md day section, project file, or Tickler) — NOT the daily report (the daily report is archival; SSOT files surface in `/morning` and `/pickup`)
- If no: proceed

### 8. Generate Daily Report

Create file at `{VAULT}/06 Archive/Claude/Daily Reports/YYYY-MM-DD.md`.

**Include the goodnight session itself as the last numbered entry in the Sessions list.** The goodnight session log entry is written later (Step 14), but the Daily Report is the user-facing day index and should enumerate every session — including the goodnight close-out itself. Plan the topic/outcome line at Step 8 to match the entry you'll write at Step 14 so the two stay in sync. The reorder constraint (Step 8 before Step 14) is non-negotiable because Step 14's `### Files Created` references the Daily Report path — the Daily Report must exist on disk first.

```markdown
# Daily Report - [Day], [Date]

## Today's Plan

[Include today's day section from This Week.md here (the `## [Day] [DD] [Mon]` heading and all items under it). Convert any `- [ ]` to plain `- ` bullets and any `- [x]` to `- ✓` — the daily report is an archival record, not a task SSOT. Checkboxes live in This Week.md, project files, and Tickler only. If This Week.md doesn't exist or today falls outside the date range, omit this section.]

## Sessions
1. [Topic] — [outcome]
2. [Topic] — [outcome]
...
N. **Goodnight: [Brief Topic Summary]** — [one-line outcome matching the Step 14 session entry]

## Outside-Claude
- [Off-Claude activity surfaced in Step 3 (pre-verification debrief) or Step 7 (additional captures) — wander/exercise/social/admin/errands done outside the assistant. Useful end-of-day signal that wouldn't otherwise be recorded anywhere. Omit section entirely if nothing to record.]

## Blockers
- [Item] — waiting on [what]

---
*Links:*
- Sessions: [[06 Archive/Claude/Session Logs/YYYY-MM-DD]]
- Previous: [[06 Archive/Claude/Daily Reports/YYYY-MM-DD]] (yesterday if exists)
```

Ensure directory exists first:
```bash
mkdir -p "{VAULT}/06 Archive/Claude/Daily Reports"
```

### 9. Route undone items from past day sections

Before collapsing, scan today's section — and any earlier days that are still verbose — for `- [ ]` items. For each:
- **Has a natural future day?** → Move to that day's section.
- **Priority item that should happen tomorrow?** → Move to tomorrow's section.
- **Low priority / no deadline?** → Move to Tasks.md (`{VAULT}/01 Now/Tasks.md`).
- **Already appears in a future day?** → Delete the duplicate from today, don't move.

**Critical: carry items forward intact.** Move the full item text, sub-items, checklists, and surrounding context exactly as they appear. A multi-line checklist (e.g. a sprint with Tier 1/Tier 2 items) is an active working artefact — move the entire block, not a summary. Never summarise, condense, or strip items during routing — including `[x]` items. Completed items within a block are progress context.

**Block boundary rule:** A section header (bold text line like `**Sprint Tier 1:**`) and all items beneath it until the next section header form a block. If *any* `- [ ]` item remains in a block, move the entire block (header + all items + `[x]` items). The destination should be a copy of the source block, not a reconstruction.

Preserve existing project/area links when moving items. If an item lacks a link, add one (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`, or `→ [[01 Now/Works in Progress#Heading]]`). No link for items with no project context.

Also check for sub-sections scoped to a future day. Move the entire sub-section to the appropriate future day before collapsing.

### 10. Collapse past day sections

After all undone items have been routed, collapse today's section — and any earlier days in This Week.md that are still verbose — to a one-line summary + link:

```markdown
## [emoji] [Day] [Date] — [Theme] ✅
[One sentence: what happened, what didn't, key outcome.] [[06 Archive/Claude/Daily Reports/YYYY-MM-DD|Full report]]
```

Sweep all past days, not just today. Earlier days may still be verbose if a previous `/goodnight` run predates this step or was interrupted. Any day before tomorrow should be a one-liner.

Nothing with `- [ ]` should remain in any collapsed section. If it does, something was missed in step 9 — route it before collapsing.

### 11. Maintain rolling 7-day horizon

Run the This Week.md Rolling Window Maintenance procedure (see `_shared-rules.md` Section 9). This ensures the file always extends 7 days ahead, preventing it from shrinking as days get collapsed.

### 12. Log Goodnight Session (deferred to Step 14)

The goodnight session entry is written at Step 14 via `write-session.sh --auto-number` — nothing is written at this step. (The step is kept as a stub so cross-references to Steps 13–18 stay stable.)

### 13. Concurrent-Session Detection (folded into Step 14)

Pre-write probing is superseded: the goodnight session's number is resolved atomically at write time in Step 14 via `--auto-number`, and Step 14's **post-write reconciliation** compares the assigned N against Step 2's displayed baseline — which detects every session added since Step 2, with no probe-to-write blind window and no cross-Bash-call shell-variable hazard (the old probe's `$SESSION_FILE` was never defined in its own block, so it silently false-passed). Proceed to Step 14.

### 14. Append Goodnight Session Entry

**Use the write-session script with `--auto-number`** — same as `/park`. This avoids the permission system corruption bug from inline flock commands AND resolves the session number atomically inside the file lock (eliminates collision against parallel /park or /morning catch-up invocations).

**Note on section structure:** The goodnight session log intentionally omits the `### Next Steps / Open Loops` section used in `/park` session entries. For goodnight specifically, the Pickup Context line below already names tomorrow's anchors (the entire purpose of goodnight is forward-routing), so the two sections would duplicate. Files Created and Files Updated are split per session-log convention — a freshly created Daily Report belongs under Created, not Updated.

**Body only — no `## Session N - …` heading.** The script prepends the heading inside the lock. (The script will reject stdin starting with a `## Session N` heading.)

```bash
cat << 'EOF' | "{VAULT}/.claude/scripts/write-session.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" --auto-number "Goodnight: [Brief Topic Summary]" "HH:MMam/pm"
### Summary
[2-3 sentences covering what was reviewed/decided/updated during goodnight]

### Key Insights / Decisions
- [Any significant decisions made during close-out]

### Files Created
- [Daily Report path — typically the only newly-created file. Omit section if no new files.]

### Files Updated
- [List any files modified during goodnight]

### Pickup Context
**For next session:** [One sentence for tomorrow morning]
EOF
```

**Capture N from stdout.** The script's final line is `Session number assigned: N`. This N is the canonical source for downstream steps (15c sub-agent brief, completion message in Step 18). Display it explicitly:

```
Session number assigned: N
```

**Post-write reconciliation (the concurrent-session check):** Compare the assigned N against `STEP2_LAST_N` — the baseline displayed at Step 2's checkpoint (use the literal value from the page, not internal memory). If `N − 1 > STEP2_LAST_N`, sessions `STEP2_LAST_N + 1` through `N − 1` were added by parallel instances since Step 2. For each: read its summary from the session file (the only exception to the write-only-after-initial-read rule — read just the new session blocks, not the whole file), update your working memory, and patch the daily report's Sessions list (Step 8 output, already on disk) to include it. Display: `Reconciliation: baseline X, assigned N → M missed session(s) patched` (or `→ no missed sessions`).

**First session of the day** (no session file exists yet): no special flag needed — the same invocation lays down the `# Claude Session - DATE` header automatically when the file is absent/empty, assigns N=1, and writes atomically inside the lock.

### 14a. Update Works in Progress

If any project status changed significantly today, update `{VAULT}/01 Now/Works in Progress.md` with current state. **Always bump the "Last updated" timestamp** at the top of WIP — goodnight always modifies planning files (This Week.md, Tasks.md, Tickler), so the timestamp should reflect the current date/time even if no individual project entry was edited.

**Write mechanism:** apply every WIP edit here (project-entry rewrites and the timestamp bump) — and the project-hub propagation edits below — through `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5).

**Also propagate state changes disclosed during goodnight conversation, not just session-file outcomes.** State updates revealed in the Pre-Verification Debrief (Step 3) or Additional Captures (Step 7) are authoritative even when session logs don't yet reflect them. When the user discloses that a waited-on event has landed (a reply received, a decision made, an external action completed), rewrite the affected `**Last:**` / `**Next:**` / `**Next action:**` fields across WIP *and* any matching project hub in `03 Projects/` or `04 Areas/`. A stale "awaiting X" line in WIP or a hub file will mislead the next `/morning` or `/pickup` into expecting something that has already happened.

**⛔ CHECKPOINT:** Display `✓ WIP timestamp bumped: YYYY-MM-DD HH:MM TZ`. Do not proceed to Step 15 without this line.

**Why this step is here (not at the end):** Earlier orderings put WIP update after provenance hashing. That left WIP edits uncovered by the auto-audit (Step 15) and meant the provenance hash was computed against a not-yet-final WIP propagation state. Moving WIP ahead of audit fixes both — audit's Layer 3 propagation check covers the WIP edits, and provenance hashing in Step 17 captures the final state.

### 15. Delegate /audit to a fresh sub-agent

The audit runs in a fresh model context via the Agent tool, NOT inline. /goodnight is 18 steps with heavy state propagation; inline audit at step 15 suffers cognitive load, recency bias on just-edited files, and enumeration scoping limited to "what /goodnight directly edited" rather than "what world-state changes the day caused." Sub-agent delegation eliminates all three. See `park.md` (same commands directory) Step 14 tail for the full empirical rationale — the same applies here a fortiori (/goodnight does heavier state propagation than /park).

**(a) Enumerate identifiers IN MAIN SESSION (required checkpoint).** The enumeration discipline must stay in the main session — it's the load-bearing defence against silent miss-pattern. List every identifier as `old → new` pairs, plus any *new* named state introduced, before dispatching the sub-agent.

/goodnight's distinctive Layer 3 substrate (use as a checklist when enumerating):
- Completed-loop identifiers (text marked `[x]` in This Week.md, deleted from Tickler, or marked done in a project file via Step 4 / Step 6)
- Items moved between day sections in Step 9 (old day → new day)
- Items routed to Tasks.md in Step 9 (new home for the loop text)
- Day-section collapses in Step 10 (verbose section → one-liner; the outbound `[[…|Full report]]` link must resolve to a real file)
- New day sections added by rolling-window maintenance in Step 11
- WIP `**Last:**` / `**Next:**` / `**Next action:**` field changes from Step 14a (especially propagation-from-debrief edits)
- NEW: today's daily report file at `06 Archive/Claude/Daily Reports/YYYY-MM-DD.md`
- NEW: the goodnight session entry itself at Session N in today's session log

```
Identifiers in scope:
- "old value" → "new value" (where: file path)
- NEW: "value" introduced (where: file path)
[OR (nil case, formatted as enumerated checklist, not bare assertion):]
- Completed-loop status flips: none
- Day-section moves (Step 9): none
- Tasks.md routings: none
- Day-section collapses (Step 10): none / Daily-report wikilink targets: none broken
- Rolling-window day additions (Step 11): none
- WIP Last/Next field changes: none
- New named state introduced (daily report, goodnight session entry): always at least these two — list them
→ All Layer 3 substrate enumerated; propagation check follows in sub-agent.
```

**The nil case is not a free pass.** "Nothing changed" is a positive claim requiring the explicit checklist. **New state introduced is the most-missed category** — every /goodnight introduces at minimum a daily report file and a goodnight session entry, so a "nothing introduced" claim is always wrong by construction.

**(b) Identifier count integrity check before despatch.**

Count the identifiers in your enumeration block. When you write the sub-agent brief in (c), embed the enumeration verbatim — do NOT re-construct from memory (typed-from-memory lists silently drop entries). Display:

```
Identifier count check: enumeration N → brief N ✓
```

If mismatch, regenerate the prompt from the enumeration block, not from memory.

**(c) Spawn the sub-agent** with `subagent_type: "general-purpose"`, foreground.

The prompt must be **self-contained** — the sub-agent has zero /goodnight context. Include verbatim:

- **Vault path** (resolved from Step 0): the absolute path, not `{VAULT}`
- **Session log path**: `<vault>/06 Archive/Claude/Session Logs/YYYY-MM-DD.md` and the session number N (from Step 14's `Session number assigned: N` stdout)
- **Daily report path**: `<vault>/06 Archive/Claude/Daily Reports/YYYY-MM-DD.md`
- **File list** — every file /goodnight touched, embedded as a newline-separated list inline in the prompt. The session log doesn't yet contain all of these (Step 14 wrote the goodnight session entry but Steps 11-14a edits happen elsewhere); enumerate them from memory of the goodnight flow.
- **One-paragraph summary** of what /goodnight accomplished today (loops marked complete, items routed, day-sections collapsed, WIP propagation done)
- **Enumerated identifiers** verbatim from (a)
- **Script paths** the sub-agent will need (substitute resolved vault):
  - `<vault>/.claude/scripts/update-session-section.sh` — for session-log section edits (preserves flock concurrency safety)
  - `<vault>/.claude/scripts/backfill-files-updated.sh` — to record any remediation edits into Session N's Files Updated section. **Caveat:** the script dedups by normalised path and *silently discards* the new text for a file already listed — to extend an already-listed entry's description, rewrite the section via `update-session-section.sh … "Files Updated" --replace` instead
  - `<vault>/.claude/scripts/write-tickler.sh` — if routing surfaces an open loop
  - `<vault>/.claude/scripts/locked-edit.sh` — for remediation edits to planning/hub files (WIP, This Week, Tickler, project/area hubs)
- **Locking constraint:** "For session-log edits, use `update-session-section.sh`. For planning/hub files (WIP, This Week, Tickler, `03 Projects/`, `04 Areas/` hubs), use `locked-edit.sh` (see `_shared-rules.md` §5). For other vault files, the Edit tool is acceptable. The lockless Edit tool races with concurrent parks/goodnights on planning files and silently clobbers."
- **Audit protocol pointer**: read `audit.md` (same commands directory) Phase 2 (Layers 1-5) first; do NOT recall the protocol from memory.
- **Special-focus instruction** (the empirically-missed Layer 3 category): "**Phase/status framings rendered historical by session actions** is the category prior inline audits silently miss. For each project/area hub touched by today's session work, search for prose like 'upcoming', 'planned', 'pending', 'will', 'next', 'forthcoming', 'awaiting' near references to work completed today; flag every hit. This includes goodnight's OWN `Pickup Context` / Daily Report describing goodnight's already-run steps (this audit, item routing) as forthcoming — written before this audit fired, so a 'the audit will…' framing is already stale; reframe to completed/current tense. Do NOT flag legitimate forward-routing to tomorrow's anchors — Pickup Context naming tomorrow's work is its purpose, not staleness. Also: read each touched project/area hub IN FULL, not just the subsection that was edited."
- **Read-coverage backstop**: "If your file list contains more than 5 project/area hubs to read in full, split the audit across multiple passes rather than truncating any read. Report bytes-read per hub in your final report so the main session can verify plausible coverage."
- **Layer 5 specifics for /goodnight**: "Trace tomorrow's /morning against current This Week.md / Tickler / WIP. Will it surface the right items, or is anything we marked complete still showing as open? Will collapsed-day one-liners' `[[…|Full report]]` links resolve? Will rolling-window day additions be visible to /morning's Step 6 maintenance pass without conflict?"
- **Authority**: remediate inline using Edit / Bash / scripts. Re-audit after every fix; iterate until clean.
- **Report format expected back**: per-layer findings (or nil-case statements that explicitly name what was checked — generic affirmations like "approach is sound" are not acceptable); list of remediation edits with file paths + summary of change; bytes-read-per-hub for read-coverage verification; final clean-pass confirmation OR "could not clean — N issues remain because X" if iteration stalled.

**(d) Receive the sub-agent's report.** Display its summary in your response. Do NOT re-run the audit yourself; trust the sub-agent's report (the whole point is that you don't have the fresh-context advantage).

**(e) Process the report.** If the sub-agent made remediation edits, verify it called `backfill-files-updated.sh` for them. If not, run the backfill yourself using the file list it reported. If read-coverage report shows any hub at suspicious-low byte count (well below the file's actual size), re-despatch a focused sub-agent on that hub.

- **Sanity-check remediation edits that change a factual claim, before accepting them.** "Trust the report" (step d) means don't re-run the full audit — it does *not* mean accept a remediation blind. If the sub-agent edited a file to "correct" a numeric/ordinal/identifier claim (counts, FIFO trims, dates, link targets — the categories it's documented to drift on), verify the correction against the **live file** (and your own in-session grep evidence) before letting it stand. The vault `.git` is auto-save with arbitrary commit boundaries, so a sub-agent's `git diff` does **not** reliably reconstruct pre-goodnight state — a partial-commit diff can flag a real edit as "fabricated." On a confirmed false positive, revert the sub-agent's edit and restore the accurate text. **Caught 2026-06-03** (in `/park`, which shares this audit-delegation design): an audit sub-agent misread an auto-save `git diff` and rewrote an accurate FIFO-trim line as a fabrication.

**(f) Mandatory Files-Updated backfill (runs every goodnight, not just when the audit finds something).** Step 14 wrote the session log *before* the Step 14a WIP edit, the Step 14 daily-report reconciliation patches, and this audit. Those edits are therefore absent from the session entry's `### Files Updated` unless backfilled. Reconcile now, unconditionally:

1. List every file goodnight touched at Step 11 onward (WIP from 14a, daily-report patches from Step 14's reconciliation, any audit remediation from (e)). **Exclude WIP if the only change was the bare "Last updated" timestamp bump** — that bump is unconditional meta-bookkeeping, not content, so recording it adds a near-identical noise line to every goodnight log. If Step 11/14a wrote *content* to WIP (a project-entry Status/Last/Next rewrite), backfill that content change (not the bump); if WIP got nothing but the timestamp bump, omit it and don't let the audit flag its absence.
2. Diff that list against the `### Files Updated` already in Session N's entry.
3. Pipe the missing lines through `backfill-files-updated.sh "<session-file>" N`.

This is the F4 fix: the session log's footprint record must match what goodnight actually changed, even on a clean audit. Skipping it because "the audit was clean" is the failure mode — a clean audit says nothing about whether the post-Step-14 edits were recorded.

**⛔ CHECKPOINT — required outputs:**
1. Identifier enumeration block (real or nil-case checklist) in main session response
2. Identifier count check line (`enumeration N → brief N ✓`)
3. Agent tool invocation with `subagent_type=general-purpose`
4. Display of sub-agent's report
5. One of: `✓ Audit: clean pass` OR `🔧 Audit: N findings fixed and re-audited clean — see [paths]`
6. `✓ Files Updated backfilled: M post-Step-14 file(s) reconciled into Session N` (M may be 0 only if the entry already listed every post-Step-14 edit)

You cannot proceed to Step 16 without all six. If you find yourself walking the audit layers yourself in /goodnight's main response, STOP — that's the inline-audit failure mode this step exists to prevent. Spawn the sub-agent.

**Why auto-run + delegate:** /goodnight propagates state across This Week.md, Tickler, project files, WIP, and project hubs (Steps 4, 9, 10, 11, 14a). Layer 3 propagation gaps are the highest-risk failure mode — a "marked complete" loop that didn't propagate to a project hub will silently mislead tomorrow's /morning or /pickup. Inline audits empirically rubber-stamp these gaps; sub-agent delegation eliminates the three mechanisms causing the rubber-stamp (enumeration scoping, cognitive load, recency bias). See `park.md` (same commands directory) Step 14 tail for the full mechanism analysis.

### 16. Export Session Transcripts

Export today's verbatim session transcripts to the vault. Claude Code auto-deletes JSONL session files after 30 days — this preserves them as searchable markdown. Takes <1 second.

```bash
cd "<session launch directory>" || exit 1   # load-bearing: script keys session discovery on cwd; persistent-shell cd drift would otherwise export the wrong project. Launch dir = the static working directory in your environment context, NOT pwd. Script now fails closed if no project matches and prints `Session directory: <path>` — confirm it names the expected project
python3 "{VAULT}/.claude/scripts/export-session-transcripts.py" "{VAULT}" --days 1
```

**Re-export unconditionally, even if /park already exported today.** The script regenerates the whole day file in <1 second, and Step 17 hashes the transcript as *final* — a skip-if-exists here would OTS-stamp a file missing everything since the last park, unconditionally including this goodnight conversation itself.

Output goes to `{VAULT}/06 Archive/Claude/.Session Transcripts/YYYY-MM-DD.md`. Report the count in the close message.

### 17. Process Provenance Flags

Check for provenance flag files created during today's sessions:
```bash
# Inline date — a variable set in a prior Bash tool call does not survive to this one; an empty
# expansion would glob ALL pending flags and stamp/delete the wrong days' artefacts.
ls "{VAULT}/07 System/Provenance/pending/$(date +%Y-%m-%d)"*.md 2>/dev/null
```

**⚠ Ordering dependency:** Steps 14-16 MUST complete before this step. The session log and transcript must be in their final state before hashing — if you hash then append, the hash is immediately invalid and the OTS stamp covers the wrong content. This is the single most common execution error in this skill. The audit step (15) and transcript export (16) both potentially modify the session log and transcript, so both must finish before provenance hashing.

If any flags exist, process each one:
1. Read the flag file to get the project tag and work product list
2. Hash any work products not already hashed (check the flag file's "Hashed Immediately" section and the provenance log for existing entries). For entries already in "Hashed Immediately", re-hash and compare to the recorded hash — on mismatch (silent edit since the immediate hash), announce it and run `/provenance` Step 5's re-hash path (superseding row), don't skip silently
3. Hash the session transcript (exported in step 16, now final)
4. Hash the session log (now final — goodnight session appended in step 14, audit findings inlined in step 15)
5. OTS stamp all hashed files in a single `ots stamp` invocation (batching reduces calendar submissions)
6. Append entries to `07 System/AI Provenance Log.md` via `locked-edit.sh --append` (mechanism in `/provenance` Step 5)
7. Delete the flag file only after verifying every listed item has a log row — a partially processed flag stays in `pending/` for `/weekly-hygiene`

If no flags exist, skip silently. See `/provenance` for flag file format and full hashing instructions.

### 18. Close

```
✓ Report saved: 06 Archive/Claude/Daily Reports/YYYY-MM-DD.md
✓ Session logged: 06 Archive/Claude/Session Logs/YYYY-MM-DD.md (Session N)
✓ WIP timestamp bumped: YYYY-MM-DD HH:MM TZ
✓ Audit: clean pass [OR "🔧 Audit: N findings fixed and re-audited clean — see [paths]"]
✓ Transcripts exported: N sessions → 06 Archive/Claude/.Session Transcripts/YYYY-MM-DD.md
✓ Provenance: N files hashed [OR "no flags"]
Goodnight.
```

## Guidelines

- **Technical, not emotional:** Focus on state and status, not feelings
- **Accountability:** Each session line should clearly state what was accomplished — the Sessions list is the record of what got done
- **Quick:** This should take 3-5 minutes unless there's a lot to capture
- **No guilt:** If it was a low-output day, just note the status honestly
- **Always resolve vault path first:** Step 0 determines whether to use NAS mount or local fallback. If neither is accessible, abort rather than silently fail.
- **File locking is mandatory — via the dedicated scripts** (`write-session.sh`, `update-session-section.sh`, `backfill-files-updated.sh`, `locked-edit.sh`), never inline `flock` and never the Edit tool on shared files. Inline flock commands corrupt `settings.local.json` via the permission system — the exact failure class Step 14's script mandate exists to prevent (see `_shared-rules.md` §5).

### Working Memory Model (Critical)

**Session files are inputs, not ground truth.** Once you read them in Step 2, work from your working memory for the rest of the command. This prevents the bug where:
1. the user says "that's done"
2. You acknowledge it
3. You re-read the session file (which still shows it open)
4. You present it as open again

**The flow:**
1. Read session files once (Step 2) - populate working memory
2. Ask about completions BEFORE presenting (Step 3) - update working memory AND files
3. Present from working memory (Step 5) - never re-read files mid-flow
4. Handle mid-flow corrections (Step 6) - update working memory AND files
5. Generate daily report from working memory (Step 8)

**Session file updates are write-only after initial read.** You update them when the user marks something done (so future runs see correct state), but you don't re-read them within this session.

## Triggers

This command should trigger when the user says:
- "goodnight"
- "end of day"
- "close out"
- "wrap up the day"
- "done for the day"

## Integration

- **Reads from:** This Week.md, Claude Sessions (today), Works in Progress
- **Creates:** Daily Reports
- **Updates:** Claude Sessions (adds goodnight session), This Week.md (marks completed items `[x]`, collapses today's section, rolls undone items to future days/Tasks.md), Tickler.md (deletes completed items), Project files (marks complete), Works in Progress (if needed)
- **Complements:** `/morning` (start of day), `/park` (end of session), `/afternoon` (mid-day)
- **Auto-runs:** `/audit` on the just-completed goodnight (Step 15) — same protocol as `/park`'s Step 14
- **Replaces:** `/daily-review` (deprecated)
