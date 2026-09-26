# Claude Park: batched preparation

Use after final propagation, open-loop routing and attribution are reconciled.
Keep the preceding quality and SOURCE checks and the independent audit. This
helper packages their inputs; it does not replace their judgment.

```bash
python3 "{VAULT}/.claude/scripts/park-prepare.py" --vault "{VAULT}" --session-log "<session log>" --number N <<'JSON'
{
  "backfill": ["- <path> - <what changed>"],
  "identifiers": ["<final completion/value identifier>"],
  "propagation": "<actual report and addendum, or checked-nil result with category checks>",
  "evidence": [
    {"label": "<claim>", "source": "<URL/tool/path>", "provenance": "primary", "text": "<verbatim evidence>"}
  ],
  "prestate": [],
  "coverage": []
}
JSON
```

Only `propagation` is required. Omit empty lists. `backfill` is the reconciled
park-time delta, not an inferred inventory; the normal locked backfill script
preserves existing descriptions. Explicitly extend descriptions and close log
open loops through their normal steps before calling the helper.

`evidence` and `prestate` use the same fields, with provenance `primary`,
`secondary` or `unverified`. Derive evidence coverage per shared §16; an empty
list is not proof that no evidence was used. Supply real text, never a guessed
or synthetic report. All provided excerpts remain separate.

Ordinary UTF-8 files up to 64 KiB are included in full. Carry Step 2's exceptions
in `coverage` before invoking the helper:

- Imported reference: `{"path":"<exact Files row path>","kind":"reference","receipt":"<absolute park-artifact receipt path>","targets":["<passage actually used>"]}`.
- Large semantic artefact: the same fields with `kind: "large"` and explicit targets.
- Remote or secret-bearing file: `{"path":"<exact Files row path>","kind":"nonlocal"}`; represent it through the supplied evidence. No source body is packaged.

The helper runs locked backfill, derives and deduplicates all Files-list paths,
runs the existing verifier, checks that inputs stayed unchanged, and writes a
hashed `audit-inputs.md`, manifest and timings outside the vault. Reference and
large-file receipts must match current source and review-copy hashes. Only the
selected session is included from the log. An attempt never overwrites an older
packet; use only the path printed by the current successful attempt.

FAIL or REVIEW stops before producing an audit packet. Reconcile or triage via
Step 8, then rerun. Inherited-lint exceptions keep the existing standalone
verification and manual brief path; the helper does not waive them. A landed
backfill is retained after a later failure, and retries deduplicate its rows.

At Step 9, supply the generated packet and its SHA-256 alongside the existing
reviewer protocol, attribution/deletion rules and evidence-attestation table.
Require the reviewer to verify its digest before reading. **Preparation PASS
is not audit PASS.** Claude's reviewer still remediates and re-audits until clean.
