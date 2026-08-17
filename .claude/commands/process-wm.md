---
name: process-wm
description: Process Working Memory fresh captures — generate checkbox checklist, user reviews, then execute routes and deletes
---

# Process Working Memory

Process the user's Working Memory fresh captures zone. Route items to their permanent homes per the routing guide, delete stale items, and leave a clean capture surface.

## Philosophy

Working Memory (`01 Now/Working memory.md`) is a frictionless capture surface. Items land there without categorisation. Processing is a separate step — examining each item and routing it to the right permanent home.

**Key constraint:** The user captured these items in context that you don't have. Never summarise, editorialise, or strip context from captures. Preserve full original text so the user can make routing decisions without cross-referencing the source file.

## Instructions

### Step 0 — Resolve vault path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

### Step 1 — Load context

Read these files:
- `{VAULT}/01 Now/Working memory.md` — the file to process
- `{VAULT}/07 System/Working Memory Routing Guide.md` — routing table (SSOT for where items go)

**Destination resolution.** Stat every destination path the routing table names before proposing anything. Report unresolved rows to the user as a short list ("routing guide row X points at a path that doesn't exist") and treat those destinations as unavailable for this run — items that would route there go to "Needs your context". Never create a missing destination and never substitute a plausible-looking neighbour: a broken row is a routing-guide bug for the user to fix, not a path for you to invent.

### Step 2 — Identify the processing scope

The Fresh captures zone (between `## Fresh captures` and `## To process`) is the primary target. If the zone is empty, tell the user and stop.

**Item boundaries:** Items aren't consistently delimited, and whitespace alone doesn't decide it — consecutive lines separated by a single blank line are sometimes one continuous thought and sometimes three unrelated captures. Segment on **semantic continuity**: lines belong to the same item when the later ones only make sense as continuation of the earlier (same subject, a sentence completing the one above, a list under its own lead-in). Structural markers (`---` separators, headers) are hard boundaries where present, but their absence proves nothing. Where continuity is genuinely ambiguous, propose the more plausible split and flag the ambiguity in the item's note so the user can override the grouping in review.

**Foreign state:** the Fresh captures zone can also carry maintenance markers written by other skills (e.g. lines of the form `⚠ Hygiene W<n>: …`). These are not captures — they have their own lifecycle owned by the skill that wrote them. Never propose them for route or delete. Leave them untouched and mention them in the Step 6 report as a separate count.

The `## To process` backlog is a separate, larger task. Don't mix them unless the user explicitly asks.

**Run cap:** propose at most ~20 items per run, oldest-first. If the zone holds more, say so and process the oldest chunk — a checklist of a hundred fragments doesn't get reviewed, it gets abandoned.

### Step 3 — Generate checklist

Glob `{VAULT}/01 Now/WM Processing - *.md` first. Any prior checklist — today's or an earlier day's — is unfinished business: if it carries ticks or notes those are undelivered decisions, so offer to execute or archive it before generating a new one. A prior file with no ticks and no notes can be deleted. Resume today's file rather than overwriting it; extend it with any new items.

