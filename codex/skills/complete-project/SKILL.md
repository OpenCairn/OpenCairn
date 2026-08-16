---
name: complete-project
description: Explicitly complete a project and route artefacts - prevents zombie projects lingering in the 03 Projects root
---

# Complete Project - Formal Project Completion

You are helping the user formally complete a project. This command prevents "zombie projects" that linger in the `03 Projects/` root long after they're effectively done.

## Philosophy

Projects often fade away rather than explicitly complete. This creates clutter in the active root and uncertainty ("Am I still doing this? Should I be?"). Explicit completion:
- Provides psychological closure
- Documents outcomes for future reference
- Keeps the `03 Projects/` root accurate — folder location IS status, so moving the doc out of the root is the de-registration
- Allows celebration of completion

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `~/.codex/skills/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get current time: `date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'`
   - Store for metadata

2. **Identify project to complete:**
   - List project docs under `{VAULT}/03 Projects/` (root) and `{VAULT}/03 Projects/Cold/` — root = active, Cold = paused. Include `Backlog/` on request. The headline completion case under "When to Use" (a project stalled 30+ days) often sits in Cold, so a root-only list hides exactly the projects this command exists to close.
   - If project name provided as parameter: Use that
   - Otherwise: Ask the user which project to complete
   - Validate the project doc exists under `03 Projects/`, `03 Projects/Backlog/`, or `03 Projects/Cold/`, and **record the exact path found** — Steps 4-5 bind to it.
   - **Initiative check:** run `rg -F --glob '*.md' -- '**Initiative:** [[03 Projects/[Project Name]]]' "{VAULT}/03 Projects"`. (`-F` is the literal-search flag; in ripgrep, `-r` means replacement text, not recursion.) Hits mean this is an initiative with child projects — list them and confirm with the user that each child is completed or re-homed before proceeding; an initiative completed out from under live children leaves them pointing at a moved hub.
   - **Obsidian preflight:** Step 4's moves need the `obsidian` CLI with the app running. Probe now — `obsidian vault info=name` — **before any writes**. Use this, not `obsidian version`: `version` answers only "is the CLI installed", while `vault info=name` has to reach the running app's vault index, which is the precondition Step 4 actually depends on. **A failed probe does not block completion** — ask the user to launch Obsidian; if they can't or won't, proceed with the interview and completion marker but defer every move (Step 4 becomes a hand-off: name each pending move for the user to drag in Obsidian's file explorer, which heals links in one pass). Never fall back to raw `mv`.

3. **Interactive completion interview:**
   First, scan the project file for unchecked `- [ ]` items. Each one gets resolved with the user before completion — done, abandoned, or migrated to a live home (This Week, Tickler, another project doc). **Write mechanism (F1):** migrations write via `write-tickler.sh` (Tickler) or `locked-edit.sh` (This Week.md, project docs) per `_shared-rules.md` §5 — never a raw edit, and never left as a note-to-self that never lands. A completed file leaves every surfacing loop; unchecked tasks moved with it become invisible zombie tasks.
   Then ask the user:
   - **Outcome:** "How did this project end? (Completed successfully / Abandoned / Superseded / Merged into other work)"
   - **Result:** "What was accomplished or learned?"
   - **Why now:** "Why are you completing this now?" (helps catch premature completion)
   - **Domain:** "Does this project belong to a specific area (Health, Hobbies, Work, etc.)?" (determines routing in Step 4)

4. **Route project artefacts and move the project file:**

   The key principle: **`06 Archive/` holds write-once records only, never working files.** A completed project's useful material (reference docs, templates, learnings — and usually the project file itself) belongs on the owning Area's archival shelf. Material with no reference value is deleted, not archived — a session-log record of the completion is proof enough that it existed.

   **Resolve that shelf before routing anything — propose, then ask. Never invent a shelf, and never file silently.** `Archive/` is the working default, but the vault's archiving convention wins where it differs (Archiving convention in `07 System/Vault Organisation Principles.md` — tune the convention there, not here). Check whether `04 Areas/[Area]/Archive/` actually exists, then **put the proposed shelf to the user and wait for confirmation before any move — whether or not the folder already exists.** The proposal is a suggestion, not a decision. If `Archive/` exists, propose it. If it does **not**, never create one *unilaterally*: an Area lacking one often shelves finished material a different way (by year, by sub-domain, by destination), and a blind `mkdir -p` manufactures a second tree competing with the real one — so show the Area's existing subfolders and propose the one whose scope matches the material's lifetime. **If the Area has no subfolders at all**, there is no competing tree to manufacture: say the listing is empty, propose creating `Archive/` as its shelf, and create it once confirmed. Everything below writes to the **confirmed shelf**, written `[shelf]`.

   **State the shelf with its observable, not as an assertion** — print the listing the resolution rests on (`ls` of the Area) alongside the chosen path. "No `Archive/` here, the Area holds X and Y, proposing X" is checkable; "the Area has no archive" is not.

   **⚠ How to move files — use `obsidian move`, never shell `mv`.** Every move in this step (artefacts *and* the project file) must go through Obsidian so inbound links auto-heal:

   ```bash
   obsidian move path="03 Projects/[Project Name].md" to="[shelf]/[Project Name].md"
   ```

   Bind with `path=` (exact), not `file=` (resolves by name like a wikilink). Step 2 already located the file at an exact path, and `file=` can bind a same-named note elsewhere in the vault.

   Shell `mv` moves the bytes but leaves every inbound link dangling. This matters most for the **project file**: per `_shared-rules.md` §3, items link to projects with *path-based* references (`→ [[03 Projects/Project Name]]`), so the instant the file leaves the root a raw `mv` breaks every one of them across This Week.md, Tickler, day sections, and other project files. `obsidian move` rewrites those references for you. (Requires the Obsidian app running — the Step 2 `vault info=name` probe. A probe that passed does not guarantee every later call succeeds, for the reasons in `_shared-rules.md` §24; verify each move by result. A probe that failed means every move here is deferred to the user per Step 2 — completion still proceeds.)

   **Batches are fine, but drive the CLI per `_shared-rules.md` §24** — the single source of truth for this CLI (the `</dev/null`, the settle delay, verify-by-result rather than exit code, and why raw `mv` is never an alternative for link-bearing files). The Claude-side quarterly-hygiene command's Step 6 has the worked batch loop.

   **Step 4a — Route artefacts:**
   - Check if the project has associated files (resource folders, reference docs, templates, setup guides) beyond the project file itself — explicitly including `05 Resources/[Project Name]/` (created by `$start-project` Step 7) and anything linked from the project file's `## Resources` section, not just folders under `03 Projects/`
   - **Present the artefacts as one batch with a proposed destination each, not one question per file.** Default every artefact to the owning Area (reference value is the common case and the reversible one) and ask the user only to name the exceptions — "these all go to `[shelf]` unless you call one dead or still live." An empty reply accepts the defaults.
     - **Reference value** → `[shelf]` (a doc still in active use goes in the Area proper, not on its archival shelf)
     - **No reference value** (old CSVs, superseded docs, one-time exports) → **delete**
   - **Stopping rule:** one pass. Don't re-interrogate artefacts the user has already routed, and don't ask about files under ~5 that are obviously project-internal scratch — delete them with the user's batch approval.
   - If the project has a resource folder in `03 Projects/`, apply the same test to its contents — don't move the whole folder blindly
   - **Moving a folder:** a folder move means moving each file individually, per the batch note above and `_shared-rules.md` §24. `mkdir -p` the destination, move each file, then remove the empty source folder. If the Obsidian app is unavailable, hand off to the user to multi-select in the file explorer and drag the batch across — Obsidian heals every inbound link in one pass.
   - **Before any delete:** check inbound links via a backlinks route §24 marks reliable — and treat a nil result from an unreliable route as *unverified*, not as zero. Update live-doc references to the deleted file; links inside frozen records (session logs, snapshots) may be left dangling — the record of the deletion lives in the session log.

   **Step 4b — Move the project file:**
   - Determine destination:
     - **Reference value** (the common case — the doc records decisions, results, learnings): `[shelf]/[Project Name].md`
     - **No reference value** (nothing anyone will re-read): **delete the file** — after the Step 4a backlink check. If the user wants a durable trace beyond the session log, write a short completion record (outcome, result, dates) to `06 Archive/Projects/YYYY/[Project Name].md` — a new write-once record, not the project file. `mkdir -p "{VAULT}/06 Archive/Projects/$(date +%Y)"` first (derive the real year; never a literal `YYYY` folder).
   - If unsure, ask: "Will you ever re-read this doc? Area archive if yes, delete if no."
   - **Create the destination folder first** — `mkdir -p "{VAULT}/[shelf]"`, using the shelf **confirmed** at the top of Step 4. Only ever `mkdir` a path the user confirmed; never let this line be the thing that invents a new shelf. `obsidian move` rewrites inbound links but is not documented to create missing destination folders.
   - Then move the file from the exact path recorded in Step 2 using `obsidian move` (see the move-mechanics note above), which rewrites inbound links as it goes
   - **If the move fails** (Electron lock, app closed since the preflight): don't loop-retry. Continue to Step 5 — the completion marker still lands — and report in Step 7 that the file has not moved, naming the exact path it is still at and the intended destination. A named pending move the user can finish is recoverable; a silent failure is not.

   **Step 4c — Verify link integrity:**
   - **Baseline first, before the Step 4b move:** `obsidian unresolved total`. After the move, run it again and compare. A bare post-move `obsidian unresolved` lists every pre-existing dangling link in the vault and cannot tell you which ones *this move* introduced — the count delta can.
   - Bound the call (it reindexes the vault and can hang). On timeout, print `link integrity: UNVERIFIED (unresolved check timed out)` and carry that through to Step 7 rather than reporting success.
   - On the **delete** route, an unresolved-count rise equal to the frozen-record inbound links is expected — report it as such, not as a failure.
   - **Also grep the moved project's path form and its bare title as plain text** — `rg -Fi '03 Projects/Project Name' "{VAULT}"` and `rg -Fi 'Project Name' "{VAULT}"`. Both are needed: the path form catches links and locators, and only the bare title catches the prose references ("see the Project Name doc") this check exists for. A wikilink example is redundant — under `-F` the path form is a substring of `[[03 Projects/Project Name]]` and matches it anyway. Scope to `{VAULT}` explicitly — an unscoped `rg` searches whatever cwd the session happens to be in and false-passes. Grep the path the file was **actually found at** in Step 2: a `Backlog/` or `Cold/` project's path form is `03 Projects/Backlog/Project Name`, which the root form misses. `-i` catches lowercased prose forms like "the project name doc". `obsidian move` rewrites `[[wikilink]]` references and `obsidian unresolved` catches dangling ones, but neither touches *prose/plain-text* references to the moved project ("see the Project Name doc", a path inside a fenced code block, a `**Source:**` line). Grep with NO keyword conjunction; triage each hit per `_shared-rules.md §12` (grep-hit triage — stale pointer → update; live locator → update on move; historical record → leave).

5. **Mark the completion in the project doc** (skip if the doc was deleted in Step 4b — the session record carries the outcome):

   This runs **after** the move on purpose: the marker landing last means a run that dies partway leaves an ordinary un-marked project, never a marked-done doc still registered in the root. Apply the edits at the doc's **current** path — the Step 4b destination, or the Step 2 path if the move was deferred.

   - **Write mechanism (F1):** apply this edit through `locked-edit.sh` (per `_shared-rules.md` §5), NOT a raw edit. To prepend the completion block, `--replace` the file's first heading line with the block followed by that same heading line.
     - **Failure branches (the script's exit codes, don't improvise):** exit 2 = anchor not found — abort before any write and report which file. exit 3 = the anchor matched more than once (the H1 text recurs in the body) — re-anchor on a longer unique span that includes the following line, or use `--replace-all` only if every occurrence should change. Never retry the same failing anchor.
     - After each edit, grep the file for the separator token `========OPENCAIRN-LOCKED-EDIT-SEP========`. A hit means the heredoc leaked the separator into the file instead of splitting on it — fix before continuing.
   - Add completion section at top:
     ```markdown
     **Status:** COMPLETED ([Date])
     **Outcome:** [Completed successfully / Abandoned / etc.]
     **Result:** [What was accomplished]

     ---
     ```
   - **Legacy docs only:** if the file carries a pre-cutover body `**Status:**` line (the old template wrote one; new-format docs have none — folder location is status), rewrite it to `COMPLETED` with a second `locked-edit.sh --replace` so the body doesn't still read as live. New-format docs: skip — the prepended block is the only status marker.
   - **Then close out the template's `## Current Objective` block** (older files: `## Current Status`) with a third `locked-edit.sh --replace`: replace its body with one line stating the end state, and bump the co-located `**Last update:**` stamp to today's date (Step 1). Skipped, the file reads a live objective under a COMPLETED header, and every status scanner believes the body.
   - This preserves project history while marking completion

6. **Session record:**
   - The completion lands in the session log at the next `$park` — the lock-safe owner of the session entry. State the outcome plainly in-conversation so park's summary captures it; no separate completion-record structure or hand-off fields are needed.
   - **Do NOT hand-append to the session file with a raw edit.** Session-file writes must go through the locked session scripts (`_shared-rules.md` §5); a raw append bypasses the flock and can be clobbered by a concurrent `$park` or `$goodnight`.

7. **Display confirmation:**

```
✓ Project completed: [Project Name]
✓ Outcome: [Completed successfully / etc.]
[✓ Project file moved to: [actual destination path] | ✓ Project file deleted (no reference value) | ⚠ Move pending — file marked COMPLETED but still at [path]; intended destination [path]]
[✓ Link integrity verified (unresolved count unchanged: N) | ⚠ Link integrity UNVERIFIED (check timed out) | ⚠ N new unresolved links — triage before finishing]

Project completion complete. Well done.
```

## Guidelines

- **Explicit completion prevents drift:** Projects often fade rather than explicitly end - this forces a decision
- **Completion ≠ success:** Abandoned projects are valid completions. Acknowledging abandonment is better than indefinite limbo.
- **Outcomes:** Be honest - "Completed successfully", "Abandoned (lost interest)", "Superseded by X", "Merged into Y"
- **Route by value:** Useful reference → the Area's archival shelf (`Archive/` where one exists; otherwise resolved with the user, never invented). No reference value → delete. `06 Archive/` holds only write-once records (a completion record, if one is written) — never the project file or working material.
- **Session archive is the completion log:** Completed projects are recorded in session logs, not in any dashboard
- **Preserve history where it earns its keep:** A doc with reference value stays intact, just moved. A doc nobody will re-read is deleted, not entombed.
- **Psychology matters:** Explicit completion provides closure and allows celebration

## When to Use This Command

**Use when:**
- Project genuinely complete (shipped, delivered, done)
- Project abandoned (decided not to pursue)
- Project superseded (better approach found)
- Project merged into larger work
- Project stalled for 30+ days with no intent to resume

**Don't use when:**
- Project just on hold temporarily or revivable → move it to `03 Projects/Cold/` instead (folder is status; Cold = paused, not dead)
- Waiting for external dependency
- Will resume within weeks

If unsure, ask the user: "Is this project truly complete, or just on hold?"

## Integration

- **03 Projects root:** moving the doc out of the root IS the de-registration — the active set stays clean by location
- **Weekly synthesis:** Can review session archive for completion patterns
- **Session summaries:** Searchable record of when projects ended
- **06 Archive:** write-once records only — a project's history lives with its Area, not in Archive
