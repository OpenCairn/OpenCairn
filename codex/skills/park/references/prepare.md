# Batched review preparation

Use on the full Park path after final propagation, routing, attribution and
backfill are complete. This batches already-decided mechanical work; it does
not replace the quality pass, propagation review, source checks or independent
audit. Keep early evidence capture at the point the evidence becomes available.

```bash
python3 "$PARK_REVIEW" prepare --vault "{VAULT}" --session-log "<session log>" --number N <<'JSON'
{
  "classifications": [
    ["--path", "<new or changed file>", "--semantic", "--reason", "<why>"]
  ],
  "captures": [
    {"kind": "propagation", "label": "Step 6 propagation", "text": "<complete report and addendum, or checked-nil result with category checks>"}
  ],
  "identifiers": ["<final completion/value identifier>"]
}
JSON
```

- `classifications` contains argument arrays accepted by `classify`, without
  `--vault` or `--session-id`; both come from the enclosing invocation. Supply
  new or changed classifications only. Existing classifications remain in use.
- `captures` accepts evidence, prestate and propagation records. Evidence also
  needs `source` and `provenance`. Supply real excerpts/reports, never a made-up
  receipt. Existing receipts can be reused by omitting this list. Exact repeated
  evidence/prestate records are deduplicated; distinct excerpts are retained.
- `identifiers` is the final Step 8 list, not a replacement for enumeration.
  Optional `accept_inherited_lint` lists only paths eligible under Step 8's
  existing proof requirement. Omitted fields default to empty lists.

The helper classifies the supplied files, captures the supplied evidence,
derives `--touched` from the session's reconciled Files lists, runs the existing
receipt-wrapped verifier, and builds the independent review brief. Local paths
are normalised and deduplicated; deleted and explicitly nonlocal rows are kept.

Exit 0 means preparation completed, **not** that the audit is clean. A failure
or REVIEW stops before dispatch; inspect the output and fix/triage through the
normal Park rules. Do not use a leftover brief from a failed run. Rerun after
reconciliation; the helper rechecks current bytes rather than trusting the prior
attempt. It refuses a content change during verification/brief generation.

Each attempt saves stage durations under the session's `prepare-runs/` directory
and prints that path. These timings cover helper work, not model deliberation or
reviewer runtime. After success, Step 9 uses the printed brief and digest without
running `build` again. Any subsequent change to the inputs requires preparation
again; every remediation round still receives independent re-audit until clean.
