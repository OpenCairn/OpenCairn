# Semantic second pass

Shared Jev assistance for SOURCE, Park and article synthesis. The caller owns
retrieval, source completeness, decisions and writes. This is triage over supplied
text; it cannot prove search coverage, publish, approve a change or replace review.

Configure `OPENCAIRN_JEV_ROOT`, or `backend_root` in
`~/.claude/semantic-check.json` (shared by both harnesses), to a reviewed checkout of
[hermes-jev-skills](https://github.com/kerpopule/hermes-jev-skills). The adapter reuses
`jevkit.client.ask`, not its installer, model router or Hermes profiles. Supply
`TYPESAFE_API_KEY` through the process environment or the OS keyring entry
`service=scripts key=typesafe-api-key`; never print or embed the key. No extra Python
packages are required. With no configured checkout, follow the ordinary workflow.

When configured, use Jev only for explicitly selected synthetic fixtures or public
text already in scope for the current task. Private, mixed or unclassified vault
and session text stays on the ordinary local review path. Removing names does not
by itself make private material synthetic. Never upload a vault.

Prepare one JSON item per proposition (a complete conditional rule or formula can
be one proposition), with its complete relevant source context. Set `data_class`
to `synthetic` or `public` only when that classification is established; `private`
and `unclassified` return ordinary review without a credential lookup or request.
Do not silently shorten a passage to fit. Input exceeding 24,000 bytes is rejected.
Keep the input locally with the receipt. State fields are strings:

| kind | state fields | Use |
|---|---|---|
| `claim` | `source`, `claim` | Restatements, including user statements, formulas and alternative procedures |
| `propagation` | `change`, `candidate`, `role` | Each retrieved candidate's framing; role comes from its owning document |
| `check` | `hypothesis`, `procedure`, `pass`, `under_negative`, `control` | Whether a proposed verification actually distinguishes the negative case |

Example input:

```json
{"id":"summary-status","kind":"claim","data_class":"synthetic","state":{"source":"The job is queued.","claim":"The job is running."}}
```

Execute with the installed script, keeping stdout as the receipt:

```bash
python3 "{VAULT}/.claude/scripts/semantic-check.py" --input "<item.json>"
```

`--offline` exercises the ordinary-review route without resolving credentials.
The adapter checks the pinned backend import closure before importing it or reading
a credential; changed backend bytes use ordinary review. The receipt binds raw and
canonical input, questions, adapter and backend hashes, and records UTC time, a nonce,
actual answers, model, elapsed time and usage. A changed input requires another receipt. Exit 2
means invalid input, not a pass. Exit 0 can still mean outage or model drift:
always inspect `status` and `action`.

Before accepting a receipt, verify its bindings; for a saved claim, also bind the
verbatim claim to the target:

```bash
python3 "{VAULT}/.claude/scripts/semantic-check.py" --input "<item.json>" --verify "<receipt.json>" --target "<saved-file>"
```

Pass is `status: bindings_match` with exit 0; exit 2 is invalid or changed evidence.
This proves neither the source's truth nor current world state. For a propagation
or check item omit `--target`. A fallback receipt is diagnostic, not gate evidence.

Apply the action visibly, naming the receipt ID and the caller's disposition:

- `revise`: locate the unsupported clause and repair or tag it; recheck revised text.
  If the source comparison contradicts Jev, retain the disagreement and resolve it
  through ordinary review; do not weaken a faithful claim to satisfy a score.
- `review_change`: inspect the owning rule and update stale live text under its lock.
- `limitation`: repair the proposed check or save its limitation explicitly.
- `ordinary_review`: perform the existing manual/source review; never infer approval.
- An action ending in `_candidate`: compare against the evidence before accepting.
  Historical candidates retain history; current/unrelated candidates still require
  a disposition. No candidate authorises skipping an unseen part of the search.

Thresholds are provisional triage cutoffs, not a measured guarantee. A model other
than `jev-1.14.0` routes to ordinary review pending evaluation. On errors or missing
configuration, retain the fallback receipt if invoked and continue the ordinary
workflow. Keep exact arithmetic, hashes, locks, quote presence, file modes,
publication and installation checks in code.
