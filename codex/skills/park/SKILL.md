---
name: park
description: Capture session with bookkeeping — quality gate, session log, project-doc update, open-loop routing, and a bounded close-out review.
allow_implicit_invocation: false
---

# Park - Session Capture

Capture a work session: quality gate, session log, project-doc update, reference-graph propagation, open-loop routing, and a bounded close-out review. Every session gets the full bookkeeping pass and one fresh close-out review.

**The propagation agent is despatched at Step 4b and collected at Step 8** — it runs in the background across Steps 4, 5 and 7. Park's cost is dominated by model turns, not by its scripts, so a blocking sub-agent is dead wall clock. **The overlap is not conflict-free:** the agent writes planning and hub files that Steps 5 and 7 also write. `locked-edit.sh` prevents lost updates, not stale-preimage conflicts — an exit 2/3 on either side means re-read and recompute (§5), and that is the expected cost of the overlap, not a malfunction. The saving is bounded by however long Steps 4, 5 and 7 actually take; it does not remove the agent's runtime, it hides as much of it as those steps cover.

**Concurrent parks are safe.** All shared-file writes go through the locking scripts (`write-session.sh`, `update-session-section.sh`, `backfill-files-updated.sh`, `locked-edit.sh`, `write-tickler.sh` — `_shared-rules.md` §5; exit 2/3 = a parallel writer changed the region: re-read and recompute, don't loop-retry; lock timeouts are §5 Failure mode B — kill the hung script, never fall back to a raw write). After each `locked-edit.sh` call, grep the target for the full padded separator line `========OPENCAIRN-LOCKED-EDIT-SEP========`, not the bare fragment, which also matches any doc discussing the token (§5). `$goodnight` uses the same machinery; parking before goodnight keeps its daily report coherent.

## Steps

### 0. Setup

Run `"$VAULT_PATH/.claude/scripts/resolve-vault.sh"`; abort on error (usual cause: `VAULT_PATH` unset — `$setup` covers it). Read `~/.codex/skills/_shared-rules.md` and apply it throughout. `{VAULT}` below = the resolved vault path.

Get date and time from bash — `date +"%Y-%m-%d"` and `LC_TIME=C date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'` (`LC_TIME=C` guards `%p`, which expands empty under many locales).

Derive and display today's session-log path mechanically:

```bash
TODAY="$(date +%F)"
SESSION_DIR="{VAULT}/06 Archive/Claude/Session Logs"
SESSION_LOG="$SESSION_DIR/$TODAY.md"
[ "$(dirname "$SESSION_LOG")" = "$SESSION_DIR" ] || { echo "ERROR: session log escaped current-log directory: $SESSION_LOG" >&2; exit 1; }
printf 'Session log path: %s\n' "$SESSION_LOG"
```

**Path invariant:** a new entry for today goes directly in `Session Logs/YYYY-MM-DD.md`, never `Session Logs/YYYY/YYYY-MM-DD.md`. Year subfolders contain archived logs; an archived path loaded by `$pickup` must not be carried into this park. Shell variables do not persist between tool calls, so re-derive and assert `SESSION_LOG` inside every later call that writes or edits today's log, or use the exact path printed above. Step 1 may still update an existing archived session at its existing path when genuinely merging into that old session.

**Parboil draft.** A mid-session snapshot may already hold this park's expensive half — session narrative, identifier enumeration, open-loop list — derived while the context was still cheap:

```bash
SID="$(. "{VAULT}/.claude/scripts/lib-session.sh"; _session_id)"
S="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state/${SID:-none}"
[ -f "$S.parboil.md" ] && { echo "LEDGER NOW: $(wc -l < "$S.tsv" 2>/dev/null || echo 0)"; cat "$S.parboil.md"; } || echo "no parboil draft"
```

Compare the draft's `SNAPSHOT-LEDGER-LINES: K` against `LEDGER NOW`. **An equal count does not mean nothing changed** — the ledger records file writes only, so decisions taken, messages sent, bookings made and shell-mediated work all move the session on without moving the number. Equal count licenses adopting the *Files* sections, not the narrative: re-check Summary, Key Insights, Next Steps and the enumeration against what happened after the snapshot regardless. Higher → adopt as the base, and **read the delta paths** before extending the enumeration; a draft enumeration carried forward unread becomes the Step 6 agent's grep list, so an error there is a silent reference-graph miss, not a cosmetic one.

Either way the draft is a cheap artefact, not authority: anything in it that a file you read this session contradicts loses, and Steps 2, 4–5 and 8–11 run in full regardless — they verify current state, which no snapshot can stand in for.

### 1. Merge-continuation check

If this session directly continues a just-parked session (a `$pickup` loaded it and the work finishes its loose end), don't create a new entry — update the existing one via `update-session-section.sh <log> N <section> [--replace]` (append to Summary / Files sections; `--replace` for Next Steps and Pickup Context), then run Steps 2 and 4–11 against the merged session's N. **Escape hatch:** if the addendum would exceed ~2× the target's current summary or touch >3 files unrelated to its topic, start a new session instead — a session titled X that hides hours of Y is invisible to topic search. Completion: `✓ Merged into Session N — [what was added]`. Otherwise proceed normally.

### 2. Quality gate

(a) **Enumerate every file the session created or edited** — vault and non-vault. Recall reliably under-reports the non-vault half (early config edits, tooling side-effects, hook-written files), so derive it mechanically:

```bash
"{VAULT}/.claude/scripts/session-ledger.sh" --read
"{VAULT}/.claude/scripts/park-files.sh" "{VAULT}" [-m MINUTES] [repo ...]
```

The ledger is exact where it reaches — it records the session id at write time, so §20 attribution comes free rather than being inferred — but under this harness no write-hook exists: `locked-edit.sh`'s self-ledger is the only recorder, so only edits made through it have rows. The mtime sweep stays as the backstop for everything else: raw writes, shell redirection, scripts. Two distinct failure observables, both meaning "fall back to park-files.sh alone and say so": `NOTE: no ledger` (no locked-edit write has landed yet), and `ERROR: no session id` (no harness session id resolvable — see lib-session.sh) with **exit 1** — that exit 1 is expected here and is not the invocation error Step 3 warns about. A sub-agent's writes ledger under **this** session's id only when its brief carries the `env OPENCAIRN_SESSION_ID=<this session's id>` prefix on every `locked-edit.sh` call (mandatory in every despatch block below — a sub-agent otherwise gets its own thread id and its edits land in a separate ledger). With the prefix, the Step 4b propagation agent's edits appear inline in your own list. `# CONCURRENT-SESSION` lines are other sessions — or a sub-agent despatched without the prefix; account for your own sub-agents before excluding per §20. The `# ledger begins` line is the coverage window — earlier writes are not in it, which is one more reason park-files.sh stays.

Reconcile park-files.sh's candidate lines (sync-receipt, config-tree mtimes, repo status, transient surfaces) against the ledger and your own list; anything either returns that you were about to omit gets added. Files another session wrote are not yours — the file list is the attribution boundary (§20); exclude and say so. Display the list.

(b) **Read each edited file IN FULL** (mid-session direction changes leave stale residue in *unedited* regions) and fix: broken syntax/links/paths, stale interim state, redundancy, typos and spelling per the user's locale, filename still carrying a draft-era prefix after a terminal status change (rename via link-healing move, not raw `mv`), and hook collateral on verbatim external text (§14 — repair via shell, never Edit/Write). A durable doc created this session must be linked from a durable parent (hub/`_index`), not only from rolling-window files. Don't auto-revert changes you didn't make — surface them.

(c) **SOURCE check:** run `_shared-rules.md` §19 over the enumerated files; its required output line is part of this gate.

(d) **Hot-capture nudge:** if substantive insights surfaced but weren't routed in the moment, name the habit gap in one line — don't cold-read the transcript to enumerate them. Omit if none.

Output: `✓ Quality check: N files checked, no issues` or `🔧 Quality check: fixed M issues — [file: fix]`.

### 3. Write the session log

**Metadata:** topic (descriptive weeks later — "Wezterm config fix", not "Terminal stuff"); project link per §2 (shipped one-shot work → area hub) and §3. Display: `Session: [Topic] | Project: [[03 Projects/Name]] (or "None")`.

**Body format is a parse contract** — `$pickup`, `pickup-scan.sh`, and `$weekly-review` key on these exact headings:

```markdown
### Summary
[2-4 sentence narrative — outcomes and decisions]

### Key Insights / Decisions
- ...

### Next Steps / Open Loops
- [specific enough to resume without re-reading the conversation; plain bullets, never checkboxes — session logs are records, not task trackers]

### Files Created
- path - purpose        [bare `None` if empty; same for Updated]

### Files Updated
- path - what changed and why   [not vault-scoped — include load-bearing external paths]

### Files Deleted
- path - why removed    [omit the section entirely if none]

### Pickup Context
**For next session:** [one immediately-actionable sentence]
**Continues:** [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session X - Topic)   [only if continuing]
**Project:** [exact link from the metadata line]
```

**Write it:**

```bash
TODAY="$(date +%F)"
SESSION_DIR="{VAULT}/06 Archive/Claude/Session Logs"
SESSION_LOG="$SESSION_DIR/$TODAY.md"
[ "$(dirname "$SESSION_LOG")" = "$SESSION_DIR" ] || { echo "ERROR: session log escaped current-log directory: $SESSION_LOG" >&2; exit 1; }
cat << 'EOF' | "{VAULT}/.claude/scripts/write-session.sh" "$SESSION_LOG" --auto-number "TOPIC" "HH:MMam/pm"
[body — NO `## Session N` heading; the script assigns N inside the file lock and rejects a supplied heading]
EOF
```

The script handles locking, file/header creation, and atomic numbering — parallel parks can't collide, which is why N is never pre-computed. Its stdout ends `Session number assigned: N`: **that N is canonical for every later step** — display it. On a `Lock timeout` stderr message retry once; any other exit-1 means the invocation is wrong — fix it, don't retry.

**Continuation link** (only if continuing previous work): add the back-link to the original session via `"{VAULT}/.claude/scripts/add-forward-link.sh" --continued-in <session-file> <orig-N> <new-N> "<topic>" [<target-date>.md]`. Continuation links are the only session-to-session links (chronology is already file order), and they are file-level — never `#Session N` heading anchors (§13). Script failure logs a warning, doesn't fail the park.

### 4. At-risk work product

Three checks:
- **Conversation-only drafts** Claude composed (emails, messages, analysis, plans) exist only as text output — write each to its semantic vault home. Drafts the user authored/pasted themselves are not at-risk.
- **Transient surfaces** (Scratchpad, Inbox captures, daily notes) are cleared on a cadence — `park-files.sh`'s `[transient]` lines list this-session candidates mechanically (memory-gating is the failure this check exists to prevent). Read each hit; move durable this-session work product to its semantic home and update every reference to the old location. **Exception:** `$reply` draft sections (headings starting `**Reply to `) need explicit per-draft user confirmation before removal (§11). Pre-existing cross-session content is the user's working buffer — leave it (`$weekly-hygiene`'s job).
- **Claude-internal files** live outside the vault, so `park-files.sh`'s vault-only transient scan cannot see them: run `find ~/.claude/plans -type f -mmin -<session minutes>` and Read every hit individually. A sub-agent's output (`*-agent-*.md`) shares its parent plan's name prefix but is a separate document with its own migration status — "the plan was migrated" is not a verdict on it. Migrate standalone reference material to its semantic vault home; leave spent execution plans (`$weekly-hygiene` owns their cleanup).

Output: `✓ No at-risk work product to persist` or `🔧 Persisted N item(s): [paths]`.

### 4b. Despatch the propagation agent (background)

**Do this here — after Step 4, before Step 5 — not at Step 6.** Build the identifier enumeration per Step 6 and despatch that agent now via `collaboration.spawn_agent` (background). Step 6 below defines what it does and what its prompt contains; this step fixes *when*.

Not earlier: Step 4 **moves files**, and moves are one of Step 6's identifier classes (full old-path forms). Despatching before Step 4 would put every park-time relocation outside the vault-wide sweep, leaving Step 4's own hand-picked reference update as the only net — which is exactly the candidate-list approach §12 forbids. Not later: walking the headings to Step 6 costs the Step 5 and 7 overlap, which is the saving.

If you reach Step 5 without having despatched it, despatch it before continuing.

### 5. Project doc update

If the session materially changed a project's state, update that project's doc in `03 Projects/` — rewrite its `## Current Objective` / `## Next Actions` to match reality, via `locked-edit.sh` (§5). No material change, no edit. If the doc has a `## Session History` section, append `- [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session N) — one-line gloss` via `locked-edit.sh --replace` on the section's tail (not `--append` — the section may not be last; skip if this N is already there from a merge). No such section → don't create one.

### 6. Reference-graph propagation

**Enumerate (main session):** list every identifier value the session changed as `old → new` pairs — status flips, factual corrections, renames/moves (include full old-path forms, not just filenames), numeric changes (carry the constrained subject phrase too), new options on pre-existing decisions (carry the decision's anchor), and **world-state changes from what the session did**: a sent message or made booking changes the acted-on entity's state even where no file token changed. Commits pushed this session are their own identifier class — hub record per §17. Display the enumeration. Nil is a positive claim, not a default — display `✓ Reference graph: No identifier values changed` only after actually checking these categories.

**Propagate (sub-agent — standing authorisation; running it inline instead is the failure):** despatch a background sub-agent via `collaboration.spawn_agent`, on the session's own model — do not downgrade this seat. §12 triage decides whether each hit is a stale cross-reference, a live locator, a historical record, or unrelated; getting that wrong silently corrupts the reference graph, and the failure is invisible until something breaks much later. Despatch at Step 4b, then run Steps 5 and 7 while it works; collect its report at Step 8 before the backfill (`collaboration.wait_agent` at Step 8 is the collection mechanism — do not poll by proxy; `collaboration.send_message` if you need to reach it mid-run. Backfill and park-verify both depend on its file list). Its prompt is self-contained, embedding verbatim: the enumeration (copied, not retyped — count must match), the resolved vault path, and instructions to `rg --type md -i` each identifier over the whole live vault (exclude `06 Archive/`; separate call per identifier; the vault-wide hit-set IS the scope — no hand-picked candidate lists, and "already updated" docs get re-grepped for other instances), triage every hit per §12 (read §12 itself, don't recall it), run the structural link-integrity query after any file moves, bump co-located `Last updated:` stamps on docs it edits, and report the full per-identifier hit-list with each hit tagged updated / left-and-why. Planning/hub writes via `locked-edit.sh`, every call prefixed `env OPENCAIRN_SESSION_ID=<id>` with this session's id (resolve it first: `echo $CODEX_THREAD_ID`; embed the value in the brief) so the sub-agent's edits ledger under this session.

**Out-of-vault facts** (skill/command files asserting things about each other) stay in the main session — the sub-agent has no skill-edit authority: grep `~/.codex/skills`, `~/.claude/commands` and repo command dirs yourself, propagate mechanical fixes, and log non-mechanical skill changes at Step 10.

Output: `✓ Reference graph: N files updated for [identifier]` (+ file list) or the nil line.

### 7. Route open loops

Route every open loop to exactly one canonical target — no per-item prompting:

1. **Explicit future date** → Tickler: `"{VAULT}/.claude/scripts/write-tickler.sh" "{VAULT}/01 Now/Tickler.md" "YYYY-MM-DD" "- [ ] text → [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session N - Topic)"`
2. **No date, actionable this week** → This Week.md day section (tomorrow's; today's if parking before noon) via `locked-edit.sh --replace` on the day section — never `--append`, which lands outside any section. Format: `- [ ] text → [[project/area doc]]`. Trigger-contingent loops ("next time X runs, check Y") are not day-bound — use rule 3, or the Tickler at +10 days if no project doc exists.
3. **No date, has a project** → that project doc's `## Next Actions` (prefer existing `## Next Actions`, then `## Open Loops`; if neither, create `## Next Actions` above `## Session History` or at EOF — no improvised section names).
4. **Undated, low-priority, no project home** → Whimsy: append a plain line (no checkbox) to `{VAULT}/04 Areas/Whimsy/_notes.md`. There is no undated catch-all task list.

**§18 applies:** an item carrying a deadline/expiry/window token MUST land on a dated surface — for this skill the disallowed sinks are the project doc and Whimsy. Derive the date (`date -d`) if it isn't written as one.

**Dedup before writing:** grep a distinctive substring across This Week.md, Tickler.md, and the candidate project doc; on a hit display `✓ Skipped (already present in <file>)`.

Output: `✓ Routed: [item] → [target]` per item. A zero-routing claim cites an observable (the dedup grep hit, or the session log's "None — work completed").

### 8. Backfill + mechanical verification

**Collect Step 6 first.** The background propagation agent must have reported before anything here runs — its edits belong in the backfill, and park-verify's `--touched` list is incomplete without them. If its report hasn't arrived, collect it with `collaboration.wait_agent`; do not proceed on the assumption it changed nothing. wait_agent's return is the *only* signal it has finished — never substitute a proxy that cannot tell "running" from "finished" (a transcript's file size, an elapsed-time guess, a scratch file appearing). Improvising one has already reported completion mid-run.

**Backfill:** park-time edits (Steps 5–7: project docs, This Week, Tickler) postdate the Step 3 log write — pipe them as `- path - what changed` lines through `"{VAULT}/.claude/scripts/backfill-files-updated.sh" <log> N`. The script dedups by path but *silently discards* the incoming description on a hit — to extend an already-listed entry's description, rewrite the section via `update-session-section.sh <log> N "Files Updated" --replace`. Also reconcile inline closures: a Next Steps item that park itself closed comes out of `### Next Steps / Open Loops` (`--replace`, preserving the other lines).

**Verify:** run the verifier and resolve every FAIL, re-running until clean:

```bash
"{VAULT}/.claude/scripts/park-verify.sh" "{VAULT}" "<session log>" N \
  --ident "<distinctive substring per item/identifier the session completed>" ... \
  --touched "<each file the session+park created or edited>" ...
```

**`--touched` must be the log's own Files-list paths**, all of them — they are already enumerated by this point, so pass that list rather than a subset you retype. The verifier can only speak for the paths it was handed: a narrower list still prints `PASS backfill`, and a `REVIEW backfill` naming paths the log lists but the run never saw means the list was short, not that the log is wrong. `--ident` values must be distinctive strings — a bare number under ~4 digits matches digit runs inside phone numbers, order IDs and amounts, burying real hits in noise. Paths may be absolute, `~`-prefixed, or relative to `{VAULT}`.

It checks the deterministic layer: session numbering, required sections, Project line (compare its printed line against Step 3's metadata — fix the log if they differ), stranded locked-edit separator lines, list-join/blank-line lint on touched files, unchecked planning-doc items matching each ident, and Files-list coverage of touched paths. Judgement stays with you: each closure `REVIEW` hit is either an item the session genuinely completed — flip `[ ]`→`[x]` via `locked-edit.sh --replace` with a `→ [[log]] (Session N)` backlink (Tickler flips only after confirming it's the very item resolved — a false flip silently kills deferred work) — or an adjacent still-open item: surface it in Pickup Context, don't action it. Passing edited-file basenames as extra `--ident` args catches adjacent open items mechanically.

**One accepted-FAIL class:** a lint hit in a file the session only *moved* or appended to, inside content it never wrote. A relocation inherits every blank-line run in the file it carried, and "fixing" those means reformatting the user's own notes — which a standing instruction forbids. Say so and move on; do not edit the file to clear the gate. Anything the session actually wrote is not in this class.

Output: the script's `RESULT:` line plus what you fixed.

### 9. Bounded audit (fresh read-only sub-agent — standing authorisation)

This is a **close-out review, not a nested `$audit` run**. Steps 2, 6 and 8 already perform full-file hygiene, vault-wide propagation and deterministic verification. Keep the independent fresh-context check, but do not repeat those passes or import `$audit`'s panel, remediation or "iterate until clean" workflow. A deliberate full six-layer review remains available by invoking `$audit` separately.

Despatch exactly one reviewer with this shape (replace `yyyymmdd` and `n` with the current date and assigned session number; both substitutions use digits only):

```text
collaboration.spawn_agent({
  task_name: "park_audit_yyyymmdd_n",
  fork_turns: "none",
  message: "<self-contained brief>"
})
```

Omit both `model` and `reasoning_effort`: the reviewer must inherit the active park seat's model and reasoning effort exactly. Do not resolve, copy or hard-code their current names or values; omission keeps the match intact when the user changes either setting. `fork_turns: "none"` keeps the context fresh and does not change that inheritance. The propagation seat's anti-downgrade clause in Step 6 is unaffected.

Before despatch, display the §16 line `Out-of-band evidence: sources N → excerpts embedded N` (or the none-line). The brief embeds verbatim:

- Resolved vault path; session log path and N; the post-backfill Files Created/Updated list; the `### Summary`; relevant pre-state from this session's own Reads; out-of-band evidence excerpts; the Step 6 propagation result; and the Step 8 verifier result. The file list is the §20 attribution boundary; auto-save Git is not pre-state evidence.
- **One-pass checklist:** Layer 1 — does the approach serve the stated outcome? Layer 2 — do operating assumptions agree with the embedded evidence? Layer 3 — do the session summary, pending/completed state and listed files agree in both directions? Layer 4 — is the changed content internally correct? Layer 5 — are claimed results supported and future checks falsifiable? Layer 0 is out of scope because the park frame is fixed.
- **Strict scope:** read only Session N and the attributed local files, reading each local file in full once with the bounded per-file pattern below. Treat non-local paths only through embedded evidence. Use the Step 6 report for reference-graph coverage; do not repeat its vault-wide searches. No web, network, SSH, remote hosts, sub-agents, skill/command maintenance, or adjacent cleanup.
- **Read-only and bounded:** make no edits. Read each attributed file exactly once in its own tool call; a canonical/live pair may share one call when a byte comparison proves them identical, and the session-log call extracts only Session N. If a single file truncates, continue only from its first unread line in a targeted follow-up. Make no exploratory or repeated calls and run one review pass. Return only material findings introduced by this session; omit style nits and speculative improvements.
- **Compact report:** scope and coverage; findings tagged Layer 1–5 with exact file/line evidence and a concrete fix, or one evidence-bearing clean line; files read; commands used; coverage gaps; terminal state `clean`, `findings`, or `incomplete`. State explicitly that no network was used.

Collect with `collaboration.wait_agent` in intervals no longer than 60 seconds until the report arrives. Do not infer completion from elapsed time or another proxy, and do not re-despatch merely because the seat is still running.

For a completed report, sanity-check each finding in the live file. The main seat may remediate confirmed, attributable findings in one fix round using the normal locked write mechanics, backfill any newly touched paths, re-read the changed portions and rerun the relevant deterministic check. Do not send the reviewer back for another pass; route anything needing external verification or a broader design decision as an open loop.

Output: `✓ Audit: bounded clean pass` or `🔧 Audit: N findings fixed — see [paths]`.

### 10. Skill monitor

Per §8: review this park execution including the audit — an audit catch that a documented step should have made is a skill gap, the highest-signal kind. Log observations per `_skill-monitor.md`, else `✓ Skill monitor: No gaps detected`.

### 11. Export transcript (last, so it captures the audit)

```bash
python3 "{VAULT}/.claude/scripts/export-session-transcripts.py" "{VAULT}" --days 7 --all-projects
```

`--all-projects` is cwd-independent and merges multi-project days (a single-project export hashes an incomplete day; do NOT use `--fallback-any-project`). `--days 7` because the cutoff is a rolling window from now — `--days 1` truncates boundary days. Report the count. The exporter covers Claude Code sessions and Codex rollouts alike (Codex sessions appear as `codex-<id>` sections).

### 12. Completion message

```
✓ Quality check: N files, [no issues | M fixed]
✓ Session N saved: 06 Archive/Claude/Session Logs/YYYY-MM-DD.md
✓ At-risk work product: [none | persisted N]
✓ Project doc: [updated [[Name]] | no material change]
✓ Reference graph: [N files updated | No identifier values changed]
✓ Open loops routed: N (This Week: X, Tickler: Y, Project: Z, Whimsy: W)
✓ park-verify: PASS
✓ Audit: [bounded clean pass | N findings fixed]
✓ Skill monitor: [no gaps | N logged]
✓ Transcript exported: N sessions

Parked. Pick up when ready: `claude` then `$pickup`
```
