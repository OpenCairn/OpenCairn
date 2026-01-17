---
name: pickup
aliases: [resume, restore]
description: Interactive menu to pickup recent sessions with full context
---

# Pickup - Session Pickup

You are helping the user pickup a previous work session with full context.

## Instructions

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current timestamp: `date +"%s"` (for age calculations)

2. **Scan for sessions:**
   - Read session files from `06 Archive/Claude Sessions/` for last 9 days
   - Extract session metadata:
     - Session number and title
     - Date and time
     - One-sentence summary
     - Open loops (count unchecked `- [ ]` items)
     - Related project
   - Calculate session age ("2 hours ago", "yesterday", "3 days ago")

3. **Display interactive menu:**

```
╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Recent Sessions (Last 9 Days)           ║
╠════════════════════════════════════════════════════════════╣
║  1. Project Work - Sat 17 Jan 9:40am                      ║
║     "Implemented new feature, tests passing"               ║
║     Open loops: 3 | Last: 2 hours ago                     ║
║                                                            ║
║  2. Documentation - Thu 16 Jan 7:23pm                     ║
║     "Updated README, added examples"                       ║
║     Open loops: 1 | Last: 2 days ago                      ║
║                                                            ║
║  [Enter number to pickup, 'n' for new session, 'q' to quit]║
╚════════════════════════════════════════════════════════════╝

>
```

4. **Wait for user selection:**
   - Number: Load that session
   - 'n': Start fresh
   - 'q': Exit

5. **Load selected session context:**
   - Read the full session summary
   - Extract open loops, files updated, resume context
   - Read the linked project file (if applicable)

6. **Display session context:**

```
Loading: [Session Title] ([Date/Time])

Last session summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Summary from session]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Open loops:
 [ ] First unchecked item
 [ ] Second unchecked item

Project: [[03 Projects/Project Name]]
Files updated: path/to/file.md

Ready to continue. What's next?
```

7. **Auto-load relevant context:**
   - Read CLAUDE.md
   - Read linked project file
   - Display what was loaded

## Guidelines

- **Always check current date/time:** First step for accurate age calculations
- **9-day default:** Reliably covers weekend-to-weekend
- **Session ordering:** Most recent first
- **Age display:** Relative time ("2 hours ago", "yesterday")
- **Date formatting:** Natural language ("Sat 17 Jan 9:40am")

## Benefits

1. Zero-friction pickup (no mental "where was I?")
2. Open loops displayed upfront
3. Auto-loading of relevant context
4. Confidence in session continuity

Combined with `/park`, this creates the **park and pickup system**.
