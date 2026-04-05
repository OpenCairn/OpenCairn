---
name: update
description: Update OpenCairn commands and scripts from the template repository
parameters:
  - "--dry-run" - Preview changes without applying them
  - "--force" - Accept all changes without per-file review
---

# Update - OpenCairn Template Sync

You are updating the user's OpenCairn commands and scripts from the upstream template repository. This updates **infrastructure only** (commands, scripts) — vault content and CLAUDE.md are never touched.

## What Gets Updated

| Category | Path | Action |
|----------|------|--------|
| Commands | `.claude/commands/*.md` | Per-file review (accept/skip) |
| Scripts | `.claude/scripts/*.sh` | Per-file review (accept/skip) |
| CLAUDE.md | `CLAUDE.md` | **Never touched** |
| Vault content | `01-07 folders` | **Never touched** |
| Settings | `.claude/settings*` | **Never touched** |

## Git Command Constraint

Do not use `git show ref:path` (colon syntax) — Windows Git Bash mangles the colon. Use `git diff` to compare and `git checkout` to restore. All commands in this skill already use cross-platform forms; this constraint prevents improvisation with colon syntax during execution.

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
  git remote add template https://github.com/OpenCairn/OpenCairn.git
  git fetch template
Then run /update again.
```

### Step 2: Determine Template Remote

```bash
# Check all remotes
git remote -v
```

Determine the correct remote name:
1. If any remote URL contains `OpenCairn` → use that remote name (usually `origin` for direct clones, or `template` if added separately)
2. If no remote points to the template → add it:
   ```bash
   git remote add template https://github.com/OpenCairn/OpenCairn.git
   ```
   Then use `template`

Store the remote name as `$REMOTE` for subsequent steps.

### Step 3: Fetch Latest and Detect Branch

```bash
git fetch $REMOTE 2>&1
```

If fetch fails:
- **Network error:** "✗ Couldn't reach GitHub. Check your internet connection."
- **Auth error:** "✗ Repository access denied. The template may have moved — check the template repo URL."
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
✗ Couldn't find main or master branch on remote. The template repo may have changed — check the template repo URL.
```

Store as `$BRANCH`. Use `$REMOTE/$BRANCH` for all subsequent steps.

### Step 3b: Verify Commit Signature

Before applying any changes, verify the template commit is signed:

```bash
VERIFY_OUTPUT=$(git verify-commit $REMOTE/$BRANCH 2>&1)
```

**If verification succeeds** (exit code 0), display:
```
✓ Template commit is signed and verified
```
Continue to Step 4.

**If verification fails** (exit code non-zero), check whether the failure is a missing config or an actual signature problem:

```bash
echo "$VERIFY_OUTPUT" | grep -q "allowedSignersFile"
```

**If `allowedSignersFile` is mentioned** — the user hasn't configured signature verification locally. This is a config gap, not a security problem. Display:
```
ℹ Signature verification is not configured on your machine.
  The template commit may be signed, but your git can't check it.

  To enable verification, see: https://github.com/OpenCairn/OpenCairn#commit-signing

  Continuing without signature check.
```
Continue to Step 4 (no user prompt needed — this is informational, not a security warning).

**Otherwise** — the commit is genuinely unsigned or the signature is invalid. Display:
```
⚠ WARNING: Template commit at $REMOTE/$BRANCH is NOT signed.

  This could mean:
  - The repository maintainer pushed without signing (ask them to fix it)
  - The repository has been compromised

  Commit: $(git rev-parse --short $REMOTE/$BRANCH)
  Author: $(git log -1 --format='%an <%ae>' $REMOTE/$BRANCH)
  Date:   $(git log -1 --format='%ci' $REMOTE/$BRANCH)

  Do you want to continue anyway? (y/n)
```

If the user chooses **n**, abort. If **y**, continue with a warning banner prepended to all subsequent output:
```
⚠ UNVERIFIED — applying unsigned template commit
```

**Why warn instead of hard-block:** Early adopters pulling older (pre-signing) commits would be locked out. Once all historical commits are superseded by signed ones, this can be tightened to a hard block.

### Step 4: Compare Working Tree Against Template

Compare the user's **actual files on disc** (not committed state) against the template:

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

### Step 6: Per-File Review and Apply

For each changed file, show a short diff and let the user decide. This prevents template updates from overwriting local improvements.

