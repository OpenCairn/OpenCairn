---
name: park
description: Capture session with bookkeeping — quality gate, session log, project-doc update, open-loop routing, and a fresh-context audit.
argument-hint: "[--quick]"
---

# Park - Session Capture

**Scoped rule loading:** `_shared-rules-planning.md` before project/task routing; `_shared-rules-reviewer.md` before attribution or reviewer preparation; `_shared-rules-content.md` before verbatim or structural operations. Read the applicable numbered sections at that point, from the same directory as the core `_shared-rules.md`; do not preload unrelated supplements.

Capture a work session: quality gate, session log, project-doc update, reference-graph propagation, open-loop routing, audit.

**Args:** `/park --quick` requests the fail-closed quick path below. Quick mode activates only when the complete argument string is exactly `--quick`; bare `/park` and every other argument string, including `--quick foo`, run the full protocol. Never infer quick mode from a quiet-looking session.

**On the full path, despatch propagation at Step 4b only for a checked nonempty identifier enumeration; recheck and collect at Step 8.** Checked-empty skips only this agent, not the quality gates, backfill, mechanical verification or independent Step 9 audit; it is not quick mode. When despatched, it runs in the background across Steps 4c, 5 and 7. Park's cost is dominated by model turns, not by its scripts, so a blocking sub-agent is dead wall clock. **The overlap is not conflict-free:** the agent writes planning and hub files that Steps 4c, 5 and 7 may also touch. `locked-edit.sh` prevents lost updates, not stale-preimage conflicts — an exit 2/3 on either side means re-read and recompute (§5), and that is the expected cost of the overlap, not a malfunction. The saving is bounded by however long Steps 4c, 5 and 7 actually take; it does not remove the agent's runtime, it hides as much of it as those steps cover.

