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

OpenCairn gives your AI sessions continuity by saving decisions, open tasks and project context in local Markdown files, so you can return to a project without explaining it again.

It combines a personal knowledge vault with reusable workflows for [Claude Code](https://code.claude.com/docs/en/overview) and [Codex CLI](https://developers.openai.com/codex/cli/). [Obsidian](https://obsidian.md/) is an optional interface for reading and organising the files.

<p align="center">
  <a href="#quick-start">Quick start</a> · <a href="docs/getting-started.md">Setup guide</a> · <a href="docs/skills.md">Skill reference</a> · <a href="DESIGN.md">Architecture</a>
</p>

## Who this is for

OpenCairn suits people managing projects and life admin who want useful context to survive between AI sessions. You should be comfortable using a terminal and adapting a Markdown-based system to your own routines.

## The handoff between sessions

Work with the agent as usual, then run `/park` to record the outcome and what remains open. In a later session, `/pickup` loads the relevant project and session notes. In Codex, use `$park` and `$pickup`.

An illustrative handoff in Claude Code:

```text
> /park

Saved: Website redesign
Decision: Keep the existing publishing platform.
Open: Choose a homepage layout.
Next: Compare the two draft layouts.

[In a new session]

> /pickup Website redesign

Loaded the project and last session.
You kept the publishing platform. The homepage layout is still open.
Ready to compare the drafts.
```

You can read and edit the handoff notes yourself, or continue the work with either agent.

## What the full system adds

Skills are written instructions the agent follows when you invoke them.

| Workflow | What it helps you do |
|---|---|
| Session continuity | Save decisions and unfinished work with `park`; resume with `pickup`. |
| Daily planning | Plan the day with `morning`, adjust with `afternoon`, and close with `goodnight`. |
| Reviews | Use weekly and quarterly reviews to check progress, stalled projects and priorities. |
| Context routing | Keep personal and project context in linked notes that the agent reads when relevant. |
| Reusable tools | Research a topic, review a plan, compare purchases, draft replies or process media. |

## Choose your starting point

| What you want | Where to start |
|---|---|
| The vault, session continuity and planning routines | [Full vault](#full-vault), then choose Claude Code or Codex |
| Skills inside an existing Claude Code project | [Claude Code plugin](#claude-code-plugin) |
| Selected workflows in your current notes system | [Existing-system guidance](docs/getting-started.md#already-have-a-vault) |

## Quick start

### Full vault

You need Git, Python 3, Bash 4.2+, ripgrep, and an installed, authenticated Claude Code or Codex CLI. See the [setup guide](docs/getting-started.md#prerequisites) for platform notes.

Choose a new or empty directory for your vault, then run this in a Bash or Zsh terminal:

```bash
export VAULT_PATH="/path/to/your/obsidian/vault"

git clone https://github.com/OpenCairn/OpenCairn.git "$VAULT_PATH"
cd "$VAULT_PATH"
git remote rename origin template
chmod +x .claude/scripts/*.sh
```

[Save `VAULT_PATH` in your shell configuration](docs/getting-started.md#keep-the-vault-path-between-sessions), then choose your agent below. You can also open this directory as a vault in Obsidian.

### Claude Code

From the vault directory, run `claude`, then enter `/setup` for the personalisation interview. Work on a task and finish with `/park`; start a new session and use `/pickup` to return to it.

[Claude Code setup and optional hooks →](docs/getting-started.md#claude-code)

### Codex CLI

[Install the Codex skills and vault instructions](docs/getting-started.md#codex-cli), then run `codex` from the vault directory. Work on a task and finish with `$park`; use `$pickup` in a new session to resume.

Codex personalisation is manual: OpenCairn's `/setup` and `/setup-hooks` are Claude-only.

### Claude Code plugin

To use skills in an existing Claude Code project, enter:

```text
/plugin marketplace add OpenCairn/OpenCairn
/plugin install opencairn@opencairn
```

Plugin commands use a namespace, for example `/opencairn:thinking-partner`. You can use [standalone skills](docs/skills.md#requirements) without a vault; session and planning workflows still need the full vault and `VAULT_PATH`. [Plugin details →](docs/getting-started.md#claude-code-plugin)

## Folder structure (NIPARAS)

NIPARAS extends Tiago Forte's [PARA method](https://fortelabs.com/blog/para/) with **Now**, **Inbox** and **System**.

| Folder | Purpose |
|---|---|
| `01 Now` | Current plans, deferred reminders and scratch notes |
| `02 Inbox` | New material awaiting organisation |
| `03 Projects` | Work with a defined end state; active projects live at the root |
| `04 Areas` | Ongoing responsibilities and their reference material |
| `05 Resources` | Reference material that does not yet belong to an area |
| `06 Archive` | Historical records, session logs and review reports |
| `07 System` | Context hubs, preferences, templates and system conventions |

[Architecture and context routing →](DESIGN.md)

## All skills

The [skill reference](docs/skills.md) lists the workflows by purpose, with links to their instructions, requirements and availability in each agent.

## Updating and migration

Use `/update` in Claude Code or `$update` in Codex for full-vault installations. See the [update guide](docs/getting-started.md#updating-and-migration) for previews, migration and signed release selection.

## Already have a system?

Start with the workflows you need. The [adoption guide](docs/getting-started.md#already-have-a-vault) explains how to assess the template alongside your existing notes.

## Tips

Read [how OpenCairn was built](https://hedwards.dev/claude-code-obsidian/), the [context navigation series](https://hedwards.dev/hierarchical-context-navigation/), or [workflow and context-management tips](https://hedwards.dev/claude-code-tips/).

## Contributing

Issues and proposals are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and contributor licence agreement.

## Credits

Inspired by [claudesidian](https://github.com/heyitsnoah/claudesidian), [obsidian-claude-pkm](https://github.com/ballred/obsidian-claude-pkm), and [The Neuron](https://www.theneuron.ai/explainer-articles/how-to-turn-claude-code-into-your-personal-ai-assistant). Built with Claude Code and Codex.

## Licence

[CC BY-NC 4.0](LICENSE): free for personal use. [Contact me](mailto:harrisonaedwards@gmail.com) for commercial licencing.
