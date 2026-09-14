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

**Write mechanism (F1) — applies to every step below.** All mutations of `This Week.md`, `Tickler.md`, and project/area hub files in this skill go through `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5 — incl. the `write-tickler.sh`-vs-`locked-edit.sh` split for Tickler and exit-code handling).

### 0. Resolve Vault Path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
"$VAULT_PATH/.claude/scripts/check-archive-layout.sh" --enforce "$VAULT_PATH"
```

If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

### 1. Check current date/time

```bash
date +"%A, %d %b %Y — %H:%M %Z"  # friendly display with time and timezone
date +"%Y-%m-%d"                   # for file paths if needed
```

### 2. Reconcile recent close-outs

Read `~/.claude/commands/goodnight.md` and execute its **Catch-up mode**, passing the current date from Step 1. Goodnight owns missed-day detection, close-out recovery and late-session reconciliation. Retain its returned dates, report paths and deferred debriefs for Steps 4–5, then continue to the landscape. Do not implement a second catch-up procedure here.

### 3. Surface the Landscape (auto, ~1 min)

**Maintain the window before reading the landscape.** If This Week.md exists, run `_shared-rules.md` Section 9 now, before the Tickler migration or upcoming-day scan. This creates and populates the today+6 section so the landscape's stated forward window is the surface it actually reads. Preserve project/area links, replace session-log-only links, and link bare items per Section 3.

**Weather forecast:** Fetch the 7-day forecast from the Open-Meteo API (free, no key). Determine the user's current city from CLAUDE.md context (TZ field, travel status, or This Week.md location banner), resolve its coordinates — if not already known, use Open-Meteo's geocoding endpoint (`curl -sf "https://geocoding-api.open-meteo.com/v1/search?name=CITY&count=1"`, take `latitude`/`longitude` from the first result; do not guess coordinates) — and run:

```bash
curl -sf "https://api.open-meteo.com/v1/forecast?latitude=LAT&longitude=LON&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation&timezone=TZ&forecast_days=7"
```
API returns Celsius by default. Keep Celsius unless the user's **locale** (CLAUDE.md, e.g. `en_US`) uses Fahrenheit — only then add `&temperature_unit=fahrenheit`. Base this on locale/home preference, **never** on the current travel location: a Celsius user travelling in the US still wants Celsius.

Parse the JSON and format as a compact markdown block:
```
**Weather (City):** 25°C now, humidity 88%, wind 9 km/h
**Forecast:** ☁️ Sat 28/25°C · 🌦️ Sun 27/23°C, 33% rain · ...
*Updated [Day DD Mon HH:MM TZ] via Open-Meteo*
```

WMO weather codes → emoji: 0 ☀️, 1 🌤️, 2 ⛅, 3 ☁️, 45/48 🌫️, 51-55 🌦️, 61-65 🌧️, 71-75 🌨️, 80 🌦️, 81-82 🌧️, 95-99 ⛈️. Only show rain % if >5%.

**⛔ The `HH:MM` in the `*Updated ...*` stamp must come from a `date +"%a %d %b %H:%M %Z"` result you have already seen** — never estimated from when you think the fetch happened (`_shared-rules.md` §19, clock values: two calls, ordered).

If the API call fails (no internet, timeout), skip silently — weather is nice-to-have, not blocking.

Include the weather output in the landscape presentation, and if This Week.md exists, update or insert the weather block in the banner area (after the `**Location:**` line, before the `---` separator that divides the banner from the day sections). If the file has no banner — no `**Location:**` line, no `---` — insert the block directly after the `# This Week — ...` heading and add a `**Location:** [current city]` line above it and a `---` below it, so the banner matches the Step 7 creation skeleton from then on. Replace any existing `**Weather` / `**Forecast:**` / `*Updated ... via Open-Meteo*` lines with the fresh output.

**Drop any `**Status:**` line from the banner.** Deprecated — duplicates today's day section, drifts the moment the plan shifts mid-session, and creates a second authoritative surface for today's focus that can silently diverge from the day section (which is the real artefact). Keep `**Location:**` (stable travel context) and the weather block (external, refreshed); remove any legacy `**Status:**` line on this morning's pass.

