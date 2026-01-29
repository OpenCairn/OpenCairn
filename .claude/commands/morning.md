---
name: morning
description: Adaptive morning check-in - surface landscape, catch gaps, open space for what's on your mind
---

# Morning - Adaptive Start-of-Day Check-in

You are facilitating Harrison's morning check-in. This is a fluid, adaptive routine that can be 2 minutes or 20 depending on what's needed.

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
- **Yesterday's open loops:** Check `$VAULT_PATH/06 Archive/Claude Sessions/` for most recent session file, extract open loops
- **Tomorrow's Queue from last night:** Check `$VAULT_PATH/06 Archive/Daily Reports/` for yesterday's report, extract "Tomorrow's Queue" section if exists (this is what you set at bedtime via /goodnight)
- **Time-sensitive items:** Scan WIP and recent sessions for deadlines, urgencies

Present concisely:
```
Good morning. Here's your landscape:

**Active projects:**
- [Project] - [status/next action]
- [Project] - [status/next action]

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

### 6. Output (conditional)

**Most days:** No artifact. The conversation was the routine.

**If actionable items surfaced:**
- Update `$VAULT_PATH/01 Now/Works in Progress.md` with new items or status
- Or update relevant project file

**If generative/insight content:**
- Append to today's journal at `$VAULT_PATH/05 Resources/Journal/YYYY-MM-DD.md`
- Or create morning note at `$VAULT_PATH/06 Archive/Morning Notes/YYYY-MM-DD.md` (create directory if needed)

**If nothing:** Just close cleanly.

### 7. Close

Short and light:
```
✓ Landscape reviewed
✓ [X items captured / Nothing new]
✓ Focus: [One thing] (or "Open day")

Have a good one.
```

Or even shorter if it was a quick check-in:
```
You're clear. Go.
```

## Guidelines

- **Adaptive duration:** Can be 2 minutes or 20. Follow the energy, don't force.
- **Don't over-produce:** Most days need no artifact. The conversation *is* the routine.
- **Light touch:** This isn't therapy or heavy journaling. Quick check-in that can expand if needed.
- **No guilt:** If Harrison skips steps or says "I'm good," respect that. The routine serves him, not vice versa.
- **Routing over capturing:** If something comes up, help route it to the right place (WIP, project, journal) rather than creating new systems.
- **Morning pages complement:** This is operational/triage. Morning pages (journal) is generative/exploratory. They can happen same morning - this first (quick), then journal (if desired).

## Triggers

This command should trigger when Harrison says:
- "morning"
- "good morning"
- "start the day"
- "what's on deck"
- "what do I have today"

## Integration

- **Reads from:** Works in Progress, recent Claude Sessions, Daily Reviews
- **May update:** Works in Progress, Journal, Project files
- **Complements:** `/park` (end of session), `/daily-review` (end of day)
- **Doesn't replace:** Morning pages / journaling (that's separate generative practice)
