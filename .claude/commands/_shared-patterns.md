# Shared Patterns

A **pointer index** of reusable infrastructure patterns that recur across commands, and which skill implements each best. Sibling to `_shared-rules.md`, but a different kind of thing:

- `_shared-rules.md` holds *rules you obey at runtime* — commands load it and follow it.
- This file holds *where to find the battle-tested version of a pattern* you'd want when building or improving a skill.

**Consult it** whenever you build or substantially edit a skill: scan for patterns this skill wants, then **read the named reference skill for the real implementation** and adapt it. Cross-pollination is the point — skills get sharper by sharing infrastructure. (A Stop hook on skill edits automates this reminder; it ships with the template — opt in with `/setup-hooks`.)

## Staleness contract (load-bearing — keep this file drift-proof)

This is an *index*, not a library. Drift is avoided by keeping entries trivially thin:

- **Each entry = pattern name + a ≤8-word shape + `→ reference`. No code, ever.** Code blocks rot; pointers don't. A reference is a skill name, or `_shared-rules.md §N` when the canonical implementation lives in a shared-rules section.
- **The reference is the single source of truth.** Always read it before using the pattern — never trust this file's one-liner as the spec.
- **Proven-twice gate — a pattern earns an entry only after it's been reused in ≥2 skills.** First sighting is not indexable; a one-off lives in its own skill. Add the pointer here the moment you port a non-obvious mechanism into a *second* skill — that's the proof it's transferable. (Borrowed from Voyager's verify-before-adding-to-the-library: the admission bar is what keeps the index high-signal.)
- **Adding a pattern:** add one line pointing at the reference implementation. If you can't say the shape in ≤8 words, it's too specific for the index — leave it in its skill.
- **`/weekly-hygiene` spot-checks that every `→` pointer still resolves** to a live file; fix or drop stale pointers there.

## Patterns

- **Manifest + resumability** — JSONL per-item status; resume from first incomplete. → `transcribecloud`
- **Progress reporting** — stream per-item index, status, elapsed, rate. → `transcribe`, `transcribecloud`
- **Cost/time estimation up front** — project units × cost; confirm before spend. → `transcribecloud`
- **Parallel cross-model trio despatch** — Claude + Gemini + Codex, identical brief, concurrent. → `second-opinion` (command block: `_shared-rules.md §10`)
- **Reviewer read-attestation** — brief demands files-read list; missing list discredits review. → `audit`
- **File-size threshold + progressive resize** — read hook limit; shrink width stepwise to fit. → `ocr`
- **Helper-reuse check** — probe for existing scripts before writing fresh. → `ocr`
- **Prereq verification with install hints** — verify each dependency; emit specific install line. → `transcribe`
- **WhisperX audio→JSON core** — model → align → diarise → segments JSON. → `transcribe`
- **Published-transcript-first** — prefer ready-made human-edited transcript over re-running ASR. → `transcribe` Phase 0
- **Grep-hit triage on identifier change** — stale-ref / live-locator / historical / unrelated → act. → `_shared-rules.md §12`
- **Surface, don't act, on what you can't attribute or verify** — report as finding; never delete or rewrite. → `audit` (deletion discipline), `park` Step 11
- **Grep with path exclusion** — exclusion via find/rg/pipe, never grep flags. → `park` Step 12(d), `weekly-hygiene` Step 12
- **Locked atomic file write** — serialise via canonical `.lock`; atomic replace. → `_shared-rules.md §5`
- **Step-0 vault resolution** — `resolve-vault.sh`; abort on error, never guess; substitute `{VAULT}`. → `_shared-rules.md §1`, `park` Step 0
- **Sync marker on deliberate duplication** — comment names the twin; update both together. → `podcast-digest`, `transcribecloud` Phase 8
- **Substitute-me placeholder for cross-call values** — literal placeholder, never shell var; substitute before running. → `_shared-rules.md §1`, `park` Step 8a
- **Deterministic temp path for cross-call files** — when work spans tool calls (so a self-contained block can't hold it), derive the path from a stable input (URL/ID slug + hash), never a random `mktemp` name; a later call reconstructs it with nothing carried. → `_shared-rules.md §15`, `podcast-digest` Phase 0
- **Collision filenames take letter suffixes** — letters sort after bare name; `-N` sorts before. → `weekly-review` Step 5, `quarterly-review` Step 10
- **Dollar-digit-free snippets** — loader substitutes bare `$0`–`$9`; avoid or `-v z=0`. → `quarterly-hygiene` Step 6, `park` Step 8a
- **`LC_TIME=C` guard on `%p`** — `%p` expands empty under non-English locales. → `park` Step 1, `hibernate`/`awaken` Step 1
- **Weekday via `date -d`, never internal mapping** — verify weekday+date pairs before writing. → `park` Step 11, `guillotines` Step 3
- **`obsidian move` is one-off only** — batches deadlock the single-instance lock; GUI drag. → `quarterly-hygiene`, `complete-project` Step 5
- **Self-contained Bash blocks** — vars die between tool calls; bind in-block. → `provenance` Step 5, `goodnight` Step 17
- **Transcript export → `--days 7 --all-projects`** — both project + mtime-window axes clobber the date-canonical day file. → `morning` 2a.h, `goodnight`/`park` Step 16, `weekly-hygiene`
- **Preference quiz with ranked hard requirements** — AskUserQuestion; skip context-answered; rank firmest→negotiable. → `shop` Phase 2, `book-stay` Step 2
- **Date an artefact from its content, not mtime** — later touches reset mtime; overdue reads as current. → `weekly-hygiene` Steps 2-3, `morning` Step 3
