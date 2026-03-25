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
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `.claude/commands/_shared-rules.md` and apply its rules throughout this command. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

### 1. Check current date/time

```bash
date +"%A, %d %b %Y — %H:%M %Z"  # friendly display with time and timezone
date +"%Y-%m-%d"                   # for file paths if needed
```

### 2. Reconcile post-goodnight sessions

Check if any sessions were logged after last night's /goodnight close-out. If so, patch the daily report so it reflects the full day.

1. Compute yesterday's date: `date -d "yesterday" +"%Y-%m-%d"`
2. Check if yesterday's daily report exists: `{VAULT}/06 Archive/Claude/Daily Reports/YYYY-MM-DD.md`
3. If no daily report → skip (no /goodnight was run). Proceed to Step 3.
4. Read yesterday's session log: `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`
5. Find the goodnight session — match pattern `^## Session [0-9]+ - Goodnight:` (colon required to distinguish from sessions that happen to mention "goodnight" in their topic).
6. If daily report exists but no goodnight session found in the session log → skip (daily report wasn't created by /goodnight). Proceed to Step 3.
7. Extract the goodnight session number. Check if any sessions exist with a higher number.
8. If no post-goodnight sessions → skip silently. Proceed to Step 3.
9. If post-goodnight sessions found:
   - Read each post-goodnight session block.
   - **Append** the late session(s) to the `## Sessions` list in the daily report.
   - **Append** any completions to `## Completed`.
   - Do NOT modify other sections — the daily report's Tomorrow's Queue, Blockers, and Notes were set deliberately at close-out and remain valid.
   - Add a note at the end of the Sessions section: `*Sessions N–M added by /morning (ran after close-out)*`
   - Display:
     ```
     ✓ Reconciled: [N] post-goodnight session(s) added to yesterday's daily report
       - Session M: [Topic] - [outcome]
     ```

### 3. Surface the Landscape (auto, ~1 min)

Read and present:
- **Works in Progress:** Read `{VAULT}/01 Now/Works in Progress.md`, show Active section
- **This Week.md freshness:** Check `{VAULT}/01 Now/This Week.md` — if it exists, parse the date range from the heading (e.g. "# This Week — 28 Feb – 7 Mar 2026"). The range is a rolling window (up to 10 day sections: 3 past + today + 6 future), not calendar weeks. If today's date falls within the range, it's current — note today's day section and any unchecked items in your working memory for step 7. If today falls outside the range, it's stale — note any unchecked items in your working memory for carry-forward in step 7. If the file doesn't exist, skip.
- **Tickler items due:** Read `{VAULT}/01 Now/Tickler.md` (skip if file doesn't exist), show items where date header <= today (YYYY-MM-DD format). Separate into two groups: **Today** (date == today) shown in full, and **Overdue** (date < today) shown as a compact summary — just the item names with overdue flag, not full descriptions. If overdue count is large (>5), group by theme or just show count + the most time-sensitive ones. Don't let overdue backlog bury today's items.
- **Tickler→This Week migration (automatic):** If `{VAULT}/01 Now/This Week.md` exists, check Tickler for unchecked items with date headers falling within the This Week.md date range that aren't already represented in This Week.md. **Migrate them automatically** — add each item to the appropriate day section in This Week.md and delete from Tickler (This Week becomes SSOT per Tickler transfer rules). Also delete any completed (`[x]`) items from those same Tickler date sections as cleanup. When migrating, preserve existing project/area links (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`). If an item has only a session log link (`→ [[06 Archive/...]]`), replace it with the relevant project/area link. If no link, add one per the item linking convention (see Step 7).
- **Coming up this week:** After migration, scan This Week.md for all unchecked items on **future days** (day sections after today). Show them in the landscape output grouped by day. This gives visibility into the week ahead regardless of whether items were just migrated or were already there. This prevents the misleading "Nothing due today" pattern where upcoming items are invisible.
- **Yesterday's sessions (context only):** Check `{VAULT}/06 Archive/Claude/Session Logs/` for most recent session file — note topics and summaries for context, but do NOT extract open loops from session files. Open items come from This Week.md and Tickler only (session loops were routed to SSOT at park time)
- **Tomorrow's Queue from last night:** Check `{VAULT}/06 Archive/Claude/Daily Reports/` for yesterday's report, extract "Tomorrow's Queue" section if exists (this is what you set at bedtime via /goodnight)
- **Time-sensitive items:** Scan WIP and recent sessions for deadlines, urgencies
- **Review staleness:** Check when the last weekly review and quarterly review were run:
  ```bash
  ls -1t "{VAULT}/06 Archive/Claude/Weekly Reviews/"*.md 2>/dev/null | head -1
  ls -1t "{VAULT}/06 Archive/Quarterly Reviews/"*.md 2>/dev/null | head -1
  ```
  Weekly review files are `YYYY-Wnn.md` (ISO week number). Quarterly files are `YYYY-QN.md`. Convert the most recent filename of each type to a date and calculate days elapsed. Flag if weekly review is >10 days old or quarterly review is >100 days old. Show each overdue review individually — don't mention reviews that are current. If a review directory is empty or missing, skip that review type entirely (don't flag a cadence the user hasn't started).

Present concisely:
```
Good morning. **[HH:MM TZ] — [Day], [DD] [Mon] [YYYY]**

Here's your landscape:

**Active projects:**
- [Project] - [status/next action]
- [Project] - [status/next action]

**Tickler items due:**
- [ ] [Item] → [[context link]]
- [ ] [Another item] (⚠️ overdue) → [[context link]]

**Coming up this week:** (from This Week.md future days)
- [Day] [DD]: [Item], [Item]
- [Day] [DD]: [Item]

**From yesterday's sessions (context only):**
- [Topic 1] - [brief summary]
- [Topic 2] - [brief summary]

**Last night's queue:** (from /goodnight)
- [Item you queued at bedtime]
- [Another item]

**Time-sensitive:**
- [Item] - [deadline]

**⚠️ Weekly review overdue** — last run [date] ([N] days ago)
**⚠️ Quarterly review overdue** — last run [date] ([N] days ago)
```

If a section is empty, skip it. Keep it scannable.

### 4. Catch Gaps + Open Space (single prompt)

Ask both questions together — don't force two round trips:
> "Anything from yesterday that didn't get captured? And what's on your mind this morning?"

**If "nothing" or minimal:** Move to step 6, keep it quick.

**If stuff comes up:** Let it flow. Don't rush. This is generative space. Let the user dump everything before you respond. The user will often also respond to the landscape from step 3 in the same message (marking items done, rescheduling, adding context). Treat all of this as input to step 5.

### 5. Capture Gate (MANDATORY — do not skip or defer)

**After** the user finishes their response (whether it's brain dump items, landscape corrections, scheduling decisions, or all three), and **before** moving to step 6:

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

2. **Write immediately.** Do the file edits NOW, in this step, before asking any more questions. Do not batch them for step 6. Do not hold them in conversational memory.

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

### 6. Maintain This Week.md window

This step runs every morning regardless of whether the user wants a timeline for today. It keeps the rolling window current.

If This Week.md doesn't exist, skip this step (step 7 will offer to create it if needed).

Run the This Week.md Rolling Window Maintenance procedure (see `_shared-rules.md` Section 9). This trims old sections, extends the window to today+6, and populates new days from Tickler.

**Additional morning-specific behaviour:** Step 3 (landscape surfacing) handles Tickler migration for *existing* day sections. The rolling window procedure here only covers *newly created* day sections. Apply the same link handling as Step 3: preserve project/area links, replace session-log-only links, add links to bare items per the item linking convention (see `_shared-rules.md` Section 3).

### 7. Update today's timeline (optional)

If the day has enough structure to benefit from a visual plan (appointments, time blocks, multiple tasks), offer:

> "Want me to update today's section in This Week.md?"

**If yes:**

If This Week.md doesn't exist or is stale (today outside the date range), offer to create a fresh one first (see "Creation" below).

Find today's day section by matching `## [Day] [DD] [Mon]` headings. Replace/expand it with the timeline format — native markdown so Obsidian checkboxes work:

````
## [Day] [DD] [Mon]

### Morning (HH:MM–HH:MM)
- [ ] **HH:MM Scheduled block (1h30m)**
  - [ ] Sub-item detail
- [ ] HH:MM Quick task (20m)
- Flexible time
  - [ ] Option 1
  - [ ] Option 2

### Afternoon (HH:MM–HH:MM)
- [ ] **HH:MM–HH:MM Longer scheduled block (3h)**
  - [ ] Task within it
- Admin batch
  - [ ] Task 1
  - [ ] Task 2

### Evening (HH:MM–)
- [ ] **HH:MM Evening event (2h)**

### Done today
- [x] Completed item — detail
- [x] Another completed item
````

**Timeline format reference:**
- **Bold entire line** = scheduled item longer than 1 hour: `- [ ] **14:00–17:00 Workshop (3h)**`
- Normal weight = items 1 hour or under: `- [ ] 09:30 Quick call (15m)`
- Duration in parentheses after every scheduled item: `(1h)`, `(30m)`, `(2h30m)`
- Time prefix = scheduled at a specific time: `- [ ] 09:00 Dentist (1h)`
- No time prefix = flexible/unscheduled: `- [ ] Reply to email (10m)`
- Plain text (no checkbox) = time container headers: `- Flexible time`, `- Admin batch`
- `~` prefix = approximate time: `- [ ] ~14:00 Delivery window (30m)`
- `### Morning / Afternoon / Evening` = section dividers with time ranges
- Tentative items get `(tentative)` suffix: `- [ ] 19:00 Dinner with Sam (tentative)`

**Every actionable item gets a `- [ ]` checkbox.** Time container headers (plain `- ` lines grouping flexible tasks) are the only lines without checkboxes.

**Item linking:** Every item in a day section or Backlog should link to its project/area context where one exists:
- Project doc exists → `→ [[03 Projects/Project Name]]`
- Area doc exists → `→ [[04 Areas/path/doc]]`
- No dedicated doc but tracked in WIP → `→ [[01 Now/Works in Progress#Heading]]`
- Standalone/generic items (no project context) → no link
When moving items that already have project/area links, preserve them. Replace session log links with project/area links (session context is low-value once the item is in a planning doc).

Pull items from:
- Items carried forward from stale This Week.md (if any, noted in step 3)
- Time-sensitive items and appointments
- WIP project docs (follow **Next:** links to project pages for task queues)
- Yesterday's queue (from /goodnight Daily Report)
- Today's items already in This Week.md (migrated from Tickler in steps 3/6)
- Anything the user mentioned in step 4

**Move, not copy.** When an item from the Backlog section is scheduled into today's timeline, delete it from the Backlog. The day section becomes SSOT for that item. If the item doesn't get done, /goodnight routes it back to Backlog or a future day — but it must never exist in both places simultaneously.

Completed items get `[x]` in the timeline (standard Obsidian checkbox: `- [x] Task`). Detailed completion notes go in the "Done today" subsection under today's day heading.

**Future days** in the same file stay simple — just task lists under the `## ` heading, no `### Morning/Afternoon/Evening` sub-sections. They get expanded with the full timeline format when that day becomes "today" via /morning.

**Refs** section at bottom of the file — `[[wikilinks]]` linking timeline items to project/area files.

**Creation:** If This Week.md is stale or missing:
> "This Week.md is [stale/missing]. Want me to create one for this week?"

If yes — and if replacing a stale file, first show unchecked items from the old This Week.md and ask which to carry forward into the new week. Then create `{VAULT}/01 Now/This Week.md` — today + 6 future days (7 sections). Today gets the full timeline (including carried-forward items); future days get simple task lists:

````
# This Week — [DD] [Mon] – [DD] [Mon] [YYYY]

## [Today] [DD] [Mon]
[Full timeline with ### Morning/Afternoon/Evening sections as above]

## [Day+1] [DD] [Mon]
- Task 1
- Task 2

## [Day+2] [DD] [Mon]
- Task 1

[... 7 days total]

## Refs
- [[wikilinks to relevant project/area files]]
````

**If no or the day is unstructured:** Skip. Not every day needs a timeline.

### 8. Output (conditional)

**Note:** By this point, all brain dump items from step 4 should ALREADY be written to files (step 5). This step is only for This Week.md and any additional generative content — not for deferred captures.

**Most days with This Week.md:** The updated This Week.md is the artifact. No additional output needed.

**If generative/insight content** (beyond what was captured in step 5):
- Append to today's journal at `{VAULT}/05 Resources/Journal/YYYY-MM-DD.md`
- Or create morning note at `{VAULT}/06 Archive/Morning Notes/YYYY-MM-DD.md` (create directory if needed)

**If nothing:** Just close cleanly.

### 9. Close

Short and light:
```
✓ Landscape reviewed
✓ [X items captured / Nothing new]
✓ This Week.md updated (or "Open day — no plan needed")
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

- **Reads from:** Works in Progress, This Week.md (date-range freshness + tickler migration), Tickler, recent Claude Sessions, Daily Reports, Weekly Reviews (staleness), Quarterly Reviews (staleness)
- **May create/update:** This Week.md (weekly plan with day sections)
- **May update:** Works in Progress, Tickler (mark items done or reschedule), Journal, Project files, previous day's Daily Report (post-goodnight reconciliation)
- **Complements:** `/park` (end of session), `/goodnight` (end of day), `/afternoon` (mid-day)
- **Doesn't replace:** Morning pages / journaling (that's separate generative practice)
