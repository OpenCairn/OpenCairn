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

### Propagation receipts

After the final enumeration and consolidated triage, save the original report text inside the structured `report` field and retain every executed search. Record both captures, including the checked-empty case (`needles: []`, `searches: []` with the actual checked-nil report). Keep each pass's input files outside the vault and print their exact paths; do not regenerate receipts from remembered totals.

```json
{"needles":[{"needle":"subject phrase","match_mode":"phrase"}]}
```

```json
{"report":"verbatim consolidated report","searches":[{"needle":"subject phrase","match_mode":"phrase","exit_status":0,"command":"rg --hidden --no-ignore -n -F -i -- 'subject phrase' .","cwd":"/absolute/vault","stdout_file":"/absolute/complete.stdout","stderr_file":"/absolute/complete.stderr"}]}
```

**Primary versus supplemental runs:** `searches` contains one default final vault-coverage row per `(needle, match_mode)`. Initial/rerun receipts remain retained, but only the selected final primary row enters this set. An additional scoped run for excluded/oversized text or a non-vault consumer can legitimately reuse that key: retain it separately as tagged supplemental evidence/raw captures, including literal scope/command/cwd/status, complete stdout/stderr paths/digests and hit dispositions. Refer to that evidence in the verbatim consolidated report; do not insert another same-key row, merge its hit count into the primary row, replace the required primary run, or describe the supplemental scope as whole-vault coverage. For example, use ordinary `capture --kind evidence --source "<supplemental scope>" --provenance primary --label "Supplemental excluded-text search"` for its metadata/triage and `--raw-file` captures for the raw streams.

The illustrated command is the receipt's literal executed command, not a substitute for the caller's full exclusion-bearing command. Modes are `fixed`, `word` (`-w`) and `phrase` (a literal multi-word anchor); `-F` and a separately bound `-- <needle>` or `-e <needle>` are required. Use each actual expanded argv from the caller's command receipt. Preserve even empty stdout/stderr files; the helper copies their raw bytes into immutable hash paths and records LF/per-file counts. Native `exit_code`/`returncode` aliases normalise to `exit_status`, but a failure remains a failure.

```bash
python3 "$PARK_REVIEW" capture --kind enumeration --label "Final needles" < "<final-needles.json>"
python3 "$PARK_REVIEW" capture --kind propagation --label "Final propagation" < "<final-propagation.json>"
```

Build compares the final needle+mode set with the latest executed set and rejects missing, extra, failed or corrupt receipts. It also refuses a stale one: `stale propagation receipt: '<needle>' path:line ... rerun this needle` means that hit's text is no longer a line of its file (edited since the search, for example a closure backlink added at verification, or the file is gone); rerun that needle and recapture the final propagation receipt. A line that only moved stays valid. An earlier prose-only capture remains a legacy path, not the updated caller contract. Declare each cited local companion with `capture --dependency "<absolute local path>"` or `classify --dependency "<absolute local path>"`; inspect the automatic backticked-path diagnostics from inspection targets. A remote Files row needs evidence capture metadata `--mutation-for "<exact row path>" --command "<literal mutation command>" --cwd "<absolute execution directory>" --exit-status "<observed exit status>"`. The strict build gate rejects missing concrete dependencies/mutation proof; it supplements the parent's cited-source reconciliation rather than proving every conceivable citation was discovered.

Use `capture-tools --transcript "<actual session JSONL>" --claims-file "<claims.json>"` to index native `function_call`/`custom_tool_call` outputs and Claude content blocks, including escaped JSON and paired async wait results. Claims are `[{"source":"https://example.invalid/source","call_id":"original-or-result-call-id","passage":"verbatim load-bearing passage","provenance":"primary"}]`. Primary support requires an unambiguous requested source and exact captured passage; URL/title metadata or discovery/batched ambiguity is not primary passage evidence. Read the cumulative `tool-source-index.json` as source-union assistance, not automatic entailment or proof that every cited source was opened.

For oversized/non-UTF8 tool evidence use `capture --kind evidence --raw-file "<raw file>" --source "<source>" --provenance primary --label "<label>"`; retain its metadata and exact supporting passages without decoding/retyping the full byte stream.

## Inventory

**Enumerate every file the session created or edited** — vault and non-vault. Recall reliably under-reports the non-vault half (early config edits, tooling side-effects, hook-written files), so derive it mechanically:

```bash
"{VAULT}/.claude/scripts/session-ledger.sh" --read -m auto
"{VAULT}/.claude/scripts/park-files.sh" "{VAULT}" -m auto [--root DIR ...] [repo ...]
```

Pass `--root <dir>` (repeatable) for every directory the session installed into or wrote under that the default sweep does not cover — `~/.local/bin`, `~/.config`, `/etc`, `~/.claude/settings.json` itself (a file root is listed as a `[root]` row; passing the whole `~/.claude` tree floods the inventory with transcripts), build or `__pycache__` output — an explicit root prunes only `.git`, so cache byproducts under it are listed. Read the first output line, `# roots searched:`: a directory absent from it was not searched, so a write there is found only by recall. **Remote writes are a recall-only class.** Nothing on this machine sweeps a file pushed to another host (ssh, scp, rsync to a remote, a remote API that stores a file), so list each from the session's own tool calls as a `[remote]` row (`host:path — what changed`) beside the scanned candidates and carry it into the Files rows in the verifier's form, `- host:path (remote) - what changed` (the `(remote)` annotation and ` - ` separator are what the parsers read); a `[remote]` row is never produced by a scan.

Under this harness no Write/Edit hook exists: `locked-edit.sh`, `locked-ingress.sh` and the session-log writers (`write-session.sh`, `update-session-section.sh`, `backfill-files-updated.sh`) self-ledger writes, including Obsidian move collateral performed by `locked-edit.sh`. Other raw shell, script and MCP mutations can bypass those recorders, so the mtime/ctime and git candidates remain the backstop. The ledger records the session ID; its `agents` value is `?` when the shell writer has no agent identity. That value does not identify `main` or a sub-agent. Reconcile it with the session's actual tool/action evidence, and retain the explicit parent-session prefix requirement for dispatched agents. Two distinct failure observables, both meaning "fall back to park-files.sh alone and say so": `NOTE: no ledger` (no self-ledger write has landed yet), and `ERROR: no session id` (no harness session id resolvable — see lib-session.sh) with **exit 1** — that exit 1 is expected here and is not the invocation error the session writer warns about. A sub-agent's writes ledger under **this** session's id only when its brief carries the `env OPENCAIRN_SESSION_ID=<this session's id>` prefix on every `locked-edit.sh` call (required for any separate writing seat — a sub-agent otherwise gets its own thread id and its edits land in a separate ledger). With the prefix, the caller’s propagation agent's edits appear inline in your own list. `# CONCURRENT-SESSION` lines are other sessions — or a sub-agent despatched without the prefix; account for your own sub-agents before excluding per §20. `-m auto` sets both look-backs from the session's start (the earlier of its first ledger row and its transcript's first record) plus a 30-minute margin and prints `# window: -m <N> from <start> ...` as the ledger's first output line and park-files.sh's second; report that line beside the inventory. A `(default)` window line found no start and fell back to 240 minutes: say so and rerun both commands with `-m` minutes over-covering the whole session, since `-m` also drops this session's own rows older than it. The `# ledger begins` line is the ledger's coverage start — earlier writes are not in it, which is one more reason park-files.sh stays.

