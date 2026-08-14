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
- **Shipped one-shot work** (published blog post, completed migration, resolved bug, anything finite that's now done with no ongoing tracking need) → link to an *existing* area hub that naturally groups related work. **Do not create a project file retroactively.** The "finite work → project file" rule above is calibrated for in-flight finite work where a project file earns its cost by hosting the task queue; once the work ships, the task queue is empty and a retroactive project file is noise. Example: a published post on your blog links to `[[04 Areas/Blog/Blog]]`, not a newly-created post-specific project file.
- **Operational/meta work with no natural project or area home** (e.g. /morning, /goodnight, general sysadmin, security hygiene, vault maintenance) → `Project: None (operational <scope>)` — e.g. `None (operational /morning)`, `None (operational tech-infra)`. Don't reach for a loosely-related project to fill the slot; `None` is the correct answer.
- **Never link to:** Resources, Archive, or 07 System files (these are references and meta, not project/area homes).
- **No canonical home and work is still in flight?** Create a project or area file. Small one-off items may simply live in This Week or the Tickler with no home doc.
- **Working in Resources?** That's a signal it should graduate to an Area
- **Why:** Consistent project links enable reliable pickup grouping.

---

## 3. Item Linking Convention

Every actionable item in a day section or planning document should link to its project/area context where one exists:

- Project doc exists → `→ [[03 Projects/Project Name]]`
- Area doc exists → `→ [[04 Areas/path/doc]]`
- Standalone/generic items (no project context) → no link

When moving items that already have project/area links, preserve them. Replace session log links (`→ [[06 Archive/...]]`) with project/area links — session context is low-value once the item is in a planning doc.

---

## 4. Tickler SSOT Transfer

Tickler is a time-deferred queue, not a persistent SSOT. When items are pulled from Tickler into a planning document (This Week.md, a project page, etc.), **the planning document becomes SSOT** for those items. Delete the Tickler copy immediately to prevent duplicate checkboxes across the vault. The Tickler's job is done once the item surfaces and lands in a plan.

When migrating Tickler items:
- Preserve existing project/area links (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`)
- Replace session-log-only links with the relevant project/area link
- Add links to bare items per the Item Linking Convention (Section 3)

---

## 5. File Locking Mandate

**Use `flock` via dedicated scripts, NOT the Edit tool.** The Edit tool has no file locking — if two Claude instances edit the same file simultaneously, one write silently overwrites the other.

**Why dedicated scripts instead of inline flock:** Claude Code's permission system saves the entire bash command as a permission pattern in `settings.local.json`. Multi-kilobyte session summaries inside flock commands bloat the settings file. The scripts (`write-session.sh`, `add-forward-link.sh`, `write-tickler.sh`, `update-session-section.sh`, `backfill-files-updated.sh`, `locked-edit.sh`) receive content via stdin or arguments — the permission system only stores the short script invocation, not the payload.

### Planning-file writes go through `locked-edit.sh` (NOT the Edit tool)

**Every mutation of a shared planning file — `01 Now/This Week.md`, `01 Now/Tickler.md`, and project/area hub docs in `03 Projects/` or `04 Areas/` — uses `locked-edit.sh`, not the Edit tool.** These files are written by `/park`, `/goodnight`, `/morning`, `/weekly-hygiene`, `/weekly-review`, `/start-project`, and `/complete-project`; any two running concurrently (e.g. a scheduled `/goodnight` while you `/park`) would silently clobber each other through the lockless Edit tool. `locked-edit.sh` serialises writers through the file's canonical lock and matches literally, so concurrent edits either both land (disjoint) or fail loudly (conflicting) — never silent loss.

**Creation is not mutation — a first write uses `Write`, not the lock.** The rule above governs *editing existing content*: the hazard it prevents is a lost read-modify-write cycle, and a file that does not yet exist has no content to lose. (`locked-edit.sh` *can* create a missing target — that capability is real, it is simply not the reason to reach for it.) The genuine risk when creating is two sessions racing to create the *same* file, and the lock does not address that: it would serialise both writes and report success twice. That is a name-collision check's job, owned by the creating skill's own conflict step, which must test both the file path **and** any index/dashboard heading the new file claims. A skill whose Step-N creates a project or area doc should say so explicitly rather than leaving the mechanism unstated, since an unstated mechanism reads as an oversight against this section.

```bash
# Replace a unique block (old_string must match exactly once, like the Edit tool):
cat << 'EOF' | "{VAULT}/.claude/scripts/locked-edit.sh" "{VAULT}/03 Projects/Project Name.md" --replace
**Last update:** 2026-06-01 - old state
========OPENCAIRN-LOCKED-EDIT-SEP========
**Last update:** 2026-06-02 - new state
EOF
# Other modes: --replace-all (every occurrence), --append (stdin appended at EOF).
# Exit codes: 0 ok · 1 usage/lock error · 2 no match · 3 ambiguous (>1 match under --replace).
# Treat 2/3 as a real conflict (a parallel writer changed the region): re-Read the file and
# recompute, don't loop-retry. Exit 1 with a lock message means another writer holds the lock
# past the timeout — that is Failure mode B, not a content conflict: report it and stop rather
# than retrying or falling back to the Edit tool, which is what the lock exists to prevent.
```

**⛔ After each `locked-edit.sh` call, grep the target for the full padded input form — `^========OPENCAIRN-LOCKED-EDIT-SEP========$` — and not the bare fragment.** The fragment matches any file that merely *documents* the token (several skills and logs do), so it false-positives on exactly the files this library edits most; anchoring on the padded line is what distinguishes residue from prose. Residual false positive, stated so it isn't mistaken for residue: a file carrying the separator inside a fenced code example still matches — this file does, twice. Judge a hit by whether it sits in the region you just wrote, not by the count. A hit means a malformed heredoc left the separator line in the file — remove it under the same lock before continuing. Exit 0 does not rule this out: the script separates on the first occurrence, so a payload with a stray or mis-indented separator can write cleanly and still land the token in the file. The defect is silent and survives into whatever reads the file next.

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
- **Use Python+flock only after killing the hung scripts**, and only when a dedicated script would be the normal path. This Week/Tickler/project-doc/hub edits are no longer "ad-hoc with no dedicated script" — `locked-edit.sh` is their dedicated path (Section 5); use it rather than inline Python+flock.

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

## 6. (retired 2026-08-05 — WIP demoted) WIP Session Link FIFO Cap

Session links now live in project docs' `## Session History`; no dashboard cap applies.

---

## 7. Timezone and Date Handling

- **Always check current date/time** via the `date` command at the start of every command. Never assume, cache, or reuse timestamps from prior tool calls.
- **Use system timezone** (local time wherever the user is). During travel, sessions are dated in local context (Tokyo → JST, Denver → MST). This is intentional — local time is more meaningful than forcing the home timezone.
- **Verify date-to-weekday mappings** with `date -d`. LLMs are unreliable at mapping dates to days of the week. When writing "Mon 15 Feb" or similar, always run `date -d "2026-02-15" +%A` in bash first.
- **Portability — `date -d` is GNU-only.** On macOS/BSD the equivalent is `date -j -f "%Y-%m-%d" "2026-02-15" +%A`, and relative arithmetic is `date -v+6d +"%A %d %b"` rather than `date -d "+6 days" …`. `brew install coreutils` provides `gdate` with GNU semantics, which is the simplest fix for a mac user running this library. This applies to **every** `date -d` in this file (§9's rolling-window arithmetic, §18's deadline derivation) and in any skill that loads it — the date rules above are mandatory and frequently executed, so unlike §5's post-failure diagnostics a portability gap here breaks normal operation on the first run.

---

## 8. Skill Monitor

When executing any slash command, also follow the instructions in `_skill-monitor.md` (same commands directory as this file). Watch for gaps in the command's logic. If you improvise a step that isn't documented, if a mistake could have been caught by a better checklist item, or if a documented step turns out unnecessary — note it and log it per `_skill-monitor.md` at the end. Do not propose edits in-session; the log is processed weekly by `/weekly-hygiene`.

---

## 9. This Week.md Rolling Window Maintenance

This procedure keeps the rolling 7-day window current. It runs during `/morning` (step 6) and `/goodnight` (step 11). If This Week.md doesn't exist, skip entirely.

**Write mechanism (F1):** `This Week.md` is a shared planning file — every trim/extend/populate mutation below goes through `locked-edit.sh`, not the Edit tool (see §5). Use `--replace`/`--replace-all` to delete or rewrite day sections. `--append` adds at EOF, so it is valid for new day sections **only when the file has no trailing non-day content**; if a `---` / `## Refs` / other trailing section exists, use `--replace` on the trailing boundary block instead (per the placement rule below).

### Trim old day sections

Delete any day sections whose date is more than 3 calendar days before today. Past days are already archived in Daily Reports — keeping them past 3 days adds clutter without value.

1. Parse each `## ` heading for a date (e.g. `## ☀️ Fri 6 Mar` → 6 Mar, `## Mon 9 Mar` → 9 Mar). Skip headings that aren't day sections (e.g. `## Refs`).
2. For each day section, compute: `today_date - section_date`. If > 3 calendar days, it becomes eligible for deletion — but **sweep before deleting**. Grep the section body for unchecked items first:
   ```bash
   # Materialise the section body first — from the day heading to the next '## ' (exclusive)
   BODY=$(awk -v z=0 'f && /^## /{exit} index($z, "## HEADING_TEXT") == 1 {f=1} f' "{VAULT}/01 Now/This Week.md")
   printf '%s\n' "$BODY" | grep -nE '^[[:space:]]*-[[:space:]]*\[ \]'
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

**This move is gated on the date and nothing else.** Callers carry advisory load thresholds for This Week (`/morning`, `/goodnight`, `/weekly-review`); none of them gate this step. Extending the window into a date is what makes that date's items due, so a section left empty because the window "looks full" is a day section asserting nothing is due while the Tickler still holds the items — the SSOT split this section exists to close. Move them all, then let the caller report the count.

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

- **Headless `gemini -p` has no shell tool at all — this is not the `--policy` file's doing.** Verified on gemini 0.40.1 by despatching with *no* `--policy` flag and asking the model to enumerate its own toolset: `update_topic, list_directory, read_file, grep_search, glob, google_web_search, enter_plan_mode, invoke_agent`. `run_shell_command` is absent. So the deny-rule above is belt-and-braces for shell rather than its cause, and **loosening the policy does not buy an executing Gemini seat** — the seat can read, grep and glob, nothing more. Codex is the CLI seat that *can* run commands: `--sandbox read-only` blocks writes, not execution. Two traps: seeing `Tool "run_shell_command" not found` and blaming your own policy (costs a redundant despatch to disprove), and briefing a Gemini seat to "run the tests" — it cannot, so per the pre-flight below the orchestrator runs them and embeds the receipts.

- **Seats do not verify equally, and the read-only measure is what causes the gap.** Where a CLI offers a filesystem-level read-only sandbox, the seat keeps shell and can check a claim against local man pages, config and unit files. Where no read-only sandbox or command-level policy is available, the remaining option is to deny the shell tool outright (shell *is* a write path: `echo > file`) — which also removes that seat's ability to verify anything locally. Classify each seat by the outcome, not by the product: whichever seats end up shell-denied under your despatch config are the ones that cannot verify. Two consequences to design around, not fix:
  - **A shell-denied seat's findings skew toward the unverifiable.** In a tiebreak, its unique claim about a flag, key or path carries less evidential weight than the same claim from a seat that could run the command. Weigh by what the seat could actually check; don't count votes.
  - **A seat whose only evidence route is the network fails wholesale when that route degrades**, producing no output rather than a weaker review. Silence from such a seat is a transport failure, never endorsement — announce it as a reduced panel.

  **Remedy — a pre-flight, and it is the orchestrator's job.** Before despatch, not after: if any seat is shell-denied and the review turns on anything a shell would settle (a flag's behaviour, a config key, whether a path exists, what a command actually prints), run those checks yourself and embed the output under §16's out-of-band heading. For a shell-denied seat, "material the reviewer cannot reach from the artefact" includes everything behind a shell, so omitting it reproduces §16's partial-evidence false positives in that seat specifically. Doing it afterwards does not help — by then the seat has already guessed, and you are adjudicating its guess instead of preventing it. Every skill despatching a mixed-capability panel runs this as a step in its own pre-despatch sequence and points here rather than restating it.

- **The Grok seat is an API seat, not a CLI seat — it reads nothing.** `xai_client.py` posts to xAI's Responses API over stdlib `urllib`; it has no filesystem access, so the target must be passed with `--source` and is inlined into the prompt as a delimited appendix. Three consequences that the other two seats don't have:
  - **Manifest in place of a read-list.** The wrapper appends each source as `path | bytes | sha256` and instructs the seat to reproduce that manifest verbatim and quote what it relied on. That manifest is this seat's evidence standard — the attestation rule (**§23**) is satisfied by the manifest, not waived. §23 carries the enforcement test; note it requires manifest **and** quoted passages, so supplying only one fails.
  - **Size cap, fail-closed.** `MAX_INLINE_BYTES` (400 KB, ~100k tokens — kept under xAI's >200k-token tier where the per-token rate doubles). Over the cap the wrapper raises and the seat is **dropped with the reduced panel announced**; it never silently truncates, because a truncated appendix produces confident findings about text the seat never saw.
  - **Availability probe is `--probe`, not `--version`.** There is no binary: `xai_client.py --probe` exits 0 when `XAI_API_KEY` is set, 1 otherwise. Probe *before* despatch — an unset key must degrade to a three-seat panel up front, not fail mid-run. Note the key must be in the environment the Bash tool actually runs in; a key exported only in `~/.bashrc` will not reach a non-interactive shell (same trap as `second-opinion.md` Phase 2A step 5).

  The wrapper sets `store: false` (xAI otherwise retains responses server-side for 30 days) and never enables live search on a review call. `store: false` forecloses `previous_response_id` threading, which is why the Grok seat has no true resume — round 2 replays prior context. **xAI does not train on API inputs or outputs by default** — its API security FAQ states it "never trains on your API inputs or outputs without your explicit permission," so training is opt-in, not opt-out. The "improve the model" toggle is the *consumer* Grok control, not a developer-API setting; there is nothing to switch off. What does apply: API requests and responses are retained 30 days, encrypted at rest, for abuse auditing. `store: false` governs stateful threading, not that audit window. Zero Data Retention eliminates it but is team-level and disables the stateful Responses API, Files, Collections, Batch, and per-key logging — don't enable it for this.

- **Seat tiering (Claude seats).** Judgment and generation seats — anything whose errors propagate invisibly or whose output *is* the deliverable — run on the despatching session's model; do not downgrade them. Verification and mechanical seats — audits of work the session already did, bounded-failure checks whose misses are caught downstream — may pin to a strong-but-cheaper tier via the Agent tool's `model` argument (e.g. `model: opus`). A pin is declared at the despatch site in the despatching skill, with its reason stated, and never sits below the Opus tier without an explicit per-skill justification. **A pin is a floor, not a discount:** it only reduces spend when the despatching session is running something more expensive, is a no-op when the parent is already at the pinned tier, and *raises* cost against a cheaper parent. Justify a pin by the capability the seat needs, not by an assumed saving. This tiering governs Claude Agent-tool seats only; the CLI/API seats' models resolve per the bullet below.

- **Seat model resolution (for currency checks).** Each seat resolves its model a different way, and the answer lives in config or a live probe, never in memory: the **Claude seat** floats with the despatching session's model by default; seats pinned under the seat-tiering rule above declare `model:` at their despatch site — resolve pins by grepping the command files (`rg -n "model: (opus|sonnet|haiku)" <commands dir>`); the **Gemini seat** reads `model.name` in `~/.gemini/settings.json`; the **Codex seat** reads the `model` key in `~/.codex/config.toml`, falling back to the CLI's built-in default when unset — probe the resolved default live (a minimal `codex exec` call prints `model:` in its preamble) and record the CLI version, since an unpinned seat is only as current as its last CLI update; the **Grok seat**'s models are the constants at the top of `xai_client.py`, checked against the provider's models endpoint (`GET https://api.x.ai/v1/models`, `XAI_API_KEY` in the Bash tool's environment). Consumed by `/quarterly-hygiene`'s model-currency step; update here, not there, when a CLI moves its config.

---

## 11. Scratchpad Work-Product Protection

Scratchpad files (`Scratchpad.md`) are transient capture surfaces — designed to be cleared regularly, not durable homes. `/reply` drafts persisted there are at-risk work product until the user confirms lifecycle completion.

**Draft identification.** `/reply` draft sections are identified by a heading line starting with `**Reply to ` and ending with `:**`. Example: `**Reply to Sarah (WhatsApp — dinner plans):**`.

**Section boundary.** A draft section starts at the heading line, includes all content through the trailing `> Context:` / `> Note:` blockquote, and ends before the next line matching the same heading pattern, the next `#`-heading, or EOF.

**Cleanup ownership.** `/reply` owns in-session cleanup — it removes its draft section from Scratchpad after lifecycle completion (user says "sent" or pastes final text). `/park` Step 4 and `/weekly-hygiene` Step 5 may remove or route draft sections only after explicit per-draft user confirmation that the draft was sent or is no longer needed.

**Locking.** Scratchpad mutations (section removal, routing) use `locked-edit.sh` (§5 mechanism) for atomicity. Read the current Scratchpad content first, extract the exact section text per the boundary rules above, then pass as `old_string` to `locked-edit.sh --replace` with empty `new_string`.

---

## 12. Grep-hit triage (reference-graph / Layer-3 propagation)

When propagating a changed identifier across the vault — `park` Step 6 (reference graph), `audit` Layer 3, `complete-project`'s moved-anchor sweep — classify each grep hit **by what the value does, not by the file type** before editing:

**First, choose the right grep target — the value sibling docs actually contain.** For a *changed* value, grep the old value. For a **NEW option/alternative added to a pre-existing decision/record**, the new value is *absent* from the very sibling docs that need it (the stale timeline row, the index that lists only the incumbent) — so grep the decision's **anchor** (route/decision/record key), the join key those docs already share, **not** the new option text. Grepping the new value finds nothing and false-passes the propagation.

**When the change *adds a member to a documented set*, the anchor is the container — not the member, and not its topic.** A relocation *into* the set from elsewhere is a member-addition too — the destination set's membership changed even though no item is new. Adding a component to an assembly, a leg to a bundle, an entry to an enumeration: the doc recording that set's *membership* lists the incumbents and names the container, so it contains neither the new member's identifier nor, often, any topic keyword you would think to grep. Both obvious targets return nothing and false-pass; only the **container's name** (the set/list/collection identifier) reaches the membership record. **Checkable:** for every added member, one enumerated anchor's grep must return the membership record — if none does, the anchor is wrong, not the record clean. Note this is *not* satisfied by "also re-grep the docs you edited": the membership record is routinely inside an edited doc yet shares no token with the change, so an identifier-scoped intra-file grep misses it exactly as an inter-file one does. Highest-stakes case is a set that some *other* documented procedure rebuilds or re-derives from — a stale membership list silently reverts the change later, invisibly, under a procedure that looks correct.

**When a section, queue, or SSOT moved *out* of a document (even if the document still exists), grep the moved-from doc's bare inbound anchor (`[[wikilink]]` + path forms) with NO keyword conjunction.** The relocated content's inbound link is itself the identifier; a line pointing at the old home as "the project doc" / "full spec here" / "see [[…]]" is exactly the stale pointer that now misdirects, and it won't match an anchor-AND-topic-keyword grep. Structural queries (below) catch dangling *wikilinks* but never the *plain-text/prose* references to a moved target — only a bare-anchor text grep does. Triage each hit per the categories below (bare-anchor grep returns legitimate navigation links too).

**For link-integrity questions specifically, prefer structural queries over text grep.** A rename/move/delete that needs link-integrity verification is a structural question, not a text search. The system probably has a purpose-built query: an Obsidian vault has `obsidian unresolved` (queries the live link index); a codebase has language-server "find references" or `git grep` with the right filters; a wiki has a broken-link report. Read the project's tool-routing doc (e.g. CLAUDE.md, a contributor guide, or a "how to search" reference) before designing the verification step. The grep-as-default reflex is itself a failure mode — text search is sensitive to file format, encoding, hidden-directory exclusions, and ignore-pattern semantics that the structural query is indifferent to.

- **Stale cross-reference** — a pointer meant to track the current value but now wrong → **update it**. (The most common miss.) **Includes dated rolling current-state fields** an owning rule defines as replace-on-update — notably a project doc's `## Current Objective` / `## Next Actions` state (replace, don't chain) and live planning/hub `Status` / `Current position` lines: the date is a refresh stamp, not a frozen-event timestamp, so update them when the session changed the state they summarise. **A hub's Status / Current-Status section also carries a co-located date-only `**Last update:**` / `**Last updated:**` stamp separate from the content it sits above** — when you edit that section's content, bump the stamp to the current date in the *same* pass; it's part of the edit's footprint, not a frozen timestamp. A content flip that updates the prose but leaves the co-located date stamp stale is a recurring miss (propagation catches the value, not the stamp beside it). **The enclosing artefact governs:** a "current"-phrased line inside a frozen artefact (session log, daily report, weekly-context snapshot, provenance record) stays historical, and a path that relocates with content is a **Live locator** (below), not this — don't infer "rolling" from wording alone.
- **Enumeration-predicate hit** — a hit where the changed identifier is still a valid list member, but the list's *governing predicate* makes a current-state claim the change falsifies for that member (a status flip to "deferred" where the name sits inside "three items **confirmed** (…, X, …)" or "launching **\<month\> \<year\>** (…, X, …)"; or a count: "3 items (A, B, X)" now 2). **Mechanical trigger:** the identifier and an *old* status/date/count token from the change sit in the *same* line, list-item, table cell/row, parenthetical, or immediately governing heading — that co-location is the reviewer-observable check. → **Update the framing, not the membership:** split the member out and annotate the new state ("X — deferred"), or revise the count. **Do NOT remove X** unless the change is an actual removal/cancellation (a deferral keeps the member). Do NOT classify "different context → leave" merely because the identifier string is still true. The enclosing-artefact rule still governs — a falsified predicate inside a frozen snapshot, or a timeless/current-neutral list with no stale predicate co-located, stays as-is.
- **Live locator** — a path/link/ID a *current workflow resolves to locate or re-read an artefact* (e.g. a hash/provenance log's path column that a verify pass re-hashes; a `**Source:**` path a tool reads). On a **move/rename** of unchanged content → update **only the locator field**, never a content hash/timestamp/proof. On a **delete** → leave it and flag (a MISSING / unresolved result is the correct integrity signal). A locator inside an *otherwise-historical* record is still live — this is the subtlest case and the one propagation passes miss.
- **Historical record** — a frozen record of what was actually said/sent/observed, or where an artefact lived *at event time* → **leave it** (or add a separate relocation note; don't overwrite).
- **Different context** — unrelated content that merely shares the identifier string → **leave it**.

If you can't tell whether a value is a live locator or a frozen record, **report the ambiguity instead of editing**. Use the file's lock if one exists. Always show the grep output (it proves the grep ran) — and the **full** hit-set, not a sampled subset: the grep's complete hit-list *is* the scope of the triage, so account for every returned hit (tag each `updated` / `left (historical)` / `left (different context)`). A "no remaining stale refs" conclusion is earned only by triaging the whole hit-list, never by checking the files you expected to matter or a hand-picked candidate list.

---

## 13. Cite Vault Items by Stable Identifier, Not Line Number

When a skill writes a **durable artefact** — a report, review, session log, routed flag, or any note that will be re-read later — that references an item living in a churning planning file (a `This Week.md` task, a project-doc Next Action, a `Tickler.md` line, an open loop), name it by its **title / heading / content**, never by line number (`This Week.md L43`).

Line numbers rot the instant the file is edited — and several skills mutate a planning file *within the same run*, so any `Lnn` written after that point is stale on write. The canonical case: a purge of completed `[x]` lines from `This Week.md` shifts every line below; a report generated later in the same run that cites `This Week.md L43` already points at the wrong line. The durable artefact outlives the line-numbering; the title does not.

Ephemeral, in-conversation references during a single turn (e.g. a grep result you act on immediately) are exempt — this rule governs what gets **persisted**.

### Session-log links are file-level, never heading anchors

The rule above says cite by heading rather than line number. **Session logs are the exception**, because their headings are not stable identifiers: `write-session.sh` appends a `(hh:mmam/pm)` suffix that the linking side does not hold, so a `[[…/YYYY-MM-DD#Session N - Topic]]` anchor silently resolves to nothing. This defect was patched on individual artefacts twice before the convention was changed.

Link the **file** and name the session in plain text after it:

```
[[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session N)
```

Applies to every session-log reference a skill writes — continuation links, project-hub Session History rows, completed-item backlinks, Tickler routing links — and to session-log links written into vault docs outside a skill. Consumers key on the `[[06 Archive/Claude/Session Logs/` prefix, which is unchanged, and the plain-text session number carries what `/pickup` reads.

Heading anchors remain correct for **stable** docs (project hubs, guides, reference notes) where the heading is hand-written and durable.


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

⛔ **Bare URLs are rewritten too, and this one does not announce itself.** A normaliser matches inside a URL's path segments like any other text, so a link can be silently altered into one that 404s — which reads to a later reader as a *fabricated citation* rather than a formatting artefact. That makes it the highest-consequence case in this section and the one most likely to reach a research or reference note, where citations are the point. Two rules: wrap bare URLs in the same inline code span you'd use for any other protected token, and **verify after the write, not before** — the hook fires on every `Write`/`Edit`, so a link that was correct when composed can be wrong on disk. Checkable: after writing any note carrying citations, extract its URLs (`grep -o 'https\?://[^ )`]*' <file>`) and confirm each still matches the source. Which constructs a given normaliser leaves alone is an implementation detail that changes with its version — establish it empirically once (write a control file containing a known-rewritable token in each construct, then re-read it) and record the result in your project's own reference doc rather than assuming it here. The same applies to verbatim quotations in prose: backticks render them as code, so paraphrase the clause or exclude the whole doc by path instead.

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

**Names and speakers: the page's human-written text outranks the transcript body — per field.** The body wins on prose; it does **not** win on identity. A *published* transcript is frequently the publisher's own ASR, which garbles names phonetically and assigns speaker labels by voice-clustering guess: turns come out as `Unknown`, or get handed to whoever spoke last. The show notes, chapter list, resource links and pull-quotes on that same page are typed by a person. Each check below states the command **and** the observation that separates pass from fail — without the second half every one of them returns something plausible under both hypotheses and manufactures confidence.

**First, split `$BODY` into its two halves.** The extractor concatenates the human-written page text and the transcript body into one file, so "prefer A over B" is unusable until you know where A ends. Locate the boundary; everything below is scoped to one side or the other:
```bash
BOUND=$(grep -nE '^#{1,3} *(Transcript|Full [Tt]ranscript|Episode [Tt]ranscript)' "$BODY" | head -1 | cut -d: -f1)
if [ -z "$BOUND" ] || [ "$BOUND" -lt 3 ]; then echo "SPLIT FAILED (${BOUND:-no heading})"; else echo "boundary line: $BOUND"; fi
```
**⛔ `SPLIT FAILED` aborts the two checks below — do not run them.** This guard is the point: with `$BOUND` empty the slice commands error, but the errors are swallowed by their pipes and each check still emits a *plausible* result — an empty name set (which the rule reads as "the page never names them") and an empty timestamp scan (read as "no usable segment map"). A broken split therefore disguises itself as a legitimate finding *about the page*, which is the same confirmatory-only defect one level up. `BOUND < 3` catches the other direction: a nav link or a heading on line 1 matched first, which leaves the "human-written half" as a single heading line — and a degenerate range like `1,0p` may be accepted silently rather than erroring, so the guard cannot rely on the slice itself failing loudly (see the portability note above: `sed` behaviour here is implementation-dependent). On `SPLIT FAILED`, say the halves are unseparated and **flag** names rather than resolving them.

- **Provenance defaults to unverified, and only positive evidence upgrades it.** Absence of a disclaimer is not evidence of human editing — it is equally consistent with a differently-worded disclaimer, or one outside the selected container. So the header value starts at `published transcript (provenance unverified)` and moves to `(source-provided, auto-generated)` on a match, or to `(human-edited)` only where the page positively claims editing:
  ```bash
  sed -n "1,$((BOUND+8))p" "$BODY" | grep -niE 'automatically generated|auto-generated|AI-generated|machine.generated|may contain errors|transcribed by'
  ```
  **Scope it to the boundary region, not the whole body** — a disclaimer sits within a few lines of the transcript heading, whereas on an AI-topic episode those same phrases appear in the transcript as *subject matter* and would downgrade provenance on topical content. **Fail observation: zero matches ⇒ `provenance unverified`, never `human-edited`.** Never let the null select the stronger claim.
- **Names — compare the matched tokens, not the match count.** A stem grep is non-empty whether the two halves agree or diverge, so hit-count cannot detect garbling. Extract and diff the actual tokens, one side at a time:
  ```bash
  sed -n "1,$((BOUND-1))p" "$BODY" | grep -oiE '<stem>[a-z]*' | tr 'A-Z' 'a-z' | sort -u   # human-written half
  sed -n "$BOUND,\$p"      "$BODY" | grep -oiE '<stem>[a-z]*' | tr 'A-Z' 'a-z' | sort -u   # transcript half
  ```
  Use a **stem** (whole-surname matching fails — the garbling is phonetic). The `tr` is load-bearing: `grep -oiE` matches case-insensitively but prints the *original* case, so without it a name styled all-caps on one side and title-case on the other reads as divergence, and the runner "corrects" a spelling that was already right. Chapter lists and pull-quote attributions are commonly styled in caps, so this is the ordinary case, not an edge one. **Fail observation: the two lowercased token sets differ ⇒ the human-written half's spelling wins** (take its original-case form from the un-`tr`'d output). Identical sets means agreement, not that you skipped the check; an empty human-written set means the page never names them — then correct from your own knowledge or flag, never invent, and never report a name unresolvable that this comparison would have settled.
- **Speakers — find the timestamped chapter list, which is usually *not* headings.** The section outline the metadata block extracts is often navigational (`Show Notes`, `Resources`, `Transcript`), naming no participant and carrying no time; a page's real segment map is frequently bold prose or a plain list. Scan the human-written half for leading timestamps:
  ```bash
  # rg, not grep, deliberately. rg's -E is --encoding, so -n alone (extended syntax is rg's default).
  sed -n "1,$((BOUND-1))p" "$BODY" | rg -n '^[^a-z0-9]*\(?\**\[?[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?'
  ```
  The leading class is deliberately unbounded (`*`, not a `{0,4}` cap): a bullet-and-bold prefix like `- **(0:01)**` already spends four characters, so any capped bound is calibrated to one page's exact decoration and an indented or slightly heavier list silently stops matching.
  A turn whose timestamp falls inside a segment naming one participant is that participant, and the show-notes prose says who argued what. **Fail observation: no line carrying a leading timestamp ⇒ there is no usable segment map — fall back to conversational cues, and attribute nothing you cannot place.** A non-empty *outline* is not a usable map; the map must carry times.
- **Never edit the verbatim body to match** (per §14) — correct the header/synthesis and report the divergence.

⚠️ The word/leak gate above tests a fixed tag set, so inline tags outside it survive into `$BODY` — which matters here in a way it doesn't for verbatim appending, because a surviving tag run buries the divergence mid-line inside multi-thousand-character prose. Pipe through `sed -E 's/<[^>]+>//g'` when resolving identity, and count what actually survived — `grep -coE '<[a-z][^>]*>' "$BODY"` — since the gate itself can only ever report on the tags it enumerates. A non-zero count is the reason to widen that set for the next run.

**Fallback (no published transcript / JS-rendered):** machine-transcribe the audio/video instead — the WhisperX path (`/transcribe` locally, `/transcribecloud` on a cloud GPU). Much heavier; tell the user before launching a batch.

---

## 16. Out-of-Band Evidence in Reviewer Briefs

Canonical rule for every skill that despatches a brief to a reviewer that cannot see this session — `/park`'s audit sub-agent, `/audit`'s panel seats, `/second-opinion`'s reviewers, and any non-template skill that despatches a brief (e.g. a personal `/security-audit`). Those skills point here and carry no copy to drift.

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

### A never-opened citation is closed by opening it, not by declaring it

Where the work product cites a source the session never opened, **open it before despatch.** Declaring the gap in the brief does not neutralise it — it *aims* every seat at the same hole. Each reviewer then reasons from the same absent evidence to the same conclusion, and the synthesis reads that convergence as corroboration when it is a single artefact of your own brief. Adding seats cannot detect this, because the seats are the mechanism.

The cost is asymmetric. A claim gets challenged precisely where its support looks thinnest, so the source you skipped is disproportionately the one that would settle whatever the panel disputes. The unanimous verdict a disclosed gap produces is therefore not merely unsupported — it is the verdict most likely to be wrong, arriving with the most confidence behind it.

This is also a bar on the work product, not only on the brief: an artefact should not cite what it never opened. Repairing the citation list before review is far cheaper than adjudicating every seat's guess about it afterwards.

**Checkable:** every citation in the work product's reference list has a corresponding fetch or read in the session *before* the brief is written. Where a source genuinely cannot be opened, record the **failure mode** (dead link, paywall, auth wall, unparseable format) rather than the fact that it was untried — a tested failure is evidence a reviewer can reason from; an untried link is a gap that manufactures one.

### When a source is unrecoverable

If a source's text has left context (a long session, a `/compact` — and the first thing lost is the earliest fetch, which this rule identifies as disproportionately the originating source), **re-fetch it**. If it cannot be recovered, say so in the brief under the same heading — `<source> — text unavailable; do NOT flag claims traced to it as fabricated` — and **still count it in N**. Never paraphrase it from memory (that manufactures the fabricated-quote failure), and never drop it silently (that is the original failure, reproduced).

---

## 17. Push-Side Hub Record (commits are their own identifier class)

Canonical rule for every skill that runs a reference-graph / propagation pass after a session that pushed code — `/park` Step 6, `/goodnight` Step 15(a). Those skills point here and carry no copy to drift.

**The rule.** Every commit hash a session records is its own identifier. For each one, grep the vault for that repository's hub and confirm three things:

1. A `## Session History` row exists for the session that pushed it.
2. The hub's own `**Last update:**` / `Last updated:` stamp is current.
3. The project doc's current-state prose (`## Current Objective` / status line) reflects the push.

**Why the ordinary per-identifier pass misses it.** A pushed commit is a world-state change with no textual footprint in the vault. Nothing in the session's file edits contains the hash, so no content grep reaches the hub — and the hub is frequently a file the session never opened. The propagation pass therefore returns a clean, *fully earned* hit-list while the project's own commit-level record silently misses an entry. This is the inverse of the usual failure: not a stale value left behind, but a **new** record never written, in a document whose stated job is to hold it.

**Scope.** Applies to any repository with a hub in the vault, whether or not the session edited vault files for it. It applies equally when the commit was pushed by a skill's own bookkeeping (a skill-file fix committed during `/park` is still a push, and its hub row is still owed) — the rule is about the push, not about who initiated it.

**Checkable:** for each hash, one grep must return the repo's hub, and that hub must carry a row citing the pushing session. A propagation report that enumerates no commits on a session that pushed one has not run this check.

---

## 18. Deadline Tokens Force a Dated Surface

Canonical rule for every skill that routes open items to a destination — `/park` Step 7, `/goodnight` Step 9. Those skills point here and carry no copy to drift.

**The rule.** If an item's text contains a deadline, cut-off, expiry, renewal, or window-close token, its route MUST terminate in a **dated surface**: a specific day section when the date falls inside the rolling window, otherwise the Tickler (via `write-tickler.sh`).

**An undated destination does not discharge such an item**, however canonical that destination is. A project doc, an area hub, an undated notes list — each records *what* to do and never *when it stops being possible*. The undated branch of a routing table exists for items with genuinely no date; a deadline token means the item has one **even when it isn't written as a calendar date**. Derive it (`date -d`), don't route past it.

**The failure surface is caller-specific — name yours.** Each routing skill has a different undated sink, and the check must bind to that skill's own sink: for `/park` Step 7 the disallowed sinks are the project doc and Whimsy; for `/goodnight` Step 9 it is `→ Whimsy`. A caller adopting this rule states which of its destinations is the disallowed one, because "route to a dated surface" is unfalsifiable without naming what that excludes.

**Checkable:** any routed item whose text carries a deadline token must land under a dated heading, and the routing summary must name that dated target.

---

## 19. Value Provenance Check (SOURCE)

Canonical rule for every skill with a pre-audit quality gate over files it just wrote — `/park` Step 2(c) (the SOURCE check of its quality gate), `/goodnight` Step 14b. Those skills point here and carry no copy to drift; each supplies its own **scope** (which files it wrote this run) and runs the rule over them.

- Enumerate every specific value written into a file: number, date, quantity, duration, price, rate, capacity, identifier.
- Confirm each traces to one of: (a) something the user stated, (b) a tool result from this session, (c) an explicit uncertainty tag. A value tracing to none of these is fabricated — verify it, cut it, or tag it. "It sounds right" is not a source.
- **Derived values inherit the check.** A total computed from components, or two items presented as equivalent/substitutable, are unsourced unless the inputs *and the equivalence* were themselves checked. Plausible arithmetic over unverified inputs is the same defect as an invented figure.
  - **Unit conversions are derivations.** When a written value is a unit conversion of a tool-result number, recompute the conversion at the gate and match the divisor family to the unit label written — `GB`/`TB` are decimal (10⁹, 10¹²), `GiB`/`TiB` are binary (2³⁰, 2⁴⁰). A GiB value carrying a `GB` label passes the trace check (the byte count is real) while stating a wrong number.
- **Clock values must be read before they are written — two calls, ordered.** A timestamp, date, or "as of" stamp written into a file must come from a `date` result that appears in a **prior** tool result. Issuing `date` in the *same* tool call as the write does not satisfy this: by then the value is already composed, so what ships is an estimate and the `date` output merely documents how far off it was. This is the one value class that escapes the trace check above — the written stamp *does* correspond to a real tool call, so it reads as sourced while still being fabricated. Tell: a write whose stamp was chosen before its `date` output was visible. Applies to file-header stamps, `Last updated:` lines, banner refresh stamps, and provenance rows alike.
- **Asserted preconditions are values too.** A claim that *gates work* — "needs a restart first", "blocked until X is installed", "the key isn't visible yet" — is an unsourced factual claim, not a property of the task, and inherits the same trace requirement. It escapes the enumeration above because it reads as a precondition rather than a value, which is exactly why it survives: **premises are not challenged the way findings are.**
  - **Scope: preconditions naming a local machine or tooling observable** — an environment variable, a running process, a file or binary, a port, a reachable service, a credential. These are testable *by definition*, so testability is not a judgement call the asserting party gets to make.
  - **Out of scope, and not to be enumerated or tagged:** blockers resolved by a person, a third party, or an unmade decision ("waiting on the builder", "blocked on the lease call"). Tagging those is noise, and they are the overwhelming majority of blocker-shaped text in ordinary planning docs.
  - In scope → run the read-only command and cite its output, or tag `[unverified]`. **If the command falsifies the blocker, correct the document** — a cited probe sitting beside an uncorrected precondition is the defect, not the fix.
  - **Tag placement:** in a dated or archival surface (a session log), `[unverified]` is fine. In a living hub or planning doc, cut the claim or rewrite it as an open question — an untagged expiry date is how a tag rots into a permanent shrug.
- **Required output:** `Value check: N values traced, M unsourced (fixed); P preconditions asserted, Q verified` — or `Value check: no specific values written this session` (append `; no preconditions asserted` when that half is also nil).

Distinct from §16 (out-of-band evidence in reviewer briefs), which governs *supplying* sources to a reviewer; this one governs whether a value written into a file had a source at all.

---

## 20. Session-Boundary Attribution (the file list is the boundary, not the commit window)

Canonical rule for every skill that delegates an audit over "the files this session touched" — `/park` Step 9, `/goodnight` Step 15(c). Those skills point here and carry no copy to drift; each supplies its own embedded file list.

**The rule.** The vault's `.git` is an **auto-save** repo: commits are time-window snapshots, not session boundaries, and concurrent sessions write to the same vault. A file appearing in the same commit as a session's bookkeeping is therefore **not** evidence that session produced it.

Attribute work **only** from the file list embedded in the brief. A changed file that is not on that list belongs to a concurrent session: surface it as an observation, and never

- add it to `Files Created` / `Files Updated`,
- open a `Next Steps` loop or `Pickup Context` thread for it, or
- write a Session History row for it in another project's hub.

**Partial application is the failure mode.** Applying the test to some files in a commit and not others produces a confident, internally consistent record of work the session did not do — which is harder to detect than an obvious error, because every individual claim reads as plausible and the record is self-consistent. When unsure whether a file is in scope, say so in the report rather than deciding.

**Checkable:** every file the auditor writes into a session record appears in the brief's embedded file list. One that doesn't is misattribution, whatever the commit history shows.

Caught 2026-07-19: an audit sub-agent correctly excluded two files from a commit window as concurrent work, then attributed a 194-line project file from the *same* window to the session, and wrote four separate false records off the back of it — a Files Created entry, an open loop, a Pickup Context thread, and a Session History row in an unrelated project hub.

The read-side sibling is `_shared-patterns.md`'s *Auto-save git is not pre-state*: that one governs using auto-save history to reconstruct what a file looked like before; this one governs using it to decide who did what.

---

## 21. Concurrent-Safe Git Staging (never stage broadly)

Canonical rule for every skill that commits to a git repository, and for ad-hoc commits made during a session. Applies wherever more than one Claude session may touch the same working tree.

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

Canonical rule for every skill that despatches a review to a reviewer whose tool calls you cannot see — panel seats, delegated audit sub-agents, any brief sent to a separate context. Those skills point here and carry no copy to drift. §16 governs what evidence *you* must put **into** a brief; this section governs what evidence the reviewer must return **out** of one.

**The rule.** A reviewer's working is invisible to you, so a review is evidence only to the extent it attests where its claims came from. Require the attestation in the brief's output-format section, and enforce it on receipt. The artefact differs by what the seat can reach; the standard does not:

| Seat can reach | Required attestation |
|---|---|
| The filesystem | The list of files it read |
| A shell | For each command-backed claim: the exact command and the quoted output |
| The network | For each fetched-source claim: the URL and the quoted passage |
| Nothing (sources inlined into its prompt) | The source manifest reproduced verbatim, **and** the passages it relied on |

A seat owes every row its reach covers, not one of them. **Paste this table into the brief body — do not point the reviewer at this file.** A reviewer's workspace is the audit target, which is rarely the directory holding these rules, so a bare cross-reference is an instruction it cannot follow, and discarding it on receipt then punishes a competent review for a rule it never saw.

**Enforcement.** A review attesting nothing is brief-echo, not independent judgement — discard it and say so in the synthesis rather than quietly running an N-1 panel labelled as N. Partial attestation is not discarded wholesale: the unattested claims are reported as unverified and never promoted to findings on the reviewer's say-so. Where a row requires two artefacts, missing either fails that claim; the test is not "neither was supplied".

**Attestation is a locator, not a proof — spot-check before promoting.** A citation is as forgeable as the claim it supports, so an unchecked URL-and-quote does not merely fail to help, it actively inverts the ranking below: a fabricated primary source outranks an honest "from recall". Before promoting any fetched-source or command-backed finding that changes what you do, verify it yourself — open the URL and match the quote, or re-run the command. If you cannot, carry the finding as `[unverified]` at its unattested rank. The attestation's job is to make the check cheap and targeted, not to substitute for it.

**Do not solve the invisibility problem by cutting off the reach.** A seat that can search will sometimes locate the primary source you did not know to put in the brief, which is precisely the discovery a fixed evidence block cannot supply and the reason an independent seat is worth its cost. Removing the capability removes the upside along with the risk. Attestation keeps both: the seat may go looking, and you can see what it came back with.

**Evidence class is the tiebreak, and it outranks seat count.** Rank a finding by what backs it: a command the reviewer ran, then a primary source it quoted, then a secondary source, then unattested assertion. A lone finding carrying a quoted primary source outranks a majority reasoning from recall, and on a question of how a tool actually behaves, the seat that ran the command or read the source wins regardless of how many disagree. Correlated agreement is weak evidence to begin with (models share priors); agreement with nothing behind it is none. This is what makes attestation load-bearing rather than bookkeeping — without it the classes are indistinguishable, and a confident guess reads exactly like a verified fact.

**Checkable:** every brief a skill despatches names the required attestation for the seats it is despatching to, and every finding carried into a synthesis is traceable to a read, a manifest entry, a command, or a citation.

---

## 24. Driving the Obsidian CLI (link-healing moves, batches, verification)

Canonical rule and **single source of truth** for every skill that moves, renames, or deletes vault files through the `obsidian` CLI — `quarterly-hygiene` Step 6, `complete-project` Step 4, `inbox-processor` Step 4. Those skills point here and carry no copy to drift. The procedure below was last exercised end-to-end against **Obsidian 1.13.4** (link-healing move, async settle, verify-by-result); the older behaviour notes date from **1.12.7** and not every one has been re-tested since. Treat the version stamp as a staleness marker, not a guarantee, and re-verify rather than trusting it indefinitely.

**The durable rule, independent of any tool version.** A path-qualified wikilink (`[[folder/note]]`) does not survive the file moving unless something rewrites it. Only a link-aware move does that, so raw `mv` on a linked note is never correct — not as a fallback, not for a batch, not "just this once". Where a link-aware move is unavailable, **move nothing and defer**: relocating files and orphaning their links is worse than not running.

**Do not rely on basename fallback to cover a raw `mv`.** Two independent reasons, and the second holds regardless of resolver behaviour: a path-qualified link is a path, not a name; and vault filenames are far less unique than they look — date-keyed conventions (`YYYY-MM-DD.md`) collide exactly across folders, so a bare-name resolution can bind a different note entirely. Any skill claiming a "globally unique basename" exception is asserting something the vault's own naming conventions contradict.

**Current CLI behaviour (the volatile half — this is the only place it is stated).**

- It drives the **already-running app**; it does not boot an instance per call. So a batch is fine, and it is fast. It also heals inbound wikilinks including `#heading` anchors.
- **It requires the app to be running.** With no app, calls silently do nothing and every item appears to fail. Probe before writing anything (`obsidian version`), and treat a whole-batch failure as the app being down rather than a per-file problem.
- **It reads stdin.** Inside a `while read` loop it swallows the loop's input, so only the first item is processed while the run still looks successful. Pass `</dev/null` on every call.
- **⛔ Derive the invocation form before the first write call of a batch — from the CLI's own help subcommand, never from memory.** Argument *style* is version-volatile (positional vs named), and getting it wrong is not a loud failure: a mis-formed call can print a usage string, change nothing, and still exit 0. Ask the tool: `<cli> help <subcommand>` returns the parameter list. Two traps to avoid on the way there — the `--help` **flag** is not the same route and a subcommand may ignore it and simply execute; and **never probe syntax by running the bare or deliberately-incomplete command**, because a destructive subcommand with no explicit target may default to one (the active file, the current directory) and act on it. Then confirm the form against your vault's CLI-reliability reference (below) rather than assuming it matches the last version you used.
- **Operations apply asynchronously and the exit status is unreliable in both directions.** It can be non-zero on success; it is also **zero when the call did nothing at all**. So a skill keying on exit codes can report a clean batch having moved not one file. Verify by **result** — the file's presence at source *and* destination — after a settle delay of a couple of seconds. Never key on the exit code or an immediate `test`. Re-verify an apparent failure after a further delay before retrying.
- **Run the first item of a structural batch as a canary.** Verify it by result before issuing the rest. This is what converts a version-drift surprise from a half-applied batch into one failed call, and it is the only cheap defence against the exit-0-did-nothing mode above.
- **The per-subcommand specifics — which subcommands work, their current argument style, their known silent failures — live in your vault's CLI-reliability reference, not here.** That table is versioned and rechecked per subcommand; this section carries only the durable procedure. Read it before a structural batch, and add a dated row when you learn something new. Same reasoning as the backlinks rule below: what a given CLI version does changes under you, so it needs one canonical, updatable home rather than a copy inside every skill.
- **Graph queries (`unresolved`, `backlinks`) return empty or stale while the app reindexes. Empty is not zero** — re-query once the index settles rather than reading a blank result as a pass.
- **⛔ Before gating a destructive action on a backlinks result, check that the route is one your vault's search-routing doc marks reliable.** A settled index is not sufficient: a subcommand can return false *negatives* — a confident "no inbound links" for a file that has them — in which case waiting for the index changes nothing. **Treat a nil from an unverified route as *unknown*, not as zero**, and never let it authorise a raw `mv` or a delete. This is the specific failure this section exists to prevent, and it is the reason the reliability verdict lives in the routing doc rather than here: which route is trustworthy changes with the app and plugin versions, so it must have one canonical, updatable home.
- **Link healing writes the copies of a duplicated file non-atomically.** If a batch is resolving duplicate pairs and each move heals links inside files *later* in the batch, a byte-compare of a still-unresolved pair can catch one copy mid-rewrite and report a difference that is not real. So **re-verify a refusal or skip after a delay before treating it as genuine**, exactly as for an apparent failure. A compare-before-delete guard is still correct: its failure mode is a false skip, never a false delete.

**Verification, and it must produce numbers.** Take the vault's unresolved-link count before the batch and again after; a link-preserving move must not increase it. Then confirm no moved item appears as an unresolved target. A skill that reports no numbers has verified nothing.

**Structural moves need the sync client ON.** Moves made while a vault's sync client is off never reach the remote, so the remote keeps the pre-move tree; the next merge-on-reconnect pushes it back down and **resurrects a copy of everything just moved**. The resurrection is silent, and because the resurrected copies absorb the inbound links, nothing looks broken while duplication accumulates. This is not shell-checkable — confirm with the user before a structural batch, and record which way it went.

**Checkable:** no skill executes a raw `mv` on a linked vault note, no skill keys a move's success on the CLI's exit status, every CLI call inside a loop carries `</dev/null`, and every structural batch reports a before/after unresolved-link count. A skill restating this section's CLI behaviour instead of pointing at it is the drift this section exists to prevent.

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

Canonical fetch order for any skill that needs a web page's content from a known URL. Ordered so the free, exact-bytes route comes first and credit-metered scrapers last — a metered scraper as the default rung burns quota on pages plain `curl` handles, and its quota exhaustion then breaks every skill that leads with it.

1. **§15 static extractor** (`curl` + `bs4` + `pandoc`) — first rung for any article/transcript-shaped page. Free, and it leaves the exact source bytes on disk, which quote-fidelity checks require. Its word-count gate is the self-diagnosis: a body far short of the visible article means a JS-rendered page — climb to rung 2 rather than iterating selectors indefinitely.
2. **Configured fetch MCPs** — whichever reader/scraper servers the install has (reader APIs, scrapers with JS rendering or anti-bot proxies). ⛔ **A credits/quota/plan-limit error is unavailability, not failure:** move down the ladder without retrying, stalling the run, or asking the user to top up mid-task. Reader APIs can manufacture phantom pagination on static pages (§15) — that is why this is rung 2, not 1. Anti-bot-blocked pages (403/429/Cloudflare) are the one case to *start* here: rung 1's plain `curl` is refused identically.
3. **WebFetch** — last rung. It answers a prompt through a summarising model rather than returning the page, so it serves metadata and gist but never verbatim quotation; a skill with a fidelity requirement that ends up here records the gap instead of quoting.

Search-shaped needs (no known URL) are a different tool class — the WebSearch tool or a configured search MCP — with the same quota-is-unavailability rule for metered ones. Where a skill records provenance for the fetched body, name the rung that produced it.
