---
name: weekly-review
description: Weekly patterns review - aggregate progress, insights, and alignment
---

# Weekly Review - Patterns Over Time

You are facilitating the user's weekly review. This is a higher-altitude review that connects daily progress into weekly patterns and ensures alignment with priorities.

## Philosophy

The weekly review creates the crucial link between tactical execution (daily/session level) and strategic direction (monthly/quarterly goals). It's where you catch value drift, spot emerging patterns, and realign effort with priorities. Vault structural maintenance is handled by `/weekly-hygiene` — this command focuses on reflexion and planning.

## Instructions

0. **Resolve Vault Path**

   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and calculate review boundaries** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Get ISO week number: `date +"%Y-W%V"` (for file naming: YYYY-Wnn.md)
   - Find the previous weekly review: `ls -1 "{VAULT}/06 Archive/Claude/Weekly Reviews/" 2>/dev/null | sort -r | head -1`
   - **Review period starts** at the day after the previous review's last covered date. Parse the end date from the `## Daily Reports` section (which has explicit `YYYY-MM-DD` dated links) — this is more reliable than parsing the free-text title. If no previous review exists, fall back to Monday of the current ISO week. Store as `PERIOD_START`.
   - **Review period ends** at the current date.
   - Get date range for display: e.g., "Week 11, Mar 9-11" or "Weeks 10-11, Mar 2-11" if the period spans multiple ISO weeks.
   - This command can be run on any day of the week, at any cadence (4-12 days between reviews is normal). Do not assume Sunday-to-Sunday cycles.

