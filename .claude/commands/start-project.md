---
name: start-project
description: Spin up a new project - create the project doc in 03 Projects, link to initiative
argument-hint: "[Project Name] [--initiative=Name] [--backlog]"
---

# Start Project - New Project Initialisation

You are helping the user spin up a new project. This command creates the project doc in `03 Projects/` — folder location IS status (root = active, `Backlog/` = backlog), so creating the doc there is the whole registration — and optionally links it to an initiative project.

## Philosophy

Projects should be explicit from the start. Creating a project properly:
- Forces clarity on what "done" looks like
- Makes the commitment visible in the `03 Projects/` root
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

Ask which bucket it belongs to (one line — the doc's `bucket:` frontmatter, which /morning groups the landscape by):
> "Which bucket?" (offer the vault's taxonomy — Project Doc Format in `07 System/Vault Organisation Principles.md`)

Ask for deadline/target (optional):
> "Any deadline or target date? (Leave blank if open-ended)"

Ask about initiative linkage — **skip this question if `--initiative=Name` was passed**, and use that value:
> "Is this part of a larger initiative? (e.g., 'Summer Vacation', 'Working Memory Consolidation')"

### 3. Check for conflicts

- Check if `{VAULT}/03 Projects/[Project Name].md` already exists
- Check if `{VAULT}/03 Projects/Backlog/[Project Name].md` already exists
- Check if `{VAULT}/03 Projects/Cold/[Project Name].md` already exists
- Glob the vault for any other `[Project Name].md` — a completed project of the same name may live in `04 Areas/.../Archive/` or `06 Archive/`, and a basename collision breaks basename wikilinks elsewhere in the vault. Warn on any hit.
- If exists, warn and ask if they want to:
  - Resume existing project
  - Create with different name
  - **Finish a half-done creation** — hub file exists but the initiative backlink or resources folder is missing, the signature of an earlier run that failed partway. Create only the missing artefacts; don't rewrite what's there.
  - Abort

### 4. Create project file

Create at `{VAULT}/03 Projects/[Project Name].md` (or `Backlog/` if `--backlog`). Under `--backlog`, `mkdir -p "{VAULT}/03 Projects/Backlog"` first — the folder is a library-wide convention but is not guaranteed to exist in a fresh vault:

**Write mechanism:** this step **creates** a file, so it uses `Write`, not `locked-edit.sh`. Per `_shared-rules.md` §5, the lock governs mutation of existing content; there is no read-modify-write cycle to lose here. Duplicate-creation safety is Step 3's collision check, not the lock's — the lock would serialise two racing creates and report success for both. Steps that mutate an initiative hub later in this skill are mutations and **do** go through `locked-edit.sh`.

Omit the `**Initiative:**` line entirely when there's no initiative — don't write the words "(if applicable)" into the file.

```markdown
---
bucket: [bucket from step 2]
---

# [Project Name]

**Created:** [Date]
**Initiative:** [[03 Projects/[Initiative Name]]]

---

## Goal

[Done state from step 2]

---

## Current Objective

[First milestone toward the goal — or the goal restated, if it's one push]

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

### 5. Root-cap check

Creating the doc in the `03 Projects/` root IS the registration — folder location is status (root = active, `Cold/` = paused, `Backlog/` = backlog); there is no separate index or dashboard to update.

After creating (skip under `--backlog`), count the root:

```bash
ls "{VAULT}/03 Projects/"*.md 2>/dev/null | wc -l
```

If the count exceeds the **active project cap** (resolve it first: `grep -F '**Active project cap:'` over `{VAULT}/07 System/Vault Organisation Principles.md` → *Project Doc Format*, and state the value found. **`-F` is required** — a leading `**` is a repetition operator to some greps, which error out instead of matching. Exit 1, or a line yielding no number, means state `cap line unreadable — using default 5` and proceed on 5, so a failed read is never mistaken for a vault that states no cap. **Any other non-zero exit is a tool error, not an absent line** — report it and stop, rather than falling through to the default, which is the failure this branch exists to prevent) — say so and suggest which existing root project looks most moveable to `03 Projects/Cold/` — the root is the active-attention set, and it only stays legible if it stays small. Note it for the user; don't move anything without their say-so.

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
✓ Registered by location: [03 Projects root (active) / Backlog] — folder is status
[⚠ Root count now N (cap M) — consider moving [candidate] to Cold — omit when at or under the cap, or under --backlog]
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
- Quick task (route to This Week or the Tickler — small items need no home doc)
- Existing project already covers this work
- Area maintenance (belongs in `04 Areas/`, not a project)

If unsure whether something is a project or a task: if it needs multiple sessions and has a clear "done", it's a project.

## Integration

- **03 Projects root:** the doc's folder is its status; /morning reads it into the landscape
- **Initiatives:** Linked bidirectionally for navigation
- **Session summaries:** Session History section captures all work
- **complete-project:** Eventual counterpart to route the doc out of the root when done


