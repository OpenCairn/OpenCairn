---
name: archive-transcript
description: Archive a podcast/talk transcript from a URL into the vault — verbatim body plus a synthesis header — without routing the full text through context or letting a formatting hook corrupt verbatim quotes.
---

# Archive Transcript — Verbatim Capture + Synthesis

You are archiving one or more podcast/talk transcripts into the vault. Each note is the **verbatim transcript** with a short **synthesis header** on top. The user gives you one or more episode URLs (or a person/show whose appearances you find first).

Two principles drive this skill:

1. **Keep the transcript out of your context.** A transcript is ~10–20k words. Fetch and clean it straight to a file and append it to the note via the shell — never read the whole thing into the conversation. You write only the small synthesis header and read at most a few lines to verify boundaries.
2. **A formatting hook will corrupt verbatim quotes unless you bypass it.** This is the general problem in `_shared-rules.md` §14 — read it. The skill-local invariant: **write the header with the editor tool, append the body with the shell, and never `Write`/`Edit` the note again after appending.** The *why*, the precondition (the hook must not intercept shell writes), and the path-exclude alternative all live in §14.

## Phase 0 — Preflight

Run the `_shared-rules.md` §15 prereq check (`curl`, `pandoc`, `python3` + `bs4`/`lxml`) before fetching, so a fresh machine fails fast with a clear message rather than mid-pipe. If anything is missing, tell the user and stop (or use the §15 transcription fallback — transcribe the audio/video — after confirming with the user).

## Phase 1 — Resolve the sources

1. If given direct URLs, use them.
2. If given a show or a person, find the appearances first (web search), confirm each URL, and list them back before fetching.
3. For each episode capture: show, host, guest, publish date, canonical URL.

## Phase 2 — Fetch the verbatim transcript to a file

Use the **`_shared-rules.md` §15 published-transcript extractor** (the single source of truth for this) to pull each episode to a file. Run it once per episode, each in its own temp dir, leaving:

- `<BODY_FILE>` — the clean verbatim transcript body (parser-selected container, chrome stripped, converted to markdown, gated on word + leak count; the body never enters your context). This is §15's printed `BODY=` path, a **deterministic function of the URL** — reuse that exact path in Phase 3/4 (or re-derive it from the URL); there is no random temp name to carry across the tool-call boundary.
- the published **description** and the `## `/`### ` **section outline** — the raw material for the Phase 3 synthesis header.

§15 owns the mechanism (prereqs, static-HTML confirm, the extractor, the word/leak gate, the metadata pull) and the fallback. This skill owns what surrounds it: Phase 1 resolved the sources, and Phase 3 writes the note.

**If §15's fallback applies** (no published transcript, or a JS-rendered page §15 can't extract): machine-transcribe the audio/video via the WhisperX path (`/transcribe` or `/transcribecloud`). Much heavier — tell the user before launching a batch.

## Phase 3 — Write the note (header via editor, body via shell)

Per `_shared-rules.md` §14:

1. **Dedupe first**, keyed on the canonical source URL (catches retitled/renamed notes that a filename check misses), then title/date:
   ```bash
   grep -rl --fixed-strings "<canonical_url>" "<transcript-folder>" || echo "no existing note"
   ```
   If it exists, report it and ask whether to update or skip — don't write a duplicate.

2. **Match existing conventions.** Inspect one existing transcript note in the folder for its frontmatter schema and filename pattern; reuse them. Only if none exists, fall back to: filename `<Speaker> - <Title> (<Show>, <Year>).md`; frontmatter `title, show, host, guest, date, source, captured, type: podcast-transcript`.

3. **Write only the header** with the editor tool: frontmatter + synthesis.
   - The synthesis is **explicitly derived from the published description + section headings only** — say so in the note (e.g. a one-line provenance caveat). Do **not** present an authoritative "bottom line" you can't support without reading the body: give a *topic summary* + the section-derived **cruxes**, and flag relevance to the user's purpose. This respects "don't invent claims the page doesn't support."
   - End the header with a `## Full transcript` heading and a one-line provenance note (verbatim; source; that timestamp links were stripped from headings).

4. **Append the verbatim body via the shell** (bypasses the hook — §14):
   ```bash
   printf '\n' >> "<DESTINATION_NOTE>.md"      # guarantee a newline boundary
   cat "<BODY_FILE>" >> "<DESTINATION_NOTE>.md"   # <BODY_FILE> = §15's printed BODY= path (deterministic from the URL)
   ```

5. **Never `Write`/`Edit` the note again after appending** — it re-fires the hook on the whole file, body included. Fix the header *before* appending, or re-append a fresh body.

## Phase 4 — Integrate, verify, report

1. **Link** the new transcript from the relevant person/dossier or topic hub. ⚠️ These are `Edit`s on *other* `.md` notes and fire the same formatting hook on them (§14 "collateral edits"): short edits to already-normalised hub prose are safe, but if a target note itself holds verbatim quotes, exclude it or append rather than `Edit`.
2. **Verify the append landed** — shell only, no context bloat:
   ```bash
   wc -w "<BODY_FILE>" "<DESTINATION_NOTE>.md"   # destination should exceed body (<BODY_FILE> = §15's printed BODY= path)
   tail -n 5 "<DESTINATION_NOTE>.md"               # confirm it ends in transcript, intact
   ```
3. **Report:** file paths, final word counts, any episodes that fell back to transcription, and any fidelity caveats.

## Guidelines

- **Verbatim means verbatim.** Don't summarise, fix grammar, or let a hook rewrite the body. Synthesis lives in the header only.
- **Synthesis from structure, not from a full read.** Build the topic summary + cruxes from the published description and section headings; don't pull 15k words into context to write 8 bullets, and don't assert a thesis the metadata doesn't support.
- **Locale of the header follows the vault; locale of the body follows the speaker.** Your synthesis can be the vault's English; the transcript stays as published.
- **Match the vault's transcript conventions** (folder, filename, frontmatter) — inspect an existing note before inventing a layout.
