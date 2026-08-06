---
name: setup-hooks
description: Opt in to OpenCairn's optional Claude Code hooks (skill-edit cross-pollination survey, /park acceleration)
argument-hint: "[skill-edit|park|all] [--remove]"
---

# Setup Hooks — Opt Into Optional Hooks

You are wiring (or removing) OpenCairn's **optional** hooks into the user's Claude Code
settings. Hooks are opt-in: `/update` deliberately never touches `settings.json`, so this
command is the explicit, reversible way to enable them. Idempotent — safe to re-run.

Two independent hook sets, wired by their own scripts so enabling one cannot disturb the
other. `all` (the default) applies to both:

| Set | Scripts | What it costs |
|---|---|---|
| `skill-edit` | `wire-skill-edit-hook.sh` | one extra turn per skill-edit batch |
| `park` | `wire-park-hooks.sh` | one extra turn per parboil snapshot (1–2 per long session) |

## What the skill-edit hook does

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

## What the park hooks do

Two scripts that make `/park` cheaper, addressing its two structural costs — its wall clock
is dominated by model turns, and per-turn cost rises with the context it runs in:
- `session-ledger.sh` (PostToolUse on `Write|Edit`) — records every file this session
  writes, keyed on the session id. Step 2a's enumeration becomes exact instead of
  reconstructed from mtimes, and §20 attribution comes free.
- `parboil-check.sh` (UserPromptSubmit) — **ships DISABLED**; wiring it is inert until you
  set `OPENCAIRN_PARBOIL_TOKENS` (try `150000`) in `settings.json`'s `env` block. Its payback
  is unproven — it consolidates park's work rather than removing it — so it is opt-in on top
  of the opt-in. Once enabled: when context passes that threshold and the session has written files, it asks for
  a shadow-park snapshot: the session narrative, changed-identifier enumeration and open
  loops, drafted from context already held. `/park` Step 0 adopts or patches it. Refires
  each further `OPENCAIRN_PARBOIL_INTERVAL_TOKENS` of growth, but only when the ledger has
  grown too.

**Trade-off to state plainly before enabling:** the ledger is free (shell only) and is the
part worth having. The parboil is the experimental half and is off unless its env var is
set — each snapshot is **one extra turn**, wasted entirely on a session that never parks.

## Steps

Each snippet resolves the config root inline — shell state does not carry between calls,
so never assign it once and reference it later.

1. **Prerequisite — `jq`.** The hook scripts and the wiring script all require it:
   ```bash
   command -v jq >/dev/null 2>&1 && echo "jq: ok" || echo "jq: MISSING"
   ```
   If missing, stop and give the install hint for the user's OS
   (`sudo apt install jq` / `brew install jq` / `sudo dnf install jq`).

2. **Parse and validate `$ARGUMENTS` FIRST, then check only the selected set's scripts.**
   Accepted tokens are a set name (`skill-edit`, `park`, `all`) and/or `--remove`, in either
   order, nothing else; absent set name means `all`. Anything else — stop, tell the user the
   usage is `/setup-hooks [skill-edit|park|all] [--remove]`, and run nothing. Then check only
   the scripts the selected set needs — checking all six would make `/setup-hooks park` fail
   because a *skill-edit* script is missing, which defeats the point of independent sets.
   They ship via `/update`; if absent, the user hasn't synced yet:
   ```bash
   # skill-edit set (run only if that set is selected)
   CD="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; ls -1 "$CD/scripts/skill-edit-marker.sh" \
         "$CD/scripts/skill-edit-survey.sh" "$CD/scripts/wire-skill-edit-hook.sh" 2>&1
   # park set (run only if that set is selected)
   CD="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; ls -1 "$CD/scripts/session-ledger.sh" \
         "$CD/scripts/parboil-check.sh" "$CD/scripts/wire-park-hooks.sh" 2>&1
   ```
   If any are missing, instruct the user to run `/update` first, then re-run `/setup-hooks`.

3. **Apply.** Run the matching literal form(s) — one script per selected set (never splice
   the raw argument string into the command line). **Note the contract change:** a bare
   `--remove` used to remove the skill-edit hooks only; it now defaults to `all` and removes
   both sets. Say so if the user runs it bare, and offer the targeted forms:
   ```bash
   # skill-edit set:  add / remove
   "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/wire-skill-edit-hook.sh"
   "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/wire-skill-edit-hook.sh" --remove
   # park set:        add / remove
   "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/wire-park-hooks.sh"
   "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/wire-park-hooks.sh" --remove
   ```
   ⛔ **When both sets are selected, run the two scripts SEQUENTIALLY in one Bash call —
   never as two parallel tool calls.** Neither script locks `settings.json`; each does
   read → merge → atomic `mv`. Run concurrently they race, and the loser's hooks are lost
   while **both** scripts print `Updated … Backup: …`, so step 4's reporting table cannot
   detect it. Sequential execution is the whole mitigation.

   Each script makes a timestamped backup, merges idempotently (no duplicates on re-run),
   validates the JSON before replacing, and prints the resulting `.hooks` block.

4. **Confirm and report — branch on what each script actually printed**, per set. Report
   only what is in the output; never describe a backup or a `.hooks` block that wasn't
   printed.

   | Script output | Report |
   |---|---|
   | `Updated … Backup: …` plus a `.hooks` block | Show the user the `.hooks` block and the backup path. |
   | `No changes — hooks already in their target state (…)` | Say the settings already match the requested state; no backup was made and nothing changed. |
   | `No settings file at … — nothing to remove.` | Say there were no hooks to remove. |
   | Non-zero exit (missing `jq`, usage error, unparseable existing settings, produced-invalid-JSON abort) | Settings are unchanged. Show the script's error line verbatim, state the remedy it implies, and stop — do not retry or hand-edit `settings.json`. |

   Whenever the end state is hooks-enabled: **don't assert when they start firing — say how
   to check.** Newly wired hooks may take effect for subsequent tool calls and prompt
   submissions in the *current* session rather than only in new ones, so tell the user to
   confirm by triggering one (edit a file, submit a prompt) and to start a new session only
   if it doesn't fire. They can disable a set any time with `/setup-hooks <set> --remove`.

## Caveats

- The survey reminder points at `_shared-patterns.md` resolved relative to the scripts
  directory (`scripts/../commands/`). This is correct for the standard layout where
  `commands/` and `scripts/` sit together under one `.claude/`. If a user keeps commands
  in a different location from the scripts, the reminder falls back to a generic phrasing.
- This command edits `settings.json` (user-level hooks), **not** `settings.local.json`
  (which Claude Code manages for permission grants). Do not redirect it.
