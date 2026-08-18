---
name: migrate
description: Run pending versioned OpenCairn vault migrations and the legacy project-doc task migration
---

# Migrate - OpenCairn Vault Migrations

Compatibility marker: `archive-bundle-v3`.

Run required vault migrations without letting infrastructure updates silently outrun the vault layout. Versioned migrations are live-state checked and resumable; the older task-system conversion remains component-wise and consent-gated.

When `/update` handed off to this procedure, return to the suspended update immediately after migration verification. A directly invoked migration may finish normally; a subsequent `/update` is safe and idempotent.

## 0. Resolve and load rules

Run:

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

Do **not** run `check-archive-layout.sh --enforce` here: this skill is the recovery route that enforcement deliberately leaves open. Read `_shared-rules.md` from this skill's commands directory and apply it throughout, especially §5 (locked vault writes), §12 (grep-hit triage), §23 (evidence), and §24 (structural moves). `{VAULT}` is the resolved path.

Require these helpers before continuing:

```bash
test -x "{VAULT}/.claude/scripts/check-archive-layout.sh"
test -x "{VAULT}/.claude/scripts/archive-namespace-migration.py"
test -x "{VAULT}/.claude/scripts/locked-edit.sh"
test -r "{VAULT}/.claude/scripts/lib-lock.sh"
test -r "{VAULT}/.claude/scripts/lib-session.sh"
command -v python3
```

If one is absent, stop: the installed migration bundle is incomplete. A full-clone user should rerun `/update` and accept the nine-file `archive-bundle-v3` recovery set; a Codex user should also accept the paired live `update` and `migrate` adapters from that checkout. Do not improvise the migration from partial instructions.

Before any versioned archive migration, run the pre-2026-08 task-format probes in §2. If any outstanding component remains, execute §2 first. After its Doctor report, re-run the same probes. If a required component remains `later` or its live check fails, stop. Otherwise print `✓ Task-system migration complete — continuing to the archive namespace migration` and return directly to §1 in this same invocation. This preserves the supported order for both intact v0.8.0 users and partial updates recovered by the current bundle without making them invoke migration twice: task-system revamp first, archive namespace second.

## 1. Versioned migrations

### Registry

Current required migration:

| Migration ID | Purpose | Blocking |
|---|---|---|
| `archive-namespace-opencairn-v1` | Rename `06 Archive/Claude/` to `06 Archive/OpenCairn/` and repair live locators | Yes |

Versioned outcomes live in a separate `## Versioned migrations` table in `07 System/Migration Record.md`:

```markdown
| Migration | State | Last checked |
|---|---|---|
| archive-namespace-opencairn-v1 | complete | YYYY-MM-DD |
```

Allowed states: `in-progress`, `blocked`, `deferred`, `declined`, `complete`. Only verified `complete` unblocks incompatible workflows. Preserve the legacy component table and its `now/later/never` vocabulary unchanged; the helper updates only the versioned row.

### Inspect live state

```bash
"{VAULT}/.claude/scripts/check-archive-layout.sh" --status "{VAULT}"
python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" inspect "{VAULT}"
```

Read the three-line gate result first. A valid completed journal, or a canonical completed ledger row when no journal exists, is terminal only while the physical topology is `new-root-only`; the gate then reports `new-only` without rescanning live prose or re-hashing a historical inventory. Skip `inspect` in that terminal state. When the journal phase is `complete`, run `finish` once to repair a missing, stale, or duplicated secondary ledger row without scanning or hashing, then proceed to Doctor. With no journal, the already-canonical ledger row needs no repair. `complete-journal-topology-mismatch` or `complete-ledger-topology-mismatch` is contradictory evidence: stop and inspect the two archive paths manually. Do not recreate, move, or delete either root automatically.

For non-terminal states, `inspect` reports both directory paths, actionable old-path files, excluded immutable/transcript hits, and the transaction-journal phase. The scanner is standard-library Python and does not depend on `rg`.

If `journal_phase` is `invalid`, report `journal_error` and the journal path. The gate and mutating subcommands deliberately fail closed on an invalid journal. Ask the user to inspect and remove or quarantine that single journal in their file manager, then rerun `/migrate`; never delete it silently or treat it as absent without approval.

#### `empty-clean`

This is a fresh vault with neither archive tree nor actionable legacy locator. Initialise the new archive root before recording completion:

```bash
python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" archive-root --write "{VAULT}"
```

