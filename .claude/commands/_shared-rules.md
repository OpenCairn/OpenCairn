# Shared Rules

Operational rules referenced by multiple commands. Commands load this file in Step 0 after vault path resolution:

> Read `.claude/commands/_shared-rules.md` and apply its rules throughout this command.

This prevents rule divergence across 30+ command files. Change a rule once here — all commands follow it.

---

## 1. Vault Path Post-Check

After running `resolve-vault.sh`, if it errors: **abort — no vault accessible.** Do NOT silently fall back to `~/Files` without an active failover symlink — that copy may be stale.

**Use the resolved path for all file operations.** Code examples in commands use `{VAULT}` as a placeholder — substitute the resolved vault path before executing. Do NOT use `{VAULT}` in Bash tool calls — shell state does not persist between calls, so the variable will be empty.

---

## 2. Project Linking Rules

When a session or task links to a project context:

- **Finite work** → link to `03 Projects/[name].md` (or `03 Projects/Backlog/[name].md`)
- **Ongoing area work** → link to `04 Areas/[path]/[name].md`
- **Never link to:** WIP sections (`01 Now/Works in Progress#...`), Resources, or Archive
- **No canonical home?** Create a project or area file rather than linking to WIP
- **Working in Resources?** That's a signal it should graduate to an Area
- **Why:** WIP is for status tracking, not session clustering. Consistent project links enable reliable pickup grouping.

---

## 3. Item Linking Convention

Every actionable item in a day section, Backlog, or planning document should link to its project/area context where one exists:

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
- **Deduplicate against Backlog:** After migrating each Tickler item, check whether a matching item already exists in the Backlog section of This Week.md (same task, possibly different phrasing). If so, delete the Backlog copy — the day section is now SSOT.

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

---

## 6. WIP Session Link FIFO Cap

When adding session links (`→ [[06 Archive/Claude/Session Logs/...]]`) to a WIP entry:

1. Add the new link
2. Count standalone session link lines (lines matching `→ [[06 Archive/Claude/Session Logs/`) in this WIP entry
3. If more than 2, remove the oldest by date until exactly 2 remain
4. **Do NOT trim non-session-log reference links** (`→ [[03 Projects/`, `→ [[04 Areas/`, etc.) — these are navigation pointers

Session history lives in the archive and project hub pages; WIP links are convenience pointers, not the record of truth.

**Mechanical verification (required after every WIP edit):**
```bash
# Extract the WIP entry for this project and count session links
# Substitute the heading text (e.g. "Claude Code Learning / OpenCairn")
# Uses awk index() for fixed-string matching (headings often contain / and &)
awk 'f && /^### /{exit} index($0, "### HEADING_TEXT") == 1 {f=1} f' "{VAULT}/01 Now/Works in Progress.md" | grep -c '^→ \[\[06 Archive/Claude/Session Logs/'
```
Display: `FIFO check: N/2 session links`. If more than 2, fix before proceeding.

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

1. Parse each `## ` heading for a date (e.g. `## ☀️ Fri 6 Mar` → 6 Mar, `## Mon 9 Mar` → 9 Mar). Skip headings that aren't day sections (e.g. `## Refs`, `## Backlog`).
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
