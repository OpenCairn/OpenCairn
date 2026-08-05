---
name: update
description: Update OpenCairn commands and scripts from the template repository
argument-hint: "[--dry-run] [--force] [--tag VERSION]"
---

# Update - OpenCairn Template Sync

You are updating the user's OpenCairn commands and scripts from the upstream template repository. This updates **infrastructure only** (commands, scripts) — vault content and CLAUDE.md are never touched.

**Two modes.** By default `/update` tracks the template's main branch (latest, possibly unreleased). Pass `--tag VERSION` to instead pin to a specific signed release and verify its tag signature before applying anything — the supply-chain-cautious path. The two modes differ only in *what* you compare against (Step 3b/3c); the per-file review and apply (Steps 4–6) are identical.

## What Gets Updated

| Category | Path | Action |
|----------|------|--------|
| Commands | `.claude/commands/` (whole tree, including subdirectories) | Per-file review (accept/skip) |
| Scripts | `.claude/scripts/` (whole tree, any extension) | Per-file review (accept/skip) |
| CLAUDE.md | `CLAUDE.md` | **Never touched** |
| Vault content | `01-07 folders` | **Never touched** |
| Settings | `.claude/settings*` | **Never touched** |

## Git Command Constraint

Do not use `git show ref:path` (colon syntax) — Windows Git Bash mangles the colon. Use `git diff` to compare and `git checkout` to restore. All commands in this skill already use cross-platform forms; this constraint prevents improvisation with colon syntax during execution.

## Shell Variables Do Not Persist

Each Bash call runs in a fresh shell, so a variable assigned in one fenced block is **empty** in the next. `$REMOTE`, `$BRANCH`, `$REF`, `$VERSION`, `$ASF`, `$LOCAL_FILES` and `$TEMPLATE_FILES` below are notation for values *you* resolve and then **substitute literally** into every later command — never carry them across blocks as shell state. An empty `$REF` is not a harmless no-op: `git checkout $REF -- <dirs>` with `$REF` unset silently discards the working tree against the index.

Where a block assigns a variable and consumes it, keep the assignment and its consumers in that **same** block. Where a value is needed in a later step, write the resolved literal (e.g. `origin/main`, `refs/tags/v1.2.3`) into the command you run.

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
  git add -A && git commit -m "Baseline before first /update"
Then run /update again.
```

**Also check for an unborn HEAD** (repo initialised but no commits yet — e.g. the user ran `git init` without a baseline commit):
```bash
git rev-parse --verify HEAD >/dev/null 2>&1 && echo "HEAD_OK" || echo "NO_COMMITS_YET"
```
If `NO_COMMITS_YET`, abort and instruct: `git add -A && git commit -m "Baseline before first /update"`, then re-run. Without a baseline commit, every local file is untracked — the Step 4–6 diffs show the template as wholesale deletions (hiding local customisations right before checkout clobbers them) and Error Recovery has no pre-update HEAD to restore from.

### Step 1c: Old-Format Vault Check

The template's task system changed in Aug 2026 (project docs as SSOT; Tasks.md and Works in Progress removed). Updating an old-format vault would ship skills that ignore surfaces the vault still relies on. Check:

```bash
# Primary marks — either file alone is enough
if [ -e "01 Now/Tasks.md" ] || [ -e "01 Now/Works in Progress.md" ]; then echo OLD_FORMAT; else echo FORMAT_OK; fi

# Secondary probe — root project docs carrying **Status:** without bucket: frontmatter
grep -LZ '^bucket:' "03 Projects/"*.md 2>/dev/null | xargs -r0 grep -l '^\*\*Status:\*\*' | head -3

# Migration decisions on record — read before judging
cat "07 System/Migration Record.md" 2>/dev/null
```

If the secondary probe returns any file, print `SCHEMA_DRIFT` and treat it as `OLD_FORMAT`.

If `OLD_FORMAT` — and the Migration Record doesn't record those components as `never` — abort:
```
✗ This vault uses the pre-2026-08 task format (Tasks.md / Works in Progress present,
  or project docs carry **Status:** without bucket: frontmatter).
  Run /migrate first — it converts the vault component-by-component with your consent,
  then /update proceeds normally. Migration decisions are recorded in
  07 System/Migration Record.md: components recorded `never` (intentional divergence)
  unblock /update; `later` deferrals keep the gate.
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

Note the remote name — it appears below as `$REMOTE`, and you substitute the literal name into each command you run (see *Shell Variables Do Not Persist*).

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

Note the branch name — like `$REMOTE`, substitute it literally below.

