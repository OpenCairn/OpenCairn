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
  stop **once** to inject a reminder: first a **placement check** on what was just written
  (durable procedure stays in the skill, volatile facts move out — this gate can reverse
  the edit), then consult `_shared-patterns.md` and survey sibling skills for transferable
  infrastructure, then log a one-line outcome to `cross-pollination.log` (which
  `/quarterly-hygiene` consumes). Trivial edits — typo, wording, one-liner — are carved out
  of the survey.

**Trade-off to state plainly before enabling:** when you edit a skill file, the hook adds
**one extra turn per edit batch** — a session with several separate rounds of skill edits
pays it several times. If you don't actively maintain a skill library, you probably don't
want it.

## Steps

Each snippet resolves the config root inline — shell state does not carry between calls,
so never assign it once and reference it later.

1. **Prerequisite — `jq`.** The hook scripts and the wiring script all require it:
   ```bash
   command -v jq >/dev/null 2>&1 && echo "jq: ok" || echo "jq: MISSING"
   ```
   If missing, stop and give the install hint for the user's OS
   (`sudo apt install jq` / `brew install jq` / `sudo dnf install jq`).

2. **Prerequisite — scripts present.** They ship via `/update`; if absent, the user hasn't
   synced yet:
   ```bash
   CD="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; ls -1 "$CD/scripts/skill-edit-marker.sh" \
         "$CD/scripts/skill-edit-survey.sh" \
         "$CD/scripts/wire-skill-edit-hook.sh" 2>&1
   ```
   If any are missing, instruct the user to run `/update` first, then re-run `/setup-hooks`.

3. **Apply.** First validate `$ARGUMENTS`: the only accepted values are empty or exactly
   `--remove`. Anything else — stop, tell the user the usage is
   `/setup-hooks [--remove]`, and run nothing. Then run the matching literal form (never
   splice the raw argument string into the command line):
   ```bash
   # add
   "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/wire-skill-edit-hook.sh"
   # remove
   "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/wire-skill-edit-hook.sh" --remove
   ```
   The script makes a timestamped backup, merges idempotently (no duplicates on re-run),
   validates the JSON before replacing, and prints the resulting `.hooks` block.

4. **Confirm and report — branch on what the script actually printed.** Report only what is
   in the output; never describe a backup or a `.hooks` block that wasn't printed.

   | Script output | Report |
   |---|---|
   | `Updated … Backup: …` plus a `.hooks` block | Show the user the `.hooks` block and the backup path. |
   | `No changes — hooks already in their target state (…)` | Say the settings already match the requested state; no backup was made and nothing changed. |
   | `No settings file at … — nothing to remove.` | Say there were no hooks to remove. |
   | Non-zero exit (missing `jq`, usage error, unparseable existing settings, produced-invalid-JSON abort) | Settings are unchanged. Show the script's error line verbatim, state the remedy it implies, and stop — do not retry or hand-edit `settings.json`. |

   Whenever the end state is hooks-enabled, note that the hook takes effect for **new**
   sessions, and that they can disable it any time with `/setup-hooks --remove`.

## Caveats

- The survey reminder points at `_shared-patterns.md` resolved relative to the scripts
  directory (`scripts/../commands/`). This is correct for the standard layout where
  `commands/` and `scripts/` sit together under one `.claude/`. If a user keeps commands
  in a different location from the scripts, the reminder falls back to a generic phrasing.
- This command edits `settings.json` (user-level hooks), **not** `settings.local.json`
  (which Claude Code manages for permission grants). Do not redirect it.
