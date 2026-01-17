# Claude Code + Obsidian Template

A system for using Claude Code as your thinking partner, with Obsidian as persistent memory.

## Why This Exists

This system addresses a specific cluster of problems:

- **Mental open loops** - Tasks and ideas rattling around your head because you don't trust your capture system
- **Context amnesia** - Starting each Claude session from scratch, re-explaining who you are and what you're working on
- **Terminal window anxiety** - Keeping sessions open for days because closing them means losing context
- **Scattered notes** - Ideas spread across apps, files, and browser tabs with no coherent structure
- **"Where was I?"** - Returning to work after a break and spending 20 minutes reconstructing your mental state

The core insight: Claude Code can read your filesystem. If your notes are well-organised files, Claude becomes a thinking partner with perfect memory of everything you've written.

## Why Obsidian?

Obsidian is just a markdown editor. Your vault is just a folder of files.

Claude Code reads files directly from disk. It doesn't need plugins, APIs, or integrations - it just reads your notes. This means:

- **No sync issues** - Any note you write is immediately available to Claude
- **No plugins required** - Works with a fresh Obsidian install (or any markdown editor)
- **Bidirectional** - Claude can create notes that appear instantly in Obsidian
- **No lock-in** - It's just files. Switch editors anytime.

The magic isn't in Obsidian specifically - it's in having your knowledge as accessible files rather than locked in apps.

## Two Ways to Use This

### Starting Fresh

If you don't have an existing Obsidian vault or want a clean start:

1. Clone this template
2. Customise `CLAUDE.md` with your personal context
3. Start using the folder structure and commands

### Existing System

If you already have an Obsidian vault or note-taking system:

**Don't wholesale adopt this.** Instead:

1. **Examine the components** - Read through this repo with Claude Code:
   ```
   cd /path/to/this/repo
   claude
   > "Analyse this template. I have an existing [describe your system].
   >  Which elements would integrate well? Which would conflict?"
   ```

2. **Cherry-pick what fits** - You might want:
   - Just the `/park` and `/pickup` commands for session management
   - Just the CLAUDE.md pattern for personal context
   - Just the folder structure ideas
   - The full system

3. **Workshop the integration** - Ask Claude to help adapt components to your existing conventions rather than forcing you into mine.

The goal is *your* system working for *you*, not conformity to this template.

---

## Quick Start (Fresh Install)

```bash
# Clone the template
git clone https://github.com/harrisonaedwards/claude-code-obsidian-template.git my-vault
cd my-vault

# Remove the git history (start fresh)
rm -rf .git
git init

# Customise CLAUDE.md with your details
# (see CLAUDE.md for instructions)

# Start Claude Code
claude
```

## What's Included

### Folder Structure (NIPARAS)

```
01 Now/          - Active working memory, current focus
02 Inbox/        - Capture point for new stuff (process later)
03 Projects/     - Discrete sprints with end states
04 Areas/        - Ongoing responsibilities (no end date)
05 Resources/    - Reference material
06 Archive/      - Completed/inactive items
07 System/       - Meta-documentation, context files for Claude
```

See `07 System/Vault Organisation Principles.md` for the philosophy.

### Commands

Session management (the core of this system):
- **`/park`** - End session, document what happened, capture open loops
- **`/pickup`** - Resume a previous session with full context

Discovery and thinking:
- **`/thinking-partner`** - Explore ideas through questions before solutioning
- **`/research-assistant`** - Deep vault search and synthesis

Review and reflection:
- **`/daily-review`** - End-of-day reflection
- **`/weekly-synthesis`** - Weekly patterns and alignment check

Workflow:
- **`/inbox-processor`** - Organise captures into NIPARAS structure
- **`/de-ai-ify`** - Remove AI writing patterns, restore your authentic voice

### The Park and Pickup System

This is the cornerstone. At the end of each session:

```
> /park
```

Claude documents what happened, captures open loops, and saves to `06 Archive/Claude Sessions/`. Next time:

```
> /pickup
```

You get an interactive menu of recent sessions. Select one and Claude loads the full context - what you were doing, what's still open, which files you were editing.

**The result:** Zero "where was I?" friction. Confident shutdown knowing everything is captured.

---

## Customisation

### CLAUDE.md

The `CLAUDE.md` file is your persistent context. Claude reads it at the start of every session. Include:

- Who you are (life stage, profession, current priorities)
- How you think (mental frameworks, decision-making style)
- Communication preferences (locale, depth, pushback tolerance)
- Key context file locations

See the template file for structure and examples.

### Adding Commands

Create `.md` files in `.claude/commands/`. Format:

```markdown
---
name: command-name
description: What this command does
---

# Command Name

Instructions for Claude when this command is invoked...
```

### Hub Files

Create domain-specific context files in `07 System/`:
- `Context - [Domain].md` for areas you work in frequently
- These become "indexes" Claude can read to understand that domain

---

## Philosophy

**Files, not features.** Everything is plain markdown files. No plugins required, no lock-in, works with any editor.

**Hierarchical context loading.** Claude doesn't read everything upfront. It reads CLAUDE.md, then follows links to hub files, then to detailed pages. Like navigating a city - you don't need the whole map, just which turns to make.

**Park and pickup.** Explicit session boundaries with documented handoffs. Based on Cal Newport's "shutdown complete" ritual - you can rest knowing everything is captured.

**Your system, not mine.** This template reflects my preferences. Fork it, modify it, throw out what doesn't work.

---

## Credits

Inspired by:
- [claudesidian](https://github.com/heyitsnoah/claudesidian) - "thinking partner" philosophy
- [obsidian-claude-pkm](https://github.com/ballred/obsidian-claude-pkm) - skills and agents system

Built with Claude Code.

---

## License

**CC BY-NC-SA 4.0** ([Creative Commons Attribution-NonCommercial-ShareAlike 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/))

You're free to use, adapt, and share this template for personal and non-commercial purposes, as long as you credit the source and share derivatives under the same license.

**Commercial use** (courses, products, corporate deployment, AI training, etc.) requires explicit permission - reach out first.
