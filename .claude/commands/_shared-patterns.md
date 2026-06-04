# Shared Patterns

A **pointer index** of reusable infrastructure patterns that recur across commands, and which skill implements each best. Sibling to `_shared-rules.md`, but a different kind of thing:

- `_shared-rules.md` holds *rules you obey at runtime* — commands load it and follow it.
- This file holds *where to find the battle-tested version of a pattern* you'd want when building or improving a skill.

**Consult it** whenever you build or substantially edit a skill (the skill-edit Stop hook reminds you): scan for patterns this skill wants, then **read the named reference skill for the real implementation** and adapt it. Cross-pollination is the point — skills get sharper by sharing infrastructure.

## Staleness contract (load-bearing — keep this file drift-proof)

This is an *index*, not a library. Drift is avoided by keeping entries trivially thin:

- **Each entry = pattern name + a ≤8-word shape + `→ reference skill`. No code, ever.** Code blocks rot; pointers don't.
- **The reference skill is the single source of truth.** Always read it before using the pattern — never trust this file's one-liner as the spec.
- **Proven-twice gate — a pattern earns an entry only after it's been reused in ≥2 skills.** First sighting is not indexable; a one-off lives in its own skill. Add the pointer here the moment you port a non-obvious mechanism into a *second* skill — that's the proof it's transferable. (Borrowed from Voyager's verify-before-adding-to-the-library: the admission bar is what keeps the index high-signal.)
- **Adding a pattern:** add one line pointing at the reference implementation. If you can't say the shape in ≤8 words, it's too specific for the index — leave it in its skill.
- **`/weekly-hygiene` spot-checks that every `→` pointer still resolves** to a live skill; fix or drop stale pointers there.

## Patterns

- **Manifest + resumability** — JSONL per-item status; resume from first incomplete. → `transcribecloud`
- **Progress reporting** — stream per-item index, status, elapsed, rate. → `transcribe`, `transcribecloud`
- **Cost/time estimation up front** — project units × cost; confirm before spend. → `transcribecloud`
- **Parallel cross-model trio despatch** — Claude + Gemini + Codex, identical brief, concurrent. → `second-opinion`
- **File-size threshold + progressive resize** — read hook limit; shrink width stepwise to fit. → `ocr`
- **Helper-reuse check** — probe for existing scripts before writing fresh. → `ocr`
- **Prereq verification with install hints** — verify each dependency; emit specific install line. → `transcribe`
- **WhisperX audio→JSON core** — load model → align → optional diarise → emit segments JSON. → `transcribe`
- **Grep-hit triage on identifier change** — stale-ref / live-locator / historical / unrelated → act. → `_shared-rules.md §12`
- **Locked atomic file write** — serialise writers via canonical `.lock`; replace via temp + atomic rename. → `_shared-rules.md §5`
