---
name: quarterly-review
description: Quarterly deep review - strategic alignment and direction. Consumes /quarterly-hygiene for vault structural health.
---

# Quarterly Review - Strategic Check

You are facilitating the user's quarterly review. This is the highest-altitude review — strategic direction and alignment over a 3-month horizon: the questions too heavy for weekly that accumulate debt if never asked.

This is the **strategic half**, the reflective companion to `/quarterly-hygiene` (mechanical deep maintenance) — exactly as `/weekly-review` pairs with `/weekly-hygiene`. Vault structural health (context-file drift, CRM staleness, oversized files, session-log archiving) is handled by `/quarterly-hygiene`; this command **consumes its report** rather than re-deriving any of it.

## Philosophy

1. **Strategic alignment** — Are the projects and priorities from 3 months ago still the right ones? What emerged that wasn't planned? What was planned but never started?
2. **Direction maintenance** — A quarterly review is the natural checkpoint to overhaul `Context - Direction.md`: strategic plans, anti-goals, disciplines.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and calculate quarter boundaries** using bash `date`:
   - Current date: `date +"%Y-%m-%d"`
   - Quarter: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec). Calculate start/end. File naming: `YYYY-QN.md`.

2. **Gather quarterly data:**
   - Read current `01 Now/Works in Progress.md`
   - Read `{VAULT}/07 System/Context - Direction.md` (if it exists) — the reference document for strategic alignment
   - Read `{VAULT}/07 System/Strategic Decision Log.md` (if it exists) — decisions made this quarter
   - Read weekly reviews from `06 Archive/Claude/Weekly Reviews/` for the quarter
   - Scan `03 Projects/` for all project files (root, Cold/, Backlog/)
   - **Consume the quarterly-hygiene report:** find the latest in `{VAULT}/06 Archive/Claude/Quarterly Hygiene Reports/` (filename descending).
     - **Current quarter:** read it — its findings populate the Vault Health section of the output. Do not re-scan context files, CRM, or run structural queries; that work is done.
     - **Older quarter, or absent:** warn — "No current quarterly-hygiene report — vault structural findings will be missing from this review. Recommend running `/quarterly-hygiene` first." Continue with the strategic review regardless.

### Part 1: Strategic Review

3. **Run the quarterly strategic interview:**

**Retrospective — What happened this quarter:**
- "Which projects were completed? Which stalled? Which were abandoned?"
- "What emerged that wasn't planned 3 months ago?"
- "What was planned but never started — why?"
- "Looking at the weekly reviews, what patterns persisted across the full quarter?"

**Alignment — Are you working on the right things (reference Direction.md if loaded):**
- "Have your priorities shifted since the start of the quarter?"
- "Looking at your career and personal strategic plans — do they still reflect reality?"
- "What's consuming time that shouldn't be?"
- "What deserves more attention than it's getting?"
- "Any projects that should be explicitly killed rather than lingering?"
- "Any anti-goals that crept back in this quarter?"
- "Are your disciplines holding? Any to add, remove, or adjust?"

4. **Direction.md overhaul (if Direction.md exists):**
- Walk through each section of Direction.md with the user
- Update strategic plans to reflect the current chapter (a quarterly review is a natural checkpoint for overhaul)
- Review anti-goals list — any to add or remove (premises changed)?
- Review disciplines — still the right set? Any to add, drop, or adjust?
- **Always ask before editing** — Direction.md is high-trust, like context files. Edit only with user-provided text.

**Forward-looking — Next quarter:**
- "What are the 3-5 Big Rocks for next quarter?"
- "What needs to start now to be ready on time? (Long Poles)"
- "What should you stop doing?"

### Part 2: Vault Health (from quarterly-hygiene)

5. **Fold in the quarterly-hygiene findings.**
   This section is sourced entirely from the quarterly-hygiene report read in step 2 — no re-scanning here. Summarise its findings (context-file drift, CRM stale entries, oversized/near-empty files, carried weekly-hygiene structural items, session-log archiving status) into the output's Vault Health section. If no current report exists, write "No quarterly-hygiene report — run `/quarterly-hygiene` for vault structural maintenance" and move on.

### Part 3: Output

6. **Ensure output directory exists:**
   ```bash
   mkdir -p "{VAULT}/06 Archive/Quarterly Reviews"
   ```

7. **Generate quarterly review** at `{VAULT}/06 Archive/Quarterly Reviews/YYYY-QN.md`:

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
*Source: Quarterly Hygiene Reports/YYYY-QN (current / not found — run /quarterly-hygiene)*

[Summarised from the quarterly-hygiene report — context-file drift, CRM stale entries, oversized/near-empty files, carried weekly-hygiene structural findings, session-log archiving status. Not re-derived here.]

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

8. **Execute strategic edits (user-confirmed only):**
   - Apply Direction.md updates the user approved during step 4 (user-provided text only).
   - Vault structural fixes (context corrections, file moves, archiving) are **not** done here — they belong to `/quarterly-hygiene`. If the user wants them actioned, point them at that command.

9. **Display confirmation:**

```
✓ Quarterly review saved to: 06 Archive/Quarterly Reviews/YYYY-QN.md
✓ Quarterly-hygiene report: [folded in / not found — run /quarterly-hygiene]
✓ Direction.md: [N sections updated / no changes]
✓ Projects reviewed: N active, M completed, P killed

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
