---
name: podcast-digest
description: Digest an informational podcast/talk episode from a URL — existing transcript or captions, else local/cloud WhisperX — into a cruxes-first written summary
---

# Podcast Digest — Episode to Written Digest

Given a single episode URL, produce a written **digest** of an informational podcast or talk so the user can get the content without listening, and decide for themselves whether the episode is worth a full listen. The digest is **purely descriptive — it never rates the episode or says whether it's "worth it."** That call stays with the user.

This skill adapts `/transcribe`'s WhisperX core for the transcription step (see *Transcription core* below) and inlines a scrape/duplicate-check/synthesis pattern of its own. The **local** transcription path runs self-contained — it *owns* the WhisperX core rather than delegating to `/transcribe`. The one permitted runtime delegation is the optional **cloud** path: for long audio on a GPU-less box it hands off to `/transcribecloud` for RunPod GPU transcription (see the engine fork in *Transcription core*).

## When to use

When the user pastes an episode URL (a show's episode page, a YouTube video, a Pocket Casts `pca.st` link, or a direct audio link) and wants the *content* rather than the listening experience. Triggers: "digest this", "digest this episode", "what's in this podcast", "summarise this talk/episode".

## Transcription core (Tiers 2–3) — self-contained, adapted from `/transcribe`

This section powers **Tiers 2 and 3** of the Phase 1 ladder — reached only when **Tier 1 (an existing transcript or auto-captions) yielded nothing usable**. The engine fork below decides local (Tier 2) vs cloud (Tier 3).

`/transcribe` is a *prose* command, not a callable subroutine — so this skill does **not** delegate to it at runtime. Delegating would (a) trigger `/transcribe`'s interactive save/rename/discuss tail, and (b) **critically**, when diarisation is requested but no HF token is present, `/transcribe` *stops during its own validation, before transcribing* — so a "fall back to non-diarised" decision made on this skill's side would never be reached. Instead this skill **owns** the transcription, adapting `/transcribe`'s WhisperX core. Treat `/transcribe` Phase 2 as the **canonical reference** for the WhisperX Python block — update both together if the model or parameters change. (A future refactor could extract this into a shared `scripts/whisperx_transcribe_json.sh` used by both commands; until then, this is an intentional, commented duplication.)

### Engine fork — local WhisperX (`/transcribe` core) vs `/transcribecloud` — decide BEFORE downloading

This box is CPU-bound unless it has an Nvidia GPU; on CPU a ~1 hr episode takes tens of minutes. `/transcribecloud` runs the *same* WhisperX on a rented RunPod GPU — far faster for long audio, but it **costs money** and needs `runpodctl` + RunPod credits. Choose the engine up front — get the duration without a full download: **YouTube** → `yt-dlp --print "%(duration)s" URL`; **non-YouTube** → first resolve a media URL (per *Tier 2 → Resolve to a media URL* below), then `ffprobe` it (or read the HTTP `Content-Length`/headers) for duration. Resolving the media URL here also feeds the cloud handoff below:

1. **Probe the local GPU:** `~/venvs/whisperx/bin/python3 -c "import torch; print(torch.cuda.is_available())"`.
2. **Fork on (GPU × duration), or an explicit user request:**
   - **Local GPU present (`True`)** → **local core** (Steps below). Fast at any length; never pay for cloud.
   - **CPU-only (`False`) and audio ≲ 20–30 min** → **local core**, run as a background task. Tell the user the rough ETA so the wait isn't a surprise.
   - **CPU-only and audio > ~30 min** (this is `/transcribecloud`'s own threshold), **or** the user explicitly asks for cloud/RunPod → **prefer `/transcribecloud`**. It's a paid, outward action, so surface the trade-off and let the user pick — don't spend their money silently: *local CPU = free but slow (~N min for an N-min episode); cloud = a few min + ~1 min setup, but ~$0.20–1 of GPU time and needs credits.*
3. **Cloud prereq check before committing** (per `/transcribecloud` Prerequisites): `command -v runpodctl && runpodctl pod list`. If `runpodctl` is missing or there are no credits, say so and **fall back to the local core** (background task) rather than stalling — but first confirm the local prereq gate (Step 1) actually passes. If WhisperX is *also* missing, don't promise a local run that can't happen: stop with the install hint, or offer Tier 1 (captions / a pasted transcript).

**If cloud is chosen — hand off to `/transcribecloud`** (the single runtime delegation this skill allows; re-inlining ~46 KB of stateful RunPod pod-provisioning is impractical, so unlike the local core there's no benefit to owning it).
- **Pass a target `/transcribecloud` actually accepts — a YouTube URL or a *local file path*, never an arbitrary page/feed URL.** YouTube primary → hand it the YouTube URL. **Any non-YouTube source** (Pocket Casts / episode webpage / RSS / direct audio) → first resolve + download the audio locally to `$TMP/podcast_digest_$SAFE_ID.<ext>` (Step 2's mechanism — Tier 3 still needs this one download) and pass **that file path**. Handing it the raw page / `pca.st` / RSS URL fails — it ingests only YouTube URLs and local files.
- **Use a dedicated output dir** so the result file is unambiguous (`--output "$TMP"` alone is not — `/transcribecloud` names outputs after the source, and `$TMP` may hold prior runs): `CLOUD_OUT="$TMP/podcast_digest_${SAFE_ID}_cloud"`. Invoke with `--output "$CLOUD_OUT"`, plus `--diarize` / `--speakers N` per the Step-3 diarisation *intent* (interview → diarise; the `no_token` branch is moot — the pod manages its own token) and `--language` if non-English is known. Let its upfront cost/GPU confirmation run — that gate is appropriate for a paid job.
- It transcribes on the pod, so **skip local Steps 2 and 4** (except the non-YouTube download above). When it finishes, **Read the single transcript file inside `$CLOUD_OUT`** into context and continue at Phase 2 (synthesis). Cleanup removes `$CLOUD_OUT` *and* any `$TMP/podcast_digest_$SAFE_ID.*` (Step 6).

**Define once — used by *all three tiers*** (the Tier-1 caption file, the Tier-2 audio + JSON, the Tier-3 cloud download, and every cleanup). **Set these in Phase 0, before attempting Tier 1** — they are *not* local-core-only:
- `TMP="${TMPDIR:-/tmp}"` — `TMPDIR` is frequently unset on Linux; `/tmp` is the reliable fallback (`/transcribe` itself hardcodes `/tmp`).
- `SAFE_ID` — a slug from the primary URL: lowercase host + a short hash of the full URL, sanitised to `[a-z0-9_-]`, ≤40 chars. Use the **identical** value for the audio file, JSON file, and cleanup so the read-back and cleanup resolve the same paths.

**Steps:**
1. **Prereq gate (before downloading anything).** Verify the transcription toolchain: `~/venvs/whisperx/bin/python3 -c "import whisperx" && command -v ffmpeg && command -v ffprobe`; plus `command -v yt-dlp` (YouTube) and `command -v curl` or `wget` (remote audio). If any is missing, **stop loudly** with the specific install hint — but first fall back to **Tier 1**, which needs none of this toolchain: for YouTube, auto-captions need only `yt-dlp`; otherwise the user can paste a published transcript. Never download audio you can't process.
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
6. **Cleanup:** remove `$TMP/podcast_digest_$SAFE_ID.*` once synthesis is complete — and, if the cloud path ran, `rm -rf "$CLOUD_OUT"` too.

- **Caption cross-reference** is inherited only for YouTube sources (where `yt-dlp` fetched captions for the proper-noun divergence check). For non-YouTube audio, accept the WhisperX transcript as-is. (This is the *Tier-2* role for captions — fixing WhisperX proper nouns. In **Tier 1**, captions *are* the transcript, with no second source to cross-check — see the Tier-1 proper-noun caveat.)

## Arguments

`$ARGUMENTS` — one episode URL. Optionally a second URL as a **manual media fallback** (a YouTube version or a direct audio link), used only if the primary can't be resolved. If no URL is provided, ask for one.

## Workflow

### Phase 0 — Validate & detect source

Classify the **primary URL**:
- contains `youtube.com/watch` or `youtu.be/` → **YouTube**
- contains `pca.st` or `pocketcasts.com` → **Pocket Casts**
- ends in `.mp3`/`.m4a`/`.ogg`/`.wav`/`.flac` → **direct audio**
- otherwise → **episode webpage**

Then **define `TMP` and `SAFE_ID` now** (see *Transcription core → Define once*) — every tier, including Tier 1, uses them for temp files and cleanup.

### Phase 1 — Acquire transcript (three-tier ladder)

Climb from cheapest to most expensive and stop at the first tier that yields a usable transcript: **Tier 1** existing text (free, instant, inline) → **Tier 2** local WhisperX (free, local compute) → **Tier 3** cloud WhisperX (paid GPU). **Always try Tier 1 first** — it needs no GPU, no audio download, and no `whisperx` toolchain. The Tier 2 vs Tier 3 choice is made by the *Engine fork* in the *Transcription core*, not by sequential fall-through.

#### Tier 1 — use an existing transcript (published transcript *or* auto-captions)

Ready-made text the running instance fetches directly — no transcription engine. **Quality order: a published/official transcript beats a manual caption track beats auto-captions** — auto-captions mangle proper nouns (see caveats). So check for a published transcript *first* (1a); fall to captions (1b) only when there's none. For non-YouTube sources a published transcript is usually the only Tier-1 option; for YouTube, scan the description / show-notes for an official transcript link before defaulting to the auto-captions.

**1a — published/official transcript** (episode webpage / show-notes; for YouTube also check the description for an official transcript link):
- **Scrape ladder:** `mcp__firecrawl__firecrawl_scrape` with `waitFor: 5000` if firecrawl MCP is available → else `WebFetch` → if neither tool is available or both fail, fall to 1b captions (or Tier 2/3); don't stall, note the gap in the final report. This degradation is expected for users without the firecrawl MCP.
- **Guard against show-notes masquerading as a transcript.** Judge on *structure*, not a single threshold: accept as a genuine transcript if it has sustained episode-specific prose AND either (a) visible turn-taking / speaker markers, or (b) for a single-speaker talk, continuous prose, or (c) the page explicitly labels it a transcript. Reject obvious show-notes: a short episode summary, a few-bullet description, or a clear excerpt. If duration is known, a rough sanity floor of ≳80–100 words per minute of audio helps — but **don't reject a labelled transcript just for being below it** (edited transcripts, slow speakers, and ad-stripped versions run lighter), and when duration is unknown (the common pure-webpage case) fall back to the structural test (a) / (b) / (c) above. State which you found and why.

**1b — captions** (YouTube fallback when there's no published transcript). Fetch *without* downloading audio (uses the `$TMP`/`$SAFE_ID` set in Phase 0, so the cleanup sweep also removes the caption file):
```bash
yt-dlp --write-auto-subs --write-subs --sub-langs "en.*" --skip-download --sub-format vtt \
  -o "$TMP/podcast_digest_$SAFE_ID" "URL"
```
For a known non-English source, swap `en.*` for that language's code; if English yields nothing, retry without `--sub-langs` to take whatever exists (digest in English per *Edge cases*). Then **glob the result** — yt-dlp suffixes a language/format tag, so the file is `$TMP/podcast_digest_$SAFE_ID*.vtt` (e.g. `.en.vtt`, `.en-orig.vtt`), not a fixed name; if both a manual (`--write-subs`) and an auto (`--write-auto-subs`) track landed, **prefer the manual one** (human-authored — far better proper nouns than the auto track). Parse it to de-duplicated, timestamped lines (strip the `<…>` inline tags and the repeated rolling-window cue lines). **Quality guard:** get the duration (`yt-dlp --print "%(duration)s" URL`) and check density (≳80–100 words per minute of audio) — treat that as a caution band, not a hard reject on its own; reject an empty / music-only / garbled caption track and fall to Tier 2/3.

**Tier-1 caveats (both sources):**
- **No diarisation.** Captions never carry speaker labels; published transcripts only sometimes show turn-taking. Attribute speakers by inference in Phase 2. **If the user explicitly needs guaranteed speaker labels or verbatim-exact quotes, skip Tier 1** and transcribe with diarisation (Tier 2/3).
- **Proper nouns are unverified.** With no WhisperX second source to cross-check, auto-captions mangle names (e.g. an economist's surname rendered phonetically). Correct uncertain proper nouns from your own knowledge or flag them — **never invent**; do not silently pass a garbled name into the digest.
- **Timestamps:** captions always carry them; published transcripts only sometimes (handle per Phase 2).
- **Cleanup:** a Tier-1-only run still leaves the caption VTT in `$TMP` — `rm -f "$TMP/podcast_digest_$SAFE_ID."*` after synthesis (same sweep as *Transcription core* Step 6).

Harvest episode metadata for the filename + frontmatter by this **precedence:** structured page metadata (`og:`/`<meta>` tags, JSON-LD) or RSS fields (`<title>`, `<pubDate>`, `<itunes:episode>`) first; `yt-dlp --print` for YouTube; scraped body text last.

#### Tier 2 — transcribe locally (WhisperX)

No usable Tier-1 transcript, and the *Engine fork* selects **local** (GPU present, or CPU + audio ≲ 20–30 min):

1. **Resolve to a media URL** (the *Transcription core* then handles prereqs, download, diarisation decision, and the WhisperX run):
   - **YouTube** → the YouTube URL itself (the core lets `yt-dlp` fetch audio + captions for the cross-reference).
   - **Pocket Casts** → resolve to an audio enclosure URL (see *Pocket Casts resolution* below).
   - **direct audio** → the URL as-is.
   - **episode webpage** → find a media URL: (i) an audio enclosure / `<audio>` / `og:audio` on the page; (ii) else a linked YouTube version — *prefer this*, it also gets captions; (iii) else the show's RSS feed `<enclosure>`.
2. **Run the Transcription core** (above) on that media URL → a cleaned, timestamped (and, where the HF token allowed, diarised) transcript in context. No caption cross-reference for non-YouTube primaries.
3. **Discard the raw transcript** — it is never written to disk; the core removes its `$TMP/podcast_digest_$SAFE_ID.*` temp files after synthesis.

#### Tier 3 — transcribe in the cloud (`/transcribecloud`)

No usable Tier-1 transcript, and the *Engine fork* selects **cloud** (CPU + audio > ~30 min, or a batch, or an explicit cloud/RunPod request). The fork has already surfaced the paid-vs-slow trade-off and got the user's okay. **Execute the *Engine fork → "If cloud is chosen"* bullets** — they are the single source of truth for the handoff. In brief:

1. **Hand off to `/transcribecloud`** with a target it accepts — a YouTube URL, or (for any non-YouTube source) the audio downloaded to `$TMP/podcast_digest_$SAFE_ID.<ext>` and passed as a **local file path** — using `--output "$CLOUD_OUT"` (`="$TMP/podcast_digest_${SAFE_ID}_cloud"`) plus `--diarize`/`--speakers`/`--language` per the diarisation intent.
2. **Read the single transcript file inside `$CLOUD_OUT`** into context.
3. **Discard** `$CLOUD_OUT` and any `$TMP/podcast_digest_$SAFE_ID.*` in cleanup (Step 6).

### Phase 2 — Synthesise the digest (cruxes-first)

From the in-context transcript, produce, in this order:

1. **`## Cruxes` (2–4).** The non-obvious, contested, or surprising moments — disagreements, claims that update a prior, strong assertions. Each crux:
   - 1–3 sentences capturing the *substance* of the exchange (synthesis, not a quote dump);
   - **speaker attribution** — when the transcript is **diarised** (Tier 2/3 with an HF token), resolve `Speaker 1/2` to real names from the episode metadata; if you can't confidently map a label to a person, attribute by role ("the host" / "the guest"). When the transcript is **not diarised** — any Tier-1 source (captions / published transcript), or a Tier-2/3 run without a token — there are no reliable speaker labels; infer host/guest from conversational cues as best-effort, and omit attribution on a crux rather than guess. Say which case applies in the report;
   - a `[H:MM:SS]` **jump-to timestamp** at the start of that exchange. (Available from WhisperX in Tier 2/3 and from caption VTT in Tier 1b; a Tier-1a published transcript has them only if it carried them — otherwise omit timestamps and note this once.)
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
2. Report: the file path; **which of the three tiers acquired the transcript** (e.g. "Tier 1a — published transcript", "Tier 1b — captions (YouTube auto/manual)", "Tier 2 — local WhisperX, diarised", "Tier 3 — cloud") and why lower tiers were skipped or failed; whether timestamps are present; any gaps (e.g. "Tier-1 captions — non-diarised, speakers attributed by inference; proper nouns unverified", "couldn't resolve the Pocket Casts audio — used the user-supplied YouTube link", "published transcript had no timestamps, cruxes are untimestamped", "no diarisation — HF token absent, attributed by role").

## Pocket Casts (`pca.st`) audio resolution

`yt-dlp` has no Pocket Casts extractor, so don't point it at a `pca.st` URL. This step only **resolves a media URL** — the Transcription core then downloads and transcribes it:

1. **Scrape the pca.st episode page** (`firecrawl_scrape waitFor:5000` → `WebFetch`) for an `og:audio` / enclosure URL. This also harvests episode metadata.
2. **RSS fallback:** from the scraped podcast name, find the show's RSS feed (page link, or a search for "{podcast name} RSS feed"), fetch it, match the episode by title + publish date, and read its `<enclosure url="...">` (a plain HTTP MP3).
3. Hand the resolved media URL to the *Transcription core* above (which downloads it to `$TMP/podcast_digest_$SAFE_ID.<ext>`, `ffprobe`-validates, and runs WhisperX). Don't point `yt-dlp` at the `pca.st` URL itself — only at an already-resolved CDN URL if used as a convenience downloader.

**Graceful failure** (all paths fail / JS-gated page / ambiguous feed match / no scrape tool available): stop and ask — "I couldn't resolve the audio from that link. Please paste (a) the YouTube URL for this episode, (b) a direct audio/MP3 link, or (c) the show's RSS feed URL." — then re-enter the transcription tiers (2/3) with whatever is provided. Never produce a contentless digest.

## Edge cases

- **Very long (2–3 hr) episodes:** transcription routes to a background task (slow on CPU). Synthesise section-by-section if needed, but consolidate cruxes to **2–4 globally**, not per-section.
- **Published transcript without timestamps:** keep the cruxes, omit `[H:MM:SS]`, and state once in the report that timestamps weren't available. Don't silently transcribe again just for timestamps unless the user asks.
- **Single-speaker talk:** set `NUM_SPEAKERS=1` (or run non-diarised) in the Transcription core; attribute cruxes to the one speaker.
- **Non-English episode:** WhisperX detects and aligns the language; write the digest in English and note the source language.
- **Metadata for the filename:** prefer structured metadata (RSS `<pubDate>`, og tags, `yt-dlp --print`) over scraped body text. If the publish year is genuinely unobtainable, note the assumption rather than guessing a value.

## Guidelines

- **Self-contained on the local path; one permitted delegation on the cloud path.** The local Transcription core runs without delegating — it cites `/transcribe` only as the *reference* for the WhisperX block (both ship in the same template; keep them in sync). The sole runtime delegation is the optional cloud engine, which hands off to `/transcribecloud` (see the engine fork) because re-inlining RunPod provisioning is impractical. Both delegation targets are template commands; it references no personal/non-template command.
- **Synthesis over transcription.** The digest must be more useful than the raw audio — distil, don't copy.
- **Never invent.** Don't fabricate a date, number, name, or quote that isn't in the transcript or verified metadata. Omit or flag instead.
- **Descriptive, never evaluative.** The skill reports what's in the episode; the user decides whether to listen.

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
