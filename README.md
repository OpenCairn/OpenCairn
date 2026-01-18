# Claude Code + Obsidian Template

> **It's Sunday afternoon. You sit down to continue that project you were excited about on Thursday. You open your laptop and... nothing. Where were you? What were the next steps? What files were you editing? You spend 20 minutes scrolling through browser tabs and file histories, trying to reconstruct your mental state. By the time you remember, the motivation is gone.**

This template fixes that. Permanently.

```
> /pickup

╔════════════════════════════════════════════════════════════╗
║  Pickup Session - Last 9 Days (By Project)                ║
╠════════════════════════════════════════════════════════════╣
║  1. Side Project - App                         (5 sessions)║
║     Latest: Auth flow implementation       Thu 9:16pm     ║
║     Open loops: 7 total | Last: 2 days ago                 ║
╚════════════════════════════════════════════════════════════╝

> 1

╔════════════════════════════════════════════════════════════╗
║  Side Project - App (5 sessions)                          ║
╠════════════════════════════════════════════════════════════╣
║  1. Auth flow implementation         Thu 9:16pm | Loops: 3 ║
║  2. Database schema design           Wed 7:30pm | [C]      ║
║  3. Initial project setup            Tue 2:15pm | [C]      ║
╚════════════════════════════════════════════════════════════╝

> 1

Loading: Auth flow implementation (Thu 9:16pm)

Open loops:
 [ ] Finish password reset flow
 [ ] Add rate limiting to auth endpoints
 [ ] Write tests for login edge cases

Ready to continue. What's next?
```

Zero reconstruction. Zero "where was I?" You're back in flow within seconds.

---

## The Core Idea

Claude Code can read files from your disk. Obsidian stores notes as files on your disk.

Put them together: Claude becomes a thinking partner with perfect memory of everything you've written - your projects, your preferences, your context, your open loops.

**Before:** Every Claude conversation starts from scratch. You re-explain who you are, what you're working on, what you've already tried.

**After:** Claude reads your `CLAUDE.md` and knows your life context. It reads your project files and knows what you're building. It reads your session history and knows exactly where you left off.

---

## What This Solves

- **"Where was I?"** - The Sunday afternoon problem. Session history with one-command pickup.
- **Mental open loops** - Tasks rattling around your head because you don't trust your capture system. Everything captured, nothing forgotten.
- **Context amnesia** - Re-explaining yourself every conversation. Claude knows who you are.
- **Terminal anxiety** - Keeping sessions open for days because closing means losing context. Park confidently, pickup seamlessly.
- **Scattered notes** - Ideas across apps, files, browser tabs. One folder, one system, infinite context.

---

## The Park and Pickup System

This is the heart of the template.

**At the end of each work session:**
```
> /park
```

Claude documents what you did, captures open loops, and archives the session. You get a "shutdown complete" moment - confident closure knowing everything is captured.

**When you return:**
```
> /pickup
```

Interactive menu of recent sessions, grouped by project. Select one and Claude loads everything - what you were doing, what's still open, which files matter. No reconstruction. Instant flow.

---

## 5-Minute Quick Start

```bash
# Clone the template
git clone https://github.com/harrisonaedwards/claude-code-obsidian-template.git my-vault
cd my-vault

# Remove git history (start fresh)
rm -rf .git && git init

# Open CLAUDE.md and fill in your details
# (who you are, what you're working on, how you think)

# Start Claude Code
claude

# Try it
> /pickup     # See the session menu (empty at first)
> /park       # End your first session
```

That's it. You now have:
- A folder structure that scales
- Session management that never forgets
- An AI that knows your context

---

## What's Included

### Folder Structure (NIPARAS)

```
01 Now/          - Active focus, current priorities
02 Inbox/        - Quick capture (process later)
03 Projects/     - Discrete work with end states
04 Areas/        - Ongoing responsibilities (no end date)
05 Resources/    - Reference material, knowledge base
06 Archive/      - Completed/inactive items, session history
07 System/       - Meta-documentation, Claude context files
```

