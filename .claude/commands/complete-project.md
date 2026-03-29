---
name: complete-project
description: Explicitly complete a project and route artifacts - prevents zombie projects lingering in Works in Progress
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

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

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
   - **Domain:** "Does this project belong to a specific area (Health, Photography, Derm, etc.)?" (determines routing in Step 5)

4. **Update project file:**
   - Find project file (check all locations):
     - `{VAULT}/03 Projects/[Project Name].md` (active projects)
     - `{VAULT}/03 Projects/Backlog/[Project Name].md` (backlog projects)
     - `{VAULT}/03 Projects/Cold/[Project Name].md` (cold projects)
   - Add completion section at top:
     ```markdown
     **Status:** COMPLETED ([Date])
     **Outcome:** [Completed successfully / Abandoned / etc.]
     **Result:** [What was accomplished]

     ---
     ```
   - This preserves project history while marking completion

5. **Route project artifacts:**

   The key principle: **"completed project" ≠ "archived."** A completed project's useful artifacts (reference docs, templates, learnings) still belong in Areas. Archive is only for things where the information itself is no longer useful — just proof it existed.

   **Step 5a — Route useful artifacts to Areas:**
   - Check if the project has associated files (resource folders, reference docs, templates, setup guides) beyond the project file itself
   - For each artifact, ask: "Is this information still useful for reference, or is it truly dead?" Route accordingly:
     - **Still useful** → move to the relevant `04 Areas/[Area]/` folder
     - **Truly dead** (old CSVs, superseded docs, one-time exports) → `06 Archive/`
   - If the project has a resource folder in `03 Projects/`, apply the same test to its contents — don't move the whole folder blindly

   **Step 5b — Move the project file:**
   - Determine destination based on the artifact routing test:
     - **Area-owned project** (belongs to a specific domain): `04 Areas/[Area]/[Project Name].md`
     - **Cross-cutting project with lasting reference value**: `04 Areas/[most relevant area]/[Project Name].md`
     - **Truly dead project** (no reference value, just proof of existence): `06 Archive/Projects/YYYY/[Project Name].md`
   - If unsure, ask: "Does this project belong to a specific area, or is it truly dead with no future reference value?"
   - Create destination directory if needed
   - Move file from wherever it was found

6. **Update Works in Progress:**
   - Read `{VAULT}/01 Now/Works in Progress.md`
   - Remove project from its current section (Active, Maintenance, Backlog, etc.)
   - Update "Last updated" timestamp

7. **Create completion record in session file:**
   - If current session file exists for today, append brief note:
     ```markdown
     ---
     **Project Completed:** [[actual/destination/path/Project Name]]
     **Outcome:** [Result]
     **Date:** [Date and time]
     ---
     ```
   - Use the actual destination path from Step 5 (may be Areas or Archive)
   - This creates searchable record of when project was completed

8. **Display confirmation:**

```
✓ Project completed: [Project Name]
✓ Outcome: [Completed successfully / etc.]
✓ Project file moved to: [actual destination path]
✓ Works in Progress updated
✓ Completion recorded in today's session

Project completion complete. Well done.
```

## Guidelines

- **Explicit completion prevents drift:** Projects often fade rather than explicitly end - this forces a decision
- **Completion ≠ success:** Abandoned projects are valid completions. Acknowledging abandonment is better than indefinite limbo.
- **Outcomes:** Be honest - "Completed successfully", "Abandoned (lost interest)", "Superseded by X", "Merged into Y"
- **Route by value:** Useful reference → Areas. Truly dead → Archive (by year)
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
