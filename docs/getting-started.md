# Getting started

[README](../README.md) · [Skill reference](skills.md)

Choose a [full vault](#full-vault) for session continuity and planning, or the [Claude Code plugin](#claude-code-plugin) to use standalone skills in an existing project.

## Prerequisites

For the full vault, install:

- [Git](https://git-scm.com/downloads).
- Python 3, available as `python3` on your agent's `PATH`.
- Bash 4.2 or later, available as `bash`.
- [ripgrep](https://github.com/BurntSushi/ripgrep), available as `rg`.
- [Claude Code](https://code.claude.com/docs/en/overview) or [Codex CLI](https://developers.openai.com/codex/cli/), installed and authenticated.

[Obsidian](https://obsidian.md/) is recommended for browsing and editing the vault. Workflows that move linked notes, such as `set-project-status`, need Obsidian's link-healing operations; see the relevant [skill instructions](skills.md#project-lifecycle).

| Platform | Shell setup |
|---|---|
| Linux | Use Bash and install the prerequisites through your distribution's package manager. |
| macOS | Install a current Bash with Homebrew (`brew install bash`). Make sure the Homebrew binary precedes the system Bash on `PATH`. Your interactive shell can remain Zsh. |
| Windows | Run the shell examples in Git Bash, included with Git for Windows. Ensure `python3` and `rg` are executable from that shell and the agent's shell. A PowerShell-only installation does not provide the shared Bash runtime. |

Check from the terminal you will use to launch your agent:

```bash
git --version
python3 --version
bash --version
rg --version
```

Each command should print a version; Bash must be at least 4.2. A missing command needs fixing before you continue. Media workflows and optional hooks have [additional requirements](skills.md#requirements).

## Full vault

Run the [clone commands in the README](../README.md#full-vault) to create a new vault. Renaming the upstream remote to `template` keeps it separate from any remote you later use for your personal vault.

If you already have notes, follow the [existing-vault guidance](#already-have-a-vault) before copying anything into them.

### Keep the vault path between sessions

Add this line to your shell configuration, using the same absolute path you chose when cloning:

```bash
export VAULT_PATH="/path/to/your/obsidian/vault"
```

Use `~/.bashrc` for Bash or `~/.zshrc` for Zsh. With Git Bash, ensure your login profile loads that file, or put the export in `~/.bash_profile`. Open a new terminal and verify:

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

Success prints `VAULT_PATH=` followed by your vault path. An unset variable, a missing script or a different path means the shell configuration or clone location needs correcting. Start your agent from that terminal so it inherits the variable.

### Claude Code

Launch from the vault:

```bash
cd "$VAULT_PATH"
claude
```

Inside Claude Code, run:

```text
/setup
```

The setup interview checks your environment, personalises the root `CLAUDE.md`, and creates context notes for the domains you choose. You can rerun it to revise your preferences.

An optional shell shortcut is:

```bash
alias cc='cd "$VAULT_PATH" && claude'
```

Add it beside the `VAULT_PATH` export if you want `cc` to open Claude Code in your vault.

**Optional hooks:** `/setup-hooks` enables the skill-edit survey and park acceleration hooks. It requires `jq`; these hooks are separate from the core setup. See the [hook instructions](../.claude/commands/setup-hooks.md) to select or remove them.

### Codex CLI

OpenCairn distributes Codex skills in [`codex/skills/`](../codex/skills/). Its updater manages the installed copies under `${CODEX_HOME:-$HOME/.codex}/skills/`. From the cloned vault, copy the complete tree, including the shared support files:

```bash
cd "$VAULT_PATH"
OPENCAIRN_CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$OPENCAIRN_CODEX_ROOT/skills"
cp -Ri codex/skills/. "$OPENCAIRN_CODEX_ROOT/skills/"
```

The copy prompts before replacing existing files. If you have customised an existing skill, decline its overwrite and compare the copies before merging it. Keep the shared rules and their supplements together.

Next, install the generic vault instructions from [`codex/AGENTS.md`](../codex/AGENTS.md): copy that file to `${CODEX_HOME:-$HOME/.codex}/AGENTS.md` if no instruction file exists there. Otherwise, merge its vault-location and locking sections into your existing instructions. If you use `AGENTS.override.md`, merge into that active file instead; it takes precedence over `AGENTS.md`. See the [OpenAI instruction-loading guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

**Personalisation is manual.** There is no `$setup` or `$setup-hooks` skill. Add your preferences and a topic-to-context-file list to your active `AGENTS.md` (or override), using the root [`CLAUDE.md`](../CLAUDE.md) as an outline. Point it to the context hubs you use under `07 System/`, and use `$name` for Codex skill invocations.

Start a fresh Codex session from the vault:

```bash
cd "$VAULT_PATH"
codex
```

Type `$` to check that OpenCairn skills such as `pickup` and `park` are available. If they are missing, check the copy destination against your `CODEX_HOME` and restart Codex. Vault-backed skills also need the checkout's `.claude/scripts/`; `$update` and `$migrate` use the canonical procedures in `.claude/commands/`.

### Your first handoff

Pick a real task and work on it with the agent. If you want a project to appear in the active-project list, create it with `/start-project` or `$start-project`.

When you finish, run `/park` or `$park`. Check the resulting entry under `06 Archive/OpenCairn/Session Logs/`: it should capture the outcome and any unfinished work. In a new session, run `/pickup` or `$pickup` with the project name or topic. The agent should restore the relevant notes so you can continue.

You can open `$VAULT_PATH` in Obsidian at any point. Keep your notes backed up. The shared write scripts coordinate cooperating local processes; they do not resolve edits made independently on different synced machines.

## Claude Code plugin

Inside Claude Code, run:

```text
/plugin marketplace add OpenCairn/OpenCairn
/plugin install opencairn@opencairn
```

Plugin commands include the plugin name, for example `/opencairn:thinking-partner` or `/opencairn:shop`. This is Claude Code's [plugin namespace convention](https://code.claude.com/docs/en/plugins). The shorter `/name` examples elsewhere in this repository refer to the full-vault installation.

The plugin installs the workflows, without creating a personal vault or installing their external dependencies. Start with the [standalone skills](skills.md#requirements). To use session capture, planning or reviews, complete the [full-vault setup](#full-vault); the plugin alone is insufficient.

## Already have a vault?

Clone OpenCairn into a separate directory to inspect it before adapting your existing vault. You can ask your agent:

> Compare this template with my existing notes system. Which workflows fit, and what would each require?

The context-routing pattern and standalone skills can be adopted independently. Session and planning skills expect the NIPARAS folders and shared scripts, so copying only `park` and `pickup` is not a complete installation. Review the selected skills' requirements before merging folders or instructions.

`migrate` upgrades supported OpenCairn layouts; it is not a general importer for arbitrary notes systems.

## Updating and migration

For full-vault installations, run `/update` in Claude Code or `$update` in Codex. The updater compares infrastructure with upstream and asks you to review replacements. It preserves personal context and vault content during the ordinary update; a required migration is a separate step that can move or change vault files.

| Intent | Claude Code | Codex |
|---|---|---|
| Preview changes | `/update --dry-run` | `$update --dry-run` |
| Update from the main branch | `/update` | `$update` |
| Select a release | `/update --tag VERSION` | `$update --tag VERSION` |
| Apply a required vault migration | `/migrate` | `$migrate` |

Replace `VERSION` with a tag from [Releases](https://github.com/OpenCairn/OpenCairn/releases). Pinned updates require a verified signed tag. Configure verification using [CONTRIBUTING.md](../CONTRIBUTING.md#commit-signing) before using that mode.

If the updater directs you to migrate, complete that step and resume the update. Restart the agent afterwards to load the updated instructions. Codex updates review the live skill copies separately from the repository copies.

For a plugin-only installation, use Claude Code's plugin manager to update the plugin. OpenCairn's `update` workflow requires a full vault checkout.

## Further reading

- [Skill reference](skills.md): workflows, aliases and requirements.
- [Design document](../DESIGN.md): context routing, session records and shared runtime.
- [Walkthrough](https://hedwards.dev/cco-setup/): the original Claude Code setup guide.
- [Workflow tips](https://hedwards.dev/claude-code-tips/): context management and daily use.
