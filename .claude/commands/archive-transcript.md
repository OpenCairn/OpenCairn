---
name: archive-transcript
description: Archive a podcast/talk transcript from a URL into the vault — verbatim body plus a synthesis header — without routing the full text through context or letting a formatting hook corrupt verbatim quotes.
---

# Archive Transcript — Verbatim Capture + Synthesis

You are archiving one or more podcast/talk transcripts into the vault. Each note is the **verbatim transcript** with a short **synthesis header** on top. The user gives you one or more episode URLs (or a person/show whose appearances you find first).

Two principles drive this skill:

1. **Keep the transcript out of your context.** A transcript is ~10–20k words. Fetch and clean it straight to a file and append it to the note via the shell — never read the whole thing into the conversation. You write only the small synthesis header and read at most a few lines to verify boundaries.
2. **A formatting hook can corrupt verbatim quotes unless you bypass it.** This is the general problem in `_shared-rules.md` §14 — read it. The skill-local invariant: **write the header with the editor tool, append the body with the shell.** Whether a *later* `Write`/`Edit` on the finished note is safe depends on the vault, so establish that in Phase 0 rather than assuming. The *why*, the precondition (the hook must not intercept shell writes), and the path-exclude alternative all live in §14.

## Phase 0 — Preflight

1. Run the `_shared-rules.md` §15 prereq check (`curl`, `pandoc`, `python3` + `bs4`/`lxml`) before fetching, so a fresh machine fails fast with a clear message rather than mid-pipe. If anything is missing, tell the user and stop (or use the §15 transcription fallback — transcribe the audio/video — after confirming with the user).
2. **Establish the formatting-hook state** (§14): is a `PostToolUse` hook configured on `.md` writes, what does its matcher cover, and does it read a path-exclude list? Three outcomes drive the later phases:
   - **No hook** → verbatim is safe by any write method; the no-edit invariant below doesn't apply.
   - **Hook matching `Write`/`Edit` only** (the usual case) → the shell append holds; treat the note as no-edit after appending unless the destination folder is on the exclude list.
   - **Hook that also matches `Bash`/shell writes** → the append corrupts silently with no error. Path-exclude the destination folder (§14 defence 2) before writing anything, or stop.

## Phase 1 — Resolve the sources

1. If given direct URLs, use them.
2. If given a show or a person, find the appearances first (web search), confirm each URL, and list them back before fetching.
3. For each episode capture: show, host, guest, publish date, canonical URL.

## Phase 2 — Fetch the verbatim transcript to a file

Use the **`_shared-rules.md` §15 published-transcript extractor** (the single source of truth for this) to pull each episode to a file. Run it once per episode (the per-URL slug keeps a multi-episode batch from colliding), leaving:

- `<BODY_FILE>` — the clean verbatim transcript body (parser-selected container, chrome stripped, converted to markdown, gated on word + leak count; the body never enters your context). This is §15's printed `BODY=` path, a **deterministic function of the URL** — reuse that exact path in Phase 3/4 (or re-derive it from the URL); there is no random temp name to carry across the tool-call boundary.
- the published **description** and the `## `/`### ` **section outline** — the raw material for the Phase 3 synthesis header.

§15 owns the mechanism (prereqs, static-HTML confirm, the extractor, the word/leak gate, the metadata pull) and the fallback. This skill owns what surrounds it: Phase 1 resolved the sources, and Phase 3 writes the note.

**If §15's fallback applies** (no published transcript, or a JS-rendered page §15 can't extract): machine-transcribe the audio/video via the WhisperX path (`/transcribe` or `/transcribecloud`). Much heavier — tell the user before launching a batch.

## Phase 3 — Write the note (header via editor, body via shell)

Per `_shared-rules.md` §14:

1. **Choose the destination first (no hardwired path)** — the dedupe grep needs a real operand. Propose a transcript folder: detect an existing transcript/podcast folder in the vault (never create or assume one); if there's no obvious folder, **ask** rather than guessing. Bind the three operands once here and reuse them verbatim through Phase 4:
   - `<TRANSCRIPT_FOLDER>` — the chosen folder (user-overridable).
   - `<DESTINATION_NOTE>` — `<TRANSCRIPT_FOLDER>/<filename>.md`, filename per step 3.
   - `<BODY_FILE>` — §15's printed `BODY=` path (a deterministic function of the URL).

