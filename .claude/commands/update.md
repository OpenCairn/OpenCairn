---
name: update
description: Update CCO commands and scripts from the template repository
parameters:
  - "--dry-run" - Preview changes without applying them
  - "--force" - Skip confirmation prompt
---

# Update - CCO Template Sync

You are updating the user's CCO commands and scripts from the upstream template repository. This updates **infrastructure only** (commands, scripts) — vault content and CLAUDE.md are never touched.

## What Gets Updated

| Category | Path | Action |
|----------|------|--------|
| Commands | `.claude/commands/*.md` | Overwrite from template |
| Scripts | `.claude/scripts/*.sh` | Overwrite from template |
| CLAUDE.md | `CLAUDE.md` | **Never touched** |
| Vault content | `01-07 folders` | **Never touched** |
| Settings | `.claude/settings*` | **Never touched** |

## Instructions

### Step 1: Verify Git Repository

```bash
git rev-parse --is-inside-work-tree 2>/dev/null && echo "GIT_OK" || echo "NOT_GIT_REPO"
```

If not a git repo, abort:
```
✗ This vault isn't a git repository. /update requires git.

If you copied files instead of cloning, you can fix this:
  cd /path/to/your/vault
  git init
  git remote add template https://github.com/harrisonaedwards/claude-code-obsidian-template.git
  git fetch template
Then run /update again.
```

### Step 2: Determine Template Remote

```bash
# Check all remotes
git remote -v
```

Determine the correct remote name:
1. If any remote URL contains `claude-code-obsidian-template` → use that remote name (usually `origin` for direct clones, or `template` if added separately)
2. If no remote points to the template → add it:
   ```bash
   git remote add template https://github.com/harrisonaedwards/claude-code-obsidian-template.git
   ```
   Then use `template`

Store the remote name as `$REMOTE` for subsequent steps.

### Step 3: Fetch Latest

```bash
git fetch $REMOTE 2>&1
```

If fetch fails:
- **Network error:** "✗ Couldn't reach GitHub. Check your internet connection."
- **Auth error:** "✗ Repository access denied. The template may have moved — ask Harrison."
- Abort in all failure cases.

### Step 4: Check Current State

```bash
# Get current local commit for commands (last time they were updated)
git log -1 --format="%h %s" -- .claude/commands/ .claude/scripts/ 2>/dev/null

# Get latest template commit for commands
git log -1 --format="%h %s" $REMOTE/main -- .claude/commands/ .claude/scripts/ 2>/dev/null
```

Check if there are any differences:
```bash
git diff HEAD...$REMOTE/main --stat -- .claude/commands/ .claude/scripts/ 2>/dev/null
```

If no differences:
```
✓ Already up to date. Commands and scripts match the latest template.
```
Stop here — nothing to do.

### Step 5: Preview Changes

```bash
# Summary of what changed
git diff HEAD...$REMOTE/main --stat -- .claude/commands/ .claude/scripts/

# Detect new files (in template but not local)
git diff HEAD...$REMOTE/main --diff-filter=A --name-only -- .claude/commands/ .claude/scripts/

# Detect deleted files (in local but removed from template)
git diff HEAD...$REMOTE/main --diff-filter=D --name-only -- .claude/commands/ .claude/scripts/
```

Display a clear summary:
```
Template update available:

  Updated:  park.md, pickup.md, morning.md (+3 more)
  New:      update.md, weekly.md
  Removed:  daily-review.md (deprecated)

  Total: N files changed
```

If `--dry-run`: Stop here and display:
```
Dry run complete. Run /update to apply these changes.
```

### Step 6: Confirm and Apply

Unless `--force` was specified, ask the user: "Apply these updates? Your CLAUDE.md and vault content won't be touched."

If confirmed:

```bash
# Check for uncommitted changes in target paths only
git status --porcelain -- .claude/commands/ .claude/scripts/
```

If there are uncommitted local changes to commands/scripts, warn:
```
⚠ You have local modifications to these commands:
  .claude/commands/park.md (modified)

These will be overwritten with the template version. Continue? (y/n)
```

Apply the update:
```bash
# Checkout template versions of commands and scripts
git checkout $REMOTE/main -- .claude/commands/ .claude/scripts/

# Commit the update (changes are already staged by git checkout)
git commit -m "Update CCO commands from template"
```

If the commit fails (nothing to commit), that's fine — files are already updated in the working tree.

### Step 7: Post-Update Checks

**Check VAULT_PATH:**
```bash
if [[ -z "${VAULT_PATH:-}" ]]; then
  echo "VAULT_PATH_MISSING"
else
  echo "VAULT_PATH=$VAULT_PATH"
fi
```

If VAULT_PATH is not set, display:
```
⚠ VAULT_PATH is not set in your shell profile.

Updated commands require VAULT_PATH to know where your vault is.
Add this line to your ~/.bashrc (Linux) or ~/.zshrc (Mac):

  export VAULT_PATH="$HOME/Files"

Replace "$HOME/Files" with your actual vault path if different.
Then restart your terminal or run: source ~/.bashrc
```

### Step 8: Display Completion

```
✓ CCO commands updated

  Commands: N updated, M new, K removed
  Scripts:  N updated, M new, K removed
  Your CLAUDE.md and vault content were not touched.

  Restart Claude Code to use the updated commands.
  (Just exit and re-launch)
```

## Error Recovery

If anything goes wrong mid-update:

```bash
# Undo the checkout (restore previous state)
git checkout HEAD -- .claude/commands/ .claude/scripts/
```

Display:
```
✗ Update failed — rolled back to previous commands. Nothing changed.
Error: [specific error message]
```

## Guidelines

- **Safe by design:** Only `.claude/commands/` and `.claude/scripts/` are ever modified. All other files are outside the checkout path.
- **Custom commands are preserved:** If the user has added their own commands (not from the template), `git checkout` won't remove them — it only updates files that exist in the template.
- **Idempotent:** Running `/update` twice in a row is safe — second run shows "Already up to date."
- **Offline-safe:** Fails cleanly if GitHub is unreachable. No partial updates.
- **No force push:** This never pushes anything. It only fetches and applies locally.
