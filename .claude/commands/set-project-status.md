---
name: set-project-status
description: Move an existing vault project between active, Cold, and Backlog while letting Obsidian heal its links. Use for pausing, reactivating, or returning an unstarted project to Backlog; do not use for completion.
argument-hint: "[Project Name] [active|cold|backlog]"
---

# Set Project Status

**Scoped rule loading:** `_shared-rules-content.md` before moving project notes. Read the applicable numbered sections at that point, from the same directory as the core `_shared-rules.md`; do not preload unrelated supplements.

Change one project's lifecycle state through the standard link-healing move.

## Workflow

1. Resolve the vault with `"$VAULT_PATH/.claude/scripts/resolve-vault.sh"`. Read `_shared-rules.md` from this command's installation and the project-lifecycle section of `07 System/Vault Organisation Principles.md`.
2. Require a project basename and target state. This command only moves among:
   - `active` → `03 Projects/Project Name.md`
   - `cold` → `03 Projects/Cold/Project Name.md`
   - `backlog` → `03 Projects/Backlog/Project Name.md`
   Completion belongs to `/complete-project`.
3. Run the helper in dry-run mode and display its plan:

   ```bash
   python3 "$VAULT_PATH/.claude/scripts/set-project-status.py" \
     --vault "$VAULT_PATH" --project "Project Name" --to cold --dry-run
   ```

   It must find exactly one lifecycle file. It resolves the active-project cap from the vault's organisation principles and reports whether the destination directory needs creating. Do not cool a second project without the user's instruction.
4. Structural moves require the vault's sync client to be on. If the user has not already confirmed that in the current conversation, ask once and wait.
5. Apply the same request with `--apply`. The helper delegates to `locked-edit.sh --move`; the wrapper creates a missing lifecycle directory, lets Obsidian heal links everywhere (including `06 Archive/`), verifies the final paths and old-link absence, and records the move plus exact link-healing deltas for `/park`.
6. Report the old and new status, active-project count and cap, unresolved-link before/after counts, verification state, and move receipt path. If verification says `needs-review`, inspect the reported result rather than retrying or moving the file directly.

Do not hand-edit project status prose merely to mirror the folder. Update meaning-bearing current-state prose only when the user supplied a new state beyond active/cold/backlog.
