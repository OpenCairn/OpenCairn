---
name: pickup
aliases: [resume, restore]
description: Resume previous work — pass a topic, keyword, or file path to jump straight in
parameters:
  - "$ARGUMENTS" - Topic, keyword, or file path to pick up (optional — bare /pickup shows WIPs)
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
   - **Bare `/pickup`** with no arguments → Step 6 (WIP overview)

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

### Works in Progress Overview (bare /pickup)

6. **Read Works in Progress:**

   Read `{VAULT}/01 Now/Works in Progress.md`. Parse each `###` entry, extracting:
   - **Name** (the heading text)
   - **Status** (from the `**Status:**` line — abbreviate to one word if verbose)
   - **Last touched** (date from the `**Last:**` line, if present)

   Show only the **top section** (entries above `## Active`) and the **Active section**. These are the things worth picking up. Collapse Maintenance and Backlog into counts.

7. **Display a numbered WIP list:**

   ```
   Works in Progress:

     1. Project Alpha                          Active    | Last: Sun 29 Mar
     2. Tax 2025-26                            Active    | Last: Thu 26 Mar
     3. Travel 2026                            Active    | Last: Mon 30 Mar

     Active
     4. Side Project with Sam                  Active    | Last: Sat 28 Mar
     5. Research Topic                         Exploring | Last: Mon 30 Mar
     6. Job Application                        Submitted | Last: Sat 28 Mar

     + 2 maintenance, 15 backlog (say "show all" or name one)

   Pick a number, or tell me what you want to work on.
   ```

   - Preserve section grouping (top items, then Active heading)
   - Omit "Last" column for entries with no `**Last:**` line
   - If WIP file is empty or missing, suggest starting fresh or running `/awaken`

8. **Wait for user response:**

   - **Number** → Load that WIP's context: follow the first `[[03 Projects/...]]` link in `**Next:**` to read the project hub, read the most recent session log linked in `**Next:**`, and load relevant context files per CLAUDE.md routing table. Present as in Step 5.
   - **"show all"** → Redisplay with Maintenance and Backlog entries included
   - **Topic/keyword** → Treat as targeted pickup (Step 4)
   - **Anything else** → Respond naturally

## Guidelines

- **Speed over completeness.** Load only what's needed, not everything that exists.
- **No interactive menus.** No hide, snooze, pagination, view toggles. Find and load.
- **Session logs are read on demand.** The scan script extracts metadata cheaply for targeted pickup. Only read full session files when the user has selected a specific WIP or topic.
- **WIP is the orientation layer.** Bare `/pickup` shows what's in flight, not session history. Sessions are implementation details; WIPs are the unit you pick up.
- **Project hubs live in two places:** `03 Projects/` (active) and `03 Projects/Backlog/` (backlog). Check both.
- **Trust your search tools.** Don't over-prescribe search strategies. Use Grep, Glob, and the scan script as appropriate for what the user asked.

## Integration

Combined with `/park`, this forms the **park and pickup system**.

**Reads from:** Works in Progress (bare mode), Session Logs (via pickup-scan.sh for targeted pickup, direct read for selected topic), Project hubs, Context files
