---
name: pickup
aliases: [resume, restore]
description: Resume previous work — pass a topic, keyword, or file path to jump straight in
parameters:
  - "$ARGUMENTS" - Topic, keyword, or file path to pick up (optional — bare /pickup shows recent sessions)
---

# Pickup - Session Pickup

You are helping the user resume previous work with full context.

## Instructions

1. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

2. **Check current date** using bash `date` command.

3. **Route based on arguments:**

   - **Arguments provided** (topic, keyword, or file path) → Step 4 (targeted pickup)
   - **Bare `/pickup`** with no arguments → Step 6 (recent sessions list)

---

### Targeted Pickup (arguments provided)

4. **Find relevant context:**

   The user gave you a topic, keyword, or file path. Find the relevant session and project context using your normal search tools (Grep, Glob, Read).

   - **Run the scan script** to get recent session metadata cheaply:
     ```bash
     "{VAULT}/.claude/scripts/pickup-scan.sh" --days=30
     ```
     Filter the TSV output for lines where TITLE, PROJECT, or SUMMARY match the user's input (case-insensitive). If no matches, extend to `--days=90`.

   - **Search the vault** for matching project hubs (`03 Projects/`, `03 Projects/Backlog/`), WIP entries, and area files as needed.

   - **Follow CLAUDE.md's context routing table** for domain-specific context files (e.g. travel topic → load travel context files).

   Use judgement about what's relevant. Don't over-load — read what the user needs to get back into the work.

5. **Load and present:**

   From whatever you found, read:
   - The most recent matching session section — the scan script's DATE column (e.g. `2026-03-30`) maps directly to `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`, and SESSION_NUM tells you which `## Session N` block to read. Go straight there; don't re-search.
   - The project hub file if one exists
   - Relevant context files per CLAUDE.md routing table

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

### Recent Sessions List (bare /pickup)

6. **Scan recent sessions:**

   ```bash
   "{VAULT}/.claude/scripts/pickup-scan.sh" --days=7
   ```

   If no results, extend to `--days=30`. If still nothing, say so and suggest starting fresh or running `/awaken` if it's been a long break.

7. **Display a simple list:**

   Show the most recent 10-15 sessions, grouped by date:

   ```
   Recent sessions (last 7 days):

   Today
     1. Session Title                        10:30am  | Project Name
     2. Another Session                       8:15am  | Loops: 2

   Yesterday
     3. Evening Work                          9:20pm  | Project Name
     4. Morning Check-in                      7:00am

   Fri 28 Mar
     5. Deep Research Session                 2:15pm  | Project Name | Loops: 1

   Pick a number, or tell me what you want to work on.
   ```

   - Show loop count only when > 0
   - Show project name when present
   - Most recent first within each day

8. **Wait for user response:**

   - **Number** → Load that session (read the full session section, plus project hub and context files as in Step 5)
   - **Topic/keyword** → Treat as targeted pickup (Step 4)
   - **Anything else** → Respond naturally

## Guidelines

- **Speed over completeness.** Load only what's needed, not everything that exists.
- **No interactive menus.** No hide, snooze, pagination, view toggles. Find and load.
- **Session logs are read on demand.** The scan script extracts metadata cheaply. Only read full session files when the user has selected one.
- **Open loops are historical.** Session log loops are a snapshot from when `/park` ran. Current task state lives in This Week.md and project hubs.
- **Project hubs live in two places:** `03 Projects/` (active) and `03 Projects/Backlog/` (backlog). Check both.
- **Trust your search tools.** Don't over-prescribe search strategies. Use Grep, Glob, and the scan script as appropriate for what the user asked.

## Integration

Combined with `/park`, this forms the **park and pickup system**.

**Reads from:** Session Logs (via pickup-scan.sh for metadata, direct read for selected session), Works in Progress, Project hubs, Context files
