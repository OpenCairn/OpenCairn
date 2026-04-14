# Shared Rules

Operational rules referenced by multiple commands. Commands load this file in Step 0 after vault path resolution:

> Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill.

This prevents rule divergence across 30+ command files. Change a rule once here — all commands follow it.

---

## 1. Vault Path Post-Check

After running `resolve-vault.sh`, if it errors: **abort — no vault accessible.** Do NOT silently fall back to `~/Files` without an active failover symlink — that copy may be stale.

**Use the resolved path for all file operations.** Code examples in commands use `{VAULT}` as a placeholder — substitute the resolved vault path before executing. Do NOT use `{VAULT}` in Bash tool calls — shell state does not persist between calls, so the variable will be empty.

---

## 2. Project Linking Rules

When a session or task links to a project context:

- **Finite work (in flight)** → link to `03 Projects/[name].md` (or `03 Projects/Backlog/[name].md`)
- **Ongoing area work** → link to `04 Areas/[path]/[name].md`
- **Shipped one-shot work** (published blog post, completed migration, resolved bug, anything finite that's now done with no ongoing tracking need) → link to an *existing* area hub that naturally groups related work. **Do not create a new project file, and do not create a WIP entry.** The "finite work → project file" rule above is calibrated for in-flight finite work where a project file earns its cost by hosting the task queue; once the work ships, the task queue is empty and creating a project file (or WIP entry) retroactively is noise. Example: a published post on your blog links to `[[04 Areas/Blog/Blog]]`, not a newly-created post-specific project file.
- **Never link to:** WIP sections (`01 Now/Works in Progress#...`), Resources, or Archive
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

**Why dedicated scripts instead of inline flock:** Claude Code's permission system saves the entire bash command as a permission pattern in `settings.local.json`. Multi-kilobyte session summaries inside flock commands bloat the settings file. The scripts (`write-session.sh`, `add-forward-link.sh`, `write-tickler.sh`, `update-session-section.sh`, `backfill-files-updated.sh`) receive content via stdin or arguments — the permission system only stores the short script invocation, not the payload.

**Lock files:**

| Lock file | Protects | Used by |
|-----------|----------|---------|
| `06 Archive/Claude/Session Logs/.lock` | Session file reads/writes | write-session.sh, add-forward-link.sh, goodnight session edits |
| `07 System/.provenance-lock` | Provenance log writes | All provenance operations |

**Lock ordering:** When both locks are needed, always acquire the session lock first, release it, then acquire the provenance lock. Never hold both simultaneously.

## Failure modes for in-place file edits

Three distinct failure modes can trip up file edits during a skill's execution. Each has a different root cause and a different remediation. **Diagnose before treating.**

### Failure mode A: Edit tool refuses with "modified since read"

Symptom: `Edit` tool returns "File has been modified since read, either by the user or by a linter." even after a fresh `Read`.

Likely causes (in decreasing probability):
1. A PostToolUse hook (e.g. britfix) fired on a prior write and advanced mtime between this Read and Edit
2. A parallel Claude session is editing the same file
3. Syncthing bidirectional sync with the NAS mirror advanced mtime
4. An Obsidian background process touched the file

**Diagnostic:** `stat -c '%y' "$file"` immediately before the Read and immediately before the Edit. If mtime advances between them with no intervening write from this session, an external process is touching the file.

**Remediation:** Don't loop-retry the Edit tool. Fall back to an atomic Python rewrite with `fcntl.flock(LOCK_EX)` on the target file:

```python
import fcntl
path = "/absolute/path/to/file.md"
with open(path, 'r+', encoding='utf-8') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    content = f.read()
    # ... modify content via str.replace(old, new, 1) / re.sub() ...
    f.seek(0)
    f.truncate()
    f.write(content)
```

The Python fallback works for this failure mode because it skips the Edit tool's mtime freshness check entirely and performs an atomic read-modify-write under a kernel-level exclusive lock on the target file.

### Failure mode B: Session-management script times out on its lock

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
- **Use Python+flock only after killing the hung scripts**, and only when a dedicated script would be the normal path. For ad-hoc edits with no dedicated script (e.g. WIP mid-park), Python+flock is the primary tool regardless.

### Failure mode C: Bash tool backgrounds a command that finishes normally

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

### Section-targeted append patterns (when scripts are unavailable)

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
awk 'f && /^### /{exit} index($0, "### HEADING_TEXT") == 1 {f=1} f' "{VAULT}/01 Now/Works in Progress.md" | grep -c '^→ \[\[06 Archive/Claude/Session Logs/'
```
Display: `FIFO check: N/3 session links`. If more than 3, fix before proceeding.

---

## 7. Timezone and Date Handling

- **Always check current date/time** via the `date` command at the start of every command. Never assume, cache, or reuse timestamps from prior tool calls.
- **Use system timezone** (local time wherever the user is). During travel, sessions are dated in local context (Tokyo → JST, Denver → MST). This is intentional — local time is more meaningful than forcing the home timezone.
- **Verify date-to-weekday mappings** with `date -d`. LLMs are unreliable at mapping dates to days of the week. When writing "Mon 15 Feb" or similar, always run `date -d "2026-02-15" +%A` in bash first.

---

## 8. Skill Monitor

When executing any slash command, also follow the instructions in `.claude/commands/_skill-monitor.md`. Watch for gaps in the command's logic. If you improvise a step that isn't documented, if a mistake could have been caught by a better checklist item, or if a documented step turns out unnecessary — note it and propose edits at the end.

---

## 9. This Week.md Rolling Window Maintenance

This procedure keeps the rolling 7-day window current. It runs during `/morning` (step 6) and `/goodnight` (step 11). If This Week.md doesn't exist, skip entirely.

### Trim old day sections

Delete any day sections whose date is more than 3 calendar days before today. Past days are already archived in Daily Reports — keeping them past 3 days adds clutter without value.

1. Parse each `## ` heading for a date (e.g. `## ☀️ Fri 6 Mar` → 6 Mar, `## Mon 9 Mar` → 9 Mar). Skip headings that aren't day sections (e.g. `## Refs`).
2. For each day section, compute: `today_date - section_date`. If > 3 calendar days, delete the heading and all content until the next `## ` heading.
3. Keep the 3 most recent past days for quick reference. Today and future days are never trimmed.

### Extend the window

Ensure day sections exist for today + 6 calendar days ahead (7 total including today). Rolling window: 3 past + today + 6 future = 10 sections max.

1. Run `date -d "+N days" +"%A %d %b"` for each missing day (N = 1 to 6)
2. Add new day sections after the last existing day, before `---` / Refs / other trailing sections
3. Remove day sections beyond the 6-day window (heading + content until next `## ` heading)
4. Format for days with no content: `## [Day] [DD] [Mon]` — just the heading
5. Update the file heading date range: set start date to the earliest remaining day section, end date to the latest

### Populate new days from Tickler

For each newly created day section, convert to YYYY-MM-DD format and check Tickler.md for a matching `## YYYY-MM-DD` date header. Move any unchecked items from that Tickler section into the new day section and delete from Tickler (per Tickler SSOT Transfer rules in Section 4).

### Update the heading

Update `# This Week — [start] – [new end] [YYYY]` to match the actual date range.
