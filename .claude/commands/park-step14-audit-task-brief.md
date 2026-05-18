# Step 14 Audit Task Brief

This file is the task brief the audit sub-agent invoked by /park Step 14 must execute. The dispatching session passes session-specific values (vault path, session log path, session number, file list, summary) as inputs; the framing and discipline below is the same on every despatch.

**You are the audit sub-agent for /park Step 14.** The dispatching session has embedded the audit inputs in its prompt to you:

- `VAULT_PATH` — the absolute vault path (no placeholders)
- `SESSION_LOG_PATH` — `<VAULT_PATH>/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`
- `SESSION_NUMBER` — the integer N
- `FILE_LIST` — every file the session+park touched, verbatim from the session log's `### Files Created` and `### Files Updated`
- `SESSION_SUMMARY` — verbatim from the session log's `### Summary`

## What to audit

Session N of `SESSION_LOG_PATH` and all files the session+park touched. The session itself accomplished: `SESSION_SUMMARY`. The park+session edited: `FILE_LIST`.

Layer 3 must include not just identifiers /park changed, but world-state framings rendered stale by what the session DID — e.g. if the session sent a message, hubs that previously described the send as upcoming may now be stale even though /park didn't edit them. Read each touched project/area hub IN FULL (not just the subsection that was edited) before claiming clean.

## Protocol to follow

Read `~/.claude/commands/audit.md` Phase 2 (Layers 1-5) first. Do not recall layers from memory.

## Enumeration discipline

List identifiers as `old → new` pairs OR explicit nil-case checklist:
- Row removals
- Content corrections
- Naming changes
- Status flips
- Section relocations
- New named state introduced
- **Phase/status framings rendered historical by session actions** ← the category inline audits keep missing

For the last category, give extra interrogation: for each project/area hub the session touched, search for prose like `upcoming`, `planned`, `pending`, `will`, `next`, `forthcoming`, `awaiting` near references to work the session completed; flag every hit.

## Script paths

Substitute `VAULT_PATH` into:
- `<VAULT_PATH>/.claude/scripts/update-session-section.sh` — for session-log edits (preserves flock concurrency safety against parallel /park or /goodnight)
- `<VAULT_PATH>/.claude/scripts/backfill-files-updated.sh` — to record any remediation edits into Session N's Files Updated section

## Locking constraint

For session-log edits, use `update-session-section.sh` — concurrent parks via Edit tool race and silently clobber. For other vault files, Edit tool is acceptable but assume single-session execution.

## Read-coverage backstop

If `FILE_LIST` contains more than 5 project/area hubs to read in full, split the audit across multiple passes rather than truncating any read. Report bytes-read per hub in your final report so the main session can verify plausible coverage. Sub-agent summaries have been observed to drift on ordinal detail under context pressure — bytes-read evidence prevents silent truncation.

## Authority to remediate

Use Edit / Bash / the scripts above to fix findings inline. Re-audit after each fix; iterate until clean (per audit.md Phase 4).

## Report format expected back

- Per-layer findings (or nil-case statements that explicitly name what was checked — generic affirmations like "approach is sound" are not acceptable)
- List of remediation edits with file paths + summary of change
- Bytes-read-per-hub for read-coverage verification
- Final clean-pass confirmation OR explicit "could not clean — N issues remain because X" if iteration stalled

## Why this file exists

The dispatching session previously reconstructed this brief from inline park.md prose every time, costing 17-23s of token-gen per /park run. Every defensive element (read-coverage backstop, locking constraint, enumeration discipline, framings-rendered-historical category, etc.) is unchanged — only the *location* of the content moved. Per the defensive-mechanism guardrail in plan-v4: content stays, assembly mechanism becomes mechanical.

Sibling file: `park-step12d-propagation-protocol.md`.
