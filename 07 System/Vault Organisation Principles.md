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
| **04 Areas** | Domains of life (with nested resources) | Health, Finances, Photography, Worldview |
| **05 Resources** | Generic scrapbook, pre-emergence staging | Journal, recipes, screenshots, misc |
| **06 Archive** | Completed/inactive items | Old projects, session logs, historical notes |
| **07 System** | Meta-documentation | This file, context files, vault config |

### The Key Distinction: Projects vs Areas

**Projects** have an end state. You complete them and move on.
- "Write blog post about X" - project
- "Plan 2026 vacation" - project
- "Learn enough Python to automate Y" - project

**Areas** are domains of life you actively maintain. They never end, only evolve. Each Area contains its own nested resources - reference material lives with the domain it supports.
- "Health" - area (with nested folders for supplements, bloodwork, etc.)
- "Photography" - area (with nested portfolios, gear notes, learning materials)
- "Finances" - area (with nested tax docs, investment notes, etc.)

**Resources** is a staging ground for generic material that doesn't belong to a specific Area yet. When something accumulates enough mass or importance, it graduates to become an Area.

If you're confused about where something goes: Does it have a finish line? Project. Is it a domain of life? Area. Is it generic reference material? Resources.

---

## Projects Are Pages, Not Folders

Each project is a **single hub page** in `03 Projects/`, not a folder full of files.

The hub page:
- Describes the project goal and current status
- Links to related files wherever they live
- Tracks progress and open loops

Related files live in the relevant Area folder (e.g., travel files in `04 Areas/Travel/`) or in `05 Resources/` for project-specific material that doesn't belong to an Area.

**Backlog subfolder:** `03 Projects/Backlog/` contains project pages for items not yet active. These are real project pages (sessions can link to them), just not in play yet. When a backlog item becomes active, move the page up to `03 Projects/`. This keeps the main Projects folder uncluttered.

**Project lifecycle:**
```
Idea emerges     → 03 Projects/Backlog/Project Name.md
Becomes active   → 03 Projects/Project Name.md
Completes        → 06 Archive/Projects/YYYY/Project Name.md
```

**Project page threshold:** If it'll take more than one session, it gets a project page. Single-session tasks can live as WIP entries without a dedicated page.

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
