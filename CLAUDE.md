# [Your Name] - Claude Code Context

<!--
This file is read by Claude Code at the start of every session.
It's your persistent context - who you are, how you think, what you're working on.

INSTRUCTIONS:
1. Replace all [bracketed placeholders] with your actual information
2. Delete sections that don't apply to you
3. Add sections for domains specific to your life
4. Keep it updated as your situation changes

The goal: Claude should understand you well enough to give relevant,
personalised responses without you re-explaining context every session.
-->

## Who I Am

[Your name], [age]. [Brief description of your profession/life stage.]

[1-2 sentences about what you're primarily working on or focused on right now.]

## How I Think

<!-- Help Claude understand your mental models and decision-making style -->

[Describe your thinking style. Are you analytical? Creative? Systems-oriented?
What frameworks or mental models do you use? What's your bias - toward action
or toward deliberation?]

## Communication Preferences

- **Locale:** [e.g., en_GB.UTF-8, TZ=Europe/London] *(Commands use this for spelling localisation: en_AU/en_GB → British spelling, en_US → American spelling)*
- **Evidence-based:** [Do you want to understand the "why" or just follow instructions?]
- **Technical depth:** [Comfortable with complexity? Prefer simplified explanations?]
- **Pushback:** [Do you want Claude to challenge your ideas or mostly agree?]

<!-- Add any other communication preferences that matter to you -->

## Key Context Files

<!-- List the hub files Claude should read for different domains -->

**Start here:** `01 Now/Works in Progress.md` - what's actively in flight
**This Week:** `01 Now/This Week.md` - rolling 7-day plan with time-blocked days (refreshed each morning)
**Direction:** `07 System/Context - Direction.md` - values, strategic plans, anti-goals, disciplines

For deeper context on specific domains:
- **[Domain A]:** `07 System/Context - [Domain A].md`
- **[Domain B]:** `07 System/Context - [Domain B].md`

<!-- Add more as you create hub files for your domains -->

## Context Navigation Philosophy

**Hierarchical lazy loading** - Claude doesn't read everything upfront. Navigate just-in-time through increasing specificity:

1. **CLAUDE.md** (this file) - orientation, where to look for what
2. **07 System hub files** - high-level summaries with links to detailed pages
3. **Detailed pages** - follow links as needed for specific information

Read `07 System/README - Context Navigation.md` for implementation details.

## File Organisation Rules

### Never Separate Files by Filetype

Files belong together by *topic/purpose*, not by technical format. A folder contains ALL related files regardless of extension.

**Wrong:**
```
Resources/
├── Documents/Travel/booking.pdf
├── Notes/Travel/itinerary.md
├── Images/Travel/map.png
```

**Right:**
```
Resources/
└── Travel/
    ├── booking.pdf
    ├── itinerary.md
    └── map.png
```

### No Checkboxes in Dashboard Files

`01 Now/Works in Progress.md` is a **dashboard**, not a task SSOT. Never use `- [ ]` checkboxes in this file — the canonical checkbox lives in the relevant Project page, Area file, or Tickler. Dashboard files should reference or summarise tasks, not duplicate their completion state.

**Exception:** WIP entries that have no corresponding Project page or Area folder may use checkboxes, since they have no other SSOT.

### Tickler SSOT Transfer

Tickler is a time-deferred queue, not a persistent SSOT. When items are pulled from Tickler into a planning document (a weekly plan, project page, etc.), **the planning document becomes SSOT** for those items. Delete the Tickler copy immediately to prevent duplicate checkboxes across the vault. The Tickler's job is done once the item surfaces and lands in a plan.

## Path-Keyed Memories

Claude Code stores memories and corrections in `~/.claude/projects/` keyed to the absolute path of the directory you run it from. If you move your vault to a different path, memories will appear to be lost. They're still at the old path — copy the `.md` files from `~/.claude/projects/<old-path>/memory/` to `~/.claude/projects/<new-path>/memory/` to recover them.

## Session Management

**At session end:** Use `/park` or cue words like "wrapping up", "done for now", "packing up"

This will:
- Write session summary to `06 Archive/Claude/Session Logs/YYYY-MM-DD.md`
- Document open loops (so you can rest knowing everything is captured)
- Enable frictionless resume next session

**To resume:** Run `/pickup` to load your current landscape, or just start talking and link relevant files

## Working With Me

<!-- Customise these to match your preferences -->

- **Prioritise truth over comfort.** I want accurate information and honest pushback, not validation.
- **Long-term goals over short-term pleasures.** Help me stay aligned with what I actually want.
- [Add your own principles here]

## Verification

<!-- Universal default, not a placeholder — applies whoever you are.
Reword to taste, but keep the intent: check before you assert. -->

Default to checking over asserting. Training data is stale and memory is
fallible; the user's words, current tool output, and primary sources outrank
any context doc, which is only ever a stale model of the world.

- **Check before claiming.** Before asserting a falsifiable fact the answer
  turns on — current state (a file's contents, whether a service is up, a tool
  installed, a thing booked), a date, or a decision-driving figure (a dose, a
  rate, a deadline, a spec) — confirm it (read the file, run a command, search)
  rather than answering from memory or a context doc. General knowledge and
  definitions don't need a tool. If the source you'd check is unavailable, say
  so and qualify the answer rather than asserting anyway.
- **Never fabricate a specific value you weren't given.** When an edit needs a
  concrete date, amount, count, name, or ID and it isn't in the user's words or
  a tool result from this session, don't supply a plausible default; omit it or
  ask. The trap is the convenient assumption: "paid the deposit" quietly
  becoming "paid on today's date" invents a fact.
- **Say "I don't know" before confabulating.** When you lack the evidence to
  explain something, lead with the uncertainty instead of inventing a plausible
  story that doesn't fit the facts. If successive explanations keep getting shot
  down, stop and say you don't know.
- **Artefact metadata is not reality.** Filenames, status labels, folder names,
  and draft tags describe the artefact, not the world. "Researched hotel" isn't
  a booking; "Draft - X" isn't unsent; a log dated 14 to 16 April isn't proof a
  trip happened then. Confirm against the actual content, a tool, or the user
  before treating a label as the fact it implies.
