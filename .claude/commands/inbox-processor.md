---
name: inbox-processor
aliases: [process-inbox, organise, categorise]
description: Organise inbox captures into NIPARAS structure
---

# Inbox Processor - NIPARAS Categorisation

You are helping the user process his inbox. Your job is to categorise captured items and move them to the appropriate location in the NIPARAS structure.

## Philosophy

The inbox (`02 Inbox/`) is a frictionless capture point. Items land there without categorisation. Processing is a separate step - examining each item and routing it to the right permanent home.

This follows the GTD/PARA principle: **capture is fast and mindless, organisation is thoughtful and periodic**.

## Instructions

0. **Resolve Vault Path**

   ```bash
   if [[ -z "${VAULT_PATH:-}" ]]; then
     echo "VAULT_PATH not set"; exit 1
   elif [[ ! -d "$VAULT_PATH" ]]; then
     echo "VAULT_PATH=$VAULT_PATH not found"; exit 1
   else
     echo "VAULT_PATH=$VAULT_PATH OK"
   fi
   ```

   If ERROR, abort - no vault accessible. (Do NOT silently fall back to `~/Files` without an active failover symlink - that copy may be stale.) **Use the resolved path for all file operations below.** Wherever this document references `$VAULT_PATH/`, substitute the resolved vault path.

1. **Scan the inbox:**
   - Read all files in `$VAULT_PATH/02 Inbox/`
   - List items with brief description (filename, size, date)

2. **Categorise each item:**

For each item, determine the appropriate home using NIPARAS logic:

**Ask these questions:**
- **Is this actionable now?** → `01 Now/Working memory.md` or a specific project
- **Is this a project?** (Has a specific end goal) → `03 Projects/[Project Name]/`
- **Is this an ongoing area of responsibility?** → `04 Areas/[Area]/`
- **Is this reference material?** → `05 Resources/[Topic]/`
- **Is this completed/inactive?** → `06 Archive/`
- **Is this system documentation?** → `07 System/`

**Additional routing rules:**
- Session notes → `06 Archive/Claude Sessions/`
- Daily reflections → `06 Archive/Daily Reviews/`
- Blog drafts → `03 Projects/Blog-Sites/blog/content/posts/`
- Screenshots/images → Keep with related topic (never separate by filetype!)
- Meeting notes → Usually `04 Areas/` or linked project
- Article clippings → `05 Resources/[Topic]/` or relevant project

3. **Present categorisation plan:**

Show the user the proposed categorisation:

```markdown
## Inbox Processing Plan

1. **[filename]**
   → `[destination path]`
   Reason: [Why this destination is appropriate]

...

Proceed with this plan? (yes/no/modify)
```

4. **Execute moves** (after confirmation):
   - Move files to their new locations
   - Create necessary folders if they don't exist
   - Update any relevant index files (project pages, hub files, etc.)
   - Rename files for clarity if needed (add dates, context)

5. **Verify and confirm:**

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
       └─ No → Uncertain, ask the user
```

## Guidelines

- **Never separate by filetype:** Images, PDFs, markdown files on same topic stay together
- **Create folders as needed:** If a new topic emerges, create appropriate structure
- **Rename for clarity:** Add dates, context, or more descriptive names when moving
- **Link, don't duplicate:** If item relates to multiple places, keep in one location and link from others
- **Ask when uncertain:** If categorisation isn't obvious, present options and ask the user
- **Batch similar items:** If multiple items go to same destination, move them together
- **Update indexes:** If adding to a project or area, update the relevant hub file

## Special Cases

**Quick thoughts / stream of consciousness:**
- If actionable: Extract actions to Working Memory, archive the rest
- If insightful: Move to relevant context file or resource page
- If neither: Archive to `06 Archive/Quick Thoughts/`

**Article clippings:**
- Always to `05 Resources/[Topic]/`
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
