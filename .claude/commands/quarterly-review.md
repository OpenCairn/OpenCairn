---
name: quarterly-review
description: Quarterly deep review - strategic alignment and direction. Consumes /quarterly-hygiene for vault structural health.
---

# Quarterly Review - Strategic Check

You are facilitating the user's quarterly review. This is the highest-altitude review — strategic direction and alignment over a 3-month horizon: the questions too heavy for weekly that accumulate debt if never asked.

This is the **strategic half**, the reflective companion to `/quarterly-hygiene` (mechanical deep maintenance) — exactly as `/weekly-review` pairs with `/weekly-hygiene`. Vault structural health (context-file drift, CRM staleness, session-log archiving) is handled by `/quarterly-hygiene`; this command **consumes its report** rather than re-deriving any of it.

## Philosophy

1. **Strategic alignment** — Are the projects and priorities from 3 months ago still the right ones? What emerged that wasn't planned? What was planned but never started?
2. **Direction maintenance** — A quarterly review is the natural checkpoint to overhaul `Context - Direction.md`: strategic plans, anti-goals, disciplines.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and calculate quarter boundaries** using bash `date`:
   - Current date: `date +"%Y-%m-%d"`
   - Quarter: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec). Calculate start/end. File naming: `YYYY-QN.md`.
   - **Boundary rule:** if today falls in the first 2 weeks of a quarter, ask the user once whether this run reviews the just-ended quarter or the current one — a review run 2 Jul almost always covers Q2, and keying it to Q3 mislabels the output file and falsely stales a days-old hygiene report. Use the answer for the hygiene-report lookup, every "current quarter" test, and the output filename. (`/quarterly-hygiene` carries the same rule; keep the two runs on the same quarter.)

2. **Gather quarterly data:**
   - Read current `01 Now/Works in Progress.md`
   - Read `{VAULT}/07 System/Context - Direction.md` (if it exists) — the reference document for strategic alignment
   - Read `{VAULT}/07 System/Strategic Decision Log.md` (if it exists) — decisions made this quarter
   - Read weekly reviews from `06 Archive/Claude/Weekly Reviews/` for the quarter. **Boundary selection:** include any weekly review whose covered date range (from its `## Daily Reports` section) intersects the quarter; label partial-quarter reviews in the output. **Extraction guidance:** for each review, extract the Synthesis section, Projects Active, Alignment Check findings, and Course Corrections. Skip session counts, daily report links, and vault maintenance details (those are in the hygiene report).
   - Scan `03 Projects/` for all project files (root, Cold/, Backlog/)
   - **Consume the quarterly-hygiene report:** find the latest in `{VAULT}/06 Archive/Claude/Quarterly Hygiene Reports/` (filename descending).
     - **Current quarter:** read it — its findings populate the Vault Health section of the output. Do not re-scan context files, CRM, or run structural queries; that work is done.
     - **Older quarter:** warn — "Latest quarterly-hygiene report is [quarter] — structural findings may be stale. Recommend re-running `/quarterly-hygiene`." Still fold its findings into Vault Health, labelled stale in the source line. Continue with the strategic review.
     - **Absent:** warn — "No quarterly-hygiene report — vault structural findings will be missing from this review. Recommend running `/quarterly-hygiene` first." Vault Health gets the not-found line. Continue with the strategic review.

### Part 1: Strategic Review

3. **Mode choice.** Before the interview, ask the user once: interactive mode (walk through each section together) or auto-generate mode (compile answers from gathered data, present for validation). One question upfront — don't re-ask per section.

4. **Synthesise and present.** Before asking questions, present a brief data-driven summary from the gathered data: projects completed/stalled/abandoned (from WIP and project files), recurring patterns across weekly reviews, time allocation trends, and any alignment drift signals. This primes the user for the interview — they confirm, correct, and reflect rather than recall from memory.

5. **Run the quarterly strategic interview:**

   **Retrospective — What happened this quarter:**
   1. "Which projects were completed? Which stalled? Which were abandoned?"
   2. "What emerged that wasn't planned 3 months ago?"
   3. "What was planned but never started — why?"
   4. "Looking at the weekly reviews, what patterns persisted across the full quarter?"

   **Alignment — Are you working on the right things (reference Direction.md if loaded):**
   5. "Have your priorities shifted since the start of the quarter?"
   6. "Looking at your career and personal strategic plans — do they still reflect reality?"
   7. "What's consuming time that shouldn't be?"
   8. "What deserves more attention than it's getting?"
   9. "Any projects that should be explicitly killed rather than lingering?"
   10. "Any anti-goals that crept back in this quarter?"
   11. "Are your disciplines holding? Any to add, remove, or adjust?"

   **Forward-looking — Next quarter:**
   12. "What are the 3-5 Big Rocks for next quarter?"
   13. "What needs to start now to be ready on time? (Long Poles)"
   14. "What should you stop doing?"

6. **Direction.md overhaul (if Direction.md exists):**
   - Review these sections with the user: career strategic plan, personal strategic plan, anti-goals, disciplines, plus any section the user explicitly flags.
   - **Always ask — and collect only, don't edit yet.** Direction.md is high-trust, like context files. Gather the user's exact replacement text (or explicit approval of your proposed text) per section here; **step 8 is the single writer** — no edits happen in this step. (Direction.md is a context file, not a shared planning file — the Edit tool is fine there, `locked-edit.sh` not required.)

### Part 2: Vault Health (from quarterly-hygiene)

7. **Fold in the quarterly-hygiene findings.**
   This section is sourced entirely from the quarterly-hygiene report read in step 2 — no re-scanning here. Summarise its findings (carried weekly-hygiene structural items, context-file drift, CRM stale entries, session-log archiving status, skill-library flywheel findings, actions taken/routed) into the output's Vault Health section. A stale (older-quarter) report is folded with its stale label per step 2; only if no report exists at all, write "No quarterly-hygiene report — run `/quarterly-hygiene` for vault structural maintenance" and move on.

