---
name: park
description: Capture session with full bookkeeping — quality gate, WIP update, open loop routing, session log, inline audit.
---

# Park - Session Capture

You are capturing a work session. Full bookkeeping: quality gate, WIP update, continuation links, reference graph tracing, conversation draft check, tickler.

**Concurrent parks are safe.** All shared-file writes (session log, WIP, This Week, Tickler, Tasks, project hubs) go through locking infrastructure (`write-session.sh`, `locked-edit.sh`, `write-tickler.sh` — see `_shared-rules.md` §5). Concurrent edits to the same file either both land (disjoint regions) or fail loudly (exit 2/3 — re-read and recompute). **Stale-read caveat:** concurrent parks may redundantly route the same open loop or flip the same checkbox; this is harmless — the dedup check (Step 13) catches most cases, and the next `/weekly-hygiene` trims any residual duplicates. **Goodnight note:** `/goodnight` runs its own close-out using the same locked-write machinery (it does not invoke /park); running goodnight while other parks are in flight is safe with locking, but parking first keeps the day's state most coherent for goodnight's daily report.

## Capture Philosophy

Every session captures the full bookkeeping pass. Sessions where there's nothing to capture (no files modified, no decisions, no open loops) produce a sparse log entry naturally — the bookkeeping cost on genuinely-trivial sessions is negligible (~30 sec), so there's no opt-out fast-path.

## Instructions

### Phase 1: Setup and Verification

0. **Resolve vault path** before proceeding:
   ```bash
   "$VAULT_PATH/.claude/scripts/resolve-vault.sh"
   ```
   If error, abort — the usual cause is `VAULT_PATH` unset (a required install precondition; `/setup` documents how to set it per-OS). Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

1. **Check current date and time** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"` (for session file naming)
   - Get current time: `LC_TIME=C date +"%I:%M%p" | tr '[:upper:]' '[:lower:]'` (for session timestamp; `LC_TIME=C` guards `%p`, which expands empty under many non-English locales)
   - Store these for use in metadata and file paths

2. **Check for merge-continuation** before creating a new session:
   - Determine from context whether this is a direct continuation of a recently parked session (same task, just finishing a loose end). Indicators: `/pickup` loaded a specific session, topic is identical, work is completing an open loop from that session. (Note: `/audit` no longer produces a separate canonical merge case — audit runs inline as Step 14 of the prior park, with any remediation merged in the same response. A *manual* `/audit` invoked after the park has fully finished can still trigger this merge path.) If the remediation is large, see the merge-size escape hatch below before treating it as canonical. Only ask the user if genuinely ambiguous.
   - **Merge-size escape hatch — don't merge when remediation dwarfs the target.** The canonical merge case assumes small follow-on work (a loose end, a small correction). Evaluate against the target session's *current* state (including any prior merge addendums, not the pre-first-merge original). If the `/audit` remediation would add a summary addendum >2× the target's current summary length, or touches >3 files unrelated to the target's stated topic, start a new session instead — fall through to Step 3 as if this were not a continuation. The merge rule exists to keep small fixes with the work they complete, not to absorb unrelated discoveries under a poorly-matching title. Topic-searches find sessions by their headline; a session titled "X closed" that actually contains hours of work on unrelated topic Y becomes invisible to future-pickup searches for Y.
   - **Script lock timeout — diagnose, don't work around:** If `update-session-section.sh`, `backfill-files-updated.sh`, `write-session.sh`, or `add-forward-link.sh` fails with "Lock timeout after 10s / Failed to acquire lock," the most likely cause is a hung prior invocation of the same script holding the flock. This happens when the Bash tool backgrounded an earlier heredoc-fed invocation (`cat <<EOF | script.sh ... EOF`) and the script got stuck in `anon_pipe_read` waiting for stdin that never closed. **Diagnose first, then kill the hung process** — don't immediately jump to a Python workaround. Full diagnosis and remediation (fuser, ps, kill, wchan inspection) is in `_shared-rules.md` §5 Failure mode B. Python+flock is a *secondary* fallback only — it bypasses the hung script by locking a different file, which does not coordinate with the script's `.lock` and is unsafe against a genuine concurrent writer. Kill the zombies first, then re-run the dedicated script.
   - If yes: **don't create a new session entry.** Instead, update the existing session using the update-session-section script (not the Edit tool — race condition risk with parallel parks):
     ```bash
     # Append to Summary (leading blank line creates paragraph break)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Summary"

     Merge addendum: [description]
     EOF

     # Append to Files Created (handles None→list automatically)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Files Created"
     - path/to/file - description
     EOF

     # Append to Files Updated (handles None→list automatically)
     # ⚠ MERGE PATH ONLY. Everywhere else in this skill, Files Updated is written by
     # Step 13a via backfill-files-updated.sh, which dedups by path. This call appends
     # unconditionally — using it during Steps 11-13 produces duplicate entries.
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Files Updated"
     - path/to/file - description
     EOF

     # Replace Next Steps / Open Loops (when changed)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Next Steps / Open Loops" --replace
     - Updated loop
     EOF

     # Replace Pickup Context (always replaced on merge)
     cat << 'EOF' | "{VAULT}/.claude/scripts/update-session-section.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N "Pickup Context" --replace
     **For next session:** ...
     **Project:** ...
     EOF
     ```
   - **After merging, run Steps 4, 8a, 8b, 10, 11, 12, 13, 13a, 13b, 14, 15, 16, 17** (quality gate, Pickup Context + Project verification, conversation draft persistence, WIP update, reference graph, open loop routing, backfill, timestamp bump, audit, skill monitor, transcript export, completion — all using the merged session's number). Steps 8a/8b matter here because the merge path is the one path that *rewrites* Pickup Context — scope them to the merged session's N and compare the Project line against the merged session's original link. Skip Step 3 (the conversation content is already in context) and Steps 5-9 *except 8a/8b* (no new session entry is needed, but the rewritten Pickup Context still gets verified). Because Step 5 is skipped, emit the observable project source downstream steps need, immediately after the merge edits: `Merged session: [existing topic] | Project: [Project line from the merged session]`.
   - **Steps 10, 12, 13, 15 typically produce their clean-pass checkpoint output in a merge** — `✓ No at-risk work product to persist`, `✓ Reference graph: No identifier values changed`, `✓ No open loops to route`, `✓ Skill monitor: No gaps detected` — because the remediation already did the routing/graphing inline as it ran. Run the mechanical checks anyway (Scratchpad `find`, enumerate-before-grepping, loop scan) — the checkpoint emission is mandatory either way — but don't fabricate findings to fill the slots if the checks come up clean. Steps 4, 8a, 8b, 11, 13a, 13b, 14, 16, 17 typically still have at least a small amount of real work (quality gate on the remediation edits, backfill, WIP timestamp bump, audit re-execution against the merged state, transcript re-export, completion reporting), but may also come up clean — in which case their normal success outputs apply.
   - This applies even if the session to merge into isn't the most recent — with parallel sessions, the relevant session may be the penultimate or earlier entry.
   - Completion message: `✓ Merged into Session N — [what was added]`
   - If not a continuation, proceed normally:

3. **Review the conversation context** to understand what was accomplished, decisions made, and what remains open. (The conversation itself is the source — no transcript artefact exists yet; the export happens at Step 16.)

### Phase 2: Quality Assurance

4. **⚠️ QUALITY GATE: Lint, refactor, proofread modified files (inline)**

   Quality gate runs inline in the main session — Step 4 is at the start of /park, before cognitive load accumulates, and the main session has session memory that's load-bearing for the mid-session-direction-changes and hot-capture-habit checks. A sub-agent delegation here would lose that memory advantage and pay token cost without empirical justification of inline failure (see Step 14's tail for the contrast — Step 14 has documented inline-failure history; Step 4 does not).

   **This step MUST produce visible output. No silent skipping.**

   **(a) Enumerate modified files explicitly (required output).** Before running any checks, list every file the session created or edited — vault AND non-vault (`~/repos/`, `~/.claude/commands/`, scripts, configs). Display the list. This makes the scope observable and prevents "I checked everything" claims that skip files. Format:

   ```
   Files to check:
   - path/to/file1.md
   - path/to/file2.py
   - …
   ```

   **⛔ Derive the non-vault half mechanically — recall is not sufficient.** The vault half of this list comes from work you did minutes ago and is easy to recall. The non-vault half is not: config and skill edits happen early, tooling writes files as a side effect, and hooks write files you never touched. This clause has existed for a long time and has still been observed to miss four files in one session — so it needs a trigger, not more emphasis. Run both checks and reconcile their output against what you were about to list:

   ```bash
   CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"   # never hardcode ~/.claude — the config dir is relocatable
   CUTOFF=$(date -u -d '4 hours ago' +%FT%TZ)         # BSD/macOS: date -u -v-4H +%FT%TZ

   # 1. Receipts from tooling that records its own writes (e.g. /sync-template).
   #    Lines are TAB-separated <UTC-ISO-8601>\t<path>\t<description>, so select by
   #    timestamp — never `tail -N`, which silently truncates a busy session and
   #    silently re-reads a quiet one.
   [ -f "$CONFIG_DIR/.sync-receipt" ] && awk -F'\t' -v c="$CUTOFF" '$1 >= c' "$CONFIG_DIR/.sync-receipt"

   # 2. mtime sweep of the config tree — catches hook-written and side-effect files
   #    that no receipt knows about (survey logs, caches). Window matches Step 10's.
   find "$CONFIG_DIR/commands" "$CONFIG_DIR/scripts" -maxdepth 1 -type f -mmin -240 2>/dev/null
   find "$CONFIG_DIR" -maxdepth 1 -name '*.log' -type f -mmin -240 2>/dev/null
   ```

   The two checks are deliberately redundant: the receipt carries *descriptions* and reaches outside the config dir (the template repo, a `{VAULT}` script copy), while the sweep needs no cooperation from the writing tool and so catches hook-written files no receipt can know about. Neither alone is sufficient.

   Anything either check returns that is missing from your list is a file you were about to under-report — add it. Anything they return that another session wrote is **not** yours: exclude it per `_shared-rules.md` §20 (the file list is the attribution boundary, not the mtime window) and say so rather than silently absorbing it. A git repo edited this session (`~/repos/…`) is covered by its own `git status --short`, not by these sweeps.

   **(b) Hot-capture habit nudge.** If substantive insights surfaced during the session but weren't routed in the moment via a "save that to [file]" interjection, name the habit gap in one line — metacognitive only. Do NOT cold-read the transcript to enumerate/classify/route — that re-introduces the failure mode hot-capture interjection is designed to avoid. If no habit gap, omit silently.

   **(c) Read each file before checking.** For every file listed in (a), issue a Read tool call. Session memory of what you wrote is not a substitute — the quality gate exists to catch what memory misses (stale interim state, mid-session direction changes, typos normalised away from attention). A file that wasn't Read cannot appear in the "N files checked" count at the checkpoint. Non-vault files (scripts, configs) that were Read earlier in the session for editing purposes still need a fresh Read here — the gate checks the file's current state, not the state at edit time. **For any file the session *edited*, read it IN FULL, not just the edited sections — mid-session direction changes (a reversal, a now-completed item, a superseded plan) leave stale residue in the file's *unedited* regions, which a section-scoped read can't see.** (The section-scoped read is acceptable only for large files the session merely *referenced* but did not edit.)

   **(d) Apply five check categories** to every file just read:

   **LINT** — Syntax and structure:
   - YAML frontmatter syntax errors
   - Broken file paths or internal links
   - Markdown syntax issues (unclosed code blocks, malformed lists)
     - **Concatenated list items:** after a session that removed list lines, run `grep -nE '[^[:space:]]- \[[ x]\]' <file>` on edited list-bearing docs — any non-space immediately before a `- [ ]`/`- [x]` is a join defect (a leading-`\n` removal ate the separator newline). Flag for review.
     - **Blank-line residue:** after a session that deleted a section, day, or block, run `awk 'NF{n=0;next}{n++}n==3{print FILENAME":"FNR": 3+ blank lines"}' <file>` on edited docs — a run of 3+ consecutive blank lines is deletion residue (the match removed the block but left its surrounding blanks). Collapse to the file's modal gap (1–2). Sibling defect to concatenated-list-items: same root cause (a block-boundary match that mis-handles separator newlines), opposite symptom (too many blanks vs too few).
   - Broken Obsidian wikilinks
   - **Terminal status vs draft-era filename:** if the session set a document's status field (a `Status:` line, frontmatter status, or equivalent body marker) to a terminal value (sent, done, booked, cancelled, shipped), check the filename for draft-era prefixes (Draft, WIP, TODO or local equivalents) and flag the mismatch — rename via the vault's link-healing move mechanism, not raw `mv`. The reference graph (Step 12) propagates changed *values*, not artefact *names*, so nothing else catches a filename asserting a state the body has outgrown.
   - **Hook collateral on verbatim content.** If the session used `Edit`/`Write` on a file containing verbatim external text (quoted titles, citations, transcript passages, foreign-spelling proper nouns, code identifiers), check the file for changes *outside* the edited region — a `PostToolUse` formatting hook rewrites the **whole file** on every write, not just the lines you touched, so a one-word edit can silently alter quoted material elsewhere in the document. Diff against the pre-session state where one is recoverable; otherwise scan the file's verbatim-bearing regions directly. Repair via shell (`sed`, `cat`), **never** `Edit`/`Write` — the repair re-fires the hook and re-causes the defect. Full rule and the two defences: `_shared-rules.md` §14. Highest-risk files: anything with a reference list, an interview excerpt, or deliberately non-local spelling.

   **REFACTOR** — Content quality:
   - Consolidate redundant content (did I repeat myself across files?)
   - Update stale references (outdated info, old dates, deprecated approaches)
   - Fix broken structure (illogical heading hierarchy, orphaned sections)
   - Remove dead/orphaned content created then abandoned
   - **Mid-session direction changes:** If the session's conclusion diverges from its starting position (e.g. an item went from "moot" to "live option", or a decision was reversed), re-read files edited earlier in the session and verify they reflect the final state, not the interim state. This is distinct from general staleness — these files were correct when written but became stale because the conversation changed direction.
   - **Research persistence:** Did this session produce research (subagent findings, web searches, analysis) that should be captured in a reference/area file, not just narrated in the session summary? If a stub entry exists for the researched topic, update it with the findings.
   - **Hub/index discoverability:** For each durable hub, index, or aggregator doc the session *created* inside a project/area subtree (one meant to be re-read later, not a dated note), verify it's linked from a durable parent — the subtree's `_index`/hub — not only from a rolling-window file (This Week, WIP `**Last:**`). Grep the parent for the new doc's link; if absent, add it. If the subtree has no `_index`/hub, link from the nearest ancestor hub or the session's project/area doc instead — don't create a hub just to host the link. A doc reachable solely via dated planning lines orphans once those lines age out. (Distinct from the Step 12 reference graph, which propagates *changed* identifiers but never catches a *newly-created* doc that no durable file points to.)

   **VERIFY** — Session summary accuracy (if updating an already-parked session):
   - Do open loops still reflect reality? (If user completed something mid-conversation, remove it from the list)
   - Does pickup context still match? (If "ready for upload" is now uploaded, update the line)
   - Were any "Next Steps" completed during the session? Remove them from the list (they're no longer open)

   **PROOFREAD** — Language and consistency:
   - **Spelling localisation:** Skip if a PostToolUse spelling hook (e.g. britfix) already normalises spelling at write time. Otherwise: use the locale from the user's CLAUDE.md (`**Locale:**` line). If `en_AU` or `en_GB`: normalise to British/Australian spelling. If `en_US`: normalise to American. If no locale set: skip spelling normalisation.
   - Terminology consistency (park/pickup not parking/resume/restore)
   - Typos, grammar, unclear phrasing
   - Tone consistency with the user's voice (if the vault has a voice/style context file — see the user's CLAUDE.md routing — load it when voice questions arise; skip if none exists)

   **SOURCE** — Unsourced specific values, **and asserted preconditions**. Run **`_shared-rules.md` §19** (already in context — Step 0 reads it in full) over every file enumerated in (a). Its required output line is part of this gate's checkpoint. §19's precondition clause is the half that bites here: a blocker this session wrote into a forward-looking doc ("needs a restart first", "blocked until X is installed") is an unsourced claim gating future work, and it reaches the next session as fact unless it is tested or cut now.

   **Fix any issues found automatically.** For fixes to shared planning files (WIP, This Week, Tickler, Tasks), use `locked-edit.sh` per `_shared-rules.md` §5.

   **⛔ Don't auto-revert changes you didn't make.** If a file has been modified between your Edit and the quality-gate scan and the change wasn't yours, surface it in the gate output and let the user decide — don't undo it. Auto-reverting silently overwrites work you didn't make, and you have no reliable way to attribute the source of the change anyway.

   **(e) Display the required checkpoint output:**

   ```
   ✓ Quality check: N files checked, no issues found
   ```

   ```
   🔧 Quality check: Fixed N issues
   - [path1] - [specific fix]
   - [path2] - [specific fix]
   ```

   **⛔ CHECKPOINT:** You cannot proceed to Step 5 until the quality-check line appears in your response. The file enumeration in (a), Read calls in (c), and a quality check result are all required — if any are missing, the count claim in the checkpoint output is unverifiable. If you find yourself writing session metadata without having displayed all three, STOP and return to this step.

