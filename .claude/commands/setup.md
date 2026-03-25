---
name: setup
description: First-run onboarding - environment checks, platform prerequisites, CLAUDE.md personalisation interview
---

# Setup - First-Run Onboarding

You are running the initial setup for a new OpenCairn user. This handles environment configuration and personalises CLAUDE.md through a conversational interview.

## Philosophy

**Detect, then guide.** Check what's already in place before asking questions. Don't re-do what's done. Don't install anything automatically — guide the user and verify.

## Instructions

### Phase 1: Environment Detection

Run all checks first, display the result, then act on what's missing.

1. **Detect OS:**
   ```bash
   uname -s
   ```

2. **Check git repo:**
   ```bash
   git rev-parse --is-inside-work-tree 2>/dev/null && echo "GIT_OK" || echo "NOT_GIT_REPO"
   ```

3. **Check template remote:**
   ```bash
   git remote -v 2>/dev/null | grep -i "OpenCairn" || echo "NO_TEMPLATE_REMOTE"
   ```

4. **Check VAULT_PATH:**
   ```bash
   if [[ -z "${VAULT_PATH:-}" ]]; then
     echo "VAULT_PATH_MISSING"
   else
     echo "VAULT_PATH=$VAULT_PATH"
   fi
   ```

5. **Check bash version (macOS only):**
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

6. **Check scripts executable:**
   ```bash
   if [[ -x .claude/scripts/pickup-scan.sh ]]; then
     echo "SCRIPTS_EXECUTABLE"
   else
     echo "SCRIPTS_NOT_EXECUTABLE"
   fi
   ```

7. **Check CLAUDE.md state:**
   ```bash
   if [[ ! -f CLAUDE.md ]]; then
     echo "CLAUDE_MD_MISSING"
   elif grep -q '\[Your name\]' CLAUDE.md 2>/dev/null; then
     echo "CLAUDE_MD_UNPERSONALISED"
   else
     echo "CLAUDE_MD_PERSONALISED"
   fi
   ```

8. **Display environment summary:**

   ```
   Environment Check
   ─────────────────
   OS:              [Linux/macOS/Windows]
   Git repo:        [✓/✗]
   Template remote: [✓/✗]
   VAULT_PATH:      [✓ /path/to/vault / ✗ not set]
   Bash version:    [✓ 5.x / ⚠ 3.2 — upgrade needed] (macOS only)
   Scripts:         [✓ executable / ✗ need chmod]
   CLAUDE.md:       [✓ personalised / ○ needs setup]
   ```

### Phase 2: Fix Environment Issues

Address each issue found in Phase 1. Skip items that are already fine.

**If not a git repo:**
```
Your vault isn't a git repository. This is needed for /update to pull future template changes.

Run these commands:
  git init
  git remote add template https://github.com/OpenCairn/OpenCairn.git
  git fetch template
```
Wait for the user to confirm before proceeding.

**If no template remote:**
```
No git remote pointing to the OpenCairn template. This is needed for /update.

Run:
  git remote add template https://github.com/OpenCairn/OpenCairn.git
```

**If VAULT_PATH not set:**

Display OS-appropriate instructions:

- **Linux:** Add `export VAULT_PATH="$HOME/Files"` to `~/.bashrc`, then `source ~/.bashrc`
- **macOS:** Add `export VAULT_PATH="$HOME/Files"` to `~/.zshrc`, then `source ~/.zshrc`
- **Windows:** Run in PowerShell: `[Environment]::SetEnvironmentVariable("VAULT_PATH", "C:\Users\YourName\Files", "User")`

Tell the user to replace the path with their actual vault location. Wait for confirmation.

**Important:** The user's shell profile change won't be visible to Claude Code's Bash tool in this session. After the user confirms the path, set it inline for the remainder of setup:
```bash
export VAULT_PATH="[path the user confirmed]"
echo "VAULT_PATH=$VAULT_PATH (set for this session — persists via shell profile for future sessions)"
```

**If macOS + bash < 4.2:**
```
Some OpenCairn scripts (like /pickup) require bash 4.2+.
macOS ships bash 3.2 due to licensing constraints.

Install a newer bash:
  brew install bash

Claude Code will use the Homebrew bash automatically via $PATH.
No shebang or shell profile changes needed.
```

**If scripts not executable:**
```bash
chmod +x .claude/scripts/*.sh
echo "Scripts now executable"
```

After addressing all issues, re-run the checks from Phase 1 to confirm everything passes. Display the updated summary.

### Phase 3: Onboarding Interview

**Skip condition:** If CLAUDE.md is already personalised (no `[Your name]` placeholder), ask:
> "CLAUDE.md looks like it's already been personalised. Want to re-run the interview to update it, or skip to the end?"

If skipping, jump to Phase 6.

**Interview approach:** Ask questions conversationally, one or two at a time. Don't present a numbered quiz. Use the user's answers naturally — if they volunteer information early, don't re-ask.

**Detect locale and timezone from system before asking:**
```bash
echo "LANG=${LANG:-not set}"
echo "TZ=${TZ:-not set}"
date +"%Z (UTC%z)"
```

**Questions:**

Start with:
> "Let's personalise your CLAUDE.md so I can give you relevant, tailored responses in future sessions. This takes about 5 minutes."
>
> "First — what's your name, and what do you do? Give me the one-line version: name, age if you want to include it, and what you'd tell someone at a conference."

