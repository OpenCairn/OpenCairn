# Shared Rules — Core and Section Directory

Read this core file when a skill asks for `_shared-rules.md`. The scoped supplements live beside it; **do not load them all at startup**. Before performing an operation below, read the relevant numbered sections from its supplement, once per session:

- **Planning:** project/task linking, Tickler transfers, day-window maintenance or dated routing → [_shared-rules-planning.md](_shared-rules-planning.md).
- **Reviewers:** preparing, dispatching or evaluating a reviewer, or attributing work across sessions → [_shared-rules-reviewer.md](_shared-rules-reviewer.md).
- **Content:** preserving verbatim text, fetching source bodies, or moving/renaming/deleting linked vault files → [_shared-rules-content.md](_shared-rules-content.md).

Skills spanning these operations load the corresponding sections when needed. Read any cross-referenced procedure before using it; a reference in explanatory history alone does not require another file read. A missing required supplement is an incomplete installation: stop the dependent operation and repair the installation, never improvise a substitute. An unrelated operation can continue.

**Section numbers remain global and unchanged.** Use the directory below for bare `§N` / `Section N` references. Forwarding headings retain old `_shared-rules.md` locators; the rule body has one owner. Support paths resolve against the same installation as this file, never the shell working directory. Under Codex, that is the shared skills root, one directory above an individual `SKILL.md`.

## Section directory

| Section | Rule | Owner |
|---|---|---|
| 1 | Vault Path Post-Check | [_shared-rules.md](_shared-rules.md) |
| 2 | Project Linking Rules | [_shared-rules-planning.md](_shared-rules-planning.md) |
| 3 | Item Linking Convention | [_shared-rules-planning.md](_shared-rules-planning.md) |
| 4 | Tickler SSOT Transfer | [_shared-rules-planning.md](_shared-rules-planning.md) |
| 5 | File Locking Mandate | [_shared-rules.md](_shared-rules.md) |
| 6 | (retired 2026-08-05 — WIP demoted) WIP Session Link FIFO Cap | [_shared-rules.md](_shared-rules.md) |
| 7 | Timezone and Date Handling | [_shared-rules.md](_shared-rules.md) |
| 8 | Skill Monitor | [_shared-rules.md](_shared-rules.md) |
| 9 | This Week.md Rolling Window Maintenance | [_shared-rules-planning.md](_shared-rules-planning.md) |
| 10 | Invoking Gemini & Codex (CLI sandbox, vision, panel despatch) | [_shared-rules-reviewer.md](_shared-rules-reviewer.md) |
| 11 | Scratchpad Work-Product Protection | [_shared-rules.md](_shared-rules.md) |
| 12 | Grep-hit triage (reference-graph / Layer-3 propagation) | [_shared-rules.md](_shared-rules.md) |
| 13 | Cite Vault Items by Stable Identifier, Not Line Number | [_shared-rules.md](_shared-rules.md) |
| 14 | Verbatim External Text vs In-Place Formatting Hooks | [_shared-rules-content.md](_shared-rules-content.md) |
| 15 | Published-Transcript Extraction (fetch a verbatim body to a file) | [_shared-rules-content.md](_shared-rules-content.md) |
| 16 | Out-of-Band Evidence in Reviewer Briefs | [_shared-rules-reviewer.md](_shared-rules-reviewer.md) |
| 17 | Push-Side Hub Record (commits are their own identifier class) | [_shared-rules.md](_shared-rules.md) |
| 18 | Deadline Tokens Force a Dated Surface | [_shared-rules-planning.md](_shared-rules-planning.md) |
| 19 | Value Provenance Check (SOURCE) | [_shared-rules.md](_shared-rules.md) |
| 20 | Session-Boundary Attribution (the file list is the boundary, not the commit window) | [_shared-rules-reviewer.md](_shared-rules-reviewer.md) |
| 21 | Concurrent-Safe Git Staging (never stage broadly) | [_shared-rules.md](_shared-rules.md) |
| 22 | Artefact Age Comes From Content, Never From mtime | [_shared-rules.md](_shared-rules.md) |
| 23 | Reviewer Evidence Attestation (a review counts only as far as it shows its work) | [_shared-rules-reviewer.md](_shared-rules-reviewer.md) |
| 24 | Driving the Obsidian CLI (link-healing moves, batches, verification) | [_shared-rules-content.md](_shared-rules-content.md) |
| 25 | Write `rg` in Executable Blocks, Never Bare `grep` | [_shared-rules.md](_shared-rules.md) |
| 26 | Web-Fetch Fallback Ladder (getting a page body) | [_shared-rules-content.md](_shared-rules-content.md) |

---

## 1. Vault Path Post-Check

After running `resolve-vault.sh`, if it errors: **abort — no vault accessible.** Do NOT silently fall back to `~/Files` without an active failover symlink — that copy may be stale.

**Resolver output:** success prints `VAULT_PATH=/resolved/path`. Strip only the `VAULT_PATH=` prefix when extracting the path; do not evaluate the output as shell code.

**Use the resolved path for all file operations.** Code examples in skills use `{VAULT}` as a placeholder — substitute the literal resolved path wherever `{VAULT}` appears before executing. Do NOT rely on a shell variable set in an earlier call persisting — each shell call is a fresh process, so the variable will be empty. `$VAULT_PATH` itself is safe inline: Codex runs commands via `/bin/bash -lc`, which re-reads the profile that exports it.

---

## 2. Project Linking Rules

Moved to [_shared-rules-planning.md §2](_shared-rules-planning.md). Read that section before applying it.

---

## 3. Item Linking Convention

Moved to [_shared-rules-planning.md §3](_shared-rules-planning.md). Read that section before applying it.

---

## 4. Tickler SSOT Transfer

Moved to [_shared-rules-planning.md §4](_shared-rules-planning.md). Read that section before applying it.

---

## 5. File Locking Mandate

