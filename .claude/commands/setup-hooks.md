---
name: setup-hooks
description: Opt in to OpenCairn's optional Claude Code hooks (currently the skill-edit cross-pollination survey)
argument-hint: "[--remove]"
---

# Setup Hooks — Opt Into Optional Hooks

You are wiring (or removing) OpenCairn's **optional** hooks into the user's Claude Code
settings. Hooks are opt-in: `/update` deliberately never touches `settings.json`, so this
command is the explicit, reversible way to enable them. Idempotent — safe to re-run.

Currently this manages one hook: the **skill-edit cross-pollination survey**.

## What this hook does

Two scripts work together:
- `skill-edit-marker.sh` (PostToolUse on `Write|Edit`) — notes, per session, when a file
  under any `.claude/commands/` directory is edited.
- `skill-edit-survey.sh` (Stop) — if a command file was edited this session, it blocks the
  stop **once** to inject a reminder: consult `_shared-patterns.md` and survey sibling
  skills for transferable infrastructure before wrapping up, then log a one-line outcome
  to `cross-pollination.log` (which `/quarterly-hygiene` consumes).

**Trade-off to state plainly before enabling:** when you edit a skill file, the hook adds
**one extra turn** at the end of that session. If you don't actively maintain a skill
library, you probably don't want it.

## Steps

1. **Resolve the config root** (honours a custom config dir):
   ```bash
   CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
   ```

2. **Prerequisite — `jq`.** The hook scripts and the wiring script all require it:
   ```bash
   command -v jq >/dev/null 2>&1 && echo "jq: ok" || echo "jq: MISSING"
   ```
   If missing, stop and give the install hint for the user's OS
   (`sudo apt install jq` / `brew install jq` / `sudo dnf install jq`).

3. **Prerequisite — scripts present.** They ship via `/update`; if absent, the user hasn't
   synced yet:
   ```bash
   ls -1 "$CONFIG_DIR/scripts/skill-edit-marker.sh" \
         "$CONFIG_DIR/scripts/skill-edit-survey.sh" \
         "$CONFIG_DIR/scripts/wire-skill-edit-hook.sh" 2>&1
   ```
   If any are missing, instruct the user to run `/update` first, then re-run `/setup-hooks`.

4. **Apply.** If the user passed `--remove`, run with that flag; otherwise add:
   ```bash
   "$CONFIG_DIR/scripts/wire-skill-edit-hook.sh" $ARGUMENTS
   ```
   The script makes a timestamped backup, merges idempotently (no duplicates on re-run),
   validates the JSON before replacing, and prints the resulting `.hooks` block.

5. **Confirm and report.** Show the user the printed `.hooks` block and the backup path.
   Note that the hook takes effect for **new** sessions, and that they can disable it any
   time with `/setup-hooks --remove`.

## Caveats

- The survey reminder points at `_shared-patterns.md` resolved relative to the scripts
  directory (`scripts/../commands/`). This is correct for the standard layout where
  `commands/` and `scripts/` sit together under one `.claude/`. If a user keeps commands
  in a different location from the scripts, the reminder falls back to a generic phrasing.
- This command edits `settings.json` (user-level hooks), **not** `settings.local.json`
  (which Claude Code manages for permission grants). Do not redirect it.
