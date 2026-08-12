---
name: migrate
description: One-shot migration of an existing OpenCairn vault to the project-doc task system (post-2026-08 format)
---

# Migrate - Old-Format Vault to the Project-Doc Task System

You are migrating an existing OpenCairn vault from the pre-2026-08 task format (Tasks.md catch-all + Works in Progress dashboard + Status fields) to the current one (project docs as SSOT, folder-location-as-status, rendered Strategic Overview, Whimsy sink). This runs **once per vault**; `/update` refuses old-format vaults and redirects here. A new vault created by `/setup` never needs it.

**Old format** (any of these marks a vault as old-format): `01 Now/Tasks.md` exists · `01 Now/Works in Progress.md` exists · `03 Projects/` root docs carry `**Status:**` lines and lack `bucket:` frontmatter.

**Target format:** each `03 Projects/` root doc = `bucket:` YAML frontmatter + `## Current Objective` + `## Next Actions`; root = active, `Cold/` = paused, `Backlog/` = unstarted — folder is the status; `/morning` renders `01 Now/Strategic Overview.md` (read-only view); undated low-priority items live in `04 Areas/Whimsy/_notes.md` (plain lines, no checkboxes); dated items in This Week / Tickler. See `07 System/Vault Organisation Principles.md` → Project Doc Format.

## Instructions

### 0. Resolve Vault Path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `_shared-rules.md` from this skill's own commands directory and apply it throughout — §5 (locked writes) governs every planning-file edit below. `{VAULT}` = the resolved path.

### 1. Detect and inventory

Check the three old-format marks above and count the work: root-doc count, Tasks.md line/checkbox count, WIP entry count.

If none of the marks are present AND no `{VAULT}/07 System/Migration Record.md` exists, the vault is current-format — stop. If a Migration Record exists with `later`/deferred components, skip the inventory and jump to Step 2 for the outstanding components only (then Doctor).

### 2. Per-component consent

The migration is component-wise, and each component is asked **now / later / never** — record the answers in a `{VAULT}/07 System/Migration Record.md` (create it). "Later" components re-offer on the next `/migrate` run; "never" is recorded and not re-asked (the vault then intentionally diverges — `/update` accepts it once the record says so).

**Record format — one table row per component, machine-greppable** (`/update` greps this file for `never` against the file-mark components):

```
| # | Component | now/later/never | YYYY-MM-DD |
```

