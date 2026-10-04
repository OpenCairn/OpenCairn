---
name: batch
description: Clear engineering-ticket batches using a supplied queue and runbook, with file-isolated workers, parent integration and review before authorised publication. Use for repository work queues, not arbitrary media or document batch processing.
---

**Shared rules:** load `_shared-rules.md`; load its planning and reviewer supplements at the relevant routing/review steps.

**Arguments:** queue/worklist path, runbook path and repository; use supplied context when already known.

# Batch engineering tickets

Clear an engineering-ticket batch using the supplied queue and runbook. The runbook owns its detailed procedure; this command coordinates it without creating a second policy.

## Inputs and scope

Read the queue/worklist, runbook and repository instructions in full before acting. Use paths already supplied in the conversation. If an input is absent, search the relevant project/area and repository for the existing workflow before asking for a path. Keep the user's publication/install authorisation and limits; a batch request does not grant unrelated external actions.

Inspect each current target before calling an old ticket unfixed. Separate clearly specified ordinary fixes, already-landed work and genuine design, personal or live-use decisions. Preserve original request text and every reported residual. Choose routine implementation details yourself; do not shrink the assignment to the easiest passing subset.

## Execute the runbook

- Group work by owned files. Tickets touching a shared hot file run serially in that lane. Give every worker an explicit worktree, literal ticket text, exact file ownership and the ordinary-use bar; only the parent integrates, acknowledges rendering hashes, publishes, installs or edits the live queue/vault.
- Despatch one worker per disjoint lane with the harness's native agent tools, bounded by the available slots and the user's limit. Workers use fixtures, never the live vault/install, and run only their owned checks. Require failing-before evidence for script defects, aligned Claude/Codex consumers, and literal positive/negative controls for prescribed commands. If required delegation is unavailable, report that concrete boundary; do not claim a delegated run occurred.
- Read each worker's diff and not-done list before signed, path-scoped integration. Verify the complete integrated batch and mapped renderings. Obtain the runbook's ordinary peer review before publication; handle the leaf reviews directly through the shared reviewer protocol, without silently invoking a separate audit skill. Reproduce disputed blockers, fix confirmed batch defects and re-review the changed source until clear.
- Recheck current main/remote and install preimages before shipping within the authorised scope. Verify actual remote HEAD and installed bytes/modes, preserving unrelated concurrent work. A local status or file name is not a remote/publication check.
- Re-read the live queue; match stable literal markers independently of recurrence counts. Close only verified complete scope, rewrite partial items to their residual, and record the published evidence in the existing history/home under canonical locks. Keep the user's task-home rules; do not create duplicate trackers.
- Preserve review/test/ownership evidence before removing only owned worktrees/branches. Run the normal Park closeout with its independent reviewer, retaining every unresolved item honestly. Report what shipped, how it was checked and what remains.
