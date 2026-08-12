# Shared Patterns

A **pointer index** of reusable infrastructure patterns that recur across commands, and which skill implements each best. Sibling to `_shared-rules.md`, but a different kind of thing:

- `_shared-rules.md` holds *rules you obey at runtime* — commands load it and follow it.
- This file holds *where to find the battle-tested version of a pattern* you'd want when building or improving a skill.

**Consult it** whenever you build or substantially edit a skill: scan for patterns this skill wants, then **read the named reference skill for the real implementation** and adapt it. Cross-pollination is the point — skills get sharper by sharing infrastructure. (A Stop hook on skill edits automates this reminder; it ships with the template — opt in with `/setup-hooks`.)

## Staleness contract (load-bearing — keep this file drift-proof)

This is an *index*, not a library. Drift is avoided by keeping entries trivially thin:

- **Each entry = pattern name + a ≤8-word shape + `→ reference`. No code, ever.** Code blocks rot; pointers don't. A reference is a skill name, optionally with a step/phase anchor (`park` Step 7), or `_shared-rules.md §N` when the canonical implementation lives in a shared-rules section. **`/weekly-hygiene` verifies the file half of a pointer, never the anchor** — a step number that drifts is not caught by any check.
- **The reference is the single source of truth.** Always read it before using the pattern — never trust this file's one-liner as the spec.
- **Proven-twice gate — a pattern earns an entry only after it's been reused in ≥2 skills.** First sighting is not indexable; a one-off lives in its own skill. Add the pointer here the moment you port a non-obvious mechanism into a *second* skill — that's the proof it's transferable. (Borrowed from Voyager's verify-before-adding-to-the-library: the admission bar is what keeps the index high-signal.)
- **Adding a pattern:** add one line pointing at the reference implementation. If you can't say the shape in ≤8 words, it's too specific for the index — leave it in its skill.
- **`/weekly-hygiene` spot-checks that every `→` pointer still resolves** to a live file; fix or drop stale pointers there.

## Patterns

