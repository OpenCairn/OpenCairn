---
name: pickup
description: Resume previous work — pass a topic, keyword, or file path to jump straight in
argument-hint: "[topic, keyword, or file path — optional; bare /pickup shows active projects]"
---

# Pickup - Session Pickup

You are helping the user resume previous work with full context.

## Instructions

1. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   "$VAULT_PATH/.claude/scripts/check-archive-layout.sh" --enforce "$VAULT_PATH"
   ```

   If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

2. **Check current date** using bash `date` command.

3. **Route based on arguments:**

   - **Arguments provided** (topic, keyword, or file path) → Step 4 (targeted pickup)
   - **Bare `/pickup`** with no arguments → Step 6 (project overview)

---

### Targeted Pickup (arguments provided)

4. **Find relevant context:**

   The user gave you a topic, keyword, or file path. Find the relevant session and project context using your normal search tools (Grep, Glob, Read).

   - **Run the scan script** to get recent session metadata cheaply, filtering inside the command so only matching rows come back:
     ```bash
     "{VAULT}/.claude/scripts/pickup-scan.sh" --days=30 | rg -i -- 'TOPIC'
     ```
     Substitute the user's keyword for `TOPIC`. The TSV columns are `DATE, SESSION_NUM, TITLE, TIME, PROJECT, LOOP_COUNT, SUMMARY` (seven — match columns by name, not position); the filter matches against TITLE, PROJECT, and SUMMARY alike. If no matches, extend to `--days=90`; if the topic is likely older still, `--days=365` — archived logs in `Session Logs/YYYY/` subfolders are only reachable when the day window covers them. **Keep the filter in the pipeline every time you widen the window.** Unfiltered output is sorted newest-first and grows fast enough to be truncated, which cuts exactly the older rows the wider window exists to reach. If output is ever truncated or spilled to a file, re-run with the filter (or a tighter one) rather than reading the preview. **If the script errors** (no session directory yet on a fresh vault; stock macOS bash 3.2 — the script needs bash 4.2+), treat it as "no session metadata yet" and continue with the vault search below; mention `brew install bash` to macOS users for future scans.

   - **Search the vault** for matching project hubs (`03 Projects/`, `03 Projects/Cold/`, `03 Projects/Backlog/`) and area files as needed.

   - **Follow CLAUDE.md's context routing table** for domain-specific context files. If the vault-root CLAUDE.md is absent or has no routing table, follow the user's explicit target link and load its project/area hub plus directly related context notes.

   Use judgement about what's relevant. Don't over-load — read what the user needs to get back into the work.

5. **Load and present:**

   From whatever you found, read:
   - The most recent matching session section — the scan script's DATE column (e.g. `2026-03-30`) maps to `{VAULT}/06 Archive/OpenCairn/Session Logs/YYYY-MM-DD.md`, or `{VAULT}/06 Archive/OpenCairn/Session Logs/YYYY/YYYY-MM-DD.md` if that date has been archived into a year subfolder (logs >90 days old; `pickup-scan.sh` finds them via `-maxdepth 2`). SESSION_NUM tells you which `## Session N` block to read. Go straight there; don't re-search. The year-subfolder form is an archival **read** path only: if `/park` or `/goodnight` follows, today's new entry still goes directly in `Session Logs/YYYY-MM-DD.md`; never carry this loaded path forward as the write target.
   - The project hub file if one exists
   - Relevant context files per the routing rule above

   Present concisely:

   ```
   Picked up: [Topic/Project Name]

   Last session: [Title] ([date])
   [1-2 sentence summary]

   Open loops:
   - Item 1
   - Item 2

   Loaded: [list of context files read]

   Ready to continue. What's next?
   ```

   Skip sections that don't apply (no "Open loops" if there are none). → Done.

---

### Project Overview (bare /pickup)

6. **Read the project-doc root:**

   - List `{VAULT}/03 Projects/*.md` (root only — root = active; folder location is status). For each doc, read its `bucket:` frontmatter and the first line under `## Current Objective`.
   - Count `Cold/` and `Backlog/` docs for the collapsed line — only tiers that exist.

7. **Display a numbered project list**, grouped by bucket, with Current Objective one-liners:

   ```
   Active projects (03 Projects root):

     Craft
     1. Project Alpha        — [Current Objective one-liner]
     2. Research Topic       — [Current Objective one-liner]

     Community
     3. Side Project with Sam — [Current Objective one-liner]

     + 2 cold, 15 backlog (say "show all" or name one)

   Pick a number, or tell me what you want to work on.
   ```

   - Bucket order: per the vault's bucket taxonomy (Project Doc Format in `07 System/Vault Organisation Principles.md`) — group by `bucket:` value, skip empty buckets; docs with no `bucket:` go last under "(no bucket)"
   - Truncate Current Objective lines to one glanceable clause; never synthesise one for a doc that lacks the section — leave the slot blank
   - If the `03 Projects/` root is empty, suggest starting fresh (`/start-project`) or running `/awaken`

8. **Wait for user response:**

   - **Number** → Follow the project doc directly: read it in full (Current Objective, Next Actions, Current Status), then read the newest session link found in it — its `## Session History` wikilinks (`[[06 Archive/OpenCairn/Session Logs/...]]`), or via `pickup-scan.sh` filtered on the project name if the doc carries none — and load relevant context files per the routing rule above. Present as in Step 5.
   - **"show all"** → Redisplay including `Cold/` and `Backlog/` docs (grouped under their tier headings)
   - **Topic/keyword** → Treat as targeted pickup (Step 4)
   - **Anything else** → Respond naturally

## Guidelines

- **Speed over completeness.** Load only what's needed, not everything that exists.
- **No complex interactive menus.** No hide, snooze, pagination, multi-step view toggles. "Show all" is the only expansion permitted.
- **Session logs are read on demand.** The scan script extracts metadata cheaply for targeted pickup. Only read full session files when the user has selected a specific project or topic.
- **The project-doc root is the orientation layer.** Bare `/pickup` shows what's in flight, not session history. Sessions are implementation details; projects are the unit you pick up.
- **Folder location is status:** `03 Projects/` root = active, `Cold/` = paused, `Backlog/` = backlog. Check all three when a name doesn't turn up.
- **Trust your search tools.** Don't over-prescribe search strategies. Use Grep, Glob, and the scan script as appropriate for what the user asked.

## Integration

Combined with `/park`, this forms the **park and pickup system**.

**Reads from:** 03 Projects root docs (bare mode), Session Logs (via pickup-scan.sh for targeted pickup, direct read for selected topic), Project hubs, Context files
