---
name: complete-project
description: Explicitly complete a project and route artefacts - prevents zombie projects lingering in Works in Progress
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

   If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current time: `date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'`
   - Store for metadata

2. **Identify project to complete:**
   - Read `{VAULT}/01 Now/Works in Progress.md`
   - Display projects from the **top section** (entries above `## Active`, if any) and **every `##` section that exists** — not just Active. Don't hard-name a fixed trio; a vault may have only Active and Backlog, and project entries often sit in the untitled preamble above `## Active`. The headline completion case under "When to Use" (a project stalled 30+ days) has usually already been demoted out of Active, so an Active-only list hides exactly the projects this command exists to close.
   - If project name provided as parameter: Use that
   - Otherwise: Ask the user which project to complete
   - Validate the project exists — either as a WIP entry, **or** as a project file under `03 Projects/`, `03 Projects/Backlog/`, or `03 Projects/Cold/`. A long-stalled project may have a file but no WIP entry; that still completes.
   - **Initiative check:** `rg -Fr` (literal — the pattern contains `[[`, which is a character class to a regex engine) over `03 Projects/` for `**Initiative:** [[03 Projects/[Project Name]]]`. Hits mean this is an initiative with child projects — list them and confirm with the user that each child is completed or re-homed before proceeding; an initiative completed out from under live children leaves them pointing at a moved hub.
   - **Obsidian preflight:** Step 5's moves need the `obsidian` CLI with the app running. Probe now — `obsidian vault info=name` — **before any writes**. Use this, not `obsidian version`: `version` answers only "is the CLI installed", while `vault info=name` has to reach the running app's vault index, which is the precondition Step 5 actually depends on. Step 4 marks the file COMPLETED; discovering the CLI is down after that strands a half-completed project (marked done, still in `03 Projects/`, still in WIP — exactly the zombie this skill exists to kill). If the probe fails, ask the user to launch Obsidian, or defer the whole completion — don't start.

3. **Interactive completion interview:**
   First, scan the project file for unchecked `- [ ]` items. Each one gets resolved with the user before completion — done, abandoned, or migrated to a live home (WIP, Tickler, another project). **Write mechanism (F1):** migrations write via `write-tickler.sh` (Tickler) or `locked-edit.sh` (WIP, project files) per `_shared-rules.md` §5 — never the Edit tool, and never left as a note-to-self that never lands. A completed file leaves every surfacing loop; unchecked tasks moved with it become invisible zombie tasks.
   Then ask the user:
   - **Outcome:** "How did this project end? (Completed successfully / Abandoned / Superseded / Merged into other work)"
   - **Result:** "What was accomplished or learned?"
   - **Why now:** "Why are you completing this now?" (helps catch premature completion)
   - **Domain:** "Does this project belong to a specific area (Health, Hobbies, Work, etc.)?" (determines routing in Step 5)

4. **Update project file:**
   - **Write mechanism (F1):** apply this edit through `locked-edit.sh` (per `_shared-rules.md` §5), NOT the Edit tool. To prepend the completion block, `--replace` the file's first heading line with the block followed by that same heading line.
     - **Failure branches (the script's exit codes, don't improvise):** exit 2 = anchor not found — abort before any write and report which file. exit 3 = the anchor matched more than once (the H1 text recurs in the body) — re-anchor on a longer unique span that includes the following line, or use `--replace-all` only if every occurrence should change. Never retry the same failing anchor.
     - After each edit, grep the file for the separator token `========OPENCAIRN-LOCKED-EDIT-SEP========`. A hit means the heredoc leaked the separator into the file instead of splitting on it — fix before continuing. (This is the in-place edit *before* the Step 5b `obsidian move`.)
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
   - **Then rewrite the file's original status line** (the `/start-project` template's `**Status:** Active | **Target:** ...` below the H1) with a second `locked-edit.sh --replace`: change `Active` (or whatever live state it reads) to `COMPLETED` — same casing as the prepended block, so a grep for either finds both — keeping the rest of the line. Left as-is, the file carries two contradictory Status fields and anything scanning the body still reads the project as live. If the file predates the template and has no body Status line, skip this — the prepended block is then the only Status field.
   - **Then close out the template's `## Current Status` block** with a third `locked-edit.sh --replace`: replace its body with one line stating the end state, and bump the co-located `**Last update:**` stamp to today's date (Step 1). Skipped, the file reads "Project initialised" under a COMPLETED header, and every status scanner believes the body.
   - This preserves project history while marking completion

