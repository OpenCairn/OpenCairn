# Claude Code + Obsidian Template

> **It's Sunday afternoon. You sit down to continue planning that Japan trip you were excited about on Thursday. You open your laptop and... nothing. Where were you? Which hotels were you comparing? What did you decide about the Kyoto day trips?**
>
> **You won't spend 20 minutes reconstructing. Nobody does. The activation energy is too high, the dopamine too low. So you check your phone. Refresh something. The trip sits there unplanned for another week.**

This template fixes that.

```
> /pickup

Recent Sessions (By Project)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Japan Trip                (4 sessions)
   Latest: Kyoto logistics       Thu 9:16pm | 3 loops

> 1

Loading: Kyoto logistics

Open loops:
 [ ] Book ryokan - narrowed to 2 options, need to decide
 [ ] Figure out JR pass vs individual tickets
 [ ] Ask Mike about that ramen place in Osaka

Ready to continue. What's next?
```

Zero reconstruction. Instant flow.

---

## How It Works

Web-based LLMs are like collaborating on a Word doc via email - you send a file, they send edits, you lose track of versions, they forget what you discussed last week.

Claude Code is different. It reads and writes files directly on your disk. **The files are the context.** Not Claude's summary of the files. Not what it thinks you said last week. The actual files.

This means:

- **You control what Claude knows.** Put it in the folder, Claude can read it. Don't put it there, Claude doesn't know it exists. No algorithm deciding what's "relevant".

- **Context doesn't drift.** Web LLMs compress and summarise behind the scenes. After a few sessions, their memory of your project diverges from reality. Here, Claude reads your actual notes every time. The source of truth is your files.

- **Structure is yours to define.** Want Claude to understand your health history before giving supplement advice? Write a `Context - Health.md` file and link it from `CLAUDE.md`. Claude navigates to what it needs, when it needs it.

Obsidian is just a nice way to view and edit these files. The magic is **local files + an LLM that can actually use them**.

---

## The System

### Park and Pickup

The core mechanic.

**End of session:** `/park` - Claude documents what you did, captures open loops, archives the session. Confident closure.

**Next session:** `/pickup` - Interactive menu, grouped by project. Select one, get full context. No reconstruction.

### Daily Rhythm

Structure your day:

| Command | When | What |
|---------|------|------|
| `/morning` | Start of day | Surface landscape, catch gaps, set intention |
| `/afternoon` | Mid-day | Check drift, reprioritise remaining time |
| `/goodnight` | End of day | Inventory loops, set tomorrow's queue |

### Extended Breaks

Going on vacation? `/hibernate` before you leave. `/awaken` when you return. Bridges the gap between sessions and months.

---

## Quick Start

```bash
git clone https://github.com/harrisonaedwards/claude-code-obsidian-template.git my-vault
cd my-vault
rm -rf .git && git init

# Edit CLAUDE.md with your details
claude

> /park    # End your first session
> /pickup  # See it appear in the menu
```

---

## What's Included

**Folder structure (NIPARAS):**
```
01 Now/       - Current focus, working memory
02 Inbox/     - Quick capture, downloads
03 Projects/  - Sprints with end states
04 Areas/     - Domains of life (with nested resources)
05 Resources/ - Generic scrapbook, pre-emergence staging
06 Archive/   - Completed items, session history
07 System/    - Context files for Claude
```

**Areas vs Resources:** Areas are domains you actively maintain (Photography, Health, Finances) - each contains its own reference material. Resources is a staging ground for generic stuff that doesn't belong to a specific domain yet. When something accumulates enough mass, it graduates to an Area.

**Commands:** `/park`, `/pickup`, `/morning`, `/afternoon`, `/goodnight`, `/thinking-partner`, `/research-assistant`, `/weekly-synthesis`, `/hibernate`, `/awaken`, `/inbox-processor`, `/de-ai-ify`

---

## Already Have a System?

Don't adopt this wholesale. Cherry-pick:

- Just `/park` and `/pickup`
- Just the `CLAUDE.md` pattern
- Just the folder structure
- The full system

Clone it, run `claude`, ask: *"Analyse this template. I have [your system]. What integrates well?"*

---

## Philosophy

**Files, not features.** Plain markdown. No plugins, no lock-in.

**Hierarchical context.** Claude reads `CLAUDE.md`, follows links to hub files, then details. Efficient, not brute force.

**Park and pickup.** Explicit session boundaries. Based on Cal Newport's "shutdown complete" ritual.

---

## Credits

Inspired by [claudesidian](https://github.com/heyitsnoah/claudesidian), [obsidian-claude-pkm](https://github.com/ballred/obsidian-claude-pkm), [The Neuron](https://www.theneuron.ai/explainer-articles/how-to-turn-claude-code-into-your-personal-ai-assistant). Built with Claude Code.

---

## License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) - Free for personal use with attribution. Commercial use requires permission.
