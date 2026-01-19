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

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current time: `date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'`
   - Store for metadata

2. **Identify project to complete:**
   - Read `01 Now/Works in Progress.md`
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
   - Read `03 Projects/[Project Name].md`
   - Add completion section at top:
     ```markdown
     **Status:** COMPLETED ([Date])
     **Outcome:** [Completed successfully / Abandoned / etc.]
     **Result:** [What was accomplished]

     ---
     ```
   - This preserves project history while marking completion

5. **Move project file to archive:**
   - Create archive directory if needed: `mkdir -p "06 Archive/Projects/YYYY"`
   - Move file: `03 Projects/[Project Name].md` → `06 Archive/Projects/YYYY/[Project Name].md`
   - Update any resource folders (e.g., `03 Projects/[Project]-Resources/` → `06 Archive/Projects/YYYY/`)

6. **Update Works in Progress:**
   - Read `01 Now/Works in Progress.md`
   - Remove project from "Active" section
   - Add to "Recently Completed" section at bottom:
     ```markdown
     - **[Project Name]** — [Date] ([Outcome])
       - [Brief result/accomplishment]
       - [[06 Archive/Projects/YYYY/Project Name]]
     ```
   - Update "Last updated" timestamp
   - Keep Recently Completed limited to last 10 items (archive older ones)

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
- **Recently Completed visible:** Last 10 completed projects stay in WIP for context before being fully archived
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
- **Weekly synthesis:** Can review Recently Completed for patterns
- **Session summaries:** Searchable record of when projects ended
- **Archive:** Long-term storage of all project history

## Example Completion Flow

```
User: /complete-project "Claude Code Learning"

You: Reading Works in Progress...

Active projects:
1. Home Renovation
2. Side Project - App ⚠️
3. Travel Planning
...

Project "Claude Code Learning" found.

How did this project end?
(Completed successfully / Abandoned / Superseded / Merged into other work)

User: Completed successfully

You: What was accomplished or learned?

User: Created comprehensive park and pickup system, implemented all critical and high-value improvements, published documentation.

You: Why are you completing this now?

User: Core infrastructure is done and battle-tested. Template creation can be a separate project.

You:
✓ Project completed: Claude Code Learning
✓ Outcome: Completed successfully
✓ Result: Core infrastructure complete, blog published, system ready
✓ Project file moved to: 06 Archive/Projects/2026/Claude Code Learning.md
✓ Works in Progress updated
✓ Completion recorded in today's session

Project completion complete. Well done.
```

This creates clean closure and keeps Works in Progress accurate.