### Step 3b: Resolve the comparison ref (`$REF`)

Every diff and checkout from here on targets a single ref, written below as `$REF` and substituted literally into each command you run. This is the **only** thing `--tag` changes — *what* you compare against, never *how* files are applied (Step 6's per-file review is identical in both modes).

**Default — branch-follow:** `$REF` is `<remote>/<branch>` — the two names resolved in Steps 2 and 3, e.g. `origin/main`.

**If `--tag VERSION` was passed** — pin to a specific signed release instead of tracking the branch. Resolve the version the user passed **against the remote**: a bare `git rev-parse --verify` only proves a *local* tag exists, so a stale or locally-created tag named like a release would pass. Run the checks as one block, substituting the literal remote and version:
```bash
VERSION="<the value passed to --tag>"; REMOTE="<the remote resolved in Step 2>"
git ls-remote --exit-code --tags "$REMOTE" "refs/tags/$VERSION" >/dev/null 2>&1 \
  || { echo "✗ Tag $VERSION not found on $REMOTE — check https://github.com/OpenCairn/OpenCairn/releases"; exit 1; }
git fetch -f "$REMOTE" "refs/tags/$VERSION:refs/tags/$VERSION" 2>&1 \
  || { echo "✗ Failed to fetch refs/tags/$VERSION from $REMOTE"; exit 1; }   # -f overwrites any stale local tag
```
`$REF` is then `refs/tags/<VERSION>` — substitute that literal below.

### Step 3c: Verify `$REF` is signed

Verification differs by mode. **Branch-follow warns and continues** — an early adopter on a pre-signing commit shouldn't be locked out. **A `--tag` pin fails closed** — you explicitly asked for a verified release, so an unverifiable one aborts.

#### Pinned mode (`--tag`) — fail closed

Classify on **structured signals** — object type, verify exit code, config state — not on scraped stderr text (git's messages vary by version and locale, and don't reliably contain the config key name). `--force` is **not** consulted here: a requested pin that can't be verified aborts, full stop (matching `CONTRIBUTING.md`'s "unverifiable aborts"). `--force` only ever skips per-file review (Step 6).

Run this as one block, with the literal ref and version substituted in:

```bash
REF="refs/tags/<VERSION>"; VERSION="<VERSION>"; REMOTE="<the remote resolved in Step 2>"
git verify-tag "$REF" >/dev/null 2>&1; TAG_RC=$?
OBJTYPE=$(git cat-file -t "$REF" 2>/dev/null)
ASF=$(git config --get gpg.ssh.allowedSignersFile)

if [ "$OBJTYPE" != tag ]; then                          # lightweight tag → HARD ABORT (can't carry a signature)
  echo "✗ $VERSION is a lightweight tag (a pre-signing release), not a verifiable signed release."
  echo "  Tag object types are not monotonic, so pick from the tags that actually verify here:"
  git fetch -q -f --tags "$REMOTE"
  for T in $(git tag --sort=-v:refname | head -20); do
    [ "$(git cat-file -t "refs/tags/$T" 2>/dev/null)" = tag ] \
      && git verify-tag "refs/tags/$T" >/dev/null 2>&1 && echo "    $T"
  done
  echo "  (an empty list means signature verification isn't configured here — see CONTRIBUTING.md#commit-signing)"
  exit 1
elif [ "$TAG_RC" -eq 0 ]; then                          # good signature → proceed
  echo "✓ Release tag $VERSION is signed and verified"
elif [ -z "$ASF" ] || [ ! -r "$ASF" ]; then            # verifier not configured → STOP (config gap, not tamper)
  echo "✗ Signature verification isn't configured here (gpg.ssh.allowedSignersFile unset or unreadable),"
  echo "  so $VERSION can't be verified. Set it up once, then re-run:"
  echo "  https://github.com/OpenCairn/OpenCairn/blob/main/CONTRIBUTING.md#commit-signing"; exit 1
else                                                    # tag object, verifier configured, still bad → HARD ABORT
  echo "✗ $VERSION is not a verified signed release (unsigned, or signature invalid/tampered). Aborting."; exit 1
fi
```
Object-type is tested first because a lightweight tag can never carry a signature, so it must abort regardless of verifier config — and `git cat-file -t` is deterministic where stderr text is not. The config gap **stops** rather than continuing (the inversion from branch-follow): you *asked* for a verified pin, so an unverifiable one is a hard stop, and the fix is a one-time setup, not a `--force`.

