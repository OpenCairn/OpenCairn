---
name: pickup
aliases: [resume, restore]
description: Resume work - load active projects, recent context, and open loops
parameters:
  - "--hibernate=DATE" - Load hibernate snapshot instead (redirects to /awaken)
---

# Pickup - Session Pickup

You are helping the user resume work by loading their current landscape: what's active, what happened recently, and what's open.

## Instructions

0. **Resolve Vault Path**

   ```bash
   if [[ -z "${VAULT_PATH:-}" ]]; then
     echo "VAULT_PATH not set"; exit 1
   elif [[ ! -d "$VAULT_PATH" ]]; then
     echo "VAULT_PATH=$VAULT_PATH not found"; exit 1
   else
     echo "VAULT_PATH=$VAULT_PATH OK"
   fi
   ```

   If ERROR, abort. **Use the resolved path for all file operations below.**

1. **If `--hibernate` specified:** Redirect to `/awaken --date=DATE` and stop.

2. **Read core context files (in parallel where possible):**

   a. **Works in Progress:** `$VAULT_PATH/01 Now/Works in Progress.md`

   b. **Most recent daily reports (1-2):** List files in `$VAULT_PATH/06 Archive/Daily Reports/`, sort reverse-chronological, read the 1-2 most recent. These are the most recent *reports that exist*, not the last 1-2 calendar days (the user may not use CCO daily).

   c. **Today's session file (if it exists):** `$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md` where YYYY-MM-DD is today's date (from `date +"%Y-%m-%d"`). If no file exists for today, skip — the daily reports cover prior days.

   d. **Tickler (if it exists):** `$VAULT_PATH/01 Now/Tickler.md` — scan for items where the date header (`## YYYY-MM-DD`) is today or earlier. These are due or overdue.

3. **Present a concise summary:**

   - **What's active** (from WIP — project names and status, not the full file)
   - **Where things stand** (from the most recent daily report — open loops, tomorrow's queue, blockers)
   - **What happened today** (from today's session file, if any — brief session list)
   - **Due tickler items** (if any)

   Keep it scannable. The user probably knows what they want to work on — this is orientation, not a quiz.

4. **Ask what to work on:**

   "What would you like to pick up?" or suggest the most obvious next action if one stands out (e.g. the daily report's "Tomorrow's Queue" item 1).

## Guidelines

- **This is a lightweight command.** It reads 3-5 files and presents a summary. It should complete in one turn with minimal context usage.
- **Daily reports are the primary source.** They contain pre-synthesized session summaries, open loops, tomorrow's queue, and blockers — all produced by `/goodnight`. Don't re-derive what's already been synthesized.
- **WIP is the project index.** It tells you what's active. Don't scan session files to reconstruct this.
- **Don't build menus.** If the user wants to browse specific sessions, they can link to files directly. The pickup's job is orientation, not navigation.
- **Don't read session files for prior days.** The daily reports already summarise those sessions. Only read today's session file (for context on the current day's work so far).
- **If no daily reports exist yet** (new vault), fall back to reading the most recent session file (list `$VAULT_PATH/06 Archive/Claude Sessions/`, take the most recent) and WIP.
- **If WIP hasn't been updated in 10+ days**, mention it — the landscape may have shifted.

## What This Replaced

This command was previously a 26KB interactive menu system with shell script pre-scanning, project clustering, hide/snooze, and pagination. That was replaced because:
1. Daily reports (from `/goodnight`) already synthesise everything the menu was reconstructing
2. WIP already provides the project index
3. Most pickups are "I know what I'm working on" — orientation beats navigation
4. The old command consumed significant context before work even began

If the user needs to browse old sessions, they can read `06 Archive/Claude Sessions/` or `06 Archive/Daily Reports/` directly.