5. **Route project artefacts:**

   The key principle: **"completed project" ≠ "archived."** A completed project's useful artefacts (reference docs, templates, learnings) still belong in Areas. Archive is only for things where the information itself is no longer useful — just proof it existed.

   **⚠ How to move files — use `obsidian move`, never shell `mv`.** Every move in this step (artefacts *and* the project file) must go through Obsidian so inbound links auto-heal:

   ```bash
   obsidian move path="03 Projects/[Project Name].md" to="04 Areas/[Area]/[Project Name].md"
   ```

   Bind with `path=` (exact), not `file=` (resolves by name like a wikilink). Step 4 already located the file at an exact path, and `file=` can bind a same-named note elsewhere in the vault.

   Shell `mv` moves the bytes but leaves every inbound link dangling. This matters most for the **project file**: per `_shared-rules.md` §3, items link to projects with *path-based* references (`→ [[03 Projects/Project Name]]`), so the instant the file lands in `04 Areas/` or `06 Archive/` a raw `mv` breaks every one of them across This Week.md, Tickler, Tasks.md, day sections, and other project files. `obsidian move` rewrites those references for you. (Requires the Obsidian app running — the Step 2 `vault info=name` probe confirmed the app answered before anything was written. It boots an instance per call, so a probe that passed does not guarantee every later call succeeds; treat a mid-step failure as the abort case in Step 5b.)

   **Batch limit:** `obsidian move` boots a fresh Electron instance per call and deadlocks on the single-instance lock after a handful of files — fine for the project file and a few artefacts, unusable for a batch. For bulk artefacts, follow `/quarterly-hygiene`'s batch protocol: Obsidian GUI drag-and-drop (heals all inbound links in one pass), with raw `mv` acceptable only for files verified link-free via `obsidian backlinks` first.

   **Step 5a — Route useful artefacts to Areas:**
   - Check if the project has associated files (resource folders, reference docs, templates, setup guides) beyond the project file itself — explicitly including `05 Resources/[Project Name]/` (created by `/start-project` Step 7) and anything linked from the project file's `## Resources` section, not just folders under `03 Projects/`
   - **Present the artefacts as one batch with a proposed destination each, not one question per file.** Default every artefact to **Areas** (reference value is the common case and the reversible one) and ask the user only to name the exceptions — "these all go to `04 Areas/[Area]/` unless you call one dead." An empty reply accepts the defaults.
     - **Still useful** → the relevant `04 Areas/[Area]/` folder
     - **Truly dead** (old CSVs, superseded docs, one-time exports) → `06 Archive/`
   - **Stopping rule:** one pass. Don't re-interrogate artefacts the user has already routed, and don't ask about files under ~5 that are obviously project-internal scratch — route them with the project file.
   - If the project has a resource folder in `03 Projects/`, apply the same test to its contents — don't move the whole folder blindly
   - **Moving a folder:** `obsidian move` is file-only, and the batch limit below forbids calling it per-file. For a resources folder, use `/quarterly-hygiene`'s hand-off protocol: `mkdir -p` the destination, then have the user multi-select in Obsidian's file explorer and drag the batch across — Obsidian heals every inbound link in one pass. Raw `mv` only for files first verified link-free with `obsidian backlinks`.

   **Step 5b — Move the project file:**
   - Determine destination based on the artefact routing test:
     - **Area-owned project** (belongs to a specific domain): `04 Areas/[Area]/[Project Name].md`
     - **Cross-cutting project with lasting reference value**: `04 Areas/[most relevant area]/[Project Name].md`
     - **Truly dead project** (no reference value, just proof of existence): `06 Archive/Projects/YYYY/[Project Name].md`
   - If unsure, ask: "Does this project belong to a specific area, or is it truly dead with no future reference value?"
   - **Create the destination folder first** — `mkdir -p "{VAULT}/06 Archive/Projects/$(date +%Y)"` for the archive route (derive the real year; never a literal `YYYY` folder). `obsidian move` rewrites inbound links but is not documented to create missing destination folders, and `06 Archive/Projects/` does not exist in a fresh vault.
   - Then move the file from wherever it was found using `obsidian move` (see the move-mechanics note above), which rewrites inbound links as it goes
   - **If the move fails** (Electron lock, app closed since the preflight): stop. Report that the file is marked COMPLETED but has not moved, and name the exact path it is still at — a silent failure here is the zombie this skill exists to kill.

   **Step 5c — Verify link integrity:**
   - **Baseline first, before the Step 5b move:** `obsidian unresolved total`. After the move, run it again and compare. A bare post-move `obsidian unresolved` lists every pre-existing dangling link in the vault and cannot tell you which ones *this move* introduced — the count delta can.
   - Bound the call (it reindexes the vault and can hang). On timeout, print `link integrity: UNVERIFIED (unresolved check timed out)` and carry that through to Step 8 rather than reporting success.
   - **Also grep the moved project's path form and its bare title as plain text** — `rg -Fi '03 Projects/Project Name' "{VAULT}"` and `rg -Fi 'Project Name' "{VAULT}"`. Both are needed: the path form catches links and locators, and only the bare title catches the prose references ("see the Project Name doc") this check exists for. A wikilink example is redundant — under `-F` the path form is a substring of `[[03 Projects/Project Name]]` and matches it anyway. Scope to `{VAULT}` explicitly — an unscoped `rg` searches whatever cwd the session happens to be in and false-passes. Grep the path the file was **actually found at** in Step 4: a `Backlog/` or `Cold/` project's path form is `03 Projects/Backlog/Project Name`, which the root form misses. `-i` catches lowercased prose forms like "the project name doc". `obsidian move` rewrites `[[wikilink]]` references and `obsidian unresolved` catches dangling ones, but neither touches *prose/plain-text* references to the moved project ("see the Project Name doc", a path inside a fenced code block, a `**Source:**` line). Grep with NO keyword conjunction; triage each hit per `_shared-rules.md §12` (grep-hit triage — stale pointer → update; live locator → update on move; historical record → leave).

