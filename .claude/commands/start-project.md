---
name: start-project
description: Spin up a new project - create file, add to WIP, link to initiative
argument-hint: "[Project Name] [--initiative=Name] [--backlog]"
---

# Start Project - New Project Initialisation

You are helping the user spin up a new project. This command creates the project file, adds it to Works in Progress, and optionally links it to an initiative project.

## Philosophy

Projects should be explicit from the start. Creating a project properly:
- Forces clarity on what "done" looks like
- Makes the commitment visible in Works in Progress
- Links to broader context if part of an initiative
- Creates the session linkage from day one

**Initiatives vs Projects:**
- **Initiative:** Large, multi-week or multi-month effort that contains multiple projects (e.g., "Summer Vacation", "Working Memory Consolidation")
- **Project:** Discrete deliverable, often part of an initiative (e.g., "Task System Consolidation" under "Working Memory Consolidation")

## Instructions

### 0. Resolve Vault Path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

### 1. Check current date/time

```bash
date +"%Y-%m-%d"
date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'
```

### 2. Gather project details

If project name not provided as parameter, ask:
> "What's the name of the project?"

**Run Step 3's conflict check now, as soon as the name is known** — before spending the user's time on the remaining questions. A collision may change the name or abort the run, which makes every answer gathered first a wasted interaction.

Then ask:
> "What does 'done' look like for this project? (One sentence or a few bullet points)"

Ask for deadline/target (optional):
> "Any deadline or target date? (Leave blank if open-ended)"

Ask about initiative linkage — **skip this question if `--initiative=Name` was passed**, and use that value:
> "Is this part of a larger initiative? (e.g., 'Summer Vacation', 'Working Memory Consolidation')"

### 3. Check for conflicts