The parent-session ledger key and writer identity are separate. Keep the parent `OPENCAIRN_SESSION_ID` prefix on dispatched writes. Self-ledgered writes use explicit `OPENCAIRN_AGENT_ID` when supplied, otherwise `codex:<the actual writer CODEX_THREAD_ID>`; unidentified shell writers remain `?`. Do not infer main/child identity from time or convert legacy unknown rows to main. For a harness without a writer thread ID, pass `OPENCAIRN_AGENT_ID` only when the actual agent handle is known.

Reconcile park-files.sh's candidate lines (sync-receipt, config/runtime mtimes or ctimes, `[root]` extra-root hits, repo status, `[vault]` body files, `[git-diff]` working-tree changes, `[git-history]` recent vault commits and transient surfaces) against the ledger and the session's actual tool/action evidence. Git rows contain the repo root, status and repo-relative path; rename rows contain both the original and destination paths. Resolve each against that repo root, use deletion and rename rows to recover removed or moved paths, and preserve intermediate history paths that a later auto-save removed. A supplemental git inventory you run yourself uses `git -c core.quotePath=false diff --name-only -z` (`--name-status -z` where renames matter) and splits on NUL, never quoted display names; pass is `ls -l --` succeeding on every decoded name. These are candidates, not attribution: a time-window match does not make another session's or already-parked work yours. Add each attributable path you were about to omit, and exclude other sessions' work per §20. An attributable `[vault]` binary candidate with no ledger row has no `locked-ingress.sh` record: confirm the raw copy from the session's tool calls, print `Raw ingress (§5 breach): <path>`, and carry that note into its Files row description before any Files rows are written.

