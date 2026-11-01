# Shared close-out protocol

Used by Park and Goodnight, including Goodnight C1 catch-up. Read this file from the same installation as the caller’s shared rules; a missing dependency blocks the affected close-out. Install this file before its consumers. This protocol does not invoke either caller or the audit skill.

## Caller contract

At setup, the caller supplies the resolved vault and actual parent session ID. Before verification, it supplies the log path and assigned N, attributed files, raw evidence/pre-state, final identifier enumeration and propagation result, and its specific acceptance checks. Keep numbered steps, routing policy and final messages in the caller. Park retains quick-mode eligibility and its incomplete checkpoint; Goodnight retains debrief → report → carry-forward → collapse → session entry → review → export → provenance. A failed review never permits a successful close-out message or provenance processing.

For Goodnight, the day’s earlier sessions are evidence for the report, not writes owned by this run. During C1, record a ledger/action boundary before each date’s work: the helper session ID stays the actual parent ID, while attribution is only this date’s close-out delta. Re-read the ledger at each boundary; prior dates’ and concurrent sessions’ paths are not silently claimed. A shared path modified in this date still belongs to this date’s Files list.

Set `PARK_ARTIFACT="{VAULT}/.claude/scripts/park-artifact.py"` and `PARK_ARTIFACT_STATE="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/.park-artifacts"`; check the helper exists. Check the Agent interface before beginning.

Keep count of completed independent reports, rounds of parent fixes and distinct confirmed findings. Record wall-clock start/end of inventory, verification and review using `date +%s` in existing tool calls; label waits and user interaction separately. Report observed elapsed times and unknowns without claiming a speedup. Park retains its existing metrics recorder; do not send Goodnight runs to the Park-only recorder.

## Evidence

Retain the caller’s own pre-edit reads before changing status, carrying tasks or collapsing sections. Preserve raw command invocation, working directory, exit status and discriminating stdout/stderr; keep primary, secondary and unverified provenance distinct (§16). Do not reconstruct pre-state from auto-save git. Assemble these exact excerpts with their source paths in the independent review brief.

## Inventory

**Enumerate every file the session created or edited** — vault and non-vault. Recall reliably under-reports the non-vault half (early config edits, tooling side-effects, hook-written files), so derive it mechanically:

```bash
"{VAULT}/.claude/scripts/session-ledger.sh" --read -m auto
"{VAULT}/.claude/scripts/park-files.sh" "{VAULT}" -m auto [--root DIR ...] [repo ...]
```

Pass `--root <dir>` (repeatable) for every directory the session installed into or wrote under that the default sweep does not cover — `~/.local/bin`, `~/.config`, `/etc`, `~/.claude/settings.json` itself (a file root is listed as a `[root]` row; passing the whole `~/.claude` tree floods the inventory with transcripts), build or `__pycache__` output — an explicit root prunes only `.git`, so cache byproducts under it are listed. Read the first output line, `# roots searched:`: a directory absent from it was not searched, so a write there is found only by recall. **Remote writes are a recall-only class.** Nothing on this machine sweeps a file pushed to another host (ssh, scp, rsync to a remote, a remote API that stores a file), so list each from the session's own tool calls as a `[remote]` row (`host:path — what changed`) beside the scanned candidates and carry it into the Files rows in the verifier's form, `- host:path (remote) - what changed` (the `(remote)` annotation and ` - ` separator are what the parsers read); a `[remote]` row is never produced by a scan.

The ledger identifies the session where it reaches: Write/Edit hooks record writes, and `locked-edit.sh`, `locked-ingress.sh` and the session-log writers (`write-session.sh`, `update-session-section.sh`, `backfill-files-updated.sh`) self-ledger shell-mediated writes. Obsidian move collateral performed by `locked-edit.sh` is recorded too. Other raw shell, script and MCP mutations can bypass those recorders, so the mtime/ctime and git candidates remain the backstop. The `agents` column names the writer only when identity was supplied; `?` means unknown, not `main`. Reconcile unknown-agent rows with the session's tool/action evidence rather than assigning them to a thread by inference. Two distinct failure observables, both meaning "fall back to park-files.sh alone and say so": `NOTE: no ledger` (no hook or self-ledger write has landed yet), and `ERROR: no session id` (no harness session id resolvable — see lib-session.sh) with **exit 1** — that exit 1 is expected here and is not the invocation error the session writer warns about. Hook-recorded sub-agent writes carry this session's ID and supplied agent ID; shell-mediated writes need the explicit parent-session prefix in their brief. Account for those writers against actual tool/action evidence before excluding a row. `# CONCURRENT-SESSION` lines are therefore genuinely other sessions: exclude per §20 and say so. `-m auto` sets both look-backs from the session's start (the earlier of its first ledger row and its transcript's first record) plus a 30-minute margin and prints `# window: -m <N> from <start> ...` as the ledger's first output line and park-files.sh's second; report that line beside the inventory. A `(default)` window line found no start and fell back to 240 minutes: say so and rerun both commands with `-m` minutes over-covering the whole session, since `-m` also drops this session's own rows older than it. The `# ledger begins` line is the ledger's coverage start — writes that predate the hook being wired are not in it, which is one more reason park-files.sh stays.