**Concurrent parks are safe.** All shared-file writes go through the locking scripts (`write-session.sh`, `update-session-section.sh`, `backfill-files-updated.sh`, `locked-edit.sh`, `write-tickler.sh` — `_shared-rules.md` §5; exit 2/3 = a parallel writer changed the region: re-read and recompute, don't loop-retry; lock timeouts are §5 Failure mode B — kill the hung script, never fall back to the Edit tool). After each `locked-edit.sh` call, apply §5's anchored padded-line residue check and region-scoped malformed-fragment check; classify documentation hits before repairing. `/goodnight` uses the same machinery; parking before goodnight keeps its daily report coherent.

## Steps

### 0. Setup

Read **Caller contract** in the [shared close-out protocol](_closeout.md); its inventory/verification/review sections are called at the steps below.

**Delegation-unavailable checkpoint (full path only).** Check the actual harness tools and governing session instructions before requiring a propagation or audit seat. Standing skill authorisation permits the required delegation unless an explicit higher-priority restriction forbids it. A busy slot, observation timeout or still-running seat is not unavailability: collect or continue that existing seat. If the Agent tool is absent, explicitly prohibited or returns a terminal unsupported error, retain the exact cause. Do not inline the independent audit, invent a clean report or change models.

Use Steps 2(a–d) and 3 to persist the attributable inventory, existing work product and session narrative. Before Step 3, perform Step 4c’s proportional quality inspection and §19 SOURCE check on that work; this checkpoint waives only Step 4b’s delegation-before-quality ordering. Record any unfinished quality/propagation/routing gates and the actual delegation reason in Pickup Context. If the failure happens later, reconcile the work already landed into that same assigned entry. Defer new structural/routing work and Steps 2(e), 4–9 that have not run. This explicit checkpoint branch permits only Step 10's monitor of the work actually performed, Step 11's transcript export and measurement close-out with outcome `blocked`; their outputs do not discharge review. When no audit began, report `✗ Audit: not run (delegation unavailable — <verified reason>)`; when an existing audit cannot finish, report `✗ Audit: not clean — <verified reason>`. Report `✗ Park: incomplete` and the actual saved log/export results. Offer to resume the saved checkpoint in a harness with independent review. An alternative completion policy requires explicit user authorisation; do not treat this branch as Park completion or use Step 12's success message.

**Full-run measurements:** keep a count of completed independent audit reports, rounds of fixes after those reports, and distinct confirmed audit findings. Before every completion or blocked return (including quick mode), record the observed counts as described under **Measurement close-out** below. Missing evidence stays unknown; human review time requires the user's report. Passive transcript collection measures the full request, including the final response.

**Check / Missing ledger.** From Step 1 onward, note each judgement call the user should verify and each detail this park needed but did not have, for the `Check:` / `Missing:` lines in Step 12 (and the quick completion). Collect them silently and do not stop the run to ask: text before the final message is easily missed, and a mid-run question makes park blocking. Where a write needs a missing value, never invent the missing value; omit it from the write and list it under `Missing:`. On the delegation-unavailable checkpoint, print the same lines after `✗ Park: incomplete`.

Run `"${VAULT_PATH:?VAULT_PATH not set}/.claude/scripts/resolve-vault.sh"`, then `"$VAULT_PATH/.claude/scripts/check-archive-layout.sh" --enforce "$VAULT_PATH"`; abort on either error (usual causes: `VAULT_PATH` unset, or a pending archive migration). Read `_shared-rules.md` from this skill's own commands directory and apply it throughout. `{VAULT}` below = the resolved vault path: the part after `VAULT_PATH=` in the resolver's output (§1). Set `PARK_ARTIFACT="{VAULT}/.claude/scripts/park-artifact.py"` and `PARK_ARTIFACT_STATE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/.park-artifacts"`; abort if the helper is absent.

**Startup bundle.** If the optional UserPromptSubmit hook supplied `Park startup receipts (not final dedup)`, retain the raw bundle separately and display a bounded status summary before loading other rules; inspect its actual session binding, command statuses and source hashes; reuse only checked current observations. If absent or stale, run the normal setup/ledger reads. The hook supplies candidates only: fresh-read task destinations and perform final literal/semantic dedup at Step 7; it never replaces attribution, propagation, verification or audit.

Get date and time from bash — `date +"%Y-%m-%d"` and `LC_TIME=C date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'` (`LC_TIME=C` guards `%p`, which expands empty under many locales).

Derive and display today's session-log path mechanically:

```bash
TODAY="$(date +%F)"
SESSION_DIR="{VAULT}/06 Archive/OpenCairn/Session Logs"
SESSION_LOG="$SESSION_DIR/$TODAY.md"
[ "$(dirname "$SESSION_LOG")" = "$SESSION_DIR" ] || { echo "ERROR: session log escaped current-log directory: $SESSION_LOG" >&2; exit 1; }
printf 'Session log path: %s\n' "$SESSION_LOG"
```

**Path invariant:** a new entry for today goes directly in `Session Logs/YYYY-MM-DD.md`, never `Session Logs/YYYY/YYYY-MM-DD.md`. Year subfolders contain archived logs; an archived path loaded by `/pickup` must not be carried into this park. Shell variables do not persist between tool calls, so re-derive and assert `SESSION_LOG` inside every later call that writes or edits today's log, or use the exact path printed above. A later-date continuation creates a new entry here, retaining a link to the earlier session.

**Parboil draft.** A mid-session snapshot may already hold this park's expensive half — session narrative, identifier enumeration, open-loop list — derived while the context was still cheap:

```bash
S="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/${CLAUDE_CODE_SESSION_ID:-none}"
[ -f "$S.parboil.md" ] && { echo "LEDGER NOW: $(wc -l < "$S.tsv" 2>/dev/null || echo 0)"; cat "$S.parboil.md"; } || echo "no parboil draft"
```

Compare the draft's `SNAPSHOT-LEDGER-LINES: K` against `LEDGER NOW`. K is the exact `wc -l < "$S.tsv"` line count captured by the hook, not a count of bullets, files, or sections in the draft. **An equal count does not mean nothing changed** — the ledger records file writes only, so decisions taken, messages sent, bookings made and shell-mediated work all move the session on without moving the number. Equal count licenses adopting the *Files* sections, not the narrative: re-check Summary, Key Insights, Next Steps and the enumeration against what happened after the snapshot regardless. Higher → adopt as the base, and **read the delta paths** before extending the enumeration; a draft enumeration carried forward unread becomes the Step 6 agent's grep list, so an error there is a silent reference-graph miss, not a cosmetic one.

Either way the draft is a cheap artefact, not authority: anything in it that a file you read this session contradicts loses. Bare and escalated parks run Steps 2, 4–5 and 8–11 in full; an eligible explicit quick park follows the checked branch below. A parboil trigger that fires after this park has begun is satisfied by the active park; do not write or refresh a shadow snapshot mid-park.

**Owned-agent and interruption boundary:** enumerate this session's live writing children before inventory; collect their actual terminal reports or retain their handles/expected writes as pending scope. Pending writes cannot silently enter an already-prepared review. Restart an interrupted park at Setup, reusing only hash-matching checked observations; rerun inventory/coverage for anything written since. The parboil draft is park-owned scratch removed by the Stop hook, not a durable Files row.

### 1. Merge-continuation check

If this session directly continues a just-parked session dated today (a `/pickup` loaded it and the work finishes its loose end, or this same conversation already parked today and has worked on since), `--quick` is ineligible: print `↪ --quick escalated to full park: merge-continuation`, then update the existing entry via `update-session-section.sh <log> N <section> [--replace]` (append to Summary / Files sections; `--replace` for Next Steps and Pickup Context), and run Steps 2 and 4–11 against the merged session's N. Before writing the addendum, run coverage and §19 over every continuation-touched file and print the SOURCE result; inherited gating is not enough. **Reconcile the whole merged entry**, including surviving Summary, Key Insights, Next Steps and Pickup Context; confirm inherited artefact classifications still fit. A continuation on a later calendar date creates a new entry with a continuation link. **Escape hatch:** if the addendum would exceed ~2× the target's current summary or touch >3 files unrelated to its topic, start a new session instead — a session titled X that hides hours of Y is invisible to topic search. Completion: `✓ Merged into Session N — [what was added]`. Otherwise proceed normally.

### 2. Quality gate

(a) Execute **Inventory** in the [shared close-out protocol](_closeout.md); retain its attributed list for Step 8.

#### Explicit `--quick` gate

Run this gate only when the complete argument string is exactly `--quick`, after inventory and before any full reads, persistence, routing, or agent despatch. Supply every repository touched during the session to `park-files.sh`, and `--root` for every directory it installed into outside the default sweep.

1. Review the session's actual tool calls and shell commands. Display one row per filesystem-mutating action as `tool/action | resolved path | ledger/park-files/repo coverage`. Every action must resolve to an inventoried path; print `none` only when there were no such actions. Any attributed creation, update, or deletion fails the gate, as does a mutation outside inventory coverage or an action whose target or ownership is uncertain.
2. Check the at-risk surfaces before Step 4: the inventory's `[transient]` hits, each recent `~/.claude/plans` file, and assistant-authored drafts that exist only in the conversation. Any candidate fails the gate.
3. Display checked results for external mutations (messages sent, bookings, purchases, pushes, remote edits); decisions, project-state changes, changed identifiers, or factual corrections requiring durable reconciliation; and resumable next steps or open loops. Read-only queries are non-mutating. Any positive or uncertain category fails the gate.
4. Display the evidence before branching: attributed-file count and inventory sources; mutation rows; transient and plan-file counts; conversation-only draft result; and world-state, project/identifier, and open-loop results. Nil must be a checked result, never a default.

If any condition fails, print `↪ --quick escalated to full park: [reasons]` and continue at Step 2(b), without rerunning setup or inventory. Otherwise follow the quick success path immediately; do not enter the remaining full-path steps.

#### Quick success path

1. Apply Step 3's metadata and locked `write-session.sh --auto-number` mechanics once. Write a sparse entry containing every normal heading, including `Files Created`, `Files Updated`, and `Files Deleted`, with bare `None` under each Files heading; `None` under Key Insights; `None — work completed` under Next Steps and `**For next session:**`; and the normal `**Project:**` line.
2. Immediately rerun the same ledger, `park-files.sh`, and local-mutation census. This second inventory—not `park-verify.sh`—detects late files. Permit only the exact assigned session-log mutation. Any new or ambiguously attributed non-bookkeeping delta prints an escalation reason and retains the assigned N: never rerun Step 3; apply Step 2(b)'s proportional classification and inspection to every late created or updated artefact; record late deleted paths from ledger, pre-state, or tool evidence without reading them; replace every affected `Summary`, `Key Insights / Decisions`, `Next Steps / Open Loops`, `Files Created`, `Files Updated`, `Files Deleted`, and `Pickup Context` section via `update-session-section.sh --replace`; complete Step 2(b–e); then resume the full path at Step 4.
3. With the second inventory still nil, re-derive `SESSION_LOG` per Step 0, then run `"{VAULT}/.claude/scripts/park-verify.sh" "{VAULT}" "$SESSION_LOG" N` with no `--ident` or `--touched` arguments. It does not discover omitted files. Repair and rerun only failures confined to the newly assigned session block. A failure involving another file, a pre-existing entry, or any correction outside that block escalates before remediation: retain N, convert every affected sparse section through the same `update-session-section.sh --replace` contract in item 2, and resume the full path at Step 4. Triage any unexpected REVIEW rather than treating it as file discovery.
4. Run the Step 10 skill monitor against the quick execution, then perform Step 11 transcript export. These outputs are Park-owned bookkeeping and do not invalidate eligibility. Skip project-doc mutation, reference-graph propagation and Step 8 collection, open-loop routing, semantic file review/classification, and the independent audit because their inputs were checked nil.
5. Finish with the quick completion contract below and stop:

```text
✓ Quick eligibility: PASS — 0 attributed files; no at-risk work; no changed world/project/identifier state; no open loops
✓ Session N saved: 06 Archive/OpenCairn/Session Logs/YYYY-MM-DD.md
✓ Quality check: no attributed files
✓ park-verify: PASS
✓ Reference graph: skipped (--quick; no changed identifiers or world state)
✓ Open loops: none (quick eligibility)
✓ Audit: skipped (--quick)
✓ Skill monitor: [no gaps | N logged]
✓ Transcript exported: N sessions
[Check: / Missing: lines per Step 12 — omitted when empty]

Quick parked.

[Short session summary.]
```

(b) Execute **Coverage** in the [shared close-out protocol](_closeout.md). Classify now; run the full quality/SOURCE pass at Step 4c after the propagation handle or checked-empty receipt exists.

**Authored-check gate:** apply the shared protocol's semantic conformance checks and §19 to how-tos, routed setup/integration actions, Next Steps and Pickup Context, including linked pre-existing procedures. Name the subject/component measured, exact command/inspection, pass, fail and where applicable `not yet`; show how observations differ under the competing hypotheses in the current state. For liveness, name the field that advances (not merely a recent timestamp); for logs, bind the interval and replay a real pass output. A README pointer or a success label alone is not a check. Retain positive/negative controls; unresolved criteria remain explicit rather than invented.

(c) Retain raw command evidence per that section.

(d) **Hot-capture nudge:** if substantive insights surfaced but weren't routed in the moment, name the habit gap in one line — don't cold-read the transcript to enumerate them. Omit if none.

(e) **Pre-log propagation pass:** the session log is not yet written, so stale living content gets fixed here, in editing mode, rather than recalled later in record-keeping mode. Build the initial Step 6 enumeration now: every `old → new` pair plus, for each named-entity claim, the entity's canonical identifiers. Search each over the live vault in Step 6's search shape (one Step 6 live-text search per identifier, `06 Archive/` excluded), reconcile every stale living hit per §12 (planning/hub writes via `locked-edit.sh`), and report `Pre-log propagation: I identifiers, H hits, U updated`. For a substantive reframe (scope, timeline, audience, constraint, underlying premise), also list the affected project's sibling artefacts (files in its folder, files its hub links, live planning lines that reference it) and read each one's framing for a premise the reframe invalidated; report `Sibling framing: S reviewed, U updated`. Carry this enumeration to Step 4b unchanged and extend it there; Step 6 stays as the backstop, not the primary catch. For new data paths, search the parent path across infrastructure docs/scripts before adding automation; inspect owning retention/backup/exclusion rows. For reframes/new guides/cross-area moves, read the destination parent/index and linked constraints, and record the owning index/table row or exclusion. For dependency changes, inspect sibling `fallback` / `fall back` / `if ... not` instructions. **New-entity check** (same pass, the complementary failure class: duplication rather than staleness): list every proper noun the session introduced as a new vault concept (person, project, organisation, product, venue, event, place) and run one `rg --hidden --no-ignore -F -i -g '!**/.git/**' -- '<distinctive name>' .` (word-boundary mode for ambiguous bare aliases, retained raw receipt) call per name from `{VAULT}` across the whole vault, `06 Archive/` included, since a prior mention under another framing is exactly what this catches. A name found only in this session's own writes is not yet new: run one variant pass over the same scope — distinctive components with separators folded (`rg -i -- 'word[-_ ]?word'`), a case- and diacritic-folded near-spelling scan of Markdown tokens and same-length phrases (NFKD-fold both sides; flag `difflib` similarity ≥ 0.8), and any alternative names the session knows. Name each existing home found and merge or cross-link rather than leaving a parallel entry. Report `New entities: E searched; V variant passes` with hit counts per name, zeros included.

Display declared classifications/coverage here; the quality verdict follows the executed Step 4c inspection.

### 3. Write the session log

Apply Step 2(b)’s authored-check gate to Next Steps and Pickup Context, including merge-continuation edits.

**Metadata:** topic (descriptive weeks later — "Wezterm config fix", not "Terminal stuff"); project link per §2 (shipped one-shot work → area hub) and §3. Display: `Session: [Topic] | Project: [[03 Projects/Name]] (or "None")`.

**Body format is a parse contract** — `/pickup`, `pickup-scan.sh`, and `/weekly-review` key on these exact headings:

```markdown
### Summary
[2-4 sentence narrative — outcomes and decisions]

### Key Insights / Decisions
- ...

### Next Steps / Open Loops
- [specific enough to resume without re-reading the conversation; plain bullets, never checkboxes — session logs are records, not task trackers]

### Files Created
- `path` - purpose        [one path per line; never brace-expand or comma-group; bare `None` if empty; same for Updated]

### Files Updated
- `path` - what changed and why   [one path per line; never brace-expand or comma-group; include load-bearing external paths]

### Files Deleted
- `path` - why removed    [one path per line; never brace-expand or comma-group; omit the section entirely if none]

### Pickup Context
**For next session:** [one immediately-actionable sentence]
**Continues:** [[06 Archive/OpenCairn/Session Logs/YYYY-MM-DD]] (Session X - Topic)   [only if continuing]
**Project:** [exact link from the metadata line]
```

Use full vault-relative paths inside the vault, and absolute or `~`-prefixed paths outside the vault. `park-verify.sh` parses these rows: each begins with one complete concrete path, never a glob, range, prose stand-in or `~/x, y, z` abbreviation. A file that predates the session goes under Updated, a moved one under Updated at its new path.

**Write it:**

```bash
TODAY="$(date +%F)"
SESSION_DIR="{VAULT}/06 Archive/OpenCairn/Session Logs"
SESSION_LOG="$SESSION_DIR/$TODAY.md"
[ "$(dirname "$SESSION_LOG")" = "$SESSION_DIR" ] || { echo "ERROR: session log escaped current-log directory: $SESSION_LOG" >&2; exit 1; }
cat << 'EOF' | "{VAULT}/.claude/scripts/write-session.sh" "$SESSION_LOG" --auto-number "TOPIC" "$(LC_TIME=C date +'%I:%M%p' | tr '[:upper:]' '[:lower:]')"
[body — NO `## Session N` heading; the script assigns N inside the file lock and rejects a supplied heading]
EOF
```

The script handles locking, file/header creation, and atomic numbering — parallel parks can't collide, which is why N is never pre-computed. Its stdout ends `Session number assigned: N`: **that N is canonical for every later step** — display it. On a `Lock timeout` stderr message retry once; any other exit-1 means the invocation is wrong — fix it, don't retry.

**Continuation link** (only if continuing previous work): run `"{VAULT}/.claude/scripts/add-forward-link.sh" --continued-in "<original session's log file>" <orig-N> <new-N> "<topic>" "<today's YYYY-MM-DD>.md"`. The first file is the **original** log gaining `Continued in:`, never today's file; explicitly pass today's target-date filename on cross-day continuations, including archived originals. Links remain file-level (§13). A failure is reported as a warning, not silently treated as inserted.

Use `"{VAULT}/.claude/scripts/update-session-section.sh" "<log>" --rename-heading N "<complete ## Session N - ... heading>"` for a needed heading correction; read and retain its existing time suffix and avoid unstable counts in topics. Every non-scratch deletion description quotes its authorising user words or says it was the session's decision; a summary request alone does not authorise deletion. A user decision left open belongs in Next Steps and its task home, not only `Check:`.

### 4. At-risk work product

Three checks:
- **Conversation-only drafts** Claude composed (emails, messages, analysis, plans) exist only as text output — write each to its semantic vault home. Drafts the user authored/pasted themselves are not at-risk.
- **Transient surfaces** (Scratchpad, Inbox captures, daily notes) are cleared on a cadence — `park-files.sh`'s `[transient]` lines list this-session candidates mechanically (memory-gating is the failure this check exists to prevent). Read each hit; tasks correctly filed in a configured map’s retained task sections are already at their task home and stay there. Move other durable this-session work product to its semantic home and update every reference to the old location. **Exception:** `/reply` draft sections (headings starting `**Reply to `) need explicit per-draft user confirmation before removal (§11). Pre-existing cross-session content is the user's working buffer — leave it (`/weekly-hygiene`'s job).
- **Claude-internal files** live outside the vault, so `park-files.sh`'s vault-only transient scan cannot see them: run `find ~/.claude/plans -type f -mmin -<session minutes>` and Read every hit individually. A sub-agent's output (`*-agent-*.md`) shares its parent plan's name prefix but is a separate document with its own migration status — "the plan was migrated" is not a verdict on it. Migrate standalone reference material to its semantic vault home; leave spent execution plans (`/weekly-hygiene` owns their cleanup).

Output: `✓ No at-risk work product to persist` or `🔧 Persisted N item(s): [paths]`.

### 4b. Check enumeration; despatch propagation if nonempty (background)

**Do this here — after Step 4, before the Step 4c quality pass and Step 5 — not at Step 6.** Actually check every Step 6 identifier class against the session's work and tool/world-state effects, extending the Step 2(e) enumeration with everything Steps 3–4 changed (including moves). Walk the session log's Files rows one file at a time and name the identifiers each change produced before adding what memory supplies; recall alone drops moves and bulk edits. Display and retain the exact enumeration, each change's event date as the session established it, and the category-check results. Checked nonempty → despatch the Step 6 agent now, `run_in_background: true`. Checked-empty → record `Step 4b: checked empty; no propagation agent despatched` and continue without a seat. Unknown/incomplete attribution or any unchecked category is not nil: resolve it before taking either branch; if it cannot be resolved, report the blocker, not a completed Park. File count and a quiet-looking session are never evidence of nil. Before despatch, trace every `new` value in the enumeration per §19, including those the Step 3 log introduced: the agent propagates whatever it is handed. Step 6 defines the agent's work and prompt; Step 8 rechecks even when no seat was created.

Not earlier: Step 4 **moves files**, and moves are one of Step 6's identifier classes (full old-path forms). Despatching before Step 4 would put every park-time relocation outside the vault-wide sweep, leaving Step 4's own hand-picked reference update as the only net — which is exactly the candidate-list approach §12 forbids. Not later: walking the headings to Step 6 costs the Step 4c, 5 and 7 overlap, which is the saving.

If you reach Step 5 without a seat or a recorded checked-empty result, perform Step 4b before continuing; do not catch-up spawn for a checked-empty enumeration.

**Coherence after status changes:** compare the changed span with its governing heading, table labels, adjacent conditions and parent scope/provenance statement. Check each clause before ticking a compound task. Reconcile surviving tasks with the settled decision, preserving any still-open clause. For claimed deduplication, inspect the retained counterpart as evidence even when it was not edited. For reciprocal links, verify both endpoints only when reciprocity was intended.

**Before saving durable prose:** replace reader-relative dates and unstable list counts/back-references with durable wording. Run the same check on the final session record and later routed items; a completed heading does not prove a scheduled event occurred.

### 4c. Proportional quality gate

Retain the Step 4b propagation handle or checked-empty receipt before the first full quality read. Execute **Quality inspection** in the [shared close-out protocol](_closeout.md), including semantic conformance and SOURCE; later status/content changes rerun the affected checks.

### 5. Project doc update

If the session materially changed a project's state, update that project's doc in `03 Projects/` — rewrite its existing current-state/action content to match reality, preserving the document's structure and bumping any `Last updated:` stamp, via `locked-edit.sh` (§5). No material change, no edit. If the doc has a `## Session History` section, read it and add `- [[06 Archive/OpenCairn/Session Logs/YYYY-MM-DD]] (Session N) — one-line gloss` at whichever end holds its newest row, via `locked-edit.sh --replace` anchored on that row (not `--append` — the section may not be last; if N already exists on a merge, re-read and refresh its gloss when the outcome changed). A section that only points at another doc gets the row in that doc instead. No such section → don't create one.

### 6. Reference-graph propagation

Perform the enumeration at Step 4b and again at Step 8. Checked-empty skips the propagation seat only; attribution, quality, verification, independent review and non-vault checks still run. A pre-log discharge is reusable evidence for a fresh seat's delta check, not permission to remove that independent check.

**Enumerate (main session):** walk each changed file and tool/world-state effect through the classes below. Mark each applicable or checked-none, name its source and literal anchors, and retain old/new values and their established event dates. Map every identifier/name/alias to its executed needle(s) and match mode; shared coverage must explicitly name the covering needle. Never infer an event date from the park clock.

| Anchor class | Carry into the enumeration |
|---|---|
| Subject / container | Canonical names/aliases, owning decision/set, refuted premise's subject and the hub a moved task links to; for new guides, the owning index/table's membership record. A location split/merge names the old and destination containers. |
| Value / locator | Old/new facts with subject and unit, old date plus task subject and any wording this session wrote naming the task's surface, complete old paths from move receipts, filename/link/heading forms (including live locators into completed projects), the write-into directory, and every removed/renamed invocation or configuration alias. Mirrors/copies under a write-to-both policy remain explicit destinations. |
| State / premise | The action/assumption discharged or invalidated and its subject noun, vendor/channel as planning text phrases purchases/bookings/messages, and per-occurrence dated records. Read the subject's sections for differently worded pending clauses; the first phrase list is not exhaustive. |
| Dependency / cause | Trigger/re-enable/fallback anchors and the changed transport, credential, server or automation parent path; inspect sibling fallback instructions and owning backup/retention/exclusion records before adding another job. |
| Structure / inventory | Governing headings/predicates/count words, diagram labels and class assignments, and software/security inventory containers. An install includes its binary, source/keyring/profile paths and privileged-component inventory, not just the package name. |

For each anchor's expected owning record (a linked hub, a membership record, or a note this session created or retitled that the anchor should reach), emit `expected record present in hit-set: true/false`; false means inspect its actual heading/wording and add the missing anchor, not call it clean. Commits pushed enter the hub check in §17. Nil requires all classes and world-state effects checked.

**Distinctive needles:** use canonical subject phrases, heading/link forms or `word` mode for short names/common substrings; pair numeric values with their unit/subject. A phrase search does not prove a bare alias absent: retain a word-boundary alias search where that form can be live. Include straight/curly apostrophe variants when applicable. Do not narrow whole-live-text coverage to `--type md` to reduce output. Preserve full receipts while displaying bounded contexts.

**Literal search command (pre-log, seat and delta use the same boundary):** select `NEEDLE`, `MATCH_MODE` (`fixed`, `phrase` or `word`), and new absolute `RAW_OUT`/`RAW_ERR` paths outside the vault before running. Preserve the complete raw bytes, including long/base64/CR-bearing lines; never cap a loop or overwrite a prior receipt. Display a bounded status/context view and raw path/digest, then triage the retained complete hit set. Full raw receipts, not pasted megabytes, establish coverage.

<!-- BEGIN LIVE SEARCH -->
```bash
VAULT="{VAULT}"  # bind the resolver-verified literal path in this call
EXCL=(-g '!**/06 Archive/**' -g '!**/07 System/.Provenance/**' -g '!**/.git/**'
      -g '!**/.obsidian*/**' -g '!**/.trash/**' -g '!**/.Trash*/**' -g '!**/.stversions/**'
      -g '!**/node_modules/**' -g '!**/__pycache__/**' -g '!**/.cache/**'
      -g '!*.lock' -g '!*.csv' -g '!*.tsv' -g '!*.jsonl' -g '!*.ndjson' -g '!*.xmp')
CMD=(rg --hidden --no-ignore -n -F -i "${EXCL[@]}" --max-filesize 2M)
case "$MATCH_MODE" in fixed|phrase) ;; word) CMD+=(-w) ;; *) echo 'ERROR: invalid match mode' >&2; exit 2 ;; esac
cd "$VAULT" || exit 2
[ ! -e "$RAW_OUT" ] && [ ! -L "$RAW_OUT" ] && [ ! -e "$RAW_ERR" ] && [ ! -L "$RAW_ERR" ] || { echo 'ERROR: receipt path already exists' >&2; exit 2; }
printf 'argv:'; printf ' %q' "${CMD[@]}" -- "$NEEDLE" .; printf '\ncwd: %s\n' "$PWD"
RC=0
"${CMD[@]}" -- "$NEEDLE" . > "$RAW_OUT" 2> "$RAW_ERR" || RC=$?
printf 'exit_status: %s\n' "$RC"
sha256sum "$RAW_OUT" "$RAW_ERR" || exit $?
[ "$RC" -le 1 ] || exit "$RC"
```
<!-- END LIVE SEARCH -->

Exactly one final `.` is the search root; punctuation is never appended to argv. Exit 0 means hits and 1 checked-no-match; a higher status voids that needle's hits. Give long jobs the harness maximum timeout; retain their actual handle/deadline and rerun a failed needle with an explicitly scoped boundary, never kill by pattern. A batch of literal needles may share one background job only with unchanged exclusions, complete per-needle outputs/statuses and initial/final accounting; one aggregate status/count is insufficient.

**Propagate (fresh sub-agent — standing authorisation):** despatch a `general-purpose` background Agent (`run_in_background: true`) on the session's own model before Step 4c; collect its actual completed report at Step 8. The self-contained brief embeds the exact enumeration, event evidence, replacement wording, source/needle map and command above. The seat reads §12 and applies its triage independently; do not pre-classify individual hits or narrow its stale-reference test. A consistent special case or still-valid SSOT locator remains current; preserve qualifiers the decision did not remove, reporting genuine ambiguity. For every hit, including in already-edited documents, read its full line and adjacent paragraph/subject section and account for stale tails, status words and neighbouring locators. Verify all locators in an edited banner/block. Run structural link checks after moves and update the document's own stamp convention. Return `identifiers received N`, exact receipts and per-needle `hits H → updated U, left L`, with a disposition for every hit. Main and seat use canonical locked writers with the actual parent session ID prefix; the seat derives no new date, count or scope assertion.

**Search boundary:** the command searches live text including ignored scripts/config and hidden authored files, with archive/evidence, infrastructure/cache trees, bulk exports, XMP and files over 2 MiB explicitly excluded. Small authored JSON stays included. For an identifier known to live in excluded/oversized text, run and name a separate scoped search with only the relevant exclusion lifted. Keep that supplemental excluded-text run, and any non-vault run reusing the needle, as separately tagged evidence/raw receipts with their literal scope, command/status and hit dispositions beside the consolidated report. The propagation result carries exactly one primary final vault-coverage receipt per `(needle, match_mode)`; never record a supplemental run as a second primary receipt for that key, substitute it for the primary run, or turn its narrow scope into a whole-vault claim. Binary content and symlink targets need format-aware/separately scoped checks. Negative conclusions name this boundary; structural link queries remain separate.

**Executed-search receipts:** retain exact needle and match mode, literal argv/cwd, the `exit_status:` line the LIVE SEARCH block prints, immutable raw stdout/stderr paths/hashes, LF-delimited record and per-file hit counts. In Step 8 compare final enumeration/needle values with executed receipts, not counts: `Propagation coverage: enumerated E; executed X; missing [needles]; failed [needles]`. Account for every missing/failed search and H = U + L before acceptance. Bounded display is not a sampled triage scope; retain the complete raw receipts and give the reviewer exact supporting contexts plus their locators.

**Non-vault consumers (main session):** for changed facts/paths, run a bounded `rg -l --hidden --no-ignore -F` over existing command/skill copies, the relevant harness config files (including existing `~/.claude.json`, `~/.codex/config.toml`, `~/.gemini/settings.json` and `~/.codex/AGENTS.md`), shell startup files such as `~/.bashrc`, relevant `~/.config` subtrees and the actual Claude memory directory; include the repository's callers. Inventory concrete roots first, then triage every file hit. A backticked command inside prose is a command site. Preserve private config contents outside public reports; source/install copies remain distinct. Propagate authorised mechanical fixes and log non-mechanical skill changes for maintenance.

Output: `✓ Reference graph: N files updated for [identifier]` plus the actual file list, or Step 8's checked-final nil result when no seat existed. Never recast an existing seat as undispatched on a later nil claim.

### 7. Route open loops

Route every open loop to exactly one canonical target — no per-item prompting. Apply Step 2(b)’s authored-check gate before saving routed checks, including Tickler and This Week items; a linked canonical procedure discharges the gate only when its actual criteria discriminate the current hypotheses. A routed setup action needs an observable done-condition isolating the new component and steps checked against the relevant live config.

**Already in This Week.md:** keep the existing task there; update any changed scope in place. Do not recapture or offload it through the routing rules below. Shared §9 owns carry-forward.

**Configured task-home map takes precedence for new open loops:** locate it through vault navigation/Autopilot and follow Quick capture, including its undated fallback. Honour actual dates and execution days the user chose; being actionable does not by itself select work for this week. Keep retained tasks as checkboxes. Whimsy is only for ideas the user has released from obligation, never merely low-priority tasks. Use the fallback table below only when no map is configured.

1. **Explicit future date** → the matching dated section in This Week.md if it exists (use `locked-edit.sh --replace`); otherwise Tickler: `"{VAULT}/.claude/scripts/write-tickler.sh" "{VAULT}/01 Now/Tickler.md" "YYYY-MM-DD" "- [ ] text → [[06 Archive/OpenCairn/Session Logs/YYYY-MM-DD]] (Session N - Topic)"`
2. **No date, actionable this week** → This Week.md day section (tomorrow's; today's if parking before noon) via `locked-edit.sh --replace` on the day section — never `--append`, which lands outside any section. Format: `- [ ] text → [[project/area doc]]`. Trigger-contingent loops ("next time X runs, check Y") are not day-bound — use rule 3, or the Tickler at +10 days if no project doc exists.
3. **No date, has a project** → that project doc's existing task/action section (prefer `## Next Actions`, then `## Open Loops`, then another clearly equivalent section). If none exists, route to the Tickler at +10 days instead of creating a section.
4. **Undated, low-priority, no project home** → Whimsy: append a plain line (no checkbox) to `{VAULT}/04 Areas/Whimsy/_notes.md`.

**§18 applies:** an item carrying a deadline/expiry/window token MUST land on a dated surface — for this skill the disallowed sinks are undated project/area task homes, general capture inboxes and Whimsy. Derive the date (`date -d`) if it isn't written as one.

**Dedup before writing:** search both a distinctive task phrase and its stable subject across This Week.md, Tickler.md, and the candidate project/area/capture destination. Read candidate hits for semantic overlap; an intact duplicate may be skipped. Preserve source triggers and safety conditions through a link to their canonical home; do not invent a stronger condition or copy volatile decision prose into another home. Follow the destination's own entry rules. If the session resolved only part of the existing item, rewrite that item's surviving scope under `locked-edit.sh`; do not skip the whole item merely because the grep hit.

A deduplicated item must carry the surviving action and trigger itself, not just a session link; an undated item can cover an undated trigger when it preserves the exact action/condition. Do not invent a date to force deduplication. Name the map row checked (or `absent from table`) before using its fallback.

Output: `✓ Routed: [item] → [target] (map row: [row | absent from table])` per item. A zero-routing claim cites an observable (the dedup grep hit, or the session log's "None — work completed").

### 8. Backfill + mechanical verification

**Finalise Step 6 first.** Recompute and display the complete enumeration after all intervening work, including Steps 4c, 5–7, using Step 4b's category checks and unknown/incomplete rule. If no seat exists and it is checked-empty, record `✓ Reference graph: No identifier values changed — checked final enumeration; no propagation agent despatched`; neither spawn nor wait, and continue to backfill and verification. If no seat exists and identifiers now exist, despatch the Step 6 background agent with the complete final enumeration and collect it before backfill.

**Only if a propagation seat was actually despatched, collect it as follows; otherwise skip this paragraph.** Its edits belong in the backfill, and park-verify's `--touched` list is incomplete without them. If its report hasn't arrived, wait for the completion notification; do not proceed on the assumption it changed nothing. The notification is the *only* signal it has finished — never substitute a proxy that cannot tell "running" from "finished" (a transcript's file size, an elapsed-time guess, a scratch file appearing). Improvising one has already reported completion mid-run. For an initial seat, compare the final enumeration with the exact despatched one and run and collect a delta propagation pass for added or changed identifiers before backfill. Keep the initial report even when the enumeration is unchanged; no final nil claim may erase work already despatched.

When a seat reported, check that its `identifiers received` count equals the despatched enumeration and that each H = U + L matches its hit-list before relaying any figure, then inspect the report for unresolved or gated consequences before backfill. Route each through Step 7. If that routing adds or changes an identifier, run and collect a delta propagation pass for it before continuing; a report that surfaces a new open loop invalidates any earlier "none" result. Apply the same consequence/delta check to each delta report; further identifier changes from propagation or later Park edits require rechecking Step 8 before completion.

Execute **Backfill and verification** in the [shared close-out protocol](_closeout.md) against this session’s log and N. If later fixes change identifiers, rerun Step 8’s propagation finalisation before verification.

**Propagation terminal failure:** a running seat/observation timeout is not failure. For a terminal API/context failure, retain its handle/error, reconcile actual writes and receipts, and try supported same-seat report recovery. If it cannot return, a replacement on the already-authorised model may rerun the complete current enumeration with the prior write boundary disclosed; no silent model change or approval is inferred. If a required seat remains unavailable, use only the documented incomplete checkpoint.

### 9. Audit until clean (fresh read-only sub-agent — standing authorisation)

Execute **Independent review** in the [shared close-out protocol](_closeout.md). Supply Step 8’s propagation result and verified Files list. Only a clean completed review permits Steps 10–11 and completion; the explicit Setup incomplete-checkpoint exception remains unchanged.

User changes or world-state updates arriving during/after the gate require the shared protocol's new fix round before completion; a clean earlier report does not cover new bytes. Re-read edited regions and the assigned entry, including heading and all paraphrases, after every repair.

### 10. Skill monitor

Per §8: on the full path, review this park execution including the audit — an audit catch that a documented step should have made is a skill gap, the highest-signal kind. On the quick path, review the checked quick execution without inventing an audit input. On the explicit delegation-unavailable checkpoint, monitor only the work actually performed; no audit input exists. Log observations per `_skill-monitor.md`, else `✓ Skill monitor: No gaps detected`.

Park-owned monitor entries, transcript exports and generated review receipts follow the shared **Late bookkeeping boundary**: retain their own receipts, do not add late Files rows to an already-accepted entry, and do not recursively review mechanical copies. Substantive new work restarts the scoped review.

### 11. Export transcript (last, so it captures the audit)

```bash
python3 "{VAULT}/.claude/scripts/export-session-transcripts.py" "{VAULT}" --days 7 --all-projects
```

`--all-projects` is cwd-independent and merges multi-project days (a single-project export hashes an incomplete day; do NOT use `--fallback-any-project`). `--days 7` because the cutoff is a rolling window from now — `--days 1` truncates boundary days. Report the count.

### Measurement close-out (full, quick and blocked paths)

Batch this with the last existing tool call before the final response; it does not replace any audit gate:

```bash
python3 "{VAULT}/.claude/scripts/park-metrics.py" record --harness claude --session-id "$CLAUDE_CODE_SESSION_ID" --outcome <completed|blocked|aborted> --review-rounds <completed reports> --correction-rounds <fix rounds> --confirmed-findings <distinct confirmed findings>
```

Use the actual harness transcript session ID (resolve via `lib-session.sh` when needed), not a synthetic bookkeeping suffix. Count independent audit reports only, including the clean pass; exclude propagation and report-only recovery. Count each accepted finding once. Omit any unknown count flag; do not turn missing data into zero. Quick success has zero audit counts only after its checks pass. A recording error is reported but does not block parking. The scheduled collector measures through the final response. Do not ask for human review time routinely; record it only when supplied by the user. Contract and report commands → `{VAULT}/.claude/scripts/park-metrics-guide.md`.

### 12. Full-path completion message

```
✓ Quality check: N files, [no issues | M fixed]   (or “no attributed files” when Step 2(a)'s checked inventory was empty)
✓ Session N saved: 06 Archive/OpenCairn/Session Logs/YYYY-MM-DD.md
✓ At-risk work product: [none | persisted N]
✓ Project doc: [updated [[Name]] | no material change]
✓ Reference graph: [N files updated | No identifier values changed — checked final enumeration; no propagation agent despatched]
✓ Open loops routed: N (This Week: X, Tickler: Y, Project: Z, Whimsy: W)
✓ park-verify: PASS
✓ Audit: [clean pass | N findings fixed]
✓ Skill monitor: [no gaps | N logged]
✓ Transcript exported: N sessions
Check: [judgement call to verify — file or target]
Missing: [detail needed but not available — where it was left out]

Parked.

[Roughly 50 words summarising the preceding session.]
```

**Check / Missing lines:** print after the status lines and before the closing word. `Check:` names a judgement call this park made where a reasonable alternative would change what the user does next (a routing target, project link, dedup skip, classification or session framing). `Missing:` names detail this park needed but did not have (a value left out rather than invented, an unknown event date, an unresolved pass/fail criterion) and where the gap was left, including a gap a propagation seat reported. One line per item, naming its file or target. Omit either heading entirely when it has no items; never write `none`. Choices made under this skill's rules and things omitted as routine are not listed. These lines are where the user answers; acting on an answer is post-park work (below).

Work done after this message is unparked: a further `/park` in the same conversation takes Step 1's merge path.
