---
name: start-project
description: Spin up a new project - create file, add to WIP, link to cornerstone
parameters:
  - "[Project Name]" - Name of the project to create
  - "--cornerstone=[Name]" - Link to existing cornerstone project (optional)
  - "--backlog" - Create in Backlog folder instead of active
---

# Start Project - New Project Initialisation

You are helping the user spin up a new project. This command creates the project file, adds it to Works in Progress, and optionally links it to a cornerstone project.

## Philosophy

Projects should be explicit from the start. Creating a project properly:
- Forces clarity on what "done" looks like
- Makes the commitment visible in Works in Progress
- Links to broader context if part of a cornerstone
- Creates the session linkage from day one

**Cornerstones vs Projects:**
- **Cornerstone:** Large, multi-week or multi-month initiative (e.g., "Travel 2026", "Working Memory Consolidation")
- **Project:** Discrete deliverable, often part of a cornerstone (e.g., "Task System Consolidation" under "Working Memory Consolidation")

## Instructions

### 1. Check current date/time

```bash
date +"%Y-%m-%d"
date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'
```

### 2. Gather project details

If project name not provided as parameter, ask:
> "What's the name of the project?"

Then ask:
> "What does 'done' look like for this project? (One sentence or a few bullet points)"

Ask for deadline/target (optional):
> "Any deadline or target date? (Leave blank if open-ended)"

Ask about cornerstone linkage:
> "Is this part of a larger initiative? (e.g., 'Travel 2026', 'Working Memory Consolidation')"

### 3. Check for conflicts

- Check if `03 Projects/[Project Name].md` already exists
- Check if `03 Projects/Backlog/[Project Name].md` already exists
- If exists, warn and ask if they want to:
  - Resume existing project
  - Create with different name
  - Abort

### 4. Create project file

Create at `03 Projects/[Project Name].md` (or `Backlog/` if `--backlog`):

```markdown
# [Project Name]

**Status:** Active | **Target:** [Deadline or "Open-ended"]
**Created:** [Date]
**Cornerstone:** [[03 Projects/[Cornerstone Name]]] (if applicable)

---

## Goal

[Done state from step 2]

---

## Current Status

Project initialised.

**Last update:** [Date] - Created

---

## Next Actions

- [ ] [First obvious next step, or "Define first action"]

---

## Resources

<!-- Link to related files:
- [[05 Resources/[Project Name]/...]]
-->

---

## Notes

[Any initial context captured during creation]

---

## Session History

- [[06 Archive/Claude Sessions/YYYY-MM-DD#Session N - [Topic]]] (created)
```

### 5. Update Works in Progress

Read `01 Now/Works in Progress.md`

Add to **Active** section (or appropriate priority section if specified):

```markdown
### [Project Name]
**Status:** Just started
**Created:** [Date]
**Next:** [First next action]
→ [[03 Projects/[Project Name]]]
```

If part of a cornerstone, add under that cornerstone's section instead (if it exists in WIP).

Update "Last updated" timestamp.

### 6. Link from cornerstone (if applicable)

If cornerstone specified:
- Read cornerstone file at `03 Projects/[Cornerstone Name].md`
- Add link to new project in appropriate section:
  ```markdown
  - [[03 Projects/[Project Name]]] - [brief description]
  ```

### 7. Create resources folder (optional)

Ask:
> "Create a resources folder at `05 Resources/[Project Name]/`? (y/n)"

If yes:
```bash
mkdir -p "05 Resources/[Project Name]"
```

### 8. Display confirmation

```
✓ Project created: 03 Projects/[Project Name].md
✓ Added to Works in Progress
✓ Linked from cornerstone: [Cornerstone Name] (if applicable)
✓ Resources folder created: 05 Resources/[Project Name]/ (if applicable)

Project ready. What's the first action?
```

## Guidelines

- **Explicit > implicit:** Creating a project forces clarity on scope and done-state
- **Cornerstones are optional:** Many projects stand alone
- **Backlog = not yet started:** Use `--backlog` for ideas not ready to pursue
- **Minimal ceremony:** Don't over-engineer the project file - it grows organically
- **Done-state is key:** "What does done look like?" prevents scope creep
- **Link early:** Session history section creates searchable project thread from day one
- **Resources folder optional:** Only create if project will have associated files

## When to Use This Command

**Use when:**
- Starting a new discrete body of work
- Splitting a cornerstone into concrete projects
- Capturing an idea that deserves tracking (use `--backlog`)
- Work that will span multiple sessions

**Don't use when:**
- Quick task (just add to Working Memory or WIP quick wins)
- Existing project already covers this work
- Area maintenance (belongs in `04 Areas/`, not a project)

If unsure whether something is a project or a task: if it needs multiple sessions and has a clear "done", it's a project.

## Integration

- **Works in Progress:** Project appears in Active (or Backlog)
- **Cornerstones:** Linked bidirectionally for navigation
- **Session summaries:** Session History section captures all work
- **complete-project:** Eventual counterpart to archive when done

## Example Flow

```
User: /start-project "Task System Consolidation"

You: What does 'done' look like for this project?

User: TickTick and Vikunja fully triaged, all tasks routed to vault or deleted, both apps empty or archived.

You: Any deadline or target date?

User: Mon 26 Jan - Australia Day, have the time

You: Is this part of a larger initiative?

User: Yes, Working Memory Consolidation

You:
✓ Project created: 03 Projects/Task System Consolidation.md
✓ Added to Works in Progress
✓ Linked from cornerstone: Working Memory Consolidation

Project ready. What's the first action?

User: Export TickTick to CSV

You: Added "Export TickTick to CSV" as first next action.
```

This creates explicit project tracking from the first moment of work.
