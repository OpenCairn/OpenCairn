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

**Write mechanism (F1) — applies to every step below.** All mutations of `Works in Progress.md`, `This Week.md`, `Tickler.md`, and project/area hub files in this skill go through `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5 — incl. the `write-tickler.sh`-vs-`locked-edit.sh` split for Tickler and exit-code handling).

### 0. Resolve Vault Path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

### 1. Check current date/time

```bash
date +"%A, %d %b %Y — %H:%M %Z"  # friendly display with time and timezone
date +"%Y-%m-%d"                   # for file paths if needed
```

### 2. Reconcile yesterday's close-out

#### 2a. Catch up missed /goodnight

**Read `goodnight.md` (same commands directory as this file) before executing a catch-up.** 2a applies /goodnight's Step 8 report format, Step 9 routing logic, Step 10 collapse format, and Step 15 audit protocol by reference — executing them from this file's paraphrase alone produces catch-up reports that drift from goodnight-produced ones, on the exact archival surface `/weekly-review` parses mechanically.

Scan backwards from yesterday up to 3 days (to catch multi-day gaps from travel/offline). For each day, in chronological order:

1. Check if a daily report exists: `{VAULT}/06 Archive/Claude/Daily Reports/YYYY-MM-DD.md`
2. If daily report exists → skip this day (already closed out).
3. Check if a session log exists: `{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`
4. If no session log or no sessions → skip silently (nothing to close out).
5. If sessions exist but no daily report → **/goodnight was missed.** Run a lightweight catch-up:

   a. Read the day's session log and its day section in This Week.md.
   b. **Generate the daily report** at `{VAULT}/06 Archive/Claude/Daily Reports/YYYY-MM-DD.md` — follow the Daily Report format in /goodnight Step 8: convert the day section into `## Today's Plan` with `[x]`→`✓` and `[ ]`→plain bullets; list sessions; list blockers. Include the catch-up close-out itself as the last numbered Sessions entry (`N. **Goodnight catch-up via /morning** — [one-line outcome]`), mirroring /goodnight Step 8's include-the-close-out rule — plan the line here to match the session entry 2a.e writes. **Omit the `## Outside-Claude` section** — no debrief prompt fires during 2a itself (the user is async — the caught-up day is done, not memory-fresh). Step 4 (Open Space) runs the deferred off-Claude debrief for each caught-up day; any activity it surfaces is back-filled into that day's daily report via the Step 5 Capture Gate (see Step 5).
   c. **Route undone items** from the day section in This Week.md — same logic as /goodnight Step 9 (natural future day → move there; priority → today's section; low priority/no deadline → Tasks.md; already in future day → delete duplicate). Carry items forward intact including sub-items and checklists, applying /goodnight Step 9's block-boundary rule. **Date shift:** during catch-up, "tomorrow" (where /goodnight would route priority items) means **today**, not the day after today.
   d. **Collapse the day section** to a one-liner + daily report link (same format as /goodnight Step 10). Also collapse any earlier verbose day sections within the file.
   e. **Log a catch-up session** to the day's session file via write-session.sh with `--auto-number` (resolves N atomically inside the file lock — eliminates collision against parallel /park or /goodnight invocations):

      ```bash
      cat << 'EOF' | "{VAULT}/.claude/scripts/write-session.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" --auto-number "Goodnight catch-up via /morning" "HH:MMam/pm"
      ### Summary
      [Brief summary of what was generated/routed]

      ### Files Created
      - 06 Archive/Claude/Daily Reports/YYYY-MM-DD.md

      ### Files Updated
      - [Items routed by 2a.c/d]

      ### Pickup Context
      **For next session:** [pickup pointer for today]
      EOF
      ```

      Body only — no `## Session N` heading; the script prepends it. Capture the assigned N from the `Session number assigned: N` stdout line for the audit brief in 2a.g.
   f. **Skip** (not part of catch-up): debrief prompt (Step 4 runs it for each caught-up day), WIP timestamp bump. These are either handled by /morning's own flow or are non-critical for a retroactive close-out. (Provenance processing is **not** skipped — see 2a.h, which runs after the audit.)
   g. **Run /audit via a fresh sub-agent on the catch-up** — apply /goodnight Step 15 sub-steps (a)–(f) verbatim (including the (f) Files-Updated backfill, scoped to the catch-up session entry). Catch-up performs the same state-propagating actions as /goodnight (status flips on items the user may have already marked, day-section collapses, item routing, session-log writes) and is subject to the same Layer 3 failure mode (stale phase/status framings in project hubs and area files that referenced the caught-up day's now-historical state). Inline audit suffers the same cognitive-load / enumeration-scoping / recency-bias mechanisms documented in `/park` Step 14 tail. **Unconditional, not gated on substrate size:** even a "trivial" catch-up writes a NEW daily report file + NEW catch-up session entry, so the enumeration floor is never zero — same logic as /goodnight Step 15.

      Substrate-specific notes (when applying Step 15's checklist to the catch-up):
      - Identifier enumeration (15a) substrate is: completed-loop flips on `[x]` items the day section already had (rare — 2a generally inherits state, doesn't flip), day-section moves from 2a.c, Tasks.md routings from 2a.c, day-section collapses from 2a.d, NEW daily report file from 2a.b, NEW catch-up session entry from 2a.e. The last two are always present.
      - Sub-agent brief (15c) must include: vault path (absolute), the caught-up day's daily report path, the catch-up session log path with session number (from 2a.e's `Session number assigned: N` stdout), the file list (different from /goodnight's — assemble from 2a.b/c/d/e edits), one-paragraph summary of what the catch-up did, the enumerated identifiers verbatim, script paths (`update-session-section.sh`, `backfill-files-updated.sh`, `write-tickler.sh`), the locking constraint, the audit-protocol pointer (`audit.md` Phase 2 Layers 1–5, in `~/.claude/commands/` or `{VAULT}/.claude/commands/`), the special-focus instruction on phase/status framings rendered historical, the read-coverage backstop with bytes-read reporting, authority to remediate inline and iterate until clean, and the expected report format. **Layer 5 specific for the catch-up:** trace this morning's landscape pass (Step 3) against the post-catch-up SSOT state — anything the catch-up just routed should surface correctly when Step 3 runs.
      - **Pre-state authority in the audit brief:** the authoritative pre-catch-up state is the main session's own Read of This Week.md at catch-up time — embed the relevant pre-collapse content in the brief if the auditor needs it. Do NOT direct the sub-agent to reconstruct pre-state from vault auto-save git: commit boundaries are arbitrary, and a morning-window commit typically captures the *user's own* pre-/morning edits, so its diff mis-attributes user actions to the catch-up. Any git-derived data-loss finding must be verified against the specific commit's diff content and timing before remediation.
      - After the sub-agent returns: verify any remediation edits were backfilled to the catch-up session entry via `backfill-files-updated.sh`. If not, run the backfill from the file list the sub-agent reported.
   h. **Process this day's provenance flag(s), if any.** Glob `{VAULT}/07 System/Provenance/pending/` for files whose name begins with **this caught-up day's own date** (`YYYY-MM-DD` — the loop's current day, never today, and never an empty/unsubstituted date, which would match every pending flag and process the wrong days). `/provenance` writes one flag per tag, so a day may have **more than one** — process **each** matching flag. If none match, skip silently. A match means `/provenance` ran that day but `/goodnight` never processed it — process it now per `/goodnight` Step 17 (mechanism) and `/weekly-hygiene` Step 14a (past-day adaptation), with these specifics:
      - **Must run after 2a.g completes — including its post-return Files-Updated backfill — never before.** Same strict ordering as /goodnight Steps 15→16→17: the audit can still modify the caught-up day's session log, and the hash must cover its final state. Hashing before the audit produces an immediately-invalid proof — the single most common provenance execution error.
      - **Export that day's transcript first, then confirm the file landed.** A missed-goodnight day may never have been exported (only /park and /goodnight export transcripts). Run `python3 "{VAULT}/.claude/scripts/export-session-transcripts.py" "{VAULT}" --days 7 --all-projects` — `--all-projects` **unconditionally** (morning has no `cd` to the day's launch directory, and which project a past session launched from is unknowable during catch-up; the flag is cwd-independent), and `--days 7` because the script windows and dates each transcript file by the JSONL's **mtime**, not the logical session date — a tight window can miss or mis-date the boundary day, so clear it with margin. **Then verify `06 Archive/Claude/.Session Transcripts/YYYY-MM-DD.md` exists for the caught-up date.** If it does not, do **not** hash a missing/empty file and do **not** delete the flag — hash what you can, leave the flag in `pending/` for `/weekly-hygiene`, and report it as partially processed.
      - **Then hash per the flag:** the work products it lists (on a mismatch against an existing "Hashed Immediately" entry, run /provenance Step 5's superseding re-hash path — don't skip silently); that date's transcript (verified above); that date's session log (`06 Archive/Claude/Session Logs/YYYY-MM-DD.md`, final after 2a.e + 2a.g). OTS-stamp the hashed files and append rows to `07 System/AI Provenance Log.md` via `locked-edit.sh --append`. **Delete each flag only after a log row exists for every required target — each listed work product, the transcript, and the session log** (not merely the flag's listed work products). Any flag with a target still unrowed stays in `pending/` for `/weekly-hygiene`. See `/provenance` for flag format and full hashing instructions.
   i. Display:
      ```
      ⚠ /goodnight was not run for [Day DD Mon] — caught up:
      ✓ Daily report generated: 06 Archive/Claude/Daily Reports/YYYY-MM-DD.md
      ✓ [N] undone items routed from [Day]'s section
      ✓ [Day] section collapsed
      ✓ Audit: clean pass [OR "🔧 Audit: N findings fixed and re-audited clean — see [paths]"]
      ✓ Provenance: N files hashed [OR "⚠ Provenance: partially hashed — flag retained for /weekly-hygiene" if a required target was missing; omit the line entirely if no flag existed]
      ```

#### 2b. Reconcile post-goodnight sessions

For each day that now has a daily report (whether from /goodnight or 2a), check for late sessions:

1. Read the day's session log.
2. Find the goodnight session — match pattern `^## Session [0-9]+ - Goodnight:` (colon required to distinguish from sessions that happen to mention "goodnight" in their topic). Also match `Goodnight catch-up via /morning` for catch-up sessions from 2a.
3. If no goodnight session found → skip.
4. Extract the goodnight session number. Check if any sessions exist with a higher number.
5. If no post-goodnight sessions → skip silently.
6. If post-goodnight sessions found:
   - Read each post-goodnight session block.
   - **Append** the late session(s) to the `## Sessions` list in the daily report. That is the only daily-report section late sessions touch — any completions they contain live in the SSOT files (This Week.md, Tickler, project files), not the report.
   - Do NOT modify other sections — `## Today's Plan`, `## Outside-Claude`, and `## Blockers` were set deliberately at close-out and remain valid.
   - Add a note at the end of the Sessions section: `*Sessions N–M added by /morning (ran after close-out)*`
   - **Refresh the collapsed day's one-liner in This Week.md.** /goodnight Step 10 collapsed the day to `## [emoji] [Day] [Date] — [Theme] ✅` + one sentence + report link. If the late sessions change what the day amounted to, extend that sentence to mention them; otherwise leave it alone. (The collapse format carries no session count — do not invent or parse one.)
   - Display:
     ```
     ✓ Reconciled: [N] post-goodnight session(s) added to yesterday's daily report
       - Session M: [Topic] - [outcome]
     ✓ This Week.md collapsed-day summary extended (only if the late sessions changed the day's shape)
     ```

### 3. Surface the Landscape (auto, ~1 min)

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

If the API call fails (no internet, timeout), skip silently — weather is nice-to-have, not blocking.

Include the weather output in the landscape presentation, and if This Week.md exists, update or insert the weather block in the banner area (after the `**Location:**` line, before the `---` separator that divides the banner from the day sections). Replace any existing `**Weather` / `**Forecast:**` / `*Updated ... via Open-Meteo*` lines with the fresh output.

**Drop any `**Status:**` line from the banner.** Deprecated — duplicates today's day section, drifts the moment the plan shifts mid-session, and creates a second authoritative surface for today's focus that can silently diverge from the day section (which is the real artefact). Keep `**Location:**` (stable travel context) and the weather block (external, refreshed); remove any legacy `**Status:**` line on this morning's pass.

Read and present:
- **Works in Progress:** Read `{VAULT}/01 Now/Works in Progress.md`, show Active section
- **This Week.md freshness:** Check `{VAULT}/01 Now/This Week.md` — if it exists, parse the date range from the heading (e.g. "# This Week — 28 Feb – 7 Mar 2026"). The range is a rolling window (up to 10 day sections: 3 past + today + 6 future), not calendar weeks. If today's date falls within the range, it's current — note today's day section and any unchecked items in your working memory for step 7. If today falls outside the range, it's stale — note any unchecked items in your working memory for carry-forward in step 7. If the file doesn't exist, skip.
- **Tickler items due:** Read `{VAULT}/01 Now/Tickler.md` (skip if file doesn't exist), show items where date header <= today (YYYY-MM-DD format). Separate into two groups: **Today** (date == today) shown in full, and **Overdue** (date < today) shown as a compact summary — just the item names with overdue flag, not full descriptions. If overdue count is large (>5), group by theme or just show count + the most time-sensitive ones. Don't let overdue backlog bury today's items.
- **Tickler→This Week migration (automatic):** If `{VAULT}/01 Now/This Week.md` exists, check Tickler for unchecked items with date headers falling within the This Week.md date range that aren't already represented in This Week.md. **Migrate them automatically** — add each item to the appropriate day section in This Week.md and delete from Tickler (This Week becomes SSOT per Tickler transfer rules). Also delete any completed (`[x]`) items from those same Tickler date sections as cleanup. When migrating, preserve existing project/area links (`→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`). If an item has only a session log link (`→ [[06 Archive/...]]`), replace it with the relevant project/area link. If no link, add one per the item linking convention (see Step 7).
- **Coming up this week:** After migration, scan This Week.md for all unchecked items on **future days** (day sections after today). Show them in the landscape output grouped by day. This gives visibility into the week ahead regardless of whether items were just migrated or were already there. This prevents the misleading "Nothing due today" pattern where upcoming items are invisible.
- **Yesterday's sessions (context only):** Check `{VAULT}/06 Archive/Claude/Session Logs/` for most recent session file — note topics and summaries for context, but do NOT extract open loops from session files. Open items come from This Week.md and Tickler only (session loops were routed to SSOT at park time)
- **Items goodnight routed to today:** Last night's /goodnight routed undone and queued items into today's day section in This Week.md (and Tasks.md) — they're already covered by the This Week.md and Tickler bullets above. Daily reports carry no "Tomorrow's Queue" section; don't go looking for one.
- **Disciplines reminder:** Read `{VAULT}/07 System/Context - Direction.md` (skip if file doesn't exist). If a Disciplines section exists with active items, include a one-line reminder in the landscape output. Light touch — just surface the list, don't track or nag.
- **Time-sensitive items:** Scan WIP and recent sessions for deadlines, urgencies
- **Working Memory status:** Check `{VAULT}/01 Now/Working memory.md` (skip if file doesn't exist). Count unchecked items (`- [ ]`) and total lines. If unchecked count > 30 or total lines > 300, flag in landscape output:
  ```
  **⚠️ Working Memory overflow** — [N] unchecked items, [L] lines. Consider a triage pass (a Working-Memory processing skill if you have one; `/inbox-processor` only covers `02 Inbox/`, not this file).
  ```
  Also check for a "Completed" or "Likely Stale" section — if it has unchecked items, note the count: `[N] items flagged for deletion — confirm during this session?`
- **Review staleness:** Check when the last weekly review and quarterly review were run:
  ```bash
  ls -1t "{VAULT}/06 Archive/Claude/Weekly Reviews/"*.md 2>/dev/null | head -1
  ls -1t "{VAULT}/06 Archive/Quarterly Reviews/"*.md 2>/dev/null | head -1
  ```
  Weekly review files are `YYYY-Wnn.md` (ISO week number); quarterly files are `YYYY-QN.md`. **Date the review from its own header, and compute the elapsed days in bash.** Two wrong sources to avoid:

  - **Not the filename**, via internal arithmetic — the date-mapping class LLMs are unreliable at.
  - **Not the file's mtime.** Any later touch resets it — an audit remediation, a sync write, a hygiene pass, an editor opening the file — so a review edited after the fact reads as *fresher than it was run*. The error is asymmetric in the dangerous direction: it makes an overdue review look current, which is the exact failure this check exists to catch.

  Instead, read the newest file's header (reviews open with their coverage range) and take the **end** of that range as the run date. Then:
  ```bash
  echo $(( ( $(date +%s) - $(date -d "YYYY-MM-DD" +%s) ) / 86400 ))   # substitute the header's range-end date
  ```
  **⛔ State the elapsed days explicitly in your response** before drawing any staleness conclusion — "last run <date>, N days ago" is the checkable output; a bare "current" / "overdue" verdict with no number on the page means the check was done from impression, not evidence. If the header carries no usable date, say so and skip the flag rather than falling back to mtime.

  Flag if weekly review is >10 days old or quarterly review is >100 days old. Show each overdue review individually — don't mention reviews that are current. If a review directory is empty or missing, skip that review type entirely (don't flag a cadence the user hasn't started).

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

**If a catch-up fired in Step 2a this morning,** first run the off-Claude debrief that catch-up deferred. For each caught-up day, ask:
> "Before we move on — did you do anything off-Claude on [Day DD]? (exercise, errands, social, admin) It won't have been captured at close-out."

Route any answer through the Step 5 Capture Gate's off-Claude category — it back-fills the `## Outside-Claude` section into that day's daily report. Then ask the normal open-space question below.

Ask:
> "Anything you'd like to add this morning?"

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
   - **Off-Claude activity from a caught-up day** (only if Step 2a fired this morning — wander/exercise/social/admin/errands done outside the assistant on a day that was caught up) → Insert an `## Outside-Claude` section into the caught-up day's daily report at `{VAULT}/06 Archive/Claude/Daily Reports/YYYY-MM-DD.md`, between `## Sessions` (or `## Today's Plan` if no Sessions) and `## Blockers` (or `---` links footer if no Blockers). 2a scans up to 3 days back, so target the report for the specific day the user names (e.g. "Tuesday's wander" → YYYY-MM-DD for that Tuesday). If the user surfaced activity but didn't specify which day and 2a caught up >1 day, ask before writing. This is the Step 2a back-fill — 2a deliberately omitted the section because no debrief prompt fires during 2a itself; Step 4 runs it and routes the answer here. Without this back-fill, off-Claude activity from a missed-goodnight day reaches this morning's capture but never the archival daily report.
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

**Item linking:** Every item in a day section or Tasks.md should link to its project/area context where one exists:
- Project doc exists → `→ [[03 Projects/Project Name]]`
- Area doc exists → `→ [[04 Areas/path/doc]]`
- No dedicated doc but tracked in WIP → `→ [[01 Now/Works in Progress#Heading]]`
- Standalone/generic items (no project context) → no link
When moving items that already have project/area links, preserve them. Replace session log links with project/area links (session context is low-value once the item is in a planning doc).

Pull items from:
- Items carried forward from stale This Week.md (if any, noted in step 3)
- Time-sensitive items and appointments
- WIP project docs (follow **Next:** links to project pages for task queues)
- Items /goodnight routed into today's day section or Tasks.md last night
- Today's items already in This Week.md (migrated from Tickler in steps 3/6)
- Anything the user mentioned in step 4

**Move, not copy.** When an item from Tasks.md is scheduled into today's timeline, delete it from Tasks.md. The day section becomes SSOT for that item. If the item doesn't get done, /goodnight routes it back to Tasks.md or a future day — but it must never exist in both places simultaneously.

Completed items get `[x]` in the timeline (standard Obsidian checkbox: `- [x] Task`).

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
- **Capture means file writes:** If something comes up, write it to the right place (WIP, project, journal, Tickler) immediately. Don't just discuss routing — do the routing. Don't create new systems or files when an existing one fits.
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

- **Reads from:** Works in Progress, This Week.md (date-range freshness + tickler migration), Tickler, Direction (disciplines reminder), recent Claude Sessions, Daily Reports, Weekly Reviews (staleness), Quarterly Reviews (staleness), Open-Meteo API (weather forecast)
- **May create/update:** This Week.md (weekly plan with day sections)
- **May update:** Works in Progress, Tickler (mark items done or reschedule), Journal, Project files, previous day's Daily Report (post-goodnight reconciliation), `07 System/AI Provenance Log.md` + `07 System/Provenance/pending/` flags (catch-up provenance processing, step 2a.h)
- **Complements:** `/park` (end of session), `/goodnight` (end of day), `/afternoon` (mid-day)
- **Doesn't replace:** Morning pages / journaling (that's separate generative practice)
