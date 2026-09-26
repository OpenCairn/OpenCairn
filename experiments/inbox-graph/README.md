# Inbox graph trial

Research prototype, separate from the installed inbox skill. It runs only on
disposable vault copies carrying `.inbox-graph-trial` with the text
`disposable-copy`. Do not put that marker in a live vault.

```text
scan → Claude routing → validate/render plan → approval pause → execute → verify
```

LangGraph owns SQLite checkpoints and resume. Claude chooses destinations using
the existing inbox skill and an explicit context file; it has no tools in this
node. Pydantic checks the plan shape. Code checks coverage, paths, collisions and
file snapshots, then calls the existing `locked-edit.sh` for every effect.
A separate SQLite effect ledger reconciles a move or edit that landed before a
node checkpoint. `steps.jsonl` records node starts, completions, pauses and errors.

## Run

Use Python 3.11+ on Linux. Install `requirements.txt` into a dedicated virtual
environment with the host's package cooldown enabled. Tests also need pytest.
Supply a disposable fixture with `02 Inbox/`, any relevant destination/hub files,
and the repository's scripts and their dependencies under `.claude/scripts/`.
The context text should contain the available destination inventory, relevant
hub contents and applicable task-routing policy. Missing context may produce ASK.

```bash
python inbox_graph.py start --vault /path/to/copy --context /path/to/context.txt --run-dir /path/outside/copy/run
python inbox_graph.py status --run-dir /path/outside/copy/run
# Inspect run/plan.md; use the exact displayed hash:
python inbox_graph.py approve --run-dir /path/outside/copy/run --plan-hash HASH
# After an execution error, inspect and resolve its cause before resuming:
python inbox_graph.py resume --run-dir /path/outside/copy/run
python -m pytest test_inbox_graph.py -q
```

`reject` with the displayed hash ends the run without writes. A pending approval
cannot be bypassed by `resume`. Run directories hold private source contents,
model outputs and checkpoints; keep them outside the public repository and vault.

## Trial boundaries

- Text is read in full. PDFs use `pdftotext` when available. Unviewed images,
  unreadable files, other binaries and bundles are ASK/DEFER; there is no deletion
  executor. Supporting the original skill's full mixed-media inbox is unfinished.
- Patches are exact, approved before/after Markdown. There is no semantic checker
  for whether Claude chose the right hub, extracted an action correctly, or should
  have added an index link. Schema validity is not routing correctness.
- The fixture uses the repository's existing Obsidian test double through
  `OBSIDIAN_CLI`. This exercises the real locked mover and simulated link healing,
  not a live Obsidian/sync-client integration. Live structural-query checks and
  sync confirmation are outside this prototype.
- Moves preserve the original content hash. A move that heals a source's own
  links, another pending source, or a previously patched file may stop the run.
  It needs inspection/replanning, not blind retries. No batch rollback is promised.
- Keep/kill needs a same-batch prose comparison and measured human review time.
  One successful batch and failure-injection tests do not establish superiority.

Framework references: [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
and [persistence](https://docs.langchain.com/oss/python/langgraph/persistence).
