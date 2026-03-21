---
name: quarterly-review
description: Quarterly deep review - strategic alignment, landscape scan, vault structural health, and context file accuracy
---

# Quarterly Review - Deep Maintenance and Strategic Check

You are facilitating the user's quarterly review. This is the highest-altitude review — strategic direction, external landscape awareness, vault structural health, and context file accuracy. Things that are too heavy for weekly but accumulate debt if never done.

## Philosophy

Quarterly review serves three purposes:
1. **Strategic alignment** — Are the projects and priorities from 3 months ago still the right ones? What emerged that wasn't planned? What was planned but never started?
2. **Landscape scan** — What exists externally that you should know about? Patterns, tools, and architecture from teams and practitioners doing similar work.
3. **Vault deep maintenance** — Structural debt that accumulates slowly: context files drifting from reality, broken wikilinks, CRM gaps, orphaned files in areas that nobody visits weekly.

## Instructions

0. **Resolve Vault Path**

   ```bash
   if [[ -z "${VAULT_PATH:-}" ]]; then
     echo "VAULT_PATH not set"; exit 1
   elif [[ ! -d "{VAULT}" ]]; then
     echo "VAULT_PATH={VAULT} not found"; exit 1
   else
     echo "VAULT_PATH={VAULT} OK"
   fi
   ```

1. **Check current date and calculate quarter boundaries** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Determine quarter: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec)
   - Calculate quarter start/end dates
   - File naming: `YYYY-QN.md` (e.g., `2026-Q1.md`)

2. **Gather quarterly data:**
   - Read current `01 Now/Works in Progress.md`
   - Read weekly reviews from `06 Archive/Claude/Weekly Reviews/` for the quarter
   - Scan `03 Projects/` for all project files (root, Cold/, Backlog/)
   - Read all `07 System/Context - *.md` files
   - Read CRM index: `07 System/CRM/` (if exists)
   - Count vault files by area: `find "{VAULT}" -name "*.md" -type f | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -20`

### Part 1: Strategic Review

3. **Run the quarterly strategic interview:**

**Retrospective — What happened this quarter:**
- "Which projects were completed? Which stalled? Which were abandoned?"
- "What emerged that wasn't planned 3 months ago?"
- "What was planned but never started — why?"
- "Looking at the weekly reviews, what patterns persisted across the full quarter?"

**Alignment — Are you working on the right things:**
- "Have your priorities shifted since the start of the quarter?"
- "What's consuming time that shouldn't be?"
- "What deserves more attention than it's getting?"
- "Any projects that should be explicitly killed rather than lingering?"

**Forward-looking — Next quarter:**
- "What are the 3-5 Big Rocks for next quarter?"
- "What needs to start now to be ready on time? (Long Poles)"
- "What should you stop doing?"