Proceed to §2.

#### `new-only`, `new-with-legacy-locators`, or gate state `pending-verification`

This is normally an interrupted journal-backed migration. Never infer completion from the directory name. If `journal_phase` is absent and the layout is `new-only`, treat it as an already-compatible/fresh layout: record the verified no-op with `record complete` and proceed to Doctor. If the journal is absent and the layout is `new-with-legacy-locators`, run `rewrite`, confirm the layout becomes `new-only`, record `complete`, and proceed to Doctor. Do not manufacture a pre-move journal after the fact.

When an `in-progress` journal exists, run the remaining phases idempotently:

```bash
python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" rewrite "{VAULT}"
python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" finish "{VAULT}"
```

`finish` verifies the folder state and actionable locator count, the pre-move member inventory, and byte identity of excluded provenance snapshots before atomically completing the journal and recording `complete`. A completed journal is terminal: repeated `rewrite`, `verify`, `verify-immutable`, and `finish` calls check only its compatibility with the physical `new-root-only` topology and never reinterpret later archive growth as migration corruption. If an in-progress finish fails, record `blocked`, report the exact failed postcondition, and stop.

`pending-verification` is emitted by the shared gate when the directory/locator layout is otherwise safe but the transaction journal is not `complete`; only `finish` may clear it.

#### `old-only`

This is the normal migration path.

