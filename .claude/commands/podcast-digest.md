---
name: podcast-digest
aliases: [digest, pod-digest, podcast]
description: Digest an informational podcast/talk episode from a URL — published transcript or our own WhisperX — into a cruxes-first written summary
---

# Podcast Digest — Episode to Written Digest

Given a single episode URL, produce a written **digest** of an informational podcast or talk so the user can get the content without listening, and decide for themselves whether the episode is worth a full listen. The digest is **purely descriptive — it never rates the episode or says whether it's "worth it."** That call stays with the user.

This skill adapts `/transcribe`'s WhisperX core for the transcription step (see *Transcription core* below) and inlines a scrape/duplicate-check/synthesis pattern of its own — it runs self-contained, without delegating to any other command at runtime.

## When to use

When the user pastes an episode URL (a show's episode page, a YouTube video, a Pocket Casts `pca.st` link, or a direct audio link) and wants the *content* rather than the listening experience. Triggers: "digest this", "digest this episode", "what's in this podcast", "summarise this talk/episode".

## Transcription core (Tier 2) — self-contained, adapted from `/transcribe`

`/transcribe` is a *prose* command, not a callable subroutine — so this skill does **not** delegate to it at runtime. Delegating would (a) trigger `/transcribe`'s interactive save/rename/discuss tail, and (b) **critically**, when diarisation is requested but no HF token is present, `/transcribe` *stops during its own validation, before transcribing* — so a "fall back to non-diarised" decision made on this skill's side would never be reached. Instead this skill **owns** the transcription, adapting `/transcribe`'s WhisperX core. Treat `/transcribe` Phase 2 as the **canonical reference** for the WhisperX Python block — update both together if the model or parameters change. (A future refactor could extract this into a shared `scripts/whisperx_transcribe_json.sh` used by both commands; until then, this is an intentional, commented duplication.)

**Define once** (reused for the audio file, the JSON file, and cleanup):
- `TMP="${TMPDIR:-/tmp}"` — `TMPDIR` is frequently unset on Linux; `/tmp` is the reliable fallback (`/transcribe` itself hardcodes `/tmp`).
- `SAFE_ID` — a slug from the primary URL: lowercase host + a short hash of the full URL, sanitised to `[a-z0-9_-]`, ≤40 chars. Use the **identical** value for the audio file, JSON file, and cleanup so the read-back and cleanup resolve the same paths.

**Steps:**
1. **Prereq gate (before downloading anything).** Verify the transcription toolchain: `~/venvs/whisperx/bin/python3 -c "import whisperx" && command -v ffmpeg && command -v ffprobe`; plus `command -v yt-dlp` (YouTube) and `command -v curl` or `wget` (remote audio). If any is missing, **stop loudly** with the specific install hint and offer the Tier-1 path instead (the user pastes a published transcript). Never download audio you can't process.
2. **Get the media to a local path.** YouTube → let `yt-dlp` fetch audio (as `/transcribe` Phase 1 step 4: `-f "bestaudio[abr<=64]/worstaudio" -x --audio-format wav -o "$TMP/podcast_digest_$SAFE_ID.wav"`) and its auto-captions for the proper-noun cross-reference. Non-YouTube (resolved enclosure / RSS / direct) → download to `$TMP/podcast_digest_$SAFE_ID.<ext>` with curl/wget, then `ffprobe -v quiet -show_entries format=duration -of csv=p=0` to validate + get duration.
3. **Decide diarisation BEFORE running** (this is where delegation would have aborted). Default to diarisation for interviews. Probe the HF token yourself: `~/venvs/whisperx/bin/python3 -c "from huggingface_hub import HfApi; HfApi().whoami()" 2>/dev/null && echo ok || echo no_token`. If `ok` → `DIARIZE=True`, `NUM_SPEAKERS=2` (or `1` for a known monologue). If `no_token` → `DIARIZE=False`, proceed **non-diarised** (do not abort; the transcript will have no speaker labels — see Phase 2 for best-effort role attribution).
4. **Run the WhisperX block as a tracked background task, JSON → durable file.** Use `/transcribe` Phase 2's exact Python block with the five variables set (`INPUT_FILE_PATH="$TMP/podcast_digest_$SAFE_ID.<ext>"`, `DIARIZE`, `NUM_SPEAKERS`, `MIN_SPEAKERS=None`, `MAX_SPEAKERS=None`), but **redirect stdout to a durable path and run detached**:
   ```bash
   JSON_OUT="$TMP/podcast_digest_$SAFE_ID.json"; ERR="$TMP/podcast_digest_$SAFE_ID.err"
   ~/venvs/whisperx/bin/python3 > "$JSON_OUT" 2>"$ERR" <<'PYEOF' &
   # … /transcribe Phase 2 Python block, ending in print(json.dumps({"segments": …, "language": …})) …
   PYEOF
   ```
   On CPU with ~1hr+ audio this is slow — run it as a background Bash task (no timeout). On completion, check the exit code; on failure read `$ERR` for diagnostics; on success Read `$JSON_OUT`.
5. **Format in-context** using `/transcribe` Phase 3 **steps 1–3 only** (parse → format with `[H:MM:SS]` + any speaker labels → cleanup pass). **Do NOT run step 4 (display), or steps 5–8 (rename/save/discuss prompts).** The digest needs the transcript in context — not dumped to the user, not saved to disk.
6. **Cleanup:** remove `$TMP/podcast_digest_$SAFE_ID.*` once synthesis is complete.

- **Caption cross-reference** is inherited only for YouTube sources (where `yt-dlp` fetched captions for the proper-noun divergence check). For non-YouTube audio, accept the WhisperX transcript as-is.

## Arguments

`$ARGUMENTS` — one episode URL. Optionally a second URL as a **manual media fallback** (a YouTube version or a direct audio link), used only if the primary can't be resolved. If no URL is provided, ask for one.

## Workflow

### Phase 0 — Validate & detect source

Classify the **primary URL**:
- contains `youtube.com/watch` or `youtu.be/` → **YouTube**
- contains `pca.st` or `pocketcasts.com` → **Pocket Casts**
- ends in `.mp3`/`.m4a`/`.ogg`/`.wav`/`.flac` → **direct audio**
- otherwise → **episode webpage**

### Phase 1 — Acquire transcript (two-tier ladder)

#### Tier 1 — published transcript on the page (try first whenever there is a webpage)

For YouTube primaries, also check the description / linked show-notes for an official transcript link.

1. **Scrape ladder:** `mcp__firecrawl__firecrawl_scrape` with `waitFor: 5000` if firecrawl MCP is available → else `WebFetch` → if neither tool is available or both fail, **skip Tier 1 and go to Tier 2** (don't stall; note the gap in the final report). This degradation is expected for users without the firecrawl MCP.
2. **Guard against show-notes masquerading as a transcript.** Judge on *structure*, not a single threshold: accept as a genuine transcript if it has sustained episode-specific prose AND either (a) visible turn-taking / speaker markers, or (b) for a single-speaker talk, continuous prose, or (c) the page explicitly labels it a transcript. Reject obvious show-notes: a short episode summary, a few-bullet description, or a clear excerpt. If duration is known, a rough sanity floor of ≳80–100 words per minute of audio helps — but **don't reject a labelled transcript just for being below it** (edited transcripts, slow speakers, and ad-stripped versions run lighter), and when duration is unknown (the common pure-webpage case) fall back to the structural test (a) / (b) / (c) above. State which you found and why.
3. If genuine, use it directly. **Carry timestamps only if the transcript already contains them** (many published transcripts have none — handle per Phase 2). Harvest episode metadata for the filename + frontmatter using this **precedence:** structured page metadata (`og:`/`<meta>` tags, JSON-LD) or RSS fields (`<title>`, `<pubDate>`, `<itunes:episode>`) first; scraped body text last; a YouTube mirror's title only when YouTube is the primary source.

#### Tier 2 — transcribe it ourselves (no usable published transcript)

1. **Resolve to a media URL** (the *Transcription core* above then handles prereqs, download, diarisation decision, and the WhisperX run):
   - **YouTube** → the YouTube URL itself (the core lets `yt-dlp` fetch audio + captions).
   - **Pocket Casts** → resolve to an audio enclosure URL (see *Pocket Casts resolution* below).
   - **direct audio** → the URL as-is.
   - **episode webpage** → find a media URL: (i) an audio enclosure / `<audio>` / `og:audio` on the page; (ii) else a linked YouTube version — *prefer this*, it also gets captions; (iii) else the show's RSS feed `<enclosure>`.
2. **Run the Transcription core** (above) on that media URL → a cleaned, timestamped (and, where the HF token allowed, diarised) transcript in context. No caption cross-reference for non-YouTube primaries.
3. **Discard the raw transcript** — it is never written to disk; the core removes its `$TMP/podcast_digest_$SAFE_ID.*` temp files after synthesis.

### Phase 2 — Synthesise the digest (cruxes-first)

From the in-context transcript, produce, in this order:

1. **`## Cruxes` (2–4).** The non-obvious, contested, or surprising moments — disagreements, claims that update a prior, strong assertions. Each crux:
   - 1–3 sentences capturing the *substance* of the exchange (synthesis, not a quote dump);
   - **speaker attribution** — when the transcript is diarised, resolve `Speaker 1/2` to real names from the episode metadata; if you can't confidently map a label to a person, attribute by role ("the host" / "the guest"). When transcription ran **non-diarised** (no HF token), there are no speaker labels at all — infer host/guest from conversational cues as best-effort, and omit attribution on a crux rather than guess. Say which case applies in the report;
   - a `[H:MM:SS]` **jump-to timestamp** at the start of that exchange. (Tier 2: free from WhisperX. Tier 1: only if the transcript carried timestamps — otherwise omit timestamps and note this once.)
2. **`## Claims & Facts`.** The "got-the-content" insurance layer — capture all *major* claims, frameworks, named entities, numbers, and recommendations as tight bullets, **grouped by theme/segment**. Omit banter, ads, repetition, and purely illustrative anecdotes unless they carry the argument. Synthesis over transcription — this is not a re-transcription. "Comprehensive" means every load-bearing point, not every sentence.
3. **No verdict.** No rating, no star score, no "worth listening?" line. Purely descriptive — the user decides.

### Phase 3 — Choose destination, then duplicate-check

The duplicate-check must grep the *actual* destination, so choose it first.

1. **Choose destination (no hardwired path).** Propose a save folder — default inferred from the current working directory; if a podcast/notes folder already exists at or under the CWD, offer it (detect, never create or assume). Propose a filename too. Both are user-overridable. If there's no obvious local content folder, **ask** rather than guessing.
2. **Duplicate-check the chosen folder:** grep it (recursively) for the source URL, then for 2–3 distinctive title keywords plus the speaker surname. A pre-existing file for the same episode (even one tagged `transcript` rather than `digest`) is a legitimate hit → surface it and ask whether to write the digest alongside, update, or skip. Never silently duplicate.

### Phase 4 — Write the digest

Write to the destination chosen in Phase 3.

- **Filename default:** `{Speaker} - {Title} ({Source}, {Year}).md`, falling back to `{Speaker} - {Title} ({YYYY-MM-DD}).md` when there's no clean show/source tag. Keep it clean: `{Speaker}` is the bare headline name with any parenthetical handle stripped (e.g. `Patrick McKenzie`, not `Patrick McKenzie (patio11)`) so it doesn't nest inside the filename's own parentheses; `{Source}` is a **short show slug** (e.g. `Complex Systems`, `a16z`), not the full `podcast` field.
- **Frontmatter default** (user can override):
  ```yaml
  ---
  title: "{Episode title, without the show name}"
  date: {YYYY-MM-DD episode publish date}
  source: {primary episode URL}
  speaker: {Headline speaker(s)}
  podcast: {Full show name}
  episode: {number if known, else omit}
  tags:
    - digest
    - {2–4 topic tags, kebab-case}
  ---
  ```
  Note the tag is `digest`. Body: `**Episode description:**` line (+ any source link) → `---` → `## Cruxes` → `## Claims & Facts`.
- **Locale:** do not hardcode a spelling dialect — follow the user's CLAUDE.md locale for localisation, like the other template commands.
- No running index — each digest is a standalone file.

### Phase 5 — Verify & report

1. Confirm the file exists at the expected path.
2. Report: the file path; which tier acquired the transcript (and, for Tier 1, why it was or wasn't usable); whether timestamps are present; any gaps (e.g. "couldn't resolve the Pocket Casts audio — used the user-supplied YouTube link", "published transcript had no timestamps, cruxes are untimestamped", "no diarisation — HF token absent, attributed by role").

## Pocket Casts (`pca.st`) audio resolution

`yt-dlp` has no Pocket Casts extractor, so don't point it at a `pca.st` URL. This step only **resolves a media URL** — the Transcription core then downloads and transcribes it:

1. **Scrape the pca.st episode page** (`firecrawl_scrape waitFor:5000` → `WebFetch`) for an `og:audio` / enclosure URL. This also harvests episode metadata.
2. **RSS fallback:** from the scraped podcast name, find the show's RSS feed (page link, or a search for "{podcast name} RSS feed"), fetch it, match the episode by title + publish date, and read its `<enclosure url="...">` (a plain HTTP MP3).
3. Hand the resolved media URL to the *Transcription core* above (which downloads it to `$TMP/podcast_digest_$SAFE_ID.<ext>`, `ffprobe`-validates, and runs WhisperX). Don't point `yt-dlp` at the `pca.st` URL itself — only at an already-resolved CDN URL if used as a convenience downloader.

**Graceful failure** (all paths fail / JS-gated page / ambiguous feed match / no scrape tool available): stop and ask — "I couldn't resolve the audio from that link. Please paste (a) the YouTube URL for this episode, (b) a direct audio/MP3 link, or (c) the show's RSS feed URL." — then re-enter Tier 2 with whatever is provided. Never produce a contentless digest.

## Edge cases

- **Very long (2–3 hr) episodes:** transcription routes to a background task (slow on CPU). Synthesise section-by-section if needed, but consolidate cruxes to **2–4 globally**, not per-section.
- **Published transcript without timestamps:** keep the cruxes, omit `[H:MM:SS]`, and state once in the report that timestamps weren't available. Don't silently transcribe again just for timestamps unless the user asks.
- **Single-speaker talk:** set `NUM_SPEAKERS=1` (or run non-diarised) in the Transcription core; attribute cruxes to the one speaker.
- **Non-English episode:** WhisperX detects and aligns the language; write the digest in English and note the source language.
- **Metadata for the filename:** prefer structured metadata (RSS `<pubDate>`, og tags, `yt-dlp --print`) over scraped body text. If the publish year is genuinely unobtainable, note the assumption rather than guessing a value.

## Guidelines

- **Self-contained.** This command runs without delegating to any other command at runtime — the Transcription core is self-contained. It cites `/transcribe` only as the *reference* for the WhisperX block (both ship in the same template; keep them in sync). It references no personal/non-template command.
- **Synthesis over transcription.** The digest must be more useful than the raw audio — distil, don't copy.
- **Never invent.** Don't fabricate a date, number, name, or quote that isn't in the transcript or verified metadata. Omit or flag instead.
- **Descriptive, never evaluative.** The skill reports what's in the episode; the user decides whether to listen.

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
