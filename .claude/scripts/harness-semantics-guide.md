# Harness semantics version warning

`harness-semantics-check.py` is an optional Claude SessionStart diagnostic. It runs only `claude --version` with a timeout, compares the observed version with a locally recorded baseline, and emits advisory context on stdout. It returns zero on missing evidence, CLI failure and drift so an ordinary session can continue. Invalid command-line arguments remain usage errors.

The distribution ships no verification manifest. A missing, unknown or malformed baseline is explicitly unverified. Record evidence only after the scoped checks have actually run, in `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/harness-semantics.json`:

```json
{
  "verified_against": "<version actually tested>",
  "claims": ["<specific harness behavior tested>"],
  "evidence": ["<locally retained test record and section>"]
}
```

The angle-bracket values deliberately fail validation. Version numbers have three numeric components. `claims` and `evidence` must be nonempty string lists; evidence locators are records, not proof that this detector reran those tests. Keep concurrency, Stop decision/reason delivery, UserPromptSubmit stdout delivery and the Read size cap in the verified scope only when their records support that scope. Retired per-write britfix echo behavior stays retired.

Install the script in the runtime scripts directory. An opt-in hook entry inside an existing `hooks.SessionStart` array is:

```json
{
  "matcher": "startup|resume|clear|compact",
  "hooks": [{"type": "command", "command": "python3 \"${CLAUDE_CONFIG_DIR:-$HOME/.claude}/scripts/harness-semantics-check.py\"", "timeout": 10}]
}
```

Merge this entry without replacing unrelated hooks, settings or permissions. The hook runs from the configured runtime directory; the manifest is runtime configuration and must not be copied into a public template. This is Claude wiring, not a Codex hook.

Atomic `mkdir` markers under `${XDG_CACHE_HOME:-$HOME/.cache}/opencairn/harness-semantics` allow one warning per recorded/observed version pair, including concurrent starts. `--cache-dir`, `--manifest`, `--claude` and `--timeout` support isolated checks. A cache inside `VAULT_PATH` is rejected; cache errors emit the advisory warning without suppression. Missing/invalid baselines and version failures always report unknown rather than silently passing. Removing a cache marker permits the corresponding drift warning again. The manifest is never written or advanced by this script. A matching version means only that the stored version equals the observed version.
