---
name: morning
description: Adaptive morning check-in - surface landscape, catch gaps, open space for what's on your mind
---

# Morning - Adaptive Start-of-Day Check-in

You are facilitating the user's morning check-in. This is a fluid, adaptive routine that can be 2 minutes or 20 depending on what's needed.

## Philosophy

Morning mental loops come from different sources:
- **Unparked work** - things that didn't get captured yesterday (system gap)
- **Overnight processing** - brain worked on something, surfaced new insight/anxiety/connection
- **Life stuff** - relationship, health, existential, personal (outside "work")
- **Ambient anxiety** - known loops that brain keeps chewing on despite being captured

This routine handles all four without forcing you into one mode. Start operational, expand if needed.

## Instructions

### 0. Resolve Vault Path

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

### 1. Check current date/time

```bash
date +"%A, %d %b %Y"  # friendly display
date +"%Y-%m-%d"       # for file paths if needed
```

### 2. Surface the Landscape (auto, ~1 min)

Read and present:
- **Works in Progress:** Read `$VAULT_PATH/01 Now/Works in Progress.md`, show Active section
- **This Week.md freshness:** Check `$VAULT_PATH/01 Now/This Week.md` — if it exists, parse the date range from the heading (e.g. "# This Week — 28 Feb – 7 Mar 2026"). The range is a rolling 7-day window, not calendar weeks. If today's date falls within the range, it's current — note today's day section and any unchecked items in your working memory for step 6. If today falls outside the range, it's stale — note any unchecked items in your working memory for carry-forward in step 6. If the file doesn't exist, skip.
- **Tickler items due:** Read `$VAULT_PATH/01 Now/Tickler.md` (skip if file doesn't exist), show items where date header <= today (YYYY-MM-DD format). Separate into two groups: **Today** (date == today) shown in full, and **Overdue** (date < today) shown as a compact summary — just the item names with overdue flag, not full descriptions. If overdue count is large (>5), group by theme or just show count + the most time-sensitive ones. Don't let overdue backlog bury today's items.
- **Tickler→This Week migration:** If `$VAULT_PATH/01 Now/This Week.md` exists, parse its date range from the heading (e.g. "28 Feb – 7 Mar 2026"). Check Tickler for unchecked items with date headers falling within that range that aren't already represented in This Week.md. If any found, flag them:
  ```
  **Tickler items for this week not yet in This Week.md:**
  - [Item] (tickler date: YYYY-MM-DD)
  ```
  In step 4 (Capture Gate), offer to add them to the appropriate day in This Week.md. Per SSOT rules: once an item moves to This Week.md, delete it from Tickler — This Week becomes the canonical location.
- **Yesterday's open loops:** Check `$VAULT_PATH/06 Archive/Claude Sessions/` for most recent session file, extract open loops
- **Tomorrow's Queue from last night:** Check `$VAULT_PATH/06 Archive/Daily Reports/` for yesterday's report, extract "Tomorrow's Queue" section if exists (this is what you set at bedtime via /goodnight)
- **Time-sensitive items:** Scan WIP and recent sessions for deadlines, urgencies

Present concisely:
```
Good morning. Here's your landscape:

**Active projects:**
- [Project] - [status/next action]
- [Project] - [status/next action]

**Tickler items due:**
- [ ] [Item] → [[context link]]
- [ ] [Another item] (⚠️ overdue) → [[context link]]

**Open loops from yesterday:**
- [ ] Item 1
- [ ] Item 2

**Last night's queue:** (from /goodnight)
- [Item you queued at bedtime]
- [Another item]

**Time-sensitive:**
- [Item] - [deadline]
```

If a section is empty, skip it. Keep it scannable.

### 3. Catch Gaps + Open Space (single prompt)

Ask both questions together — don't force two round trips:
> "Anything from yesterday that didn't get captured? And what's on your mind this morning?"

**If "nothing" or minimal:** Move to step 5, keep it quick.

**If stuff comes up:** Let it flow. Don't rush. This is generative space. Let the user dump everything before you respond. The user will often also respond to the landscape from step 2 in the same message (marking items done, rescheduling, adding context). Treat all of this as input to step 4.

### 4. Capture Gate (MANDATORY — do not skip or defer)

**After** the user finishes their response (whether it's brain dump items, landscape corrections, scheduling decisions, or all three), and **before** moving to step 5:

**Capture means writing to a file, not acknowledging in conversation.** If it's not in a file, it's not captured. Discussing an item, triaging it, or giving an opinion about it is not capturing it.

For every item the user mentioned:

1. **Triage each item into one of these categories:**
   - **Status update** (e.g. "Tentrem done", "train booked") → Mark done in Tickler/WIP/project file. Trace references — a status change may touch multiple files.
   - **Reschedule** (e.g. "do this on the 26th", "next week") → Move to appropriate Tickler date or update project file
   - **Actionable task** → Write to the appropriate file (Tickler for date-specific, project file for project-scoped, WIP for new workstreams)
   - **Decision (resolved)** → Write the decision + rationale to the relevant project file or WIP
   - **Decision (open)** → Write to relevant project's "Open Decisions" section or WIP
   - **Research/idea** → Write to the relevant project or area file
   - **Just venting** → Don't write. But this category should be rare — most things people say in the morning are at least "note-worthy"

2. **Write immediately.** Do the file edits NOW, in this step, before asking any more questions. Do not batch them for step 7. Do not hold them in conversational memory.

3. **Confirm with a receipt.** After writing, show the user a summary:
   ```
   Captured:
   - [item] → [file path or section]
   - [item] → [file path or section]
   - [item] → acknowledged (no file needed)
   ```
   The user should be able to glance at this and verify nothing was dropped.

**Silence is agreement, not dismissal.** When the user responds to a landscape summary or brain dump triage, they will often only comment on items they want to change or clarify. Items they don't mention are agreed-as-presented — they still need to be captured/actioned. Do NOT interpret "user didn't comment on this item" as "user doesn't care about this item" or "this item can be dropped." The default for an uncontested item is: proceed as proposed.

**Why this gate exists:** The failure mode is: user dumps 10 items, Claude discusses all 10 intelligently, user assumes they're captured, they're not. Conversation is volatile memory. Files are the system of record. The gap between "discussed" and "captured" is where trust erodes.

### 5. Set Intention (optional closer)

Ask:
> "What's your one thing for today? Or skip if you'd rather stay open."

- If they have one: note it, offer to add to WIP or just hold it
- If skip: that's fine, some days are exploratory

### 6. Update This Week.md (optional)

If the day has enough structure to benefit from a visual plan (appointments, time blocks, multiple tasks), offer:

> "Want me to update today's section in This Week.md?"

**If yes:**

If This Week.md doesn't exist or is stale (today outside the date range), offer to create a fresh one first (see "Creation" below).

Find today's day section by matching `## [Day] [DD] [Mon]` headings. Replace/expand it with the full visual timeline format — the same at-a-glance layout formerly used in the daily plan:

````
## [Day] [DD] [Mon]

```
┄┄ morning (HH:MM–HH:MM) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
HH:MM   ██ Scheduled block (duration)
        ┊ Sub-item detail
~HH:MM  ░░ Open/flexible time
        ┊ Option 1
        ┊ Option 2
┄┄ afternoon (HH:MM–HH:MM) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄
HH:MM   ████████ Longer scheduled block
~HH:MM  ░░ Admin batch
        ┊ Task 1
        ┊ Task 2
┄┄ evening (HH:MM–HH:MM) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
HH:MM   ░░ Wind down
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
```

### Done today
- [x] Completed item — detail
- [x] Another completed item
````

**Timeline format reference:**
- `██` = scheduled block with duration: `09:00 ██ Dentist (1h)`
- `████████` = longer blocks use more block chars, roughly proportional
- `░░` = open/flexible time: `░░ open — 90 min`
- `▓▓` = tentative/pending: `?? ▓▓ Dinner with Sam (pending)`
- `┊` = sub-items within a block
- `┄┄` = section dividers (morning/afternoon/evening)
- `[x]` prefix = completed items in the timeline (standard Obsidian checkbox)
- `~` prefix = approximate time

Pull items from:
- Items carried forward from stale This Week.md (if any, noted in step 2)
- Time-sensitive items and appointments
- WIP next actions
- Yesterday's queue (from /goodnight Daily Report)
- Tickler items due today
- The "one thing" from step 5
- Anything the user mentioned in step 3

Completed items get `[x]` in the timeline (standard Obsidian checkbox: `- [x] Task`). Detailed completion notes go in the "Done today" subsection under today's day heading.

**Future days** in the same file stay simple — just task lists under the `## ` heading, no timeline code block. They get expanded with the full timeline format when that day becomes "today" via /morning.

**Refs** section at bottom of the file — `[[wikilinks]]` linking timeline items to project/area files.

**Creation:** If This Week.md is stale or missing:
> "This Week.md is [stale/missing]. Want me to create one for this week?"

If yes — and if replacing a stale file, first show unchecked items from the old This Week.md and ask which to carry forward into the new week. Then create `$VAULT_PATH/01 Now/This Week.md` — rolling 7-day window. Today gets the full timeline (including carried-forward items); future days get simple task lists:

````
# This Week — [DD] [Mon] – [DD] [Mon] [YYYY]

## [Today] [DD] [Mon]
[Full timeline code block as above]

## [Day+1] [DD] [Mon]
- Task 1
- Task 2

## [Day+2] [DD] [Mon]
- Task 1

[... 7 days total]

## Refs
- [[wikilinks to relevant project/area files]]
````

Rolling 7 days from today — each /morning recalculates.

**If no or the day is unstructured:** Skip. Not every day needs a timeline.

### 7. Output (conditional)

**Note:** By this point, all brain dump items from step 3 should ALREADY be written to files (step 4). This step is only for This Week.md and any additional generative content — not for deferred captures.

**Most days with This Week.md:** The updated This Week.md is the artifact. No additional output needed.

**If generative/insight content** (beyond what was captured in step 4):
- Append to today's journal at `$VAULT_PATH/05 Resources/Journal/YYYY-MM-DD.md`
- Or create morning note at `$VAULT_PATH/06 Archive/Morning Notes/YYYY-MM-DD.md` (create directory if needed)

**If nothing:** Just close cleanly.

### 8. Close

Short and light:
```
✓ Landscape reviewed
✓ [X items captured / Nothing new]
✓ This Week.md updated (or "Open day — no plan needed")
✓ Focus: [One thing] (or "Open day")

Have a good one.
```

Or even shorter if it was a quick check-in:
```
You're clear. Go.
```

## Guidelines

- **Adaptive duration:** Can be 2 minutes or 20. Follow the energy, don't force.
- **This Week.md is the artifact when needed:** For structured days, update today's section in This Week.md. For open/exploratory days, the conversation itself is the routine — no file update needed.
- **Light touch:** This isn't therapy or heavy journaling. Quick check-in that can expand if needed.
- **No guilt:** If the user skips steps or says "I'm good," respect that. The routine serves him, not vice versa.
- **Capture means file writes:** If something comes up, write it to the right place (WIP, project, journal, Tickler) immediately. Don't just discuss routing — do the routing. Don't create new systems or files when an existing one fits.
- **Morning pages complement:** This is operational/triage. Morning pages (journal) is generative/exploratory. They can happen same morning - this first (quick), then journal (if desired).

## Triggers

This command should trigger when the user says:
- "morning"
- "good morning"
- "start the day"
- "what's on deck"
- "what do I have today"

## Integration

- **Reads from:** Works in Progress, This Week.md (date-range freshness + tickler migration), Tickler, recent Claude Sessions, Daily Reports
- **May create/update:** This Week.md (weekly plan with day sections)
- **May update:** Works in Progress, Tickler (mark items done or reschedule), Journal, Project files
- **Complements:** `/park` (end of session), `/goodnight` (end of day), `/afternoon` (mid-day)
- **Doesn't replace:** Morning pages / journaling (that's separate generative practice)