**Active projects (read the root):** Read every `.md` in the `{VAULT}/03 Projects/` root (not `Cold/`, not `Backlog/` — folder location is project status: root = active, `Cold/` = paused). Each root doc must carry `bucket:` YAML frontmatter (values per the vault's bucket taxonomy — Project Doc Format in `07 System/Vault Organisation Principles.md`). `## Current Objective` and `## Next Actions` are optional conventions: use them when present; otherwise read the document's existing current-state and action structure without inventing missing sections. If a doc lacks `bucket:`, **fail closed for that doc** — list the missing field in the landscape output rather than inventing content. There is no rendered dashboard file: the fresh root listing plus these reads *are* the view, presented in the landscape output and discarded — never persisted to `01 Now/`. If the root doc count exceeds the **active project cap** (resolve it first: `grep -F '**Active project cap:'` over `{VAULT}/07 System/Vault Organisation Principles.md` → *Project Doc Format*, and state the value found. **`-F` is required** — a leading `**` is a repetition operator to some greps, which error out instead of matching. Exit 1, or a line yielding no number, means state `cap line unreadable — using default 5` and proceed on 5, so a failed read is never mistaken for a vault that states no cap. **Any other non-zero exit is a tool error, not an absent line** — report it and stop, rather than falling through to the default, which is the failure this branch exists to prevent) — flag it in the landscape output and ask which project moves to `Cold/`.

Read and present:
- **Active projects:** From the root docs just read — project names and the available current-state/action cues per bucket
- **This Week.md freshness:** Check `{VAULT}/01 Now/This Week.md` — if it exists, parse the date range from the heading (e.g. "# This Week — 28 Feb – 7 Mar 2026"). The range is a rolling window (normally 10 day sections: 3 past + today + 6 future), not calendar weeks. If today's date falls within the range, it's current — note today's day section and any unchecked items in your working memory for step 7. If today falls outside the range, it's stale — note any unchecked items in your working memory for carry-forward in step 7. If the file doesn't exist, skip.
- **Tickler items due:** Read `{VAULT}/01 Now/Tickler.md` (skip if file doesn't exist), show items where date header <= today (YYYY-MM-DD format). Separate into two groups: **Today** (date == today) shown in full, and **Overdue** (date < today) shown as a compact summary — just the item names with overdue flag, not full descriptions. If overdue count is large (>5), group by theme or just show count + the most time-sensitive ones. Don't let overdue backlog bury today's items.
- **Tickler→This Week migration (automatic, unconditional):** If `{VAULT}/01 Now/This Week.md` exists, check Tickler for unchecked items with date headers falling within the This Week.md date range that aren't already represented in This Week.md. **Migrate them automatically** — add each item to the appropriate day section in This Week.md and delete from Tickler (This Week becomes SSOT per Tickler transfer rules). **The migration is gated on the date and nothing else** — not on how many items the destination day already holds, not on the window total. A dated item's home is its day section; holding it back because a day looks full hides work that is genuinely due and splits the SSOT. Also delete any completed (`[x]`) items from those same Tickler date sections as cleanup. When migrating, preserve existing project/area links (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`). If an item has only a session log link (`→ [[06 Archive/...]]`), replace it with the relevant project/area link. If no link, add one per the item linking convention (see Step 7).
- **Coming up this week:** After migration, scan This Week.md for all unchecked items on **future days** (day sections after today). Show them in the landscape output grouped by day. This gives visibility into the week ahead regardless of whether items were just migrated or were already there. This prevents the misleading "Nothing due today" pattern where upcoming items are invisible.
- **Yesterday's sessions (context only):** Check `{VAULT}/06 Archive/OpenCairn/Session Logs/` for most recent session file — note topics and summaries for context, but do NOT extract open loops from session files. Open items come from This Week.md and Tickler only (session loops were routed to SSOT at park time)
- **Items goodnight routed to today:** Last night's /goodnight routed undone and queued items into today's day section in This Week.md — they're already covered by the This Week.md and Tickler bullets above. Daily reports carry no "Tomorrow's Queue" section; don't go looking for one.
- **Disciplines reminder:** Read `{VAULT}/07 System/Context - Direction.md` (skip if file doesn't exist). If a Disciplines section exists with active items, include a one-line reminder in the landscape output. Light touch — just surface the list, don't track or nag.
- **Time-sensitive items:** Scan dated entries in the root docs' existing task/action sections and recent sessions for deadlines and urgencies
- **Working Memory status:** Check `{VAULT}/01 Now/Working memory.md` (skip if file doesn't exist). Count unchecked items (`- [ ]`) and total lines. If unchecked count > 30 or total lines > 300, flag in landscape output:
  ```
  **⚠️ Working Memory overflow** — [N] unchecked items, [L] lines. Consider a triage pass (a Working-Memory processing skill if you have one; `/inbox-processor` only covers `02 Inbox/`, not this file).
  ```
  Also check for a "Completed" or "Likely Stale" section — if it has unchecked items, note the count: `[N] items flagged for deletion — confirm during this session?`
- **Review staleness:** Check when the last weekly review and quarterly review were run:
  ```bash
  ls -1 "{VAULT}/06 Archive/OpenCairn/Weekly Reviews/" 2>/dev/null | rg '^[0-9]{4}-W[0-9]{2}[a-z]?\.md$' | LC_ALL=C sort -r | head -1
  ls -1 "{VAULT}/06 Archive/Quarterly Reviews/" 2>/dev/null | rg '^[0-9]{4}-Q[1-4][a-z]?\.md$' | LC_ALL=C sort -r | head -1
  ```
  Weekly review files are `YYYY-Wnn.md` (ISO week number); quarterly files are `YYYY-QN.md` — both byte-sortable, including the known same-period suffix shape (`YYYY-Wnnb.md` / `YYYY-QNb.md`). Filter to those canonical names and pin `LC_ALL=C`; ambient locale collation can rank the older bare file after its suffixed successor. Selection sorts on filename, never mtime (`ls -t` is banned by the same rule that governs the dating below). **Date the review from its own header, and compute the elapsed days in bash** — the general rule is `_shared-rules.md` §22 (artefact age comes from content, never mtime); the two wrong sources it bans show up here as:

  - **Not the filename**, via internal arithmetic — the date-mapping class LLMs are unreliable at.
  - **Not the file's mtime.** Any later touch resets it — an audit remediation, a sync write, a hygiene pass, an editor opening the file — so a review edited after the fact reads as *fresher than it was run*. The error is asymmetric in the dangerous direction: it makes an overdue review look current, which is the exact failure this check exists to catch.

  Instead, read the newest file's header (reviews open with their coverage range) and take the **end** of that range as the run date. Then:
  ```bash
  echo $(( ( $(date +%s) - $(date -d "YYYY-MM-DD" +%s) ) / 86400 ))   # substitute the header's range-end date
  ```
  **⛔ State the elapsed days explicitly in your response** before drawing any staleness conclusion — "last run <date>, N days ago" is the checkable output; a bare "current" / "overdue" verdict with no number on the page means the check was done from impression, not evidence. If the header carries no usable date, say so and skip the flag rather than falling back to mtime.

  Flag if weekly review is >10 days old or quarterly review is >100 days old. Show each overdue review individually — don't mention reviews that are current. Before treating an empty or missing review directory as an unstarted cadence, search live planning and area docs for that review command/name. A hit that actually states a recurring schedule makes the absent output overdue; a mere mention does not. With no scheduled cadence, skip the review type.

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

**Disciplines:** [Discipline 1] · [Discipline 2] · [Discipline 3]

**Time-sensitive:**
- [Item] - [deadline]

**⚠️ Weekly review overdue** — last run [date] ([N] days ago)
**⚠️ Quarterly review overdue** — last run [date] ([N] days ago)
```

If a section is empty, skip it. Keep it scannable.

### 4. Open Space

If Step 2 returned pending debriefs, invoke `/goodnight` **C3. Complete a deferred catch-up debrief** with that handoff before the normal open-space question.

Ask:
> "Anything you'd like to add this morning?"

**If "nothing" or minimal:** Move to step 6, keep it quick.

**If stuff comes up:** Let it flow. Don't rush. This is generative space. Let the user dump everything before you respond. The user will often also respond to the landscape from step 3 in the same message (marking items done, rescheduling, adding context). Treat all of this as input to step 5.

### 5. Capture Gate (MANDATORY — do not skip or defer)

**After** the user finishes their response (whether it's brain dump items, landscape corrections, scheduling decisions, or all three), and **before** moving to step 6:

**Capture means writing to a file, not acknowledging in conversation.** If it's not in a file, it's not captured. Discussing an item, triaging it, or giving an opinion about it is not capturing it.

For every item the user mentioned:

1. **Triage each item into one of these categories:**
   - **Status update** (e.g. "Tentrem done", "train booked") → Mark done in Tickler/project file. Trace references — a status change may touch multiple files.
   - **Reschedule** (e.g. "do this on the 26th", "next week") → Move to appropriate Tickler date or update project file
   - **Actionable task** → Write to the appropriate file (Tickler for date-specific, project file for project-scoped, a new project doc via `/start-project` for new workstreams)
   - **Decision (resolved)** → Write the decision + rationale to the relevant project file
   - **Decision (open)** → Write to relevant project's "Open Decisions" section
   - **Research/idea** → Write to the relevant project or area file
   - **Activity outside agent sessions from a caught-up day** → Pass the answer and Step 2’s dated handoff to `/goodnight` C3 for capture in the correct report.
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

Step 3 already ran rolling-window maintenance before presenting the landscape. Re-run it here only if Step 5 wrote or changed dated items in Tickler or This Week.md; otherwise verify that the today+6 section still exists and make no second mutation. If This Week.md does not exist, skip this step (Step 7 will offer to create it).

### 7. Update today's timeline (optional)

**Daily execution when configured.** Follow the Planning system pointer in the vault’s navigation/Autopilot document. The user manages the calendar. If they want a rendered timeline, reflect known commitments (read the live calendar if requested) and choose This Week tasks for gaps, preserving open tasks. Do not require a daily strategy/values-plan reread, label blocks, verify weekly scheduling, or rebuild the week. Calendar changes need an explicit request. Preserve any old task’s operational review/continuation link until its disposition is settled; do not restart retired scheduling-resume machinery.

If the day has enough structure to benefit from a visual plan (appointments, time blocks, multiple tasks), offer:

> "Want me to update today's section in This Week.md?"

**If yes:**

If This Week.md doesn't exist or is stale (today outside the date range), offer to create a fresh one first (see "Creation" below).

Find today’s day section using `_shared-rules.md` §9’s date-aware heading parse (including emoji/theme suffixes). Replace/expand it with the timeline format — native markdown so Obsidian checkboxes work:

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

**Item linking:** Every item in a day section should link to its project/area context where one exists:
- Project doc exists → `→ [[03 Projects/Project Name]]`
- Area doc exists → `→ [[04 Areas/path/doc]]`
- Standalone/generic items (no project context) → no link
When moving items that already have project/area links, preserve them. Replace session log links with project/area links (session context is low-value once the item is in a planning doc).

Pull items from:
- Items carried forward from stale This Week.md (if any, noted in step 3)
- Known commitments and time-sensitive items; optional live calendar information when requested. Unavailable calendar evidence is labelled, not guessed
- Project docs (their existing task/action queues, read in step 3)
- Items /goodnight routed into today's day section last night
- Today's items already in This Week.md (migrated from Tickler in steps 3/6)
- Anything the user mentioned in step 4

Completed items get `[x]` in the timeline (standard Obsidian checkbox: `- [x] Task`).

**Future days** in the same file stay simple — just task lists under the `## ` heading, no `### Morning/Afternoon/Evening` sub-sections. They get expanded with the full timeline format when that day becomes "today" via /morning.

**Refs** section at bottom of the file — `[[wikilinks]]` linking timeline items to project/area files.

**Creation:** If This Week.md is stale or missing:
> "This Week.md is [stale/missing]. Want me to create one for this week?"

If yes — and if replacing a stale file, carry every unchecked item from the old This Week.md forward intact; do not require the user to choose the same work again. Then create `{VAULT}/01 Now/This Week.md` — today + 6 future days (7 sections). Today gets the full timeline (including carried-forward items); future days get simple task lists:

````
# This Week — [DD] [Mon] – [DD] [Mon] [YYYY]

**Location:** [current city]
[weather block from step 3, if the fetch succeeded]

---

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

**Most days with This Week.md:** The updated This Week.md is the artefact. No additional output needed.

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
- **This Week.md is the artefact when needed:** For structured days, update today's section in This Week.md. For open/exploratory days, the conversation itself is the routine — no file update needed.
- **Light touch:** This isn't therapy or heavy journaling. Quick check-in that can expand if needed.
- **No guilt:** If the user skips steps or says "I'm good," respect that. The routine serves him, not vice versa.
- **Capture means file writes:** If something comes up, write it to the right place (project doc, journal, Tickler) immediately. Don't just discuss routing — do the routing. Don't create new systems or files when an existing one fits.
- **Preserve verbatim content on compression or move.** When folding multiple items into a single bullet OR moving an item between days, scan each source item for load-bearing verbatim content the user will execute against — exact quoted phrases inside `*"..."*`, explicit if/then decision trees, specific wordings, reference numbers, exact ask wording. For each: grep the destination project/area hub for the distinctive substring. If absent there, preserve verbatim in the new location (as sub-bullets under the compressed bullet if compressed) rather than abstracting to a topic summary. Default assumption: if the user wrote it down with specific wording, the wording is the artefact, not decoration.
- **Morning pages complement:** This is operational/triage. Morning pages (journal) is generative/exploratory. They can happen same morning - this first (quick), then journal (if desired).

## Triggers

This command should trigger when the user says:
- "morning"
- "good morning"
- "start the day"
- "what's on deck"
- "what do I have today"

## Integration

- **Reads from:** 03 Projects root docs, This Week.md (date-range freshness + tickler migration), Tickler, Direction (disciplines reminder), recent agent session logs, Daily Reports, Weekly Reviews (staleness), Quarterly Reviews (staleness), Open-Meteo API (weather forecast)
- **May create/update:** This Week.md (weekly plan with day sections)
- **May update:** Tickler (mark items done or reschedule), Journal, Project files, previous day's Daily Report (post-goodnight reconciliation), `07 System/AI Provenance Log.md` + `07 System/.Provenance/pending/` flags (via `/goodnight` Catch-up mode)
- **Complements:** `/park` (end of session), `/goodnight` (end of day), `/afternoon` (mid-day)
- **Doesn't replace:** Morning pages / journaling (that's separate generative practice)
