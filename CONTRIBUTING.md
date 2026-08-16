# Contributing to OpenCairn

## Development Workflow

**Template repo:** `~/repos/OpenCairn/` ([GitHub](https://github.com/OpenCairn/OpenCairn))

**Architecture:** Two copies of commands/scripts, synced bidirectionally by `/sync-template`:

```
Template repo (~/repos/OpenCairn/)
   .claude/   <-->  Personal (~/.claude/commands/, ~/.claude/scripts/)
   codex/skills/  <-->  Personal (~/.codex/skills/)
   codex/AGENTS.md  -->  Personal install bootstrap only (never reverse-synced)
                    |
                 GitHub
```

`~/.claude/commands/` and `~/.claude/scripts/` contain **copies** (not symlinks) of the template files. `/sync-template` classifies each file as identical, diverged, template-only, or personal-only, and syncs per file with user confirmation for conflicts. Codex skills sync through the same run via their own lane. The repository's generic `codex/AGENTS.md` is an install bootstrap, not a reverse-sync source; a live `~/.codex/AGENTS.md` may contain private local instructions and must never be propagated into the repository.

The two trees are deliberately asymmetric: `.claude/` is a **live load path** — Claude Code reads `.claude/commands/` and executes `.claude/scripts/` in place when the repo is cloned as a vault, and the plugin manifest points at it — whereas `codex/` is a **distribution tree** that users copy out to `~/.codex/` (Codex CLI has no per-project skills convention). Don't rename `.claude/` for symmetry; the path is load-bearing.

### Edit → Test → Sync → Push

1. **Edit** commands in `~/repos/OpenCairn/.claude/commands/` (the template repo is the source of truth); edit Codex skills in `~/repos/OpenCairn/codex/skills/`
2. **Run** `/sync-template` to copy changes to `~/.claude/commands/` and `~/.codex/skills/` for testing; review generic `codex/AGENTS.md` changes manually
3. `/sync-template` handles the personal info check, commit, and push

### Personal-Only Commands

Some commands are personal and not part of the template (e.g. `ralph.md`, `sync-template.md`). These live only in `~/.claude/commands/` and `/sync-template` skips them.

### Codex Rendering Integrity

`codex/render-map.json` records the Claude source and Codex rendering for every ported skill and shared support file. The files are deliberately rewritten for each harness rather than generated, so their recorded hashes are a review gate, not a claim that their text should match.

After editing a mapped source or rendering, review the pair and update the Codex file if needed. Then acknowledge only the pairs you reviewed:

```bash
python3 .github/scripts/validate_codex_renderings.py --acknowledge morning park
python3 .github/scripts/validate_codex_renderings.py --check
```

`--check` passes with exit 0 and a `validation passed` line. A missing file, unregistered rendering, invalid `SKILL.md` frontmatter, or changed hash exits 1 and names the affected pair. `/sync-template` runs the same check before pushing, and GitHub Actions runs it on pushes and pull requests. Never acknowledge a pair without reading its source and rendering.

### No Personal Examples

All examples in template commands must be generic (e.g. "Workshop (3h)", "Dinner with Sam"). Never use contributor-specific details (project names, people, locations) that other users would need to change.

### Single Personalisation Point

Users configure one environment variable:

```bash
# Add to ~/.bashrc or ~/.zshrc
export VAULT_PATH=/path/to/your/obsidian/vault
```

All commands derive paths from `VAULT_PATH`. No other configuration needed.

### Pre-Commit Check

Before pushing, verify no personal information has leaked into the template:

```bash
cd ~/repos/OpenCairn
grep -rE -i "your_name|your_home_path|your_personal_details" \
  --include="*.md" --include="*.sh" --include="*.py" --include="*.json" | grep -v ".git/"
# Should return nothing
```

Substitute your own identifiers (name, home path, workplace, etc.) for the placeholders above.

`/sync-template` Phase 4 runs this automatically.

### Breaking Changes

OpenCairn has real external users. Prompt-level changes (command `.md` files) are soft — Claude adapts. Structural changes (directories, filenames, script arguments) are hard breaks and need migration guidance or a changelog entry. At minimum, flag breaking structural changes in commit messages.

## Commit Signing

All commits to this repository are signed with SSH keys. GitHub shows a "Verified" badge on each commit. `/update` checks whether the template commit is signed and emits an informational message if your local git isn't configured to verify signatures (not a security warning — the command still runs). Pinned mode (`/update --tag VERSION`) is stricter: it verifies the release tag's signature and **fails closed** — an unsigned, lightweight, or unverifiable tag aborts rather than continuing.

To enable local verification:

```bash
# 1. Create an allowed_signers file with the maintainer's public key
echo "harrisonaedwards@gmail.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAII2W2hHbB2SqhuxctJVhXBgEAOWI0SKJxp/WN96Gtibq harrison-signing-key" > ~/.ssh/allowed_signers

# 2. Tell git to use it
git config --global gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
```

After this, `/update` will show "Template commit is signed and verified" on each run.