### Phase 3: Document and Archive

5. **Determine session metadata:**
   - **Session number is resolved at write time (Step 8), not here.** This is intentional — pre-computing N via `next-session-number.sh` and then writing later is racy against parallel /park invocations from independent sessions (both can resolve to the same N before either acquires the write lock, producing duplicate `## Session N` headings). Step 8 uses `--auto-number` which resolves N inside the file lock. Treat N as unknown until then.
   - Topic/name for this session (concise, descriptive)
   - Use current time from step 1 (already checked)
   - Related project (if applicable) — follow Project Linking Rules in `_shared-rules.md` Section 2
   - **Display the determination explicitly** — this is the single source for the topic + project link used in Steps 7 and 11:
     ```
     Session: [Topic] | Project: [[03 Projects/Name]] (or "None")
     ```

   **⛔ CHECKPOINT:** You cannot proceed to Step 6 until the `Session: [Topic] | Project: [[...]]` line appears in your response. Step 8b's Project check compares against this output — if Step 5 never emitted it, Step 8b is auditing internal memory rather than observable state. Small deviations here cascade. If you find yourself writing session content without having displayed this line, STOP and return to this step.

6. **Check for continuation:**
   - Check if this session is continuing a previous one (from `/pickup` context)
   - If continuing: Store continuation link for inclusion in summary (the `**Continues:**` line in Pickup Context)

7. **Generate session summary** using the format below.

   **Body only — no `## Session N - …` heading.** Step 8's `--auto-number` mode prepends the heading inside the lock. If you include a heading here, the script rejects the write with an explicit error (exit 1) — remove the heading and re-run.

