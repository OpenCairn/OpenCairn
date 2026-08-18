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
  <a href="https://github.com/OpenCairn/OpenCairn/releases/latest"><img src="https://img.shields.io/github/v/release/OpenCairn/OpenCairn?style=for-the-badge" alt="Latest release"></a>&nbsp;
  <a href="LICENSE"><img src="https://img.shields.io/badge/licence-CC%20BY--NC%204.0-blue?style=for-the-badge" alt="Licence: CC BY-NC 4.0"></a>&nbsp;
  <a href="https://github.com/OpenCairn/OpenCairn"><img src="https://img.shields.io/github/stars/OpenCairn/OpenCairn?style=for-the-badge" alt="GitHub stars"></a>
</p>

OpenCairn is a local-first workflow system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Codex CLI](https://developers.openai.com/codex/cli/), and [Obsidian](https://obsidian.md/). It preserves project state between AI sessions, turns review routines into reusable skills, and keeps the durable context in plain Markdown files you control.

<p align="center">
  <a href="#quick-start">Quick start</a> · <a href="https://hedwards.dev/cco-setup/">Setup guide</a> · <a href="https://hedwards.dev/claude-code-obsidian/">How it was built</a> · <a href="https://hedwards.dev/claude-code-tips/">Tips</a>
</p>

---

## The handoff between sessions

AI sessions are good at the current conversation and poor at continuity. OpenCairn gives each session a deliberate handoff: `/park` records what changed and what remains open, then `/pickup` restores that state when you return. Codex uses the same skills with `$park` and `$pickup`.

```text
> /pickup

Active projects: Japan Trip, Website Redesign
Last session: Japan Trip

Open loops:
 [ ] Book ryokan - narrowed to 2 options, need to decide
 [ ] Figure out JR pass vs individual tickets
 [ ] Ask Mike about that ramen place in Osaka

Next up: Kyoto logistics
What would you like to pick up?
```

The handoff lives in your vault rather than in model memory, so it remains inspectable, editable, and available to either harness.

---

## Choose your starting point

| If you want... | Start with... |
|---|---|
| Session continuity, daily planning, reviews, and durable personal context | [Clone the full vault](#quick-start) |
| Reusable Claude Code skills inside an existing project | [Install the plugin](#claude-code-plugin) |
| The same workflows in Codex CLI | [Install the Codex renderings](#codex-cli) |

The portable skills include `/audit`, `/second-opinion`, `/thinking-partner`, `/shop`, and `/book-stay`. They work without a vault. Media skills such as `/ocr`, `/transcribe`, and `/podcast-digest` also work standalone once their external dependencies are installed.

### Claude Code plugin

```text
/plugin marketplace add OpenCairn/OpenCairn
/plugin install opencairn@opencairn
```

This installs the skills only. Vault-backed skills such as `/park`, `/morning`, and the review passes still require the [NIPARAS folder structure](#folder-structure-niparas) and `VAULT_PATH`.

---

## Quick start

### Full vault

**Prerequisites:** [Git](https://git-scm.com/downloads), Python 3, [ripgrep](https://github.com/BurntSushi/ripgrep), and either [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or [Codex CLI](https://developers.openai.com/codex/cli/). Obsidian is optional but recommended.

```bash
# Choose where the vault will live
export VAULT_PATH="/path/to/your/obsidian/vault"

git clone https://github.com/OpenCairn/OpenCairn.git "$VAULT_PATH"
cd "$VAULT_PATH"

# Keep the template remote separate from your own future vault remote
git remote rename origin template

chmod +x .claude/scripts/*.sh

# Add VAULT_PATH and this alias to ~/.bashrc or ~/.zshrc
alias cc='cd "$VAULT_PATH" && claude'
```

Start Claude Code with `cc`, then run the setup interview:

```text
> /setup
> /park
> /pickup
```

Open `$VAULT_PATH` as a vault in Obsidian if you use it. The [step-by-step setup guide](https://hedwards.dev/cco-setup/) covers shell configuration, personalisation, and optional sync.

### Codex CLI

The `codex/` directory contains Codex-native renderings of the workflows. After cloning the repository, install them into your Codex home:

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_ROOT/skills"
cp -r codex/skills/* "$CODEX_ROOT/skills/"
```

Copy `codex/AGENTS.md` to `$CODEX_ROOT/AGENTS.md` if you do not have global instructions yet; otherwise merge its vault sections into your existing file. Start Codex from the vault and invoke skills with `$name`, for example `$pickup`. Vault-backed skills use the same `VAULT_PATH` and shared runtime scripts as Claude Code.

---

## What the full system adds

| Capability | What it does |
|---|---|
| Session continuity | `/park` captures decisions, open loops, touched files, and pickup context; `/pickup` restores them. |
| Daily execution | `/morning`, `/afternoon`, and `/goodnight` frame the day, catch drift, and close open loops. |
| Periodic review | Weekly and quarterly passes surface stalled projects, maintenance debt, and priority drift. |
| Context routing | A small top-level instruction file loads only the domain and project context relevant to the current task. |
| Safe local writes | Locking and atomic-write scripts protect a vault used by concurrent agent sessions or synced machines. |
| Independent review | `/audit` and `/second-opinion` can dispatch an optional Claude, Gemini, Codex, and Grok panel. |

The core design is simple: the files are the context. Each session writes durable outcomes back to the vault, and the next session reads those files rather than relying on a model-generated memory of earlier conversations.

---

## Who this is for

**Good fit:**

- You manage several projects or life domains in parallel
- You want an AI collaborator to retain useful state across sessions
- You prefer local Markdown over a hosted, proprietary memory layer
- You are comfortable working from a terminal and customising a system

**Less good fit:**

- You just want quick answers to quick questions
- You want a turnkey GUI with no setup or maintenance

---

## Folder structure (NIPARAS)

NIPARAS extends Tiago Forte's [PARA method](https://fortelabs.com/blog/para/) with **Now** (active working memory), **Inbox** (capture), and **System** (agent instructions and context).

| Folder | Purpose | Examples |
|--------|---------|----------|
| **01 Now** | Active working memory | This Week, Tickler, scratch notes |
| **02 Inbox** | Capture point for new stuff before it's organised | Quick notes, web clippings, ideas to process |
| **03 Projects** | Discrete efforts with an end state ("done" looks like X) | "Plan Japan trip", "Launch website", "Learn Python" |
| **04 Areas** | Domains of life you maintain indefinitely, with nested resources | Health (supplements, bloodwork), Photography (portfolios, gear), Finances (tax, investments) |
| **05 Resources** | Generic reference material that doesn't belong to an Area yet | Journal entries, recipes, meeting notes, misc reference |
| **06 Archive** | Immutable write-once records (logs, reports, snapshots) | OpenCairn session logs, daily/weekly reports, scans |
| **07 System** | Agent instructions and system context | CLAUDE.md, context hubs, direction, decision/corrections/wins logs |

Areas are domains you actively maintain, with their reference material nested inside them. Resources is a staging ground for material that does not belong to an Area yet.

Context navigation is hierarchical: the agent reads the top-level instructions, loads the relevant domain hub, then follows links to project or detail files only when needed. The [blog series](https://hedwards.dev/hierarchical-context-navigation/) explains the pattern.

---

## Updating and migration

Run `/update` in Claude Code or `$update` in Codex to pull current skills and scripts. The updater previews repository changes, protects local customisations, and hands incompatible vault layouts to `/migrate` or `$migrate` before continuing.

Release tags from `v0.7.13` onward are SSH-signed annotated tags. Pinned updates verify the tag and fail closed if it is unsigned or cannot be verified. See [CONTRIBUTING.md](CONTRIBUTING.md#commit-signing) for local signature-verification setup.

---

## All skills

<details>
<summary><strong>Click to expand the full skill reference</strong></summary>

> **Standalone (no vault needed):** `/audit`, `/second-opinion`, `/thinking-partner`, `/shop`, `/book-stay` (`/shop` and `/book-stay` skip their vault-only extras), plus `/ocr`, `/transcribe`, `/transcribecloud`, and `/podcast-digest` once their external tooling is installed. Everything else assumes the NIPARAS vault structure and a `VAULT_PATH`.
>
> **Codex CLI:** Native renderings live in [`codex/skills/`](codex/skills/) and use `$name` rather than `/name`.

**Daily rhythm:**

| Skill | What it does |
|---------|-------------|
| `/morning` | Start-of-day check-in. Surfaces active projects, tickler items, yesterday's open loops, overnight queue. Helps plan the day and captures anything from overnight thinking. |
| `/afternoon` | Mid-day recalibration. Checks whether you've drifted from priorities, helps reprioritise remaining time. Quick 2-5 min reset. |
| `/goodnight` | End-of-day report. Inventories the day's work, captures open loops, sets tomorrow's priority queue, checks for stranded work product. |

**Session lifecycle:**

| Skill | What it does |
|---------|-------------|
| `/pickup` | Session start. Shows your active projects, or pass a topic/keyword/file path to jump straight into a specific project. Loads project hub and last session context on selection. |
| `/park` | Session capture and open-loop closure. Quality gate, session summary, open loops, project-doc update, reference graph tracing, bidirectional linking. Args: `--quick`, `--full`, `--auto`. |

**Extended breaks:**

| Skill | What it does |
|---------|-------------|
| `/hibernate` | Pre-break snapshot before travel or sabbatical. Captures all active projects, open loops, and context into a durable snapshot file. Interactive interview about break duration and return priorities. |
| `/awaken` | Post-break context restoration. Loads the hibernate snapshot, runs a reorientation interview, updates project statuses with post-break reality. Args: `--date=YYYY-MM-DD`. |

**Project lifecycle:**

| Skill | What it does |
|---------|-------------|
| `/start-project` | Creates a new project doc (bucket frontmatter, Current Objective, Next Actions) in the `03 Projects/` root, where creation is registration. Optionally links to initiatives. Args: project name, `--initiative=NAME`, `--backlog`. |
| `/complete-project` | Formally archives a completed/abandoned/superseded project. Moves the project doc out of the `03 Projects/` root to the Area's `Archive/`, logs completion. Args: optional project name. |

**Reviews:**

| Skill | What it does |
|---------|-------------|
| `/weekly-review` | Weekly aggregation: accomplishments, project movement, aged open loops (14+ days), project-doc integrity, corrections log review. Generates a review file. Delegates structural maintenance to `/weekly-hygiene`. |
| `/quarterly-review` | Deep strategic review: projects completed/stalled/abandoned, priority shifts, next quarter's Big Rocks, `Context - Direction.md` overhaul. Consumes `/quarterly-hygiene` for vault structural health. |
| `/quarterly-hygiene` | Quarterly deep vault maintenance: full context-file re-read (non-temporal drift), CRM stale-entry review, corrections-log index refresh, 90-day-rolling session-log archiving into `YYYY/` folders, skill-library flywheel audit, cross-model panel model-currency check. Mechanical companion to `/quarterly-review`. |

**Learning loops:**

| Skill | What it does |
|---------|-------------|
| `/oops` | Captures a mistake. Extracts what went wrong, the correction, and the transferable lesson. Appends to Claude Corrections Log. Checks for patterns warranting promotion to CLAUDE.md. |

**Research & thinking:**

| Skill | What it does |
|---------|-------------|
| `/research-assistant` | Vault-first deep search. Systematically searches the Obsidian vault before suggesting external research. Presents "What We Know" vs "What We Don't Know" with source citations. |
| `/patterns` | Cross-file pattern finder. Searches broadly for a topic and synthesises recurring themes, evolution over time, contradictions, and gaps. Args: search term (e.g., `/patterns meditation`). |
| `/thinking-partner` | Socratic mode. Asks questions, surfaces assumptions, and challenges framing through questions. Stays in thinking mode until you explicitly request implementation. |
| `/second-opinion` | Independent review of work or decisions. Runs a cross-model panel in parallel, or brings the same reviewers back for iterative deepening. |
| `/shop` | Purchase decision support. Clarifies what you actually need and why (open probing + a structured quiz), then researches current candidates and recommends. "Don't buy" is a valid verdict. Args: optional item (e.g. `/shop standing desk`), `--quick` for low-stakes buys. |
| `/landscape-scan` | Topic-parameterised scan + digest of curated sources (and/or a supplied URL pile). Default topic is the AI / Claude Code / PKM landscape, assessed against your current workflow; pass a topic (e.g. `cybersec`) to run a different profile. Run weekly or as needed. |

**Prioritisation:**

| Skill | What it does |
|---------|-------------|
| `/longpoles` | Surfaces all `[LP]` (longpole) tagged items across the vault: critical-path items that block other work. |
| `/cornerstones` | Surfaces high-value foundational tasks tagged `[CS]` across the vault. |
| `/guillotines` | Surfaces all `[GT]` (guillotine) tagged items across the vault: hard-deadline tasks that foreclose an option or cause irreversible loss if missed, sorted by how close the blade is. |

**Utilities:**

| Skill | What it does |
|---------|-------------|
| `/de-ai-ify` | Voice restoration editor. Transforms AI-generated text into your authentic writing voice by stripping cliches, hedging, corporate-speak, and formulaic structure. |
| `/reply` | Drafts a reply to an inbound message with voice matching and CRM context. Always writes drafts to scratchpad. |
| `/transcribe` | Transcribes audio files or YouTube videos using WhisperX (distil-large-v3) with optional speaker diarisation. Requires a local GPU; see `/transcribecloud` for the no-GPU path. |
| `/transcribecloud` | Batch-transcribes audio/video on a rented cloud GPU for large jobs or when there is no local GPU. The cloud counterpart to `/transcribe`. |
| `/podcast-digest` | Digests an informational podcast/talk episode from a URL into a cruxes-first written summary (with jump-to timestamps) so you can get the content without listening. Uses a published transcript when one exists, else transcribes the audio itself with WhisperX (the `/transcribe` core). It describes the episode without rating it. |
| `/archive-transcript` | Archives a podcast/talk transcript from a URL into the vault with a verbatim body and synthesis header, without routing the full text through context or letting a formatting hook corrupt the quotes. The capture counterpart to `/podcast-digest`. |
| `/archive-article` | Archives an article (research paper, clinical study, technical piece, or news report) into the vault as a structured reference note with synthesis, citation metadata, primary-source discovery, and verified wikilinks. The article counterpart to `/archive-transcript`. |
| `/ocr` | Extracts text and structured content from image screenshots (chat logs, social posts, documents). Local OCR by default, with a Claude post-pass for structure. |
| `/inbox-processor` | Processes `02 Inbox/` items using the NIPARAS decision tree, categorises each, and routes to its permanent vault location. |
| `/process-wm` | Processes Working Memory fresh captures through a reviewable checklist, then routes or deletes every reviewed item. |
| `/weekly-hygiene` | Vault structural maintenance: project-doc metrics, broken links, stale items, orphaned files, tickler past-due scan. Can run standalone or as precursor to `/weekly-review`. |
| `/book-stay` | Hotel-booking pipeline: quizzes preferences (ranked hard requirements), researches candidates with region-aware channel advice, live-verifies finalists with the user pulling prices, hands off the booking, then fans the confirmation out across the vault's trip docs. |
| `/map-day` | Turns a day's itinerary (a This Week date, or a pasted list of places) into a phone-glanceable Organic Maps KML plus a tight markdown day-sheet. Geocodes each stop via OSM, orders them around fixed-time anchors, and emits numbered pins + a route line. Offline-first; works in or out of China. |

**Audit & provenance:**

| Skill | What it does |
|---------|-------------|
| `/audit` | Layered evaluation of any implementation (code, config, plans, processes): problem framing → approach → environment → migration → implementation → execution. Iterates until clean. |
| `/provenance` | Logs a SHA256 hash of the current session file to the AI Provenance Log. Optionally creates OpenTimestamps proofs anchored to the Bitcoin blockchain. For academic disclosure/audit defence. Verification is handled automatically by `/weekly-hygiene`. |
| `/verify-provenance` | _Deprecated._ Provenance verification now lives in `/weekly-hygiene` (step 13b); this skill just redirects there. |

**Infrastructure:**

| Skill | What it does |
|---------|-------------|
| `/setup` | First-run onboarding. Detects OS, checks prerequisites (VAULT_PATH, bash version, git remote, python3), then runs a conversational interview to personalise CLAUDE.md and create context file stubs. It is idempotent and safe to re-run. |
| `/update` | Pulls latest OpenCairn skills/scripts from the upstream GitHub template repo, gates incompatible vault layouts, previews changes, and reviews live Codex copies. Args: `--dry-run`, `--force`, `--tag VERSION`. Codex: `$update`. |
| `/migrate` | Runs versioned vault migrations, including the resumable shared-archive namespace migration, then any outstanding legacy project-doc task components. Codex: `$migrate`. |
| `/setup-hooks` | Opt in to OpenCairn's optional hooks, in two independent sets: `skill-edit` (a Stop hook nudging a sibling-skill review when you edit a skill) and `park` (a write-ledger for exact file enumeration, plus a mid-session snapshot that makes `/park` cheaper). Usage `/setup-hooks [skill-edit\|park\|all] [--remove]`; default `all`. Idempotently wires into `settings.json`. Needs `jq`. |

**Aliases:**

| Skill | Alias for |
|---------|-----------|
| `/checkpoint` | `/park` |
| `/regroup` | `/afternoon` |
| `/shutdown` | `/goodnight` |

Scripts live in `.claude/scripts/` and require the `VAULT_PATH` environment variable.

</details>

---

## Already have a system?

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

Inspired by [claudesidian](https://github.com/heyitsnoah/claudesidian), [obsidian-claude-pkm](https://github.com/ballred/obsidian-claude-pkm), [The Neuron](https://www.theneuron.ai/explainer-articles/how-to-turn-claude-code-into-your-personal-ai-assistant). Built with Claude Code and Codex.

---

## Licence

[CC BY-NC 4.0](LICENSE): free for personal use. [Contact me](mailto:harrisonaedwards@gmail.com) for commercial licencing.