### Commands

**Daily rhythm:**
- `/morning` - Start of day: surface landscape, catch gaps, set intention
- `/afternoon` - Mid-day recalibration: check drift, reprioritise remaining time (alias: `/regroup`)
- `/goodnight` - End of day: inventory loops, set tomorrow's queue, close cleanly

**Session management:**
- `/park` - End session, document work, capture open loops
- `/pickup` - Resume any session with full context

**Thinking and research:**
- `/thinking-partner` - Explore ideas through questions before solutioning
- `/research-assistant` - Deep search across your vault

**Review and reflection:**
- `/weekly-synthesis` - Weekly patterns and alignment

**Workflow:**
- `/inbox-processor` - Organise captures into the folder structure
- `/de-ai-ify` - Remove AI writing patterns from text

### Extended Breaks

Going on vacation? Taking a sabbatical?

```
> /hibernate    # Before you leave - comprehensive state snapshot
> /awaken       # When you return - restore context, update priorities
```

Bridges the gap between session-to-session continuity and month-long breaks.

---

## Already Have a System?

**Don't adopt this wholesale.** Instead:

1. Clone this repo and examine it with Claude:
   ```
   cd /path/to/this/repo
   claude
   > "Analyse this template. I have [describe your system].
   >  Which elements would integrate well? Which would conflict?"
   ```

2. Cherry-pick what fits:
   - Just the `/park` and `/pickup` commands
   - Just the `CLAUDE.md` pattern
   - Just the folder structure ideas
   - The full system

3. Let Claude help you adapt components to your existing conventions.

The goal is *your* system working for *you*.

---

## Philosophy

**Files, not features.** Everything is plain markdown. No plugins, no lock-in, works with any editor.

**Hierarchical context loading.** Claude doesn't read everything upfront. It reads `CLAUDE.md`, follows links to hub files, then to detailed pages. Efficient navigation, not brute force.

**Park and pickup.** Explicit session boundaries with documented handoffs. Based on Cal Newport's "shutdown complete" ritual.

**Your system, not mine.** This reflects my preferences. Fork it, modify it, throw out what doesn't fit.

---

## Why Obsidian?

Obsidian is just a markdown editor. Your vault is just a folder of files.

Claude Code reads files directly from disk. No plugins, no APIs, no sync issues. Any note you write is immediately available to Claude. Any note Claude writes appears instantly in Obsidian.

The magic isn't Obsidian specifically - it's having your knowledge as accessible files rather than locked in apps.

---

## Customisation

### CLAUDE.md

Your persistent context file. Claude reads it at the start of every session. Include:
- Who you are (life stage, profession, current priorities)
- How you think (mental frameworks, decision-making style)
- Communication preferences (locale, detail level, pushback tolerance)
- Key file locations

See the template file for structure.

### Adding Commands

Create `.md` files in `.claude/commands/`:

```markdown
---
name: my-command
description: What this does
---

# My Command

Instructions for Claude when invoked...
```

### Hub Files

Create domain-specific context in `07 System/`:
- `Context - Work.md`
- `Context - Health.md`
- `Context - [Your Domain].md`

These become indexes Claude reads to understand each area of your life.

---

## Credits

Inspired by:
- [claudesidian](https://github.com/heyitsnoah/claudesidian) - "thinking partner" philosophy
- [obsidian-claude-pkm](https://github.com/ballred/obsidian-claude-pkm) - skills and agents system
- [The Neuron](https://www.theneuron.ai/explainer-articles/how-to-turn-claude-code-into-your-personal-ai-assistant) - workflow patterns

Built with Claude Code.

---

## License

**CC BY-NC-SA 4.0** ([Creative Commons Attribution-NonCommercial-ShareAlike 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/))

Free for personal and non-commercial use with attribution. Commercial use requires permission - [open an issue](https://github.com/harrisonaedwards/claude-code-obsidian-template/issues) to discuss.