4. **Landscape Scan — What exists that you should know about:**

   Use web search and scraping to check these specific sources. The goal is patterns and architecture, not a tool-adoption spree — "how did they solve X?" over "should I switch to Y?"

   **Claude Code ecosystem:**
   - https://github.com/hesreallyhim/awesome-claude-code — curated skills, hooks, slash commands, agent orchestrators, plugins
   - https://github.com/rohitg00/awesome-claude-code-toolkit — comprehensive toolkit (agents, skills, commands, plugins, hooks, rules, templates, MCP configs)
   - https://github.com/travisvn/awesome-claude-skills — skills and workflow customisation
   - https://code.claude.com/docs — official docs (new features, patterns since last quarter)

   **Obsidian + Claude PKM systems** (direct OpenCairn comparables):
   - https://github.com/ballred/obsidian-claude-pkm — starter kit with agents, skills, auto-commit hooks, goal hierarchy
   - https://github.com/ArtemXTech/claude-code-obsidian-starter — another starter kit with skills for projects, tasks, daily routines

   **Practitioner writeups** (people building similar systems):
   - Search for recent posts on Claude Code + PKM workflows, Obsidian + AI second brain patterns
   - Obie Fernandez's "Personal CTO Operating System with Claude Code" (Medium)
   - Matt Stockton's "How Claude Code Became My Knowledge Management System"

   **Docs-for-AI / knowledge structuring:**
   - Mintlify — docs-as-code with AI search, structuring for dual human/AI consumption
   - Documentation.AI — AI agents for documentation structure and maintenance
   - GitBook — docs-as-code with AI features

   **PKM landscape:**
   - PKM Weekly newsletter (https://www.pkmweekly.com/) — weekly digest of the space
   - AFFiNE, Tana — AI-native alternatives to Obsidian worth monitoring

   For each relevant finding:
   - What does it do?
   - What problem does it solve that OpenCairn currently handles manually (or doesn't handle)?
   - Classify: **adopt** (use directly), **adapt** (extract the pattern for OpenCairn), or **note** (interesting, not actionable now)

   If a source is unreachable or a repo has been deleted/moved, note it as "unavailable" and move on — don't block the review. Flag it in the Sources list updates section so the command file gets cleaned up.

### Part 2: Vault Deep Maintenance

5. **Context file accuracy audit:**
   - Read each `07 System/Context - *.md` file
   - For each file, check:
     - Are factual claims still accurate? (job title, location, hardware specs, active subscriptions)
     - Are preferences still current? (tools, workflows, approaches that may have changed)
     - Are referenced files/paths still valid?
     - Is anything missing that should be there based on this quarter's activity?
   - Flag inaccuracies and propose corrections
   - **Ask the user to confirm** corrections before applying (context files are high-trust, wrong corrections are worse than stale content)

6. **Vault-wide broken link scan:**
   ```bash
   # Extract all wikilinks and check if targets exist
   grep -roh '\[\[[^]]*\]\]' "{VAULT}" --include="*.md" | \
     sed 's/\[\[//;s/\]\]//;s/#.*//;s/|.*//' | \
     sort -u | while read -r link; do
       # Check if file exists (with or without .md extension)
       if [[ ! -f "{VAULT}/$link" ]] && [[ ! -f "{VAULT}/$link.md" ]]; then
         echo "BROKEN: [[$link]]"
       fi
     done
   ```
   - Group broken links by type:
     - **Renamed/moved files** — likely fixable by finding the new location
     - **Deleted files** — remove the links or recreate if needed
     - **Typos** — fix the link
   - Fix automatically where unambiguous, ask user for ambiguous cases

7. **CRM health review** (if CRM exists):
   - Read CRM index and range files
   - Check if existing CRM entries have stale information (old roles, old contact details, outdated context)
   - Review CRM candidate sections from this quarter's weekly reviews — anyone flagged multiple weeks but never added?
   - Flag stale entries and persistent gaps
   - **Don't auto-modify** — present findings and let user decide

8. **Orphaned file scan:**
   - Find files in `04 Areas/` and `05 Resources/` not linked from any other file:
     ```bash
     # List all .md files in Areas and Resources
     find "{VAULT}/04 Areas" "{VAULT}/05 Resources" -name "*.md" -type f | while read -r file; do
       basename="${file#{VAULT}/}"
       basename_no_ext="${basename%.md}"
       # Check if any other file links to this one
       if ! grep -rFl "[[${basename_no_ext}" "{VAULT}" --include="*.md" | grep -qv "$file"; then
         echo "ORPHAN: $basename"
       fi
     done
     ```
   - Orphans are candidates for: linking from a parent, archiving, or deleting
   - Present list to user for triage

9. **Archive/folder structure review:**
   - Check `03 Projects/` tier alignment with WIP (extends the weekly check but more thoroughly):
     - Every Active/Big Rock WIP entry should have a project file in `03 Projects/` root
     - Every Backlog WIP entry should have a file in `03 Projects/Cold/`
     - Every completed/abandoned project should be in `06 Archive/`
   - Check for oversized files (>500 lines) that should be split
   - Check for near-empty files (<5 lines) that should be merged or deleted
   - Check `06 Archive/Claude/Session Logs/` — are daily session files reasonably sized? Flag any anomalies.

### Part 3: Output

10. **Ensure output directory exists:**
   ```bash
   mkdir -p "{VAULT}/06 Archive/Quarterly Reviews"
   ```

11. **Generate quarterly review:**

Create a file at `{VAULT}/06 Archive/Quarterly Reviews/YYYY-QN.md`:

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

### Priorities Then vs Now
[How have priorities shifted? Is the shift deliberate or drift?]

### Time Allocation Patterns
[Aggregated from weekly reviews — where did time actually go?]

### Kill List
Projects to explicitly abandon rather than let linger:
- [ ] [Project] — Reason to kill

## Landscape Scan
**Sources checked:** [list of repos, articles, tools reviewed]

### Adopt (use directly)
- [Tool/pattern] — [what it does, why it's relevant]

### Adapt (extract the pattern)
- [Pattern] — [how to apply it to the vault/OpenCairn]

### Note (interesting, not actionable now)
- [Thing] — [why it's interesting, when it might become relevant]

### Sources list updates
- [Any new sources to add or stale ones to remove for next quarter's scan]

## Vault Health

### Context File Audit
| File | Status | Issues Found |
|------|--------|-------------|
| Context - Photography.md | Current | None |
| Context - Health.md | Stale | [specific issues] |

### Broken Links
- Fixed: N links
- Remaining (needs user input): N links

### CRM Updates
- New entries needed: [list]
- Stale entries flagged: [list]

### Orphaned Files
- Archived: N files
- Linked: N files
- User to triage: [list]

### Structural Issues
- Oversized files: [list]
- Tier mismatches fixed: [list]

## Next Quarter

### Big Rocks (Top 3-5)
1. [Priority]
2. [Priority]
3. [Priority]

### Long Poles (Start Now)
- [ ] [Thing that needs lead time]

### Stop Doing
- [Thing to drop]

## Weekly Reviews This Quarter
- [[06 Archive/Claude/Weekly Reviews/YYYY-Wnn]] — Week N
- ...
```

12. **Execute maintenance fixes:**
    - Apply context file corrections (user-confirmed)
    - Fix unambiguous broken links
    - Move tier-mismatched project files
    - Archive/delete user-approved orphans
    - **All destructive actions require user confirmation**

13. **Display confirmation:**

```
✓ Quarterly review saved to: 06 Archive/Quarterly Reviews/YYYY-QN.md
✓ Landscape scan: N sources checked, M findings
✓ Context files audited: N files, M issues found
✓ Broken links: N fixed, M remaining
✓ CRM: N new candidates, M stale entries
✓ Orphaned files: N found, M resolved
✓ Projects reviewed: N active, M completed, P killed

Quarterly review complete.
```

## Guidelines

- **User confirmation for all changes to context files and CRM.** These are high-trust files. Wrong corrections are worse than stale content.
- **Destructive actions always confirmed.** File deletions, moves, and link removals require explicit user approval.
- **Don't try to do everything.** If the vault is large, prioritise by impact. Fix context files and broken links first. Orphan scan is lower priority.
- **Connect to weekly reviews.** Reference weekly review insights rather than re-deriving everything from session logs.
- **Honest strategic assessment.** The quarterly check is where you surface uncomfortable truths about priority drift.
- **Landscape scan is research, not shopping.** The goal is patterns and architecture insights, not a tool-adoption spree. "How did they solve X?" is more valuable than "should I switch to Y?"
- **Update the source list.** If a source goes stale or a new one emerges, update the scan's source list in the command file itself so next quarter's scan stays current.
- **Natural language.** Write in the user's voice — analytical, outcome-focused, honest.

## Frequency

Run quarterly, typically:
- Last week of March, June, September, December
- Or whenever the user explicitly requests it
- First run: catch up on the current quarter even if it's mid-quarter

## Integration with Other Commands

- **Aggregates weekly reviews:** Connects weekly patterns into quarterly themes
- **Feeds into annual review:** (If the user implements one)
- **Complements /weekly-review:** Weekly handles tactical maintenance; quarterly handles strategic + deep structural
- **Informs context files:** The primary mechanism for keeping `07 System/Context - *.md` files accurate

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