**Confirm every inventoried path exists before it becomes a Files row.** The structural index (`obsidian links`, `obsidian unresolved`) lags fresh binaries and renames, so it cannot confirm presence. Run `ls -l -- "<exact path>"` on each path the inventory produced: exit 0 with the listing means the path is live; `No such file or directory` (non-zero exit) means it moved, was renamed or was deleted. Treat a missing path as a move to resolve — find the new path (ledger rows, `[git-diff]`/`[git-history]` `R`/`D` rows, `find` on the basename, the session's own tool calls, the user) and record it under Files Updated at the new path with `renamed from <full old path>` in the description (the old path goes under Files Deleted when it is gone), or under Files Deleted when deletion is evidenced. Never drop a missing path silently, and never write an unannotated local Files row for a path `ls` cannot find — a path that is gone is a `Files Deleted` row or a `(deleted)` annotation, a path on another host is a `(remote)` row.

**Session-local inventory boundary:** cover the full session window even when shell/bypass mode leaves the ledger incomplete. Add the actual harness scratchpad path with `--root` and the specific runtime output roots of tool-invoking tests (for example the relevant `~/.local/state` subtree). Do not sweep the whole `.session-state` tree: name this session's ledger/receipt/run paths and any shared artifact-cache manifest actually used. A scratchpad reset is an evidenced deletion, not an inferred move; keep its directory-recreation evidence. Reconcile note renames/deletions against canonical move receipts; an unreceipted relocation needs review. Before disposing of a sync-conflict filename, read the vault's sync workflow and record its required disposal route.

## Coverage

Apply receipt import/classification only to the caller’s attributed scope. In C1, prior dates’ move receipts do not add paths to this date’s inventory unless action evidence shows this date changed them.

Keep every attributed lexical path spelling, including symlink aliases, in the Files record and preparation input. Preparation deduplicates content review by resolved physical identity while preserving aliases for attribution in the manifest. A missing or dangling retained path fails preparation; it is not silently treated as a deletion. Mechanical classification also requires reading the whole replaced paragraph for co-located measurements or state clauses: a changed fact/premise is semantic even if the literal replacement is small.

Older session logs touched only by `add-forward-link.sh` may use its exact producer proof automatically through preparation. The helper requires a complete forward-link-only receipt chain for all logged operations ending at current bytes, with source/target session context checked. Explicit classification takes precedence. If any proof or chain is missing, changed or includes other writes, classify it as below (`build` refuses any unclassified attributed file other than the session's own log); do not exempt a file merely because it is a session log or the command reported success.

**Classify each attributed file before reading it again:**

First import link-healing receipts from any locked Obsidian move in this session:

```bash
python3 "$PARK_REVIEW" import-move-heals --vault "{VAULT}"
```

This validates each receipt's exact link-target-only delta and current hash, then pre-classifies healed files as mechanical, including files under `06 Archive/`. Inherited lint is accepted only when its fingerprint is unchanged. Mixed or later-edited files remain subject to ordinary classification; the move destination itself does too unless its only content delta was link healing. Treat an import failure as a quality-gate failure and never repair unrelated archive prose or lint.

- `semantic` — session-authored, substantively rewritten, or otherwise meaning-bearing. A bounded file uses `python3 "$PARK_REVIEW" classify --vault "{VAULT}" --path "<file>" --semantic --reason "<created|substantive>"` and receives one full coherence read at the caller’s quality gate. For a large artefact where that is disproportionate, add `--targeted --inspection-target "<page/section/line range or outcome-specific check>"` (repeat as needed); the caller’s quality gate reviews only that delta-plus-context coverage.
- `reference` — a local manual, textbook, paper, dataset or other source copied/downloaded but not authored this session. Register it with `python3 "$PARK_REVIEW" classify --vault "{VAULT}" --path "<file>" --reference --reason "<why retained>"`, adding `--inspection-target "<passage or claim actually used>"` for each source-dependent claim. The shared `park-artifact.py` helper creates a hash-bound source snapshot, metadata and text index in the cross-session/cross-lane `.park-artifacts` cache; extraction is not a whole-source read attestation. A reference with no source-dependent session claim needs identity/metadata verification only. A session-captured binary (a screenshot, an export) is this class: its coverage is the artefact receipt's hash and `text_status`, not a read. A generated directory (build output, an extracted archive) covers tool-generated bytes only: reconcile its files with the ledger and tool writes, classify each session-authored file inside it (script, prompt, config) as its own `semantic` row and exclude it from the manifest; the rest is listed and hashed (`find "<dir>" -type f -print0 | sort -z | xargs -0 sha256sum`) rather than read; save the listing outside the vault under `${PARK_ARTIFACT_STATE:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/.park-artifacts}/manifests/<session-id>-<directory-slug>.sha256` and retain its path/digest with `capture --kind evidence` as coverage, and name that captured manifest, not the directory, in the Files rows — `build` accepts regular files only.
- `mechanical` — only literal locator/token substitutions, with no other prose or state change in the same locked-edit payload. Register every exact pair and destination in one call: `python3 "$PARK_REVIEW" classify --vault "{VAULT}" --path "<file>" --mechanical --replace "<OLD>" "<NEW>" --target "<resolved target>"` (repeat `--replace` / `--target` as needed). For substitutions that change no locator, use `--no-locator-target` instead of `--target`; never pass both. The helper requires the current session's locked-edit receipts, proves their hash chain and exact declared delta, then checks old-locator absence, new-locator presence, target/anchor existence, separator integrity and lint. A missing receipt, undeclared delta or failed check means semantic; choose bounded-full or targeted coverage by the artefact rules above. If and only if lint predates an otherwise exact mechanical delta, rerun that classification with `--allow-inherited-lint`; the receipt records the exception for the verifier's exact-path gate.
- `nonlocal` — an exact remote artefact, or a local root-only/secret-bearing file that must not be copied into a review brief. Use sanitised identity/configuration checks as evidence, never secret contents. Register it with `--nonlocal --reason "<surface represented by evidence>"`; the reviewer sees it only through evidence receipts. An unreadable path (`EACCES`, root-only) registers here with `--reason "unreadable: coverage incomplete"` and the remedy named in the Coverage receipt: re-run with access, or a substitute check (owner-supplied hash, sanitised metadata). Never omit it silently. Deleted files stay in `Files Deleted` and need no read classification.

Use one classification writer per generation. Register every literal Files spelling and reconcile requested paths/modes with the stored registry before build; changed bytes need reclassification. Historical continuation/banner-only work stays targeted unless an actual full read is explicitly chosen with `--confirm-full-read`.

Display the inventory with its classification, byte/line counts, reason for any targeted class and declared coverage, then per-class file and byte totals (semantic delta apart from reference, generated and archive bytes) before the first read. Group byte-identical copies (same SHA-256 at distinct paths) under one primary: classify each copy `--semantic --targeted --inspection-target "byte-identical to <primary> sha256 <digest>"`. A bounded semantic note requires a full coherence read even for a small edit; historical continuation-only deltas may stay targeted with producer proof. Do not perform the quality read here; Park's enumeration check and any required propagation despatch precede the expensive quality pass; Goodnight inspects before its final verification.

**Cross-doc canonical home:** when a session-written claim restates content whose canonical home is another vault doc, that doc's rows or sections for every entity the claim names enter targeted coverage, not only any span the session edited there; add each as an `--inspection-target` when that doc is attributed and classified semantic or reference (a mechanical classification stores no inspection targets), otherwise read those rows and retain them with `capture --kind evidence`, then compare each with the session's claim.

**Earlier audit reuse:** if a clean independent reviewer already full-read any attributed file in this or an earlier session and returned its SHA-256, pipe that report once into `python3 "$PARK_REVIEW" record-audit --reviewer "<seat>" --vault "{VAULT}" --file "<file>" ...`. The helper records only hashes explicitly attested in a clean report; this standalone source attestation permits hash-matching reuse and does not establish completion or permit export. The shared review reuses the receipt only while the current file hash remains identical. When a file in an earlier clean report has since changed, import the unchanged rest with `record-audit --reviewer "<seat>" --vault "{VAULT}" --subset-of "<earlier receipt>" --file "<file>" ...` (no stdin): every `--file` must carry an `ATTEST` row in that receipt's report matching its current SHA-256, the report is retained verbatim, and the new receipt is the same reuse-only `source-attestation`.

## Quality inspection

- **Bounded semantic files:** read each in full once. Mid-session direction changes can leave stale residue outside the edited span.
- **Large semantic artefacts:** inspect the session delta, enough surrounding structure to judge coherence, and the declared outcome-specific pages/sections/renders/tests. State exact coverage; do not claim a whole-file read.
- **Local reference artefacts:** verify the helper's source hash and metadata, then inspect only declared passages supporting session claims. Never read a whole manual/textbook merely because it was touched. A complete extraction is an index, not evidence every page was read; `empty` or `unsupported` text status proves no text coverage, so use targeted rendering/OCR only when a declared target needs it.
- **Across semantic coverage:** fix broken syntax/links/paths, stale interim state, prose that contradicts a table, heading or list in the same doc, a `Last updated:` stamp older than the session's edit to its doc, redundancy, typos and locale spelling (if the optional locale-lint script is installed — test with `test -x "{VAULT}/.claude/scripts/locale-lint.sh"`, and record `locale lint: not installed` when it is absent instead of probing with `ls` — run `"{VAULT}/.claude/scripts/locale-lint.sh"` over attributed prose paths from the ledger's Write/Edit, `locked-edit` and `locked-ingress` rows — never the mtime backstop's — and fold accepted candidates in, always skipping candidates inside URLs, quoted spans, or capitalised runs; record candidate, applied and skipped counts, including zero), draft-era filename residue after a terminal status change (rename via link-healing move, never raw `mv`), and hook collateral on verbatim external text (§14). A durable new doc must be linked from a durable parent. Don't auto-revert changes you didn't make — surface them.
- **Wikilinks resolve through the structural index, not by eye.** Probe `obsidian version` first; a CLI that is absent or not responding means this check did not run, and the output says so (§24). When it runs: `obsidian unresolved` once, inspected for targets or basenames this session introduced, then `obsidian links` (argument form per `obsidian help links`, §24) on every edited file that added or changed a wikilink, confirming each new link resolves at file level. An empty result straight after edits can be a reindexing blank, not a pass (§24): re-query once settled. Heading anchors are outside the index: open each target and match the heading text exactly. An eyeball pass is the fallback for anchors only, never the file-level check.
- **Mechanical-only files:** do not full-read. Use the classification receipt result; inspect only its exact replacement and changed span if judgement is needed. Re-run `classify --mechanical` after any later edit; it fails if the receipt chain or current hash changed.
- **All attributed files:** run `_shared-rules.md` §19's SOURCE check; its required output line is part of this gate.
- **File-creation code:** regression-test both mode branches: a missing target receives the caller's umask-derived mode, while replacement of an existing target preserves that target's mode.
- **Superseded queues:** compare the captured pre-state with the retained canonical source before deleting or relabelling the queue. Preserve execution-critical detail; a surviving source label is not evidence that the detail survived.
- **Status narrowing:** bind claims such as "already in place" or "complete" to the exact surface checked and capture the supporting receipt. Count-only or subset evidence cannot discharge a wider status.
- **Override completeness:** when an override suspends a protocol or routine for a stated interval, enumerate every imperative in that interval from the linked SSOT and mark each suspended or retained. Disabling one named mechanism does not implicitly disable adjacent instructions.
- **Hot-capture nudge:** if substantive insights surfaced but weren't routed in the moment, name the habit gap in one line — don't cold-read the transcript to enumerate them. Omit if none. Emit it once per close-out: a later rerun of this inspection (late files, rechecks) skips it.

Output: `✓ Quality check: B bounded semantic files full-read; T large/reference artefacts target-inspected; M mechanical files receipt-verified`, `🔧 Quality check: fixed N issues — [file: fix]`, or — when the checked inventory is empty — `✓ Quality check: no attributed files (writes deferred to the later caller steps)`. The empty case is a result, not a skip: planning and research sessions can legitimately make their first writes during Park, and the later writes still pass their step contracts, shared verification and review.

**Coverage receipt:** after inspection, display `Files read in full: [exact paths | none]`, `Targeted coverage: [path: pages/sections/ranges/checks | none]` and `Mechanical substitute: [exact receipt paths/checks | none]`. Keep this tied to what was actually read or verified, not the intended inventory class; an omitted or truncated read remains incomplete until the stated substitute is performed.

**Coherence after status changes:** compare the changed span with its governing heading, table labels, adjacent conditions and parent scope/provenance statement. Check each clause before ticking a compound task. Reconcile surviving tasks with the settled decision, preserving any still-open clause. For claimed deduplication, inspect the retained counterpart as evidence even when it was not edited. For reciprocal links, verify both endpoints only when reciprocity was intended.

**Before saving durable prose:** replace reader-relative dates and unstable list counts/back-references with durable wording. Run the same check on the final session record and later routed items; a completed heading does not prove a scheduled event occurred. Flag provenance and pending/contingent clauses written into living docs (`rg --no-config -n -i '\b(pending|contingent|awaiting|depends on|regardless of)\b'` over the authored spans finds candidates): keep the volatile status only in its canonical decision or status home and link to it per §12's one-owner rule; frozen records and durable source provenance stay.


**Semantic conformance checks (use the applicable rows, not a new pass per anecdote):**

| Changed surface | Required comparison and retained observation |
|---|---|
| Approved implementation | List each applied change beside its approving decision/checklist item; flag an unmatched change before saving the session record. |
| Governing prose and state | Read the subject's sections, including already-edited lines and the instructions above an appended status paragraph. Compare final state with headings, table legends/owners, adjacent clauses, list predicates and diagram labels/classes; account for each stale clause, not only matching tokens. Apply this after membership additions as well as status flips. |
| Sources and derivations | Execute §19 at the caller's SOURCE step, over the written session record as well as the files, including every cited clause and synthesis line. Compare a derived document item-by-item with its declared source's caveats; verify attributed linked-note content in the destination. Match ordered sequences against their source (`N/N`), and give appended claims their own provenance rather than inheriting a paragraph's tag. Public figures must retain any load-bearing discretionary/derived assumption. |
| Procedures and code | Read header/docstring constraints for behaviour changes, run a minimal fixture for each claimed behaviour, and compare a durable recipe with the command actually executed (name deliberate generalisations). For an installed or symlinked entry point, run the canary through the PATH command (`command -v <name>`, then invoke that name), not the physical interpreter or source path, and confirm every local resource path it emits exists. Walk a written procedure in order: each path, control or resource a step probes exists now or is created by a named earlier step. A new prohibition/rule requires searching its own runnable blocks and templates/examples for contradictions. Check destructive-automation cadence/order; a timed-stop fixture must advance time during blocking work and verify children stop, checkpoint/guard restoration and no completion marker. |
| Instruments and branching claims | Calibrate a checker with known-present and known-absent inputs, including a valid case after a short/skipped token; retain distinct outputs before citing its null. Trace the branches a written next-action claim covers, rather than accepting neighbouring prose as proof. |
| Locators and owning context | Resolve bare paths against the document's defined shorthand. Read a linked parent hub's constraints and each destination heading before changing a still-valid SSOT locator. Use code locators for extensionless scripts rather than unresolved wikilinks. New guides need their owning index/table row or an explicit exclusion; a cross-area move needs a route from the destination area's index/hub. |
| Renders | A session-rendered PDF/image is semantic output, not an imported reference: inspect a representative page visually plus each outcome-critical region. Regenerate sibling PDF/HTML/site renders after the final source edit and verify the final edited content appears; timestamps/text extraction alone do not prove visual fidelity. |

Run and display the count-word/ordinal/back-reference/relative-time scan over final authored spans, including replacement/deletion seams and Files descriptions. Set `SCAN_INPUT` in the same call as the scan, to each retained authored span or the printed `SESSION_BLOCK` path; this scan finds candidates rather than proving prose valid.

<!-- BEGIN DURABILITY SCAN -->
```bash
SCAN_RC=0
rg -n -i '\b(one|two|three|four|five|six|seven|eight|nine|ten|both|all|first|second|third|former|latter|above|below|this (line|section)|tomorrow|yesterday|next (day|week))\b' "$SCAN_INPUT" || SCAN_RC=$?
[ "$SCAN_RC" -le 1 ] || exit "$SCAN_RC"
printf 'Durability scan: %s (0=candidates, 1=no candidates; every candidate needs triage)\n' "$SCAN_RC"
```
<!-- END DURABILITY SCAN -->
 Recompute retained counts and rewrite fragile references; repeat after every later edit or fix round. Run the stamp search on every edited doc whatever its Coverage class, mechanical and locator-only edits included: `rg --no-config -n -i 'last updated|last update|current as of|updated:' "<doc>"` (match the form the document uses, not one preferred spelling); bump a stamp the session's change leaves stale and print `Stamp: <path> <found|none> <bumped|n/a>` for each doc. A bump on a mechanically classified file is a further edit: rerun its classification.

## Backfill and verification

### Assigned-session extraction

Use this same bounded extraction for Summary quoting, final checks and `--touched`. Set the exact assigned `SESSION_LOG` and `N`; the block writes its outputs to fixed session-scoped paths outside the vault and prints them. A missing/duplicate N fails instead of borrowing a concurrent entry.

<!-- BEGIN SESSION EXTRACT -->
```bash
set -e
case "$N" in ''|*[!0-9]*) echo "ERROR: N must be the assigned session number" >&2; exit 1 ;; esac
SID="$(. "{VAULT}/.claude/scripts/lib-session.sh"; _session_id)"
[ -n "$SID" ] || { echo "ERROR: no session id; set OPENCAIRN_SESSION_ID" >&2; exit 1; }
EXTRACT_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/${SID}.closeout/$(basename "$SESSION_LOG" .md)-session-${N}/extract"
SESSION_BLOCK="$EXTRACT_DIR/session-block.txt"; SESSION_PATHS="$EXTRACT_DIR/session-paths.txt"
mkdir -p "$EXTRACT_DIR"; rm -f "$SESSION_BLOCK" "$SESSION_PATHS"  # a failed rerun leaves neither output
python3 - "$SESSION_LOG" "$N" "$SESSION_BLOCK" "$SESSION_PATHS" "{VAULT}" <<'PY' || { rm -f "$SESSION_BLOCK" "$SESSION_PATHS"; exit 1; }
from pathlib import Path
import re, sys
log, number, block_out, paths_out, vault = sys.argv[1:]
lines = Path(log).read_text(encoding="utf-8").splitlines(keepends=True)
heads = [(i, re.match(r"^## Session ([0-9]+)(?:\s+-|\s*$)", line)) for i, line in enumerate(lines)]
heads = [(i, m.group(1)) for i, m in heads if m]
found = [j for j, (_, n) in enumerate(heads) if n == str(int(number))]
if len(found) != 1:
    raise SystemExit("ERROR: assigned session is absent or duplicated")
j = found[0]; start = heads[j][0]; end = heads[j+1][0] if j+1 < len(heads) else len(lines)
block = "".join(lines[start:end]); Path(block_out).write_text(block, encoding="utf-8")
paths = []; identities = set(); in_files = False
for line in block.splitlines():
    if line.startswith("### "):
        in_files = line.strip() in ("### Files Created", "### Files Updated", "### Files Deleted")
        continue
    if not in_files or not line.startswith("- "):
        continue
    row = line[2:]
    if row.startswith("`"):
        match = re.match(r"`([^`]+)`(?:\s+\((deleted|remote)\))?(?:\s+-.*)?$", row)
        if not match: raise SystemExit("ERROR: malformed backticked Files row")
        path, annotation = match.group(1), match.group(2)
    else:
        # An empty-list placeholder is not a path: the verifier skips `None` and `None - ...`
        # (any case); the backfill writer also treats `None.` and `None (...)` as placeholders.
        if re.fullmatch(r"none(?:\.|\s*\(.*\))?", row.split(" - ", 1)[0].strip(), re.I):
            continue
        path = re.split(r"\s+\((?:deleted|remote)\)(?:\s+-|$)| - ", row, maxsplit=1)[0]
        annotation = "remote" if " (remote)" in row else "deleted" if " (deleted)" in row else None
        # Canonical rows use backticks; do not guess a legacy separator-containing path.
        if " - " in row and not Path(path).suffix:
            raise SystemExit("ERROR: backtick the complete Files path before extraction")
    local = Path(path).expanduser()
    if not local.is_absolute(): local = Path(vault)/local
    identity = (annotation, path) if annotation else (None, str(local.resolve()))
    if identity not in identities:
        identities.add(identity); paths.append(path)
Path(paths_out).write_text("".join(p+"\n" for p in paths), encoding="utf-8")
PY
printf 'SESSION_BLOCK=%s\nSESSION_PATHS=%s\n' "$SESSION_BLOCK" "$SESSION_PATHS"
```
<!-- END SESSION EXTRACT -->

Read both printed files. Each shell tool call starts a fresh shell, so no variable from this block survives into a later call: every later block sets `SESSION_BLOCK` or `SESSION_PATHS` from the printed absolute path. The paths are fixed per session, log and N, so a rerun after a fix rewrites the same files, and any failed rerun removes both, including a block written before a malformed row stopped it. Keep lexical aliases in the Files record; normalise/deduplicate the verifier's arguments by resolved identity while retaining distinct source/install paths. Every Files row written or rewritten now uses backticks around its complete path, so ` - ` in a filename is unambiguous. For a legacy ambiguous row, re-read and canonicalise its complete existing section before rerunning; never silently shorten a path.


**Backfill:** `--section "Files Created"`, `--section "Files Updated"` (default) or `--section "Files Deleted"` selects the destination; missing Files sections are inserted before Pickup Context within the assigned N. Dedup remains warn-and-preserve, so moving an already-listed row between sections requires rewriting both complete section bodies. Caller edits after the session entry was written (project docs, This Week, Tickler and report reconciliation) — pipe them as ``- `path` - what changed`` lines through `"{VAULT}/.claude/scripts/backfill-files-updated.sh" <log> N`. The script skips paths already in Files Created/Updated, keeps their existing descriptions, prints each incoming row it did not write, and ends with `<N> added, <M> skipped`. Exit 3 means it wrote nothing because every row was skipped: a result to read, not a failure to retry. Extend a skipped description in its existing section via `update-session-section.sh <log> N "<section>" --replace` with the **full new section body** (every retained row plus its updated description, no OLD/NEW separator payload) — after a fix round a `skipped` line for an already-listed path is the expected signal that its row needs rewriting, not a no-op; a created file stays in Files Created after later edits. If the caller has a Next Steps section, reconcile inline closures: an item that the caller closed comes out of `### Next Steps / Open Loops` (`--replace`, preserving the other lines).

Reconcile the Files lists with a fresh `session-ledger.sh --read`, the initial inventory (including its non-ledger backstop), and the collected propagation/close-out edits; backfill any attributed omissions before verification. The ledger alone is not complete. Reconcile the complete path set independently from attributed commit/merge ranges and tool calls, including parent-skill, shell and connector writes; do not infer ownership from a commit time window. Include renamed/deleted paths in the Files record with their actual status. Build `--touched` from the reconciled Files-list paths and deduplicate by the same resolved path (expand `~` and resolve vault-relative spellings), passing each path once. Keep distinct installed/source paths separate even when their basenames or contents match; repeated writes to one path are not separate files.

**Verify:** after the last backfill or Files-section rewrite, rerun **Assigned-session extraction** before the verifier block: an earlier extraction misses rows added since and hands the verifier a short `--touched` list. Run the verifier through the receipt wrapper and resolve every FAIL, re-running until clean. The block rebuilds `TOUCHED` from the extracted path list inside its own call:

<!-- BEGIN VERIFY -->
```bash
SESSION_PATHS="<SESSION_PATHS path printed by Assigned-session extraction>"
[ -f "$SESSION_PATHS" ] || { echo "ERROR: no extracted path list; rerun Assigned-session extraction" >&2; exit 1; }
TOUCHED=(); while IFS= read -r path || [ -n "$path" ]; do TOUCHED+=(--touched "$path"); done < "$SESSION_PATHS"
PARK_REVIEW="${PARK_REVIEW:-${CODEX_HOME:-$HOME/.codex}/skills/park/scripts/park-review.py}"
python3 "$PARK_REVIEW" run-verifier -- \
  "{VAULT}/.claude/scripts/park-verify.sh" "{VAULT}" "<session log>" N \
  --ident "<distinctive substring per item/identifier the session completed>" ... \
  "${TOUCHED[@]}"  # one --touched flag per complete path in the extracted list
```
<!-- END VERIFY -->

**`--touched` must be the log's own Files-list paths**, all of them — they are already enumerated by this point, so pass that list rather than a subset you retype. The verifier can only speak for the paths it was handed: a narrower list still prints `PASS backfill`, and a `REVIEW backfill` naming paths the log lists but the run never saw means the list was short, not that the log is wrong. `--ident` values must be distinctive strings — a bare number under ~4 digits matches digit runs inside phone numbers, order IDs and amounts, and a common word or a doc's name matches every item that mentions or links it, burying real hits in noise. Paths may be absolute, `~`-prefixed, or relative to `{VAULT}`.

Legacy free-form `on <host>` annotations are rewritten to the canonical `(remote)` form; do not silently omit a recorded remote path from `--touched`.

**Files rows the verifier parses.** A path containing ` - ` goes in backticks — `` - `03 Projects/Plan - draft.md` - what changed `` — because an unquoted one is settled by the longest left side that exists on disk, which fails once the file is gone; the backfill script backticks such paths itself, rows written by hand must too. Annotate a path not on this host's disk after the path: `(deleted)` only for a path that is gone (a bulk deletion inside a surviving directory gives every deleted path its own Files Deleted row, however many: the verifier accounts for a gone `--touched` path only through such a row, and `build` rejects a directory row), `(remote)` for a path on another host or network share that must not be read; these print `INFO backfill: ... not compared` instead of `REVIEW backfill`/`FAIL touched`. A touched path on a network/FUSE mount, over 2 MiB or binary is checked for existence only and announced as `PASS touched: existence-only (<reason>): <path>`; `PARK_VERIFY_REMOTE_PREFIXES` (colon-separated) names mounts the filesystem probe cannot classify; a prefix covering the vault root itself does not exempt vault files from content checks, only a subtree prefix does. `PARK_VERIFY_MAX_CONTENT_BYTES` overrides the size threshold.

It checks the deterministic layer: session numbering, required sections, Project line (compare its printed line against the caller’s metadata — fix the log if they differ), stranded locked-edit separator lines, list-join/blank-line lint on touched files, unchecked planning-doc items matching each ident, that each touched path exists (`FAIL touched`: mistyped or truncated), and Files-list coverage of touched paths. **A closure `PASS` is not a completion check:** it means no unchecked line matched, which an ident present only in ticked lines also produces. An ident absent from every planning file prints `N/A closure: ident '<ident>' absent from every planning file (<k> checked)` and the `RESULT` line carries the N/A count; N/A is not a pass — usually a misspelt or never-tracked ident — and a run whose every ident is N/A has verified nothing about closures. An ident is the stable identifier the planning line itself carries — the path, booking reference or the item's own wording — never a verb, a paraphrase or a status word such as "done". Two closure classes the verifier cannot see are checked by that same identifier grep, not by the ledger: an item already ticked `[x]` before close-out that this session resolved (`grep -n -i -F -- "<ident>" <file> | grep -F '[x]'`) still gets the `→ [[log]] (Session N)` backlink appended via `locked-edit.sh --replace` when its line lacks one; and a task the user discharged by pasting content into the conversation, which writes no file and leaves no ledger row — enumerate these from the session's Summary and grep each one's identifier. A "line gone" conclusion is the identifier grep on the live file returning empty **after** the same grep matched the session's own pre-state excerpt; an empty grep for a different string or a verb is not that evidence. Judgement stays with you: each closure `REVIEW` hit is an item the caller wrote during routing (expected: ignore the hit, keep the item), an item the session genuinely completed — flip `[ ]`→`[x]` via `locked-edit.sh --replace` with a `→ [[log]] (Session N)` backlink (Tickler flips only after confirming it's the very item resolved — a false flip silently kills deferred work) — or an adjacent still-open item: surface it in Pickup Context, don't action it. Passing edited-file basenames as extra `--ident` args catches adjacent open items mechanically. Once an adjacent-open hit has been recorded in Pickup Context, the final rerun may omit only that discovery-only basename while retaining every core completion/value identifier; record the triage rather than accepting an unexplained `REVIEW` forever.

**One accepted-FAIL class:** a lint hit in content the session never wrote, where the file's classification receipt proves every session delta was an exact declared locator/token substitution, carries pre/post lint fingerprints proving the edit introduced no lint, and records `--allow-inherited-lint`. "Fixing" inherited lint means reformatting the user's own notes, which a standing instruction forbids. An unchanged imported file classified as `reference` also qualifies when its current SHA-256 and retained source/review snapshots match the classification receipt. This preserves source formatting without changing its bytes. Session-authored semantic content does not qualify; missing, stale or corrupt reference receipts fail closed.

When this is the verifier's **only** failure, rerun through `run-verifier` with one `--accept-inherited-lint "<path>"` before `--` for every affected file. The wrapper accepts only paths pre-approved by those mechanical or intact-reference receipts, an exact path-set match over the complete multi-line lint block, exactly one `FAIL lint`, zero `REVIEW` lines, and `RESULT: FAIL (1 fail, 0 review)`; any additional or differently scoped issue remains a failing receipt.

Output: the script's `RESULT:` line plus what you fixed.

**Final evidence check:** re-read current edited regions and routed-task destinations, then extract only the assigned Session N with **Assigned-session extraction**. In each later call, set `SESSION_BLOCK` to its printed path: run §19's behaviour-claim command with `"$SESSION_BLOCK"` as the file argument, trace each past-event/approval/status claim to its evidence, and print a fresh `Value check:` line. Run the count-word scan with `SCAN_INPUT` set to that path in the same call, and on every rewritten description; reconcile all sections, including the heading and Key Insights, with surviving open items. Search retired wording separately in this session block (the live-vault sweep excludes the archive). Repeat this executed pass after every fix or later user/world-state change; a prior mental pass or a whole-day file read does not discharge it.

## Independent review

**Review packet currency and reach:** after a fix, rewrite affected Files descriptions with the **whole new section body**, then regenerate scope, attribution (§20), evidence and inspection targets from the current assigned entry. Search the rebuilt brief for retired wording and fragile count/back-reference tokens before sending it; re-read changed source regions and refresh their hashes. A user edit or new status during/after review is another fix round: reconcile the entry, delta propagation, verification and brief before accepting it, or wait for the user's editing to pause.

Embed the parent's literal propagation commands (argv, cwd, exclusions and statuses) beside their results, with digest-bound complete raw receipts and bounded contexts when display is large. Keep separately scoped supplemental excluded-text/non-vault executions and their dispositions tagged beside the primary report; they do not replace the required default vault-coverage row or widen its coverage claim. Include raw hash commands/output and declare whether the seat has shell. A shell-denied seat must search without negated exclusion globs, first detect a known positive control, search hidden directories by explicit path, and triage archived hits by path. Its Grep may honour ignore files and omit non-Markdown text: supply the parent's `--hidden --no-ignore` receipts for that surface; a Grep null cannot supersede them. Vision transcriptions by the same session are `[unverified]` until the decisive detail is rechecked at native resolution. Report a required remote deployment separately as `Needs main session: remote copy`; source repair does not claim the remote copy changed.

**Script probes:** embed this boundary in the reviewer brief: the reviewer may run a command only after reading its argument handling and establishing that the invocation is read-only. Otherwise copy its required inputs into a disposable scratch directory outside the vault and installed config, redirect all output/state there, and probe that fixture. `--help` is not evidence of a read-only command. If isolation cannot be established, inspect the source and report the execution check unverified; never weaken host policy or bypass a missing sandbox.

Run the independent close-out audit, remediate confirmed findings, and **re-audit until a full pass finds no further findings**. Keep the delta-aware scope and read-only reviewer; the main session owns remediation. This does not invoke `$audit` or its panel. **The caller’s export, provenance and completion must wait for the final clean report and accepted audit receipt.** Park’s Setup delegation-unavailable checkpoint is the explicit incomplete-bookkeeping exception; it never permits a caller completion claim.

Generate the brief from the post-backfill session log, raw session ledger, locked-edit/classification receipts, propagation receipt, latest verifier receipt, evidence receipts and hash-matching prior audit receipts:

```bash
python3 "$PARK_REVIEW" build --vault "{VAULT}" --session-log "<session log>" --number N --check-dependencies
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

For each completed report, re-run `session-ledger.sh --read` and reconcile any row attributed to the reviewer against the read-only contract. An unexpected reviewer write is not cured by a clean final file: inspect the target for lost concurrent content, replay any warranted vault delta through `locked-edit.sh`, and add the path to attribution/backfill. Then sanity-check each finding in the live file. **A coverage finding is closed by a re-run search, not by rewording.** When a finding says a search, grep or enumeration could have missed something (a quoted or differently spelt argument, an unread log or location), re-run a widened search that would have caught the miss the finding names, cite its argv and output (or receipt path) beside the remediation, and let that result decide the claim. Narrowing the claim's wording without the re-run leaves the finding open. When the widened search cannot be run, removing the claim, or scoping it explicitly to the surface actually searched, also closes the finding.

**Remediate and repeat:** the main seat fixes confirmed, attributable findings using the normal locked write mechanics, backfills newly touched paths while reporting each fix to a path already in the Files list as `<path>: description extension: <text>` and rewriting its **complete section body**, retaining every other row, with `update-session-section.sh --replace` (§23), refreshes affected classification/evidence receipts, re-reads the changed portions and reruns **Backfill and verification**. Rebuild the brief, then use `collaboration.followup_task` to send the same independent reviewer the new brief path and SHA-256, with instructions to verify its digest and run the full scoped checklist again. Collect and assess that report by the same contract. Repeat after every fix round; there is no one-round cap. An incomplete report or missing attestation also requires a follow-up before claiming clean.

If a finding requires unavailable evidence, a user decision or action beyond the authorised scope, report the concrete blocker and retain it as an open loop; do not label the audit clean or the caller complete. For a disputed finding, send the reviewer the counter-evidence; unresolved disagreement is a blocker, not grounds for silently accepting or endlessly repeating the finding.

On a clean report, pipe it into `python3 "$PARK_REVIEW" record-audit --reviewer "<resolved task name or agent ID>" --from-brief`. The helper refuses a receipt unless the report says clean and attests every full-read snapshot against its original path. `ATTEST` rows are only for those full reads; targeted hashes stay outside them. Every new built review, including a full-read set, requires exactly one `COMPLETE <SHA-256 of the exact brief bytes>` line. The resulting schema-3 `kind: completion`, `completion: true`, `completion_binding: 1` receipt binds the subject/packet; an all-targeted set has no invented reusable full-read attestation. Standalone `--file` imports are `kind: source-attestation`, `completion: false` and establish reuse only, never close-out completion. It then checks the live originals: unchanged files remain eligible for later audit reuse; a changed file is accepted only when post-snapshot locked-edit receipts from other sessions form a complete hash chain and every session-owned locator remains intact. Traceable disjoint edits by another session therefore do not invalidate this close-out, but that file's snapshot receipt is not reused as a clean audit of its newer live bytes. A post-snapshot edit by this session requires a rebuilt brief and new review; an untraceable change or missing owned locator fails closed as possible overlap. A targeted session log tolerates later writes only as appended new `## Session` entries, or as edits confined to other existing entries when its preamble is byte-identical, the assigned entry is byte-identical apart from trailing line endings, at least one inspection target for the log exists, and every such target names the assigned `Session N` and no changed entry; anything else requires a rebuilt brief. The helper persists `pending`, completes its final live-byte check, then atomically promotes the receipt to `clean`, so interruption cannot strand a reusable receipt before finalisation. Do not create a clean receipt after findings/remediation without a new independent full read.

Check that `record-audit` actually printed an accepted clean receipt in a separate successful call; a standalone invocation with no `--file` and no `--from-brief` fails rather than exiting zero without a receipt. Retain the accepted receipt and manifest per **Completion evidence** before returning to the caller.

Output: `✓ Audit: clean pass` or `🔧 Audit: N findings fixed and re-audited clean — see [paths]`. If blocked: `✗ Audit: not clean — [blocker]`; do not proceed to the completion message.

**Late bookkeeping boundary:** the caller's monitor/export/provenance outputs and this protocol's generated receipts/review packets are close-out bookkeeping, not newly authored session work: retain their own receipts without retroactively adding them to the accepted Files list or recursively reviewing copied evidence. A later substantive content or state edit is another review round. Declare this boundary consistently in nightly, catch-up and merged entries.

## Completion evidence

A report and a session entry prove that writing began, not that review completed. Retain the accepted independent report with its exact log path and assigned N so C1 can distinguish completion from interruption. Missing, incomplete or mismatched evidence does not authorise a clean verdict. Do not rewrite the session entry after acceptance just to stamp it complete; keep export/provenance after acceptance.

Use the accepted receipt's exact `session_log`/`session_number`, clean terminal report hash and immutable `manifest_snapshot`/`brief_snapshot` digests. The manifest snapshot must bind the same subject, generation and brief hash. **Completion lookup** checks these records in native and shared stores; the mutable latest manifest is not historical acceptance evidence. Missing, malformed or mismatched new-style proof is not a clean result. Older receipts/reports without the bound fields are historical candidates for explicit subject/brief/verifier review, not automatically invalidated or silently promoted. Later sessions are handled by C2, not by invalidating a historical verdict whenever shared file bytes change.

**Shared-store retention (Codex):** after `record-audit --from-brief` prints an accepted receipt, set `ACCEPTED_RECEIPT` to that exact path and retain byte-identical evidence beside the Claude records. This copies accepted artifacts, not a second acceptance tracker. The receipt's subject/digests remain authoritative; differing existing files fail instead of overwriting another run.

<!-- BEGIN COMPLETION RETENTION -->
```bash
SID="$(. "{VAULT}/.claude/scripts/lib-session.sh"; _session_id)"
[ -n "$SID" ] || exit 1
BUNDLE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/${SID}.closeout/$(basename "$SESSION_LOG" .md)-session-${N}/$(basename "$ACCEPTED_RECEIPT" .json)"
python3 - "$ACCEPTED_RECEIPT" "$BUNDLE" "$SESSION_LOG" "$N" <<'PY'
from pathlib import Path
import hashlib, json, sys
source, bundle, log, number = Path(sys.argv[1]), Path(sys.argv[2]), str(Path(sys.argv[3]).resolve()), int(sys.argv[4])
r = json.loads(source.read_text(encoding="utf-8")); report = r.get("report", "")
if not (r.get("schema") == 3 and r.get("kind") == "completion" and r.get("completion") is True
        and type(r.get("completion_binding")) is int and r.get("completion_binding") == 1 and r.get("status") == "clean"
        and (r.get("session_log"), r.get("session_number")) == (log, number)
        and report.splitlines().count("COMPLETE "+str(r.get("brief_sha256"))) == 1
        and report.rstrip().endswith("Terminal state: clean")
        and hashlib.sha256(report.encode()).hexdigest() == r.get("report_sha256")):
    raise SystemExit("ERROR: receipt does not establish this clean close-out")
def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data: raise SystemExit("ERROR: retained evidence collision")
    else:
        with path.open("xb") as handle: handle.write(data)
for key, digest_key, name in [("manifest_snapshot", "manifest_sha256", "review-brief-manifest.json"),
                              ("brief_snapshot", "brief_sha256", "review-brief.md")]:
    data = Path(r[key]).read_bytes(); digest = r[digest_key]
    if hashlib.sha256(data).hexdigest() != digest: raise SystemExit("ERROR: accepted snapshot digest mismatch")
    save(bundle/"snapshots"/(digest+".snapshot"), data); save(bundle/name, data)
save(bundle/"review-report.md", report.encode()); save(bundle/"audit-receipt.json", source.read_bytes())
print("Completion evidence retained:", bundle)
PY
```
<!-- END COMPLETION RETENTION -->

### Completion lookup

Run this read-only lookup with exact `SESSION_LOG` and assigned `N`. It checks native manifest/receipt pairs and lists legacy saved reports for exact-subject verification; no filename or bare heading certifies completion. `ACCEPTED` is the positive observation; `NO_ACCEPTED_RECEIPT` means the structured stores did not establish completion, while `LEGACY_CANDIDATE` still needs its header, brief digest, final verifier and clean verdict read.

<!-- BEGIN COMPLETION LOOKUP -->
```bash
python3 - "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state" "$SESSION_LOG" "$N" <<'PY'
from pathlib import Path
import hashlib, json, sys
state, log, number = Path(sys.argv[1]), str(Path(sys.argv[2]).expanduser().resolve()), int(sys.argv[3])
def load(p):
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError): return {}
def snapshot(receipt_path, r, key, digest):
    # A shared-store bundle retains byte-identical snapshots if native scratch is gone.
    local = receipt_path.parent/"snapshots"/(str(r.get(digest))+".snapshot")
    path = local if local.is_file() else Path(str(r.get(key, "")))
    try: data = path.read_bytes()
    except OSError: return None
    return data if hashlib.sha256(data).hexdigest() == r.get(digest) else None
receipts = list((state/".park-audit-receipts").glob("*.json")) + list(state.glob("*.closeout/**/audit-receipt.json"))
accepted = []
for rp in receipts:
    r = load(rp); report = r.get("report", "")
    if r.get("kind") == "source-attestation": continue
    clean = (r.get("status") == "clean" and isinstance(report, str)
             and report.rstrip().endswith("Terminal state: clean")
             and hashlib.sha256(report.encode()).hexdigest() == r.get("report_sha256"))
    if not clean: continue
    if (r.get("schema") == 3 and r.get("kind") == "completion"
        and r.get("completion") is True and type(r.get("completion_binding")) is int and r.get("completion_binding") == 1
        and (r.get("session_log"), r.get("session_number")) == (log, number)
        and report.splitlines().count("COMPLETE "+str(r.get("brief_sha256"))) == 1):
        raw = snapshot(rp, r, "manifest_snapshot", "manifest_sha256")
        brief = snapshot(rp, r, "brief_snapshot", "brief_sha256")
        try: m = json.loads(raw) if raw is not None else {}
        except ValueError: m = {}
        if (isinstance(m, dict) and m.get("schema") == 3 and type(m.get("completion_binding")) is int and m.get("completion_binding") == 1 and brief is not None
            and (m.get("session_log"), m.get("session_number")) == (log, number)
            and m.get("run_generation") == r.get("run_generation") and r.get("run_generation")
            and m.get("brief_sha256") == r.get("brief_sha256")):
            accepted.append(str(rp))
    elif r.get("kind") == "legacy-review" and (r.get("session_log"), r.get("session_number")) == (log, number):
        print("LEGACY_CANDIDATE", rp, sep="\t")
    elif "session_log" not in r:
        for mp in state.glob("*.park-review/runs/*/review-brief-manifest.json"):
            m = load(mp)
            if ((m.get("session_log"), m.get("session_number")) == (log, number)
                and m.get("run_generation") == r.get("run_generation") and r.get("run_generation")):
                print("LEGACY_CANDIDATE", rp, mp, sep="\t")
for r in sorted(set(accepted)): print("ACCEPTED", r, sep="\t")
if not accepted: print("NO_ACCEPTED_RECEIPT")
for p in sorted(state.glob("*.closeout/**/*.md")):
    try: text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeError): continue
    if log in text and (f"Session number: {number}\n" in text or f"Session N: {number}\n" in text):
        print("LEGACY_CANDIDATE", p, sep="\t")
PY
```
<!-- END COMPLETION LOOKUP -->

A lookup null is trusted only after a known accepted log/N in these same stores returns `ACCEPTED`; a wrong N or tampered report must not. Inspect `LEGACY_CANDIDATE` evidence manually before calling a historical close-out incomplete. For pre-retention-rule entries, record `historical completion evidence unavailable` once, preserve any verified historical disposition, and do not manufacture a clean receipt or repeatedly re-audit unchanged old work merely because that evidence was never required.
