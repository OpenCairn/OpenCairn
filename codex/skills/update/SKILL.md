---
name: update
description: Update a full-clone OpenCairn installation from its upstream template with signed-ref verification, required vault-migration gates, per-file review, and reviewed copying into the live Codex skills directory. Use when the user invokes $update, asks to update OpenCairn, or wants to preview/pin an OpenCairn update.
---

# Update OpenCairn

Compatibility marker: `archive-bundle-v3`.

Use the canonical updater stored in the OpenCairn checkout. This Codex skill is a harness adapter, not a second updater specification.

## Procedure

1. Resolve the vault:

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   Abort on error. `{VAULT}` is the resolved full-clone root. `$update` is not supported by a skills-only installation with no OpenCairn git checkout; direct that user to clone/reinstall the full template first.

   Change the working directory to `{VAULT}` and require `git rev-parse --show-toplevel` to resolve exactly to `{VAULT}` before executing any relative path or git command.

2. Read `{VAULT}/.claude/commands/update.md` **in full before taking any ordinary update action**. Require it to contain `archive-bundle-v3`; do not execute a pre-gate canonical updater.

   If the canonical updater is absent or stale, this adapter's only permitted bootstrap is the following exact recovery:

   - From the bound checkout, identify the Git remote whose URL contains `OpenCairn`, fetch it, and select the requested signed tag or that remote's default branch. A requested tag must pass `git verify-tag`; a branch commit should pass `git verify-commit`, with the canonical unsigned-commit warning and explicit user confirmation if it does not. Never recover from an unverified or unidentified ref.
   - Require these nine paths to exist at that ref and contain `archive-bundle-v3`: `.claude/commands/update.md`, `.claude/commands/migrate.md`, `.claude/scripts/check-archive-layout.sh`, `.claude/scripts/archive-namespace-migration.py`, `.claude/scripts/locked-edit.sh`, `.claude/scripts/lib-lock.sh`, `.claude/scripts/lib-session.sh`, `codex/skills/update/SKILL.md`, and `codex/skills/migrate/SKILL.md`. Use `git ls-tree` and `git grep <ref> -- <paths>`; do not use `git show ref:path`.
   - Resolve the verified ref to one immutable commit ID and use that literal ID throughout. Show `git diff <commit> -- <the-nine-literal-paths>` as one review. Under `--dry-run`, report the required recovery and stop without writing. Otherwise capture missing/type/mode/hash preimages, ask once even under `--force`, recheck every preimage immediately before checkout, check out exactly those paths together, verify all nine markers and executable helper modes, then commit only those nine paths.
   - Re-read the recovered canonical updater in full and continue at its Step 3d. If any bootstrap check fails, stop with the exact failed check and the nine-path list above; do not invent another recovery route.

3. Execute that canonical procedure exactly, forwarding the user's arguments (`--dry-run`, `--force`, `--tag VERSION`) and applying these harness translations only:

   - `/update` means `$update`.
   - `/migrate` means `$migrate`.
   - Claude Code restart instructions mean end this Codex session and launch a fresh one; already-loaded skill text does not change when its file is replaced.
   - Use Codex commentary for progress and concise plain-text questions when the per-file review needs a decision.
   - Read `${CODEX_HOME:-$HOME/.codex}/skills/_skill-monitor.md` for the final monitor step.

4. Preserve every safety invariant in the source procedure:

   - fetch/signature checks may run before the vault gate; the only pre-gate writes are the canonical Step 3d nine-file `archive-bundle-v3` recovery closure and its separately reviewed live `update`/`migrate` adapters;
   - abort on unrelated staged content; resume staged managed replacements only through the canonical immutable-target comparison and explicit commit review;
   - probe the helper's exact three-line `gate --status` contract before the wrapper and treat gate/helper/migrate as one all-or-nothing archive-core unit;
   - review every existing differing repository file even under `--force`; force may auto-accept only true additions;
   - separate review from apply, recheck missing/type/mode/hash preimages before checkout, and scope commits to the accepted file list;
   - never restore accepted files automatically from a historical `HEAD`; interrupted updates resume from a fresh target diff;
   - for the live `${CODEX_HOME:-$HOME/.codex}/skills/` copy, diff every accepted counterpart and ask before overwriting a differing file, even under `--force`;
   - reject symlinks/unexpected types and recheck live-copy missing/type/mode/hash preimages immediately before copying;
   - preserve local-only skills and never copy `codex/AGENTS.md` over `~/.codex/AGENTS.md`;
   - report repository and live-install results separately.

5. A running `$update` may update its own `SKILL.md`; finish using the procedure already loaded for this turn, then require a fresh Codex session.