The parent-session ledger key and writer identity are separate. Keep the parent `OPENCAIRN_SESSION_ID` prefix on dispatched writes. Self-ledgered writes use explicit `OPENCAIRN_AGENT_ID` when supplied, otherwise `codex:<the actual writer CODEX_THREAD_ID>`; unidentified shell writers remain `?`. Do not infer main/child identity from time or convert legacy unknown rows to main. For a harness without a writer thread ID, pass `OPENCAIRN_AGENT_ID` only when the actual agent handle is known.

Reconcile park-files.sh's candidate lines (sync-receipt, config/runtime mtimes or ctimes, `[root]` extra-root hits, repo status, `[vault]` body files, `[git-diff]` working-tree changes, `[git-history]` recent vault commits and transient surfaces) against the ledger and the session's actual tool/action evidence. Git rows contain the repo root, status and repo-relative path; rename rows contain both the original and destination paths. Resolve each against that repo root, use deletion and rename rows to recover removed or moved paths, and preserve intermediate history paths that a later auto-save removed. These are candidates, not attribution: a time-window match does not make another session's or already-parked work yours. Add each attributable path you were about to omit, and exclude other sessions' work per §20. Display the list.

**Confirm every inventoried path exists before it becomes a Files row.** The structural index (`obsidian links`, `obsidian unresolved`) lags fresh binaries and renames, so it cannot confirm presence. Run `ls -l -- "<exact path>"` on each path the inventory produced: exit 0 with the listing means the path is live; `No such file or directory` (non-zero exit) means it moved, was renamed or was deleted. Treat a missing path as a move to resolve — find the new path (ledger rows, `[git-diff]`/`[git-history]` `R`/`D` rows, `find` on the basename, the session's own tool calls, the user) and record it under Files Updated at the new path with `renamed from <full old path>` in the description (the old path goes under Files Deleted when it is gone), or under Files Deleted when deletion is evidenced. Never drop a missing path silently, and never write an unannotated local Files row for a path `ls` cannot find — a path that is gone is a `Files Deleted` row or a `(deleted)` annotation, a path on another host is a `(remote)` row.

**Session-local inventory boundary:** cover the full session window even when shell/bypass mode leaves the ledger incomplete. Add the actual harness scratchpad path with `--root` and the specific runtime output roots of tool-invoking tests (for example the relevant `~/.local/state` subtree). Do not sweep the whole `.session-state` tree: name this session's ledger/receipt/run paths and any shared artifact-cache manifest actually used. A scratchpad reset is an evidenced deletion, not an inferred move; keep its directory-recreation evidence. Reconcile note renames/deletions against canonical move receipts; an unreceipted relocation needs review. Before disposing of a sync-conflict filename, read the vault's sync workflow and record its required disposal route.

## Coverage

Apply receipt import/classification only to the caller’s attributed scope. In C1, prior dates’ move receipts do not add paths to this date’s inventory unless action evidence shows this date changed them.

Keep every attributed lexical path spelling, including symlink aliases, in the Files record. Do not infer a deletion from a missing or dangling retained path: resolve its actual status from action evidence. For an older log changed only by `add-forward-link.sh`, inspect its producer receipt and exact inserted locator; missing or mixed-write proof requires ordinary semantic coverage. There is no automatic preparation command in this lane.

**Classify first; inspect proportionally.** Display one class, byte/line counts and coverage reason for every created or edited artefact, then per-class file and byte totals (semantic delta apart from reference, generated and archive bytes) before the first read. Group byte-identical copies (same SHA-256 at distinct paths) under one primary: read it once and cover each copy by its hash match. A bounded semantic note requires a full coherence read even for a small edit; historical continuation-only deltas may stay targeted with producer proof. Before classifying, inspect any schema-2 JSON files under `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/${CLAUDE_CODE_SESSION_ID}.project-move-receipts/`: add every `affected_files[].path` and `unverified_files[]` path to the inventory. Treat an affected file as mechanical only when its current hash matches `post_sha256`, its pre/post lint fingerprints match, its diff is complete, and the receipt records an exact link-target-only heal. Classify unverified or later-edited files ordinarily. This applies inside `06 Archive/`; never repair unrelated archive prose or inherited lint.

- **Bounded semantic text** — session-authored prose/config/code of ordinary reviewable size: read it in full once. Mid-session direction changes can leave stale residue outside the edited span.
- **Large semantic artefact** — a session-authored output where a full read is disproportionate: inspect the session delta, the surrounding structure needed to judge coherence, and outcome-specific rendered/tested regions. State exact pages, sections, line ranges or checks; do not claim whole-file coverage.
- **Local reference artefact** — a manual, textbook, paper, dataset or other source copied/downloaded but not authored this session: hash and identify it, then inspect only passages the session used or claims it supports. Never read the whole source merely because it was touched. Prepare its immutable receipt with `python3 "$PARK_ARTIFACT" --source "<file>" --original "<file>" --state-dir "$PARK_ARTIFACT_STATE"`; text extraction is an index, not evidence every page was reviewed. `text_status: empty` or `unsupported` proves no text coverage, so use targeted rendering/OCR only if a session claim depends on it. A session-captured binary (a screenshot, an export) is this class: its coverage is the artefact receipt's hash and `text_status`, not a read.
- **Mechanical-only** — exact locator/token substitutions: inspect the whole replaced line/paragraph for co-located measurements and dependent clauses before assigning this class; a changed fact/premise is semantic. Then inspect the exact replacement and changed span, not the whole file.
- **Generated directory** (build output, an extracted archive) — tool-generated bytes only: first reconcile its files with the ledger and tool writes, give each session-authored file inside it (script, prompt, config) its own semantic row and exclude it from the manifest. List and hash the rest (`find "<dir>" -type f -print0 | sort -z | xargs -0 sha256sum`) rather than reading them; the listing and digests are the coverage. Save that listing outside the vault under `$PARK_ARTIFACT_STATE/manifests/<session-id>-<directory-slug>.sha256` and name the manifest, not the directory, in the Files rows: the content checks read regular files only.
- **Unreadable path** (`EACCES`, root-only) — record it in the Coverage receipt as `<path>: unreadable: coverage incomplete` with the remedy named beside it: re-run with access, or a substitute check (owner-supplied hash, sanitised metadata). Never omit it silently.

Do not perform the quality read here; Park's enumeration check and any required propagation despatch precede the expensive quality pass; Goodnight inspects before its final verification.

## Quality inspection

Inspect each artefact as its Coverage class prescribes. Across that semantic coverage, fix broken syntax/links/paths, stale interim state, prose that contradicts a table, heading or list in the same doc, a `Last updated:` stamp older than the session's edit to its doc, redundancy, typos and spelling per the user's locale, draft-era filename residue after a terminal status change (rename via link-healing move, not raw `mv`), and hook collateral on verbatim external text (§14 — repair via shell, never Edit/Write). If a locale-lint script exists (`.claude/scripts/locale-lint.sh`), run it once over attributed prose paths from the ledger's Write/Edit, `locked-edit` and `locked-ingress` rows — never the mtime backstop's output — and apply only context-valid candidates, always skipping URLs, quoted spans and capitalised runs. Record candidate, applied and skipped counts, including zero. A durable new doc must be linked from a durable parent. For an override, enumerate every imperative in the interval and mark it suspended or retained. Don't auto-revert changes you didn't make — surface them.

**Coverage receipt:** after inspection, display `Files read in full: [exact paths | none]`, `Targeted coverage: [path: pages/sections/ranges/checks | none]` and `Mechanical substitute: [exact receipt paths/checks | none]`. Keep this tied to what was actually read or verified, not the intended inventory class; an omitted or truncated read remains incomplete until the stated substitute is performed.

**Wikilinks resolve through the structural index, not by eye.** Probe `obsidian version` first; a CLI that is absent or not responding means this check did not run, and the output says so (§24). When it runs: `obsidian unresolved` once, inspected for targets or basenames this session introduced, then `obsidian links` (argument form per `obsidian help links`, §24) on every edited file that added or changed a wikilink, confirming each new link resolves at file level. An empty result straight after edits can be a reindexing blank, not a pass (§24): re-query once settled. Heading anchors are outside the index: open each target and match the heading text exactly. An eyeball pass is the fallback for anchors only, never the file-level check.

**SOURCE check:** run `_shared-rules.md` §19 over the enumerated files; its required output line is part of this gate. For each decision-bearing command, retain its literal invocation, working directory, exit status and discriminating stdout/stderr before cleanup or brief assembly. State which observation separates pass from fail; include empty/error output when it controls a conclusion. A prose success summary, recreated command or bare exit 0 is not the evidence. Preserve the raw result in the full-path evidence/pre-state handoff, with an exact path and digest for any companion file the reviewer must inspect.


**Semantic conformance checks (use the applicable rows, not a new pass per anecdote):**

| Changed surface | Required comparison and retained observation |
|---|---|
| Approved implementation | List each applied change beside its approving decision/checklist item; flag an unmatched change before saving the session record. |
| Governing prose and state | Read the subject's sections, including already-edited lines and the instructions above an appended status paragraph. Compare final state with headings, table legends/owners, adjacent clauses, list predicates and diagram labels/classes; account for each stale clause, not only matching tokens. Apply this after membership additions as well as status flips. |
| Sources and derivations | Execute §19 before the log, including every cited clause and synthesis line. Compare a derived document item-by-item with its declared source's caveats; verify attributed linked-note content in the destination. Match ordered sequences against their source (`N/N`), and give appended claims their own provenance rather than inheriting a paragraph's tag. Public figures must retain any load-bearing discretionary/derived assumption. |
| Procedures and code | Read header/docstring constraints for behaviour changes, run a minimal fixture for each claimed behaviour, and compare a durable recipe with the command actually executed (name deliberate generalisations). Walk a written procedure in order: each path, control or resource a step probes exists now or is created by a named earlier step. A new prohibition/rule requires searching its own runnable blocks and templates/examples for contradictions. Check destructive-automation cadence/order; a timed-stop fixture must advance time during blocking work and verify children stop, checkpoint/guard restoration and no completion marker. |
| Instruments and branching claims | Calibrate a checker with known-present and known-absent inputs, including a valid case after a short/skipped token; retain distinct outputs before citing its null. Trace the branches a written next-action claim covers, rather than accepting neighbouring prose as proof. |
| Locators and owning context | Resolve bare paths against the document's defined shorthand. Read a linked parent hub's constraints and each destination heading before changing a still-valid SSOT locator. Use code locators for extensionless scripts rather than unresolved wikilinks. New guides need their owning index/table row or an explicit exclusion; a cross-area move needs a route from the destination area's index/hub. |
| Renders | A session-rendered PDF/image is semantic output, not an imported reference: inspect a representative page visually plus each outcome-critical region. Regenerate sibling PDF/HTML/site renders after the final source edit and verify the final edited content appears; timestamps/text extraction alone do not prove visual fidelity. |

Run and display the count-word/ordinal/back-reference/relative-time scan over final authored spans, including replacement/deletion seams and Files descriptions. Set `SCAN_INPUT` to each retained authored span or the assigned-session block; this scan finds candidates rather than proving prose valid.

<!-- BEGIN DURABILITY SCAN -->
```bash
SCAN_RC=0
rg -n -i '\b(one|two|three|four|five|six|seven|eight|nine|ten|both|all|first|second|third|former|latter|above|below|this (line|section)|tomorrow|yesterday|next (day|week))\b' "$SCAN_INPUT" || SCAN_RC=$?
[ "$SCAN_RC" -le 1 ] || exit "$SCAN_RC"
printf 'Durability scan: %s (0=candidates, 1=no candidates; every candidate needs triage)\n' "$SCAN_RC"
```
<!-- END DURABILITY SCAN -->
 Recompute retained counts and rewrite fragile references; repeat after every later edit or fix round. For document stamps, search case-insensitively for the form the document uses (`Last updated`, `Last update`, `Current as of`, `Updated:`), not one preferred spelling.

Output: `✓ Quality check: B bounded semantic files full-read; T large/reference artefacts target-inspected; M mechanical spans checked`, `🔧 Quality check: fixed N issues — [file: fix]`, or — when the checked inventory is empty — `✓ Quality check: no attributed files (writes deferred to the later caller steps)`. The empty case is a result, not a skip: planning and research sessions can legitimately make their first writes during Park, and the later writes still pass their step contracts, shared verification and review.

## Backfill and verification

### Assigned-session extraction

Use this same bounded extraction for Summary quoting, final checks and `--touched`. Set the exact assigned `SESSION_LOG` and `N`; write scratch output outside the vault. A missing/duplicate N fails instead of borrowing a concurrent entry.

<!-- BEGIN SESSION EXTRACT -->
```bash
set -e
SESSION_BLOCK="$(mktemp)"; SESSION_PATHS="$(mktemp)"
python3 - "$SESSION_LOG" "$N" "$SESSION_BLOCK" "$SESSION_PATHS" "{VAULT}" <<'PY'
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
TOUCHED=()
while IFS= read -r path || [ -n "$path" ]; do TOUCHED+=(--touched "$path"); done < "$SESSION_PATHS"
```
<!-- END SESSION EXTRACT -->

Read the extracted block and path list. Keep lexical aliases in the Files record; normalise/deduplicate the verifier's arguments by resolved identity while retaining distinct source/install paths. Every Files row written or rewritten now uses backticks around its complete path, so ` - ` in a filename is unambiguous. For a legacy ambiguous row, re-read and canonicalise its complete existing section before rerunning; never silently shorten a path.


**Backfill:** `--section "Files Created"`, `--section "Files Updated"` (default) or `--section "Files Deleted"` selects the destination; missing Files sections are inserted before Pickup Context within the assigned N. Dedup remains warn-and-preserve, so moving an already-listed row between sections requires rewriting both complete section bodies. Caller edits after the session entry was written (project docs, This Week, Tickler and report reconciliation) — pipe them as ``- `path` - what changed`` lines through `"{VAULT}/.claude/scripts/backfill-files-updated.sh" <log> N`. The script skips paths already in Files Created/Updated, keeps their existing descriptions, prints each incoming row it did not write, and ends with `<N> added, <M> skipped`. Exit 3 means it wrote nothing because every row was skipped: a result to read, not a failure to retry. Extend a skipped description in its existing section via `update-session-section.sh <log> N "<section>" --replace` with the **full new section body** (every retained row plus its updated description, no OLD/NEW separator payload) — after a fix round a `skipped` line for an already-listed path is the expected signal that its row needs rewriting, not a no-op; a created file stays in Files Created after later edits. If the caller has a Next Steps section, reconcile inline closures: an item that the caller closed comes out of `### Next Steps / Open Loops` (`--replace`, preserving the other lines).

Reconcile the Files lists with a fresh `session-ledger.sh --read`, the initial inventory (including its non-ledger backstop), and the collected propagation/close-out edits; backfill any attributed omissions before verification. The ledger alone is not complete. Reconcile the complete path set independently from attributed commit/merge ranges and tool calls, including parent-skill, shell and connector writes; do not infer ownership from a commit time window. Include renamed/deleted paths in the Files record with their actual status. Build `--touched` from the reconciled Files-list paths and deduplicate by the same resolved path (expand `~` and resolve vault-relative spellings), passing each path once. Keep distinct installed/source paths separate even when their basenames or contents match; repeated writes to one path are not separate files.

**Verify:** run the verifier and resolve every FAIL, re-running until clean:

```bash
"{VAULT}/.claude/scripts/park-verify.sh" "{VAULT}" "<session log>" N \
  --ident "<distinctive substring per item/identifier the session completed>" ... \
  "${TOUCHED[@]}"  # one --touched flag per complete path from Assigned-session extraction
```

**`--touched` must be the log's own Files-list paths**, all of them — they are already enumerated by this point, so pass that list rather than a subset you retype. The verifier can only speak for the paths it was handed: a narrower list still prints `PASS backfill`, and a `REVIEW backfill` naming paths the log lists but the run never saw means the list was short, not that the log is wrong. `--ident` values must be distinctive strings — a bare number under ~4 digits matches digit runs inside phone numbers, order IDs and amounts, and a common word or a doc's name matches every item that mentions or links it, burying real hits in noise. Paths may be absolute, `~`-prefixed, or relative to `{VAULT}`.

Legacy free-form `on <host>` annotations are rewritten to the canonical `(remote)` form; do not silently omit a recorded remote path from `--touched`.

**Files rows the verifier parses.** A path containing ` - ` goes in backticks — `` - `03 Projects/Plan - draft.md` - what changed `` — because an unquoted one is settled by the longest left side that exists on disk, which fails once the file is gone; the backfill script backticks such paths itself, rows written by hand must too. Annotate a path not on this host's disk after the path: `(deleted)` only for a path that is gone (bulk deletion inside a surviving directory is a Files Updated row on that directory), `(remote)` for a path on another host or network share that must not be read; these print `INFO backfill: ... not compared` instead of `REVIEW backfill`/`FAIL touched`. Because nothing compares a `(remote)` row, retain its literal mutation command, absolute working directory and observed exit status under **Evidence** and embed them beside that row in the reviewer brief; a missing record is a brief-assembly failure to fix before despatch. A touched path on a network/FUSE mount, over 2 MiB or binary is checked for existence only and announced as `PASS touched: existence-only (<reason>): <path>`; `PARK_VERIFY_REMOTE_PREFIXES` (colon-separated) names mounts the filesystem probe cannot classify; a prefix covering the vault root itself does not exempt vault files from content checks, only a subtree prefix does. `PARK_VERIFY_MAX_CONTENT_BYTES` overrides the size threshold.

It checks the deterministic layer: session numbering, required sections, Project line (compare its printed line against the caller’s metadata — fix the log if they differ), stranded locked-edit separator lines, list-join/blank-line lint on touched files, unchecked planning-doc items matching each ident, that each touched path exists (`FAIL touched`: mistyped or truncated), and Files-list coverage of touched paths. **A closure `PASS` is not a completion check:** it means no unchecked line matched, which an ident present only in ticked lines also produces. An ident absent from every planning file prints `N/A closure: ident '<ident>' absent from every planning file (<k> checked)` and the `RESULT` line carries the N/A count; N/A is not a pass — usually a misspelt or never-tracked ident — and a run whose every ident is N/A has verified nothing about closures. An ident is the stable identifier the planning line itself carries — the path, booking reference or the item's own wording — never a verb, a paraphrase or a status word such as "done". Two closure classes the verifier cannot see are checked by that same identifier grep, not by the ledger: an item already ticked `[x]` before close-out that this session resolved (`grep -n -i -F -- "<ident>" <file> | grep -F '[x]'`) still gets the `→ [[log]] (Session N)` backlink appended via `locked-edit.sh --replace` when its line lacks one; and a task the user discharged by pasting content into the conversation, which writes no file and leaves no ledger row — enumerate these from the session's Summary and grep each one's identifier. A "line gone" conclusion is the identifier grep on the live file returning empty **after** the same grep matched the session's own pre-state excerpt; an empty grep for a different string or a verb is not that evidence. Judgement stays with you: each closure `REVIEW` hit is an item the caller wrote during routing (expected: ignore the hit, keep the item), an item the session genuinely completed — flip `[ ]`→`[x]` via `locked-edit.sh --replace` with a `→ [[log]] (Session N)` backlink (Tickler flips only after confirming it's the very item resolved — a false flip silently kills deferred work) — or an adjacent still-open item: surface it in Pickup Context, don't action it. Passing edited-file basenames as extra `--ident` args catches adjacent open items mechanically. Once an adjacent-open hit has been recorded in Pickup Context, the final rerun may omit only that discovery-only basename while retaining every core completion/value identifier; record the triage rather than accepting an unexplained `REVIEW` forever.

**One accepted-FAIL class:** inherited lint may be accepted only when current-session locked-edit receipts prove every session delta was a declared exact substitution and record identical pre/post counts for every lint class. Name those receipts in the close-out output. A missing fingerprint, a changed count, another verifier failure, or lint in content the session wrote is not accepted. Do not reformat the user's unrelated notes merely to clear the gate.

Output: the script's `RESULT:` line plus what you fixed.

**Final evidence check:** re-read current edited regions and routed-task destinations, then extract only the assigned Session N with **Assigned-session extraction**. Run §19's behaviour-claim command on that block, trace each past-event/approval/status claim to its evidence, and print a fresh `Value check:` line. Run the count-word scan on the block and every rewritten description; reconcile all sections, including the heading and Key Insights, with surviving open items. Search retired wording separately in this session block (the live-vault sweep excludes the archive). Repeat this executed pass after every fix or later user/world-state change; a prior mental pass or a whole-day file read does not discharge it.

## Independent review

**Review packet currency and reach:** after a fix, rewrite affected Files descriptions with the **whole new section body**, then regenerate scope, attribution (§20), evidence and inspection targets from the current assigned entry. Search the rebuilt brief for retired wording and fragile count/back-reference tokens before sending it; re-read changed source regions and refresh their hashes. A user edit or new status during/after review is another fix round: reconcile the entry, delta propagation, verification and brief before accepting it, or wait for the user's editing to pause.

Embed the parent's literal propagation commands (argv, cwd, exclusions and statuses) beside their results, with digest-bound complete raw receipts and bounded contexts when display is large. Before despatch, re-check each primary receipt's hit lines (`path:line:text`) against the current files: a hit whose text is no longer a line of its file (edited since the search, for example a closure backlink added at verification, or the file is gone) means rerunning that needle and embedding its new receipt; a line that only moved stays valid. Keep separately scoped supplemental excluded-text/non-vault executions and their dispositions tagged beside the primary report; they do not replace the required primary vault-coverage receipt or widen its coverage claim. Include raw hash commands/output and declare whether the seat has shell. A shell-denied seat must search without negated exclusion globs, first detect a known positive control, search hidden directories by explicit path, and triage archived hits by path. Its Grep may honour ignore files and omit non-Markdown text: supply the parent's `--hidden --no-ignore` receipts for that surface; a Grep null cannot supersede them. Vision transcriptions by the same session are `[unverified]` until the decisive detail is rechecked at native resolution. Report a required remote deployment separately as `Needs main session: remote copy`; source repair does not claim the remote copy changed.

**Script probes:** embed this boundary in the reviewer brief: the reviewer may run a command only after reading its argument handling and establishing that the invocation is read-only. Otherwise copy its required inputs into a disposable scratch directory outside the vault and installed config, redirect all output/state there, and probe that fixture. `--help` is not evidence of a read-only command. If isolation cannot be established, inspect the source and report the execution check unverified; never weaken host policy or bypass a missing sandbox.

Use a fresh read-only reviewer through the Agent tool (`subagent_type: "read-only-reviewer"`, `model: opus`). If that agent definition is unavailable, use `general-purpose` with the same explicit read-only contract and disclose that the restriction is instructional. This is the close-out review, not an invocation of `/audit` or its panel. Collect the actual completion report before the caller proceeds to export, provenance or completion. A running seat or observation timeout is not a failed seat. Never infer completion from elapsed time or a scratch file. Write the self-contained brief under `.session-state`, calculate its SHA-256, and pass its absolute path and digest. Include the raw digest output for a shell-denied seat and explicitly distinguish supplied hashes from independently recomputed hashes. After review, the parent checks that the brief and reviewed files still match the reviewed bytes; a changed caller-owned file needs a rebuilt brief and new pass. It must be self-contained, embedding verbatim:

- Resolved vault path; session log path; N; the file list (from the log's Files Created/Updated, post-backfill); the `### Summary` text (Layer 3 needs what the session *did*, not just what park edited). When park runs at the tail of another skill, name that skill and put its outputs in scope alongside park's.
- **Out-of-band evidence:** follow `_shared-rules-reviewer.md` §16's source-union, per-claim coverage and provenance procedure in full; display its evidence count before despatch.
- **§20 attribution** (the file list is the session boundary, not the auto-save commit window) and **pre-state authority**: pre-edit content, and any line the brief flags for scrutiny, is pasted verbatim with its file path from this session's own Reads or edit calls — never recalled, and never reconstructed from auto-save git, whose arbitrary commit boundaries manufacture false "silently dropped" findings.
- **Artefact coverage:** for each bounded semantic hub, provide the full file. For each large semantic or local reference artefact, provide its immutable `park-artifact.py` receipt plus only the exact pages, sections, excerpts or rendered regions used by the session. The parent supplies raw hash output for immutable sources/review copies; a shell-capable reviewer verifies it, while a shell-denied reviewer states its reliance on supplied evidence and reads the declared targets; it must not full-read a textbook/manual merely because the file appears in the Files list. An extraction covering the full source is an index, not a whole-source read attestation.
- **Protocol:** resolve `audit.md` from the directory this `_closeout.md` was loaded from — `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/commands/` or `{VAULT}/.claude/commands/`, whichever holds both files: `for d in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/commands" "{VAULT}/.claude/commands"; do [ -f "$d/_closeout.md" ] && [ -f "$d/audit.md" ] && AUDIT_MD="$d/audit.md" && break; done; ls -l "$AUDIT_MD"`. The `ls` must list the file before the brief is written; `No such file` means the path is wrong, not that the protocol is absent. Read and embed its Phase 2 text for Layers 1–5 — `sed -n '/^#### Layer 1:/,/^### Phase 3:/p' "$AUDIT_MD"`, or at minimum the five heading lines `grep -n '^#### Layer [1-5]:' "$AUDIT_MD"` prints (Layer 0 is deliberately out of scope: this delegated bookkeeping audit's frame is fixed by this brief, and there is no requester to reframe to) — and the Phase 3 deletion-discipline bullet (`grep -n 'Deletion discipline' "$AUDIT_MD"`) for proposed fixes. An empty extraction is a brief-assembly failure to fix before despatch, never a seat result. Embed the text, not an unresolved path such as `{VAULT}/.claude/commands/audit.md`; do not invoke the audit skill. Layer 3 must run the world-state check both ways — work completed but still framed as pending, and work merely scheduled but framed as discharged (check entailed-consequence clauses) — reading bounded semantic hubs in full and using the declared targeted coverage for large/reference artefacts; token lists are illustrative, meaning is the test, and an absent framing is not a finding.
- **Prescribed checks are claims too — Layer 5 must test whether they can fail.** Where the session wrote a verification step for a *later* run (a dated checkpoint, a "confirm X before Y" instruction, an acceptance criterion), name what that step's stated pass condition would show under the negative hypothesis. A pass condition that holds under both hypotheses is a finding, not a pass: it will manufacture confidence on a schedule, at a point where the session that wrote it is long gone and its reasoning unavailable to correct. A prescribed check must state **the command and the observation that separates pass from fail**; stating neither is the same finding arriving by omission, since the future reader then invents the most convenient check. The ordinary layers do not reach this — they test what the session asserted, and a prescribed check asserts nothing yet.
- **Read-only scope:** report findings; never edit vault, session log, skills or installed configuration. Do not invoke `/audit`, a panel or another reviewer. The main session owns all remediation. A shell-denied seat uses the supplied raw command outputs per §23 and explicitly lists checks it could not execute; do not invent command evidence.
- **Report format:** per-layer findings or nil-cases that name what was checked (generic affirmations rejected); proposed fixes (a fix to a path already in the file list stated as `<path>: description extension: <text>`); bytes-read per hub (>5 hubs → split passes, never truncate a read); the §23 evidence attestation (paste §23's table into the brief — the sub-agent can't read this directory); clean pass or "could not clean because X". End with exactly `Terminal state: clean`, `Terminal state: findings` or `Terminal state: incomplete`.

**Same-seat recovery:** elapsed time alone is not a failed audit. If the seat explicitly says its review is complete but repeated no-progress notifications yield no report, send one `SendMessage` requesting its existing report only. If it still cannot return, resume the same seat using the harness's supported continuation mechanism with a no-tools, report-only instruction; do not replace it before attempting that recovery. Reconcile the fresh session ledger and any landed remediation against the attributed Files list before building another brief. A model/context wall or unavailable continuation that prevents a complete report is a concrete blocker: retain the evidence and emit `✗ Audit: not clean — <reason>`. Do not claim clean or complete the caller. If the supported continuation is terminally unavailable, only Park’s Setup incomplete-checkpoint exception permits its expressly allowed bookkeeping; a model/context wall alone does not permit it. Preserve the configured review model; a named-model fallback needs existing user authorisation, never an arbitrary downgrade.

Receive and display the report; enforce §23's attestation. Missing evidence or incomplete coverage requires same-seat follow-up, not a clean label. Sanity-check findings against the live file and the primary session’s pre-state. The main session fixes confirmed attributable findings through the normal locked writers (§5), reports each remediation to a path already in the Files list as `<path>: description extension: <text>` and rewrites its **complete section body**, retaining every other row, with `update-session-section.sh --replace` (§23) while new paths go through backfill, rechecks changed identifiers through the caller’s propagation procedure, and reruns **Backfill and verification**. Rebuild the brief from the new state and resume the same independent reviewer for another full scoped pass. Repeat after every fix round until a completed pass finds no further findings; there is no one-round cap. Inspect any unexpected reviewer write against the read-only contract and reconcile it before accepting the report.

For unavailable evidence, a required user decision or out-of-scope action, retain the concrete blocker and report `✗ Audit: not clean — <reason>`. For a disputed finding, send the reviewer the counter-evidence; unresolved disagreement is a blocker. Never weaken the gate or change the model to claim completion.

Save the accepted report per **Completion evidence** before returning to the caller.

Output: `✓ Audit: clean pass` or `🔧 Audit: N findings fixed and re-audited clean — see [paths]`.

**Late bookkeeping boundary:** the caller's monitor/export/provenance outputs and this protocol's generated receipts/review packets are close-out bookkeeping, not newly authored session work: retain their own receipts without retroactively adding them to the accepted Files list or recursively reviewing copied evidence. A later substantive content or state edit is another review round. Declare this boundary consistently in nightly, catch-up and merged entries.

## Completion evidence

A report and a session entry prove that writing began, not that review completed. Retain the accepted independent report with its exact log path and assigned N so C1 can distinguish completion from interruption. Missing, incomplete or mismatched evidence does not authorise a clean verdict. Do not rewrite the session entry after acceptance just to stamp it complete; keep export/provenance after acceptance.

After the final clean report, §23 acceptance, final backfill/verification and reviewed-byte check, save the reviewer’s report verbatim beside the brief under `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/<actual-session-id>.closeout/`. Use a distinct brief/report pair for each log/N. Prefix the saved report with canonical lines `Session log: <absolute path>`, `Session number: <N>`, `Brief path: <absolute path>` and `Brief SHA-256: <digest>`, and the parent’s acceptance verdict `Close-out accepted: clean`; include the final verifier output. Never write that acceptance verdict for findings or an incomplete report. This is the retained review evidence, not a second task tracker. For C1, search these saved reports for the exact log/N, verify the referenced brief’s digest and subject, and require both the parent acceptance and the reviewer’s clean terminal verdict. Existing historical completion evidence may be used if it establishes the same subject and completed gate; a bare log heading is insufficient.

### Completion lookup

Run this read-only lookup with exact `SESSION_LOG` and assigned `N`. It lists saved reports and receipt/manifest pairs for exact-subject verification; no filename or bare heading certifies completion. A report saved under **Completion evidence** prints as `LEGACY_CANDIDATE` with its `*.closeout/**/*.md` path: that is this harness's current record, not a legacy one, and it establishes completion once its header, brief digest, final verifier, parent acceptance and clean terminal verdict are read. `ACCEPTED` appears only for a receipt from a Codex close-out, so `NO_ACCEPTED_RECEIPT` beside a Claude report is expected. A `LEGACY_CANDIDATE` naming a JSON receipt or manifest is older Codex evidence and needs the same reading.

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

A lookup null (no `ACCEPTED` and no `LEGACY_CANDIDATE` line) is trusted only after the same stores list a known accepted record for its own log/N (a saved report that passes that reading, or an `ACCEPTED` receipt) and list nothing for a wrong N. Read every `LEGACY_CANDIDATE` before calling a close-out incomplete. For pre-retention-rule entries, record `historical completion evidence unavailable` once, preserve any verified historical disposition, and do not manufacture a clean receipt or repeatedly re-audit unchanged old work merely because that evidence was never required.