**If `--force` was specified**, skip per-file review — accept all files and apply them in bulk (use the bulk checkout approach):
```bash
git checkout $REMOTE/$BRANCH -- .claude/commands/ .claude/scripts/
```
Then skip ahead to the commit step below.

**Otherwise, iterate over each changed file:**

Get the list of files that differ (excluding local-only files which aren't in the template):
```bash
git diff $REMOTE/$BRANCH --name-only -- .claude/commands/ .claude/scripts/
```

For each file in this list:

1. **Show a compact diff** (the template version vs local version):
   ```bash
   git diff $REMOTE/$BRANCH -- <file>
   ```

2. **Show a one-line summary** describing the change direction and size, e.g.:
   ```
   audit.md — template adds 2 lines (105 → 103 locally, template is longer)
   ```

3. **Ask the user:** "Accept template version? (y/n/d)"
   - **y** — accept: checkout the template version of this file
   - **n** — skip: keep the local version unchanged
   - **d** — show full diff again (re-display, then re-ask)

4. **If accepted**, apply immediately:
   ```bash
   git checkout $REMOTE/$BRANCH -- <file>
   ```

5. **If skipped**, note it for the summary. Move to the next file.

**New files** (in template but not local) don't need review — apply them automatically:
```bash
git checkout $REMOTE/$BRANCH -- <new-file>
```

**After all files are processed**, commit everything that was accepted:
```bash
# Ensure scripts are executable and stage the permission change
chmod +x .claude/scripts/*.sh 2>/dev/null
git add .claude/commands/ .claude/scripts/

# Commit with template version hash for traceability
git commit -m "Update OpenCairn commands from template ($(git rev-parse --short $REMOTE/$BRANCH))"
```

If nothing was accepted (user skipped everything), don't commit. Display:
```
No updates applied — all files skipped.
```

If the commit fails (nothing to commit), that's fine — files are already updated in the working tree.

### Step 7: Post-Update Checks

**Check VAULT_PATH:**
```bash
if [[ -z "${VAULT_PATH:-}" ]]; then
  echo "VAULT_PATH_MISSING"
else
  echo "VAULT_PATH={VAULT}"
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

**Check bash version (macOS only):**

On macOS, check whether bash meets the minimum version required by OpenCairn scripts:

```bash
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "BASH_VERSION=$BASH_VERSION"
  if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 2))); then
    echo "BASH_UPGRADE_NEEDED"
  else
    echo "BASH_OK"
  fi
fi
```

If `BASH_UPGRADE_NEEDED`, display:
```
⚠ Bash 4.2+ is required for some OpenCairn scripts (e.g. /pickup).
  Your current bash: [version]

  Install a newer bash via Homebrew:

    brew install bash

  After installing, Claude Code will use the Homebrew bash automatically
  (it resolves via $PATH). No shebang or shell profile changes needed.
```

### Step 8: Display Completion

```bash
# Get hash for display
git rev-parse --short $REMOTE/$BRANCH
```

```
✓ OpenCairn commands updated (template <hash>)

  Accepted: N files (park.md, pickup.md, morning.md)
  Skipped:  M files (audit.md)
  New:      K files (weekly.md)
  Your CLAUDE.md and vault content were not touched.

  📋 Release notes: https://github.com/OpenCairn/OpenCairn/releases
     Some updates change file paths or vault structure.
     Check the latest release notes for any manual migration steps.

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
- **Per-file review:** Each changed file is shown with its diff before applying. Users can skip files they've customised locally, preventing template regressions. `--force` bypasses review and accepts all.
- **Custom commands are preserved:** Only files that exist in the template are updated. User-created custom commands are never modified or deleted.
- **Removed template files are flagged, not deleted:** If the template removes a command, `/update` warns you but won't auto-delete — because it can't distinguish "template file that was removed" from "your custom command that was never in the template." Review the warning and delete manually if appropriate.
- **Scripts are cross-platform:** All template scripts use portable locking (flock on Linux, mkdir-based on macOS/Windows) and portable date handling. Updates won't break OS-specific functionality.
- **Version-tracked:** Each update commit includes the template hash (e.g., `a3f8c2d`) for debugging and rollback.
- **Idempotent:** Running `/update` twice in a row is safe — second run shows "Already up to date."
- **Offline-safe:** Fails cleanly if GitHub is unreachable. No partial updates.
- **No force push:** This never pushes anything. It only fetches and applies locally.
