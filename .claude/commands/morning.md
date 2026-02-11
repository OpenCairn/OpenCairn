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
- **Stale Today.md:** Check `$VAULT_PATH/01 Now/Today.md` — if it exists, check the heading for a date. If the heading has no date (template placeholder) or a date that doesn't match today, it's stale. Note the uncompleted items in your working memory for step 6 (don't present a decision here — keep the landscape survey read-only). If the file is just the empty template, note it and move on.
- **Tickler items due:** Read `$VAULT_PATH/01 Now/Tickler.md` (skip if file doesn't exist), show any items where date header <= today (YYYY-MM-DD format). Flag overdue items (date < today). These are deferred tasks that have resurfaced.
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

### 3. Catch Gaps (quick prompt)

Ask:
> "Anything from yesterday that didn't get captured? Things you did or thought about that aren't in there?"

- If yes: capture briefly, ask where it should go (WIP, project file, just noted)
- If no: move on

### 4. Open Space (adaptive)

Ask:
> "What's on your mind this morning?"

**If "nothing" or minimal:** Move to step 5, keep it quick.

**If stuff comes up:** Let it flow. Don't rush. This is generative space.

After the dump, ask:
> "Any of that actionable, or just needed to be said?"

- **Actionable:** "Want to add that to WIP / a project / today's focus?"
- **Insight worth keeping:** "Want me to add that to your journal?"
- **Just venting:** "Got it. Acknowledged." (no artifact needed)

### 5. Set Intention (optional closer)

Ask:
> "What's your one thing for today? Or skip if you'd rather stay open."

- If they have one: note it, offer to add to WIP or just hold it
- If skip: that's fine, some days are exploratory

### 6. Build Today.md (optional artifact)

If the day has enough structure to benefit from a visual plan (appointments, time blocks, multiple tasks), offer:

> "Want me to build your Today.md?"

**If yes:**

First, if a stale Today.md exists (detected in step 2), show the uncompleted items and ask which to carry forward. This keeps all Today.md decisions in one place rather than splitting them across steps.

Then create/overwrite `$VAULT_PATH/01 Now/Today.md` using the timeline format.

Pull from everything surfaced so far:
- Items carried forward from stale Today.md (if any, user chose just above)
- Time-sensitive items and appointments mentioned
- WIP next actions
- Yesterday's queue (from /goodnight Daily Report)
- Tickler items due today
- The "one thing" from step 5
- Anything the user mentioned in steps 3-4

**Today.md format:**

1. **Heading** with today's date: `# Today — [Day] [DD] [Mon] [YYYY]`
2. **Timeline** — visual time-blocked schedule in a code block:
   - `██` = scheduled block with duration: `09:00 ██ Dentist (1h)`
   - `████████` = longer blocks use more block chars, roughly proportional to duration
   - `░░` = gap or open time: `░░ open — 90 min`
   - `▓▓` = tentative/pending: `?? ▓▓ Dinner with Sam (pending)`
   - `┊` = sub-items within a block: `┊ 15:15 Prep slides`
   - `┄┄` = day start/end boundaries
   - `LATE` = end-of-day items without fixed times
3. **Refs** — one-liner linking timeline items to project/area files via `[[wikilinks]]`
4. **Done today** — items move here with `✓` as they're completed
5. **Notes** — ad-hoc sections as needed (decision trees, context, reminders)

**If no or the day is unstructured:** Skip. Not every day needs a timeline. Open/exploratory days are fine without one. (A stale Today.md from yesterday may linger — that's harmless since `/afternoon` and `/goodnight` check dates before reading it.)

**Why this exists:** Today.md is a plain-text replacement for calendar reads/writes via MCP. Calendar API integrations are flaky and brittle. A markdown file is instant to read, trivial to edit mid-session, and always available — no API calls, no auth tokens, no rate limits.

### 7. Output (conditional)

**Most days with Today.md:** The Today.md file is the artifact. No additional output needed.

**If actionable items surfaced but no Today.md:**
- Update `$VAULT_PATH/01 Now/Works in Progress.md` with new items or status
- Or update relevant project file

**If generative/insight content:**
- Append to today's journal at `$VAULT_PATH/05 Resources/Journal/YYYY-MM-DD.md`
- Or create morning note at `$VAULT_PATH/06 Archive/Morning Notes/YYYY-MM-DD.md` (create directory if needed)

**If nothing:** Just close cleanly.

### 8. Close

Short and light:
```
✓ Landscape reviewed
✓ [X items captured / Nothing new]
✓ Today.md built (or "Open day — no plan needed")
✓ Focus: [One thing] (or "Open day")

Have a good one.
```

Or even shorter if it was a quick check-in:
```
You're clear. Go.
```

## Guidelines

- **Adaptive duration:** Can be 2 minutes or 20. Follow the energy, don't force.
- **Today.md is the artifact when needed:** For structured days, Today.md is the output. For open/exploratory days, the conversation itself is the routine — no file needed.
- **Light touch:** This isn't therapy or heavy journaling. Quick check-in that can expand if needed.
- **No guilt:** If the user skips steps or says "I'm good," respect that. The routine serves him, not vice versa.
- **Routing over capturing:** If something comes up, help route it to the right place (WIP, project, journal) rather than creating new systems.
- **Morning pages complement:** This is operational/triage. Morning pages (journal) is generative/exploratory. They can happen same morning - this first (quick), then journal (if desired).

## Triggers

This command should trigger when the user says:
- "morning"
- "good morning"
- "start the day"
- "what's on deck"
- "what do I have today"

## Integration

- **Reads from:** Works in Progress, Today.md (stale check), Tickler, recent Claude Sessions, Daily Reports
- **May create:** Today.md (daily plan)
- **May update:** Works in Progress, Tickler (mark items done or reschedule), Journal, Project files
- **Complements:** `/park` (end of session), `/goodnight` (end of day), `/afternoon` (mid-day)
- **Doesn't replace:** Morning pages / journaling (that's separate generative practice)
