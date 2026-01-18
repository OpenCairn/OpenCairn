# Context Navigation for Claude Code

*How Claude should navigate this vault to find relevant information*

---

## The Core Pattern: Hierarchical Lazy Loading

Don't read everything upfront. Navigate just-in-time through increasing specificity:

```
Tier 1: CLAUDE.md (orientation - always loaded)
  ↓
Tier 2: Hub files in 07 System (domain indexes - load when relevant)
  ↓
Tier 3: Detailed pages in Projects/Areas (specific info - follow links)
  ↓
Tier 4: Related files (chase further links when needed)
```

This is like navigating a city. You don't need the entire map in working memory - just which turns to make next.

---

## When to Navigate Deeper

Read more context when:

- User asks about a specific domain → Read the hub file for that domain
- Task requires understanding preferences → Follow links to detailed pages
- Need to understand existing structure → Explore related files
- **When uncertain, read more** → Better too much context than wrong assumptions

## When to Stop

Stop navigating when:

- You've read the relevant hub file and 2-3 linked detail pages
- Further reading is clearly tangential to the task
- You're starting to read archive files or distant connections

---

## Navigation Patterns

### Pattern 1: Domain Question
User asks about photography, health, career, etc.

1. Read CLAUDE.md (already loaded)
2. Find relevant hub file: `07 System/Context - [Domain].md`
3. Read the hub file
4. Follow links to specific pages as needed

### Pattern 2: Project Work
User wants to work on a specific project.

1. Read CLAUDE.md
2. Read `01 Now/Works in Progress.md` for current status
3. Read the project hub page in `03 Projects/`
4. Read linked resource files as needed

### Pattern 3: Research/Discovery
User wants to find something in the vault.

1. Start with CLAUDE.md for orientation
2. Use Grep/Glob to search for relevant terms
3. Read promising files
4. Follow internal links to related content

### Pattern 4: Session Continuation
User is picking up previous work.

1. `/pickup` command loads the session context
2. Read the linked project file
3. Read any files mentioned in "Files Updated"
4. Continue from "Resume Context"

---

## Anti-Patterns to Avoid

- **Loading everything upfront** - Don't Glob all files and read all matches
- **Guessing file locations** - Read hub files to find where things are
- **Stopping too early** - Skimming CLAUDE.md without following links
- **Ignoring links** - Hub files contain explicit links for a reason
- **Making assumptions** - When uncertain, read more context

---

## Token Cost vs Correctness

Context consumption costs tokens, but:

**Incorrect answers from insufficient context cost more** - in user time, in rework, in frustration.

When uncertain, bias toward reading more rather than less.

---

## File Types

This vault contains mixed file types in the same folders:
- `.md` - Markdown notes (primary)
- `.pdf` - Documents, papers, receipts
- `.jpg/.png` - Images, screenshots, diagrams

Files are organised by topic, not by filetype. A Travel folder contains the itinerary (md), booking confirmation (pdf), and destination photos (jpg) together.

Claude can read all these formats. Treat them as unified context.
