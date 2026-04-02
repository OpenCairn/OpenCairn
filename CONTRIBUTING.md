# Contributing to OpenCairn

## Development Workflow

**Template repo:** `~/repos/OpenCairn/` ([GitHub](https://github.com/OpenCairn/OpenCairn))

**Architecture:** Two copies of commands/scripts, synced bidirectionally by `/sync-template`:

```
Template repo (~/repos/OpenCairn/)  <-->  Personal (~/.claude/commands/, ~/.claude/scripts/)
                    |
                 GitHub
```

`~/.claude/commands/` and `~/.claude/scripts/` contain **copies** (not symlinks) of the template files. `/sync-template` classifies each file as identical, diverged, template-only, or personal-only, and syncs per file with user confirmation for conflicts.

### Edit → Test → Sync → Push

1. **Edit** commands in `~/repos/OpenCairn/.claude/commands/` (the template repo is the source of truth)
2. **Run** `/sync-template` to copy changes to `~/.claude/commands/` for testing
3. `/sync-template` handles the personal info check, commit, and push

### Personal-Only Commands

Some commands are personal and not part of the template (e.g. `ralph.md`, `sync-template.md`). These live only in `~/.claude/commands/` and `/sync-template` skips them.

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
  --include="*.md" --include="*.sh" --include="*.json" | grep -v ".git/"
# Should return nothing
```

Substitute your own identifiers (name, home path, workplace, etc.) for the placeholders above.

`/sync-template` Phase 4 runs this automatically.
