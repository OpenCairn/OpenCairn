# Park measurements

`park-metrics.py` measures complete park requests from local Claude and Codex transcripts. It runs outside the vault, uses a locked atomic state store, and sends nothing over the network. It retains timestamps, counts and source locations, not conversation text.

## Collection and report

```bash
python3 "$VAULT_PATH/.claude/scripts/park-metrics.py" collect --since 2026-09-01T00:00:00Z
python3 "$VAULT_PATH/.claude/scripts/park-metrics.py" report
```

Choose the collection start for the trial; keep it fixed. Schedule collection every five minutes with a user timer or equivalent. The collector caches unchanged source files; file activity invalidates the cache, while **transcript event dates** determine the measurement window. State defaults to `~/.local/state/opencairn/park-metrics/`. `runs.json` is the analysis dataset; `annotations.json` holds explicit observations; `cache.json` preserves measurements if transcripts are later removed. Global `--state`, `--claude-root` and `--codex-root` options support isolated testing.

The collection output reports the source-file inventory, parse errors and run count. A nonzero exit or parse errors means inspect the named source before trusting its measurements. An empty result is not a successful trial. `collected_at` must advance on a scheduled run; inspect the scheduler's last result as well as its enabled state.

## Boundaries and limitations

- Start: an actual `/park` or `$park` request, a Claude command envelope, or a standalone Codex park-skill invocation. Repeated skill expansion does not start a second run; quoted mentions and unrelated injected instructions do not count.
- End: Codex's matching turn-completion event or final response; Claude's last `end_turn` text before a new genuine user request, allowing asynchronous reviewer continuations. No idle-gap cutoff. A later continuation can revise a provisional Claude endpoint.
- A returned response is not necessarily a successful park. Summary timing includes only explicit `Parked`/merge confirmations, excludes incomplete parses, and separates requested quick mode. Blocked/unfinished requests remain visible in the dataset.
- User interruption ends the measured request; a conversational backfill that does not invoke park is not a new park. Time includes waits, model latency and any work done during the request. It is **not** active human time or pure model thinking time.
- `tool_calls` counts top-level harness calls, so Claude and Codex counts are not directly equivalent. `tool_error_results` counts explicit tool error flags only: zero does not establish no semantic errors or no failing shell commands. `prepare_calls` detects invocation-shaped text in tool arguments, not proof that preparation succeeded.
- Review/finding counts below are reported by the closing agent. Human measurements require the user's own report. Missing fields stay unknown, never zero. Historical runs are not silently assigned review counts.
- Compare full-run minutes by harness, mode and workload. Changing models, task complexity and concurrent work confound before/after comparisons. Raw timing does not establish that batching caused a gain.

## Close-out record

The park instructions carry this once-per-close-out operation. It can be batched with the final export command; do not introduce another review or wait for collection.

```bash
python3 "$VAULT_PATH/.claude/scripts/park-metrics.py" record --harness codex --session-id "$CODEX_THREAD_ID" --outcome completed --review-rounds 2 --correction-rounds 1 --confirmed-findings 3
```

The numbers are an example, **not defaults**. Use `--harness claude --session-id "$CLAUDE_CODE_SESSION_ID"` for Claude (resolve its session ID through `lib-session.sh` if necessary). The command locates the latest park request in that actual harness transcript; it must not use a reviewer or invented follow-up session ID. It prints the stable run ID. Timing is collected after the final response, not stopped by this command.

Definitions:
- `review_rounds`: completed independent audit reports, including the final clean pass; exclude propagation seats and report-only recovery messages.
- `correction_rounds`: rounds of changes made in response to confirmed audit findings; exclude changes made before the first audit.
- `confirmed_findings`: distinct audit findings accepted as real during this park, including unresolved findings; do not recount a repeated finding. This does not enumerate all possible defects.
- `outcome`: completed, blocked, or aborted. Record blocked before yielding on an unresolved audit. Quick success has zero audit rounds/findings only when the quick eligibility checks actually passed.

If counts cannot be reconstructed, omit those flags and retain unknown. Measurement failure is visible but does not block the user's park. No guessed counts and no automatic question at each park.

## Human review effort

When the user reports effort or a later correction, attach it to the named run:

```bash
python3 "$VAULT_PATH/.claude/scripts/park-metrics.py" record --run-id RUN_ID --human-review-minutes 4 --human-corrections 1
```

These are cumulative totals for that run; replacing a value does not add to it. Only record zero on an explicit user report. Agent runtime, waiting time, an absence of complaints and an agent's clean audit are not measures of human effort. The report shows coverage, so a trial with no human reports cannot claim unchanged human review burden.
