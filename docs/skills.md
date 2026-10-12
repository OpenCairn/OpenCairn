# Skill reference

[README](../README.md) · [Setup guide](getting-started.md)

Each skill is a workflow the agent follows. The command links below open its instructions, including arguments and prerequisites.

Use `/name` in a Claude Code full-vault installation, `/opencairn:name` with the [Claude Code plugin](getting-started.md#claude-code-plugin), and `$name` in Codex. `setup` and `setup-hooks` are Claude-only.

## Requirements

| Installation | Workflows |
|---|---|
| No vault required | `audit`, `second-opinion`, `thinking-partner`, `shop`, `book-stay`. Shopping and accommodation workflows skip their vault extras when no vault is configured. |
| No vault required; external tools needed | `ocr`, `transcribe`, `transcribecloud`, `podcast-digest`. Check the linked instructions for the selected engine and input type. |
| Full vault | Session, planning, review, archiving and other vault workflows below need the NIPARAS structure, `VAULT_PATH` and shared runtime. `setup` establishes the initial configuration. |

Standalone workflows can still have dependencies: research needs web access, and additional review models need their own CLI or API access. OCR uses local extraction tools by default, transcription uses WhisperX locally or a paid cloud GPU, and podcast digests use published transcripts when available. The plugin does not install these tools for you.

## Sessions and daily planning

| Claude Code | Codex | Purpose |
|---|---|---|
| [/pickup](../.claude/commands/pickup.md) | [$pickup](../codex/skills/pickup/SKILL.md) | Show active projects, or restore a named project or topic. |
| [/park](../.claude/commands/park.md) | [$park](../codex/skills/park/SKILL.md) | Save session outcomes, close open loops and update affected project notes. |
| [/morning](../.claude/commands/morning.md) | [$morning](../codex/skills/morning/SKILL.md) | Review current work and reminders, then plan the day. |
| [/afternoon](../.claude/commands/afternoon.md) | [$afternoon](../codex/skills/afternoon/SKILL.md) | Check progress and adjust the remaining day's priorities. |
| [/goodnight](../.claude/commands/goodnight.md) | [$goodnight](../codex/skills/goodnight/SKILL.md) | Close the day, capture unfinished work and prepare the next day's plan. |
| [/hibernate](../.claude/commands/hibernate.md) | [$hibernate](../codex/skills/hibernate/SKILL.md) | Save project state and return priorities before an extended break. |
| [/awaken](../.claude/commands/awaken.md) | [$awaken](../codex/skills/awaken/SKILL.md) | Restore a pre-break snapshot and reassess priorities on return. |

## Project lifecycle

| Claude Code | Codex | Purpose |
|---|---|---|
| [/start-project](../.claude/commands/start-project.md) | [$start-project](../codex/skills/start-project/SKILL.md) | Create a project note with an objective and next actions. |
| [/set-project-status](../.claude/commands/set-project-status.md) | [$set-project-status](../codex/skills/set-project-status/SKILL.md) | Move a project between active, Cold and Backlog through Obsidian's link-healing move. |
| [/complete-project](../.claude/commands/complete-project.md) | [$complete-project](../codex/skills/complete-project/SKILL.md) | Archive a completed, abandoned or superseded project and record the outcome. |

## Reviews and maintenance

| Claude Code | Codex | Purpose |
|---|---|---|
| [/weekly-review](../.claude/commands/weekly-review.md) | [$weekly-review](../codex/skills/weekly-review/SKILL.md) | Review accomplishments, project movement, open loops and priorities. |
| [/weekly-hygiene](../.claude/commands/weekly-hygiene.md) | [$weekly-hygiene](../codex/skills/weekly-hygiene/SKILL.md) | Check vault structure, stale items, links and provenance records. |
| [/quarterly-review](../.claude/commands/quarterly-review.md) | [$quarterly-review](../codex/skills/quarterly-review/SKILL.md) | Reassess direction and choose priorities for the coming quarter. |
| [/quarterly-hygiene](../.claude/commands/quarterly-hygiene.md) | [$quarterly-hygiene](../codex/skills/quarterly-hygiene/SKILL.md) | Review context, contacts, logs and skill-library maintenance. |
| [/oops](../.claude/commands/oops.md) | [$oops](../codex/skills/oops/SKILL.md) | Record a mistake, its correction and a reusable lesson. |
| [/inbox-processor](../.claude/commands/inbox-processor.md) | [$inbox-processor](../codex/skills/inbox-processor/SKILL.md) | Sort captured items into their permanent vault locations. |

## Research, decisions and review

| Claude Code | Codex | Purpose |
|---|---|---|
| [/research-assistant](../.claude/commands/research-assistant.md) | [$research-assistant](../codex/skills/research-assistant/SKILL.md) | Search and synthesise existing vault knowledge before external research. |
| [/thinking-partner](../.claude/commands/thinking-partner.md) | [$thinking-partner](../codex/skills/thinking-partner/SKILL.md) | Explore a problem through questions and challenge its assumptions. |
| [/second-opinion](../.claude/commands/second-opinion.md) | [$second-opinion](../codex/skills/second-opinion/SKILL.md) | Get independent review of work or decisions, with follow-up rounds if needed. |
| [/audit](../.claude/commands/audit.md) | [$audit](../codex/skills/audit/SKILL.md) | Evaluate an implementation from problem framing through execution. |
| [/shop](../.claude/commands/shop.md) | [$shop](../codex/skills/shop/SKILL.md) | Clarify a purchase need, research options and recommend a decision. |
| [/book-stay](../.claude/commands/book-stay.md) | [$book-stay](../codex/skills/book-stay/SKILL.md) | Compare accommodation, verify rates and hand off booking. |
| [/landscape-scan](../.claude/commands/landscape-scan.md) | [$landscape-scan](../codex/skills/landscape-scan/SKILL.md) | Scan and digest curated sources for a selected topic. |

## Prioritisation

| Claude Code | Codex | Purpose |
|---|---|---|
| [/longpoles](../.claude/commands/longpoles.md) | [$longpoles](../codex/skills/longpoles/SKILL.md) | Find `[LP]` tasks that block other work. |
| [/cornerstones](../.claude/commands/cornerstones.md) | [$cornerstones](../codex/skills/cornerstones/SKILL.md) | Find high-value foundational tasks marked `[CS]`. |
| [/guillotines](../.claude/commands/guillotines.md) | [$guillotines](../codex/skills/guillotines/SKILL.md) | Find `[GT]` deadlines where missing the date forecloses an option. |

## Writing, media and reference material

| Claude Code | Codex | Purpose |
|---|---|---|
| [/de-ai-ify](../.claude/commands/de-ai-ify.md) | [$de-ai-ify](../codex/skills/de-ai-ify/SKILL.md) | Edit a draft to match your voice and remove formulaic AI phrasing. |
| [/reply](../.claude/commands/reply.md) | [$reply](../codex/skills/reply/SKILL.md) | Draft a reply using your writing preferences and contact context. |
| [/ocr](../.claude/commands/ocr.md) | [$ocr](../codex/skills/ocr/SKILL.md) | Extract and structure text from screenshots. |
| [/transcribe](../.claude/commands/transcribe.md) | [$transcribe](../codex/skills/transcribe/SKILL.md) | Transcribe audio or YouTube videos with local WhisperX. |
| [/transcribecloud](../.claude/commands/transcribecloud.md) | [$transcribecloud](../codex/skills/transcribecloud/SKILL.md) | Transcribe audio or video on a rented RunPod GPU. |
| [/podcast-digest](../.claude/commands/podcast-digest.md) | [$podcast-digest](../codex/skills/podcast-digest/SKILL.md) | Summarise a podcast or talk from a published transcript or transcription. |
| [/archive-transcript](../.claude/commands/archive-transcript.md) | [$archive-transcript](../codex/skills/archive-transcript/SKILL.md) | Save a published transcript with a synthesis header and verbatim body. |
| [/archive-article](../.claude/commands/archive-article.md) | [$archive-article](../codex/skills/archive-article/SKILL.md) | Save an article or paper as a reference note with synthesis and verified citations. |
| [/map-day](../.claude/commands/map-day.md) | [$map-day](../codex/skills/map-day/SKILL.md) | Turn an itinerary into an Organic Maps KML and a Markdown day-sheet. |

## Provenance

| Claude Code | Codex | Purpose |
|---|---|---|
| [/provenance](../.claude/commands/provenance.md) | [$provenance](../codex/skills/provenance/SKILL.md) | Request hashing and timestamp proofs at day-end, or attest a final work product immediately. |
| [/verify-provenance](../.claude/commands/verify-provenance.md) | [$verify-provenance](../codex/skills/verify-provenance/SKILL.md) | **Deprecated:** redirects to the provenance check in `weekly-hygiene`. |

## Setup and updates

| Claude Code | Codex | Purpose |
|---|---|---|
| [/setup](../.claude/commands/setup.md) | Not available | Check prerequisites and personalise the vault through an interview. |
| [/setup-hooks](../.claude/commands/setup-hooks.md) | Not available | Configure optional skill-edit and park hooks; requires `jq`. |
| [/update](../.claude/commands/update.md) | [$update](../codex/skills/update/SKILL.md) | Review and apply upstream infrastructure changes to a full vault checkout. |
| [/migrate](../.claude/commands/migrate.md) | [$migrate](../codex/skills/migrate/SKILL.md) | Apply pending migrations for supported OpenCairn vault layouts. |

For Codex installation and personalisation, use the [manual setup instructions](getting-started.md#codex-cli).

## Aliases

| Claude Code | Codex | Equivalent workflow |
|---|---|---|
| [/checkpoint](../.claude/commands/checkpoint.md) | [$checkpoint](../codex/skills/checkpoint/SKILL.md) | `park` |
| [/regroup](../.claude/commands/regroup.md) | [$regroup](../codex/skills/regroup/SKILL.md) | `afternoon` |
| [/shutdown](../.claude/commands/shutdown.md) | [$shutdown](../codex/skills/shutdown/SKILL.md) | `goodnight` |