| # | Component | What it does |
|---|-----------|--------------|
| 1 | Whimsy sink | Create `04 Areas/Whimsy/_notes.md` if absent (plain-line dump; no checkboxes, no scanner) |
| 2 | Project-doc schema | Retrofit every `03 Projects/` root doc: `bucket:` frontmatter (offer the taxonomy from Vault Organisation Principles → Project Doc Format; the user personalises), draft `## Current Objective` + `## Next Actions` FROM the doc's own content for approval, strip `**Status:**` tokens (keep informative remainders under a different label). User approves bucket + active/Cold/Backlog per doc, batched |
| 3 | Tasks.md triage + kill | Propose a route for EVERY item (project doc / Tickler date / Whimsy / delete + reason) — veto-of-proposed-routes: the user vetoes, nothing is left unproposed. Execute the approved routes, then delete Tasks.md |
| 4 | WIP demotion + delete | Absorb any WIP entry state not already in its project doc (Last/Next fields → the doc's Current Objective / Next Actions), then delete `01 Now/Works in Progress.md` |
| 5 | Archive re-sort | Optional, deferrable: move living docs out of `06 Archive/` to their Area (or Area `Archive/`) per the routing taxonomy — `06 Archive/` keeps only immutable dated records |

Sequencing constraint: 3 and 4 require 2 (routes need schema'd destinations). 1 is independent and takes seconds. 5 is fully independent — offer "later" as the default.

### 3. Execute consented components

In the order above. Mechanics:

- All planning/hub edits via `locked-edit.sh` (§5), Tickler writes via `write-tickler.sh`, file moves via the `obsidian` CLI (link healing — §24), never raw `mv`.
- Component 2's drafting rule: Current Objective / Next Actions are drafted **from the doc's own content**, never invented; a doc that reads as finished is flagged for the user's call (Cold, complete, or delete) rather than retrofitted.
- Component 2's taxonomy fallback: if the vault's `07 System/Vault Organisation Principles.md` lacks a Project Doc Format section, first append the template's version of that section to it (default taxonomy: craft / constitution / community / contemplation / calm — the user personalises), then offer the taxonomy from there. `/update` never touches vault content, so a template user's vault will not have this section already.
- Component 3's routing heuristics: next-30-45-day items → project doc or dated Tickler; obviously dead → delete with one-line reason; everything else → Whimsy. Whole sections may route wholesale.
- Component 5's execution: move living docs out of `06 Archive/` with the `obsidian` CLI per the routing taxonomy — propose the full move list for the user's review first, never bulk-move unreviewed.
- Existence-check every destination before appending — `locked-edit.sh` silently creates missing targets, so a typo'd path mints a stray file.

### 3b. Re-render the Strategic Overview

Run this if components 2, 3 or 4 ran — each writes `03 Projects/` root docs, which are the render's source set. Components 1 and 5 alone leave the root untouched; skip and say so.

Render `{VAULT}/01 Now/Strategic Overview.md` **following the Strategic Overview render step in `morning.md`** — read it and apply it; do not reimplement it here, or the two specs drift. In a migrated vault this is usually a creation rather than a refresh: component 4 deletes `01 Now/Works in Progress.md`, the old format's dashboard, and nothing stands in for it until the user's first `/morning`. That gap is what makes a fresh migration feel like it lost something.

**Check (run it here — Step 4 cannot do it for you):** list the root and compare it against what the render emitted.

```bash
ls "{VAULT}/03 Projects/"*.md | sed 's|.*/||; s|\.md$||' | sort
grep -o '\[\[03 Projects/[^]]*\]\]' "{VAULT}/01 Now/Strategic Overview.md" | sed 's|\[\[03 Projects/||; s|\]\]||' | sort
```

The two lists must be identical; report the comparison as its own line, not folded into a component's status. Step 4's schema loop looks like it covers this and does not — it enumerates root docs and their `bucket:`/heading status but never opens the rendered file, so it returns the same output whether the render ran, ran wrong, or never ran at all. A doc the render had to fail closed on is a separate finding: it is a component-2 retrofit that did not land, and the schema loop's `MISSING` is what evidences it. Write tool, full overwrite (`locked-edit.sh` does not apply — §5 governs shared planning files; this one is regenerated, not authored).

### 4. Doctor - verify actual state, then report

Check each component's **live state**, not this run's memory of what it did:

```bash
# marks gone?
ls "{VAULT}/01 Now/Tasks.md" "{VAULT}/01 Now/Works in Progress.md" 2>/dev/null
# schema present?  (per root doc: bucket + both headings)
for f in "{VAULT}/03 Projects/"*.md; do printf '%s: ' "$f"; grep -q '^bucket:' "$f" && grep -q '^## Current Objective' "$f" && grep -q '^## Next Actions' "$f" && echo OK || echo MISSING; done
# sink present?
ls "{VAULT}/04 Areas/Whimsy/_notes.md"
# archive re-sort spot-check: living docs still in 06 Archive/ (excluding the Migration Record)
find "{VAULT}/06 Archive" -name '*.md' | wc -l
```

The archive count is a **spot-check, not a proof** — `06 Archive/` legitimately holds immutable dated records, so a non-zero count is expected. Compare it against the component-5 move list: a count unchanged since before the run means the moves didn't land.

Report one line per component: **live** (verified working) / **broken** (attempted but the check fails — say what's wrong) / **declined** (user said never) / **deferred** (user said later) / **stale** (consented on a previous run but the check no longer passes). Never assume this run's own success — the check is the claim. Append the Doctor table to `07 System/Migration Record.md` with the date.

## Guidelines

- **One vault, one migration, many sittings is fine** — the Migration Record + "later" answers make re-runs cheap and idempotent.
- **The user gates judgement; the skill executes mechanics.** Bucket choices, route vetoes, and finished-doc calls are the user's; drafting, counting, moving, and verifying are yours.
- **Don't migrate content into invented structure** — a vault without Areas that the taxonomy expects gets the question, not a guess.

## Integration

**Reads:** `03 Projects/`, `01 Now/Tasks.md`, `01 Now/Works in Progress.md`, Vault Organisation Principles.
**Writes:** project docs, Tickler, This Week, Whimsy, `01 Now/Strategic Overview.md` (rendered), `07 System/Migration Record.md`; deletes Tasks.md and WIP on consent.
**Called by:** `/update` (redirects here on old-format detection).
