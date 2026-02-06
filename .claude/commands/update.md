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

### Step 3: Fetch Latest and Detect Branch

```bash
git fetch $REMOTE 2>&1
```

If fetch fails:
- **Network error:** "✗ Couldn't reach GitHub. Check your internet connection."
- **Auth error:** "✗ Repository access denied. The template may have moved — ask Harrison."
- Abort in all failure cases.

**After fetching**, determine the default branch:
```bash
# Check which branch exists on the remote (fetch must complete first)
git rev-parse --verify $REMOTE/main 2>/dev/null && echo "BRANCH=main" || {
  git rev-parse --verify $REMOTE/master 2>/dev/null && echo "BRANCH=master" || echo "BRANCH_NOT_FOUND"
}
```

If neither `main` nor `master` exists, abort:
```
✗ Couldn't find main or master branch on remote. The template repo may have changed — ask Harrison.
```

Store as `$BRANCH`. Use `$REMOTE/$BRANCH` for all subsequent steps.

### Step 4: Compare Working Tree Against Template

Compare the user's **actual files on disk** (not committed state) against the template:

```bash
# Compare working tree against template (catches uncommitted local changes too)
git diff --stat $REMOTE/$BRANCH -- .claude/commands/ .claude/scripts/
```

If no differences:
```
✓ Already up to date. Commands and scripts match the latest template.
```
Stop here — nothing to do.

### Step 5: Preview Changes

Categorise what changed by comparing the working tree against the template:

```bash
# Files that differ between working tree and template
git diff $REMOTE/$BRANCH --name-only -- .claude/commands/ .claude/scripts/
```

Detect files that exist locally but NOT in the template (may be deprecated or user-created):
```bash
# Local command/script files
LOCAL_FILES=$(ls .claude/commands/*.md .claude/scripts/*.sh 2>/dev/null | sort)

# Template command/script files
TEMPLATE_FILES=$(git ls-tree -r --name-only $REMOTE/$BRANCH -- .claude/commands/ .claude/scripts/ | sort)

# Files in local but not in template
REMOVED_CANDIDATES=$(comm -23 <(echo "$LOCAL_FILES") <(echo "$TEMPLATE_FILES"))
```

Detect files in the template but not locally (new commands/scripts):
```bash
# Files in template but not local
NEW_FILES=$(comm -13 <(echo "$LOCAL_FILES") <(echo "$TEMPLATE_FILES"))
```

Display a clear summary:
```
Template update available:

  Updated:  park.md, pickup.md, morning.md (+3 more)
  New:      update.md, weekly.md

  Total: N files changed
```

**If removed candidates were detected**, display them separately with a warning:
```
  ⚠ These local files don't exist in the template:
    .claude/commands/daily-review.md
    .claude/commands/my-custom-thing.md

  These may be deprecated template files OR your own custom commands.
  They will NOT be auto-deleted. Review and remove manually if unwanted.
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
git checkout $REMOTE/$BRANCH -- .claude/commands/ .claude/scripts/

# Ensure scripts are executable and stage the permission change
chmod +x .claude/scripts/*.sh 2>/dev/null
git add .claude/scripts/*.sh

# Commit with template version hash for traceability
git commit -m "Update CCO commands from template ($(git rev-parse --short $REMOTE/$BRANCH))"
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

**Detect OS for appropriate instructions:**
```bash
uname -s
```

If VAULT_PATH is not set, display OS-appropriate instructions:

**Linux (uname returns "Linux"):**
```
⚠ VAULT_PATH is not set in your shell profile.

Updated commands require VAULT_PATH to know where your vault is.
Add this line to your ~/.bashrc:

  export VAULT_PATH="$HOME/Files"

Replace "$HOME/Files" with your actual vault path if different.
Then restart your terminal or run: source ~/.bashrc
```

**macOS (uname returns "Darwin"):**
```
⚠ VAULT_PATH is not set in your shell profile.

Updated commands require VAULT_PATH to know where your vault is.
Add this line to your ~/.zshrc:

  export VAULT_PATH="$HOME/Files"

Replace "$HOME/Files" with your actual vault path if different.
Then restart your terminal or run: source ~/.zshrc
```

**Windows (uname returns MINGW*, MSYS*, or CYGWIN*, or $OS is "Windows_NT"):**
```
⚠ VAULT_PATH is not set.

Updated commands require VAULT_PATH to know where your vault is.
Run this in PowerShell (one-time):

  [Environment]::SetEnvironmentVariable("VAULT_PATH", "C:\Users\YourName\Files", "User")

Replace the path with your actual vault location.
Then restart your terminal.
```

### Step 8: Display Completion

```bash
# Get hash for display
git rev-parse --short $REMOTE/$BRANCH
```

```
✓ CCO commands updated (template <hash>)

  Commands: N updated, M new
  Scripts:  N updated, M new
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
- **Custom commands are preserved:** `git checkout` only updates files that exist in the template. User-created custom commands are never modified or deleted.
- **Removed template files are flagged, not deleted:** If the template removes a command, `/update` warns you but won't auto-delete — because it can't distinguish "template file that was removed" from "your custom command that was never in the template." Review the warning and delete manually if appropriate.
- **Scripts are cross-platform:** All template scripts use portable locking (flock on Linux, mkdir-based on macOS/Windows) and portable date handling. Updates won't break OS-specific functionality.
- **Version-tracked:** Each update commit includes the template hash (e.g., `a3f8c2d`) for debugging and rollback.
- **Idempotent:** Running `/update` twice in a row is safe — second run shows "Already up to date."
- **Offline-safe:** Fails cleanly if GitHub is unreachable. No partial updates.
- **No force push:** This never pushes anything. It only fetches and applies locally.