**Use `flock` via dedicated scripts, NOT lockless edits.** Codex's patch/editor mechanism and ad-hoc shell writes (`sed -i`, `>` redirection, `tee`) have no file locking — if two agent sessions edit the same file simultaneously, one write silently overwrites the other. This vault runs concurrent sessions, across two harnesses (Claude Code and Codex): the canonical lock is the only thing serialising them.

**Why dedicated scripts instead of inline flock:** the scripts (`write-session.sh`, `add-forward-link.sh`, `write-tickler.sh`, `update-session-section.sh`, `backfill-files-updated.sh`, `locked-edit.sh`) receive content via stdin or arguments, lock the target's canonical lock path, and write atomically. An inline flock reimplementation locks a different path and coordinates with nothing (see Failure mode B below).

### Planning-file writes go through `locked-edit.sh` (NOT apply_patch or raw writes)

**Every mutation of a shared planning file — `01 Now/This Week.md`, `01 Now/Tickler.md`, and project/area hub docs in `03 Projects/` or `04 Areas/` — uses `locked-edit.sh`.** These files are written by $park, $goodnight, $morning, $weekly-hygiene, $weekly-review, $start-project, and $complete-project — from either harness; any two running concurrently (e.g. a scheduled $goodnight while you $park) would silently clobber each other through a lockless edit. `locked-edit.sh` serialises writers through the file's canonical lock and matches literally, so concurrent edits either both land (disjoint) or fail loudly (conflicting) — never silent loss.

**Creation is not mutation — a first write uses a direct write, not the lock.** The rule above governs *editing existing content*: the hazard it prevents is a lost read-modify-write cycle, and a file that does not yet exist has no content to lose. (`locked-edit.sh` *can* create a missing target — that capability is real, it is simply not the reason to reach for it.) The genuine risk when creating is two sessions racing to create the *same* file, and the lock does not address that: it would serialise both writes and report success twice. That is a name-collision check's job, owned by the creating skill's own conflict step, which must test both the file path **and** any index/dashboard heading the new file claims. A skill whose Step-N creates a project or area doc should say so explicitly rather than leaving the mechanism unstated, since an unstated mechanism reads as an oversight against this section.

```bash
# Replace a unique block (old_string must match exactly once):
cat << 'EOF' | "{VAULT}/.claude/scripts/locked-edit.sh" "{VAULT}/03 Projects/Project Name.md" --replace
**Last update:** 2026-06-01 - old state
========OPENCAIRN-LOCKED-EDIT-SEP========
**Last update:** 2026-06-02 - new state
EOF
# Other modes: --replace-all (every occurrence), --append (stdin appended at EOF),
# --replace-whole <expected-sha256|MISSING> (atomic compare-and-swap from stdin).
# --move <destination> <expected-source-sha256> (link-healing compare-and-move;
# both paths must be inside VAULT_PATH and the destination directory must exist).
# Exit codes: 0 ok · 1 usage/lock error · 2 no match/stale snapshot · 3 ambiguous (>1 match under --replace).
# For --replace/--replace-all, treat 2/3 as a real conflict: re-read and recompute, don't loop-retry.
# For --replace-whole, exit 2 means re-read, rebuild and retry with the fresh snapshot hash.
# Exit 1 with a lock message means another writer holds the lock past the timeout — that is
# Failure mode B, not a content conflict: report it and stop rather than bypassing the lock.
```

**⛔ After each `locked-edit.sh` call, grep the target for the full padded input form — `^========OPENCAIRN-LOCKED-EDIT-SEP========$` — and not the bare fragment.** The fragment matches any file that merely *documents* the token (several skills and logs do), so it false-positives on exactly the files this library edits most; anchoring on the padded line is what distinguishes residue from prose. Residual false positive, stated so it isn't mistaken for residue: a file carrying the separator inside a fenced code example still matches — this file does, twice. Judge a hit by whether it sits in the region you just wrote, not by the count. A hit means a malformed heredoc left the separator line in the file — remove it under the same lock before continuing. Exit 0 does not rule this out: the script separates on the first occurrence, so a payload with a stray or mis-indented separator can write cleanly and still land the token in the file. The defect is silent and survives into whatever reads the file next.

**Empty-replacement seam:** deleting a whole line or block by supplying an empty replacement leaves the newline that terminated it. Match the deletion plus its following newline and successor, then re-emit the successor. Re-read the edited seam and confirm no new blank-only line remains; a clean separator check alone cannot detect this residue.

`Tickler.md` has a structured inserter (`write-tickler.sh`) for adding dated items — keep using it; both it and `locked-edit.sh` lock the same canonical path, so they're mutually exclusive. Use `locked-edit.sh` for free-form Tickler edits (editing/removing an existing item). **Session logs are NOT planning files** — they keep their dedicated scripts (`write-session.sh` et al.), which lock the Session Logs directory, not the per-file path.

**Binary and directory ingress:** use `locked-ingress.sh <vault> <source> <destination> [--move]`, never raw `cp`/`mv` into the vault. It locks the new destination, stages in the destination directory, and installs atomically; the parent must already exist and the destination must not. `--move` accepts only a source outside the vault and removes it after the target lands, so a failed cleanup leaves a duplicate rather than data loss.

**Lock files:**

