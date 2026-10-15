# Shared close-out protocol

Used by Park and Goodnight, including Goodnight C1 catch-up. Read this file from the same installation as the caller’s shared rules; a missing dependency blocks the affected close-out. Install this file before its consumers. This protocol does not invoke either caller or the audit skill.

## Caller contract

At setup, the caller supplies the resolved vault and actual parent session ID. Before verification, it supplies the log path and assigned N, attributed files, raw evidence/pre-state, final identifier enumeration and propagation result, and its specific acceptance checks. Keep numbered steps, routing policy and final messages in the caller. Park retains quick-mode eligibility and its incomplete checkpoint; Goodnight retains debrief → report → carry-forward → collapse → session entry → review → export → provenance. A failed review never permits a successful close-out message or provenance processing.

For Goodnight, the day’s earlier sessions are evidence for the report, not writes owned by this run. During C1, record a ledger/action boundary before each date’s work: the helper session ID stays the actual parent ID, while attribution is only this date’s close-out delta. Re-read the ledger at each boundary; prior dates’ and concurrent sessions’ paths are not silently claimed. A shared path modified in this date still belongs to this date’s Files list.

Resolve `CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"`; set `PARK_REVIEW="$CODEX_ROOT/skills/park/scripts/park-review.py"` and `PARK_ARTIFACT="{VAULT}/.claude/scripts/park-artifact.py"`. Check both exist. These retained filenames are shared implementation dependencies, not instructions to invoke Park. Resolve **Delegation** below before beginning.

Keep count of completed independent reports, rounds of parent fixes and distinct confirmed findings. Record wall-clock start/end of inventory, verification and review using `date +%s` in existing tool calls; label waits and user interaction separately. Report observed elapsed times and unknowns without claiming a speedup. Park retains its existing metrics recorder; do not send Goodnight runs to the Park-only recorder.

## Delegation

**Resolve native delegation by capability (full path only).** Inspect the available tools and their schemas. Tool names below describe operations, not a required namespace: use an equivalent native interface without asking for additional permission. This preserves the review protocol and is not an alternative completion policy.

| Operation | `collaboration` interface | `multi_agent_v1` interface |
|---|---|---|
| Fresh reviewer | `spawn_agent` with `fork_turns: "none"` | `spawn_agent` with `fork_context: false` |
| Collect completion/report | `wait_agent` | `wait_agent` using the returned agent ID |
| Continue the same seat | `followup_task` | `send_input` to that agent ID; `resume_agent` first only if closed |
| Interrupt for report-only recovery | Supported interruption/continuation operation | `send_input` with `interrupt: true` |

Use the exact exposed names and arguments; do not invent a missing alias or pass another interface's parameters. Preserve fresh context, the read-only reviewer contract, inherited model/reasoning effort, same-seat continuation and an authoritative completion result. Retain the returned agent handle for later calls. A missing agent-listing tool or caller-supplied task-name field does not block an interface that returns unique agent IDs. Apply this mapping to every despatch, collection and follow-up below.

## Evidence

**Full-path evidence receipts.** Begin a fresh run once before any capture, classification or preparation. Park enters here only on its full path; Goodnight enters before its first read/edit, and C1 once per caught-up date. Do not restart a generation on remediation or retries:

```bash
python3 "$PARK_REVIEW" begin-run
```

This retains earlier runs under the real harness session ID, including same-session re-parks and merged entries. Keep the active generation throughout remediation and re-audit; do not begin another on a retry. Prior clean file audits remain reusable only while their hashes match. Then capture source text for Independent review using §16's source-size and per-claim coverage rules instead of reconstructing it later:

```bash
python3 "$PARK_REVIEW" capture --kind prestate --label "<what this establishes>" --source "<path/tool>" <<'EOF'
<excerpt>
EOF

python3 "$PARK_REVIEW" capture --kind evidence --label "<source name>" --source "<URL/path/message>" --provenance primary <<'EOF'
<excerpt>
EOF
```

For each decision-bearing command, retain its literal invocation, working directory, exit status and discriminating stdout/stderr before cleanup or brief assembly. State which observation separates pass from fail; include empty/error output when it controls a conclusion. A prose success summary, recreated command or bare exit 0 is not the evidence. Preserve the raw result in the full-path evidence/pre-state handoff, with an exact path and digest for any companion file the reviewer must inspect. Capture that raw result with `capture --kind evidence` or `--kind prestate` as appropriate.

