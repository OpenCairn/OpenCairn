---
name: migrate
description: Run pending versioned OpenCairn vault migrations and the legacy project-doc task migration with resumable state checks, locked writes, link-aware structural moves, and live Doctor verification. Use when the user invokes $migrate, an OpenCairn workflow reports a required archive migration, or $update is blocked on vault format.
---

# Migrate OpenCairn

Compatibility marker: `archive-bundle-v3`.

Use the canonical migrator stored in the OpenCairn checkout. This Codex skill is the native harness adapter and deliberately stays paired with the Claude-source procedure.

## Procedure

1. Resolve the vault:

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   Do not enforce the archive-layout gate: `$migrate` is its recovery route. `{VAULT}` is the resolved full-clone root.

2. Read these files **in full before acting**:

   - `{VAULT}/.claude/commands/migrate.md`
   - `${CODEX_HOME:-$HOME/.codex}/skills/_shared-rules.md`

   Require the canonical migrate command to contain `archive-bundle-v3`; stop if either file is absent or the command is stale. Required deterministic helpers remain under `{VAULT}/.claude/scripts/`; a skills-only Codex install without the checkout cannot execute the migration.

3. Execute the canonical migration procedure exactly, with these harness translations only:

   - `/migrate` means `$migrate`.
   - `/update` means `$update`.
   - `_shared-rules.md` in the source command means the installed Codex support file already read above.
   - Use Codex commentary for progress and concise plain-text questions for sync confirmation, split-archive collision decisions, or destructive approvals.
   - Read `${CODEX_HOME:-$HOME/.codex}/skills/_skill-monitor.md` for the final monitor step.

4. Preserve the migration invariants: completed journal or canonical ledger evidence is terminal only with a real `06 Archive/OpenCairn` root; completed migrations are never re-audited against later archive growth; only verified `complete` unblocks workflows; vault prose writes use `locked-edit.sh`; linked structural moves follow shared-rules §24; raw `mv` is forbidden; and split archives never auto-merge.
