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

# Set your vault path (add to ~/.bashrc or ~/.zshrc for persistence)
export VAULT_PATH="$(pwd)"

# Make scripts executable
chmod +x .claude/scripts/*.sh

# Edit CLAUDE.md with your details
claude

> /park    # End your first session
> /pickup  # See it appear in the menu
```

**Important:** Commands require `VAULT_PATH` environment variable. Add to your shell profile:
```bash
echo 'export VAULT_PATH=/path/to/your/vault' >> ~/.bashrc  # or ~/.zshrc
source ~/.bashrc
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

**Commands:** `/park`, `/pickup`, `/morning`, `/afternoon`, `/goodnight`, `/weekly-synthesis`, `/hibernate`, `/awaken`, `/thinking-partner`, `/research-assistant`, `/inbox-processor`, `/de-ai-ify`, `/complete-project`, `/archive-sessions`, `/start-project`

**Scripts:** `.claude/scripts/` contains shell scripts used by commands:
- `pickup-scan.sh` - Pre-scans vault for `/pickup`, reducing context usage by ~50%
- `write-session.sh` - Atomic session file writes with flock
- `add-forward-link.sh` - Bidirectional session linking

Scripts require `VAULT_PATH` environment variable (set during Quick Start).

---

## Already Have a System?

Don't adopt this wholesale. Cherry-pick:

- Just `/park` and `/pickup`
- Just the `CLAUDE.md` pattern
- Just the folder structure
- The full system

Clone it, run `claude`, ask: *"Analyse this template. I have [your system]. What integrates well?"*

---

## Tips

### Context-Aware Status Line

Claude Code's default status line shows absolute tokens (`Ctx: 30.7k`). More useful: percentage with colour-coded warnings.

Create `~/.claude/statusline.sh`:

```bash
#!/bin/bash
input=$(cat)
MODEL=$(echo "$input" | jq -r '.model.display_name // .model // "Claude"')
PERCENT=$(echo "$input" | jq -r '.context_window.used_percentage // 0')
TOTAL=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')
DURATION_MS=$(echo "$input" | jq -r '.cost.total_duration_ms // 0')
USED=$((TOTAL * PERCENT / 100))
USED_FMT=$([ "$USED" -ge 1000 ] && awk "BEGIN {printf \"%.0fk\", $USED/1000}" || echo "$USED")
SESSION_SECS=$((DURATION_MS / 1000))

if [ "$SESSION_SECS" -lt 60 ]; then DURATION="<1m"
elif [ "$SESSION_SECS" -lt 3600 ]; then DURATION="$((SESSION_SECS / 60))m"
else DURATION="$((SESSION_SECS / 3600))h$((SESSION_SECS % 3600 / 60))m"; fi

if [ "$PERCENT" -ge 50 ]; then CTX="\033[31m${USED_FMT} (${PERCENT}%)\033[0m"
elif [ "$PERCENT" -ge 30 ]; then CTX="\033[33m${USED_FMT} (${PERCENT}%)\033[0m"
else CTX="\033[32m${USED_FMT} (${PERCENT}%)\033[0m"; fi

echo -e "Ctx: ${CTX} | Model: ${MODEL} | Session: ${DURATION}"
```

Then in `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
```

Make it executable and ensure `jq` is installed:

```bash
chmod +x ~/.claude/statusline.sh
# On Debian/Ubuntu: sudo apt install jq
# On macOS: brew install jq
```

Now you see `Ctx: 30.7k (15%)` - green under 30%, yellow 30-50%, red above 50%. Park around 30-40% to stay ahead of context rot. Changes take effect immediately (no restart needed).

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

[MIT License](LICENSE)
