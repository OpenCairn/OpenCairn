---
name: complete-project
description: Explicitly complete and archive a project - prevents zombie projects lingering in Works in Progress
---

# Complete Project - Formal Project Completion

You are helping the user formally complete a project. This command prevents "zombie projects" that linger in Works in Progress long after they're effectively done.

## Philosophy

Projects often fade away rather than explicitly complete. This creates clutter in Works in Progress and uncertainty ("Am I still doing this? Should I be?"). Explicit completion:
- Provides psychological closure
- Documents outcomes for future reference
- Keeps Works in Progress accurate
- Allows celebration of completion

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `.claude/commands/_shared-rules.md` and apply its rules throughout this command. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current time: `date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'`
   - Store for metadata

2. **Identify project to complete:**
   - Read `{VAULT}/01 Now/Works in Progress.md`
   - Display list of Active projects
   - If project name provided as parameter: Use that
   - Otherwise: Ask the user which project to complete
   - Validate project exists in Active section

3. **Interactive completion interview:**
   Ask the user:
   - **Outcome:** "How did this project end? (Completed successfully / Abandoned / Superseded / Merged into other work)"
   - **Result:** "What was accomplished or learned?"
   - **Why now:** "Why are you completing this now?" (helps catch premature completion)
   - **Archive location:** "Where should the project file be archived?" (suggest: `06 Archive/Projects/YYYY/`)

4. **Update project file:**
   - Find project file (check both locations):
     - `{VAULT}/03 Projects/[Project Name].md` (active projects)
     - `{VAULT}/03 Projects/Backlog/[Project Name].md` (backlog projects)
   - Add completion section at top:
     ```markdown
     **Status:** COMPLETED ([Date])
     **Outcome:** [Completed successfully / Abandoned / etc.]
     **Result:** [What was accomplished]

     ---
     ```
   - This preserves project history while marking completion

5. **Move project file to archive:**
   - Determine archive destination based on ownership:
     - **Area-owned project** (belongs to a specific domain): `04 Areas/[Area]/Archive/[Project Name].md`
     - **Cross-cutting project** (no single area): `06 Archive/Projects/YYYY/[Project Name].md`
   - If unsure, ask: "Does this project belong to a specific area (Health, Photography, etc.), or is it cross-cutting?"
   - Create archive directory if needed: `mkdir -p "{VAULT}/[chosen archive path]"`
   - Move file from wherever it was found:
     - From `03 Projects/[Project Name].md` → chosen archive path
     - From `03 Projects/Backlog/[Project Name].md` → chosen archive path
   - Update any resource folders similarly

6. **Update Works in Progress:**
   - Read `{VAULT}/01 Now/Works in Progress.md`
   - Remove project from its current section (Active, Maintenance, Backlog, etc.)
   - Update "Last updated" timestamp

7. **Create completion record in session file:**
   - If current session file exists for today, append brief note:
     ```markdown
     ---
     **Project Completed:** [[06 Archive/Projects/YYYY/Project Name]]
     **Outcome:** [Result]
     **Date:** [Date and time]
     ---
     ```
   - This creates searchable record of when project was completed

8. **Display confirmation:**

```
✓ Project completed: [Project Name]
✓ Outcome: [Completed successfully / etc.]
✓ Project file moved to: 06 Archive/Projects/YYYY/[Project Name].md
✓ Works in Progress updated
✓ Completion recorded in today's session

Project completion complete. Well done.
```

## Guidelines

- **Explicit completion prevents drift:** Projects often fade rather than explicitly end - this forces a decision
- **Completion ≠ success:** Abandoned projects are valid completions. Acknowledging abandonment is better than indefinite limbo.
- **Outcomes:** Be honest - "Completed successfully", "Abandoned (lost interest)", "Superseded by X", "Merged into Y"
- **Archive by year:** Keeps archive organised and searchable
- **Session archive is the completion log:** Completed projects are recorded in session logs, not in WIP
- **Preserve history:** Project file stays intact, just moved. All decisions and work documented.
- **Psychology matters:** Explicit completion provides closure and allows celebration

## When to Use This Command

**Use when:**
- Project genuinely complete (shipped, delivered, done)
- Project abandoned (decided not to pursue)
- Project superseded (better approach found)
- Project merged into larger work
- Project stalled for 30+ days with no intent to resume

**Don't use when:**
- Project just on hold temporarily
- Waiting for external dependency
- Will resume within weeks

If unsure, ask the user: "Is this project truly complete, or just on hold?"

## Integration

- **Works in Progress:** Keeps active list clean and accurate
- **Weekly synthesis:** Can review session archive for completion patterns
- **Session summaries:** Searchable record of when projects ended
- **Archive:** Long-term storage of all project history