2. **Check for Hygiene Report and gather the week's data:**

   **Hygiene report:**
   - Look for the latest file in `{VAULT}/06 Archive/Claude/Hygiene Reports/` (sorted by filename descending)
   - If a report exists, parse the week number from its filename (e.g., `2026-W10.md` → W10) and compare to the current ISO week (`date +%G-W%V`):
     - **Current week:** Read and incorporate — no warning
     - **Previous week or older:** Warn: "Latest hygiene report is from [week] — vault state may have changed. Consider re-running `/weekly-hygiene` before continuing. Proceeding with stale data." Continue with the review but flag staleness in the output.
   - If no reports exist, note this and suggest running `/weekly-hygiene` first (but continue with the review)

   **Week's activity data:**
   - Read daily reports from `{VAULT}/06 Archive/Claude/Daily Reports/` for dates from `PERIOD_START` to current date
   - **Daily report gap detection:** Compare the review period date range against files actually present in `Daily Reports/`. Flag any missing dates (e.g., "No daily report for Mar 18, 19, 20"). Include this in the review output under Challenges & Friction if gaps exist.
   - Read session summaries from `{VAULT}/06 Archive/Claude/Session Logs/` for the same date range
   - **Session count:** Use `grep -c "^## Session" <session-log-file>` as the canonical session count per day. Daily report self-reported counts may disagree due to merge addendums creating sub-entries under existing session headers. When counts disagree, use the `^## Session` header count and note the discrepancy.
   - Read current `01 Now/Works in Progress.md` to see active projects
   - Check project files in `03 Projects/` that were active this week

   **Schedule-vs-Execution data (Alignment Check input):**
   - **Cadence gate.** Run `cd "{VAULT}" && git log --since="7 days ago" --pretty=format:%H | wc -l`. If `git` errors (no vault repo) or the count is <24 × days_in_review_period (suggests autocommit hook isn't running at ~1/hr+), skip this data-gather entirely — the Schedule-vs-Execution subsection in step 5 degrades gracefully to a one-line note.
   - **Otherwise, for each day in the review period:**
     - **Post-/morning This Week.md state.** Find the commit closest to 14:00 vault-local time that day:
       ```bash
       cd "{VAULT}" && git rev-list -n 1 --before="YYYY-MM-DD 14:00" HEAD
       ```
       Then `git show $COMMIT:"01 Now/This Week.md"` and parse out that day's section. If empty, fall back to the first commit of the day whose day section has a populated `### Morning` subsection.
     - **Daily report.** Reuse the daily report read above.
     - **Load-bearing declaration.** Extract the `**Load-bearing today:** ...` line from the daily report (first content line under the heading, written by `/goodnight` step 8). If missing (days before step 6.5 rolled out), falls back to modal scheduled-items folder below.
     - **Vault attention profile.** Run:
       ```bash
       cd "{VAULT}" && git log --since="YYYY-MM-DD 00:00" --until="YYYY-MM-DD 23:59" --name-only --pretty=format: | sort -u
       ```
       Exclude infrastructure paths: `01 Now/This Week.md`, `06 Archive/Claude/Daily Reports/*`, `06 Archive/Claude/Session Logs/*`, `06 Archive/Claude/Session Transcripts/*`, `06 Archive/Claude/Weekly Context/*`, `06 Archive/Claude/Weekly Reviews/*`, `06 Archive/Claude/Hygiene Reports/*`, `.obsidian/*`.
   - **Compute per day:**
     - Scheduled items: count + folder distribution from This Week.md post-morning state, grouping by wikilink-target folder at its native depth (e.g. `04 Areas/Romantic relationships/Katie Fu`, not just `04 Areas`).
     - Executed items from daily report: `- ✓` = checked; plain `- ` items with `rolled to` suffix or absent from post-morning state = migrated-out; `~~strike~~` = dropped; items in daily report not in post-morning state = added mid-day. Skip container headers (`- Flexible between…`, `- Pick one, cycle, or timebox`, `- Admin batch`).
     - Actual attention: aggregate touched files into buckets defined by that week's scheduled-item wikilinks (longest-prefix match); files outside the vocabulary go to a catch-all `(outside scheduled vocabulary)` bucket.
     - Declared top folder: load-bearing line's wikilink if present; else modal scheduled-items folder; else literal token `load-bearing not folder-mapped` (skip salience row for that day).
     - Actual top folder: bucket with most files touched.
   - **Schema-drift sanity check.** If a day has non-zero attention-profile commits but zero parsed scheduled items, mark that day for a warning line in step 5.

   **Sweep for tagged tasks:**
   - Long Poles [LP]: `grep -r "\[LP\]" "{VAULT}" --include="*.md" --exclude-dir=".stversions" --exclude-dir="06 Archive" -l`
   - Cornerstones [CS]: `grep -r "\[CS\]" "{VAULT}" --include="*.md" --exclude-dir=".stversions" --exclude-dir="06 Archive" -l`
   - Read the matched files and extract the tagged items for review

   **Direction (strategic layer):**
   - Read `{VAULT}/07 System/Context - Direction.md` (if it exists)
   - Note the current values, strategic plans, and active disciplines for use in the Align section
   - This is the reference document for "are you working on the right things?"

   **Claude Corrections Log review:**
   - Read `{VAULT}/07 System/Claude Corrections Log.md`
   - Identify entries from this week (by date header)
   - Flag any lessons that should be promoted to CLAUDE.md or `~/.claude/projects/*/memory/MEMORY.md` for active recall

3. **Run the weekly review interview:**

Before diving into the lenses below, ask the user once whether they want interactive mode (walk through each lens together) or auto-generate mode (compile answers from data, present for validation). One question upfront — don't re-ask per section.

**Collect - What happened:**
- "What were the major accomplishments this week?"
- "Which projects moved forward? Which stalled?"
- "Time allocation: Where did the bulk of hours go?"
- If hygiene report exists, reference its open loop / scratchpad / tickler findings here rather than re-gathering

**Reflect - What matters:**
- "Key insights or learning from this week?"
- "What patterns emerged? (Good and bad)"
- "Any surprises - things that were easier or harder than expected?"
- "What did you overestimate? Underestimate?"

**Align - Priorities check (reference Direction.md if loaded):**
- "Looking at how you spent time vs your strategic plans - any misalignment?"
- "What got attention that shouldn't have?"
- "What didn't get attention that should have?"
- "Are you working on the right things?" (Check against career and personal strategic plans)
- "Any disciplines that slipped this week?" (Check against disciplines list)
- "Anything on the anti-goals list that crept back in?"

**Plan - What's next:**
- "What's the focus for next week?"
- "Any course corrections needed?"
- "Anything to stop doing or delegate?"

4. **Ensure directory exists:**
   - Check if `{VAULT}/06 Archive/Claude/Weekly Reviews/` directory exists
   - If not, create it: `mkdir -p "{VAULT}/06 Archive/Claude/Weekly Reviews"`
   - This prevents first-run failures

5. **Generate weekly review:**

Create a file at `{VAULT}/06 Archive/Claude/Weekly Reviews/YYYY-Wnn.md` (using the ISO week of the current date for the filename):

```markdown
# Weekly Review — [Date Range]

## Synthesis
**The week:** [One-line summary of what the week was about and what got done]
**Honest take:** [Candid 1-2 sentence assessment - alignment, drift, or what the user should hear]

## Session Count
[Total sessions, daily breakdown table if useful, average per day]

## Major Accomplishments
[Bullet list of significant progress, completions, milestones]

## Projects Active This Week
**Advanced:**
- [[03 Projects/Project A]] - [What moved forward]
- [[03 Projects/Project B]] - [What moved forward]

**Stalled:**
- [[03 Projects/Project C]] - [Why stalled, what's blocking]

**Completed:**
- [[03 Projects/Project D]] - [Outcome achieved]

## Time Allocation
[High-level breakdown of where hours went]
- Work/Training: X%
- Projects: Y%
- Health/Fitness: Z%
- etc.

## Key Insights & Patterns

### Wins & What's Working
[Patterns of success, effective strategies, good decisions]

### Challenges & Friction
[Recurring problems, inefficiencies, areas needing attention]

### Learning
[New skills, realisations, mental model updates]

## Alignment Check

### Schedule vs Execution
*[Populate from Schedule-vs-Execution data gathered in step 2. If the cadence gate failed, render just: "Schedule-vs-Execution reconciliation skipped — vault autocommit cadence below threshold (or no git repo)." Otherwise render the table + profile + divergence list below.]*

| Day | Scheduled | Checked | Added | Migrated | Declared top | Actual top |
|-----|-----------|---------|-------|----------|--------------|------------|
| [Day DD] | N | N | N | N | [folder] | [folder] |

**Folder-attention profile ([period] total, distinct files touched):**
- [folder at scheduled-vocabulary depth] — N
- [folder] — N
- *(outside scheduled vocabulary)* — N

**Days where declared ≠ actual:** [list of days, or "none"]

*[If any days flagged by the schema-drift sanity check, append:]*
⚠ Parser returned zero scheduled items for [day(s)] despite non-zero commits — This Week.md format may have drifted. Spot-check the day section.

*Blind spots:* non-vault work (packing, spoken conversations, reading PDFs) is invisible; deep-work commit sparsity (4h on one file = few commits) under-counts genuine focus.

### Priorities vs Reality
[Honest assessment: Is effort aligned with stated priorities? The Schedule vs Execution subsection above gives you the mechanical distribution — this subsection is the judgement call on whether that distribution matches what mattered.]

### Value Drift Alerts
[Any signs of drift toward low-value activities?]

### Aged Open Loops (14+ Days)
**Stale items requiring action:**
- Item from Session X (N days old) - Complete, drop, or delegate?
- Item from Session Y (N days old) - Complete, drop, or delegate?

**Recommendation:** These have lingered for 2+ weeks. Either act or explicitly drop.

### Long Poles [LP] & Cornerstones [CS]

**Long Poles** - Need lead time, can't be rushed:
- [LP task from file X] - Status/progress this week?
- [LP task from file Y] - Status/progress this week?

**Cornerstones** - Foundational, other things depend on these:
- [CS task from file X] - Status/progress this week?
- [CS task from file Y] - Status/progress this week?

**Review:** Are LP items getting attention early enough? Are CS blockers being addressed?

### Claude Corrections Log Review
**New entries this week:**
- [Date] - [Mistake summary] - Lesson: [key takeaway]

**Promote to active recall?**
- [Entry] → Add to CLAUDE.md or MEMORY.md? (Y/N, reason)

*Corrections Log is write-only unless promoted. Review weekly to catch patterns worth internalising.*

### Vault Maintenance
*Hygiene report from: YYYY-Wnn (current week / stale — re-run recommended / not found)*

[Populated from Hygiene Report if available — see `/weekly-hygiene`]

[Summary of hygiene findings: WIP health, tier mismatches, tickler items, broken links, etc.]

*If no hygiene report: "No hygiene report available — run `/weekly-hygiene` for vault maintenance."*

### Course Corrections Needed
[What to adjust for next week]

## What's Next

**Big Rocks (Priority 1):**
- Most important thing
- Second priority

**Active Projects:**
- Project A - [Specific next milestone]
- Project B - [Specific next milestone]

**Stop/Delegate:**
[Things to drop or hand off]

## Daily Reports
[Links to daily reports for drill-down]
- [[06 Archive/Claude/Daily Reports/YYYY-MM-DD]] - Mon
- [[06 Archive/Claude/Daily Reports/YYYY-MM-DD]] - Tue
- etc.
```

6. **Populate Vault Maintenance section from hygiene report.** If a hygiene report was found (from step 2), include its findings in the review output's Vault Maintenance section. If no report exists, note "No hygiene report available — run `/weekly-hygiene` for vault maintenance" in that section.

7. **Update Works in Progress** (if needed):
   - Update project statuses based on weekly progress
   - Add new projects if they emerged this week

8. **Generate Claude Web context summary:**

   Generate a comprehensive context snapshot (~120-150 lines) for the user to import into Claude Web via Settings > Capabilities > Memory > "Import memory from other AI providers" > paste into the "Add to memory" field. This gives Claude Web up-to-date, vault-informed context that merges into its Memory.

   **How Claude Web Memory works:** Claude Web auto-generates a "Memory from your chats" summary nightly from chat history. Imported context merges into this same Memory blob. The nightly regeneration restructures everything into third-person prose with sections like "Work context", "Personal context", "Top of mind", "Brief history". The context file is the user's authoritative, vault-informed self-description — more accurate than what Memory derives from chat patterns alone.

   **Output location:**
   - Ensure directory: `mkdir -p "{VAULT}/06 Archive/Claude/Weekly Context"`
   - Write output to `{VAULT}/06 Archive/Claude/Weekly Context/YYYY-Wnn.md` (using the current ISO week)

   **Gather context for dynamic sections:**
   - Read `{VAULT}/01 Now/Works in Progress.md` — every active entry is a candidate for inclusion, not just "projects." Relationships, health threads, ongoing evaluations, and personal decisions that are actively shaping behaviour belong in the context file if they'd change how Claude Web responds.
   - Read the 2-3 most recent weekly reviews from `{VAULT}/06 Archive/Claude/Weekly Reviews/` (sorted descending) for trajectory and recent events. The current week's review data is already available from earlier steps.

   **Read previous context version** to carry forward stable sections:
   - Find the latest file in `{VAULT}/06 Archive/Claude/Weekly Context/` (sorted by filename descending)
   - The file has two kinds of sections:
     - **Stable sections** (Background, Photography, Technical Setup, Health & Medications, Interests & Worldview, How I Like to Work): Carry forward from the previous version. Update only facts that changed this week. If no previous version exists, generate from CLAUDE.md and context files in `07 System/`.
     - **Dynamic sections** (What I'm Working On Right Now, Recent Context, Active Research Interests, and any active personal threads from WIP): Regenerate fully from WIP, recent weekly reviews, and this week's review data.

   **Output structure:**

   ~~~
   Last updated: YYYY-MM-DD

   [1-2 sentence identity/situation summary from CLAUDE.md]

   [Active personal context from WIP that shapes behaviour and decision-making — relationships being evaluated, major life transitions, ongoing personal threads. These aren't "projects" but they change how Claude Web should respond. Include enough detail that Claude Web can give informed advice without asking for backstory. Omit if nothing active.]

   ## What I'm Working On Right Now
   [Top 3-5 from "What's Next" section of this review, plus significant WIP entries. Include key dates/deadlines.]

   ## Recent Context
   [Key decisions, changes, events from the review period. 2-4 bullets.]

   ## How I Like to Work
   [Communication preferences from CLAUDE.md. Carry forward from previous version.]

   ## Background
   [Stable biographical context: citizenship, credentials, practice details, key collaborators, family, housing. Carry forward, update as needed.]

   ## Photography
   [Gear, websites, aesthetic, editing workflow. Carry forward, update as needed.]

   ## Technical Setup
   [Devices, OS, NAS, networking, backups, self-hosted services. Carry forward, update as needed. No vault file paths — irrelevant to Claude Web.]

   ## Health & Medications
   [Current medication stack, fitness approach, relevant conditions. Carry forward, update as needed.]

   ## Interests & Worldview
   [Core frameworks, influences, political orientation, intellectual interests. Carry forward, update as needed.]

   ## Active Research Interests
   [Current academic/intellectual pursuits. Refresh from review data.]
   ~~~

   **Section guidance:**
   - Not all users will have all sections. Omit any section with no corresponding context file or CLAUDE.md content. The section list above is a superset — match to what the user's vault actually contains.
   - For stable sections, look for `07 System/Context - *.md` files matching the section topic (e.g., a photography context file for Photography, a health context file for Health & Medications).

   **Constraints:**
   - ~120-150 lines target. Stable sections should be detailed enough that the user doesn't need to re-explain these domains in web conversations.
   - Written in third person ("[Name] is...", "He/She prefers...") — Claude Web's Memory system uses third person, and imported content is restructured into the same style. Third person is more predictable and consistent.
   - Start with `Last updated: YYYY-MM-DD` so staleness is self-evident both in the vault file and after pasting into Claude Web
   - No wikilinks, callouts, or dataview queries — standard markdown (headers, bullets, bold) is fine
   - No vault file paths (irrelevant to Claude Web)
   - Factual and current
   - **Magic phrase test:** Every line should change how Claude Web responds. If removing a line wouldn't change behaviour, cut it. 120 lines of load-bearing content is valuable; 120 lines with filler is worse than 60 tight lines.
   - **Stable sections: carry forward by default.** Only rewrite if facts changed. This preserves user edits and avoids churn.
   - **Dynamic sections: regenerate fully** from this week's review data with recency weighting.
   - **First-use bootstrap:** If no previous version exists, generate stable sections from CLAUDE.md and `07 System/Context - *.md` files that match the section topics. Dynamic sections will be generated from the current review data and WIP (gathered above). The first generation will require reading these files; subsequent weeks carry forward.

9. **Display confirmation:**

```
✓ Weekly review saved to: 06 Archive/Claude/Weekly Reviews/YYYY-Wnn.md
✓ Projects reviewed: N active, M completed, P stalled
✓ Hygiene report: [Incorporated / Not found — run /weekly-hygiene]
✓ Claude Web context: 06 Archive/Claude/Weekly Context/YYYY-Wnn.md (import via Settings > Capabilities > Memory)
✓ What's next: [Top 2-3 priorities]

Weekly review complete.

Recommended: Skim this review at the start of next week to set the week's direction.
```

## Guidelines

- **Always check current date:** First step - run `date` command to calculate accurate week boundaries. Never assume.
- **Patterns over details:** Look for recurring themes, not exhaustive documentation
- **Honest alignment check:** This is where you catch yourself working on the wrong things
- **Forward-looking:** Use insights to improve next week, not just to record past week
- **Connect timescales:** Link weekly patterns to monthly/quarterly goals (if tracked)
- **Quantify when useful:** Time allocation, completed tasks, etc. - numbers reveal patterns
- **Natural language:** Write in the user's voice - analytical, outcome-focused, honest

## Frequency

Run whenever the user requests it. Typical cadence is every 4-12 days — there is no fixed day-of-week requirement. The review period adapts to cover whatever time has elapsed since the last review.

## Integration with Other Commands

- **Consumes `/weekly-hygiene`:** Reads the hygiene report for vault maintenance findings — no need to re-gather
- **Synthesises daily reviews:** Aggregates daily patterns into weekly insights
- **Informs project planning:** Identifies what needs attention, what to drop
- **Feeds into monthly/quarterly reviews:** (If the user implements those)
- **Alignment with philosophy:** Connects tactics to values (see Philosophy & Worldview context)

This creates a **review rhythm** that prevents value drift and ensures high-level course correction.

## Goal Alignment (Optional Enhancement)

If the user starts tracking explicit goals in the vault:
- Compare weekly effort to goal progress
- Flag misalignments ("You spent 40% of time on X, but it's not in your top 3 goals")
- Suggest reallocation or goal updates