- Check if `{VAULT}/03 Projects/[Project Name].md` already exists
- Check if `{VAULT}/03 Projects/Backlog/[Project Name].md` already exists
- Check if `{VAULT}/03 Projects/Cold/[Project Name].md` already exists
- Glob the vault for any other `[Project Name].md` — a completed project of the same name may live in `04 Areas/` or `06 Archive/Projects/`, and a basename collision breaks the basename wikilinks other skills write (e.g. `/complete-project`'s completion record). Warn on any hit.
- Check for a duplicate `### [Project Name]` heading in `{VAULT}/01 Now/Works in Progress.md`. A second identical heading breaks `_shared-rules.md` §6's FIFO awk (it stops at the first `### `) and `/pickup`'s per-`###` parse — a file-level check alone won't catch it.
- If exists, warn and ask if they want to:
  - Resume existing project
  - Create with different name
  - **Finish a half-done creation** — hub file exists but no WIP entry (or vice versa), the signature of an earlier run that failed partway. Create only the missing artefacts; don't rewrite what's there.
  - Abort

### 4. Create project file

Create at `{VAULT}/03 Projects/[Project Name].md` (or `Backlog/` if `--backlog`). Under `--backlog`, `mkdir -p "{VAULT}/03 Projects/Backlog"` first — the folder is a library-wide convention but is not guaranteed to exist in a fresh vault:

Omit the `**Initiative:**` line entirely when there's no initiative — don't write the words "(if applicable)" into the file.

```markdown
# [Project Name]

**Status:** Active | **Target:** [Deadline or "Open-ended"]     <!-- `Backlog` under --backlog: the Status must match the folder tier, or /weekly-hygiene flags a tier mismatch -->
**Created:** [Date]
**Initiative:** [[03 Projects/[Initiative Name]]]

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

<!-- /park appends session links here -->
```

Leave Session History empty apart from the comment — `/park` is the writer (it appends the session link there when it runs — see `park.md` for the exact format, which this file must not restate and let drift). Seeding a link at creation time means fabricating the session number and topic before `/park` has assigned them: a guaranteed-dangling link in a different anchor format. The `## Session History` heading itself is load-bearing — `/park` appends only where it exists.

### 5. Update Works in Progress

**Write mechanism (F1):** WIP edits use `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5). To insert the entry, `--replace` the target section's heading line with the heading followed by the new entry — `--append` lands at EOF, not in the section.

Read `{VAULT}/01 Now/Works in Progress.md`

Add to the **Active** section — or the **Backlog** section if `--backlog` (the WIP section must match the file's folder tier; a Backlog-folder file listed under Active is a tier mismatch `/weekly-hygiene` flags):

```markdown
### [Project Name]
**Status:** Just started
**Last:** [Date] - Created
**Next:** → [[03 Projects/[Project Name]]]
```

Use the file's **actual path** in the `**Next:**` link — `[[03 Projects/Backlog/[Project Name]]]` when `--backlog` (`/pickup` follows this link to load the hub; the root form dangles).

Every project gets its own `###` entry. Initiative membership is carried by the template's `**Initiative:**` field and the Step 6 backlink — never by nesting the entry under the initiative's WIP section, which makes it invisible to `/pickup`'s per-`###` parse.

Update the `**Last updated:**` timestamp, matching the file's existing format — `date +"%Y-%m-%d %H:%M %Z"`. Per `_shared-rules.md` §19 the `date` result must come from a *prior* tool call; a value composed in the same call as the write is an estimate, not a clock read.

### 6. Link from initiative (if applicable)

If initiative specified:
- **Write mechanism (F1):** initiative hubs live in `03 Projects/` — edit via `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5)
- Read initiative file at `{VAULT}/03 Projects/[Initiative Name].md`
- Add link to new project in appropriate section, using the file's actual path (`Backlog/` form if `--backlog`):
  ```markdown
  - [[03 Projects/[Project Name]]] - [brief description]
  ```

### 7. Create resources folder (optional)

Ask:
> "Create a resources folder at `05 Resources/[Project Name]/`? (y/n)"

If yes:
```bash
if [ -d "{VAULT}/05 Resources/[Project Name]" ]; then echo "existed"; else mkdir -p "{VAULT}/05 Resources/[Project Name]" && echo "created"; fi
```

Report whichever the test returned in Step 8 — `mkdir -p` silently adopts a colliding topic folder, so an unconditional "✓ created" can claim a folder this run didn't make. Then **uncomment the hub's `## Resources` link** to point at the folder; left commented, nothing links it and the folder is orphaned.

### 8. Display confirmation

```
✓ Project created: [actual file path — 03 Projects/[Project Name].md, or Backlog/ form]
✓ Added to Works in Progress ([Active / Backlog] section)
[✓ Linked from initiative: [Initiative Name] — omit this line entirely when there's no initiative]
[✓ Resources folder created: 05 Resources/[Project Name]/ | ✓ Resources folder already existed: … — whichever the Step 7 test returned]

Project ready. What's the first action?
```

## Guidelines

- **Explicit > implicit:** Creating a project forces clarity on scope and done-state
- **Initiatives are optional:** Many projects stand alone
- **Backlog = not yet started:** Use `--backlog` for ideas not ready to pursue
- **Minimal ceremony:** Don't over-engineer the project file - it grows organically
- **Done-state is key:** "What does done look like?" prevents scope creep
- **Link early:** Session history section creates searchable project thread from day one
- **Resources folder optional:** Only create if project will have associated files

## When to Use This Command

**Use when:**
- Starting a new discrete body of work
- Splitting an initiative into concrete projects
- Capturing an idea that deserves tracking (use `--backlog`)
- Work that will span multiple sessions

**Don't use when:**
- Quick task (just add to Working Memory or WIP quick wins)
- Existing project already covers this work
- Area maintenance (belongs in `04 Areas/`, not a project)

If unsure whether something is a project or a task: if it needs multiple sessions and has a clear "done", it's a project.

## Integration

- **Works in Progress:** Project appears in Active (or Backlog)
- **Initiatives:** Linked bidirectionally for navigation
- **Session summaries:** Session History section captures all work
- **complete-project:** Eventual counterpart to archive when done