Capture: name, age (optional), profession/life stage.

Then:
> "What are you primarily working on or focused on right now? Could be a career transition, a project, study — whatever's top of mind."

Capture: current focus.

Then:
> "How do you think? Some people are analytical and systems-oriented, others are intuitive or creative. Do you tend toward action or deliberation? Any mental models or frameworks you lean on?"

Capture: thinking style.

Then, present the detected locale/timezone:
> "I detected your system locale as [LANG] and timezone as [TZ]. Does that look right, or should I use something different?"

Capture: locale string (e.g., `en_AU.UTF-8, TZ=Australia/Brisbane`).

Then:
> "Three quick preferences for how I should communicate with you:
> 1. Do you want to understand the 'why' behind things, or just get the answer?
> 2. Are you comfortable with technical depth, or prefer things simplified?
> 3. Do you want me to challenge your ideas and push back, or mostly go along with your direction?"

Capture: evidence preference, technical depth, pushback preference.

Then:
> "What are the main domains or areas of your life you want to organise in your vault? These become context files — for example, Health, Career, Photography, Finances, Relationships. List as many or few as you like."

Capture: domain list.

Finally:
> "Any personal principles or decision frameworks you want me to know about? Things like 'bias toward action', 'evidence over authority', 'long-term over short-term'. These go in the Working With Me section."

Capture: principles (optional — the template already includes two defaults).

### Phase 4: Write CLAUDE.md

Use the Edit tool to replace bracketed placeholders with the user's answers:

1. Replace `[Your name], [age]. [Brief description of your profession/life stage.]` with the user's identity line
2. Replace `[1-2 sentences about what you're primarily working on or focused on right now.]` with current focus
3. Replace the multi-line thinking style block — this spans 3 lines from `[Describe your thinking style.` through `or toward deliberation?]`. Replace all 3 lines with the user's answer.
4. Replace `[e.g., en_AU.UTF-8, TZ=Australia/Brisbane]` with confirmed locale
5. Replace `[Do you want to understand the "why" or just follow instructions?]` with evidence preference
6. Replace `[Comfortable with complexity? Prefer simplified explanations?]` with technical depth
7. Replace `[Do you want Claude to challenge your ideas or mostly agree?]` with pushback preference
8. Replace the `[Domain A]` / `[Domain B]` entries with the user's domain list, one line per domain:
   ```
   - **[Domain]:** `07 System/Context - [Domain].md`
   ```
9. Replace `[Add your own principles here]` with the user's principles (keep the two default principles above)

Remove HTML comments (`<!-- ... -->`) from sections that have been filled in — they're instructions for setup, not permanent content.

After editing, display: `✓ CLAUDE.md personalised`

### Phase 5: Create Context File Stubs

For each domain the user listed, create a stub file at `07 System/Context - [Domain].md`:

```markdown
# Context - [Domain]

<!-- This is a hub file for the [Domain] area of your life.
Add key facts, current state, goals, and links to detailed notes.
Claude reads this file when your conversation touches [Domain]. -->

## Current State

[What's happening now in this domain]

## Goals

[What you're working toward]

## Key References

[Links to important notes, documents, or resources in this domain]
```

Ensure the directory exists:
```bash
mkdir -p "07 System"
```

After creating stubs, display:
```
✓ Created context file stubs:
  - 07 System/Context - [Domain1].md
  - 07 System/Context - [Domain2].md
  ...
```

### Phase 6: Verify & Close

Re-run the environment checks from Phase 1. If VAULT_PATH was set inline during Phase 2, prepend the same `export VAULT_PATH="..."` to the bash command so it's available in the new shell. Display the final summary:

```
Setup Complete
──────────────
OS:              [✓]
Git repo:        [✓]
Template remote: [✓]
VAULT_PATH:      [✓]
Bash version:    [✓] (macOS only)
Scripts:         [✓]
CLAUDE.md:       [✓]
Context files:   [N] created

Next steps:
  • Fill in your context files in 07 System/ as you go — they don't need to be complete now
  • Use /park when you're done with a session (captures your work)
  • Use /pickup to resume where you left off
  • Use /update periodically to pull the latest commands
  • Open Obsidian and select this folder as your vault (optional but recommended)
```

## Guidelines

- **Don't install software.** Guide the user to run install commands themselves. Verify after they confirm.
- **Idempotent.** Running `/setup` again detects what's already done and skips it. Offer to re-run specific sections.
- **No vault content changes.** Only touch CLAUDE.md and `07 System/Context - *.md` stubs. Never modify 01-06 folders.
- **Conversational interview.** Not a form. Adapt to what the user volunteers — if they give detailed answers, extract what's needed without re-asking.
- **System detection first.** Always detect (locale, timezone, OS, bash version) before asking the user to confirm or correct.

## Cue Word Detection

This command should trigger when the user says:
- "setup"
- "first time"
- "getting started"
- "new here"
- "just cloned"
- "how do I set this up"

## Integration

- **Reads from:** CLAUDE.md (template state), system environment
- **Creates:** `07 System/Context - [Domain].md` stubs
- **Updates:** CLAUDE.md (replaces placeholders with user's answers)
- **Complements:** `/update` (ongoing template sync — setup is one-time)
