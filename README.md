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
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-CC%20BY--NC%204.0-blue?style=for-the-badge" alt="Licence: CC BY-NC 4.0"></a>&nbsp;
  <a href="https://github.com/OpenCairn/OpenCairn/stargazers"><img src="https://img.shields.io/github/stars/OpenCairn/OpenCairn?style=for-the-badge" alt="GitHub stars"></a>
</p>

Session chaining, day/week/quarter review loops, and a 7-folder vault for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) + [Obsidian](https://obsidian.md/) — plus skills like `/audit` and `/second-opinion` that run standalone in any project.

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

## Two Ways to Use This

**Grab the portable skills.** `/audit`, `/second-opinion`, and `/thinking-partner` work in *any* Claude Code project — no vault, no folder structure. Install them as a plugin:

```bash
/plugin marketplace add OpenCairn/OpenCairn
/plugin install opencairn@opencairn
```

`/audit` runs a rigorous five-layer review of any code, config, or plan — by default through a **cross-model panel** (Claude + Gemini + Codex), so you catch what a single model rationalises away. `/second-opinion` brings those same three models together for an independent verdict on a decision or a piece of work. `/thinking-partner` is a Socratic mode that interrogates your assumptions instead of jumping to answers. None of them need a vault.

**Or adopt the whole system.** Everything below is the integrated vault: session chaining, the day/week/quarter review loops, and a life-direction layer. The rest of the skills (`/park`, `/morning`, `/oops`, the review passes) assume the [folder structure](#folder-structure-niparas) and a `VAULT_PATH`. Start at [Quick Start](#quick-start).

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

**Obsidian** is a markdown editor that works on local files - no cloud, no proprietary format, just folders of `.md` files on your disc. **Claude Code** reads and writes those same files directly. Your notes and Claude's context are the same thing.

**The files are the context.** Not Claude's summary of the files. Not what it thinks you said last week. The actual files. Each conversation produces refined thinking that gets written back to your vault, becoming input for the next conversation. Context compounds instead of decaying.

This template provides the structure: where files go, how Claude navigates them, and how sessions connect across time.

---

## The System

Five layers, from single sessions up to life direction.

### Session: Park and Pickup

The core mechanic. Based on the "shutdown complete" ritual — the idea that you can't truly rest while your brain holds onto incomplete loops.

**End of session:** `/park` documents what you did, captures open loops, and archives to a session file. It detects whether you did 5 minutes of quick work or an hour of deep thinking and adjusts accordingly - quick sessions get a one-liner, full sessions get structured documentation with next steps and pickup context. Before closing, it runs a quality gate (lint, refactor, proofread any files you modified). Sessions chain bidirectionally - each one links to the previous and next, so you can trace a project's history through time.

**Next session:** `/pickup` shows your Works in Progress as a numbered list — pick one to load its project hub and last session context. Or pass a topic/keyword to jump straight in; a shell script extracts session metadata as compact TSV so targeted searches are cheap.

All session writes use `flock` (Linux) or an `mkdir` fallback (macOS/Windows), so concurrent Claude instances and NAS-mounted vaults don't trample each other.

### Day: Morning, Afternoon, Goodnight

| Skill | When | What |
|---------|------|------|
| `/morning` | Start of day | Read the landscape (WIP, tickler, yesterday's loops), catch gaps, optionally build today's time-blocked plan in `This Week.md` |
| `/afternoon` | Mid-day | Check progress against morning intention, catch productive drift, reprioritise remaining time |
| `/goodnight` | End of day | Inventory open loops, set tomorrow's queue, generate daily report, log the session |

`This Week.md` is a rolling 7-day plan — viewable in Obsidian on your phone (via [Obsidian Sync](https://obsidian.md/sync)), editable by hand mid-day, never dependent on a calendar API being up. Each day gets a time-blocked section. `/afternoon` and `/goodnight` read today's section to track what actually happened.

A **tickler** sits underneath the day layer: `/park` offers to defer open loops to specific future dates, and deferred items resurface automatically in `/morning` and `/pickup` when their date arrives. Once an item is pulled into a planning document, that document becomes SSOT and the tickler copy is deleted — no duplicate checkboxes drifting across the vault.

### Week: Weekly Review

`/weekly-review` zooms out. Aggregates progress across projects, surfaces stalled work, checks for zombie projects lingering in WIP, and flags open loops older than 14 days. It also reviews the **corrections log** — `/oops` captures mistakes and lessons as you go; the weekly pass looks for recurring patterns worth promoting to context files, so you only get something wrong once. Structural vault maintenance (broken links, stale items, orphaned files) is handled by `/weekly-hygiene`, which can run standalone or as a precursor.

### Quarter: Quarterly Review

`/quarterly-review` is the deepest pass: strategic alignment (are you working on the right things?), priority drift, next quarter's Big Rocks, and a `Context - Direction.md` overhaul. Structural deep maintenance (full context-file re-read, CRM stale-entry review, oversized files, session-log archiving) is handled by `/quarterly-hygiene`, which the review consumes — mirroring how `/weekly-review` pairs with `/weekly-hygiene`. Too heavy for weekly, but accumulates real debt if never done.

### Extended Breaks: Hibernate and Awaken

Going on vacation? `/hibernate` captures a full state snapshot - all active projects, prioritised open loops, deliberate deferrals, recent decisions. `/awaken` restores context when you return weeks or months later and interviews you on what changed while you were away.

### Direction: Values, Strategic Plans, Disciplines

Without a strategic layer, you can be perfectly organised and still working on the wrong things. `07 System/Context - Direction.md` holds your values and roles, career and personal strategic plans, anti-goals (things you've explicitly decided against), and an evolving list of disciplines (hard commitments you always follow). Everything below flows from this — your weekly plan is shaped by your strategic plan, which is shaped by your values. Reviewed weekly for alignment, overhauled at major life transitions. A separate `Strategic Decision Log` preserves the rationale behind major direction choices.

---

## Folder Structure (NIPARAS)

NIPARAS extends Tiago Forte's [PARA method](https://fortelabs.com/blog/para/) (Projects, Areas, Resources, Archive) by adding three folders: **Now** (active working memory), **Inbox** (capture point), and **System** (meta-documentation and context files for Claude).

| Folder | Purpose | Examples |
|--------|---------|----------|
| **01 Now** | Active working memory - what's in flight right now | Works in Progress, This Week (rolling 7-day plan), scratch notes |
| **02 Inbox** | Capture point for new stuff before it's organised | Quick notes, web clippings, ideas to process |
| **03 Projects** | Discrete efforts with an end state ("done" looks like X) | "Plan Japan trip", "Launch website", "Learn Python" |
| **04 Areas** | Domains of life you maintain indefinitely, with nested resources | Health (supplements, bloodwork), Photography (portfolios, gear), Finances (tax, investments) |
| **05 Resources** | Generic reference material that doesn't belong to an Area yet | Journal entries, recipes, meeting notes, misc reference |
| **06 Archive** | Completed or inactive items | Finished projects, old session logs, historical notes |
| **07 System** | Meta-documentation - how the vault works and context for Claude | CLAUDE.md, Context hub files, Direction (strategic plans), decision/corrections/wins logs |

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

Then start Claude and run the setup interview:

```bash
cc   # or: cd ~/Files && claude

> /setup   # Checks prerequisites, personalises CLAUDE.md through a short interview
> /park    # End your first session
> /pickup  # See your landscape and open loops
```

If using Obsidian, open it and select `~/Files` as your vault folder.

**Staying current:** Run `/update` periodically to pull the latest skills and scripts from the template repo. Your CLAUDE.md and vault content are never touched - only infrastructure files update.

**Install just the skills (optional):** OpenCairn is also a Claude Code plugin marketplace, so you can pull the skills into any project without cloning the vault:

```bash
/plugin marketplace add OpenCairn/OpenCairn
/plugin install opencairn@opencairn
```

This installs the **skills only**. Most assume the NIPARAS folder structure and `VAULT_PATH` — `/park`, `/morning`, the review passes, and logging skills like `/oops`, `/win`, and `/de-ai-ify` (which read or write vault files). Others run in any project with no vault: `/audit`, `/second-opinion`, and `/thinking-partner`, plus media utilities like `/ocr`, `/transcribe`, and `/podcast-digest`. For the full system, clone the template above.

---

## All Skills

<details>
<summary><strong>Click to expand the full skill reference</strong></summary>

> **Standalone (no vault needed):** `/audit`, `/second-opinion`, `/thinking-partner`, plus the media utilities `/ocr`, `/transcribe`, `/podcast-digest`. Everything else — session chaining, the day/week/quarter loops, reviews, and logging skills like `/oops` and `/win` — assumes the NIPARAS vault structure and a `VAULT_PATH`.

**Daily rhythm:**

| Skill | What it does |
|---------|-------------|
| `/morning` | Start-of-day check-in. Surfaces active projects, tickler items, yesterday's open loops, overnight queue. Helps plan the day and captures anything from overnight thinking. |
| `/afternoon` | Mid-day recalibration. Checks whether you've drifted from priorities, helps reprioritise remaining time. Quick 2-5 min reset. |
| `/goodnight` | End-of-day report. Inventories the day's work, captures open loops, sets tomorrow's priority queue, checks for stranded work product. |

**Session lifecycle:**

| Skill | What it does |
|---------|-------------|
| `/pickup` | Session start. Shows your Works in Progress, or pass a topic/keyword/file path to jump straight into a specific project. Loads project hub and last session context on selection. |
| `/park` | Session capture ("shutdown complete"). Quality gate, session summary, open loops, WIP update, reference graph tracing, bidirectional linking. Args: `--quick`, `--full`, `--auto`. |

**Extended breaks:**

| Skill | What it does |
|---------|-------------|
| `/hibernate` | Pre-break snapshot before travel or sabbatical. Captures all active projects, open loops, and context into a durable snapshot file. Interactive interview about break duration and return priorities. |
| `/awaken` | Post-break context restoration. Loads the hibernate snapshot, runs a reorientation interview, updates project statuses with post-break reality. Args: `--date=YYYY-MM-DD`. |

**Project lifecycle:**

| Skill | What it does |
|---------|-------------|
| `/start-project` | Creates a new project file with goal/status/next actions, adds to Works in Progress, optionally links to initiatives. Args: project name, `--initiative=NAME`, `--backlog`. |
| `/complete-project` | Formally archives a completed/abandoned/superseded project. Moves to archive, removes from WIP, logs completion. Args: optional project name. |

**Reviews:**

| Skill | What it does |
|---------|-------------|
| `/weekly-review` | Weekly aggregation: accomplishments, project movement, aged open loops (14+ days), WIP integrity, corrections log review. Generates a review file. Delegates structural maintenance to `/weekly-hygiene`. |
| `/quarterly-review` | Deep strategic review: projects completed/stalled/abandoned, priority shifts, next quarter's Big Rocks, `Context - Direction.md` overhaul. Consumes `/quarterly-hygiene` for vault structural health. |
| `/quarterly-hygiene` | Quarterly deep vault maintenance: full context-file re-read (non-temporal drift), CRM stale-entry review, oversized/near-empty files, 90-day-rolling session-log archiving into `YYYY/` folders. Mechanical companion to `/quarterly-review`. |

**Learning loops:**

| Skill | What it does |
|---------|-------------|
| `/oops` | Captures a mistake. Extracts what went wrong, the correction, and the transferable lesson. Appends to Claude Corrections Log. Checks for patterns warranting promotion to CLAUDE.md. |
| `/win` | Captures a success. Extracts what went well, why, and the transferable pattern. Appends to Claude Wins Log. The counterpart to `/oops`. |

**Research & thinking:**

| Skill | What it does |
|---------|-------------|
| `/research-assistant` | Vault-first deep search. Systematically searches the Obsidian vault before suggesting external research. Presents "What We Know" vs "What We Don't Know" with source citations. |
| `/patterns` | Cross-file pattern finder. Searches broadly for a topic and synthesises recurring themes, evolution over time, contradictions, and gaps. Args: search term (e.g., `/patterns meditation`). |
| `/thinking-partner` | Socratic mode. Asks questions, surfaces assumptions, challenges framing — exploration through questions, not solutions. Stays in thinking mode until you explicitly request implementation. |
| `/second-opinion` | Independent review of work or decisions. Runs a cross-model panel in parallel, or brings the same reviewers back for iterative deepening. Aliases: `/tiebreak`, `/panel`. |
| `/landscape-scan` | Scans curated sources (and/or a supplied URL pile) for AI / Claude Code / PKM developments and digests them against your current workflow. Run weekly or as needed. |

**Prioritisation:**

| Skill | What it does |
|---------|-------------|
| `/longpoles` | Surfaces all `[LP]` (longpole) tagged items across the vault — critical-path items that block other work. |
| `/cornerstones` | Surfaces high-value foundational tasks tagged `[CS]` across the vault. |
| `/guillotines` | Surfaces all `[GT]` (guillotine) tagged items across the vault — hard-deadline tasks that foreclose an option or cause irreversible loss if missed, sorted by how close the blade is. |

**Utilities:**

| Skill | What it does |
|---------|-------------|
| `/de-ai-ify` | Voice restoration editor. Transforms AI-generated text into your authentic writing voice by stripping cliches, hedging, corporate-speak, and formulaic structure. |
| `/reply` | Drafts a reply to an inbound message with voice matching and CRM context. Always writes drafts to scratchpad. |
| `/transcribe` | Transcribes audio files or YouTube videos using WhisperX (distil-large-v3) with optional speaker diarisation. Requires a local GPU — see `/transcribecloud` for the no-GPU path. |
| `/transcribecloud` | Batch-transcribes audio/video on rented GPU cloud — for large jobs or when there's no local GPU. The cloud counterpart to `/transcribe`. |
| `/podcast-digest` | Digests an informational podcast/talk episode from a URL into a cruxes-first written summary (with jump-to timestamps) so you can get the content without listening. Uses a published transcript when one exists, else transcribes the audio itself with WhisperX (the `/transcribe` core). Descriptive only — never rates the episode. |
| `/ocr` | Extracts text and structured content from image screenshots (chat logs, social posts, documents). Local OCR by default, with a Claude post-pass for structure. |
| `/inbox-processor` | Processes `02 Inbox/` items using the NIPARAS decision tree, categorises each, and routes to its permanent vault location. |
| `/weekly-hygiene` | Vault structural maintenance: WIP metrics, broken links, stale items, orphaned files, tickler past-due scan. Can run standalone or as precursor to `/weekly-review`. |

**Audit & provenance:**

| Skill | What it does |
|---------|-------------|
| `/audit` | Rigorous five-layer evaluation of any implementation (code, config, plans, processes). Layers: approach → environment → migration → implementation → execution. Iterates until clean. |
| `/provenance` | Logs a SHA256 hash of the current session file to the AI Provenance Log. Optionally creates OpenTimestamps proofs anchored to the Bitcoin blockchain. For academic disclosure/audit defence. Verification is handled automatically by `/weekly-hygiene`. |
| `/verify-provenance` | _Deprecated._ Provenance verification now lives in `/weekly-hygiene` (step 14b); this skill just redirects there. |

**Infrastructure:**

| Skill | What it does |
|---------|-------------|
| `/setup` | First-run onboarding. Detects OS, checks prerequisites (VAULT_PATH, bash version, git remote), then runs a conversational interview to personalise CLAUDE.md and create context file stubs. Idempotent — safe to re-run. |
| `/update` | Pulls latest OpenCairn skills/scripts from the upstream GitHub template repo. Previews changes before applying. Args: `--dry-run`, `--force`. |

**Aliases:**

| Skill | Alias for |
|---------|-----------|
| `/checkpoint` | `/park` |
| `/regroup` | `/afternoon` |
| `/shutdown` | `/goodnight` |

Scripts live in `.claude/scripts/` and require the `VAULT_PATH` environment variable.

</details>

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

**Context-aware status line.** Claude Code's default status line shows absolute tokens. A percentage with colour-coded warnings is more useful - see [hedwards.dev/claude-code-tips/](https://hedwards.dev/claude-code-tips/) for the setup script. Startup skills (`/morning`, `/pickup`, etc.) consume significant context on their own - a fresh session typically starts around 15-20% just from loading context files and skill prompts, so your usable working window is smaller than the raw percentage suggests.

**More tips** on context management, workflow patterns, keyboard shortcuts, and MCP servers: [hedwards.dev/claude-code-tips/](https://hedwards.dev/claude-code-tips/)

---

## Credits

Inspired by [claudesidian](https://github.com/heyitsnoah/claudesidian), [obsidian-claude-pkm](https://github.com/ballred/obsidian-claude-pkm), [The Neuron](https://www.theneuron.ai/explainer-articles/how-to-turn-claude-code-into-your-personal-ai-assistant). Built with Claude Code.

---

## Licence

[CC BY-NC 4.0](LICENSE) - Free for personal use. [Contact me](mailto:harrisonaedwards@gmail.com) for commercial licencing.