Use `secondary` or `unverified` where §16 requires it. Add receipts as evidence arrives; all excerpts for the same `--source` are retained in capture order. A later excerpt does not replace an earlier one. For this full close-out, follow §16's source-union, source-size and per-claim coverage rules: capture short sources whole and the supporting passages from longer sources. Independent review then assembles the brief from receipts; it never reconstructs it from the transcript. Park’s eligible quick path creates only its verifier receipt.

## Inventory

**Enumerate every file the session created or edited** — vault and non-vault. Recall reliably under-reports the non-vault half (early config edits, tooling side-effects, hook-written files), so derive it mechanically:

```bash
"{VAULT}/.claude/scripts/session-ledger.sh" --read [-m MINUTES]
"{VAULT}/.claude/scripts/park-files.sh" "{VAULT}" [-m MINUTES] [--root DIR ...] [repo ...]
```

Pass `--root <dir>` (repeatable) for every directory the session installed into or wrote under that the default sweep does not cover — `~/.local/bin`, `~/.config`, `/etc`, `~/.claude/settings.json` itself (a file root is listed as a `[root]` row; passing the whole `~/.claude` tree floods the inventory with transcripts), build or `__pycache__` output — an explicit root prunes only `.git`, so cache byproducts under it are listed. Read the first output line, `# roots searched:`: a directory absent from it was not searched, so a write there is found only by recall. **Remote writes are a recall-only class.** Nothing on this machine sweeps a file pushed to another host (ssh, scp, rsync to a remote, a remote API that stores a file), so list each from the session's own tool calls as a `[remote]` row (`host:path — what changed`) beside the scanned candidates and carry it into the Files rows; a `[remote]` row is never produced by a scan.

Under this harness no Write/Edit hook exists: `locked-edit.sh`, `locked-ingress.sh` and the session-log writers (`write-session.sh`, `update-session-section.sh`, `backfill-files-updated.sh`) self-ledger writes, including Obsidian move collateral performed by `locked-edit.sh`. Other raw shell, script and MCP mutations can bypass those recorders, so the mtime/ctime and git candidates remain the backstop. The ledger records the session ID; its `agents` value is `?` when the shell writer has no agent identity. That value does not identify `main` or a sub-agent. Reconcile it with the session's actual tool/action evidence, and retain the explicit parent-session prefix requirement for dispatched agents. Two distinct failure observables, both meaning "fall back to park-files.sh alone and say so": `NOTE: no ledger` (no self-ledger write has landed yet), and `ERROR: no session id` (no harness session id resolvable — see lib-session.sh) with **exit 1** — that exit 1 is expected here and is not the invocation error the session writer warns about. A sub-agent's writes ledger under **this** session's id only when its brief carries the `env OPENCAIRN_SESSION_ID=<this session's id>` prefix on every `locked-edit.sh` call (required for any separate writing seat — a sub-agent otherwise gets its own thread id and its edits land in a separate ledger). With the prefix, the caller’s propagation agent's edits appear inline in your own list. `# CONCURRENT-SESSION` lines are other sessions — or a sub-agent despatched without the prefix; account for your own sub-agents before excluding per §20. That listing looks back 240 minutes: for a longer session pass `-m` with minutes over-covering the whole session, since `-m` also drops this session's own rows older than it. The `# ledger begins` line is the coverage window — earlier writes are not in it, which is one more reason park-files.sh stays.

The parent-session ledger key and writer identity are separate. Keep the parent `OPENCAIRN_SESSION_ID` prefix on dispatched writes. Self-ledgered writes use explicit `OPENCAIRN_AGENT_ID` when supplied, otherwise `codex:<the actual writer CODEX_THREAD_ID>`; unidentified shell writers remain `?`. Do not infer main/child identity from time or convert legacy unknown rows to main. For a harness without a writer thread ID, pass `OPENCAIRN_AGENT_ID` only when the actual agent handle is known.

Reconcile park-files.sh's candidate lines (sync-receipt, config/runtime mtimes or ctimes, `[root]` extra-root hits, repo status, `[vault]` body files, `[git-diff]` working-tree changes, `[git-history]` recent vault commits and transient surfaces) against the ledger and the session's actual tool/action evidence. Git rows contain the repo root, status and repo-relative path; rename rows contain both the original and destination paths. Resolve each against that repo root, use deletion and rename rows to recover removed or moved paths, and preserve intermediate history paths that a later auto-save removed. These are candidates, not attribution: a time-window match does not make another session's or already-parked work yours. Add each attributable path you were about to omit, and exclude other sessions' work per §20.

