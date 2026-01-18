# Vault Organisation Principles

*How this vault is structured and why*

---

## NIPARAS Structure

This vault uses a seven-folder structure called NIPARAS:

| Folder | Purpose | Examples |
|--------|---------|----------|
| **01 Now** | Active working memory, current focus | Works in Progress, Working memory scratch |
| **02 Inbox** | Capture point for new stuff | Quick notes, web clippings, ideas |
| **03 Projects** | Discrete sprints with end states | "Launch website", "Plan trip", "Learn X" |
| **04 Areas** | Ongoing responsibilities (no end date) | Health, Finances, Career, Relationships |
| **05 Resources** | Reference material | Saved articles, how-to guides, templates |
| **06 Archive** | Completed/inactive items | Old projects, session logs, historical notes |
| **07 System** | Meta-documentation | This file, context files, vault config |

### The Key Distinction: Projects vs Areas

**Projects** have an end state. You complete them and move on.
- "Write blog post about X" - project
- "Plan 2026 vacation" - project
- "Learn enough Python to automate Y" - project

**Areas** are ongoing responsibilities. They never end, only evolve.
- "Health" - area (you're always maintaining health)
- "Career" - area (even after retiring, it becomes "legacy")
- "Home" - area (always needs maintenance)

If you're confused about where something goes: Does it have a finish line? Project. Is it an ongoing concern? Area.

---

## Projects Are Pages, Not Folders

Each project is a **single hub page** in `03 Projects/`, not a folder full of files.

The hub page:
- Describes the project goal and current status
- Links to related files wherever they live
- Tracks progress and open loops

Related files live in `05 Resources/[Project Name]/` or wherever makes sense topically.

**Why?**
- One place to see project status (the hub page)
- Files organised by topic, not by project membership
- Easier to find things (fewer nested folders)
- Projects can share resources without duplication

---

## Never Separate Files by Filetype

This is an iron-clad rule. Files belong together by *topic/purpose*, not by technical format.

**Wrong:**
```
Documents/Travel/booking.pdf
Notes/Travel/itinerary.md
Images/Travel/map.png
```

**Right:**
```
Resources/Travel/
├── booking.pdf
├── itinerary.md
└── map.png
```

If files are related to the same thing, they live together regardless of whether they're `.md`, `.pdf`, `.jpg`, or anything else.

---

## Hub Files for Context

The `07 System/` folder contains "hub files" - high-level context documents that help Claude (and you) understand different domains of your life.

Format: `Context - [Domain].md`

Examples:
- `Context - Career.md` - your professional situation, goals, key relationships
- `Context - Health.md` - your health priorities, conditions, routines
- `Context - Photography.md` - your gear, style, current projects

Hub files are *indexes*, not encyclopedias. They contain:
- Overview of the domain
- Current status/priorities
- Links to detailed pages

Claude reads hub files to understand a domain, then follows links for specifics.

---

## Navigation Philosophy

See `README - Context Navigation.md` for how Claude navigates this vault.

The key insight: hierarchical lazy loading. Claude doesn't read everything upfront. It reads CLAUDE.md, then hub files as needed, then detailed pages.

Like navigating a city - you don't need the whole map in memory, just which turns to make.