2. **Dedupe**, keyed on the canonical source URL (catches retitled/renamed notes that a filename check misses), then title/date:
   ```bash
   grep -rl --fixed-strings "<canonical_url>" "<TRANSCRIPT_FOLDER>" || echo "no existing note"
   ```
   If it exists, report it and ask whether to update or skip — don't write a duplicate. **Update means rebuild, not edit:** write the new header to a fresh file, append the body from `<BODY_FILE>` again, then `mv` it over the old note. Never `Edit` a note that already carries an appended body.

3. **Match existing conventions.** Probe the folder from the **shell, not `Read`** — a finished transcript note is 10–20k words, and reading one defeats Principle 1:
   ```bash
   ls "<TRANSCRIPT_FOLDER>"                     # filename pattern
   head -n 20 "<TRANSCRIPT_FOLDER>"/*.md        # frontmatter only
   ```
   Sample **2–3** notes that are actually transcripts (`type: podcast-transcript`; skip digests, concept notes, and untagged strays) and follow the **modal** filename + frontmatter convention. The folder is usually heterogeneous — one sample is a coin flip. Only if none exists, fall back to: filename `<Speaker> - <Title> (<Show>, <Year>).md`; frontmatter `title, show, host, guest, date, source, captured, type: podcast-transcript`.

4. **Write only the header** with the editor tool: frontmatter + synthesis.
   - The synthesis is **explicitly derived from the published description + section headings only** — say so in the note (e.g. a one-line provenance caveat). Do **not** present an authoritative "bottom line" you can't support without reading the body: give a *topic summary* + the section-derived **cruxes**, and flag relevance to the user's purpose. This respects "don't invent claims the page doesn't support."
   - End the header with a `## Full transcript` heading and a one-line provenance note (verbatim; source; that timestamp links were stripped from headings).

5. **Append the verbatim body via the shell** (bypasses the hook — §14):
   ```bash
   printf '\n' >> "<DESTINATION_NOTE>"      # guarantee a newline boundary
   cat "<BODY_FILE>" >> "<DESTINATION_NOTE>"
   ```

6. **Don't `Write`/`Edit` the note again after appending** — unless Phase 0 cleared it (no hook configured, or the folder is path-excluded), any later edit re-fires the hook on the whole file, body included. Fix the header *before* appending, or rebuild per step 2's update path.

## Phase 4 — Integrate, verify, report

1. **Link** the new transcript from the relevant person/dossier or topic hub. ⚠️ These are `Edit`s on *other* `.md` notes and fire the same formatting hook on them (§14 "collateral edits"): short edits to already-normalised hub prose are safe, but if a target note itself holds verbatim quotes, exclude it or append rather than `Edit`.
2. **Verify the append landed** — shell only, no context bloat:
   ```bash
   wc -w "<BODY_FILE>" "<DESTINATION_NOTE>"   # destination should exceed body
   tail -n 5 "<DESTINATION_NOTE>"             # confirm it ends in transcript, intact
   cmp <(tail -c "$(wc -c < "<BODY_FILE>")" "<DESTINATION_NOTE>") "<BODY_FILE>" \
     && echo "body byte-identical"            # catches an in-place rewrite that wc/tail both pass
   ```
   The `cmp` is the one check that detects a hook which intercepted the shell write: a spelling normaliser leaves word count and tail intact but changes bytes. If it differs, don't patch the note — path-exclude the folder (§14) and rebuild.
3. **Report:** file paths, final word counts, any episodes that fell back to transcription, and any fidelity caveats.

## Guidelines

- **Verbatim means verbatim.** Don't summarise, fix grammar, or let a hook rewrite the body. Synthesis lives in the header only.
- **Synthesis from structure, not from a full read.** Build the topic summary + cruxes from the published description and section headings; don't pull 15k words into context to write 8 bullets, and don't assert a thesis the metadata doesn't support.
- **Locale of the header follows the vault; locale of the body follows the speaker.** Your synthesis can be the vault's English; the transcript stays as published.
- **Names and speakers follow `_shared-rules.md` §15 "Names and speakers"** — the page's human-written text outranks the transcript body on identity, per field. Applies to every name reaching `host` / `guest` / the filename / the synthesis header, and to who-spoke-when. Sharpened here by the header being built from structure rather than a full read: the outline §15 extracts is your only view of the segments, so grep it rather than inferring identity from a body you never read.
- **Match the vault's transcript conventions** (folder, filename, frontmatter) — probe 2–3 existing transcript notes with a shell `head`, not a `Read`, and follow the modal convention before inventing a layout.
