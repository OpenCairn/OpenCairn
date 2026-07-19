---
name: inbox-processor
description: Organise inbox captures into NIPARAS structure
---

# Inbox Processor - NIPARAS Categorisation

You are helping the user process their inbox. Your job is to categorise captured items and move them to the appropriate location in the NIPARAS structure.

## Philosophy

The inbox (`02 Inbox/`) is a frictionless capture point. Items land there without categorisation. Processing is a separate step - examining each item and routing it to the right permanent home.

This follows the GTD/PARA principle: **capture is fast and mindless, organisation is thoughtful and periodic**.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Scan the inbox:**
   - List every entry in `{VAULT}/02 Inbox/` — files **and** subdirectories — with filename, size, date, and type
   - Read markdown/text notes in full. For binaries (PDFs, images, audio, installers, archives), classify from filename + metadata; extract content only where cheap tooling exists (e.g. `pdftotext`). **Never execute a binary.**
   - Treat a subdirectory as a single bundle: list its top level, don't deep-recurse; it moves (or defers) as one unit

2. **Categorise each item:**

For each item, determine the appropriate home using NIPARAS logic:

**Ask these questions:**
- **Is this actionable now?** → extract the action into `01 Now/Working memory.md` or a specific project (a non-text item still gets a file home below — the action and the artefact route separately)
- **Is this a project?** (Has a specific end goal) → `03 Projects/[Project Name]/`
- **Is this an ongoing area of responsibility?** → `04 Areas/[Area]/`
- **Is this reference material?** → `05 Resources/[Topic]/`
- **Is this completed/inactive?** → `06 Archive/`
- **Is this system documentation?** → `07 System/`

**Additional routing rules:**
- Session notes → `06 Archive/Claude/Session Logs/`
- Daily reflections (user-authored) → `06 Archive/Daily Reviews/` (create if missing; deliberately distinct from `06 Archive/Claude/Daily Reports/`, which is /goodnight's machine-generated day index — never file user prose there)
- Blog drafts → the blog's own project or area folder (its drafts/content directory if it's a static site)
- Screenshots/images → Keep with related topic (never separate by filetype!)
- Meeting notes → Usually `04 Areas/` or linked project
- Article clippings → active project if project-specific; the owning Area's nested reference material if domain-owned; `05 Resources/[Topic]/` only when generic with no Area home
- Not every item must move: **leave deferred**, **delete** (junk/duplicates), or **ask the user** are valid plan outcomes — propose them explicitly in Step 3

3. **Present categorisation plan:**

Show the user the proposed categorisation:

```markdown
## Inbox Processing Plan

1. **[filename]**
   → `[destination path]`
   Rename: [proposed new filename, only if renaming — renames happen only when shown here and approved]
   Reason: [Why this destination is appropriate]

...

Proceed with this plan? (yes/no/modify)
```

4. **Execute moves** (after confirmation):
   - Move items to their new locations. For any item that may have inbound links or embeds (notes *and* attachments — `![[file.pdf]]` embeds break too), use a link-healing move (Obsidian's move) rather than raw `mv`. Verify "link-free" before a raw `mv`: a backlink/structural query, or grep the vault for the filename. Fresh captures usually have none. If link-healing moves may be needed, probe the Obsidian CLI first (`obsidian help`); if it's unavailable, raw-`mv` only verified link-free items and defer the rest.
   - Create necessary folders if they don't exist
   - Update relevant index files (project pages, hub files) for durable notes that need discoverability — not for raw attachments/receipts. Hub/planning-file edits go through `locked-edit.sh` per `_shared-rules.md` §5, not the Edit tool
   - Apply only the renames approved in the Step 3 plan
   - When adding an item to `01 Now/Working memory.md`, respect the file's existing structure — if it has a fresh-capture zone at the top, insert directly below that zone's heading, not at EOF (items appended below a backlog section are invisible to downstream Working Memory processing)

5. **Verify and confirm:**

Re-list `{VAULT}/02 Inbox/` before reporting — only claim "Inbox is now empty" if the listing confirms it; otherwise report the count of items deliberately left (deferred/uncertain).

```
✓ Processed 7 items from inbox
✓ Moved to Projects: 2
✓ Moved to Areas: 2
✓ Moved to Resources: 2
✓ Added to Working Memory: 1

Inbox is now empty.

Recommended: Review new items in their destinations to ensure they make sense in context.
```

## Categorisation Decision Tree

```
Item → Is it actionable RIGHT NOW?
       ├─ Yes → 01 Now/Working memory.md
       └─ No → Continue...

Item → Does it have a specific END GOAL?
       ├─ Yes → 03 Projects/[Project]/
       └─ No → Continue...

Item → Is it ongoing RESPONSIBILITY?
       ├─ Yes → 04 Areas/[Area]/
       └─ No → Continue...

Item → Is it REFERENCE for future use?
       ├─ Yes → 05 Resources/[Topic]/
       └─ No → Continue...

Item → Is it COMPLETED/INACTIVE?
       ├─ Yes → 06 Archive/
       └─ No → Continue...

Item → Is it SYSTEM documentation (how the vault/Claude works)?
       ├─ Yes → 07 System/
       └─ No → Uncertain, ask the user (or leave deferred)
```

## Guidelines

- **Never separate by filetype:** Images, PDFs, markdown files on same topic stay together
- **Create folders as needed:** If a new topic emerges, create appropriate structure
- **Rename for clarity:** Add dates, context, or more descriptive names when moving — always proposed in the Step 3 plan, never ad hoc
- **Link, don't duplicate:** If item relates to multiple places, keep in one location and link from others
- **Ask when uncertain:** If categorisation isn't obvious, present options and ask the user
- **Batch similar items:** If multiple items go to same destination, move them together
- **Update indexes:** If adding a durable note to a project or area, update the relevant hub file (skip for raw attachments/receipts — see Step 4)

## Special Cases

**Quick thoughts / stream of consciousness:**
- If actionable: Extract actions to Working Memory, archive the rest
- If insightful: Move to relevant context file or resource page
- If neither: Archive to `06 Archive/Quick Thoughts/`

**Article clippings:**
- Route per the Step 2 rule: project → Area's nested reference → `05 Resources/[Topic]/` as the generic fallback
- Consider: Does this relate to an active project? If yes, also link from project page

**Meeting notes:**
- If project-related: `03 Projects/[Project]/`
- If ongoing relationship/area: `04 Areas/[Area]/`
- If one-off: `06 Archive/Meetings/`

**Screenshots:**
- Keep with the thing they document (never in a generic "Screenshots" folder)
- If documenting a bug/issue: Keep with project until resolved, then archive

## Frequency

Run inbox processing:
- Weekly (Sunday/Monday) as part of weekly review
- When inbox gets >10-15 items
- Before starting deep work on a project (clear the decks)
- Whenever the user explicitly requests it

## Integration with Other Commands

- **After capture sessions:** When you've clipped many articles/notes, process them
- **Before /weekly-review:** Clean inbox so weekly review has clear boundaries
- **Complements /research-assistant:** Organised resources are easier to search

This creates a **clear separation between capture (fast) and organisation (thoughtful)**.