| Lock file | Protects | Used by |
|-----------|----------|---------|
| `06 Archive/OpenCairn/Session Logs/.lock` | Session file reads/writes | write-session.sh, add-forward-link.sh, goodnight session edits |
| `<dir>/.<basename>.lock` (canonical, via `lib-lock.sh`'s `_lock_path_for`) | A file's atomic mutation or participation in a structural move | locked-edit.sh (planning edits, generated whole-file CAS and link-healing moves), write-tickler.sh |
| (retired 2026-06-12) `07 System/.provenance-lock` | — | AI Provenance Log writes now use `locked-edit.sh`'s canonical per-file lock, like every planning file (B9) |

**Lock ordering:** Ordinary edits hold one canonical per-file lock. `locked-edit.sh --move` holds the source and destination locks together in lexical path order, preventing two overlapping moves from deadlocking. Never wrap these operations in another file or session lock.

**System logs are shared files too:** append to correction, wins, strategic-decision and provenance logs through `locked-edit.sh --append`; their folder does not exempt them from locking.

### Failure modes for in-place file edits

Three distinct failure modes can trip up file edits during a skill's execution. Each has a different root cause and a different remediation. **Diagnose before treating.**

> **Portability note:** the diagnostic commands below (`fuser`, `/proc/<PID>/wchan`, `pkill`, GNU `stat -c`) are Linux-specific. On macOS/Windows Git Bash, identify hung script processes with `ps -ef | grep <script-name>` and kill by PID; skip the `/proc` checks.

#### Failure mode A: an editor-tool patch fails because the file changed underneath it

Symptom: a patch/edit against a shared file fails to apply because the file's content no longer matches what was just read.

Likely causes (in decreasing probability):
1. A parallel agent session (either harness) is editing the same file
2. Syncthing bidirectional sync with the NAS mirror rewrote the file
3. An Obsidian background process touched the file

**Diagnostic:** `stat -c '%y' "$file"` immediately before the read and immediately before the edit. If mtime advances between them with no intervening write from this session, an external process is touching the file.

**Remediation:** Don't loop-retry the edit. Use `locked-edit.sh` (see Section 5) — for planning/hub files this is the primary path anyway, not just a fallback:

```bash
cat << 'EOF' | "{VAULT}/.claude/scripts/locked-edit.sh" "/absolute/path/to/file.md" --replace
<old_string>
========OPENCAIRN-LOCKED-EDIT-SEP========
<new_string>
EOF
```

This performs an atomic read-modify-write under the file's canonical lock, immune to the file having moved on since your read — the literal match either finds the region or fails loudly (exit 2/3).

#### Failure mode B: Session-management script times out on its lock

Symptom: `write-session.sh`, `update-session-section.sh`, `backfill-files-updated.sh`, or `add-forward-link.sh` exits with code 1 and "Lock timeout after 10s / Failed to acquire lock."

Likely cause: **a prior invocation of the same script is still running and holds the flock.** Current stdin-consuming session scripts use `lib-lock.sh`'s bounded `_read_stdin_content` helper *before* locking, so a backgrounded heredoc whose writer never closes now exits 2 with `Timed out ... waiting for stdin to close`. A lock timeout can still identify an older deployed script, a legitimate concurrent writer, or another failure after acquisition; diagnose the holder instead of killing by name.

**Diagnostic — find the hung process, don't work around it:**
```bash
# List processes holding the lock
fuser "{VAULT}/06 Archive/OpenCairn/Session Logs/.lock"
# Inspect them
ps -ef | grep -E "write-session|update-session-section|backfill-files|add-forward-link" | grep -v grep
# Confirm they're blocked on stdin pipe (expect anon_pipe_read)
cat /proc/<PID>/wchan
```

**Remediation — kill only the proven hung holder:**
```bash
# Kill specific PIDs reported by fuser
kill <PID1> <PID2> ...
```

After killing, the lock releases and subsequent script invocations work normally.

**Why Python+flock is only a partial fallback here.** The scripts lock a *separate* `.lock` sibling file (e.g. `06 Archive/OpenCairn/Session Logs/.lock`), while Python+flock locks the *target* session log file directly. These are two different inodes, two different locks — they do not coordinate at all. Python "works" not because it's stronger than the shell `flock(1)` command (both use `flock(2)` under the hood), but because it's locking a different file entirely and therefore doesn't contend with the hung script. This means:

- **The dual-lock bypass is unsafe against a genuine concurrent writer.** If another agent session legitimately has the `.lock` held via one of the scripts, a Python fallback that locks the target file won't see the `.lock` and could race.
- **The correct fix is to kill the specific proven hung process, not to route around it.** Routing around it leaves zombies accumulating and disguises the underlying failure mode; pattern-wide `pkill -f` can terminate a legitimate writer from another session.
- **Use Python+flock only after killing the hung scripts**, and only when a dedicated script would be the normal path. This Week/Tickler/project-doc/hub edits are no longer "ad-hoc with no dedicated script" — `locked-edit.sh` is their dedicated path (Section 5); use it rather than inline Python+flock.

#### Failure mode C: command killed by the harness timeout or blocked by the sandbox

Symptom: a script dies abruptly with partial or no output, or fails with a permission error it would not produce in a plain terminal.

Likely causes: the harness kills commands that exceed its execution timeout; under `workspace-write` sandboxing, writes outside the workspace roots (and most network access) are denied. [Exact timeout and denial behaviour unverified — verify against a real long-running script before leaning on this subsection.]

**Diagnostic:** re-run the failing command alone with a generous window; if it is a sandbox denial, the error names the blocked operation.

**Remediation:** for a timeout, re-run and let it complete; for a sandbox denial, confirm the target path sits inside the workspace (launch Codex from `$HOME` — or any directory containing the vault — so the vault is covered) rather than working around the sandbox. A script killed mid-`locked-edit.sh` cannot half-write the target (the write is atomic via `os.replace`). `flock` releases with the dying process; the mkdir fallback deliberately does not auto-reap, so an abandoned directory must be verified against its `owner` metadata and removed by an operator before retrying.

#### Section-targeted append patterns (when scripts are unavailable)

When you need to append to or replace a specific section within a session log (`### Summary`, `### Files Updated`, `### Pickup Context`) and the dedicated script is unavailable, use these safe insertion points:

- **Append to `### Summary`:** insert immediately before the next `### ` heading within the same `## Session N` block (typically `### Key Insights` or `### Next Steps`). This preserves section order.
- **Append to `### Files Updated`:** insert immediately before `### Pickup Context` within the same session block.
- **Replace `### Pickup Context`:** find `### Pickup Context` and the next `## ` or `---` boundary, replace the span between them.

Use markers unique to the session block (the full `## Session N - Topic` header) to scope the find. Python example:

```python
s3_idx = content.find("## Session 3 - Topic")
next_section_idx = content.find("### Key Insights", s3_idx)
before, after = content[:next_section_idx], content[next_section_idx:]
before = before.rstrip("\n") + "\n\n" + addendum + "\n\n"
```

**Reminder:** Prefer killing hung scripts and re-running the dedicated script over writing ad-hoc Python. The dedicated scripts encode conventions (None→list placeholder handling, dedup logic) that inline Python reimplementations will miss.

---

## 6. (retired 2026-08-05 — WIP demoted) WIP Session Link FIFO Cap

Session links now live in project docs' `## Session History`; no dashboard cap applies.

---

## 7. Timezone and Date Handling

- **Always check current date/time** via the `date` command at the start of every command. Never assume, cache, or reuse timestamps from prior tool calls.
- **Use system timezone** (local time wherever the user is). During travel, sessions are dated in local context (Tokyo → JST, Denver → MST). This is intentional — local time is more meaningful than forcing the home timezone.
- **Verify date-to-weekday mappings** with `date -d`. LLMs are unreliable at mapping dates to days of the week. When writing "Mon 15 Feb" or similar, always run `date -d "2026-02-15" +%A` in bash first.
- **Portability — `date -d` is GNU-only.** On macOS/BSD the equivalent is `date -j -f "%Y-%m-%d" "2026-02-15" +%A`, and relative arithmetic is `date -v+6d +"%A %d %b"` rather than `date -d "+6 days" …`. `brew install coreutils` provides `gdate` with GNU semantics, which is the simplest fix for a mac user running this library. This applies to **every** `date -d` across this shared-rule library (§9's rolling-window arithmetic, §18's deadline derivation) and in any skill that loads it — the date rules above are mandatory and frequently executed, so unlike §5's post-failure diagnostics a portability gap here breaks normal operation on the first run.

---

## 8. Skill Monitor

When executing any slash command, also follow the instructions in `_skill-monitor.md` (same directory as this file; if it has not been ported to Codex yet, log observations directly to `07 System/Skill Monitor Log.md` in the vault, matching its existing entry format). Watch for gaps in the command's logic. If you improvise a step that isn't documented, if a mistake could have been caught by a better checklist item, or if a documented step turns out unnecessary — note it and log it per `_skill-monitor.md` at the end. Do not propose edits in-session; the log is processed weekly by `$weekly-hygiene`.

---

## 9. This Week.md Rolling Window Maintenance

Moved to [_shared-rules-planning.md §9](_shared-rules-planning.md). Read that section before applying it.

---

## 10. Invoking Gemini & Codex (CLI sandbox, vision, panel despatch)

Moved to [_shared-rules-reviewer.md §10](_shared-rules-reviewer.md). Read that section before applying it.

---

## 11. Scratchpad Work-Product Protection

Scratchpad files (`Scratchpad.md`) are transient capture surfaces — designed to be cleared regularly, not durable homes. `$reply` drafts persisted there are at-risk work product until the user confirms lifecycle completion.

**Draft identification.** `$reply` draft sections are identified by a heading line starting with `**Reply to ` and ending with `:**`. Example: `**Reply to Sarah (WhatsApp — dinner plans):**`.

**Section boundary.** A draft section starts at the heading line, includes all content through the trailing `> Context:` / `> Note:` blockquote, and ends before the next line matching the same heading pattern, the next `#`-heading, or EOF.

**Cleanup ownership.** `$reply` owns in-session cleanup — it removes its draft section from Scratchpad after lifecycle completion (user says "sent" or pastes final text). `$park` Step 4 and `$weekly-hygiene` Step 5 may remove or route draft sections only after explicit per-draft user confirmation that the draft was sent or is no longer needed.

**Locking.** Scratchpad mutations (section removal, routing) use `locked-edit.sh` (§5 mechanism) for atomicity. Read the current Scratchpad content first, extract the exact section text per the boundary rules above, then pass as `old_string` to `locked-edit.sh --replace` with empty `new_string`.

---

## 12. Grep-hit triage (reference-graph / Layer-3 propagation)

When propagating a changed identifier across the vault — `park` Step 6 (reference graph), `audit` Layer 3, `complete-project`'s moved-anchor sweep — classify each grep hit **by what the value does, not by the file type** before editing:

**First, choose the right grep target — the value sibling docs actually contain.** For a *changed* value, grep the old value. For a **NEW option/alternative added to a pre-existing decision/record**, the new value is *absent* from the very sibling docs that need it (the stale timeline row, the index that lists only the incumbent) — so grep the decision's **anchor** (route/decision/record key), the join key those docs already share, **not** the new option text. Grepping the new value finds nothing and false-passes the propagation.

**When the change *adds a member to a documented set*, the anchor is the container — not the member, and not its topic.** A relocation *into* the set from elsewhere is a member-addition too — the destination set's membership changed even though no item is new. Adding a component to an assembly, a leg to a bundle, an entry to an enumeration: the doc recording that set's *membership* lists the incumbents and names the container, so it contains neither the new member's identifier nor, often, any topic keyword you would think to grep. Both obvious targets return nothing and false-pass; only the **container's name** (the set/list/collection identifier) reaches the membership record. **Checkable:** for every added member, one enumerated anchor's grep must return the membership record — if none does, the anchor is wrong, not the record clean. Note this is *not* satisfied by "also re-grep the docs you edited": the membership record is routinely inside an edited doc yet shares no token with the change, so an identifier-scoped intra-file grep misses it exactly as an inter-file one does. Highest-stakes case is a set that some *other* documented procedure rebuilds or re-derives from — a stale membership list silently reverts the change later, invisibly, under a procedure that looks correct.

**When a section, queue, or SSOT moved *out* of a document (even if the document still exists), grep the moved-from doc's bare inbound anchor (`[[wikilink]]` + path forms) with NO keyword conjunction.** The relocated content's inbound link is itself the identifier; a line pointing at the old home as "the project doc" / "full spec here" / "see [[…]]" is exactly the stale pointer that now misdirects, and it won't match an anchor-AND-topic-keyword grep. Structural queries (below) catch dangling *wikilinks* but never the *plain-text/prose* references to a moved target — only a bare-anchor text grep does. Triage each hit per the categories below (bare-anchor grep returns legitimate navigation links too).

**For link-integrity questions specifically, prefer structural queries over text grep.** A rename/move/delete that needs link-integrity verification is a structural question, not a text search. The system probably has a purpose-built query: an Obsidian vault has `obsidian unresolved` (queries the live link index); a codebase has language-server "find references" or `git grep` with the right filters; a wiki has a broken-link report. Read the project's tool-routing doc (e.g. CLAUDE.md, a contributor guide, or a "how to search" reference) before designing the verification step. The grep-as-default reflex is itself a failure mode — text search is sensitive to file format, encoding, hidden-directory exclusions, and ignore-pattern semantics that the structural query is indifferent to.

**Deduplicating two live records is semantic propagation, not deletion.** Before deleting one copy, compare the records field by field and confirm every claim in the source survives in the retained record at the same scope. Topic overlap is not coverage: a retained claim about one credential, component, or subset does not subsume a source claim about the full set.

- **Stale cross-reference** — a pointer meant to track the current value but now wrong → **update it**. (The most common miss.) **Includes dated rolling current-state fields** an owning rule defines as replace-on-update — notably a project doc's `## Current Objective` / `## Next Actions` state (replace, don't chain) and live planning/hub `Status` / `Current position` lines: the date is a refresh stamp, not a frozen-event timestamp, so update them when the session changed the state they summarise. **A hub's Status / Current-Status section also carries a co-located date-only `**Last update:**` / `**Last updated:**` stamp separate from the content it sits above** — when you edit that section's content, bump the stamp to the current date in the *same* pass; it's part of the edit's footprint, not a frozen timestamp. A content flip that updates the prose but leaves the co-located date stamp stale is a recurring miss (propagation catches the value, not the stamp beside it). **The enclosing artefact governs:** a "current"-phrased line inside a frozen artefact (session log, daily report, weekly-context snapshot, provenance record) stays historical, and a path that relocates with content is a **Live locator** (below), not this — don't infer "rolling" from wording alone.
- **Current-state confirmation** — a relevant live hit already carries the propagated value correctly → **leave it and report `checked — already current`**. This is positive coverage, distinct from historical or unrelated content; omitting it makes the hit-set look untriaged.
- **Enumeration-predicate hit** — a hit where the changed identifier is still a valid list member, but the list's *governing predicate* makes a current-state claim the change falsifies for that member (a status flip to "deferred" where the name sits inside "three items **confirmed** (…, X, …)" or "launching **\<month\> \<year\>** (…, X, …)"; or a count: "3 items (A, B, X)" now 2). **Mechanical trigger:** the identifier and an *old* status/date/count token from the change sit in the *same* line, list-item, table cell/row, parenthetical, or immediately governing heading — that co-location is the reviewer-observable check. → **Update the framing, not the membership:** split the member out and annotate the new state ("X — deferred"), or revise the count. **Do NOT remove X** unless the change is an actual removal/cancellation (a deferral keeps the member). Do NOT classify "different context → leave" merely because the identifier string is still true. The enclosing-artefact rule still governs — a falsified predicate inside a frozen snapshot, or a timeless/current-neutral list with no stale predicate co-located, stays as-is.
- **Live locator** — a path/link/ID a *current workflow resolves to locate or re-read an artefact* (e.g. a hash/provenance log's path column that a verify pass re-hashes; a `**Source:**` path a tool reads). On a **move/rename** of unchanged content → update **only the locator field**, never a content hash/timestamp/proof. On a **delete** → leave it and flag (a MISSING / unresolved result is the correct integrity signal). A locator inside an *otherwise-historical* record is still live — this is the subtlest case and the one propagation passes miss.
- **Historical record** — a frozen record of what was actually said/sent/observed, or where an artefact lived *at event time* → **leave it** (or add a separate relocation note; don't overwrite).
- **Different context** — unrelated content that merely shares the identifier string → **leave it**. A live recommendation of the same provider, candidate, or option is not unrelated merely because it appears in another product or decision context: re-evaluate that recommendation against the new evidence before leaving it.

If you can't tell whether a value is a live locator or a frozen record, **report the ambiguity instead of editing**. Use the file's lock if one exists. Always show the grep output (it proves the grep ran) — and the **full** hit-set, not a sampled subset: the grep's complete hit-list *is* the scope of the triage, so account for every returned hit (tag each `updated` / `left (historical)` / `left (different context)`). A "no remaining stale refs" conclusion is earned only by triaging the whole hit-list, never by checking the files you expected to matter or a hand-picked candidate list.

---

**Verify propagation in both directions:** search the old value for missed references and the new value for intended destinations. Search stable subject/container anchors separately when wording varies. For a changed route, check diagram edges as well as prose; unchanged endpoint names do not prove the route is current.

## 13. Cite Vault Items by Stable Identifier, Not Line Number

When a skill writes a **durable artefact** — a report, review, session log, routed flag, or any note that will be re-read later — that references an item living in a churning planning file (a `This Week.md` task, a project-doc Next Action, a `Tickler.md` line, an open loop), name it by its **title / heading / content**, never by line number (`This Week.md L43`).

Line numbers rot the instant the file is edited — and several skills mutate a planning file *within the same run*, so any `Lnn` written after that point is stale on write. The canonical case: a purge of completed `[x]` lines from `This Week.md` shifts every line below; a report generated later in the same run that cites `This Week.md L43` already points at the wrong line. The durable artefact outlives the line-numbering; the title does not.

Ephemeral, in-conversation references during a single turn (e.g. a grep result you act on immediately) are exempt — this rule governs what gets **persisted**.

### Session-log links are file-level, never heading anchors

The rule above says cite by heading rather than line number. **Session logs are the exception**, because their headings are not stable identifiers: `write-session.sh` appends a `(hh:mmam/pm)` suffix that the linking side does not hold, so a `[[…/YYYY-MM-DD#Session N - Topic]]` anchor silently resolves to nothing. This defect was patched on individual artefacts twice before the convention was changed.

Link the **file** and name the session in plain text after it:

```
[[06 Archive/OpenCairn/Session Logs/YYYY-MM-DD]] (Session N)
```

Applies to every session-log reference a skill writes — continuation links, project-hub Session History rows, completed-item backlinks, Tickler routing links — and to session-log links written into vault docs outside a skill. Consumers key on the `[[06 Archive/OpenCairn/Session Logs/` prefix, and the plain-text session number carries what `$pickup` reads.

Heading anchors remain correct for **stable** docs (project hubs, guides, reference notes) where the heading is hand-written and durable.


---

## 14. Verbatim External Text vs In-Place Formatting Hooks

Moved to [_shared-rules-content.md §14](_shared-rules-content.md). Read that section before applying it.

---

## 15. Published-Transcript Extraction (fetch a verbatim body to a file)

Moved to [_shared-rules-content.md §15](_shared-rules-content.md). Read that section before applying it.

---

## 16. Out-of-Band Evidence in Reviewer Briefs

Moved to [_shared-rules-reviewer.md §16](_shared-rules-reviewer.md). Read that section before applying it.

---

## 17. Push-Side Hub Record (commits are their own identifier class)

Canonical rule for every skill that runs a reference-graph / propagation pass after a session that pushed code — `$park` Step 6, `$goodnight` Step 15(a). Those skills point here and carry no copy to drift.

**The rule.** Every commit hash a session records is its own identifier. For each one, grep the vault for that repository's hub and confirm three things:

1. A `## Session History` row exists for the session that pushed it.
2. The hub's own `**Last update:**` / `Last updated:` stamp is current.
3. The project doc's current-state prose (`## Current Objective` / status line) reflects the push.

**Why the ordinary per-identifier pass misses it.** A pushed commit is a world-state change with no textual footprint in the vault. Nothing in the session's file edits contains the hash, so no content grep reaches the hub — and the hub is frequently a file the session never opened. The propagation pass therefore returns a clean, *fully earned* hit-list while the project's own commit-level record silently misses an entry. This is the inverse of the usual failure: not a stale value left behind, but a **new** record never written, in a document whose stated job is to hold it.

**Scope.** Applies to any repository with a hub in the vault, whether or not the session edited vault files for it. It applies equally when the commit was pushed by a skill's own bookkeeping (a skill-file fix committed during `$park` is still a push, and its hub row is still owed) — the rule is about the push, not about who initiated it.

**Checkable:** for each hash, one grep must return the repo's hub, and that hub must carry a row citing the pushing session. A propagation report that enumerates no commits on a session that pushed one has not run this check.

---

## 18. Deadline Tokens Force a Dated Surface

Moved to [_shared-rules-planning.md §18](_shared-rules-planning.md). Read that section before applying it.

---

## 19. Value Provenance Check (SOURCE)

Canonical rule for every skill with a pre-audit quality gate over files it just wrote — `$park` Step 2(c) (the SOURCE check of its quality gate), `$goodnight` Step 14b. Those skills point here and carry no copy to drift; each supplies its own **scope** (which files it wrote this run) and runs the rule over them.

- Enumerate every specific value written into a file: number, date, quantity, duration, price, rate, capacity, identifier. Also include authorship/approval and past verification claims, causal mechanisms, guarantees and asserted requirements; trace requirements to the authority that imposes them.
- Confirm each traces to one of: (a) something the user stated, (b) a tool result from this session, (c) an explicit uncertainty tag. A value tracing to none of these is fabricated — verify it, cut it, or tag it. "It sounds right" is not a source.
- **Trace is necessary but not sufficient: require semantic entailment.** The source must support the written direction, strength, scope, and qualifiers. For example, "did not increase" does not entail "was unchanged" because it still permits a decrease.
- **Derived values inherit the check.** A total computed from components, or two items presented as equivalent/substitutable, are unsourced unless the inputs *and the equivalence* were themselves checked. Plausible arithmetic over unverified inputs is the same defect as an invented figure.
  - **Unit conversions are derivations.** When a written value is a unit conversion of a tool-result number, recompute the conversion at the gate and match the divisor family to the unit label written — `GB`/`TB` are decimal (10⁹, 10¹²), `GiB`/`TiB` are binary (2³⁰, 2⁴⁰). A GiB value carrying a `GB` label passes the trace check (the byte count is real) while stating a wrong number.
- **Clock values must be read before they are written — two calls, ordered.** A timestamp, date, or "as of" stamp written into a file must come from a `date` result that appears in a **prior** tool result. Issuing `date` in the *same* tool call as the write does not satisfy this: by then the value is already composed, so what ships is an estimate and the `date` output merely documents how far off it was. This is the one value class that escapes the trace check above — the written stamp *does* correspond to a real tool call, so it reads as sourced while still being fabricated. Tell: a write whose stamp was chosen before its `date` output was visible. Applies to file-header stamps, `Last updated:` lines, banner refresh stamps, and provenance rows alike.
- **Asserted preconditions are values too.** A claim that *gates work* — "needs a restart first", "blocked until X is installed", "the key isn't visible yet" — is an unsourced factual claim, not a property of the task, and inherits the same trace requirement. It escapes the enumeration above because it reads as a precondition rather than a value, which is exactly why it survives: **premises are not challenged the way findings are.**
  - **Scope: preconditions naming a local machine or tooling observable** — an environment variable, a running process, a file or binary, a port, a reachable service, a credential. These are testable *by definition*, so testability is not a judgement call the asserting party gets to make.
  - **Out of scope, and not to be enumerated or tagged:** blockers resolved by a person, a third party, or an unmade decision ("waiting on the builder", "blocked on the lease call"). Tagging those is noise, and they are the overwhelming majority of blocker-shaped text in ordinary planning docs.
  - In scope → run the read-only command and cite its output, or tag `[unverified]`. **If the command falsifies the blocker, correct the document** — a cited probe sitting beside an uncorrected precondition is the defect, not the fix.
  - **Tag placement:** in a dated or archival surface (a session log), `[unverified]` is fine. In a living hub or planning doc, cut the claim or rewrite it as an open question — an untagged expiry date is how a tag rots into a permanent shrug.
- **Mechanism-coverage claims inherit the check.** Before writing that mechanism X prevents, detects, or surfaces failure Y, name the comparison or surface X actually inspects and verify that it includes Y's subject. A mechanism that never touches the claimed pair cannot support the causal claim.
- **Aggregate status claims name and verify their set.** State whose items the aggregate covers, then check membership and status against that set's canonical record. A clean subset cannot support an unqualified "all complete/booked/configured" claim.
- **Scope and falsifiers:** the source must support the same subject, population, timeframe and qualifiers. State the searched boundary with a negative claim and retain a positive control from the same instrument/run. A claimed mechanism or successful verification needs an observation that would differ if it failed; a success label alone is insufficient. A durability claim needs the relevant transition tested or conditional wording.
- **Inherited specifics retain their provenance:** user-quoted assistant prose authorises the requested action but does not independently verify its contents. Trace uncertain carried values to the original evidence before strengthening them.
- **Late writes inherit this gate:** apply it to the final session record, routed tasks and other bookkeeping composed after the initial check. Compute counts from the complete relevant result, never truncated output; omit unnecessary counts.
- **Required output:** `Value check: N values traced, M unsourced (fixed); P preconditions asserted, Q verified` — or `Value check: no specific values written this session` (append `; no preconditions asserted` when that half is also nil).

Distinct from §16 (out-of-band evidence in reviewer briefs), which governs *supplying* sources to a reviewer; this one governs whether a value written into a file had a source at all.

---

## 20. Session-Boundary Attribution (the file list is the boundary, not the commit window)

Moved to [_shared-rules-reviewer.md §20](_shared-rules-reviewer.md). Read that section before applying it.

---

## 21. Concurrent-Safe Git Staging (never stage broadly)

Canonical rule for every skill that commits to a git repository, and for ad-hoc commits made during a session. Applies wherever more than one agent session may touch the same working tree.

**The rule.** Stage by explicit path. Never `git add -A`, `git add -u`, or a directory-wide `git add <dir>/`. Commit with `git commit --only -- <paths>`, which commits precisely the named paths regardless of what else sits in the index.

**Why.** Multiple sessions run against the same repo. A blanket stage collects another session's in-flight edits, and the commit then carries their work under a message describing only yours. The damage is not the mixed diff, it is that the change becomes untraceable: nobody looking at that commit message would think to find a deleted script or a foreign refactor inside it. The other session may also `git checkout` a file mid-flight, so what you staged and what gets committed can differ.

**Path-level ownership is not hunk-level ownership.** `--only -- <paths>` bounds which *files* enter the commit; it does nothing about a concurrent session's edits *inside* a file you are also editing. Those ride along in full, under your message — and the rule above does not catch it, because you named the path deliberately. A file being dirty is not evidence the dirt is yours: it can carry your hunks and theirs at once. So before staging any file, `git diff -- <path>` it and confirm every hunk is one you wrote; stage only your own (`git add -p`) or leave the file to its author and say so. **Splitting another session's change is its own damage** — committing a rule while its consumers stay uncommitted publishes an incoherent half, and the author later finds part of their work already pushed under an unrelated message. The tell is a commit whose diffstat is larger than the edits you remember making.

**A clean `git status` is a snapshot, not a guarantee.** HEAD can move between two of your own commands. Re-check state before concluding anything about the repo, and never assert "the tree is clean" from a check made earlier in the task.

**Do not assert a globally clean tree after committing.** Under concurrency, other files being dirty is expected. Assert only that the paths *you* enumerated no longer appear in `git status --short`.

**If a file seems to have vanished from git**, look for a concurrent commit that removed it — `git log --all --diff-filter=D -- <path>`, then recover from the commit before it — rather than assuming data loss.

**Scope: commits the skill itself makes.** A command a skill *prints for the user to run in their own terminal* is not one — repo-initialisation instructions (`git init … && git add -A && git commit -m "Baseline"`) are outside this rule. There, `-A` is correct: the intent is "snapshot everything as it stands", and a repo with no commits has no concurrent in-flight work to collect. Stated because the checkable below otherwise flags those lines, and "fixing" them breaks initialisation.

**Checkable:** every commit a skill executes names its paths explicitly, and no `git add` a skill executes carries `-A`, `-u`, or a bare directory. Instructions handed to the user to run themselves are exempt and need no annotation.

---

## 22. Artefact Age Comes From Content, Never From mtime

Canonical rule for every skill that asks how old an artefact is, or that windows work by recency — staleness checks, "since I last looked" scans, cadence flags, first-flagged markers. Those skills point here and carry no copy to drift.

**The rule.** Derive an artefact's date from its **content** — a header line it carries, its filename when that encodes the date, or a marker the check itself has previously written. Never from `stat` / `find -mtime` / `ls -t`.

**Scope — this governs "how old is this artefact", not "what changed on disk".** mtime is the *correct* source when the question genuinely is filesystem activity: which files a session just touched, which temp files are old enough to delete, which directory is currently active. Those uses are right and this rule does not touch them. The ban applies when mtime is standing in for a date the artefact itself carries — a report's coverage date, a session's date, a review's run date. Test: if the artefact states its own date (in a header, in its filename, in a marker) and you reached for `stat` anyway, that is the failure. If the artefact has no inherent date and you are asking about the file qua file, mtime is the answer.

**Why mtime is not merely imprecise but wrong in the dangerous direction.** Any later touch resets it: an audit remediation, a sync write, a formatting hook, a bulk restore or re-export, an editor opening the file. So an artefact reads as *fresher than it is* — an overdue review looks current, and a scan captioned "the last N days" silently ingests arbitrarily old material. The error is invisible in the output, because the wrongly-included items look exactly like correctly-included ones. It also **self-inflates**: the larger the maintenance operation, the more history it drags into range.

**A marker the check writes into the file is a special case of the same trap.** Once a check stamps a file, that file's mtime measures *the check's own last write*, not the user's — so an mtime-derived age resets to ~0 every run and shrinks as the artefact gets staler, inverting the metric. Carry a monotonic value in the marker instead (a first-seen date or week), and preserve it verbatim on refresh; never recompute it.

**Windows: prefer "since the last run" over a fixed span.** Where a check exists to surface what is new since it last looked, derive the boundary from the previous run's own artefact (its header date), falling back to a fixed span only when no prior artefact exists. A hardcoded span is wrong in both directions — it re-covers ground when runs are close together (re-surfacing items already triaged, which reads as a fresh recurrence) and drops material when they are far apart. A derived boundary widens automatically after a long gap, which is the correct behaviour. Note the ordering dependency: read the previous artefact *before* this run writes its own, or the window collapses to nothing.

**Required output — emit the derived value.** State the date and the elapsed days, or the resolved window and where it came from, before drawing any conclusion from it. `last run <date>, N days ago` and `window: <date>..today | source: <file>` are checkable; a bare "current" / "overdue" verdict, or a candidate list with no stated window, means the check was done from impression. Make the fallback branch visible rather than silent.

**Checkable:** no skill computes an age or a window from `stat`, `-mtime`, or `ls -t`, and every such check prints the value it derived.

---

## 23. Reviewer Evidence Attestation (a review counts only as far as it shows its work)

Moved to [_shared-rules-reviewer.md §23](_shared-rules-reviewer.md). Read that section before applying it.

---

## 24. Driving the Obsidian CLI (link-healing moves, batches, verification)

Moved to [_shared-rules-content.md §24](_shared-rules-content.md). Read that section before applying it.

---

## 25. Write `rg` in Executable Blocks, Never Bare `grep`

Canonical rule for every skill that puts a search command inside a runnable block.

**The agent's shell is not the author's shell.** `grep`, `find` and their neighbours can be shadowed by shell functions or re-execed against a harness-vendored binary, so a block written with `grep` is not necessarily running the `grep` it was tested against — and the substitution is invisible in the block itself. Write `rg`, which is invoked under its own name. Where real GNU `grep` semantics are genuinely required, `command grep` bypasses a *function* shadow, though not a PATH-level substitution. Whether that is sufficient in your environment is a measurement, not an assumption — this rule prefers `rg` because it cannot be shadowed by name at all, not because `command grep` has been shown to fail.

**`rg` is not a drop-in, and all three differences fail quietly.**

- **Flags.** `-E` is `--encoding`, not extended-regex — extended syntax is `rg`'s default, so the correct translation *drops* the flag. `rg -nE '<pattern>'` fails with `unknown encoding: <your pattern>`, which reads as a regex error and is not one. `-L` → `--files-without-match`, `-Z` → `--null`, and `-r` is unnecessary since `rg` recurses by default.
- **Defaults skip files `grep -r` searches, and the skip is not predictable by inspection.** `rg` omits dot-prefixed entries *and* honours `.gitignore`/`.ignore`, and the two interact: a negation (`!*.md`, `!*/`) re-admits hidden paths `rg` would otherwise skip, while an ignore rule excludes plainly visible ones. A third mechanism compounds it: a nested repository or nested ignore file **restarts** the rule set, so the enclosing tree's rules stop applying below that point. Reach is hidden-skip **and** ignore rules **and** where those rules stop, so reading any one of them mispredicts it in **both** directions — the same command can reach one dot-directory and silently miss its sibling. The failure is always the same shape: an unsearched tree reporting as a clean negative.

  **Prove reach by enumeration, and distrust the obvious controls.** Planting a match proves reach to *that path only*, and choosing which path to plant is itself the prediction this rule forbids. A `grep -r` cross-check can be worse than nothing: where the harness shadows `grep` with an *ignore-aware* engine — a sharper case than the opening paragraph's substitution, since the replacement honours the same ignore rules as `rg`, the control inherits the same blind spot and agrees with the thing under test whether or not reach is complete. Enumerate against the real binaries instead, scoped to the type you are sweeping:

  **Diff the hit sets, not the file lists.** A file-listing comparison is itself confirmatory-only, for two reasons that both under-report: an explicit `-g` glob **outranks** an ignore rule, so a file-level-ignored path is *listed* by `rg --files` and still never opened by `rg -l` (only directory-level ignores survive, because a pruned directory is never walked); and a file containing a NUL byte is listed but then skipped as binary, silently, with nothing on stderr. Run the search itself both ways:

  ```bash
  diff <(rg -l '<pattern>' | sort) \
       <(grep -rl '<pattern>' --include='<glob>' . | sed 's|^\./||' | sort)
  ```

  Every `>` line is a file the real binary matched and `rg` did not, so an **empty `>` set is the pass observation**. Use a genuinely present pattern, and invoke the control by an absolute path (`/usr/bin/grep`, or the BSD equivalent on macOS) if the shell may shadow it — a control sharing the blind spot agrees either way. `--hidden --no-ignore` forces full reach. Until that has been run, an `rg` null over such a tree is a statement about your flags, not about the tree.
- **Ordering.** `rg` walks in parallel, so output order is not stable across runs. Pipe through `sort` before diffing two runs or feeding a comparison.

**Verify a swap; never assume it.** Byte-compare against the real binary on input exercising the pattern's edge cases: `diff <(/usr/bin/grep -nE '<p>' f) <(rg -n '<p>' f)` — substitute the BSD path on macOS, where the system binary is not GNU and the comparison is a different one. Two traps when building that control, both of which make a *correct* candidate look broken: `command` is a shell builtin, so `xargs … command grep` cannot exec it; and a single-file test cannot detect a lost `--null`, so include a filename containing a space.

**Checkable:** no runnable block in a skill contains a bare `grep`, and every `rg` whose target tree includes dot-directories or ignored paths either carries `--hidden`/`--no-ignore` or says why it does not.

---

## 26. Web-Fetch Fallback Ladder (getting a page body)

Moved to [_shared-rules-content.md §26](_shared-rules-content.md). Read that section before applying it.

---