8. **Execute strategic edits (user-confirmed only):**
   - Apply Direction.md updates the user approved during step 6 (user-provided text only). Re-read Direction.md immediately before each edit to avoid stale writes.
   - Vault structural fixes (context corrections, file moves, archiving) are **not** done here — they belong to `/quarterly-hygiene`. If the user wants them actioned, point them at that command.

### Part 3: Output

9. **Ensure output directory exists:**
   ```bash
   mkdir -p "{VAULT}/06 Archive/Quarterly Reviews"
   ```

10. **Check for existing review.** If `{VAULT}/06 Archive/Quarterly Reviews/YYYY-QN.md` already exists (e.g. a mid-quarter first run), read it and ask whether to overwrite, append an update section, or write with a letter suffix (`YYYY-QNb.md`, then `c`, …). Letter suffixes sort *after* the bare name, so filename-descending latest-file lookups still find the newest run — a `-2` suffix would sort before it and invert the idiom (same reasoning as `/weekly-review`'s collision guard).

11. **Generate quarterly review** at `{VAULT}/06 Archive/Quarterly Reviews/YYYY-QN.md`:

   **⛔ Cite review items by stable identifier, not line number** — see `_shared-rules.md` §13. Name any `Tasks.md` / WIP / `Tickler.md` item by title/heading/content, never by line number, in this durable record.

```markdown
# Quarterly Review - YYYY QN ([Month] - [Month])

## Quarter in Review

### Projects Completed
- [[Project A]] — [Outcome]

### Projects Advanced
- [[Project B]] — [What moved, what remains]

### Projects Stalled/Abandoned
- [[Project C]] — [Why, and whether to keep or kill]

### Unplanned Work That Emerged
- [What came up that wasn't in the plan]

## Strategic Alignment

### Direction Check (from Direction.md)
**Career strategic plan:** [Still accurate / Updated — what changed and why]
**Personal strategic plan:** [Still accurate / Updated — what changed and why]
**Anti-goals reviewed:** [N items — any added/removed?]
**Disciplines reviewed:** [N active — any changes?]

### Priorities Then vs Now
[How have priorities shifted? Is the shift deliberate or drift?]

### Time Allocation Patterns
[Aggregated from weekly reviews — where did time actually go?]

### Kill List
Projects to explicitly abandon rather than let linger:
- [Project] — Reason to kill

## Vault Health
*Source: Quarterly Hygiene Reports/YYYY-QN (current / stale — from YYYY-QN, re-run recommended / not found — run /quarterly-hygiene)*

[Summarised from the quarterly-hygiene report — carried weekly-hygiene structural findings, context-file drift, CRM stale entries, session-log archiving status, skill-library flywheel findings, actions taken/routed. Not re-derived here.]

## Next Quarter

### Big Rocks (Top 3-5)
1. [Priority]
2. [Priority]
3. [Priority]

### Long Poles (Start Now)
- [Thing that needs lead time]

### Stop Doing
- [Thing to drop]

## Weekly Reviews This Quarter
- [[06 Archive/Claude/Weekly Reviews/YYYY-Wnn]] — Week N
- ...
```

When listing weekly reviews, preserve each file's exact name including any collision suffix (`YYYY-Wnnb` etc. — weekly-review writes suffixed files when two reviews land in one ISO week); a bare `YYYY-Wnn` link to a suffixed review is broken.

12. **Skill self-review (explicit instantiation of `_shared-rules.md` §8 / `_skill-monitor.md`).**
    This command runs ~4×/year, so the implicit skill-monitor watch is easy to skip. Before the final display, run the §8 / `_skill-monitor.md` review against this run end-to-end — did any step misfire, produce noise, mandate a tool that didn't work, or require an undocumented improvisation? If so, propose specific edits to this skill file (display for user approval — never auto-apply; edit the template copy if template-synced). If clean, state `✓ Skill self-review: no gaps this run`.

13. **Display confirmation:**

```
✓ Quarterly review saved to: 06 Archive/Quarterly Reviews/YYYY-QN.md
✓ Quarterly-hygiene report: [folded in / folded in (stale — YYYY-QN) / not found — run /quarterly-hygiene]
✓ Direction.md: [N sections updated / no changes]
✓ Skill self-review: [no gaps / N edits proposed]

Quarterly review complete.
```

## Guidelines

- **Strategic, not mechanical.** This command surfaces priority drift and overhauls Direction. Structural maintenance is `/quarterly-hygiene`'s job — consume its report, don't repeat it.
- **User confirmation for Direction.md.** High-trust file. Edit only with user-provided text; never infer an overhaul autonomously.
- **Connect to weekly reviews.** Reference weekly review insights rather than re-deriving from session logs.
- **Honest strategic assessment.** The quarterly check is where you surface uncomfortable truths about priority drift.
- **Natural language.** Write in the user's voice — analytical, outcome-focused, honest.

## Frequency

- Last week of March, June, September, December — or whenever the user requests it.
- First run: catch up on the current quarter even if mid-quarter.
- Run `/quarterly-hygiene` first (or alongside) so the Vault Health section has a report to consume.

## Integration with Other Commands

- **Consumes `/quarterly-hygiene`:** reads its report for vault structural health — no re-gathering.
- **Aggregates weekly reviews:** connects weekly patterns into quarterly themes.
- **Complements `/weekly-review`:** weekly handles tactical alignment; quarterly handles strategic + Direction overhaul.
- **Informs Direction.md:** the primary checkpoint for overhauling strategic plans, anti-goals, and disciplines.
