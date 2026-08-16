---
name: update
description: Update a full-clone OpenCairn installation from its upstream template with signed-ref verification, required vault-migration gates, per-file review, and reviewed copying into the live Codex skills directory. Use when the user invokes $update, asks to update OpenCairn, or wants to preview/pin an OpenCairn update.
---

# Update OpenCairn

Use the canonical updater stored in the OpenCairn checkout. This Codex skill is a harness adapter, not a second updater specification.

## Procedure

1. Resolve the vault:

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   Abort on error. `{VAULT}` is the resolved full-clone root. `$update` is not supported by a skills-only installation with no OpenCairn git checkout; direct that user to clone/reinstall the full template first.

2. Read `{VAULT}/.claude/commands/update.md` **in full before taking any update action**. If absent, stop: the paired updater bundle is incomplete.

3. Execute that canonical procedure exactly, forwarding the user's arguments (`--dry-run`, `--force`, `--tag VERSION`) and applying these harness translations only:

   - `/update` means `$update`.
   - `/migrate` means `$migrate`.
   - Claude Code restart instructions mean end this Codex session and launch a fresh one; already-loaded skill text does not change when its file is replaced.
   - Use Codex commentary for progress and concise plain-text questions when the per-file review needs a decision.
   - Read `~/.codex/skills/_skill-monitor.md` for the final monitor step.

4. Preserve every safety invariant in the source procedure:

   - fetch/signature checks may run before the vault gate, but no checkout/apply may run until required migrations pass;
   - accept/skip repository files individually unless `--force` was explicit;
   - scope commits and recovery to the accepted file list;
   - for the live `~/.codex/skills/` copy, diff every accepted counterpart and ask before overwriting a differing file, even under `--force`;
   - preserve local-only skills and never copy `codex/AGENTS.md` over `~/.codex/AGENTS.md`;
   - report repository and live-install results separately.

5. A running `$update` may update its own `SKILL.md`; finish using the procedure already loaded for this turn, then require a fresh Codex session.