6. **Update Works in Progress:**
   - **Write mechanism (F1):** WIP edits use `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5).
   - Read `{VAULT}/01 Now/Works in Progress.md`
   - Remove project from its current section (Active, Maintenance, Backlog, etc.). If the project had no WIP entry (a file-only stalled project, per Step 2), there's nothing to remove here — skip to the timestamp.
   - Update "Last updated" timestamp

7. **Record the completion for the session log:**
   - **Do NOT hand-append to the session file with the Edit tool.** Session-file writes must go through the locked session scripts (`_shared-rules.md` §5); a raw append bypasses the flock and can be clobbered by a concurrent `/park` or `/goodnight`, and `/park` — which owns the day's session entry — may later truncate it.
   - Instead, surface the completion to the user so it lands in the next `/park` (the lock-safe owner of the session entry). Note for them, to carry into `/park`:
     - **Project Completed:** `[[Project Name]]` (use the basename wikilink to the actual Step 5 destination, not a full path — it survives future moves)
     - **Outcome / Result:** [from the interview]
     - **Date:** [Date and time]
   - This keeps a searchable record in the session log without racing the session lock.

8. **Display confirmation:**

```
✓ Project completed: [Project Name]
✓ Outcome: [Completed successfully / etc.]
✓ Project file moved to: [actual destination path]
[✓ Works in Progress updated | – No WIP entry to remove (file-only project)]
[✓ Link integrity verified (unresolved count unchanged: N) | ⚠ Link integrity UNVERIFIED (check timed out) | ⚠ N new unresolved links — triage before finishing]
→ Completion noted — carry it into your next /park for the session log

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
