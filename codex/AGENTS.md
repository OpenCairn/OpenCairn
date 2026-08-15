# Global instructions — OpenCairn on Codex

## Vault location

The Obsidian vault is at `$VAULT_PATH` (normally `$HOME/Files`). Before vault work, confirm it resolves:

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If that errors, stop and report — do not guess a path.

## Vault writes take the lock

This vault runs concurrent agent sessions. ALL writes inside `$VAULT_PATH` — creates, edits, appends, any file — go through the locking wrapper, never through direct file writes, `sed -i`, `tee`, or editor tools:

```bash
"$VAULT_PATH/.claude/scripts/locked-edit.sh" <file> --append        # stdin appended verbatim; creates the file if absent
"$VAULT_PATH/.claude/scripts/locked-edit.sh" <file> --replace      # stdin: OLD text, separator line, NEW text; OLD must match exactly once
"$VAULT_PATH/.claude/scripts/locked-edit.sh" <file> --replace-all  # same stdin shape; replaces every occurrence
```

The separator line for the `--replace` modes is exactly:

```
========OPENCAIRN-LOCKED-EDIT-SEP========
```

Matching is literal, never regex. Exit codes: 0 ok · 1 usage/lock error · 2 OLD not found · 3 OLD ambiguous. On 2 or 3, re-read the file and retry with a unique OLD — never fall back to a direct write.

Reads need no lock.