1. Ask for one confirmation: **Obsidian Sync (or the user's vault sync client) is active, and all other vault-writing agent sessions are stopped.** Do not begin without it. This is a structural maintenance window; per-file locks cannot coordinate with Obsidian's link-healing writes.

2. Read the vault's search/tool routing documentation if present. Capture a reliable unresolved-link baseline and state the route plus count. An empty result without the route's documented positive control is unknown, not zero.

3. Start the resumable transaction:

   ```bash
   python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" begin "{VAULT}"
   ```

   This records `in-progress` and atomically writes a journal containing the logical source-member inventory (lock artefacts excluded) and immutable-file hashes. If the source changes on a repeated `begin`, stop.

4. Rename the folder **inside Obsidian** from `Claude` to `OpenCairn`, so the application heals path-qualified wikilinks. If an installed Obsidian CLI is to perform it, first follow `_shared-rules.md` §24 in full: derive syntax from `help`, prove folder support, use a canary, wait for async settlement, and verify by source/destination state rather than exit code. If folder rename support cannot be verified, ask the user to do the single File Explorer rename in Obsidian. Never use raw `mv`.

5. Re-run `inspect`. The old directory must now be absent and the new directory present. Then repair remaining live plain-text locators through the deterministic locked-edit engine:

   ```bash
   python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" rewrite "{VAULT}"
   ```

   The engine replaces literal forward- and backslash `06 Archive/Claude` locators, including an exact archive-root value with no trailing separator, across the declared text/config/script/web formats plus extensionless files, one file at a time through `locked-edit.sh --replace-all`; binary/media files are ignored. It excludes `07 System/.Provenance/`, `07 System/.OpenCairn Migration/`, `.Session Transcripts/` under the Claude/OpenCairn archive namespaces, lock files, and the Migration Record. `inspect` reports this actionable scan surface separately from excluded immutable hits; it is not a universal binary-file claim.

6. Let Obsidian's index settle. Re-run the same reliable unresolved-link route used for the baseline. The count must not increase, and no moved archive target may be unresolved. Then finish:

   ```bash
   python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" finish "{VAULT}"
   ```

   If the structural link check or `finish` fails, record `blocked` and stop. Do not mark completion from this run's memory.

#### `legacy-symlink-alias`, `legacy-symlink-unsafe`, or `new-symlink-unsafe`

A legacy symlink is not a second archive tree and must never enter per-member reconciliation. Run:

```bash
python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" split-plan "{VAULT}"
```

The report identifies the link target and whether it resolves to the new archive. Do not traverse the old path, move a member through it, or delete a supposed duplicate through it: that would mutate the target tree. Record `blocked` and stop.

For `legacy-symlink-alias`, explain that only the compatibility link itself must eventually be removed, after all pre-rename agent sessions have exited. Ask the user to remove that single alias in their file manager, explicitly distinguishing it from the `OpenCairn` target, then rerun `/migrate`. For `legacy-symlink-unsafe`, report the literal link target and ask the user to resolve or remove the link; do not guess its intent.

For `new-symlink-unsafe`, report the literal target and stop. The active OpenCairn archive root must be a real directory inside the resolved vault; do not traverse or rewrite through the link.

#### `empty-with-legacy-locators`

No archive tree exists, but live files still carry legacy locators. Run `rewrite`, confirm the layout becomes `empty-clean`, then run `archive-root --write` so the real new root exists before the concurrency-safe ledger write. Proceed to Doctor. There is no folder inventory to migrate.

#### `split`

Both trees contain live state. Do not merge or delete automatically. Record `blocked` and generate the collision inventory:

```bash
python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" record "{VAULT}" blocked
python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" split-plan "{VAULT}"
```

The report separates old-only, new-only, byte-identical, and conflicting relative paths and binds every entry to the observed SHA-256 value(s). Present the counts and full conflict list. Re-check the recorded hash immediately before any approved action. Reconciliation is explicit:

- old-only entries: propose link-aware moves into the new tree;
- new-only entries: retain;
- identical collisions: propose deletion of the old duplicate only after the user approves the destructive action;
- differing collisions: show a content diff and ask which version or merge to retain, one collision at a time.

Use the §24 maintenance window and verification for every approved structural batch. When the old tree is empty, remove it only with explicit approval, then run `rewrite`. If the split originated from a valid in-progress journal, run `finish`; otherwise confirm `new-only`, record `complete`, and proceed. Until then, all archive-backed workflows remain blocked.

## 2. Legacy project-doc task migration

Inspect the pre-2026-08 task marks before the versioned migration as directed by §0, or skip this section when those marks and any recorded `later` decisions are absent:

- `01 Now/Tasks.md` exists;
- `01 Now/Works in Progress.md` exists;
- a `03 Projects/*.md` root doc carries `**Status:**` but lacks `bucket:` frontmatter.

If none exists and the legacy component table has no `later` item, skip to Doctor. Otherwise retain the existing component-wise process. Ask **now / later / never** for each outstanding component and preserve answers in the legacy four-column table:

| # | Component | What it does |
|---|---|---|
| 1 | Whimsy sink | Create `04 Areas/Whimsy/_notes.md` if absent |
| 2 | Project-doc schema | Add `bucket:` plus `## Current Objective` and `## Next Actions`; remove `**Status:**` tokens |
| 3 | Tasks.md triage + kill | Propose a route for every item, execute unvetoed routes, then delete Tasks.md |
| 4 | WIP demotion + delete | Absorb unique state into project docs, then delete Works in Progress.md |
| 5 | Archive re-sort | Optionally move living docs from `06 Archive/` to their Area or Area archive |

Components 3 and 4 require 2. Component 5 is independent and defaults to `later`. Use `locked-edit.sh` for planning/hub writes, `write-tickler.sh` for Tickler writes, and `_shared-rules.md` §24 for every linked-file move. Draft project objectives/actions only from the document's own content. A finished-looking project requires the user's call rather than an invented objective.

Record rows exactly as before:

```markdown
| # | Component | now/later/never | YYYY-MM-DD |
```

Do not translate or merge these rows into the versioned table.

## 3. Doctor

Verify live state:

```bash
"{VAULT}/.claude/scripts/check-archive-layout.sh" --status "{VAULT}"
python3 "{VAULT}/.claude/scripts/archive-namespace-migration.py" verify "{VAULT}"
ls "{VAULT}/01 Now/Tasks.md" "{VAULT}/01 Now/Works in Progress.md" 2>/dev/null
for f in "{VAULT}/03 Projects/"*.md; do printf '%s: ' "$f"; rg -q '^bucket:' "$f" && rg -q '^## Current Objective' "$f" && rg -q '^## Next Actions' "$f" && echo OK || echo MISSING; done
```

Report the archive migration from the gate and verification output: `complete`, `blocked`, `deferred`, or `declined`. Report each legacy component as `live`, `broken`, `declined`, `deferred`, or `stale`. Completion evidence is authoritative only with a real `06 Archive/OpenCairn` directory; either explicit topology-mismatch state is a hard failure.

## Integration

**Reads:** archive layout, legacy locators, project/task surfaces, Migration Record.
**Writes:** migration journal/record, locked locator replacements, consented legacy task destinations.
**Deletes/moves:** only with explicit approval and link-aware structural mechanics.
**Called by:** `/update`; native Codex rendering is `$migrate`.

## Skill Monitor

Follow `_skill-monitor.md` from this commands directory and log any execution gap at the end.
