<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/logo-light.svg">
    <img alt="OpenCairn" src="assets/logo-light.svg" width="120">
  </picture>
</p>

<h1 align="center">OpenCairn</h1>

<p align="center"><em>Park. Pickup. Flow.</em></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--NC%204.0-blue?style=for-the-badge" alt="License: CC BY-NC 4.0"></a>&nbsp;
  <a href="https://github.com/OpenCairn/OpenCairn/stargazers"><img src="https://img.shields.io/github/stars/OpenCairn/OpenCairn?style=for-the-badge" alt="GitHub stars"></a>
</p>

21 slash commands, a 7-folder filing system, and session chaining for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) + [Obsidian](https://obsidian.md/).

<p align="center">
  <a href="https://hedwards.dev/cco-setup/">Setup Guide</a> · <a href="https://hedwards.dev/claude-code-obsidian/">Blog Series</a> · <a href="https://hedwards.dev/claude-code-tips/">Tips</a>
</p>

---

> **It's Sunday afternoon. You sit down to continue planning that Japan trip you were excited about on Thursday. You open your laptop and... nothing. Where were you? Which hotels were you comparing? What did you decide about the Kyoto day trips?**
>
> **You won't spend 20 minutes reconstructing. Nobody does. The activation energy is too high, the dopamine too low. So you check your phone. Refresh something. The trip sits there unplanned for another week.**

```
> /pickup

Active projects: Japan Trip, Website Redesign
Last daily report: Thu 9:16pm

Open loops (from Thu):
 [ ] Book ryokan - narrowed to 2 options, need to decide
 [ ] Figure out JR pass vs individual tickets
 [ ] Ask Mike about that ramen place in Osaka

Tomorrow's queue had "Kyoto logistics" first.
What would you like to pick up?
```

Zero reconstruction. Instant flow.

---

## Who This Is For

**Good fit:**
- You have multiple domains of life you think about seriously
- You want AI as a long-term thinking partner, not a chat toy
- You're comfortable with a terminal (Claude Code is a CLI tool)
- You're willing to spend an hour setting up for long-term payoff

**Less good fit:**
- You just want quick answers to quick questions
- You prefer everything to "just work" without configuration

If the terminal part sounds alien, the [setup wizard](https://hedwards.dev/cco-setup/) walks through everything step by step.

---

## How It Works

**Obsidian** is a markdown editor that works on local files - no cloud, no proprietary format, just folders of `.md` files on your disk. **Claude Code** reads and writes those same files directly. Your notes and Claude's context are the same thing.

**The files are the context.** Not Claude's summary of the files. Not what it thinks you said last week. The actual files. Each conversation produces refined thinking that gets written back to your vault, becoming input for the next conversation. Context compounds instead of decaying.

This template provides the structure: where files go, how Claude navigates them, and how sessions connect across time.

---

## The System

Four layers, from single sessions up to months-long breaks.

### Session: Park and Pickup

The core mechanic. Based on Cal Newport's "shutdown complete" ritual - the idea that you can't truly rest while your brain holds onto incomplete loops.

**End of session:** `/park` documents what you did, captures open loops, and archives to a session file. It detects whether you did 5 minutes of quick work or an hour of deep thinking and adjusts accordingly - quick sessions get a one-liner, full sessions get structured documentation with next steps and pickup context. Before closing, it runs a quality gate (lint, refactor, proofread any files you modified). Sessions chain bidirectionally - each one links to the previous and next, so you can trace a project's history through time.

**Next session:** `/pickup` reads your Works in Progress and the 1-2 most recent daily reports (produced by `/goodnight`), giving you a concise landscape of what's active, what's open, and what was queued next. Lightweight by design - it reads 3-5 files and completes in one turn, preserving context for actual work.

### Day: Morning, Afternoon, Goodnight

| Command | When | What |
|---------|------|------|
| `/morning` | Start of day | Read the landscape (WIP, tickler, yesterday's loops), catch gaps, optionally build a time-blocked `Today.md` |
| `/afternoon` | Mid-day | Check progress against morning intention, catch productive drift, reprioritise remaining time |
| `/goodnight` | End of day | Inventory open loops, set tomorrow's queue, generate daily report, log the session |

`Today.md` is a plain-text daily plan - viewable in Obsidian on your phone (via [Obsidian Sync](https://obsidian.md/sync)), editable by hand mid-day, never dependent on a calendar API being up. `/afternoon` and `/goodnight` read it to track what actually happened.

### Week: Weekly Synthesis

`/weekly-synthesis` zooms out. Aggregates progress across projects, surfaces stalled work, checks for zombie projects lingering in WIP, reviews the corrections log for patterns worth promoting to context files, and flags open loops older than 14 days.

### Extended Breaks: Hibernate and Awaken

Going on vacation? `/hibernate` captures a full state snapshot - all active projects, prioritised open loops, deliberate deferrals, recent decisions. `/awaken` restores context when you return weeks or months later and interviews you on what changed while you were away.

---

## Folder Structure (NIPARAS)

NIPARAS extends Tiago Forte's [PARA method](https://fortelabs.com/blog/para/) (Projects, Areas, Resources, Archive) by adding three folders: **Now** (active working memory), **Inbox** (capture point), and **System** (meta-documentation and context files for Claude).

| Folder | Purpose | Examples |
|--------|---------|----------|
| **01 Now** | Active working memory - what's in flight right now | Works in Progress, Today (daily plan), scratch notes |
| **02 Inbox** | Capture point for new stuff before it's organised | Quick notes, web clippings, ideas to process |
| **03 Projects** | Discrete efforts with an end state ("done" looks like X) | "Plan Japan trip", "Launch website", "Learn Python" |
| **04 Areas** | Domains of life you maintain indefinitely, with nested resources | Health (supplements, bloodwork), Photography (portfolios, gear), Finances (tax, investments) |
| **05 Resources** | Generic reference material that doesn't belong to an Area yet | Journal entries, recipes, meeting notes, misc reference |
| **06 Archive** | Completed or inactive items | Finished projects, old session logs, historical notes |
| **07 System** | Meta-documentation - how the vault works and context for Claude | CLAUDE.md, Context hub files, vault config |

**Areas vs Resources (differs from standard PARA):** NIPARAS uses Areas and Resources differently to Tiago Forte's original PARA. Here, **Areas** are domains you actively maintain, each containing its own nested reference material and Archive subfolders. **Resources** is a staging ground for generic stuff that doesn't belong to an Area yet. When something accumulates enough mass, it graduates to an Area. The key shift is that reference material lives *inside* the Area it belongs to, rather than in a separate top-level folder.

**Context navigation** follows a hierarchical lazy-loading pattern - Claude reads `CLAUDE.md` first, follows links to domain hub files (e.g. `Context - Health.md`) when relevant, then drills into specific notes only when needed. Detailed in the [blog series](https://hedwards.dev/hierarchical-context-navigation/).

---

## Quick Start

**Prerequisites:** [Git](https://git-scm.com/downloads), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Obsidian](https://obsidian.md/) (optional but recommended). For a detailed walkthrough: [hedwards.dev/cco-setup/](https://hedwards.dev/cco-setup/)

```bash
git clone https://github.com/OpenCairn/OpenCairn.git ~/Files
cd ~/Files

# Rename remote to 'template' so /update can pull future changes
# (leaves 'origin' free for your own repo if you want one)
git remote rename origin template

# Make scripts executable
chmod +x .claude/scripts/*.sh

# Add to your shell profile (~/.bashrc or ~/.zshrc):
export VAULT_PATH="$HOME/Files"
alias cc='cd ~/Files && claude'
```

Then start Claude and personalise:

```bash
cc   # or: cd ~/Files && claude

# CLAUDE.md has bracketed placeholders - fill in your name,
# profession, life context, and communication preferences.
# Then try the core loop:

> /park    # End your first session
> /pickup  # See your landscape and open loops
```

If using Obsidian, open it and select `~/Files` as your vault folder.

**Staying current:** Run `/update` periodically to pull the latest commands and scripts from the template repo. Your CLAUDE.md and vault content are never touched - only infrastructure files update.

---

## All Commands

**Session management:**

| Command | What it does |
|---------|-------------|
| `/park` | End a session - documents work, captures open loops, archives with bidirectional links, runs quality gate |
| `/pickup` | Resume work - reads WIP and recent daily reports, presents landscape and open loops |
| `/checkpoint` | Mid-session snapshot without ending the session |

**Daily rhythm:**

| Command | What it does |
|---------|-------------|
| `/morning` | Start of day - surface landscape, catch gaps, build Today.md |
| `/afternoon` | Mid-day - check Today.md progress, reprioritise |
| `/goodnight` | End of day - inventory loops, set tomorrow's queue, daily report |
| `/weekly-synthesis` | Weekly review - aggregate progress, surface patterns, check WIP integrity |

**Extended breaks:**

| Command | What it does |
|---------|-------------|
| `/hibernate` | Save full state before vacation or long break |
| `/awaken` | Restore context after returning from extended break |

**Project management:**

| Command | What it does |
|---------|-------------|
| `/start-project` | Create a new project - hub page, add to WIP, link to parent initiative |
| `/complete-project` | Archive a finished project - move to archive, update WIP |
| `/inbox-processor` | Organise inbox captures into NIPARAS structure |
| `/archive-sessions` | Clean up and organise session files |

**Thinking tools:**

| Command | What it does |
|---------|-------------|
| `/thinking-partner` | Explore ideas through questions before jumping to solutions |
| `/research-assistant` | Deep vault search and synthesis - find what's known before searching externally |
| `/patterns` | Find recurring themes, contradictions, and connections across vault files on a topic |
| `/de-ai-ify` | Remove AI writing patterns and restore your authentic voice |

**Maintenance:**

| Command | What it does |
|---------|-------------|
| `/update` | Pull latest commands and scripts from the template repo (vault content never touched) |
| `/oops` | Capture a mistake and its lesson - logs to Corrections Log, detects patterns |

**Aliases:** `/regroup` → `/afternoon`, `/shutdown` → `/goodnight`

---

## Under the Hood

- **Lightweight pickup.** `/pickup` reads Works in Progress and the 1-2 most recent daily reports — already-synthesised context from `/goodnight`. No shell scripts, no session scanning, one turn to orientation.
- **Tiered overhead detection.** `/park` measures what you actually did. Quick sessions get a one-line log. Full sessions get structured documentation. You don't pay documentation overhead for a 2-minute tweak.
- **Bidirectional session links.** Each session links forward and backward. Trace a project's history through time without searching.
- **File locking.** All writes use `flock` (Linux) or `mkdir` fallback (macOS/Windows). Safe for concurrent Claude instances and NAS-mounted vaults.
- **Tickler system.** `/park` offers to defer open loops to specific future dates. Deferred items surface automatically in `/morning` and `/pickup` when their date arrives.
- **Corrections log.** `/oops` captures mistakes and lessons. `/weekly-synthesis` reviews for recurring patterns worth promoting to context files. Only get something wrong once.

Scripts live in `.claude/scripts/` and require the `VAULT_PATH` environment variable.

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

**Context-aware status line.** Claude Code's default status line shows absolute tokens. A percentage with colour-coded warnings is more useful - see [hedwards.dev/claude-code-tips/](https://hedwards.dev/claude-code-tips/) for the setup script. Startup commands (`/morning`, `/pickup`, etc.) consume significant context on their own - a fresh session typically starts around 15-20% just from loading context files and command prompts, so your usable working window is smaller than the raw percentage suggests.

**More tips** on context management, workflow patterns, keyboard shortcuts, and MCP servers: [hedwards.dev/claude-code-tips/](https://hedwards.dev/claude-code-tips/)

---

## Credits

Inspired by [claudesidian](https://github.com/heyitsnoah/claudesidian), [obsidian-claude-pkm](https://github.com/ballred/obsidian-claude-pkm), [The Neuron](https://www.theneuron.ai/explainer-articles/how-to-turn-claude-code-into-your-personal-ai-assistant). Built with Claude Code.

---

## License

[CC BY-NC 4.0](LICENSE) - Free for personal use. [Contact me](mailto:harrisonaedwards@gmail.com) for commercial licensing.