**Confirm every inventoried path exists before it becomes a Files row.** The structural index (`obsidian links`, `obsidian unresolved`) lags fresh binaries and renames, so it cannot confirm presence. Run `ls -l -- "<exact path>"` on each path the inventory produced: exit 0 with the listing means the path is live; `No such file or directory` (non-zero exit) means it moved, was renamed or was deleted. Treat a missing path as a move to resolve — find the new path (ledger rows, `[git-diff]`/`[git-history]` `R`/`D` rows, `find` on the basename, the session's own tool calls, the user) and record it under Files Updated at the new path with `renamed from <full old path>` in the description (the old path goes under Files Deleted when it is gone), or under Files Deleted when deletion is evidenced. Never drop a missing path silently and never write a Files row for a path `ls` cannot find.

## Coverage

Apply receipt import/classification only to the caller’s attributed scope. In C1, prior dates’ move receipts do not add paths to this date’s inventory unless action evidence shows this date changed them.

Keep every attributed lexical path spelling, including symlink aliases, in the Files record and preparation input. Preparation deduplicates content review by resolved physical identity while preserving aliases for attribution in the manifest. A missing or dangling retained path fails preparation; it is not silently treated as a deletion.

Older session logs touched only by `add-forward-link.sh` may use its exact producer proof automatically through preparation. The helper requires a complete forward-link-only receipt chain for all logged operations ending at current bytes, with source/target session context checked. Explicit classification takes precedence. If any proof or chain is missing, changed or includes other writes, retain normal coverage; do not exempt a file merely because it is a session log or the command reported success.

**Classify each attributed file before reading it again:**

First import link-healing receipts from any locked Obsidian move in this session:

```bash
python3 "$PARK_REVIEW" import-move-heals --vault "{VAULT}"
```

This validates each receipt's exact link-target-only delta and current hash, then pre-classifies healed files as mechanical, including files under `06 Archive/`. Inherited lint is accepted only when its fingerprint is unchanged. Mixed or later-edited files remain subject to ordinary classification; the move destination itself does too unless its only content delta was link healing. Treat an import failure as a quality-gate failure and never repair unrelated archive prose or lint.

- `semantic` — session-authored, substantively rewritten, or otherwise meaning-bearing. A bounded file uses `python3 "$PARK_REVIEW" classify --vault "{VAULT}" --path "<file>" --semantic --reason "<created|substantive>"` and receives one full coherence read at the caller’s quality gate. For a large artefact where that is disproportionate, add `--targeted --inspection-target "<page/section/line range or outcome-specific check>"` (repeat as needed); the caller’s quality gate reviews only that delta-plus-context coverage.
- `reference` — a local manual, textbook, paper, dataset or other source copied/downloaded but not authored this session. Register it with `python3 "$PARK_REVIEW" classify --vault "{VAULT}" --path "<file>" --reference --reason "<why retained>"`, adding `--inspection-target "<passage or claim actually used>"` for each source-dependent claim. The shared `park-artifact.py` helper creates a hash-bound source snapshot, metadata and text index in the cross-session/cross-lane `.park-artifacts` cache; extraction is not a whole-source read attestation. A reference with no source-dependent session claim needs identity/metadata verification only. A session-captured binary (a screenshot, an export) is this class: its coverage is the artefact receipt's hash and `text_status`, not a read. A generated directory (build output, an extracted archive) is listed and hashed (`find "<dir>" -type f -print0 | sort -z | xargs -0 sha256sum`) rather than read; retain the listing and digests with `capture --kind evidence` as its coverage, and name that captured manifest, not the directory, in the Files rows — `build` accepts regular files only.
- `mechanical` — only literal locator/token substitutions, with no other prose or state change in the same locked-edit payload. Register every exact pair and destination in one call: `python3 "$PARK_REVIEW" classify --vault "{VAULT}" --path "<file>" --mechanical --replace "<OLD>" "<NEW>" --target "<resolved target>"` (repeat `--replace` / `--target` as needed). For substitutions that change no locator, use `--no-locator-target` instead of `--target`; never pass both. The helper requires the current session's locked-edit receipts, proves their hash chain and exact declared delta, then checks old-locator absence, new-locator presence, target/anchor existence, separator integrity and lint. A missing receipt, undeclared delta or failed check means semantic; choose bounded-full or targeted coverage by the artefact rules above. If and only if lint predates an otherwise exact mechanical delta, rerun that classification with `--allow-inherited-lint`; the receipt records the exception for the verifier's exact-path gate.
- `nonlocal` — an exact remote artefact, or a local root-only/secret-bearing file that must not be copied into a review brief. Use sanitised identity/configuration checks as evidence, never secret contents. Register it with `--nonlocal --reason "<surface represented by evidence>"`; the reviewer sees it only through evidence receipts. An unreadable path (`EACCES`, root-only) registers here with `--reason "unreadable: coverage incomplete"` and the remedy named in the Coverage receipt: re-run with access, or a substitute check (owner-supplied hash, sanitised metadata). Never omit it silently. Deleted files stay in `Files Deleted` and need no read classification.

Display the inventory with its classification and declared coverage. Do not perform the quality read here; Park's enumeration check and any required propagation despatch precede the expensive quality pass; Goodnight inspects before its final verification.

**Earlier audit reuse:** if a clean independent reviewer already full-read any attributed file in this or an earlier session and returned its SHA-256, pipe that report once into `python3 "$PARK_REVIEW" record-audit --reviewer "<seat>" --vault "{VAULT}" --file "<file>" ...`. The helper records only hashes explicitly attested in a clean report. The shared review reuses the receipt only while the current file hash remains identical.

## Quality inspection

- **Bounded semantic files:** read each in full once. Mid-session direction changes can leave stale residue outside the edited span.
- **Large semantic artefacts:** inspect the session delta, enough surrounding structure to judge coherence, and the declared outcome-specific pages/sections/renders/tests. State exact coverage; do not claim a whole-file read.
- **Local reference artefacts:** verify the helper's source hash and metadata, then inspect only declared passages supporting session claims. Never read a whole manual/textbook merely because it was touched. A complete extraction is an index, not evidence every page was read; `empty` or `unsupported` text status proves no text coverage, so use targeted rendering/OCR only when a declared target needs it.
- **Across semantic coverage:** fix broken syntax/links/paths, stale interim state, prose that contradicts a table, heading or list in the same doc, a `Last updated:` stamp older than the session's edit to its doc, redundancy, typos and locale spelling (if `.claude/scripts/locale-lint.sh` exists, run it over attributed prose paths from the ledger's Write/Edit, `locked-edit` and `locked-ingress` rows — never the mtime backstop's — and fold accepted candidates in, always skipping candidates inside URLs, quoted spans, or capitalised runs; record candidate, applied and skipped counts, including zero), draft-era filename residue after a terminal status change (rename via link-healing move, never raw `mv`), and hook collateral on verbatim external text (§14). A durable new doc must be linked from a durable parent. Don't auto-revert changes you didn't make — surface them.
- **Wikilinks resolve through the structural index, not by eye.** Probe `obsidian version` first; a CLI that is absent or not responding means this check did not run, and the output says so (§24). When it runs: `obsidian unresolved` once, inspected for targets or basenames this session introduced, then `obsidian links` (argument form per `obsidian help links`, §24) on every edited file that added or changed a wikilink, confirming each new link resolves at file level. An empty result straight after edits can be a reindexing blank, not a pass (§24): re-query once settled. Heading anchors are outside the index: open each target and match the heading text exactly. An eyeball pass is the fallback for anchors only, never the file-level check.
- **Mechanical-only files:** do not full-read. Use the classification receipt result; inspect only its exact replacement and changed span if judgement is needed. Re-run `classify --mechanical` after any later edit; it fails if the receipt chain or current hash changed.
- **All attributed files:** run `_shared-rules.md` §19's SOURCE check; its required output line is part of this gate.
- **File-creation code:** regression-test both mode branches: a missing target receives the caller's umask-derived mode, while replacement of an existing target preserves that target's mode.
- **Superseded queues:** compare the captured pre-state with the retained canonical source before deleting or relabelling the queue. Preserve execution-critical detail; a surviving source label is not evidence that the detail survived.
- **Status narrowing:** bind claims such as "already in place" or "complete" to the exact surface checked and capture the supporting receipt. Count-only or subset evidence cannot discharge a wider status.
- **Override completeness:** when an override suspends a protocol or routine for a stated interval, enumerate every imperative in that interval from the linked SSOT and mark each suspended or retained. Disabling one named mechanism does not implicitly disable adjacent instructions.
- **Hot-capture nudge:** if substantive insights surfaced but weren't routed in the moment, name the habit gap in one line — don't cold-read the transcript to enumerate them. Omit if none.

Output: `✓ Quality check: B bounded semantic files full-read; T large/reference artefacts target-inspected; M mechanical files receipt-verified`, `🔧 Quality check: fixed N issues — [file: fix]`, or — when the checked inventory is empty — `✓ Quality check: no attributed files (writes deferred to the later caller steps)`. The empty case is a result, not a skip: planning and research sessions can legitimately make their first writes during Park, and the later writes still pass their step contracts, shared verification and review.

**Coverage receipt:** after inspection, display `Files read in full: [exact paths | none]`, `Targeted coverage: [path: pages/sections/ranges/checks | none]` and `Mechanical substitute: [exact receipt paths/checks | none]`. Keep this tied to what was actually read or verified, not the intended inventory class; an omitted or truncated read remains incomplete until the stated substitute is performed.

**Coherence after status changes:** compare the changed span with its governing heading, table labels, adjacent conditions and parent scope/provenance statement. Check each clause before ticking a compound task. Reconcile surviving tasks with the settled decision, preserving any still-open clause. For claimed deduplication, inspect the retained counterpart as evidence even when it was not edited. For reciprocal links, verify both endpoints only when reciprocity was intended.

**Before saving durable prose:** replace reader-relative dates and unstable list counts/back-references with durable wording. Run the same check on the final session record and later routed items; a completed heading does not prove a scheduled event occurred.

## Backfill and verification

**Backfill:** caller edits after the session entry was written (project docs, This Week, Tickler and report reconciliation) — pipe them as `- path - what changed` lines through `"{VAULT}/.claude/scripts/backfill-files-updated.sh" <log> N`. The script skips paths already in Files Created/Updated, keeps their existing descriptions, prints each incoming row it did not write, and ends with `<N> added, <M> skipped`. Exit 3 means it wrote nothing because every row was skipped: a result to read, not a failure to retry. Extend a skipped description in its existing section via `update-session-section.sh --replace` — after a fix round a `skipped` line for an already-listed path is the expected signal that its row needs rewriting, not a no-op; a created file stays in Files Created after later edits. If the caller has a Next Steps section, reconcile inline closures: an item that the caller closed comes out of `### Next Steps / Open Loops` (`--replace`, preserving the other lines).

Reconcile the Files lists with a fresh `session-ledger.sh --read`, the initial inventory (including its non-ledger backstop), and the collected propagation/close-out edits; backfill any attributed omissions before verification. The ledger alone is not complete. Reconcile the complete path set independently from attributed commit/merge ranges and tool calls, including parent-skill, shell and connector writes; do not infer ownership from a commit time window. Include renamed/deleted paths in the Files record with their actual status. Build `--touched` from the reconciled Files-list paths and deduplicate by the same resolved path (expand `~` and resolve vault-relative spellings), passing each path once. Keep distinct installed/source paths separate even when their basenames or contents match; repeated writes to one path are not separate files.

**Verify:** run the verifier through the receipt wrapper and resolve every FAIL, re-running until clean:

```bash
python3 "$PARK_REVIEW" run-verifier -- \
  "{VAULT}/.claude/scripts/park-verify.sh" "{VAULT}" "<session log>" N \
  --ident "<distinctive substring per item/identifier the session completed>" ... \
  --touched "<each file the session+close-out created or edited>" ...
```

**`--touched` must be the log's own Files-list paths**, all of them — they are already enumerated by this point, so pass that list rather than a subset you retype. The verifier can only speak for the paths it was handed: a narrower list still prints `PASS backfill`, and a `REVIEW backfill` naming paths the log lists but the run never saw means the list was short, not that the log is wrong. `--ident` values must be distinctive strings — a bare number under ~4 digits matches digit runs inside phone numbers, order IDs and amounts, and a common word or a doc's name matches every item that mentions or links it, burying real hits in noise. Paths may be absolute, `~`-prefixed, or relative to `{VAULT}`.

**Files rows the verifier parses.** A path containing ` - ` goes in backticks — `` - `03 Projects/Plan - draft.md` - what changed `` — because an unquoted one is settled by the longest left side that exists on disk, which fails once the file is gone; the backfill script backticks such paths itself, rows written by hand must too. Annotate a path not on this host's disk after the path: `(deleted)` for a file or directory removed this session, `(remote)` for a path on another host or network share that must not be read; these print `INFO backfill: ... not compared` instead of `REVIEW backfill`/`FAIL touched`. A touched path on a network/FUSE mount, over 2 MiB or binary is checked for existence only and announced as `PASS touched: existence-only (<reason>): <path>`; `PARK_VERIFY_REMOTE_PREFIXES` (colon-separated) names mounts the filesystem probe cannot classify; a prefix covering the vault root itself does not exempt vault files from content checks, only a subtree prefix does. `PARK_VERIFY_MAX_CONTENT_BYTES` overrides the size threshold.

It checks the deterministic layer: session numbering, required sections, Project line (compare its printed line against the caller’s metadata — fix the log if they differ), stranded locked-edit separator lines, list-join/blank-line lint on touched files, unchecked planning-doc items matching each ident, that each touched path exists (`FAIL touched`: mistyped or truncated), and Files-list coverage of touched paths. **A closure `PASS` is not a completion check:** it means no unchecked line matched, which an ident present only in ticked lines also produces. An ident absent from every planning file prints `N/A closure: ident '<ident>' absent from every planning file (<k> checked)` and the `RESULT` line carries the N/A count; N/A is not a pass — usually a misspelt or never-tracked ident — and a run whose every ident is N/A has verified nothing about closures. An ident is the stable identifier the planning line itself carries — the path, booking reference or the item's own wording — never a verb, a paraphrase or a status word such as "done". Two closure classes the verifier cannot see are checked by that same identifier grep, not by the ledger: an item already ticked `[x]` before close-out that this session resolved (`grep -n -i -F -- "<ident>" <file> | grep -F '[x]'`) still gets the `→ [[log]] (Session N)` backlink appended via `locked-edit.sh --replace` when its line lacks one; and a task the user discharged by pasting content into the conversation, which writes no file and leaves no ledger row — enumerate these from the session's Summary and grep each one's identifier. A "line gone" conclusion is the identifier grep on the live file returning empty **after** the same grep matched the session's own pre-state excerpt; an empty grep for a different string or a verb is not that evidence. Judgement stays with you: each closure `REVIEW` hit is an item the caller wrote during routing (expected: ignore the hit, keep the item), an item the session genuinely completed — flip `[ ]`→`[x]` via `locked-edit.sh --replace` with a `→ [[log]] (Session N)` backlink (Tickler flips only after confirming it's the very item resolved — a false flip silently kills deferred work) — or an adjacent still-open item: surface it in Pickup Context, don't action it. Passing edited-file basenames as extra `--ident` args catches adjacent open items mechanically. Once an adjacent-open hit has been recorded in Pickup Context, the final rerun may omit only that discovery-only basename while retaining every core completion/value identifier; record the triage rather than accepting an unexplained `REVIEW` forever.

**One accepted-FAIL class:** a lint hit in content the session never wrote, where the file's classification receipt proves every session delta was an exact declared locator/token substitution, carries pre/post lint fingerprints proving the edit introduced no lint, and records `--allow-inherited-lint`. "Fixing" inherited lint means reformatting the user's own notes, which a standing instruction forbids. An unchanged imported file classified as `reference` also qualifies when its current SHA-256 and retained source/review snapshots match the classification receipt. This preserves source formatting without changing its bytes. Session-authored semantic content does not qualify; missing, stale or corrupt reference receipts fail closed.

When this is the verifier's **only** failure, rerun through `run-verifier` with one `--accept-inherited-lint "<path>"` before `--` for every affected file. The wrapper accepts only paths pre-approved by those mechanical or intact-reference receipts, an exact path-set match over the complete multi-line lint block, exactly one `FAIL lint`, zero `REVIEW` lines, and `RESULT: FAIL (1 fail, 0 review)`; any additional or differently scoped issue remains a failing receipt.

Output: the script's `RESULT:` line plus what you fixed.

**Final evidence check:** re-read the session entry as written and apply §19 to it and all caller-owned writes, including backfill descriptions; print §19's `Value check:` line again for this pass. Reconcile completion claims with surviving open items before assembling the review. If audit remediation or later edits change verified inputs, reconcile attribution and rerun this section before reporting its PASS.

## Independent review

**Script probes:** embed this boundary in the reviewer brief: the reviewer may run a command only after reading its argument handling and establishing that the invocation is read-only. Otherwise copy its required inputs into a disposable scratch directory outside the vault and installed config, redirect all output/state there, and probe that fixture. `--help` is not evidence of a read-only command. If isolation cannot be established, inspect the source and report the execution check unverified; never weaken host policy or bypass a missing sandbox.

Run the independent close-out audit, remediate confirmed findings, and **re-audit until a full pass finds no further findings**. Keep the delta-aware scope and read-only reviewer; the main session owns remediation. This does not invoke `$audit` or its panel. **The caller’s export, provenance and completion must wait for the final clean report and accepted audit receipt.** Park’s Setup delegation-unavailable checkpoint is the explicit incomplete-bookkeeping exception; it never permits a caller completion claim.

Generate the brief from the post-backfill session log, raw session ledger, locked-edit/classification receipts, propagation receipt, latest verifier receipt, evidence receipts and hash-matching prior audit receipts:

```bash
python3 "$PARK_REVIEW" build --vault "{VAULT}" --session-log "<session log>" --number N
```

The command prints the §16 evidence count and review-mode counts, writes `review-brief.md`, and uses immutable digest-addressed source/review copies under this session's `.session-state` directory. It full-reads only bounded semantic groups; large semantic and local reference artefacts carry hash-bound metadata plus declared inspection targets. It fails closed if a propagation/verifier receipt is absent, an artefact receipt is stale/corrupt, or a mechanical receipt no longer matches the live file. Give the filesystem-capable reviewer the generated brief's absolute path and printed SHA-256, instructing it to read the file and verify the digest before reviewing. Do not reconstruct the brief in the spawn message.

Despatch exactly one reviewer through the interface resolved in **Delegation**. These are alternative examples, not two seats (replace `yyyymmdd` and `n` with the current date and assigned session number; both substitutions use digits only):

```text
collaboration.spawn_agent({
  task_name: "park_audit_yyyymmdd_n",
  fork_turns: "none",
  message: "<brief absolute path + SHA-256 + read-and-verify instruction + read-only contract>"
})
```

For an exposed `multi_agent_v1__spawn_agent` tool:

```text
multi_agent_v1__spawn_agent({
  fork_context: false,
  message: "<brief absolute path + SHA-256 + read-and-verify instruction + read-only contract>"
})
```

If the interface accepts task names and exposes an agent list, check `park_audit_yyyymmdd_n` before spawning; on a collision, append `_addendum_1` and increment until unused. If only the spawn reports a name collision, recompute and retry. For an ID-based interface, use its returned unique agent ID instead; no listing or task-name parameter is needed. A failed spawn creates no reviewer, so this still yields exactly one fresh seat. Carry the actual task name or returned agent ID into collection, same-seat continuation and the audit receipt.

Omit both `model` and `reasoning_effort`: the reviewer must inherit the active parent seat's model and reasoning effort exactly. Do not resolve, copy or hard-code their current names or values; omission keeps the match intact when the user changes either setting. Use the selected interface's fresh-context argument (`fork_turns: "none"` or `fork_context: false`); it does not change that inheritance. Any separate propagation seat keeps its caller's model policy.

The generated brief is delta-aware: bounded semantic files are full-read once per pass from immutable review copies; large semantic and local reference artefacts are checked only at their declared targets after the source hash and any review-copy hash are verified; mechanical-only files use exact locked-edit receipts and changed spans; files covered by an earlier clean audit receipt are not reread while their SHA-256 is unchanged. Complete PDF extraction is an index, never a whole-book coverage claim. Attestations bind full-read snapshots to original paths. The brief embeds the Layers 1–5 checklist for each pass, §16 evidence, §23 attestation table, strict read-only scope and compact report contract. These are generated invariants, not fields to retype. Confirm the checklist landed before despatch: `grep -c '^- Layer [1-5] ' "<path>"` against the path `build` prints on its `Reviewer brief:` line must print `5`; `0` is a build failure to fix before despatch, never a seat result. The protocol source under this harness is `$CODEX_ROOT/skills/audit/SKILL.md` (`ls -l` it; its Layer headings are `grep -n '^#### Layer [1-5]:'`); never hand the seat `{VAULT}/.claude/commands/audit.md` or any other path in place of the embedded checklist.

Collect with `collaboration.wait_agent` in intervals no longer than 60 seconds until the report arrives. Do not infer completion from elapsed time or another proxy, and do not re-despatch merely because the seat is still running. If the same seat has explicitly said its review work is complete but remains running through repeated no-progress waits, send one report-only message. If it still does not yield, interrupt that seat and use `collaboration.followup_task` on the same task name with a no-tools, report-only instruction to return its existing evidence. Do not spawn a fresh audit before this same-seat recovery.

If recovery fails because the reviewer hits a model/context wall or the same-seat continuation is unavailable, reconcile the fresh session ledger and any landed edits against attribution/backfill, preserve the current brief and evidence, and report `✗ Audit: not clean — <reason>`. Do not switch the reviewer to an arbitrary named model or treat an incomplete report as clean. A terminally unavailable supported continuation may use only Park’s Setup incomplete-checkpoint exception for its expressly permitted bookkeeping; a model/context wall alone does not permit it. A different-model fallback requires existing user authorisation and must preserve the independent review contract.

For each completed report, re-run `session-ledger.sh --read` and reconcile any row attributed to the reviewer against the read-only contract. An unexpected reviewer write is not cured by a clean final file: inspect the target for lost concurrent content, replay any warranted vault delta through `locked-edit.sh`, and add the path to attribution/backfill. Then sanity-check each finding in the live file.

**Remediate and repeat:** the main seat fixes confirmed, attributable findings using the normal locked write mechanics, backfills newly touched paths while reporting each fix to a path already in the Files list as `<path>: description extension: <text>` and rewriting that row with `update-session-section.sh --replace` (§23), refreshes affected classification/evidence receipts, re-reads the changed portions and reruns **Backfill and verification**. Rebuild the brief, then use `collaboration.followup_task` to send the same independent reviewer the new brief path and SHA-256, with instructions to verify its digest and run the full scoped checklist again. Collect and assess that report by the same contract. Repeat after every fix round; there is no one-round cap. An incomplete report or missing attestation also requires a follow-up before claiming clean.

If a finding requires unavailable evidence, a user decision or action beyond the authorised scope, report the concrete blocker and retain it as an open loop; do not label the audit clean or the caller complete. For a disputed finding, send the reviewer the counter-evidence; unresolved disagreement is a blocker, not grounds for silently accepting or endlessly repeating the finding.

On a clean report, pipe it into `python3 "$PARK_REVIEW" record-audit --reviewer "<resolved task name or agent ID>" --from-brief`. The helper refuses a receipt unless the report says clean and attests every snapshot SHA-256 against its original path. It then checks the live originals: unchanged files remain eligible for later audit reuse; a changed file is accepted only when post-snapshot locked-edit receipts from other sessions form a complete hash chain and every session-owned locator remains intact. Traceable disjoint edits by another session therefore do not invalidate this close-out, but that file's snapshot receipt is not reused as a clean audit of its newer live bytes. A post-snapshot edit by this session requires a rebuilt brief and new review; an untraceable change or missing owned locator fails closed as possible overlap. The helper persists `pending`, completes its final live-byte check, then atomically promotes the receipt to `clean`, so interruption cannot strand a reusable receipt before finalisation. Do not create a clean receipt after findings/remediation without a new independent full read.

Retain the accepted receipt and manifest per **Completion evidence** before returning to the caller.

Output: `✓ Audit: clean pass` or `🔧 Audit: N findings fixed and re-audited clean — see [paths]`. If blocked: `✗ Audit: not clean — [blocker]`; do not proceed to the completion message.

## Completion evidence

A report and a session entry prove that writing began, not that review completed. Retain the accepted independent report with its exact log path and assigned N so C1 can distinguish completion from interruption. Missing, incomplete or mismatched evidence does not authorise a clean verdict. Do not rewrite the session entry after acceptance just to stamp it complete; keep export/provenance after acceptance.

Use the existing `review-brief-manifest.json` and accepted audit receipt; create no additional tracker. The manifest must name this exact `session_log` and `session_number`. Under `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/`, search `*.park-review/runs/*/review-brief-manifest.json` for that pair, then `.park-audit-receipts/*.json` for the same `run_generation`, `status: clean`, a report ending `Terminal state: clean` and a matching `report_sha256`. A matching manifest without an accepted receipt is an interrupted review, not completion. Read the matching evidence rather than inferring completion from a directory name. The record establishes the accepted close-out at that time; later sessions are handled by C2, not by invalidating the historical verdict whenever a shared file changes.