Create the checklist at `{VAULT}/01 Now/WM Processing - YYYY-MM-DD.md` (today's date via `date`).

Format:

```markdown
# WM Fresh Captures — Processing Checklist

*Every item below carries a proposed route. Your pass is veto/override, not generate: add a note to change a destination or veto a delete; leave an item alone to accept its proposal.*
*After review, tell Claude "go" and EVERY item executes its (possibly overridden) route — no item stays in Working memory. This file gets deleted after.*

---

## Proposed DELETE
- [ ] [full original text of item] — [brief reason for delete proposal]

## Proposed ROUTE

### → [Destination Category] (a routing-guide destination, e.g. Photography Scratchpad / Journal)
- [ ] [full original text of item] → [destination file]

### → [Another Destination Category]
- [ ] [full original text of item] → [destination file]

## Uncertain → Whimsy (default)
- [ ] [full original text of item] → 04 Areas/Whimsy/_notes.md (plain line) — [why routing is uncertain; note an override if this is wrong]
```

For multi-line captures, use a single checkbox with the full block indented below it:

```markdown
- [ ] **[the capture's own header/first line]** → [destination file]
  [second line of block]
  [rest of block verbatim, indented]
```

The bold line is the capture's own header or first line — never an invented summary title (rule 1 below applies to it too).

**Rules for the checklist:**

1. **Preserve full original text.** Never abbreviate, summarise, or paraphrase. The user must be able to make decisions from the checklist alone without opening Working memory.md.

2. **Don't be trigger-happy with DELETE.** "I don't see context" ≠ "no context exists." Only propose DELETE for items that are clearly stale (superseded by later events), obviously done, or are session artefacts (tool output, error messages).

3. **Group by destination**, not by source order. This makes batch review faster.

4. **Every item gets a proposed route.** Ambiguous items — unknown references, items that could go multiple ways, groupings you couldn't segment confidently (Step 2) — go in "Uncertain → Whimsy (default)" with the uncertainty stated, so the user can override. Never leave an item proposal-less.

5. **Use the routing guide** for destination mapping. Don't invent destinations.

6. **Bare fragments default to Whimsy.** A capture too short to carry its own meaning (a single word, an abbreviation, a stub with no verb) gets proposed → Whimsy `_notes.md` — don't manufacture a question for each one; the user overrides in review if a fragment deserves a real home.

### Step 4 — User reviews

Tell the user the checklist is ready at the path. Their pass is **veto/override, not generate**: they add notes to redirect a route or veto a delete; anything left alone is an accepted proposal.

Wait for user to say "go" or give feedback. Process feedback in batches — don't require item-by-item confirmation.

### Step 5 — Execute

After the user returns the checklist, **every item executes its (possibly overridden) route** — no item remains in Working memory.md after a completed run (over-cap items never entered the checklist and wait for the next run). For each item:

1. **DELETE items:** Remove from Working memory.md. Delete executes only where it was **proposed and not vetoed** — a user note can veto a delete (a vetoed delete with no alternative destination routes to Whimsy), but a note can never escalate a routed item into a delete-without-proposal; confirm first.
2. **ROUTE items:**
   - Read the destination file.
   - Append the item in a format consistent with the destination file's existing structure.
   - Remove from Working memory.md.
   - If the user's note requests a tickler, add a tickler entry via `write-tickler.sh` (per `_shared-rules.md` §5).
3. **ROUTE items whose destination is a section of Working memory.md itself** (the routing guide has such destinations, including its catch-all): this is a move within one file, not an append to another. Never append at EOF — the named `###` section is the target, not the end of the file. Use `locked-edit.sh --replace` against the target section header to insert the block beneath it, then a second `--replace` to remove the original occurrence, matching on enough surrounding text to disambiguate the two copies. Insert before removing, so an interruption leaves a duplicate (visible, recoverable) rather than a loss.
4. **Items without notes:** Execute the proposed route as shown. Silence accepts the proposal — unticked is not a veto and never means "leave in Working memory."
5. **Items with notes:** The note IS the decision — execute the action as modified (e.g. if the proposed route was "→ Project A" and the user names a different destination, route there instead). If the note doesn't specify an action (a question, "not sure"), ask — but the item still leaves WM this run once resolved; if it can't be resolved in-session, it routes to Whimsy.
6. **Uncertain items** (the "Uncertain → Whimsy" section) default to `04 Areas/Whimsy/_notes.md` as a plain line (no checkbox) unless the user's note supplies a destination.

**Progress markers:** execution is interruptible, so record each item's completion as you go. The moment an item's writes have landed, edit its checklist line to carry a done marker (`- [x] ✓done …`). A user's `- [x]` is *review markup*, not a record of execution — it can't do double duty. On resuming an interrupted run, skip every line already carrying the marker: without it, re-execution double-appends to destinations and the removals fail with spurious "no match".

**Removal matching:** when removing an item from Working memory.md, exact-match the original source text as it appears there — not the checklist rendering (which adds indentation and a bold first line). If the Edit tool refuses with "modified since read", follow `_shared-rules.md` §5 failure mode A (switch to `locked-edit.sh`); don't loop-retry.

**Write mechanism:** Destination files that are shared planning files or project/area hubs (`03 Projects/`, `04 Areas/` docs) get their appends via `locked-edit.sh`, not the Edit tool (`_shared-rules.md` §5). Working memory.md itself and the checklist may use the Edit tool.

### Step 6 — Clean up

- Delete the processing checklist file **after execution has run**. The item text is safe to lose (remaining items are still in WM), but the user's ticks and notes are decisions — if the session is ending and the user marked up the checklist but never said "go", ask before deleting (or leave the file in place); never silently discard unexecuted decisions. An untouched checklist (no ticks, no notes) can be deleted without asking.
- Report: how many items deleted, how many routed (and where, including the Whimsy-default count) — and, separately, how many over-cap items remain for the next run and how many foreign maintenance markers were left in place. A completed run leaves zero checklist items in Working memory.md.

## Routing Reference

SSOT is `{VAULT}/07 System/Working Memory Routing Guide.md` (loaded in Step 1). Don't duplicate the routing table here — read it from source each session.

## Anti-patterns

- **Don't editorialise.** "Trivial, you know this" is a judgement call about the user's intent. You don't have that context.
- **Don't create a persistent parallel doc.** The checklist is a session artefact (Step 6 handles deletion).
- **Don't process the backlog unprompted.** The `## To process` zone is large and separate. Only touch it if the user explicitly scopes it in.
- **Don't route without reading the destination file first.** Append in a format consistent with what's already there.
- **Don't batch-move items to an archive doc** as a substitute for actually processing them. That's shuffling, not processing.

## Cadence

- EOD — process fresh captures (the primary cadence per the WM file header and routing guide)
- Weekly, prompted by `/weekly-hygiene`'s Working Memory sweep flags (it flags oversized sections; it doesn't run this skill), or standalone. A flag on the `## To process` backlog still needs the user's explicit scope-in (Step 2)
- When fresh captures zone exceeds ~20 items
- Before deep work blocks (clear the mental decks)