```markdown
### Summary
[2-4 sentence narrative of what was accomplished. Focus on outcomes and decisions.]

### Key Insights / Decisions
[Bullet list of important realisations, architectural choices, or decisions made]

### Next Steps / Open Loops
- Specific actionable item with clear next action
- Another open loop that needs attention
[Each item should be actionable and specific enough to resume without re-reading entire conversation]

### Files Created
- path/to/file.md - [purpose/description]

### Files Updated
- path/to/file.md - [what changed and why]

### Files Deleted
- path/to/file.md - [why removed — e.g. merged into X, superseded by Y]
[Optional — include only when the session deleted a vault file. Omit the whole section otherwise.]

### Pickup Context
**For next session:** [One clear sentence about where to pick up - the very next action to take]
**Continues:** [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session X - Topic) — include only if this session continues previous work
**Project:** [use exact link from Step 5 — do not rewrite]
```

   **Reconcile Files Created / Files Updated / Files Deleted against the Step 4(a) enumeration.** Every file in that enumeration must appear in one of the three lists (created, updated, or deleted). This is the backstop for in-session edits to planning files — a checkbox flip in This Week, a Tickler add — which are easy to omit here because they feel like bookkeeping rather than session work. (Files edited *later*, during park Steps 11-13, aren't in the 4(a) set yet — Step 13a backfills those.)

8. **Write the summary** (with file locking + atomic session numbering):
   - **CRITICAL: Use the write-session script, NOT inline flock or the Edit tool**
   - Inline flock commands corrupt `settings.local.json` (the entire command including session content gets saved as a permission pattern)
   - The script handles locking, file creation, atomic writes, and atomic session numbering

   **✓ USE `--auto-number` MODE.** The script resolves N inside the file lock, so parallel /park invocations cannot collide on the same session number.

   **Appending to existing file:**
   ```bash
   cat << 'EOF' | "{VAULT}/.claude/scripts/write-session.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" --auto-number "TOPIC" "HH:MMam/pm"
   ### Summary

   [Session body — no `## Session N` heading; the script prepends it.]
   EOF
   ```

   **First session of the day:** identical invocation — no special flag. The script lays down the `# Claude Session - DATE` header automatically when the file is absent or empty, and appends otherwise. The decision is made from file state inside the lock, so parallel first-session writes can't lose content.

   The script handles:
   - File locking (flock) for concurrent safety
   - Lock timeout (10 seconds for NAS)
   - Date header generation (automatic when the file is absent/empty)
   - Directory creation if needed
   - **Atomic session numbering** (--auto-number reads the file inside the lock and assigns the next N, prepending the `## Session N - <topic> (<time>)` heading)

   **Capture N from stdout.** The script's final line is `Session number assigned: N`. Read it from the tool output and use that N for all downstream steps (8a, 8b, 11, 13, 13a, 14). Do NOT rely on a pre-computed N — under parallel /park, the number you'd predict and the number you got may differ.

   **If the write fails (exit code 1):** the script exits 1 for several distinct causes — lock timeout, empty stdin, the heading-reject above, usage errors. Key the retry on the stderr text, not the bare exit code: only a `Failed to acquire lock` / `Lock timeout` message warrants the retry below; any other error means the invocation is wrong — fix it instead of retrying. On a lock-timeout message, display the warning and retry once, then fail gracefully:
   ```
   ⚠ Lock acquisition timed out - another session may be parking. Retrying...
   ```

   **Display N explicitly after the write** — this is the canonical source for downstream steps:
   ```
   Session number assigned: N
   ```

8a. **⛔ Pickup Context section verification:**
   After writing the session, verify the `### Pickup Context` section actually exists in the just-written entry. The write-session script writes whatever stdin you give it without validating that all required sections are present — it's possible to write a session entry that's missing sections entirely. The Pickup Context section is the load-bearing one because it carries both the next-session pointer AND the Project link.

   **Scope the check to the just-written session block** (N = session number assigned by Step 8's `--auto-number` output, not predicted in Step 5), not the global file count. A global `grep -c` across the whole day's log can pass when the session being verified is the one missing — e.g. if an earlier session already has Pickup Context and Session N doesn't, the count is still ≥1 and passes. The check must verify the specific block:
   ```bash
   # Letter-var z=0 binding works around the slash-command loader consuming bare dollar-digit tokens (positional-arg placeholders). See github.com/anthropics/claude-code/issues/52226
   # <N> is a substitute-me placeholder like {VAULT}: replace it with the literal session number from Step 8's output.
   # Shell variables do NOT persist between Bash tool calls — a bare $N would be unset, the awk pattern would match
   # nothing, and the count would return 0: a false "missing" that triggers a duplicate-section "fix".
   awk -v n=<N> -v z=0 '$z ~ "^## Session " n " "{p=1; next} p && /^## Session /{exit} p' "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" | grep -c '^### Pickup Context'
   ```
   Expected: exactly 1. If 0, Session N is missing Pickup Context — add it via the Edit tool (the script can't append a new section that doesn't exist). Display: `Pickup Context check: present ✓` or, if fixed: `Pickup Context check: section was missing, added via Edit`.

   **⛔ CHECKPOINT:** You cannot proceed to Step 8b until `Pickup Context check:` output appears in your response.

8b. **⛔ Project link verification:**
   After confirming the Pickup Context section exists, verify the `**Project:**` line inside it matches Step 5's determination. Extract mechanically — **scope to Session N's block**, not a whole-file grep: under concurrent parks a later session's `**Project:**` line can be the file's last one, so `grep … | tail -1` over the whole file can validate the wrong session. Reuse Step 8a's Session-N awk:
   ```bash
   # Letter-var z=0 works around the slash-command loader eating bare $-digit tokens (see Step 8a).
   # <N> = literal session number, substituted as in Step 8a (shell vars don't persist between Bash calls).
   awk -v n=<N> -v z=0 '$z ~ "^## Session " n " "{p=1; next} p && /^## Session /{exit} p' "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" | grep '^\*\*Project:\*\*' | tail -1
   ```
   Compare against Step 5 output. If they differ, fix the session log before proceeding.
   Display: `Project check: [link] ✓` or, if fixed: `Project check: fixed [old] → [new]`

   **⛔ CHECKPOINT:** You cannot proceed to Step 9 until `Project check:` output appears in your response. If you find yourself writing continuation links without having displayed a project check result, STOP and return to this step.

9. **Add continuation link** (only if continuing previous work):
   - **Only fires if this session continues a specific previous session** (from `/pickup` context). If not a continuation, skip this step entirely.
   - Do NOT add chronological "Next session:" links — sessions are already in order in the file. Only topical continuation links carry information.
   - Add "Continued in:" link to the original session being continued:
     - Format: `**Continued in:** [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session N - Topic)` — the link points at the day's log **file**, naming the session in plain text after it.
     - **Never use a `#Session N - …` heading anchor here** — session-log links are file-level per `_shared-rules.md` §13 (already in context; Step 0 reads it in full).
     - Use the forward-link script with `--continued-in`:
       ```bash
       # Same-day:
       "{VAULT}/.claude/scripts/add-forward-link.sh" --continued-in "<session-file>" <orig-num> <new-num> "<new-topic>"
       # Cross-day:
       "{VAULT}/.claude/scripts/add-forward-link.sh" --continued-in "<session-file>" <orig-num> <new-num> "<new-topic>" "<target-date>.md"
       ```
   - **Error handling:** If script fails (file missing, lock timeout, session not found), log warning but don't fail the park.

10. **Check for at-risk work product.** Two failure modes to check.

   **(a) Conversation-only drafts.** Scan the conversation for drafts *Claude composed* inline that only exist as text output — emails, messages, analysis, plans. Common triggers: `/reply` drafts, email compositions, multi-paragraph analysis. If found, write each to its semantic home in the vault (correspondence file, project doc, area file). Drafts the *user* authored and pasted (e.g. typing message text into a booking field, composing in their own client) are not at-risk — they're already the user's authored artefact, not session-only output.

   **(b) Work product persisted to transient capture surfaces.** Scratchpad, Inbox, and daily notes are designed to be cleared on a regular cadence — they are *not* durable homes.

   **Scope:** this-session contributions only. Pre-existing content sitting in a transient surface across multiple sessions is the user's intentional working buffer, not at-risk material from this session. Cross-session cleanup is `/weekly-hygiene` Step 6's job, not /park's.

   **Detection:** Use `find` with `mtime` filtering, **scoped to transient-surface parent directories** — never from `{VAULT}` itself. Finding from vault root crawls `.git` auto-save history, which on a long-lived vault can take minutes. Transient surfaces live in known top-level directories (`01 Now`, `02 Inbox`, daily-note folders) that don't contain `.git`, so scoping the find to those parents avoids the crawl cost entirely while keeping the check mechanical (filesystem fact, not Claude's memory) and proportionate. Do not gate on "I don't think I wrote there" — memory-based gating is the failure mode this check exists to prevent.

   For a session of N minutes, use `-mmin -N` (a generous default for typical sessions is `-mmin -120`):

   ```bash
   # Scope the find to transient-surface parent directories.
   # NEVER pass {VAULT} itself as a find root — it crawls .git auto-save history.
   # Add vault-specific transient locations (daily-note folders, etc.) as additional roots.
   find "{VAULT}/01 Now" "{VAULT}/02 Inbox" -maxdepth 2 -type f -name "*.md" -mmin -120 2>/dev/null
   ```

   For each result, judge whether it's a transient surface (Scratchpad.md, inbox capture, daily note) — skip durable files in the same directories that happen to have recent mtimes (e.g. `01 Now/Works in Progress.md`, `01 Now/This Week.md`, `01 Now/Tickler.md`). For each transient-surface hit, read it and judge whether new content from this session is durable work product (a draft for a forthcoming submission, message, or document; anything a future session would need to retrieve). **Known at-risk signature:** `/reply` draft sections in Scratchpad, identified by headings starting with `**Reply to ` — see `_shared-rules.md` §11 for section boundaries and cleanup ownership. If durable work product is found, move it to its semantic home, remove it from the transient surface, and update every reference that pointed at the old location — grep each updated durable doc for the old locator (path, link label, heading, or reference phrase) and fix all occurrences, not just the ones you recall. **Exception — `/reply` draft sections: per §11's confirmation gate, do NOT remove or route one without explicit per-draft user confirmation that it was sent or is no longer needed.** Other at-risk work product may be moved automatically.

   - **⛔ CHECKPOINT:** Display exactly one of:
     ```
     ✓ No at-risk work product to persist
     ```
     ```
     🔧 Persisted N item(s): [paths]
     ```

   - **Why this exists:** Added 2026-04-09 after a peer-review COI disclosure was persisted to Scratchpad in one session and silently destroyed by a later session's cleanup pass before the user needed it. The unconditional-read requirement prevents the "I don't remember writing there" failure from recurring.

11. **Update Works in Progress:**
   - **"Last updated" timestamp bump is handled at Step 13b**, not here. Moved after Step 13 so bumping doesn't depend on predicting whether loop routing will modify planning files.
   - **⛔ CURRENT-line check runs FIRST — before any skip rule below fires.** Grep WIP for `**Current:**` lines. For each one whose subject overlaps this session's project link (same trip, same initiative, same area), verify it is accurate as of today; run `date +"%a %d %b"` for the day-of-week rather than trusting internal computation. **If the line asserts a fact you cannot verify from this session's tool output or the user's words — a physical location, a phase, a status — do NOT rewrite it from a plan or an itinerary; surface it to the user as a one-line question.** A stale assertion-from-plan and a fresh one are the same error. Display one of: `CURRENT check: <heading> — accurate ✓` · `CURRENT check: <heading> — stale, surfaced to user` · `CURRENT check: no Current line overlaps this session's project`. **Why this is hoisted:** the check used to live below, inside the body that the skip rules short-circuit — so a session whose project link resolved to an area home never ran it, even when a WIP entry tracking that exact subject had gone stale. The skip rules govern whether you *write* to a WIP entry; they must not govern whether you *look* at one.
   - **If there is no related project to update at all, skip the rest of Step 11** (proceed to Step 12).
   - **Shipped one-shot work (published post, completed migration, resolved bug):** Do not create a new WIP entry or a new project file. Point the session log's `**Project:**` field at an existing area hub per the Shipped-one-shot-work rule in `_shared-rules.md` §2. Skip the rest of Step 11 (timestamp bump handled at Step 13b).
   - **Project link points at an area `_Index` (or any area home that doesn't appear as a WIP entry):** Skip the rest of Step 11 by definition — there's no WIP entry to update. The file-level "Last updated" bump at Step 13b is the WIP signal. This applies when the work is operational/area-hosted (e.g. updating a strategy doc, area hub) rather than tracked as in-flight project work. Distinct from the "no related project at all" case above — here the project link IS valid, it just lives in 04 Areas, not in WIP. **Exception:** if the linked area doc itself contains a `## Session History` section (typical for a project hub recently completed/relocated by `/complete-project`), still run the "Append to the project hub's Session History" sub-step for it — the skip governs WIP-entry edits, not the hub's durable session record. (Caught 2026-07-16: a completion session's own closure park would otherwise leave the completed project's Session History without its closing entry.)
   - **Multi-project operational sessions — link only entries that received a content write.** When this session is itself an operational pass (e.g. /goodnight, /morning, /weekly-review running inside another session — any session that touches several projects' state without being scoped to one), iterate the rest of Step 11 across each touched project, but only add a session link to entries where **this session wrote new content into the entry's section**. Reading/summarising the entry in a landscape pass does not count. The file-level "Last updated" bump at Step 13b does not count either — that's unconditional and carries no per-entry signal. **The check is mechanism-independent** — it includes the Edit tool, the Write tool, Bash heredoc/sed/awk targeting WIP, and any `mcp__obsidian__*` tool (e.g. `mcp__obsidian__obsidian_update_note`, `mcp__obsidian__obsidian_search_replace`) that wrote to WIP. **Observable verification:** scan the conversation for tool calls whose target file is `01 Now/Works in Progress.md` — *regardless of which tool* — and for each one, check whether the change fell inside a project entry's heading-to-next-heading slice (Status / Last / Next / narrative content under `### Project Name`). Entries with no such write get no session link from this session; the file-level "Last updated" bump is their only signal. The 3-link FIFO cap is precious — don't burn slots on operational sessions that only traversed an entry.
   - Read `{VAULT}/01 Now/Works in Progress.md`
   - **Write mechanism:** apply every WIP edit in this step through `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5 for invocation + exit-code handling). The enumeration, FIFO, and verification rules below are mechanism-independent; only the write call changes.
   - Find the relevant project section (or sections — multi-project sessions iterate this routine across each touched project)
   - Update status with:
     - **Last:** [Today's date and time from step 1] - [Brief description of progress]
     - **Weekday verification:** When writing a weekday+date pair into Last (e.g. "Thu 16 Jul 2026"), verify the weekday with `date -d '<date>' +%A` first, or write the date without a weekday — never map date→weekday from internal computation. (Caught 2026-07-16: a park stamped "Wed 16 Jul" on a Thursday; the audit sub-agent had to fix it.)
     - **Last-field cap:** Single current entry — replace, don't chain. The Last field carries only the most recent session's update. **Do NOT prepend "Earlier [date]..." blocks for prior entries** — when updating Last, replace the prior value outright. Prior Last content is already preserved verbatim in the session-log archive and referenced by the 3-link session FIFO below; duplicating it inline as "Earlier" chains is the Last-field accretion anti-pattern. This is the prose-side parallel to the FIFO cap on session links: both rules keep WIP as a current-state dashboard, not a running log. If a prior entry contained durable thinking/lessons/decisions that belong in a project or area doc, migrate those to their natural home *before* replacing the Last field — the trimming check is "has the content been captured in an SSOT elsewhere?", not "does Last look tidy?" **SSOT here means a project or area doc — NOT auto-memory (which holds behavioural lessons, not project/commit records) and NOT a session log (a write-once archival record, not a canonical project SSOT). Before trimming durable identifiers (commit hashes, PR#s, issue#s, decisions) out of WIP, grep each dropped identifier against the target doc and display the verification block (mirror of the cited-identifier check below). Trimming on "I think it's captured" without the grep is the failure mode.**
     - **⛔ Verify cited identifiers before replacing Last.** When the prior Last cites identifiers (commit hashes, `[[wikilinks]]`, session refs like `Session N`, file paths), enumerate each and run a verification command. Display the verification block in your response **before** `locked-edit.sh` replaces Last. Verification commands by shape:
       - **Commit hash:** `git -C <repo> log --oneline | grep <hash>`
       - **Session reference:** `grep '^## Session <N> ' "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md"` (`<N>` = the literal cited session number)
       - **Wikilink:** `ls "{VAULT}/<path>.md"` (or `head` if confirming content)
       - **File path:** `ls <path>`

       Display format (mirror of FIFO check pattern):
       ```
       Cited-identifier check:
       - <identifier> → <command> → ✓ verified
       - <identifier> → <command> → ✓ verified
       ```
       or, for the nil case: `Cited-identifier check: No cited identifiers in prior Last (thin entry)`.

       If any identifier fails verification, do **not** replace — migrate the unverified content to its cited home first, then re-verify. **Why:** lucky-right replacements (where the SSOT happens to exist) hide the failure mode. Repeated park audits have caught this exact shortcut. Mechanical verification turns "I think the content is captured" into "the content is observably captured." Specific literal-output spec added (mirroring FIFO check) after audits found vague "verification block" wording produced unreliable firing.
     - **Next:** Three cases:
       1. **Has project/area doc:** `→ [[03 Projects/Project Name]]` — pointer only, project doc is SSOT for its task queue
       2. **No doc, has next action:** Single next action (one line max — if it needs more, create a project doc)
       3. **No doc, work complete:** Omit Next
       Never a queue — one pointer or one action. **Replace each park, don't inherit.** If a prior session left a queue in Next, dedup-check each item against canonical SSOT (This Week.md, Tickler, project doc, area files) and route any unrouted items (per Step 13 routing rules) before collapsing Next to the pointer/action form. **Why:** Next is a current-state field, like Last; inheriting a stale queue duplicates task tracking and risks letting items rot in WIP if they were never routed elsewhere. Mirrors the Last-field "replace, don't chain" rule above.
     - Add link to session: `→ [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session N)` — file-level, no `#` anchor; the plain-text session number is what `/pickup` reads
     - **⛔ FIFO cap + verification:** Apply the WIP session-link FIFO cap per `_shared-rules.md` §6 — the SSOT for both the cap rule (3 links, trim oldest by date, never trim non-session-log reference links) and the mechanical awk verification snippet. After the WIP edit, run §6's verification — do NOT trust your edit; count the actual lines in the file. Required output: `FIFO check: N/3 session links`. If more than 3, fix before proceeding. (§6 is already in context — Step 0 reads `_shared-rules.md` in full.)
     - **Append to the project hub's Session History.** If the Step 5 project link resolves to a hub file (typically `03 Projects/...`) containing a `## Session History` section, append the same session link there — `- [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session N) — one-line gloss` — via `locked-edit.sh --replace` on the section's current tail lines, NOT `--append` (Session History isn't guaranteed to be the file's last section). If the hub has no `## Session History` section, skip without creating one (older hubs may predate the template; don't impose structure). Also skip if the session's link is already present in the section — a merge (Step 2) re-runs Step 11 with the same N. This is the durable per-project record that justifies the lossy 3-link FIFO above — the FIFO's rationale ("session history lives in the project hub pages") needs a writer, and this is it.
   - **Check CURRENT line:** already performed at the top of this step (hoisted above the skip rules). Apply any *writable* correction it identified here; unverifiable assertions stay surfaced to the user, not rewritten.

12. **Trace reference graph for status changes (enumerate in main session, delegate propagation to sub-agent):**

   The enumeration discipline stays in the main session — it's the load-bearing checkpoint that defends against silent miss-pattern. The grep + propagation work delegates to a fresh sub-agent for thoroughness without main-session fatigue.

   **Write mechanism.** Stale-reference fixes to planning files go through `locked-edit.sh --replace`, not the Edit tool (see `_shared-rules.md` §5).

   **⛔ Do NOT write to the session log's `### Files Updated` in this step.** This step edits vault files, so the urge to record them as you go is strong — resist it. **Step 13a is the sole writer** of that section, and it already collects everything Steps 11-13 touched. Two writers is the failure mode: 13a's dedup only protects against collisions it can see, so a mid-step append lands a duplicate that someone then has to merge by hand. Carry (e)'s file list forward and let 13a write it once.

   **(a) Enumerate identifiers (MAIN SESSION, required checkpoint).** A "status change" includes: tasks completed, bookings made/cancelled, decisions finalised, items purchased, accounts set up, **WIP tier demotions/promotions** (Active↔Backlog↔Cold — these must propagate to the project hub's own `**Status:**` field, not just the WIP entry), **and any cross-referenced value that changed** (counts, dates, amounts, names, event lists, and factual claims the session reversed or refined — a property/characteristic/spec, not just status or dates). List every identifier value that changed during the session as `old → new` pairs. This enumeration must appear in your response *before* the sub-agent despatch.

   **Out-of-vault cross-references (skill-development sessions — the dominant miss here).** When the session edited command/skill files (`~/.claude/commands/`, `~/repos/*/.claude/commands/`) and changed a fact those files assert *about each other* (one skill documenting another's step / flag / behaviour — e.g. `NEW: /morning is now a provenance-flag processor — asserted in provenance.md`), that fact lives **outside** the vault, where (d)'s vault-rooted `rg` never reaches. **Handle it in the main session, not the (d) sub-agent:** propagating into a command file is a *skill edit*, which the propagation sub-agent is no more permitted to make than the Step 14 audit sub-agent (the same no-direct-skill-edit rule binds both). So grep the command dir(s) yourself (`rg -i '<fact>' ~/.claude/commands ~/repos/*/.claude/commands` — expand the glob to existing roots first; drop `--type md` if a changed fact lives in a script/config, not a doc), triage per §12, apply mechanical propagation inline, and surface any non-mechanical skill change to Step 15 to log for weekly processing rather than editing it. Out-of-vault identifiers never enter the (d) despatch, so exclude them from (c)'s `enumeration → prompt` count (display `(+K out-of-vault, handled in-session)` beside it); record them instead in the (e) output as `Out-of-vault refs: <N files updated / none>`. This leaves the (d) sub-agent purely vault-scoped — its "whole live vault" scope and hit-list wording below stay literally correct.

   **Enumerate what the session *did*, not only what park *edited*.** World-state consequences of the session's actions are status changes even when no token visibly changed in the files you touched. If the session sent a message, completed a task, or made/cancelled a booking, the *entities that action acted on* changed state — a task to "decline the quotes" completing means the **providers** went pending → declined, and a hub may still frame the action as upcoming. Enumerate the subject entity's state change (`provider: live quote → declined`), not merely the task checkbox (often contained to one planning file, which makes "no values changed" tempting and wrong). This is the Layer-3 world-state frame Step 14's audit brief already applies; running it here lets this cheap pass catch what otherwise only the expensive audit does. The Step 5 Project-link hub is a guaranteed grep target for such changes.

   **The nil case is not a free pass.** "No identifier values changed" is a positive claim requiring the explicit checklist. Format the nil case as an enumerated checklist, not a bare assertion:

   ```
   Changed values:
   - "old value" → "new value" (where: file path)
   - NEW: "value" introduced (where: file path)
   - NEW (option/alternative on a pre-existing decision): "<option>" under anchor "<decision/record key>" (where: file path)
   [OR (nil case)]
   - Row removals / replacements: none
   - Content corrections (misspellings, wrong locations, wrong dates): none
   - Factual/claim corrections (a property/characteristic the session reversed or refined): none
   - Naming changes: none
   - Status flips: none
   - World-state changes from session actions (a task completed / message sent / booking made → the affected entity's state, often still framed as "upcoming" or "pending" in a hub): none
   - Section relocations between files: none
   - New option/alternative added to a pre-existing decision/record (propagate via its anchor, not the new value): none
   - Commits pushed this session (each hash is its own identifier — see the push-side rule below): none
   → No identifier values changed.
   ```

   **Commits pushed this session are their own identifier class** — enumerate each hash and check the repository's hub per **`_shared-rules.md` §17** (already in context — Step 0 reads it in full). A pushed commit has no textual footprint in the vault, so no content grep reaches the hub that is supposed to record it.

   **A `NEW:` entry that is an option/alternative added to a *pre-existing* decision/record (one the session did not create from scratch this session) is never nil — enumerate it with the decision's *anchor* (route/decision/record key, e.g. `<ORIGIN>→<DEST>`), not just the new value.** Sibling docs that still lack the new option contain the anchor but not the new value, so the anchor — not the option text — is the propagation join key.

   **A `NEW:` member added to a documented set anchors on the *container*, not the member or its topic** — per `_shared-rules.md` §12's grep-target selection rule (read it there; it is the SSOT and `/audit` + `/complete-project` share it). **Checkable at this step:** for every member added to a set — including one *relocated into* it from elsewhere — the enumeration carries the container's name as an anchor.

   **For file moves specifically, add plain-text path strings to the enumeration, not just filenames.** Companion docs (transcripts, notes, metadata sidecars) often embed full `**Source:** /path/to/file.ext` references that won't match a filename-only grep or wikilink-shaped queries. When a file moves, both the filename and the full old path go in the enumeration as separate identifiers.

   **Numeric/limit/count changes carry a second identifier: the constrained subject.** For a cap, count, or limit change (e.g. a "max 2" → "max 3"), restatements elsewhere often share no token with the changed value ("the 2 most recent", "two latest"). Enumerate the *subject phrase* (the capped noun phrase, e.g. `session link`) alongside the `old → new` pair — the subject is what sibling restatements share; the value is what drifted. The sub-agent greps it case-insensitively in addition to the old literal value.

   **Anchor-grep rule for relocated targets (not just file moves).** When a section, queue, or SSOT moves *out* of a document — even if the document itself stays put — the moved-from document's inbound `[[wikilink]]` (and its path forms) becomes a standalone identifier. Grep the **bare anchor with no keyword conjunction** (e.g. `rg -Fi '[[03 Projects/Project Name]]'` — `-i` catches lowercased prose path forms), NOT the anchor AND a topic keyword. A keyword conjunction (anchor + `queue`/`backlog`/`<section name>`) silently drops semantic-variant references — a line pointing at the moved-from doc as "the project doc" / "full spec here" / "see [[…]]" won't match anchor-plus-keyword but is exactly the stale pointer that now misdirects. The bare inbound link is the join key; the surrounding prose is not. Assess each hit per the stale / historical / unrelated rule in (d) — bare-anchor grep returns legitimate navigation links too, so triage, don't blind-rewrite.

   **(b) If the enumeration is the nil case, skip the sub-agent and display:**

   ```
   ✓ Reference graph: No identifier values changed
   ```

   **Do not nil-skip a `NEW:` option/alternative on a pre-existing decision, and do not discharge it by self-certifying "already propagated" from memory** — it is non-nil per (a) and propagates via the (d) sub-agent. (A genuinely standalone new fact with no pre-existing cross-referenced home is nil-skippable as normal.)

   **(c) Identifier count integrity check before despatch.**

   Count the identifiers in your enumeration block. When you write the sub-agent prompt in (d), embed the enumeration verbatim — do NOT re-construct from memory. Main-session fatigue at Step 12 (after ~12 steps and several CHECKPOINTs) is documented; typing identifiers into a prompt from memory has the same drop-rate as typing them into a grep alternation pattern. Display:

   ```
   Identifier count check: enumeration N → prompt N ✓
   ```

   If mismatch, regenerate the prompt from the enumeration block, not from memory.

   **(d) Spawn the propagation sub-agent** with `subagent_type: "general-purpose"`, foreground. The prompt must be **self-contained** — every value the sub-agent needs must be embedded verbatim. Include:

   - **Enumerated identifiers** as `old → new` pairs — copied verbatim from your (a) enumeration block, not retyped from memory
   - **Path-expansion rule (re-stated at execution point):** "For any enumerated identifier that is a file rename/move/delete, also grep for plausible full-path forms — old absolute path, old vault-relative path, and the bare filename without extension. Plain-text path references inside non-link contexts (e.g. `**Source:** /path/to/file.ext` in transcripts, embedded YAML, fenced code blocks) are NOT surfaced by structural link-integrity queries — only grep catches them. Iterate each form as a separate grep call. For a section/queue/SSOT that relocated *out* of a still-existing document, also grep that document's bare inbound anchor (`[[doc]]` and its path forms) with NO keyword conjunction — per the anchor-grep rule in (a); keyword-qualified greps drop semantic-variant pointers ('the project doc', 'full spec here')."
   - **NEW attached-option rule:** "For any enumerated `NEW:` option/alternative added to a pre-existing decision/record, grep the decision's **anchor** (the route/decision/record key carried in the enumeration) across live docs — NOT only the new option text, which sibling docs that still lack the option won't contain. Read every live hit and propagate the new option into prose AND the parallel table-row / list / index representations of that decision."
   - **Numeric-change subject rule:** "For any enumerated numeric/limit/count change, also grep the constrained subject phrase (carried in the enumeration) case-insensitively — restatements of a cap/count often share no token with the changed number ('max 2' vs '2 most recent'). Triage subject-phrase hits per §12 as usual."
   - **Vault path** (resolved): the absolute path
   - **Archive-exclusion glob:** `!**/06 Archive/**`
   - **Tool guidance:** "Use `rg --type md -i` (ripgrep, respects `.gitignore`, skips `.git/` auto-save). The `-i` is load-bearing: a session-derived identifier is often lowercase while the stale copy capitalises it (or vice-versa), and the case-sensitive default silently drops such hits — the later case-insensitive closure pass then catches what this step should have. Do not use bare `grep -r` — it crawls `.git/` and takes minutes on long-lived vaults. If `rg` is not installed, the fallback is `grep -rn -i --include='*.md' --exclude-dir=.git --exclude-dir='06 Archive' <vault> | grep -v -e '/\.git/' -e '/06 Archive/'` — `--exclude-dir` is a silent no-op when `grep` resolves to ugrep, so the trailing `| grep -v` filter is the correctness backstop; translate any other rg-syntax globs in this prompt the same way."
   - **No regex alternation from memory when N>3.** "If more than three identifiers, iterate each as a separate grep call. Typed-from-memory alternation silently drops entries."
   - **Scope discipline — the vault-wide `rg` hit-set IS the scope.** "Do NOT narrow the search to a hand-picked list of likely files, and if the despatch brief offers example candidate files, treat them as a warm-start hint, never as the search boundary. A candidate list anchors coverage and silently drops stale refs in folders you didn't predict (e.g. `03 Projects/Cold/`, deep area subtrees, a second occurrence in a file you already edited). Run the case-insensitive `rg` over the whole live vault per identifier, then triage EVERY returned hit. 'No remaining hits' is a completeness claim you must *earn* by triaging the full hit-list — not by checking the files you expected to matter."
   - **Already-updated docs are NOT complete.** "For any identifier flagged in the enumeration as 'already updated in doc X' (a fix the session made inline), do NOT treat doc X as done — re-grep doc X for OTHER instances of the same stale claim. A single in-session edit fixes one occurrence; the same fact is often asserted in several places within one document (summary callout + detail table + rationale prose) **and in different words** — a section header or bolded lead carrying the same current-state framing (e.g. a \"Current…\"/\"Now\"/\"Status\" section), an admonition/callout title line (\`> [!note]\`/\`> [!warning]\` headers), or an inbound cross-reference parenthetical pointing at the rewritten passage (e.g. \`(<status> <date> — see <section> below)\`) is the same stale claim even when it shares no token with the changed marker. When you rewrite a callout body, re-read its own title line and any same-file line that points at it (e.g. lines containing \`see\`/\`below\`/\`above\` or the callout's title) — update such a line only if it restates the changed fact; a bare navigation pointer carrying no status/date is not stale, leave it. Re-grep for the claim's *meaning*, not just the literal changed string, and scan the structure (headings + leads + callout titles) of every session-edited doc, not only token matches. (Known limit: a doc with stale current-state but no token hit is never opened by the per-identifier grep — this catches restatements inside docs you're already editing, not silent stragglers elsewhere.) Include every session-edited doc in the per-identifier grep pass, not just the unedited rest of the vault."
   - **For file-path identifier changes (rename, move, delete):** "After the per-identifier grep pass, run the vault's structural link-integrity query as a post-check (e.g. `obsidian unresolved` for an Obsidian vault; `git grep` + LSP find-references for code repos; broken-link reports for wikis). The grep catches plain-text path references; the structural query catches wikilink/symlink integrity. Both are needed — neither alone is sufficient. Watch for basename collisions: if `new-name.md` and `old-name.md` share a basename with some unrelated file, structural queries may resolve a `[[old-name]]` link to the wrong file rather than flagging unresolved. Flag any ambiguous basename collisions in the report."
   - **Authority:** "For each grep hit, read the file and triage it per `_shared-rules.md §12` (in `~/.claude/commands/` or `{VAULT}/.claude/commands/`) (grep-hit triage) — **read §12 yourself** before triaging. In brief: stale cross-reference → update; live locator (a path a current workflow resolves to re-read, e.g. a provenance log's path column) → update the locator on move/rename, never the content hash/timestamp/proof; historical record of what was said/sent/observed → leave; different context sharing the identifier → leave; ambiguous → report, don't guess. Dated rolling current-state fields an owning rule replaces (e.g. WIP `**Last:**`) are stale cross-references when the session changed their underlying state, not historical records — the enclosing artefact governs (a 'current' line inside a frozen snapshot stays historical). Display grep results in the report (output proves the grep ran)."
   - **Co-located stamp bump:** "For any doc you edit, check for a co-located `Last updated:` / `Last update:` date stamp (top-of-file or a Status/Current section header) and bump it to today's date in the same edit. Editing a doc's content while leaving its own currency stamp stale is itself a stale cross-reference (per §12); the per-identifier grep won't catch it because the stamp shares no token with the changed value."
   - **Report format expected back:** "Per-identifier: `[identifier]: N files updated` (with file list + brief change description), OR `[identifier]: no living refs found`. **Plus the full vault-wide `rg` hit-list for each identifier — every path the grep returned, each tagged `updated` / `updated (stale predicate)` / `left (historical)` / `left (different context)` / `left (timeless list)` — as completeness evidence; a bare 'no remaining hits' without the enumerated hit-list is not accepted. The `(stale predicate)` / `(timeless list)` tags are the enforcement surface for the §12 enumeration-predicate category — an enumeration hit must carry one of them.** Plus structural-query results if file moves were in scope. Plus any basename-collision flags."

   **(e) Display result based on sub-agent report:**

   ```
   ✓ Reference graph: [N] files updated for [identifier] status change
   - [file1] - [what changed]
   - [file2] - [what changed]
   ```

   **This step exists because:** WIP is one file. Status changes typically touch WIP, the project hub, area detail files, the tickler, This Week.md, and potentially other planning docs. Updating only WIP leaves stale state everywhere else. Without this step, the user has to manually ask for a full update pass after every status change.

13. **Route ALL open loops to SSOT:**
   Every open loop from the session must land in a canonical location. Session docs are plain-text records, not task trackers. Route automatically (no per-item prompting):

   **Write mechanism.** Writes to This Week.md, Tasks.md, Tickler.md, and project/area files go through `locked-edit.sh`, not the Edit tool (see `_shared-rules.md` §5). For This Week.md day-section insertions, use `--replace` (read the target day section, replace with section + new `- [ ]` line) — NOT `--append` (which adds at EOF, outside any day section). For Tasks.md, `--append` is correct. For checkbox flips and project/area edits, use `--replace`.

   **Completed-item closure pass (run BEFORE routing new loops):**

   For work the session completed, grep planning docs for unchecked items whose text matches and flip them to `[x]`. Scope (entire rolling-window file, not just past days — the motivating failure case was an unchecked future-day item):

   - `{VAULT}/01 Now/This Week.md` — whole file (past 3 + today + future 6 day sections per `_shared-rules.md` §9)
   - `{VAULT}/01 Now/Tasks.md` (if present)
   - `{VAULT}/01 Now/Tickler.md` (if present) — whole file. A session that *resolves a documented problem* often closes a future-dated "investigate X" / "look into Y" item parked here; because the item is date-deferred it won't surface in This Week.md, so the reference-graph pass (Step 12) and a This-Week-only grep both miss it. **Flip a Tickler match only after confirming it is the item the session actually resolved** — a false-positive flip here silently suppresses deliberately-deferred future work that won't resurface on its date (a worse failure than in This Week.md, which the user re-reads daily).
   - Project/area hubs the session wrote to inline (enumerate from the session log's Files Updated list as written at Step 7 — limit to `03 Projects/` and `04 Areas/` paths). Step 13a's backfill runs later in /park; don't wait for it.

   Use a distinctive substring for the grep — exact-text match is too brittle when the user copy-pastes loosely. Derive substrings from the session's *action* (the verb, e.g. "cancel") as well as its nouns/identifiers — stale tasks are often phrased as the action that was performed, not the artefact. **Run the grep against each listed file yourself — Step 12's reference-graph propagation does NOT satisfy this pass; it updates changed values, it does not flip completed `[ ]` checkboxes.** Run one grep call per planning-doc file:

   ```bash
   # Session completed something with identifier "FOO-123".
   # Use -i (case-insensitive): a substring derived from the session topic is
   # often lowercase, but the task text may capitalise it — case-sensitive
   # grep would silently miss the match.
   # [[:space:]] not \s: \s is a GNU extension — BSD/macOS grep silently matches
   # nothing on it, turning every closure pass into a false nil.
   # Tasks.md / Tickler.md are optional — skip absent files and note "absent" in the checkpoint.
   grep -niE '^[[:space:]]*-[[:space:]]*\[ \].*FOO-123' "{VAULT}/01 Now/This Week.md"
   grep -niE '^[[:space:]]*-[[:space:]]*\[ \].*FOO-123' "{VAULT}/01 Now/Tasks.md"
   grep -niE '^[[:space:]]*-[[:space:]]*\[ \].*FOO-123' "{VAULT}/01 Now/Tickler.md"
   # ...per relevant project hub
   ```

   For each match, flip `[ ]` → `[x]` via `locked-edit.sh --replace` (see `_shared-rules.md` §5) and append a backlink: `→ [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session N)` (skip the backlink if one already exists from a prior in-session edit).

   **⛔ CHECKPOINT:** Display one of, with the grep evidence as the observable (mirrors Step 13's zero-routing checkpoint pattern):

   ```
   ✓ Closed N item(s) in planning docs:
   - <file>:<line> "<item text>" — flipped
   ```

   ```
   ✓ No completed items found in planning docs
   Grepped with substring "<substring>":
   - This Week.md → no [ ] match
   - Tasks.md → no [ ] match
   - Tickler.md → no [ ] match
   - <hub path> → no [ ] match
   ```

   Without grep-evidence lines, the nil case is reasoning-from-memory and ships unverified.

   **Why this exists:** /park otherwise only handles NEW loops the session created. When the user copy-pastes a task FROM a planning doc into the conversation and the session closes it, the original `[ ]` lives on — the planning doc accumulates stale unchecked items pointing at completed work. Caught by audit in a session where a multi-host security-patch batch landed but the corresponding `[ ]` in the rolling weekly plan (on a future-day section, not the session day) stayed unchecked; the audit's Layer 3 stale-state pass caught it. Closing the loop in /park instead of relying on audit makes the check mechanical and routine rather than depending on a sub-agent re-discovery. **Window scoping note:** the motivating case lived on a future day section, which is why the scope is the whole This Week.md file, not a past-only window.

   **Adjacent-open-items sweep (surface, don't action — run after the closure pass):**

   The closure pass above keys on what the session *finished*. It has no signal for a still-open task that targets a file the session *edited for a different reason*. For each vault content file this session **edited** (from the Step 4(a) enumeration; skip the session log and the planning files themselves), grep the planning docs for unchecked `[ ]` items that mention that file — by basename/slug, in either the item text or its `→ [[link]]` target (an item may link to an area hub while naming the file in its text, so match the text too):

   ```bash
   # Per edited content file, grep planning docs for open items naming it.
   grep -niE '^[[:space:]]*-[[:space:]]*\[ \].*<edited-file-basename-or-slug>' "{VAULT}/01 Now/Tasks.md" "{VAULT}/01 Now/This Week.md" "{VAULT}/01 Now/Tickler.md"
   ```

   These are **not** items the session completed — **do not flip them, do not action them.** They are adjacent opportunities: a tracked task pointing at a file you just had open. **Surface each in the session's Pickup Context** (e.g. "Adjacent open task if you revisit this file: …") so a future pickup sees it and so the Pickup Context line doesn't overstate closure. The session's scope was its own work, not the backlog for every file it touched — hence surface, not action.

   **⛔ CHECKPOINT:** Display one of:
   ```
   ✓ Adjacent-open-items: none found for edited files
   ```
   ```
   ✓ Adjacent-open-items: N surfaced to Pickup Context
   - <file>:<line> "<item text>" → targets <edited file>
   ```

   **Why this exists:** a session can edit a file that already has an open task against it; the completed-item pass won't catch that task (nothing was completed), so Pickup Context can read "nothing pending" while a tracked item targets the very file just changed. This is a completeness gap, not a propagation miss (no status changed) — surfacing it (not actioning it) closes the gap without scope creep.

   **Routing logic (applied to each open loop):**

   1. **Parse for date patterns** (reuse existing date parsing):
      - "week of [date]" → that Monday
      - "after [date]" / "from [date]" → that date
      - "[month] [day]" or "[day] [month]" → YYYY-MM-DD
      - "next week" → next Monday
      - "next month" → 1st of next month

   2. **If explicit future date found** → Tickler via write-tickler script:
      ```bash
      "{VAULT}/.claude/scripts/write-tickler.sh" "{VAULT}/01 Now/Tickler.md" "YYYY-MM-DD" "- [ ] [Loop text] → [[06 Archive/Claude/Session Logs/YYYY-MM-DD]] (Session N - Topic)"
      ```

   3. **If no date + This Week.md is current** (today falls within date range) → add to tomorrow's section in This Week.md (or today's, if parking before 12:00 local time) via `locked-edit.sh --replace` (per write-mechanism note above). Format: `- [ ] [Loop text] → [[project/area doc]]`. Append a project/area link: `→ [[03 Projects/...]]`, `→ [[04 Areas/...]]`, or `→ [[01 Now/Works in Progress#Heading]]` if tracked in WIP. The session's Project link (Step 5) identifies the target. No link for items with no project context.

      **Exception — trigger-contingent loops fall through to rule 4.** If the loop fires on a downstream trigger event rather than calendar time (e.g. "next time X runs, verify Y" or "test Z when next encountering W"), skip rule 3 and fall through to rule 4 (project file). Rule 3 assumes loops are actionable on a specific day; trigger-contingent loops aren't, and surfacing them on tomorrow's plan creates false urgency for work that shouldn't be date-bound at all. If the session has no Project link either, route directly to the Tickler with the date `today + 10 days` (computed via `date -d '+10 days' +"%Y-%m-%d"` — GNU date; on BSD/macOS use `date -v+10d +"%Y-%m-%d"`) via write-tickler.sh — not rule 5, because rule 5's condition requires This Week.md to be stale, which isn't the trigger case here.

   **Deadline tokens force a dated surface** — per **`_shared-rules.md` §18** (already in context — Step 0 reads it in full). This skill's undated sink is rule 4: `→ Project: [Name]` alone is the failure for a deadline-bearing loop, which must land in This Week's day section or the Tickler instead.

   4. **If no date + session has a Project link** → update that project file's next-action section. Deterministic target: prefer an existing `## Next Actions`, then `## Open Loops`; if neither exists, create `## Next Actions` above `## Session History` (or at EOF). Don't improvise other section names — consistency across hubs is what makes the queue greppable.

   5. **If no date + no project + This Week.md stale/missing** → Tickler with tomorrow's date via write-tickler script

   **Dedup check:** Before writing to any target file, grep the item text (or a distinctive substring) across **all canonical SSOT locations** for open loops — `01 Now/This Week.md`, `01 Now/Tickler.md`, and any project file the loop could plausibly land in. Tickler especially: prior sessions may have routed the same loop to a future date, and the current park's own tracking won't surface that without an explicit grep. If found in any SSOT, skip with `✓ Skipped (already present in <file>)`. Items may have been routed by the current session pre-park, by a prior session, or manually added.

   **After routing, display brief summary:**
   ```
   ✓ Routed: [item] → This Week (Thu)
   ✓ Routed: [item] → Tickler (2026-03-15)
   ✓ Routed: [item] → Project: [Name]
   ✓ Skipped (already present): [item]
   ```

   **⛔ Zero-routing checkpoint.** Always append the supporting observable to `✓ No open loops to route`. Two valid forms:
   - Loops were deduped against existing SSOT → cite the grep match: `found in [file]:[line]: "[text]"`
   - Session produced no loops → cite the section text: `session log: "None — work completed"`

   Without an observable, the line is reasoning-from-memory and can ship without anyone verifying the check actually ran.

13a. **Backfill "Files Updated" in session log:**
   - Steps 11-13 modify vault files (WIP, This Week, Tickler, project hubs) that aren't known at step 8 when the session log is written. Backfill these into the session log's "### Files Updated" section.
   - Collect all files modified during steps 11-13 (WIP update, reference graph tracing, open loop routing)
   - **Exclude the Step 13b WIP "Last updated" timestamp bump.** That bump is unconditional meta-bookkeeping, not session content — it fires on every park (including pure no-write sessions), so recording it would add a near-identical "Works in Progress.md - timestamp bump" line to every session log: noise, not signal. A Step 11 *content* write to WIP (Status/Last/Next/narrative under a project heading) IS a Files Updated entry; the bare timestamp bump alone is not. (If Step 11 wrote content, that content edit is what gets backfilled — describe the content change, not the bump.)
   - **Dedup check:** Before calling the backfill script, grep the session's "Files Updated" section for each file path. If already listed (from a prior park/audit backfill of the same session), skip it. This matters when a session is parked, audited, and re-merged — multiple backfill passes target the same session. (The script also dedups by normalised path, but silently, and it *discards the incoming description* on a hit rather than merging it — so the manual grep is what surfaces the hit to you, and it feeds the description-completeness check below. Don't delete it as redundant.)
   - **Description-completeness check on dedup hit:** When the dedup skip fires for a file already listed, check whether the existing description covers the new edit. If not (i.e. /park itself made an additional change to a file already touched in-session, e.g. a Step 12 reference-graph wikilink fix), append the new edit detail to the existing entry's description by rewriting the section via `update-session-section.sh … "Files Updated" --replace`, rather than skipping silently. **Not the Edit tool** — session-log edits go through the locking script (same rule as Step 14's brief and `_shared-rules.md` §5); a lockless edit here races a concurrent `/park` or `/goodnight`. Filename dedup prevents redundant entries; description completeness prevents silent under-reporting of what actually changed.
   - Use the backfill-files-updated script:
     ```bash
     cat << 'EOF' | "{VAULT}/.claude/scripts/backfill-files-updated.sh" "{VAULT}/06 Archive/Claude/Session Logs/YYYY-MM-DD.md" N
     - 01 Now/Works in Progress.md - [what changed]
     - 01 Now/This Week.md - [what changed]
     EOF
     ```
     Where `N` is the current session number. The script handles:
     - File locking (flock) for concurrent safety
     - Replacing placeholder "None" lines (bare `None`, `- None`, `- None (explanation)`) or appending after existing entries
     - Finding the correct section boundary within the session block
   - Only include files actually modified — if steps 11-13 didn't touch a file, don't list it
   - **Why this exists:** The session log is written at step 8 before steps 11-13 run, so "Files Updated" is always incomplete without this backfill. This was caught by audit — sessions were reporting "Files Updated: None" when WIP, This Week, and project files had all been modified.
   - **Also reconcile the session log against inline closures.** The `Next Steps / Open Loops` and `Pickup Context` sections were written at Step 8, before Steps 11-13 ran — same staleness root cause as the Files Updated backfill above. If any Next Steps item written at Step 8 is now *done* (e.g. a loop you closed inline at Step 13 rather than routing to a future date), rewrite `### Next Steps / Open Loops` via `update-session-section.sh … N "Next Steps / Open Loops" --replace` with the completed item omitted, and update any `**For next session:**` line in Pickup Context that referenced it. (Distinct from Step 4's VERIFY pass, which only fires when re-parking an already-parked session and runs before routing.) **Why this exists:** caught by audit 2026-06-02 — a memory-update loop listed in Next Steps was closed inline at Step 13, leaving the session log claiming the same task both done (Files Updated) and to-do (Next Steps).

13b. **Bump WIP "Last updated" timestamp:**
   - **Unconditional bump.** Replace the existing `Last updated: ...` line at the top of `01 Now/Works in Progress.md` with the current timestamp (e.g. `Last updated: YYYY-MM-DD HH:MM TZ`) **via `locked-edit.sh --replace`** (per `_shared-rules.md` §5), NOT the Edit tool. Run `date +"%Y-%m-%d %H:%M %Z"` to obtain the value — do NOT reuse Step 1's park-start time or estimate elapsed time (the auto-date reflex writes a fabricated timestamp; caught 2026-06-12). No "did we modify planning files?" check — by definition something was captured; the imperceptible cost of an over-bumped timestamp on a pure no-write session is preferable to the prediction-failure mode the old conditional produced.
   - **Concurrent-write handling.** Because `locked-edit.sh` serialises through the WIP lock, there's no "modified since read" fight to lose. If it exits 2 (no match), a parallel `/park` already replaced the `Last updated:` line; re-Read the line and, if the timestamp is *within this park's window*, accept the concurrent bump rather than re-replacing — the intent (WIP reflects recent activity) is already satisfied. Display the alternate checkpoint: `✓ WIP timestamp: current at <value> (concurrent-session bump within window; own bump declined)`.
   - **Not a Files Updated entry.** This bump is excluded from the session log's `### Files Updated` section (see Step 13a exclusion) — it's unconditional bookkeeping, not content. Don't backfill it, and the Step 14 audit should not flag its absence.
   - **⛔ CHECKPOINT:** Display `✓ WIP timestamp bumped: YYYY-MM-DD HH:MM TZ` (or the concurrent-write alternate above). Do not proceed to Step 14 without one of these lines.

14. **Delegate /audit to a fresh sub-agent:**

   The audit runs in a fresh model context via the Agent tool, NOT inline. This is the load-bearing change that makes Step 14 actually work — see the rationale at the end of this step before considering reverting to inline.

   **(a) Collect the audit brief.** The sub-agent will start with zero /park context. The prompt must be **self-contained** — every value the sub-agent needs must be embedded verbatim, not referenced by name. Collect:

   - **Vault path** (resolved from Step 0): the absolute path, not `{VAULT}` placeholder
   - **Session log path**: `<vault>/06 Archive/Claude/Session Logs/YYYY-MM-DD.md`
   - **Session number N** (from Step 8's `--auto-number` output — `Session number assigned: N`)
   - **File list** — every file the session+park touched. Pull verbatim from the session log's `### Files Created` and `### Files Updated` sections (now backfilled at Step 13a). Embed the list inline as newline-separated paths in the prompt; do NOT tell the sub-agent to "look in the session log" — embed the actual values.
   - **One-paragraph session summary** — pull verbatim from the session log's `### Summary` section. This is critical for Layer 3's "what world-state changes happened" question; without it the sub-agent only knows what /park edited, not what the session caused.
   - **⛔ Out-of-band evidence** — every external source the session's work product rests on (web fetches, emails, API results, tool output, pasted text) that the sub-agent cannot reach from the vault, embedded verbatim under an `## Out-of-band evidence (treat as given — do NOT flag as fabricated)` heading. Derive the count from the work product's citation section **plus** a sweep of this session's fetch/read tool calls — never from recollection of what you drew on. Full rule, including how to derive N, the size cap, and the unrecoverable-source fallback: **`_shared-rules.md` §16** (already in context — Step 0 reads it in full).

   **(b) Spawn the sub-agent** with the Agent tool, `subagent_type: "general-purpose"`. Foreground (not background) — Steps 15-17 need its result.

   The prompt must brief the sub-agent like a smart colleague who just walked in. It must include verbatim:

   - **What to audit:** "Session N of `<session log path>` and all files the session+park touched. The session itself accomplished: <verbatim summary>. The park+session edited: <verbatim file list>. Layer 3 must include not just identifiers /park changed, but world-state framings rendered stale by what the session DID — e.g. if the session sent a message, hubs that previously described the send as upcoming may now be stale even though /park didn't edit them. Read each touched project/area hub IN FULL (not just the subsection that was edited) before claiming clean."
   - **Protocol to follow:** "Read `audit.md` Phase 2 (Layers 1-5) AND Phase 4 step 1 (remediation, including its **deletion-discipline** rule — surface, don't delete, content you can't attribute) first (in `~/.claude/commands/` or `{VAULT}/.claude/commands/`). Do not recall the layers or the remediation rules from memory."
   - **Enumeration discipline:** "List identifiers as `old → new` pairs OR explicit nil-case checklist (Row removals, Content corrections, Factual/claim corrections, Naming changes, Status flips, Section relocations, New named state introduced, **Phase/status framings falsified by session actions — in both directions**). The last category is the one inline audits keep missing — give it extra interrogation, and run it both ways: (1) work the session **completed** still framed as pending — search prose like 'upcoming', 'planned', 'pending', 'will', 'next', 'forthcoming', 'awaiting', **and the scheduled-pending phrasings a *prior* session correctly planted** ('booked', 'scheduled', 'ordered', 'submitted', 'not yet <verb>', 'once <verb>ed', 'once administered/received/approved') near references to it; (2) an action the session merely **scheduled** (a booking made, an order placed, a submission sent) framed as already discharged — here the main verb is usually honest ('booked', 'sent'), so check the *entailed-consequence clause* beside it ('clearing X', 'unblocking Y', 'which completes Z') against what physically happened. Direction (2) bites hardest in free prose — a narrative field or summary, where no checkbox structurally forbids the over-claim. Both token lists are illustrative, not exhaustive: "no listed token matched" is **not** a clean result — read the touched hubs for the *meaning* (is anything described as still-to-happen that the session made happen, or as done that the session only scheduled?), because the exact stale phrasing routinely shares no token with either list. Flag every hit in both directions. Check too whether the session log's OWN `### Next Steps / Open Loops` and `### Pickup Context` describe /park's already-run steps (this audit, reference-graph propagation, skill monitor) as forthcoming — these sections are written at Step 8, before this audit fires, so *if* such a framing is present ('the first real exercise will…', 'the audit will…') it is already stale by the time you read it; reframe those to completed/current tense. This is a condition to test, not a defect to assume: a session log that simply doesn't mention park's own steps is clean here, and reporting an absent framing as found is a manufactured finding."
   - **WIP timestamp-bump exclusion:** "If `01 Now/Works in Progress.md` shows only a `Last updated:` timestamp change with no content write under a project heading, that bump is intentional unconditional bookkeeping (Step 13b) — do NOT flag it as a missing Files Updated entry, and do NOT add it; Step 13a excludes it by design. Only a Step 11 *content* write to WIP (Status/Last/Next/narrative under a project heading) belongs in Files Updated."
   - **⛔ Session-boundary attribution** — embed **`_shared-rules.md` §20** in the brief (already in context — Step 0 reads it in full). The file list above is the attribution boundary; the vault's auto-save commit window is not. Without it a sub-agent reads a concurrent session's file out of a shared commit and writes a self-consistent record of work this session never did.
   - **Script paths the sub-agent will need** (substitute resolved vault):
     - `<vault>/.claude/scripts/update-session-section.sh` — for session-log edits (preserves flock concurrency safety against parallel /park or /goodnight)
     - `<vault>/.claude/scripts/backfill-files-updated.sh` — to record any remediation edits into Session N's Files Updated section. **Caveat:** the script dedups by normalised path and *silently discards* the new text for a file already listed — to extend an already-listed entry's description, rewrite the section via `update-session-section.sh … "Files Updated" --replace` instead
     - `<vault>/.claude/scripts/locked-edit.sh` — for remediation edits to planning/hub files (WIP, This Week, Tickler, project/area hubs)
   - **Locking constraint:** "For session-log edits, use `update-session-section.sh`. For planning/hub files (WIP, This Week, Tickler, `03 Projects/`, `04 Areas/` hubs), use `locked-edit.sh` (see `_shared-rules.md` §5) — the lockless Edit tool races with concurrent parks/goodnights and silently clobbers. For other vault files, the Edit tool is acceptable but assume single-session execution."
   - **Read-coverage backstop:** "If the file list contains more than 5 project/area hubs to read in full, split the audit across multiple passes rather than truncating any read. Report bytes-read per hub in your final report so the main session can verify plausible coverage. Sub-agent summaries have been observed to drift on ordinal detail under context pressure — bytes-read evidence prevents silent truncation."
   - **Authority to remediate:** "Use Edit / Bash / the scripts above to fix findings inline. Re-audit after each fix; iterate until clean."
   - **Remediation scope — do NOT edit skill/command files.** "Your remediation authority is scoped to vault content (project/area docs, planning files) and the session log. Do NOT edit skill or command files (`~/.claude/commands/*`, `*/.claude/commands/*`) — not even to fix a gap you found in the very command being run. If you identify a skill improvement, return it as a *finding* in your report for the main session's Step 15 skill-monitor to log for weekly processing; never apply it yourself. Editing a command file directly bypasses user approval, and reporting such an edit as a 'discovered pre-existing change' rather than your own action is a misattribution failure."
   - **Report format expected back:** "Per-layer findings (or nil-case statements that explicitly name what was checked — generic affirmations like 'approach is sound' are not acceptable); list of remediation edits with file paths + summary of change; bytes-read-per-hub for read-coverage verification; final clean-pass confirmation OR explicit 'could not clean — N issues remain because X' if iteration stalled."

   **(c) Receive the sub-agent's report.** Display its summary in your response — this is the audit's user-facing output. Do NOT re-run the audit yourself; trust the sub-agent's report (the whole point is that you don't have the fresh-context advantage).

   **(d) Process the report.** If the sub-agent made remediation edits, verify it called `backfill-files-updated.sh` for them. If not, run the backfill yourself using the file list it reported. If read-coverage report shows any hub at suspicious-low byte count (well below the file's actual size on disk — check via `stat -c%s` on GNU/Linux, `stat -f%z` on BSD/macOS), re-despatch a focused sub-agent on that hub.

   - **Sanity-check remediation edits that change a factual claim, before accepting them.** "Trust the report" (step c) means don't re-run the full audit — it does *not* mean accept a remediation blind. If the sub-agent edited a file to "correct" a numeric/ordinal/identifier claim (counts, FIFO trims, dates, link targets — the categories it's documented to drift on), verify the correction against the **live file** (and your own in-session grep evidence) before letting it stand. The vault `.git` is auto-save with arbitrary commit boundaries, so a sub-agent's `git diff` does **not** reliably reconstruct pre-park state — a partial-commit diff can flag a real edit as "fabricated." On a confirmed false positive, revert the sub-agent's edit and restore the accurate text. **Caught 2026-06-03:** an audit sub-agent misread an auto-save `git diff` and rewrote an accurate FIFO-trim line in the session log as a fabrication; the false correction would have shipped under a literal reading of step (c).

   **⛔ CHECKPOINT — required outputs:**
   - `Out-of-band evidence: sources drawn on N → excerpts embedded N` (per `_shared-rules.md` §16), displayed **before** the despatch — or `Out-of-band evidence: none (work product rests on no material outside the vault)`. Derive N per §16 from the work product's citation section plus a sweep of this session's fetch/read tool calls; counting from recollection is the failure §16 exists to catch, so a bare `N → N` with no visible derivation is not the check.
   - Agent tool invocation with subagent_type=general-purpose targeting the audit task
   - Display of sub-agent's report in your response (including bytes-read coverage if multiple hubs)
   - One of: `✓ Audit: clean pass` OR `🔧 Audit: N findings fixed and re-audited clean — see [paths]`

   You cannot proceed to Step 15 without all four. If you find yourself walking the audit layers yourself in /park's main response, STOP — that's the inline-audit failure mode this step exists to prevent. Spawn the sub-agent.

   **Why a sub-agent:** Inline Step 14 empirically rubber-stamps findings due to cognitive load at step 14 of 17, recency bias on just-edited files, and enumeration scoping limited to /park's direct edits (missing world-state consequences). A fresh sub-agent has none of these gradients — same model, same protocol, the difference is context not capability.

15. **Skill monitor** (per shared rules §8):
   - Review the park execution just completed, **including the audit step (Step 14)**. Did you improvise any step not documented here? Did a documented step turn out unnecessary? Did you skip a step that should have a stronger gate?
   - **Audit findings are the highest-signal source of skill gaps.** If the audit caught something /park's documented steps should have caught (e.g. a stale wikilink that Step 12's reference graph missed), that's a candidate for a /park skill edit, not just an audit fix. Treat audit findings as evidence when logging skill-edit observations.
   - If gaps found: log observations per `_skill-monitor.md`.
   - If clean: `✓ Skill monitor: No gaps detected`

16. **Export session transcript:**
   - Export today's verbatim session transcripts to the vault. **This step runs last** so the exported transcript captures the full park including the audit step (Step 14) and any remediation it produced.
     ```bash
     python3 "{VAULT}/.claude/scripts/export-session-transcripts.py" "{VAULT}" --days 7 --all-projects
     ```
   - **Use `--all-projects` (cwd-independent).** The transcript file is date-canonical (`YYYY-MM-DD.md`), one per day, and the script overwrites it wholesale. A single-project export (the old `cd <launch dir>` + cwd-keyed default) regenerates that file from only the launch project's sessions, silently dropping any same-day sessions from *other* project directories — so on a multi-project day `/park` (or `/goodnight`) overwrites a complete transcript with a subset, which then gets provenance-hashed as if final. `--all-projects` sweeps every project directory and merges the day, so the export is both complete and cwd-independent — no `cd` needed, and it can't clobber a broader file with a project subset. (Do NOT use `--fallback-any-project`.)
   - **`--days 7`, not `--days 1` (boundary-day completeness).** The script dates each transcript file by JSONL **mtime**, then regenerates every date touched within the window. A narrow `--days 1` window regenerates *yesterday* (when a session ran late) from only the in-window subset of its sessions — a *partial* overwrite of a complete, possibly provenance-stamped file. A 7-day window regenerates each touched day **completely** (all of that day's sessions fall inside it), so no partial clobber. Matches `/morning` 2a.h + `/weekly-hygiene`; re-exporting 7 days costs <1s.
   - Output goes to `{VAULT}/06 Archive/Claude/.Session Transcripts/YYYY-MM-DD.md`. Report the count briefly.
   - Each park re-exports (capturing all sessions up to this point in the day); `/goodnight` re-exports again at close-out so its provenance hash covers the final state.
   - **Why at end of /park:** Earlier ordering (export before audit) meant the transcript missed the audit step entirely. Moving export to last ensures audit findings and remediation are captured for `/goodnight` provenance processing and as a backstop against session data loss.

17. **Display completion message:**
```
✓ Quality check: N files, M issues fixed [OR "no issues"]
✓ Session summary saved to: 06 Archive/Claude/Session Logs/YYYY-MM-DD.md
✓ At-risk work product: No at-risk work product to persist [OR "Persisted N item(s): [paths]"]
✓ Open loops documented: N items
✓ Continuation link added: [Original Session] (only if this session continues previous work)
✓ Project updated: [Project Name] (if applicable)
✓ Reference graph: N files updated for [identifier] (if any status changes traced)
  [OR "✓ Reference graph: No identifier values changed" if none — Step 12(b)'s exact string; don't paraphrase]
✓ Open loops routed: N items (This Week: X, Tickler: Y, Project: Z)
  [OR "✓ No open loops to route" if none]
✓ Audit: clean pass [OR "🔧 Audit: N findings fixed and re-audited clean — see [paths]"]
✓ Skill monitor: No gaps detected [OR "✓ Skill monitor: N observation(s) logged"]
✓ Transcript exported: N sessions → 06 Archive/Claude/.Session Transcripts/YYYY-MM-DD.md

Parked. Pick up when ready.

To pickup later: `claude` then `/pickup`
```

**IMPORTANT:** The "Quality check" line is REQUIRED in the completion message. If you cannot produce this line, you skipped Step 4 - go back and complete it before finishing the park.

## Guidelines

- **Merge continuations, don't fork sessions:** Step 2 handles this procedurally. Use `update-session-section.sh` for all section edits (never ad-hoc sed).
- **Continuation linking only:** No chronological "Next/Previous session:" links (redundant — sessions are ordered in the file). Only topical `**Continues:**` / `**Continued in:**` links, triggered by `/pickup`. Both are **file-level** links that name the session in plain text; never `#heading` anchors.
- **Capture ALL sessions:** Full bookkeeping pass runs unconditionally — no opt-out fast-path.
- **File locking:** Per `_shared-rules.md` §5. Use scripts, not Edit tool.
- **Narrative tone:** Write summaries in the user's voice — direct, technical, outcome-focused.
- **Open loops:** Each must be specific enough to resume without re-reading the conversation. Route to SSOT (This Week, Tickler, project files) — session docs are plain-text records, never task trackers. Use plain bullets (`- `), never checkboxes (`- [ ]`) in session logs.
- **One-sentence pickup:** The "For next session" line should be immediately actionable (or "No follow-up needed" if complete).
- **Project linking:** Per `_shared-rules.md` §2.
- **File lists:** Only files actually created/updated, not files just read. Empty sections: bare `None`. Files Updated is not vault-scoped — include external paths when load-bearing. Step 13a backfills park-time edits.
- **Session naming:** Descriptive names that make sense weeks later ("Wezterm config fix" not "Terminal stuff").

## Shutdown Philosophy

Clean shutdown = every open loop captured in a trusted system, eliminating mental residue. Capture completed work too — the archive answers "when did I make that decision?" months later.