**Commit-signing check** (the tag proves the maintainer published this release; it does not prove the tagged commit itself meets the commit-signing policy):
```bash
TAG_COMMIT=$(git rev-parse "$REF^{commit}")
git verify-commit "$TAG_COMMIT" >/dev/null 2>&1 \
  && echo "✓ Tagged commit $TAG_COMMIT is also signed" \
  || echo "⚠ Tag is signed but commit $TAG_COMMIT is not individually signed — proceeding on the tag's authority."
```
The tag signature is the release authority, so a missing commit signature **warns but continues**; only the tag verification above aborts.

#### Branch-follow mode (default, `$REF` = `$REMOTE/$BRANCH`) — warn and continue

Before applying any changes, verify the template commit is signed:

```bash
VERIFY_OUTPUT=$(git verify-commit "$REF" 2>&1)
```

**If verification succeeds** (exit code 0), display:
```
✓ Template commit is signed and verified
```
Continue to Step 4.

**If verification fails** (exit code non-zero), distinguish a missing-config gap from a real signature problem via the **config itself**, not the error text (git's stderr doesn't reliably contain the config key name):

```bash
ASF=$(git config --get gpg.ssh.allowedSignersFile)
```

**If `$ASF` is empty or unreadable** (`[ -z "$ASF" ] || [ ! -r "$ASF" ]`) — the user hasn't configured signature verification locally. This is a config gap, not a security problem. Display:
```
ℹ Signature verification is not configured on your machine.
  The template commit may be signed, but your git can't check it.

  To enable verification, see: https://github.com/OpenCairn/OpenCairn/blob/main/CONTRIBUTING.md#commit-signing

  Continuing without signature check.
```
Continue to Step 4 (no user prompt needed — this is informational, not a security warning).

**Otherwise** — the commit is genuinely unsigned or the signature is invalid. Display:
```
⚠ WARNING: Template commit at $REF is NOT signed.

  This could mean:
  - The repository maintainer pushed without signing (ask them to fix it)
  - The repository has been compromised

  Commit: $(git rev-parse --short $REF)
  Author: $(git log -1 --format='%an <%ae>' $REF)
  Date:   $(git log -1 --format='%ci' $REF)

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
git diff --stat $REF -- .claude/commands/ .claude/scripts/
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
git diff $REF --name-only -- .claude/commands/ .claude/scripts/
```

Detect files that exist locally but NOT in the template (may be deprecated or user-created), and files in the template but not locally (new commands/scripts). Run this as one block — `comm` needs `LC_ALL=C sort` on both sides, or it aborts with "not in sorted order" under a UTF-8 locale, and both inventories must cover the **whole tree** (subdirectories and any extension), not a top-level glob:
```bash
# Local command/script files: tracked + untracked-but-not-ignored, across both trees
LOCAL_FILES=$( { git ls-files -- .claude/commands/ .claude/scripts/;
                 git ls-files --others --exclude-standard -- .claude/commands/ .claude/scripts/; } \
               | LC_ALL=C sort -u)

# Template command/script files
TEMPLATE_FILES=$(git ls-tree -r --name-only $REF -- .claude/commands/ .claude/scripts/ | LC_ALL=C sort)

# Files in local but not in template
REMOVED_CANDIDATES=$(comm -23 <(echo "$LOCAL_FILES") <(echo "$TEMPLATE_FILES"))

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

**Before touching anything**, record two things you will need later:
```bash
git rev-parse HEAD    # pre-update HEAD — Error Recovery restores from this, not from HEAD-at-failure-time
```
and an **accepted-files list**: the paths you actually check out during this step (accepted files plus new files). Keep it explicitly — the commit and any rollback are scoped to those paths only, never to the directory roots.

**If `--force` was specified**, skip per-file review — accept all files and apply them in bulk (use the bulk checkout approach):
```bash
git checkout $REF -- .claude/commands/ .claude/scripts/
```
The accepted-files list for the commit is then the template's file list (`git ls-tree -r --name-only $REF -- .claude/commands/ .claude/scripts/`). Then skip ahead to the commit step below.

**Otherwise, iterate over each changed file:**

Get the list of files that differ, **intersected with what the template actually contains** — a bare `git diff --name-only` also lists committed local-only files, which then hit an impossible `git checkout` (no such path in the template):
```bash
comm -12 \
  <(git diff $REF --name-only -- .claude/commands/ .claude/scripts/ | LC_ALL=C sort) \
  <(git ls-tree -r --name-only $REF -- .claude/commands/ .claude/scripts/ | LC_ALL=C sort)