- **Manifest + resumability** — JSONL per-item status; resume from first incomplete. → `transcribecloud`
- **Progress reporting** — stream per-item index, status, elapsed, rate. → `transcribe`, `transcribecloud`
- **Cost/time estimation up front** — project units × cost; confirm before spend. → `transcribecloud`
- **Parallel cross-model panel despatch** — one seat per model family, identical brief, concurrent. → `second-opinion` (command block: `_shared-rules.md §10`)
- **Reviewer evidence attestation** — read-list / command / manifest / URL+quote; class outranks votes. → `_shared-rules.md §23`
- **Out-of-band evidence in reviewer briefs** — embed every source verbatim; omissions read as fabrication. → `_shared-rules.md §16`
- **File-size threshold + progressive resize** — read hook limit; shrink width stepwise to fit. → `ocr`
- **Helper-reuse check** — probe for existing scripts before writing fresh. → `ocr`
- **Prereq verification with install hints** — verify each dependency; emit specific install line. → `transcribe`
- **WhisperX audio→JSON core** — model → align → diarise → segments JSON. → `transcribe`
- **Gated-model silent-None assert** — assert `diarize_model.model` after `DiarizationPipeline`. → `transcribecloud`, `transcribe`
- **Tag-scan hygiene** — md-glob filter; exclude archive + frozen artefacts. → `longpoles`, `guillotines`, `cornerstones`
- **Published-transcript-first** — prefer ready-made published transcript over re-running ASR. → `transcribe` Phase 0
- **Page text outranks transcript body** — human-written show notes win names + speakers. → `_shared-rules.md §15`
- **Grep-hit triage on identifier change** — stale-ref / live-locator / historical / unrelated → act. → `_shared-rules.md §12`
- **Surface, don't act, on what you can't attribute or verify** — report as finding; never delete or rewrite. → `audit` (deletion discipline), `park` Step 2(b)
- **Grep with path exclusion** — exclusion via find/rg/pipe, never grep flags. → `park` Step 6, `weekly-hygiene` Step 11
- **Locked atomic file write** — serialise via canonical `.lock`; atomic replace. → `_shared-rules.md §5`
- **Step-0 vault resolution** — `resolve-vault.sh`; abort on error, never guess; substitute `{VAULT}`. → `_shared-rules.md §1`, `park` Step 0
- **Sync marker on deliberate duplication** — comment names the twin; update both together. → `podcast-digest`, `transcribecloud` Phase 8
- **Substitute-me placeholder for cross-call values** — literal placeholder, never shell var; substitute before running. → `_shared-rules.md §1`, `park` Step 3
- **Deterministic temp path for cross-call files** — derive from a stable input, never `mktemp`. → `_shared-rules.md §15`, `podcast-digest` Phase 0
- **Collision filenames take letter suffixes** — letters sort after bare name; `-N` sorts before. → `weekly-review` Step 5, `quarterly-review` Step 10
- **Dollar-digit-free snippets** — loader substitutes bare `$0`–`$9`; avoid or `-v z=0`. → `quarterly-hygiene` Step 6, `park` Step 3
- **`LC_TIME=C` guard on `%p`** — `%p` expands empty under non-English locales. → `park` Step 0, `hibernate`/`awaken` Step 1
- **Weekday via `date -d`, never internal mapping** — verify weekday+date pairs before writing. → `park` Step 5, `guillotines` Step 3
- **Geocode with substitution + outlier guards** — exact-match escalation; drop outliers; approximate-street fallback. → `map-day`, `book-stay` Step 4
- **Link-aware moves: never raw `mv`, batches are fine** — CLI behaviour + verification live in one place, not in each skill. → `_shared-rules.md §24`, `quarterly-hygiene` Step 6, `complete-project` Step 4, `inbox-processor` Step 4
- **Self-contained Bash blocks** — vars die between tool calls; bind in-block. → `provenance` Step 5, `goodnight` Step 17
- **Quoted heredoc for literal payloads** — unquoted `<<EOF` expands/executes `$`, backticks in content; quote `<<'EOF'`, printf the parts that should expand. → `_shared-rules.md §5`, `_skill-monitor`
- **Transcript export → `--days 7 --all-projects`** — both project + mtime-window axes clobber the date-canonical day file. → `morning` 2a.h, `goodnight` Step 16, `park` Step 11, `weekly-hygiene`
- **Preference quiz with ranked hard requirements** — AskUserQuestion; skip context-answered; rank firmest→negotiable. → `shop` Phase 2, `book-stay` Step 2
- **Date an artefact from its content, not mtime** — later touches reset mtime; overdue reads as current. → `_shared-rules.md §22`, `morning` Step 3, `weekly-hygiene` Steps 2-3 + Step 7
- **Window from the last run, not a fixed span** — derive the boundary from the previous run's artefact. → `_shared-rules.md §22`, `weekly-hygiene` Step 7
- **Auto-save git is not pre-state** — commit boundaries misread prior *content*; verify per-commit. Two sides: forbid it in the reviewer's brief (→ `park` Step 9, `goodnight` Step 15(c), `morning` 2a.g) and re-check any git-derived finding before accepting it (→ `park` Step 9, `goodnight` Step 15(e))
- **Session-boundary attribution** — brief's file list bounds *authorship*; commit window doesn't. → `_shared-rules.md §20`, `park` Step 9, `goodnight` Step 15(c)
- **Value provenance check (SOURCE)** — written values trace to user, tool, or tag. → `_shared-rules.md §19`, `park` Step 2(c), `goodnight` Step 14b, `_shared-rules.md §16` (brief evidence: primary/secondary/unverified)
- **Clock value read before written** — `date` result in a *prior* call; same-call is an estimate. → `_shared-rules.md §19`, `park` Step 0, `morning` Step 3
- **Deadline token forces dated surface** — deadline-bearing items route to dated target, never undated doc. → `_shared-rules.md §18`, `park` Step 7, `goodnight` Step 9, `weekly-review` Step 5a
- **Gate emits an observable, not an assertion** — nil case cites its evidence. → `park` Step 2(a), `park` Step 7, `oops` Phase 1
- **Gate a sub-agent on collection, not on despatch mode** — foreground is not yours to control; the completion notification is the only finish signal. → `park` Steps 8-9, `goodnight` Step 15(c), `ocr` capture loop
- **Verbatim text vs in-place formatting hook** — hook rewrites whole file; append via shell, never re-Edit. → `_shared-rules.md §14`, `archive-transcript`, `park` Step 2(b)
- **Frozen content excluded by path, not discipline** — put byte-exact copies beyond auto-rewriters' reach. → `_shared-rules.md §14`, `provenance` Step 5
- **Preimage snapshot before hashing a living doc** — a hash without its bytes proves nothing later. → `provenance` Step 5, `goodnight` Step 17
- **Push-side hub record** — pushed commit's canonical row lives in a hub no grep reaches. → `_shared-rules.md §17`, `park` Step 6, `goodnight` Step 15(a)
- **Empty CLI output is not zero** — cross-check rows vs total; crash ≠ empty; stop re-invoking. → `weekly-hygiene` Step 11, `quarterly-hygiene` Step 6
- **Sentinel termination needs a positive end-state check** — failure can forge the sentinel; name the benign case. → `transcribecloud` (frozen log ≠ dead), `ocr` 0d
- **Confirmatory-only checks pass under both hypotheses** — name the observation that actually differs. → `ocr` (last-frame message identity), `_shared-rules.md §15`
- **Portability note on GNU-only snippets** — name the BSD/Windows equivalent beside it. → `_shared-rules.md §5`, `weekly-hygiene` Guidelines, `quarterly-hygiene` Step 6
- **Deferred cross-skill handoff via a drop-box** — writer drops a dated artefact; later skill consumes it. → `provenance` (flags, deleted on processing), `park` Step 2(a) (receipt, time-filtered)
- **Blanket write-mechanism declaration** — state it once up front, not per step. → `morning`, `goodnight`
- **Cap check before adding** — count target surface first; overflow → ask which drops. → `weekly-review` (This Week cap), `morning` (root-project cap)
- **Veto-of-proposed-routes** — propose a destination per item; user pass = veto, not generate; unvetoed executes. → `process-wm`, `goodnight` Step 9 (Whimsy batch), `migrate` component 3
- **Idempotent hook merge into settings.json** — key on command string; backup, validate, atomic `mv` (unlocked — serialise callers). → `setup-hooks` (both wiring scripts)
- **A folded log has two surfaces** — count/search distilled rules *and* raw entries; an entry-heading count alone reads zero. → `oops` Phase 5, `weekly-review` (corrections-log review)
- **Default-with-SSOT-deference** — skill states a working default + defers to the owning vault doc if it differs. → `weekly-review`/`morning`/`goodnight` (This Week caps; owner: Vault Organisation Principles → Project Doc Format)
