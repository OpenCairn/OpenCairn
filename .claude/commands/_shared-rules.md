# Shared Rules

Operational rules referenced by multiple commands. Commands load this file in Step 0 after vault path resolution:

> Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill.

This prevents rule divergence across every command that loads it (~20 of the library's commands; standalone tools like `/transcribe` and `/ocr` don't). Change a rule once here — all loading commands follow it.

---

## 1. Vault Path Post-Check

After running `resolve-vault.sh`, if it errors: **abort — no vault accessible.** Do NOT silently fall back to `~/Files` without an active failover symlink — that copy may be stale.

**Use the resolved path for all file operations.** Code examples in commands use `{VAULT}` as a placeholder — substitute the literal resolved path wherever `{VAULT}` appears before executing. Do NOT rely on a `$VAULT` shell variable persisting across Bash calls — shell state does not persist between calls, so the variable will be empty.

---

## 2. Project Linking Rules

When a session or task links to a project context:

- **Finite work (in flight)** → link to `03 Projects/[name].md` (or `03 Projects/Backlog/[name].md`)
- **Ongoing area work** → link to `04 Areas/[path]/[name].md`
- **Shipped one-shot work** (published blog post, completed migration, resolved bug, anything finite that's now done with no ongoing tracking need) → link to an *existing* area hub that naturally groups related work. **Do not create a new project file, and do not create a WIP entry.** The "finite work → project file" rule above is calibrated for in-flight finite work where a project file earns its cost by hosting the task queue; once the work ships, the task queue is empty and creating a project file (or WIP entry) retroactively is noise. Example: a published post on your blog links to `[[04 Areas/Blog/Blog]]`, not a newly-created post-specific project file.
- **Operational/meta work with no natural project or area home** (e.g. /morning, /goodnight, general sysadmin, security hygiene, vault maintenance) → `Project: None (operational <scope>)` — e.g. `None (operational /morning)`, `None (operational tech-infra)`. Don't reach for a loosely-related project to fill the slot; `None` is the correct answer.
- **Never link to:** WIP sections (`01 Now/Works in Progress#...`), Resources, Archive, or 07 System files (these are references and meta, not project/area homes)
- **No canonical home and work is still in flight?** Create a project or area file rather than linking to WIP
- **Working in Resources?** That's a signal it should graduate to an Area
- **Why:** WIP is for status tracking, not session clustering. Consistent project links enable reliable pickup grouping.

---

## 3. Item Linking Convention

Every actionable item in a day section, Tasks.md, or planning document should link to its project/area context where one exists:

- Project doc exists → `→ [[03 Projects/Project Name]]`
- Area doc exists → `→ [[04 Areas/path/doc]]`
- No dedicated doc but tracked in WIP → `→ [[01 Now/Works in Progress#Heading]]`
- Standalone/generic items (no project context) → no link

When moving items that already have project/area links, preserve them. Replace session log links (`→ [[06 Archive/...]]`) with project/area links — session context is low-value once the item is in a planning doc.

---

## 4. Tickler SSOT Transfer

Tickler is a time-deferred queue, not a persistent SSOT. When items are pulled from Tickler into a planning document (This Week.md, a project page, etc.), **the planning document becomes SSOT** for those items. Delete the Tickler copy immediately to prevent duplicate checkboxes across the vault. The Tickler's job is done once the item surfaces and lands in a plan.

When migrating Tickler items:
- Preserve existing project/area links (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`)
- Replace session-log-only links with the relevant project/area link
- Add links to bare items per the Item Linking Convention (Section 3)
- **Deduplicate against Tasks.md:** After migrating each Tickler item, check whether a matching item already exists in Tasks.md (`01 Now/Tasks.md`) (same task, possibly different phrasing). If so, delete the Tasks.md copy — the day section is now SSOT.

---

## 5. File Locking Mandate

**Use `flock` via dedicated scripts, NOT the Edit tool.** The Edit tool has no file locking — if two Claude instances edit the same file simultaneously, one write silently overwrites the other.

**Why dedicated scripts instead of inline flock:** Claude Code's permission system saves the entire bash command as a permission pattern in `settings.local.json`. Multi-kilobyte session summaries inside flock commands bloat the settings file. The scripts (`write-session.sh`, `add-forward-link.sh`, `write-tickler.sh`, `update-session-section.sh`, `backfill-files-updated.sh`, `locked-edit.sh`) receive content via stdin or arguments — the permission system only stores the short script invocation, not the payload.

### Planning-file writes go through `locked-edit.sh` (NOT the Edit tool)

**Every mutation of a shared planning file — `01 Now/Works in Progress.md`, `01 Now/This Week.md`, `01 Now/Tickler.md`, `01 Now/Tasks.md`, and project/area hub docs in `03 Projects/` or `04 Areas/` — uses `locked-edit.sh`, not the Edit tool.** These files are written by `/park`, `/goodnight`, `/morning`, `/weekly-hygiene`, `/weekly-review`, `/start-project`, and `/complete-project`; any two running concurrently (e.g. a scheduled `/goodnight` while you `/park`) would silently clobber each other through the lockless Edit tool. `locked-edit.sh` serialises writers through the file's canonical lock and matches literally, so concurrent edits either both land (disjoint) or fail loudly (conflicting) — never silent loss.

```bash
# Replace a unique block (old_string must match exactly once, like the Edit tool):
cat << 'EOF' | "{VAULT}/.claude/scripts/locked-edit.sh" "{VAULT}/01 Now/Works in Progress.md" --replace
**Last:** 2026-06-01 — old state
========OPENCAIRN-LOCKED-EDIT-SEP========
**Last:** 2026-06-02 — new state
EOF
# Other modes: --replace-all (every occurrence), --append (stdin appended at EOF).
# Exit codes: 0 ok · 2 no match · 3 ambiguous (>1 match under --replace) — treat 2/3 as a
# real conflict (a parallel writer changed the region), re-Read the file and recompute, don't loop-retry.
```

`Tickler.md` has a structured inserter (`write-tickler.sh`) for adding dated items — keep using it; both it and `locked-edit.sh` lock the same canonical path, so they're mutually exclusive. Use `locked-edit.sh` for free-form Tickler edits (editing/removing an existing item). **Session logs are NOT planning files** — they keep their dedicated scripts (`write-session.sh` et al.), which lock the Session Logs directory, not the per-file path.

**Lock files:**

| Lock file | Protects | Used by |
|-----------|----------|---------|
| `06 Archive/Claude/Session Logs/.lock` | Session file reads/writes | write-session.sh, add-forward-link.sh, goodnight session edits |
| `<dir>/.<basename>.lock` (canonical, via `lib-lock.sh`'s `_lock_path_for`) | A single planning/hub file's read-modify-write | locked-edit.sh, write-tickler.sh |
| (retired 2026-06-12) `07 System/.provenance-lock` | — | AI Provenance Log writes now use `locked-edit.sh`'s canonical per-file lock, like every planning file (B9) |

**Lock ordering:** Planning-file locks — including the AI Provenance Log's canonical lock — are held only for the duration of one `locked-edit.sh` write (auto-released on script exit), so they never overlap with the session lock. Never wrap multiple lock acquisitions in one another.

### Failure modes for in-place file edits

Three distinct failure modes can trip up file edits during a skill's execution. Each has a different root cause and a different remediation. **Diagnose before treating.**

> **Portability note:** the diagnostic commands below (`fuser`, `/proc/<PID>/wchan`, `pkill`, GNU `stat -c`) are Linux-specific. On macOS/Windows Git Bash, identify hung script processes with `ps -ef | grep <script-name>` and kill by PID; skip the `/proc` checks.

#### Failure mode A: Edit tool refuses with "modified since read"

Symptom: `Edit` tool returns "File has been modified since read, either by the user or by a linter." even after a fresh `Read`.

Likely causes (in decreasing probability):
1. A PostToolUse hook (e.g. britfix) fired on a prior write and advanced mtime between this Read and Edit
2. A parallel Claude session is editing the same file
3. Syncthing bidirectional sync with the NAS mirror advanced mtime
4. An Obsidian background process touched the file

**Diagnostic:** `stat -c '%y' "$file"` immediately before the Read and immediately before the Edit. If mtime advances between them with no intervening write from this session, an external process is touching the file.

**Remediation:** Don't loop-retry the Edit tool. Use `locked-edit.sh` (see Section 5) — for planning/hub files this is the primary path anyway, not just a fallback:

```bash
cat << 'EOF' | "{VAULT}/.claude/scripts/locked-edit.sh" "/absolute/path/to/file.md" --replace
<old_string>
========OPENCAIRN-LOCKED-EDIT-SEP========
<new_string>
EOF
```

This skips the Edit tool's mtime freshness check entirely and performs an atomic read-modify-write under the file's canonical lock. It supersedes the old inline `fcntl.flock` snippet for this purpose: that snippet (a) is Unix-only — `fcntl` does not exist on Windows Git Bash, which the script suite supports — and (b) locked the target file directly rather than the canonical `.lock` sibling, so it didn't coordinate with the dedicated scripts. `locked-edit.sh` fixes both.

#### Failure mode B: Session-management script times out on its lock

Symptom: `write-session.sh`, `update-session-section.sh`, `backfill-files-updated.sh`, or `add-forward-link.sh` exits with code 1 and "Lock timeout after 10s / Failed to acquire lock."

Likely cause: **a prior invocation of the same script is still running and holds the flock.** This happens when the Bash tool backgrounded an earlier invocation and the script got stuck — most commonly, scripts fed via heredoc (`cat <<EOF | script.sh ... EOF`) can block forever in `read` from their stdin pipe if the Bash tool backgrounded the shell before the pipe writer finished. The script is blocked in `anon_pipe_read` on fd 0, still holding fd 9 on the `.lock` file.

**Diagnostic — find the hung process, don't work around it:**
```bash
# List processes holding the lock
fuser "{VAULT}/06 Archive/Claude/Session Logs/.lock"
# Inspect them
ps -ef | grep -E "write-session|update-session-section|backfill-files|add-forward-link" | grep -v grep
# Confirm they're blocked on stdin pipe (expect anon_pipe_read)
cat /proc/<PID>/wchan
```

**Remediation — kill the hung processes:**
```bash
# Kill specific PIDs reported by fuser
kill <PID1> <PID2> ...
# Or nuclear option
pkill -f backfill-files-updated
pkill -f update-session-section
```

After killing, the lock releases and subsequent script invocations work normally.

**Why Python+flock is only a partial fallback here.** The scripts lock a *separate* `.lock` sibling file (e.g. `06 Archive/Claude/Session Logs/.lock`), while Python+flock locks the *target* session log file directly. These are two different inodes, two different locks — they do not coordinate at all. Python "works" not because it's stronger than the shell `flock(1)` command (both use `flock(2)` under the hood), but because it's locking a different file entirely and therefore doesn't contend with the hung script. This means:

- **The dual-lock bypass is unsafe against a genuine concurrent writer.** If another Claude session legitimately has the `.lock` held via one of the scripts, a Python fallback that locks the target file won't see the `.lock` and could race.
- **The correct fix is to kill the hung process, not to route around it.** Routing around it leaves zombies accumulating and disguises the underlying Bash-tool-heredoc failure mode.
- **Use Python+flock only after killing the hung scripts**, and only when a dedicated script would be the normal path. WIP/This Week/Tickler/hub edits are no longer "ad-hoc with no dedicated script" — `locked-edit.sh` is their dedicated path (Section 5); use it rather than inline Python+flock.

#### Failure mode C: Bash tool backgrounds a command that finishes normally

Symptom: A simple command (`ls`, `stat`, `wc -l`, `mount`, etc.) returns "Command running in background with ID: bXXXX" instead of returning its output inline. The command may have actually completed — check the task output file before assuming it's hung.

Likely cause: The Bash tool's harness has heuristics for backgrounding commands that it considers long-running. These heuristics sometimes fire on commands that complete in milliseconds, especially during sessions with many rapid tool calls.

**Diagnostic:**
```bash
# Retrieve output from the task file (path is in the tool result)
cat /tmp/claude-XXXX/.../tasks/bXXXX.output
# Check if the command's process still exists
ps -p <PID from backgrounding message> 2>&1
```

**Remediation:** If the output file has the expected content, the command finished successfully — just use it. If the process is still alive after many seconds and the output is empty, it may be stuck; inspect and kill per Failure mode B.

**Prevention:** For simple diagnostics, prefer small focused commands and read the output promptly. Avoid chaining many commands with `;` or `&&` in one Bash tool call — each chain element can trigger backgrounding heuristics.

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

## 6. WIP Session Link FIFO Cap

When adding session links (`→ [[06 Archive/Claude/Session Logs/...]]`) to a WIP entry:

1. Add the new link
2. Count standalone session link lines (lines matching `→ [[06 Archive/Claude/Session Logs/`) in this WIP entry
3. If more than 3, remove the oldest by date until exactly 3 remain
4. **Do NOT trim non-session-log reference links** (`→ [[03 Projects/`, `→ [[04 Areas/`, etc.) — these are navigation pointers

Session history lives in the archive and project hub pages; WIP links are convenience pointers, not the record of truth.

**Mechanical verification (required after every WIP edit):**
```bash
# Extract the WIP entry for this project and count session links
# Substitute the heading text (e.g. "Claude Code Learning / OpenCairn")
# Uses awk index() for fixed-string matching (headings often contain / and &)
# Letter-var z=0 binding works around the slash-command loader consuming bare dollar-digit tokens (positional-arg placeholders). See github.com/anthropics/claude-code/issues/52226
awk -v z=0 'f && /^### /{exit} index($z, "### HEADING_TEXT") == 1 {f=1} f' "{VAULT}/01 Now/Works in Progress.md" | grep -c '^→ \[\[06 Archive/Claude/Session Logs/'
```
Display: `FIFO check: N/3 session links`. If more than 3, fix before proceeding.

---

## 7. Timezone and Date Handling

- **Always check current date/time** via the `date` command at the start of every command. Never assume, cache, or reuse timestamps from prior tool calls.
- **Use system timezone** (local time wherever the user is). During travel, sessions are dated in local context (Tokyo → JST, Denver → MST). This is intentional — local time is more meaningful than forcing the home timezone.
- **Verify date-to-weekday mappings** with `date -d`. LLMs are unreliable at mapping dates to days of the week. When writing "Mon 15 Feb" or similar, always run `date -d "2026-02-15" +%A` in bash first.

---

## 8. Skill Monitor

When executing any slash command, also follow the instructions in `_skill-monitor.md` (same commands directory as this file). Watch for gaps in the command's logic. If you improvise a step that isn't documented, if a mistake could have been caught by a better checklist item, or if a documented step turns out unnecessary — note it and propose edits at the end.

---

## 9. This Week.md Rolling Window Maintenance

This procedure keeps the rolling 7-day window current. It runs during `/morning` (step 6) and `/goodnight` (step 11). If This Week.md doesn't exist, skip entirely.

**Write mechanism (F1):** `This Week.md` is a shared planning file — every trim/extend/populate mutation below goes through `locked-edit.sh`, not the Edit tool (see §5). Use `--replace`/`--replace-all` to delete or rewrite day sections. `--append` adds at EOF, so it is valid for new day sections **only when the file has no trailing non-day content**; if a `---` / `## Refs` / other trailing section exists, use `--replace` on the trailing boundary block instead (per the placement rule below).

### Trim old day sections

Delete any day sections whose date is more than 3 calendar days before today. Past days are already archived in Daily Reports — keeping them past 3 days adds clutter without value.

1. Parse each `## ` heading for a date (e.g. `## ☀️ Fri 6 Mar` → 6 Mar, `## Mon 9 Mar` → 9 Mar). Skip headings that aren't day sections (e.g. `## Refs`).
2. For each day section, compute: `today_date - section_date`. If > 3 calendar days, it becomes eligible for deletion — but **sweep before deleting**. Grep the section body for unchecked items first:
   ```bash
   grep -nE '^[[:space:]]*-[[:space:]]*\[ \]' <section body>
   ```
   Route every match forward before removing the section — into today's section (or the relevant future day / Tickler, per the caller's routing rules), preserving existing project/area links. **Only after the sweep**, delete the heading and all content until the next `## ` heading. Normally `/goodnight` has already routed undone items nightly, so eligible sections are clean and the grep returns nothing — but across a multi-day gap where `/goodnight` never ran (travel, offline), a trimmed day can still hold live `- [ ]` tasks, and deleting without the sweep silently drops them. Completed (`[x]`) items need no sweep — they're archived in the Daily Report.
3. Keep the 3 most recent past days for quick reference. Today and future days are never trimmed.

### Extend the window

Ensure day sections exist for today + 6 calendar days ahead (7 total including today). Rolling window: 3 past + today + 6 future = 10 sections max.

1. Run `date -d "+N days" +"%A %d %b"` for each missing day (N = 1 to 6)
2. Add new day sections after the last existing day, before `---` / Refs / other trailing sections
3. Remove day sections beyond the 6-day window (heading + content until next `## ` heading)
4. Format for days with no content: `## [Day] [DD] [Mon]` — just the heading
5. Update the file heading date range — this is a **required, emitted check**, not a silent edit. See **Update the heading** below.

### Populate new days from Tickler

For each newly created day section, convert to YYYY-MM-DD format and check Tickler.md for a matching `## YYYY-MM-DD` date header. Move any unchecked items from that Tickler section into the new day section and delete from Tickler (per Tickler SSOT Transfer rules in Section 4).

### Update the heading

Update `# This Week — [start] – [new end] [YYYY]` so the range equals the earliest and latest day-section dates currently in the file.

**⛔ Required output — emit the check.** Whenever the window changes (a section added or trimmed), confirm the title against the actual first/last day sections and print the result. This is the load-bearing mechanism: the instruction to update the heading has always existed, so what recurs is *skipping it without noticing*, not not knowing to. A title edit with no emitted check is the failure signature. Format:

```
Window check: title "[start] – [end]" = sections [first day] … [last day] ✓
```

If the title and the first/last day sections disagree, the window edit is incomplete — fix the title before finishing the procedure.

---

## 10. Invoking Gemini & Codex (CLI sandbox, vision, panel despatch)

Gotchas that bite any skill calling the `gemini`/`codex` CLIs, plus the canonical read-only despatch block — the **single source of truth** for these commands; `/audit` and `/second-opinion` point here rather than carrying their own copies.

- **Gemini file reads are sandboxed to the workspace = the cwd it was launched from** (plus its project temp dir `~/.gemini/tmp/<hash>`) — NOT the home directory. Verified 2026-06-11 on gemini 0.40.1: launched from `~`, a read of `/tmp/<file>` fails "Path not in workspace"; launched from `/tmp`, a read under `~` fails the same way. Three remedies: launch from the target's root; pass `--include-directories <root>` (verified to extend the workspace); or **pipe text via stdin** — `cat <file> | gemini -p "..."` — so the sandbox never applies to the brief itself. Headless gemini also **hard-refuses to start in an untrusted directory** ("not running in a trusted directory") — when despatching from outside your trusted set, set `GEMINI_CLI_TRUST_WORKSPACE=true` or pass `--skip-trust`.
- **Vision/OCR via the CLI is unreliable** — it may not pass an image as a true vision input and frequently refuses outright ("I cannot perform OCR for handwriting"). For any image task, **bypass the CLI and call the REST API** (`generativelanguage.googleapis.com/.../generateContent`) with inline base64 and `GEMINI_API_KEY` (set in env and `~/.gemini/.env`). Python stdlib `urllib` is enough — no SDK install.
- **Keep Gemini read-only with a `--policy` file, not `--approval-mode plan`** — `plan` blocks `run_shell_command` but still exposes the `replace`/`write_file` edit tools, so a skill that briefs Gemini to propose changes can have them written straight into the target. Verified on gemini 0.40.x: a deny-rule policy strips the named tools from the model entirely (it reports them "not found") while reads stay intact — a hard guarantee. The policy file needs **no `.toml` extension** (verified 0.40.1), so create it with portable `mktemp` — GNU-only `--suffix` breaks BSD/macOS. **Don't** put the file in `~/.gemini/policies/` (auto-loaded for *every* invocation → would make all gemini sessions read-only); use an explicit temp path. After a panel run, check whether the reviewer **attempted** an edit: if it did, it must have reported the tool "not found"/unavailable — an edit that *succeeded* means the policy didn't load; treat the run as contaminated. A clean review with no edit attempt produces no such report (the tools are only reported missing when called) — for that case, and on the no-`--policy` fallback, the `git status`/snapshot backstop is the verification.
- **Canonical read-only panel despatch block.** The Claude seat is the Agent tool with the brief contents verbatim as its prompt; the CLI seats run via Bash with `timeout: 300000` passed as the **Bash-tool argument** on each call (it is not a shell flag — the default 120s kills reviewers mid-review):

  ```bash
  RO_POLICY=$(mktemp -t gemini-ro-policy.XXXXXX)   # portable: no --suffix, no .toml needed
  printf '[[rule]]\ntoolName = ["write_file", "replace", "run_shell_command"]\ndecision = "deny"\npriority = 100\n' > "$RO_POLICY"
  # Each CLI call below: pass timeout 300000 as the Bash TOOL argument (not a shell flag)
  cat <brief> | gemini -p "Follow the instructions in the piped input exactly." --policy "$RO_POLICY" -o text --include-directories <root>
  cat <brief> | codex exec --sandbox read-only --skip-git-repo-check -C <root> -
  ~/.claude/scripts/xai_client.py --panel-review <brief> --source <target> [--source <target> ...]
  ```

  `--include-directories <root>` / `-C <root>` point the seats at the target's root; drop them when the target sits under the despatch cwd. Session-handle capture, auth caveats, and fallback invocations stay in `second-opinion.md` Phase 2A.

- **The Grok seat is an API seat, not a CLI seat — it reads nothing.** `xai_client.py` posts to xAI's Responses API over stdlib `urllib`; it has no filesystem access, so the target must be passed with `--source` and is inlined into the prompt as a delimited appendix. Three consequences that the other two seats don't have:
  - **Manifest in place of a read-list.** The wrapper appends each source as `path | bytes | sha256` and instructs the seat to reproduce that manifest verbatim and quote what it relied on. That manifest is the Grok seat's evidence standard — the read-list rule (`audit.md`, `second-opinion.md`) is satisfied by the manifest, not waived. A Grok review with neither manifest nor quotes is brief-echo and is discarded exactly like a CLI review with no read-list.
  - **Size cap, fail-closed.** `MAX_INLINE_BYTES` (400 KB, ~100k tokens — kept under xAI's >200k-token tier where the per-token rate doubles). Over the cap the wrapper raises and the seat is **dropped with the reduced panel announced**; it never silently truncates, because a truncated appendix produces confident findings about text the seat never saw.
  - **Availability probe is `--probe`, not `--version`.** There is no binary: `xai_client.py --probe` exits 0 when `XAI_API_KEY` is set, 1 otherwise. Probe *before* despatch — an unset key must degrade to a three-seat panel up front, not fail mid-run. Note the key must be in the environment the Bash tool actually runs in; a key exported only in `~/.bashrc` will not reach a non-interactive shell (same trap as `second-opinion.md` Phase 2A step 5).

  The wrapper sets `store: false` (xAI otherwise retains responses server-side for 30 days) and never enables live search on a review call. `store: false` forecloses `previous_response_id` threading, which is why the Grok seat has no true resume — round 2 replays prior context. **xAI does not train on API inputs or outputs by default** — its API security FAQ states it "never trains on your API inputs or outputs without your explicit permission," so training is opt-in, not opt-out. The "improve the model" toggle is the *consumer* Grok control, not a developer-API setting; there is nothing to switch off. What does apply: API requests and responses are retained 30 days, encrypted at rest, for abuse auditing. `store: false` governs stateful threading, not that audit window. Zero Data Retention eliminates it but is team-level and disables the stateful Responses API, Files, Collections, Batch, and per-key logging — don't enable it for this.

---

## 11. Scratchpad Work-Product Protection

Scratchpad files (`Scratchpad.md`) are transient capture surfaces — designed to be cleared regularly, not durable homes. `/reply` drafts persisted there are at-risk work product until the user confirms lifecycle completion.

**Draft identification.** `/reply` draft sections are identified by a heading line starting with `**Reply to ` and ending with `:**`. Example: `**Reply to Sarah (WhatsApp — dinner plans):**`.

**Section boundary.** A draft section starts at the heading line, includes all content through the trailing `> Context:` / `> Note:` blockquote, and ends before the next line matching the same heading pattern, the next `#`-heading, or EOF.

**Cleanup ownership.** `/reply` owns in-session cleanup — it removes its draft section from Scratchpad after lifecycle completion (user says "sent" or pastes final text). `/park` Step 10(b) and `/weekly-hygiene` Step 6 may remove or route draft sections only after explicit per-draft user confirmation that the draft was sent or is no longer needed.

**Locking.** Scratchpad mutations (section removal, routing) use `locked-edit.sh` (§5 mechanism) for atomicity. Read the current Scratchpad content first, extract the exact section text per the boundary rules above, then pass as `old_string` to `locked-edit.sh --replace` with empty `new_string`.

---

## 12. Grep-hit triage (reference-graph / Layer-3 propagation)

When propagating a changed identifier across the vault — `park` Step 12 (reference graph), `audit` Layer 3, `complete-project`'s moved-anchor sweep — classify each grep hit **by what the value does, not by the file type** before editing:

**First, choose the right grep target — the value sibling docs actually contain.** For a *changed* value, grep the old value. For a **NEW option/alternative added to a pre-existing decision/record**, the new value is *absent* from the very sibling docs that need it (the stale timeline row, the index that lists only the incumbent) — so grep the decision's **anchor** (route/decision/record key), the join key those docs already share, **not** the new option text. Grepping the new value finds nothing and false-passes the propagation.

**When the change *adds a member to a documented set*, the anchor is the container — not the member, and not its topic.** A relocation *into* the set from elsewhere is a member-addition too — the destination set's membership changed even though no item is new. Adding a component to an assembly, a leg to a bundle, an entry to an enumeration: the doc recording that set's *membership* lists the incumbents and names the container, so it contains neither the new member's identifier nor, often, any topic keyword you would think to grep. Both obvious targets return nothing and false-pass; only the **container's name** (the set/list/collection identifier) reaches the membership record. **Checkable:** for every added member, one enumerated anchor's grep must return the membership record — if none does, the anchor is wrong, not the record clean. Note this is *not* satisfied by "also re-grep the docs you edited": the membership record is routinely inside an edited doc yet shares no token with the change, so an identifier-scoped intra-file grep misses it exactly as an inter-file one does. Highest-stakes case is a set that some *other* documented procedure rebuilds or re-derives from — a stale membership list silently reverts the change later, invisibly, under a procedure that looks correct.

**When a section, queue, or SSOT moved *out* of a document (even if the document still exists), grep the moved-from doc's bare inbound anchor (`[[wikilink]]` + path forms) with NO keyword conjunction.** The relocated content's inbound link is itself the identifier; a line pointing at the old home as "the project doc" / "full spec here" / "see [[…]]" is exactly the stale pointer that now misdirects, and it won't match an anchor-AND-topic-keyword grep. Structural queries (below) catch dangling *wikilinks* but never the *plain-text/prose* references to a moved target — only a bare-anchor text grep does. Triage each hit per the categories below (bare-anchor grep returns legitimate navigation links too).

**For link-integrity questions specifically, prefer structural queries over text grep.** A rename/move/delete that needs link-integrity verification is a structural question, not a text search. The system probably has a purpose-built query: an Obsidian vault has `obsidian unresolved` (queries the live link index); a codebase has language-server "find references" or `git grep` with the right filters; a wiki has a broken-link report. Read the project's tool-routing doc (e.g. CLAUDE.md, a contributor guide, or a "how to search" reference) before designing the verification step. The grep-as-default reflex is itself a failure mode — text search is sensitive to file format, encoding, hidden-directory exclusions, and ignore-pattern semantics that the structural query is indifferent to.

- **Stale cross-reference** — a pointer meant to track the current value but now wrong → **update it**. (The most common miss.) **Includes dated rolling current-state fields** an owning rule defines as replace-on-update — notably WIP per-entry `**Last:**` / `**Next:**` (`/park` Step 11: "replace, don't chain") and live planning/hub `Status` / `Current position` lines: the date is a refresh stamp, not a frozen-event timestamp, so update them when the session changed the state they summarise. **A hub's Status / Current-Status section also carries a co-located date-only `**Last update:**` / `**Last updated:**` stamp separate from the content it sits above** — when you edit that section's content, bump the stamp to the current date in the *same* pass; it's part of the edit's footprint, not a frozen timestamp. A content flip that updates the prose but leaves the co-located date stamp stale is a recurring miss (propagation catches the value, not the stamp beside it). **The enclosing artefact governs:** a "current"-phrased line inside a frozen artefact (session log, daily report, weekly-context snapshot, provenance record) stays historical, and a path that relocates with content is a **Live locator** (below), not this — don't infer "rolling" from wording alone.
- **Enumeration-predicate hit** — a hit where the changed identifier is still a valid list member, but the list's *governing predicate* makes a current-state claim the change falsifies for that member (a status flip to "deferred" where the name sits inside "three items **confirmed** (…, X, …)" or "launching **\<month\> \<year\>** (…, X, …)"; or a count: "3 items (A, B, X)" now 2). **Mechanical trigger:** the identifier and an *old* status/date/count token from the change sit in the *same* line, list-item, table cell/row, parenthetical, or immediately governing heading — that co-location is the reviewer-observable check. → **Update the framing, not the membership:** split the member out and annotate the new state ("X — deferred"), or revise the count. **Do NOT remove X** unless the change is an actual removal/cancellation (a deferral keeps the member). Do NOT classify "different context → leave" merely because the identifier string is still true. The enclosing-artefact rule still governs — a falsified predicate inside a frozen snapshot, or a timeless/current-neutral list with no stale predicate co-located, stays as-is.
- **Live locator** — a path/link/ID a *current workflow resolves to locate or re-read an artefact* (e.g. a hash/provenance log's path column that a verify pass re-hashes; a `**Source:**` path a tool reads). On a **move/rename** of unchanged content → update **only the locator field**, never a content hash/timestamp/proof. On a **delete** → leave it and flag (a MISSING / unresolved result is the correct integrity signal). A locator inside an *otherwise-historical* record is still live — this is the subtlest case and the one propagation passes miss.
- **Historical record** — a frozen record of what was actually said/sent/observed, or where an artefact lived *at event time* → **leave it** (or add a separate relocation note; don't overwrite).
- **Different context** — unrelated content that merely shares the identifier string → **leave it**.

If you can't tell whether a value is a live locator or a frozen record, **report the ambiguity instead of editing**. Use the file's lock if one exists. Always show the grep output (it proves the grep ran) — and the **full** hit-set, not a sampled subset: the grep's complete hit-list *is* the scope of the triage, so account for every returned hit (tag each `updated` / `left (historical)` / `left (different context)`). A "no remaining stale refs" conclusion is earned only by triaging the whole hit-list, never by checking the files you expected to matter or a hand-picked candidate list.

---

## 13. Cite Vault Items by Stable Identifier, Not Line Number

When a skill writes a **durable artefact** — a report, review, session log, routed flag, or any note that will be re-read later — that references an item living in a churning planning file (a `Tasks.md` task, a WIP entry, a `Tickler.md` line, an open loop), name it by its **title / heading / content**, never by line number (`Tasks.md L43`).

Line numbers rot the instant the file is edited — and several skills mutate a planning file *within the same run*, so any `Lnn` written after that point is stale on write. The canonical case: `/weekly-hygiene` step 8 purges completed `[x]` lines from `Tasks.md`, shifting every line below; a report generated later in the same run that cites `Tasks.md L43` already points at the wrong line. The durable artefact outlives the line-numbering; the title does not.

Ephemeral, in-conversation references during a single turn (e.g. a grep result you act on immediately) are exempt — this rule governs what gets **persisted**.

---

## 14. Verbatim External Text vs In-Place Formatting Hooks

When a skill writes **verbatim external text** to the vault — a transcript, a quoted source passage, an interview excerpt, anything whose exact wording must survive — a `PostToolUse` formatting hook will silently corrupt it. Some vaults run such a hook (a spelling normaliser) that fires on every `Write`/`Edit` to a `.md` file and rewrites the file **in place** (e.g. de-Americanising a US speaker's quotes: `color`→`colour`, `analyze`→`analyse`); if one is configured, the rule below is mandatory whenever exact wording matters. The existing word-level ignore files cannot help — you can't enumerate every foreign-spelled word a speaker might use.

**The hook fires on `Write`/`Edit`, not on a shell write (`cat`/`printf`).** That asymmetry is the lever.

**Two defences (use both for belt-and-braces):**

1. **Hook-safe append.** Write only your *own* prose (frontmatter + synthesis header) with the editor tool, then append the verbatim body via the shell:
   ```bash
   printf '\n' >> "$dest"      # guarantee a newline boundary
   cat "$body_file" >> "$dest" # bypasses the PostToolUse hook
   ```
   Then **never `Write`/`Edit` that note again** — any later edit re-fires the hook on the whole file, body included.

2. **Path-level exclude.** If the hook supports it, exclude the verbatim-output folder once so fidelity holds regardless of write method (if the hook reads an `exclude_paths` allowlist from a `config.local.json`-style file, add the verbatim-output folder there). This is the robust default; the append trick is the portable fallback for vaults without an exclude.

**Precondition for the append trick:** it only holds if the hook's matcher is `Write|Edit` and does **not** intercept shell writes. Verify the matcher before relying on it; if a hook matches `Bash`/shell writes, the append silently corrupts the body with no error — fall back to the path-exclude.

**Collateral edits.** Adding wikilinks/back-references to *other* notes (a dossier, a hub) after creating verbatim content also fires the hook on those notes. Short edits to already-normalised hub prose are safe; but if the target note itself holds verbatim quotes, exclude it or append rather than `Edit`.

**Inline identifiers.** For a stray foreign-spelled token in otherwise-normalised prose (a product name, a US institution, a code symbol), wrap it in an inline code span (backticks) — the markdown strategy preserves code spans. Use this for one-off tokens, not whole bodies.

---

## 15. Published-Transcript Extraction (fetch a verbatim body to a file)

The canonical procedure for pulling an **already-published** transcript (a podcast/show page, Substack, an official transcript page) off the web as a clean verbatim markdown body **in a file, never through context**. Single source of truth: `/archive-transcript` (its core job) and the published-transcript fast-path in `/transcribe` (Phase 0), `/transcribecloud` (Phase 1.5), and `/podcast-digest` (Tier 1a) all use this — point here rather than re-describing extraction in the skill. Each caller keeps its own *whether-to-use-it* framing (the cost/fidelity choice, dedup, the header it writes); this section owns only the fetch-and-extract mechanism. (Validated against Ghost sites and the Complex Systems `c-content` template; `curl`+`bs4`+`pandoc` beats reader APIs such as jina, which manufacture phantom pagination on static pages.)

**Prereqs** — confirm before fetching, so a fresh machine fails fast with a clear message rather than mid-pipe:
```bash
command -v curl pandoc python3 || echo "MISSING a core tool"
python3 -c 'import bs4, lxml' || echo "MISSING python bs4/lxml"
```
If a tool is missing, stop and tell the user (or fall back to machine transcription — see the fallback note below).

**Code blocks below sit at column 0 deliberately** — the Python heredoc is indentation-sensitive, so copy it flush-left, not indented under a list item.

**Confirm static HTML:** `curl -sL "<URL>" | wc -c` — a large byte count is necessary but not sufficient (a JS shell can be large too); the real gate is the word count below.

**Extract → clean → markdown.** The intermediate paths are a **deterministic function of the `<URL>`**, so they survive across tool-call boundaries with nothing to remember: a later step re-derives the same `$BODY` from the same `<URL>`, or just reuses the `BODY=` path the block prints (`<BODY_FILE>` in callers). This is the cross-tool-call hazard from `_shared-patterns.md` (shell vars don't persist), solved by making the path *reconstructable* rather than carried — no random `mktemp` name to lose. A multi-page batch never collides because the slug is per-URL:

```bash
TMP="${TMPDIR:-/tmp}"   # TMPDIR is often unset on Linux; /tmp is the reliable fallback
# deterministic per-URL slug (lowercase host+path prefix + cksum of the full URL) → reconstructable path, no random temp name
SLUG="$(printf '%s' "<URL>" | tr '[:upper:]' '[:lower:]' | sed -E 's#^https?://##; s#[^a-z0-9]+#-#g; s#(^-|-$)##g' | cut -c1-30)-$(printf '%s' "<URL>" | cksum | cut -d' ' -f1)"
HTML="$TMP/transcript_$SLUG.html"
BODY="$TMP/transcript_$SLUG.md"
echo "BODY=$BODY"   # the body path (<BODY_FILE> in callers); reconstruct it by re-deriving TMP+SLUG from <URL> in any later tool call
curl -sL "<URL>" -o "$HTML"
python3 - "$HTML" > "$BODY" <<'PY'
import sys, re, subprocess
from bs4 import BeautifulSoup
soup = BeautifulSoup(open(sys.argv[1], encoding='utf-8').read(), 'lxml')
# most-specific content container by PRIORITY (not densest — densest grabs the outer page wrapper)
node = None
for sel in ('section.gh-content', '.post-content', '.gh-content', '.c-content', 'article', 'main'):
    node = soup.select_one(sel)
    if node:
        break
node = node or soup.body
for t in node.select('script, style, nav, footer, form, button, iframe, figure, .kg-card, img, svg, audio, video'):
    t.decompose()
for h in node.find_all(re.compile(r'^h[1-6]$')):          # strip in-heading timestamp/permalink links, KEEP heading text
    for a in h.find_all('a'):
        atext = a.get_text().strip()
        if not atext or re.fullmatch(r'[\d:apm.\s()]+', atext, flags=re.I):
            a.decompose()                                 # empty or bare-timestamp anchor → drop it
        else:
            a.unwrap()                                    # anchor wraps real heading text → keep the text, drop the tag
    txt = re.sub(r'\s*\(\s*[\d:apm.\s]*\)\s*$', '', h.get_text(), flags=re.I).strip()
    if not txt:
        h.decompose()                                     # heading was nothing but a timestamp link → drop the empty heading
    else:
        h.clear(); h.append(txt)
for t in node.find_all(['div', 'span']):                  # flatten residual wrappers pandoc would emit as raw HTML
    t.unwrap()
md = subprocess.run(['pandoc', '-f', 'html', '-t', 'gfm', '--wrap=none'],
                    input=node.decode_contents(), text=True, capture_output=True).stdout
md = re.sub(r'\n{3,}', '\n\n', md)
md = '\n'.join(l for l in md.split('\n')
               if 'An error occurred' not in l and 'Unable to execute JavaScript' not in l)
print(md.strip())
PY
echo "body words: $(wc -w < "$BODY")"
grep -cE '<div|</div|<span|base64' "$BODY" || true   # leak check — expect 0 (grep exits 1 on no match; that's fine)
```

**Gate on the word count + leak count**, not byte count: a body far below a real transcript (say < 800 words) means the selector missed the container — inspect structure (`grep -oE '<(article|main|section|div)[^>]*class="[^"]*"' "$HTML" | sort -u | head`) and add the right selector to the priority list. A non-zero leak count means raw HTML survived — widen the `decompose`/`unwrap` set. Spot-check `head`/`tail` of `$BODY` (a few lines) to confirm it starts/ends in transcript content.

**Metadata for the header, without reading the body** — published description (covers Ghost's `og:`/`twitter:` variants) and the section outline:

```bash
python3 - "$HTML" <<'PY'
import sys
from bs4 import BeautifulSoup
soup = BeautifulSoup(open(sys.argv[1], encoding='utf-8').read(), 'lxml')
for sel in ('meta[name=description]', 'meta[property="og:description"]', 'meta[name="twitter:description"]'):
    m = soup.select_one(sel)
    if m and m.get('content'):
        print('DESC:', m['content']); break
PY
grep -E '^#{2,3} ' "$BODY"      # section outline, for the cruxes
```

**Fallback (no published transcript / JS-rendered):** machine-transcribe the audio/video instead — the WhisperX path (`/transcribe` locally, `/transcribecloud` on a cloud GPU). Much heavier; tell the user before launching a batch.

---

## 16. Out-of-Band Evidence in Reviewer Briefs

Canonical rule for every skill that despatches a brief to a reviewer that cannot see this session — `/park`'s audit sub-agent, `/audit`'s panel seats, `/second-opinion`'s reviewers, `/security-audit`'s optional panel. Those skills point here and carry no copy to drift.

**The rule.** Where the work product's claims rest on material the reviewer cannot reach from the artefact itself — web fetches, emails, API results, tool output, the user's pasted text — embed that material in the brief, verbatim, under a heading that marks it established: `## Out-of-band evidence (treat as given — do NOT flag as fabricated)`.

**Tag each excerpt's provenance — `[primary]`, `[secondary]`, or `[unverified]`** — and state under the heading what "given" licenses: *these excerpts are real and were genuinely gathered, so do not report them as fabricated; their **content** is still open to challenge, and anything tagged `[secondary]` or `[unverified]` especially so.* `[primary]` is the authority itself (vendor docs, the API's own response, the source file); `[secondary]` is someone reporting on it (a news write-up, a third-party guide, another model's summary); `[unverified]` is an assertion you carried in without checking, including one inherited from the artefact under review.

**Why the tags.** Without them this rule inverts: the heading that stops false positives starts manufacturing false negatives. An unverified claim embedded as "given" is immune to the panel — every seat is instructed not to question it, so a wrong premise emerges from review wearing four models' endorsement, and the tiebreak reads the silence as agreement. Correlated agreement is already weak evidence; agreement you *instructed* is no evidence at all. The tag is what keeps "don't call this invented" from collapsing into "don't think about this." Caught 2026-07-19: a third-party guide's claim about a vendor's data-handling defaults went into a brief untagged, survived a full tri-model audit unchallenged, and was false — the primary source said the opposite.

**Checkable:** every excerpt under the heading carries one of the three tags. An untagged excerpt is a claim you are asserting on your own authority — either verify it and tag it `[primary]`, or tag it `[unverified]` and let the panel do its job.

**Why.** A reviewer confined to the artefact cannot distinguish *"sourced from evidence you withheld"* from *"invented"*, so it reports the first as fabrication. Each false positive costs a round-trip to adjudicate and discredits the true findings beside it. In a panel it is worse: one omitted source produces a false positive *per seat*, and the synthesis then reads convergent fabrication findings as corroboration when they are one shared artefact of your own brief.

**Embedding most of the sources is the trap.** Partial evidence yields *confident, specific* false positives exactly on the claims whose source you omitted — and the omitted one skews toward the **originating** source (the report or message that began the work), because by brief-writing time your attention has moved to whatever you fetched later while correcting it.

### Deriving N — never from recollection

The count is the mechanism, and it only works if it is anchored **outside the attention that failed**. An agent that dropped a source while writing will drop it again while counting, then emit a self-consistent `3 → 3` and pass while short. So do not count "what I drew on". Derive N from two artefacts:

1. **The work product's own citation/source section** — every distinct external item it names. A secondary report is a **distinct source** from the primary it reports on.
2. **A sweep of this session's fetch/read tool calls** — every URL fetched, file read, email opened, paste received that fed a claim. This is the half that catches what a note *never cites*: pasted text, tool output, emails.

N is the union. Display before despatch:

```
Out-of-band evidence: sources drawn on N → excerpts embedded N
```

A short count means the brief is incomplete, not the work wrong.

### Scope, size, and the seats

- **"Relevant text" means the passages the claims rest on** — not whole documents. Quote the load-bearing passage; cap each source at roughly 500 words.
- **Mind the transport.** `/audit` and `/second-opinion` pipe the brief into CLI seats with differing context windows, under a requirement that the payload be identical across seats. An uncapped dump can silently truncate in one seat — reproducing the partial-evidence false positives this rule exists to prevent, now invisibly. If the evidence exceeds the budget, attach it as a file path all seats can read (§10's `--include-directories` / `-C`) rather than inlining it.
- **Conflicting sources:** where two disagree and the work picked one, say which won and why — otherwise the reviewer re-litigates a settled question.

### When a source is unrecoverable

If a source's text has left context (a long session, a `/compact` — and the first thing lost is the earliest fetch, which this rule identifies as disproportionately the originating source), **re-fetch it**. If it cannot be recovered, say so in the brief under the same heading — `<source> — text unavailable; do NOT flag claims traced to it as fabricated` — and **still count it in N**. Never paraphrase it from memory (that manufactures the fabricated-quote failure), and never drop it silently (that is the original failure, reproduced).

---

## 17. Push-Side Hub Record (commits are their own identifier class)

Canonical rule for every skill that runs a reference-graph / propagation pass after a session that pushed code — `/park` Step 12(a), `/goodnight` Step 15(a). Those skills point here and carry no copy to drift.

**The rule.** Every commit hash a session records is its own identifier. For each one, grep the vault for that repository's hub and confirm three things:

1. A `## Session History` row exists for the session that pushed it.
2. The hub's own `**Last update:**` / `Last updated:` stamp is current.
3. The WIP entry's `**Last:**` field reflects the push.

**Why the ordinary per-identifier pass misses it.** A pushed commit is a world-state change with no textual footprint in the vault. Nothing in the session's file edits contains the hash, so no content grep reaches the hub — and the hub is frequently a file the session never opened. The propagation pass therefore returns a clean, *fully earned* hit-list while the project's own commit-level record silently misses an entry. This is the inverse of the usual failure: not a stale value left behind, but a **new** record never written, in a document whose stated job is to hold it.

**Scope.** Applies to any repository with a hub in the vault, whether or not the session edited vault files for it. It applies equally when the commit was pushed by a skill's own bookkeeping (a skill-file fix committed during `/park` is still a push, and its hub row is still owed) — the rule is about the push, not about who initiated it.

**Checkable:** for each hash, one grep must return the repo's hub, and that hub must carry a row citing the pushing session. A propagation report that enumerates no commits on a session that pushed one has not run this check.
