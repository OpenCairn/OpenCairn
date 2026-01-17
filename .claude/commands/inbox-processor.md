---
name: inbox-processor
aliases: [process-inbox, organise]
description: Organise inbox captures into NIPARAS structure
---

# Inbox Processor - NIPARAS Categorisation

You are helping process the inbox. Categorise captured items and move them to the appropriate location in the NIPARAS structure.

## Philosophy

The inbox (`02 Inbox/`) is a frictionless capture point. Items land there without categorisation. Processing is separate - examining each item and routing it to the right permanent home.

**Capture is fast and mindless, organisation is thoughtful and periodic.**

## Instructions

1. **Scan the inbox:**
   - Read all files in `02 Inbox/`
   - List items with brief description

2. **Categorise each item:**

**Ask these questions:**
- **Is this actionable now?** → `01 Now/Working memory.md` or a specific project
- **Is this a project?** (Has specific end goal) → `03 Projects/`
- **Is this ongoing responsibility?** → `04 Areas/`
- **Is this reference material?** → `05 Resources/`
- **Is this completed/inactive?** → `06 Archive/`
- **Is this system documentation?** → `07 System/`

3. **Present categorisation plan:**

```markdown
## Inbox Processing Plan

1. **travel-insurance-quote.pdf**
   → `05 Resources/Travel/travel-insurance-quote.pdf`
   Reason: Reference material for travel project

2. **meeting-notes.md**
   → `03 Projects/Project Name/meeting-notes-2026-01-16.md`
   Reason: Related to active project

Proceed with this plan? (yes/no/modify)
```

4. **Execute moves** (after confirmation):
   - Move files to new locations
   - Create folders if needed
   - Update relevant index files
   - Rename files for clarity if needed

5. **Verify and confirm:**

```
✓ Processed 7 items from inbox
✓ Moved to Projects: 2
✓ Moved to Areas: 2
✓ Moved to Resources: 2
✓ Added to Working Memory: 1

Inbox is now empty.
```

## Decision Tree

```
Item → Is it actionable RIGHT NOW?
       ├─ Yes → 01 Now/Working memory.md
       └─ No → Continue...

Item → Does it have a specific END GOAL?
       ├─ Yes → 03 Projects/
       └─ No → Continue...

Item → Is it ongoing RESPONSIBILITY?
       ├─ Yes → 04 Areas/
       └─ No → Continue...

Item → Is it REFERENCE for future use?
       ├─ Yes → 05 Resources/
       └─ No → 06 Archive/
```

## Guidelines

- **Never separate by filetype:** Images, PDFs, markdown on same topic stay together
- **Create folders as needed:** If new topic emerges, create appropriate structure
- **Rename for clarity:** Add dates, context when moving
- **Link, don't duplicate:** Keep in one location, link from others
- **Ask when uncertain:** Present options if categorisation isn't obvious

## Frequency

Run inbox processing:
- Weekly as part of weekly synthesis
- When inbox gets >10-15 items
- Before starting deep work (clear the decks)

## Integration

- **Before /weekly-synthesis:** Clean inbox for clear weekly boundaries
- **Complements /research-assistant:** Organised resources are easier to search
