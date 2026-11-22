# Park startup receipts

`park-preflight.py` gathers read-only startup data for an explicit Park request. Native mode consumes UserPromptSubmit JSON, saves the complete JSON receipt bundle as a new owner-only file `<config-dir>/.session-state/<session-id>.park-preflight.<UTC time>.<pid>.json`, and emits `hookSpecificOutput.additionalContext` containing a bounded summary: session binding, per-command statuses, source hashes, ledger and task-candidate counts, and the receipt's absolute path and digest. Hook output over 10,000 characters reaches the model only as a short preview, so the code holds the whole output to at most 9,000, dropping paths and hashes (the receipt keeps them) rather than exceeding it. If the receipt cannot be written, the summary says so and carries no path. Ordinary prompts, questions about Park, quotations, fenced code and pasted prose emit nothing. Direct `/park` and `$park` forms support flag arguments, including `--quick`. Anchored command-name/command-message and skill-name expansions are supported for compatibility; matching expansion metadata is treated as a request, not authenticated by this parser.

[Claude's hook reference](https://code.claude.com/docs/en/hooks#userpromptsubmit) documents context delivery. An opt-in handler inside the existing `hooks.UserPromptSubmit` array is:

```json
{
  "hooks": [{"type": "command", "command": "python3 \"<installed-scripts-dir>/park-preflight.py\"", "timeout": 20}]
}
```

Merge the handler without replacing other settings or hooks; resolve `<installed-scripts-dir>` beside the loaded commands tree and install the helper there first. `CLAUDE_CONFIG_DIR` selects settings/state, not shipped code. No prompt matcher is used in settings: the helper filters the actual prompt. The hook event's `session_id` binds the ledger, overriding inherited parent/child environment IDs. Missing or invalid event identity stays unknown rather than using a different session. `cwd` is recorded for every command; when an event omits it, the hook's actual working directory is used.

Codex can call the same helper at setup, in its first tool call:

```bash
python3 "${VAULT_PATH:?VAULT_PATH not set}/.claude/scripts/park-preflight.py" --manual --session-id "${OPENCAIRN_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-${CODEX_THREAD_ID:-}}}"
```

Manual mode returns the bundle directly as JSON and identifies the session source; with `--receipt <new path outside the vault>` it writes the bundle there and prints the same bounded summary. This is a normal tool call, not a Codex UserPromptSubmit hook or a claim that data arrived before its first model turn. Keep a dispatched writer's actual parent `OPENCAIRN_SESSION_ID` in that call.

The bundle runs these commands sequentially, with a two-second per-command timeout by default (`--timeout` allows up to ten):

- `date +%Y-%m-%dT%H:%M:%S%z TZ=%Z` captures local clock, date, UTC offset and timezone abbreviation.
- `bash "$VAULT_PATH/.claude/scripts/resolve-vault.sh"` validates the configured vault. An unavailable or failed resolver leaves the vault unknown and skips dependent reads.
- `bash "$RESOLVED_VAULT/.claude/scripts/session-ledger.sh" --read` reads the bound parent ledger, preserving its existing coverage and concurrent-session notices.
- `rg --hidden --no-ignore --no-heading --line-number -e '^\s*[-*+]\s+\[ \]\s' -- "$RESOLVED_VAULT/01 Now/This Week.md"` and the same command for `Tickler.md` collect unchecked task candidates.

The targets are those fixed planning files, not all task homes or the whole vault. Receipts retain argv, cwd, completion/timeout/command-error status, exit status, complete stdout/stderr, exact raw bytes as base64, elapsed milliseconds and output byte counts. Receipt output is not truncated; its scope is bounded by the selected commands and files. Timeouts terminate the process group and retain captured bytes. The bundle distinguishes checked-empty from missing file, no ledger, unknown session and command error. File hashes surround the ledger/task reads; changed sources do not become checked results. Resolver and ledger helper dependencies are hashed too. Ledger rows remain candidates for attribution, not a complete mutation census.

The helper writes only its own receipt file (never in manual mode without `--receipt`), calls no model and skips no Park review. The session ledger hook's sweep of state files older than 14 days removes old receipts. The startup candidate index has no final loop needles and always says `final_dedup_complete: false`. At Step 7, perform the existing literal phrase/subject searches and semantic comparison across the task's actual destinations using fresh reads before writing.

`python3 park-preflight.py --revalidate /path/to/receipt.json`, given the hook's receipt or a manual bundle saved outside the vault, compares its source hashes with current files. Changed, missing or previously unchecked sources invalidate reuse. Even matching hashes do not authorise writes or complete dedup; always fresh-read and recompute before a write. The helper does not persist a cache or change task homes.

Measure helper milliseconds and output bytes when comparing runs. Those measurements do not establish model wall-clock savings or native delivery: verify delivery separately on an ordinary authorised invocation.