```
(`LC_ALL=C` on both sides is required — `comm` aborts with "not in sorted order" against a UTF-8 collation.)

For each file in this list:

1. **Show a compact diff** (the template version vs local version):
   ```bash
   git diff $REF -- <file>
   ```

2. **Show a one-line summary** describing the change direction and size, e.g.:
   ```
   audit.md — template adds 2 lines (local 103 → template 105)
   ```

3. **Ask the user:** "Accept template version? (y/n/d)"
   - **y** — accept: checkout the template version of this file
   - **n** — skip: keep the local version unchanged
   - **d** — show full diff again (re-display, then re-ask)

4. **If accepted**, apply immediately:
   ```bash
   git checkout $REF -- <file>
   ```

5. **If skipped**, note it for the summary. Move to the next file.

**New files** (in template but not local) don't need review — apply them automatically:
```bash
git checkout $REF -- <new-file>
```

**After all files are processed**, commit everything that was accepted:
```bash
# Ensure scripts are executable and stage the permission change
chmod +x .claude/scripts/*.sh 2>/dev/null

# Commit with template version hash for traceability.
# Name every accepted file explicitly — NOT the directory roots. `--only` scopes
# against the index, not against what this run touched, so a directory-root commit
# would sweep in files the user skipped and a concurrent session's in-flight edits.
# See `_shared-rules.md` §21.
git commit --only -m "Update OpenCairn commands from template ($(git rev-parse --short $REF))" \
  -- <accepted-file-1> <accepted-file-2> ...
```

**Assert only the files you accepted left the index** — not that the tree, or even the two directories, are globally clean. Under concurrent sessions other files being dirty is expected and is not your business:
```bash
git status --short -- <accepted-file-1> <accepted-file-2> ...   # expect empty
```

If nothing was accepted (user skipped everything), don't commit. Display:
```
No updates applied — all files skipped.
```

If the commit fails (nothing to commit), that's fine — files are already updated in the working tree.

### Step 7: Post-Update Checks

<!-- The VAULT_PATH and macOS-bash blocks below are duplicated in setup.md Phase 1/2 — edit both copies together. -->

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
git rev-parse --short $REF
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

If anything goes wrong mid-update, restore **only the files this run checked out**, from the **pre-update HEAD** you recorded at the top of Step 6 — not from `HEAD`, which may already be this run's own update commit, and not from the directory roots, which would discard unrelated uncommitted work (including a concurrent session's):

```bash
# Undo this run's checkouts (restore previous state)
git checkout <pre-update-HEAD> -- <accepted-file-1> <accepted-file-2> ...
```

If the failure landed **after** the Step 6 commit, that commit is still in history — say so rather than claiming nothing changed:
```
✗ Update failed after committing. Restored the affected files from <pre-update-HEAD>.
  The update commit is still in history — `git revert` it if you want it gone.
Error: [specific error message]
```

Otherwise:
```
✗ Update failed — rolled back the files this run touched. Nothing was committed.
Error: [specific error message]
```

## Guidelines

- **Safe by design:** Only `.claude/commands/` and `.claude/scripts/` are ever modified. All other files are outside the checkout path.
- **Per-file review:** Each changed file is shown with its diff before applying. Users can skip files they've customised locally, preventing template regressions. `--force` bypasses review and accepts all.
- **Custom commands are preserved:** Only files that exist in the template are updated. User-created custom commands are never modified or deleted.
- **Removed template files are flagged, not deleted:** If the template removes a command, `/update` warns you but won't auto-delete — because it can't distinguish "template file that was removed" from "your custom command that was never in the template." Review the warning and delete manually if appropriate.
- **Scripts are cross-platform:** All template scripts use portable locking (flock on Linux, mkdir-based on macOS/Windows) and portable date handling. Updates won't break OS-specific functionality.
- **Version-tracked:** Each update commit includes the template hash (e.g., `a3f8c2d`) for debugging and rollback.
- **Safe to re-run:** Running `/update` twice in a row never double-applies anything. It only shows "Already up to date" if nothing still differs — a second run re-offers any files you skipped, plus any local-only commands or scripts, because neither leaves a record that would suppress them.
- **Offline-safe:** Fails cleanly if GitHub is unreachable. No partial updates.
- **No force push:** This never pushes anything. It only fetches and applies locally.
- **Pinned releases (`--tag VERSION`):** pin to a specific signed release instead of tracking the branch, and verify its tag signature before applying. Unlike branch-follow (which warns and continues), pinned mode **fails closed** — an unsigned, lightweight, or unverifiable tag aborts. The per-file review and apply are otherwise identical; `--tag` only changes what you diff against.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and log observations at the end per that file.
