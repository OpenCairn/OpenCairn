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

## Current Life Stage

<!-- What's happening in your life right now? Major transitions, projects, deadlines? -->

- **Current focus:** [What's consuming most of your attention?]
- **Upcoming:** [Any significant near-term events or deadlines?]
- **Context:** [Anything else Claude should know about your situation?]

## How I Think

<!-- Help Claude understand your mental models and decision-making style -->

[Describe your thinking style. Are you analytical? Creative? Systems-oriented?
What frameworks or mental models do you use? What's your bias - toward action
or toward deliberation?]

## Communication Preferences

- **Locale:** [e.g., en_AU.UTF-8, TZ=Australia/Brisbane]
- **Evidence-based:** [Do you want to understand the "why" or just follow instructions?]
- **Technical depth:** [Comfortable with complexity? Prefer simplified explanations?]
- **Pushback:** [Do you want Claude to challenge your ideas or mostly agree?]

<!-- Add any other communication preferences that matter to you -->

## Key Context Files

<!-- List the hub files Claude should read for different domains -->

**Start here:** `01 Now/Works in Progress.md` - what's actively in flight
**Today:** `01 Now/Today.md` - today's time-blocked plan (refreshed each morning)

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

## Path-Keyed Memories

Claude Code stores memories and corrections in `~/.claude/projects/` keyed to the absolute path of the directory you run it from. If you move your vault to a different path, memories will appear to be lost. They're still at the old path — copy the `.md` files from `~/.claude/projects/<old-path>/memory/` to `~/.claude/projects/<new-path>/memory/` to recover them.

## Session Management

**At session end:** Use `/park` or cue words like "wrapping up", "done for now", "packing up"

This will:
- Write session summary to `06 Archive/Claude Sessions/YYYY-MM-DD.md`
- Document open loops (so you can rest knowing everything is captured)
- Enable frictionless resume next session

**To resume:** Run `/pickup` to see recent sessions and select one to continue

## Working With Me

<!-- Customise these to match your preferences -->

- **Prioritise truth over comfort.** I want accurate information and honest pushback, not validation.
- **Long-term goals over short-term pleasures.** Help me stay aligned with what I actually want.
- [Add your own principles here]
