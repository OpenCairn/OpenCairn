---
name: podcast-digest
description: Digest an informational podcast/talk episode from a URL — existing transcript or captions, else local/cloud WhisperX — into a cruxes-first written summary
---

# Podcast Digest — Episode to Written Digest

Given a single episode URL, produce a written **digest** of an informational podcast or talk so the user can get the content without listening, and decide for themselves whether the episode is worth a full listen. The digest is **purely descriptive — it never rates the episode or says whether it's "worth it."** That call stays with the user.

This skill adapts the Claude-side `transcribe` skill's WhisperX core for the transcription step (see *Transcription core* below) and inlines a scrape/duplicate-check/synthesis pattern of its own. The **local** transcription path is self-contained. The optional **cloud** path delegates to `$transcribecloud` only when that Codex skill is installed; otherwise it remains unavailable rather than pretending a Claude command is callable from Codex.

## When to use

When the user pastes an episode URL (a show's episode page, a YouTube video, a Pocket Casts `pca.st` link, or a direct audio link) and wants the *content* rather than the listening experience. Triggers: "digest this", "digest this episode", "what's in this podcast", "summarise this talk/episode".

## Transcription core (Tiers 2–3) — self-contained, adapted from the canonical transcribe source

This section powers **Tiers 2 and 3** of the Phase 1 ladder — reached only when **Tier 1 (an existing transcript or auto-captions) yielded nothing usable**. The engine fork below decides local (Tier 2) vs cloud (Tier 3).

The transcribe source is prose, not a callable subroutine, so this skill does **not** delegate to it at runtime. Instead it owns the local transcription block. Treat `${OPENCAIRN_REPO:-$HOME/repos/OpenCairn}/.claude/commands/transcribe.md` Phase 2 as the canonical template-repository reference when that checkout exists; otherwise use the bundled block below as authoritative for the installed skill. A future refactor may extract a shared script; until then this is intentional duplication.

### Engine fork — local WhisperX vs `$transcribecloud` — decide BEFORE downloading

This box is CPU-bound unless it has an Nvidia GPU; on CPU a ~1 hr episode takes tens of minutes. `$transcribecloud` runs the same WhisperX on a rented RunPod GPU — far faster for long audio, but it **costs money** and needs `runpodctl` + RunPod credits. Before offering that branch, verify `${CODEX_HOME:-$HOME/.codex}/skills/transcribecloud/SKILL.md` exists. If it does not, say the Codex cloud dependency is not ported and offer local CPU or a published/pasted transcript. Choose the engine up front — get the duration without a full download: **YouTube** → `yt-dlp --print "%(duration)s" URL`; **non-YouTube** → first resolve a media URL (per *Tier 2 → Resolve to a media URL* below), then `ffprobe` it (or read the HTTP `Content-Length`/headers) for duration. Resolving the media URL here also feeds the cloud handoff below:

1. **Probe the local GPU:** `~/venvs/whisperx/bin/python3 -c "import torch; print(torch.cuda.is_available())"`. A traceback (missing venv, `ModuleNotFoundError`) is neither `True` nor `False` — it means the local toolchain itself is broken: treat it as CPU-only for the fork *and* expect the Step-1 prereq gate to fail too, leaving cloud and the Tier-1 options.
2. **Fork on (GPU × duration), or an explicit user request:**
   - **Local GPU present (`True`)** → **local core** (Steps below). Fast at any length; never pay for cloud.
   - **CPU-only (`False`) and audio ≲ 20–30 min** → **local core**, run as a background task. Tell the user the rough ETA so the wait isn't a surprise.
   - **CPU-only and audio > ~30 min**, or the user explicitly asks for cloud/RunPod → prefer `$transcribecloud` if installed. It's a paid, outward action, so surface the trade-off and let the user pick — don't spend their money silently: *local CPU = free but slow; cloud = faster but paid and needs credits.*
3. **Cloud prereq check before committing** (after confirming the Codex skill exists): `command -v runpodctl && runpodctl pod list`. If `runpodctl` is missing or there are no credits, say so and **fall back to the local core** rather than stalling — but first confirm the local prereq gate actually passes. If WhisperX is also missing, don't promise a local run that can't happen: stop with the install hint, or offer Tier 1 (captions / a pasted transcript).

**If cloud is chosen — invoke `$transcribecloud`** (only after its installed `SKILL.md` has been read and its paid-action gate is honoured).
- **Pass a target `$transcribecloud` actually accepts — a YouTube URL or a *local file path*, never an arbitrary page/feed URL.** YouTube primary → hand it the YouTube URL. **Any non-YouTube source** (Pocket Casts / episode webpage / RSS / direct audio) → first resolve + download the audio locally to `$TMP/podcast_digest_$SAFE_ID.<ext>` (Step 2's mechanism — Tier 3 still needs this one download) and pass **that file path**. Handing it the raw page / `pca.st` / RSS URL fails — it ingests only YouTube URLs and local files.
- **Use a dedicated output dir** so the result file is unambiguous (`--output "$TMP"` alone is not — `$transcribecloud` names outputs after the source, and `$TMP` may hold prior runs): `CLOUD_OUT="$TMP/podcast_digest_${SAFE_ID}_cloud"`. Invoke with `--output "$CLOUD_OUT"` and `--no-published`, plus `--diarize` / `--speakers N` per the diarisation intent — but only if the local HF token file is present. Let its upfront cost/GPU confirmation run, then decline its optional speaker-rename/synthesis/index tails: this digest owns attribution and synthesis.
- It transcribes on the pod, so **skip local Steps 1, 2 and 4** (except the non-YouTube download above) — the local toolchain gate doesn't apply, and Step 3 runs in its cloud-branch form (token *file* check, no local venv). `$CLOUD_OUT` holds the final transcript only after its Phase 8 markdown save (retrieval lands raw JSON in `/tmp` first) — once Phase 8 has saved, **Read the single transcript `.md` inside `$CLOUD_OUT`** into context and continue at Phase 2 (synthesis). Cleanup removes `$CLOUD_OUT` *and* any `$TMP/podcast_digest_$SAFE_ID.*` (Step 6).

**Define once — used by *all three tiers*** (the Tier-1 caption file, the Tier-2 audio + JSON, the Tier-3 cloud download, and every cleanup). Shell variables don't survive between Bash calls, so **recompute both lines at the top of every Bash call that touches these paths** — they are a deterministic function of the primary URL, so each call reconstructs the identical paths with nothing carried. Derive them from Phase 0 onward, before attempting Tier 1 — they are *not* local-core-only:
```bash
TMP="${TMPDIR:-/tmp}"   # TMPDIR is often unset on Linux; /tmp is the reliable fallback
SAFE_ID="$(printf '%s' "<PRIMARY_URL>" | tr '[:upper:]' '[:lower:]' | sed -E 's#^https?://##; s#[^a-z0-9]+#-#g; s#(^-|-$)##g' | cut -c1-30)-$(printf '%s' "<PRIMARY_URL>" | cksum | cut -d' ' -f1)"
```
This is `_shared-rules.md` §15's slug recipe — use it verbatim (same URL string, no trailing-slash or case variation) so the audio file, JSON file, cloud dir, read-back, and cleanup all resolve the same paths.

**Steps:**
1. **Prereq gate (before downloading anything) — local branch only.** On the cloud branch the transcription runs on the pod, so use the installed `$transcribecloud` prerequisites instead. For a local run, verify the transcription toolchain: `~/venvs/whisperx/bin/python3 -c "import whisperx" && command -v ffmpeg && command -v ffprobe`; plus `command -v yt-dlp` (YouTube) and `command -v curl` or `wget` (remote audio). If any is missing, stop with the specific install hint — but first offer any Tier-1 option still untried. Never download audio you can't process.
2. **Get the media to a local path.** YouTube → let `yt-dlp` fetch audio using `-f "bestaudio[abr<=64]/worstaudio" -x --audio-format wav -o "$TMP/podcast_digest_$SAFE_ID.wav"` and fetch auto-captions for the proper-noun cross-reference. Non-YouTube → download the resolved enclosure/direct audio to `$TMP/podcast_digest_$SAFE_ID.<ext>`, then validate and measure it with `ffprobe`.
3. **Decide diarisation BEFORE running.** Default to diarisation for interviews. Probe the HF token yourself — **local branch:** `~/venvs/whisperx/bin/python3 -c "from huggingface_hub import HfApi; HfApi().whoami()" 2>/dev/null && echo ok || echo no_token`; **cloud branch:** `[ -s ~/.cache/huggingface/token ] && echo ok || echo no_token`. If `ok`, use two speakers by default (one for a known monologue). If `no_token`, proceed non-diarised unless the user explicitly required speaker labels; then surface the limitation and ask which route they want.
4. **Run the WhisperX block as a tracked Codex exec session.** Use the canonical Phase 2 Python block with the five variables set (`INPUT_FILE_PATH="$TMP/podcast_digest_$SAFE_ID.<ext>"`, `DIARIZE`, `NUM_SPEAKERS`, `MIN_SPEAKERS=None`, `MAX_SPEAKERS=None`). Do not use shell `&`. If the command yields a live session, collect it with the session's polling/input mechanism until completion so the exit status remains observable. **The block writes the segments JSON to a file of its own choosing and prints only that path** — do not redirect stdout expecting JSON:
   ```bash
   ERR="$TMP/podcast_digest_$SAFE_ID.err"
   ~/venvs/whisperx/bin/python3 2>"$ERR" <<'PYEOF'
   # … canonical Phase 2 Python block, writing JSON to its own path and ending in print(out_path) …
   PYEOF
   ```
   With `INPUT_FILE_PATH` as above, that derived path is `/tmp/transcribe_segments_podcast_digest_$SAFE_ID.json` (the block hardcodes `/tmp`, not `$TMP`) — outside the `$TMP/podcast_digest_$SAFE_ID.*` sweep, so Step 6 removes it explicitly. On completion, check the exec session's exit code; on failure inspect `$ERR`; on success read the JSON at the printed path.
5. **Format in-context** using the canonical Phase 3 formatting rules: parse, format with duration-dependent timestamps and any speaker labels, then clean up. Do not display or run rename/save/discuss tails. The digest needs the transcript in context, not as a separate user-facing artefact.
6. **Cleanup:** validate the targets before deleting anything: `SAFE_ID` must be non-empty and contain only letters, digits, `.`, `_`, or `-`; `TMP` must be an existing absolute scratch directory other than `/`; and, if set, `CLOUD_OUT` must equal `$TMP/podcast_digest_${SAFE_ID}_cloud` and must not equal `$TMP`. Then remove only scratch entries with the exact `podcast_digest_${SAFE_ID}` prefix, the exact `/tmp/transcribe_segments_podcast_digest_${SAFE_ID}.json` file, and the validated cloud directory. If any assertion fails, leave the scratch files in place and report them instead of broadening the target.

- **Caption cross-reference** is inherited only for YouTube sources (where `yt-dlp` fetched captions for the proper-noun divergence check). For non-YouTube audio, accept the WhisperX transcript as-is. (This is the *Tier-2* role for captions — fixing WhisperX proper nouns. In **Tier 1**, captions *are* the transcript, with no second source to cross-check — see the Tier-1 proper-noun caveat.)

## Arguments

Interpret the free-text arguments following `$podcast-digest` as one episode URL and, optionally, a second URL as a **manual media fallback** (a YouTube version or a direct audio link), used only if the primary can't be resolved. If no URL is provided, ask for one.

## Workflow

### Phase 0 — Validate & detect source

Classify the **primary URL**:
- contains `youtube.com/watch` or `youtu.be/` → **YouTube**
- contains `pca.st` or `pocketcasts.com` → **Pocket Casts**
- ends in `.mp3`/`.m4a`/`.ogg`/`.wav`/`.flac` → **direct audio**
- otherwise → **episode webpage**

Then **derive `TMP` and `SAFE_ID` from the primary URL** (see *Transcription core → Define once* for the exact recipe, and recompute them at the top of each later Bash call) — every tier, including Tier 1, uses them for temp files and cleanup.

### Phase 1 — Acquire transcript (three-tier ladder)

Climb from cheapest to most expensive and stop at the first tier that yields a usable transcript: **Tier 1** existing text (free, instant, inline) → **Tier 2** local WhisperX (free, local compute) → **Tier 3** cloud WhisperX (paid GPU). **Always try Tier 1 first** — it needs no GPU, no audio download, and no `whisperx` toolchain. The Tier 2 vs Tier 3 choice is made by the *Engine fork* in the *Transcription core*, not by sequential fall-through.

#### Tier 1 — use an existing transcript (published transcript *or* auto-captions)

Ready-made text the running instance fetches directly — no transcription engine. **Quality order: a published/official transcript beats a manual caption track beats auto-captions** — auto-captions mangle proper nouns (see caveats). So check for a published transcript *first* (1a); fall to captions (1b) only when there's none. For non-YouTube sources a published transcript is usually the only Tier-1 option; for YouTube, scan the description / show-notes for an official transcript link before defaulting to the auto-captions.

**1a — published/official transcript** (episode webpage / show-notes; for YouTube also check the description for an official transcript link):
- **Scrape ladder (`_shared-rules.md` §26 order):** the **§15 extractor** first (needs only `curl`/`pandoc`/`python3`+`bs4`+`lxml`; extracts the body to a file, then read it into context) → else a configured fetch MCP → else Codex web tooling → if all rungs are unavailable or fail, fall to captions (or Tier 2/3); don't stall, note the gap in the final report.
- **Guard against show-notes masquerading as a transcript.** Judge on *structure*, not a single threshold: accept as a genuine transcript if it has sustained episode-specific prose AND either (a) visible turn-taking / speaker markers, or (b) for a single-speaker talk, continuous prose, or (c) the page explicitly labels it a transcript. Reject obvious show-notes: a short episode summary, a few-bullet description, or a clear excerpt. If duration is known, a rough sanity floor of ≳80–100 words per minute of audio helps — but **don't reject a labelled transcript just for being below it** (edited transcripts, slow speakers, and ad-stripped versions run lighter), and when duration is unknown (the common pure-webpage case) fall back to the structural test (a) / (b) / (c) above. State which you found and why.

**1b — captions** (YouTube fallback when there's no published transcript). Fetch *without* downloading audio (recompute `TMP`/`SAFE_ID` in this call per *Define once*, so the cleanup sweep also removes the caption file):
```bash
yt-dlp --write-auto-subs --write-subs --sub-langs "en.*" --skip-download --sub-format vtt \
  -o "$TMP/podcast_digest_$SAFE_ID" "URL"
```
For a known non-English source, swap `en.*` for that language's code; if English yields nothing, retry without `--sub-langs` to take whatever exists (digest in English per *Edge cases*). Then **glob the result** — yt-dlp suffixes a language/format tag, so the file is `$TMP/podcast_digest_$SAFE_ID*.vtt` (e.g. `.en.vtt`, `.en-orig.vtt`), not a fixed name; if both a manual (`--write-subs`) and an auto (`--write-auto-subs`) track landed, **prefer the manual one** (human-authored — far better proper nouns than the auto track). Parse it to de-duplicated, timestamped lines (strip the `<…>` inline tags and the repeated rolling-window cue lines). **Quality guard:** get the duration (`yt-dlp --print "%(duration)s" URL`) and check density (≳80–100 words per minute of audio) — treat that as a caution band, not a hard reject on its own; reject an empty / music-only / garbled caption track and fall to Tier 2/3.

**Tier-1 caveats (both sources):**
- **No diarisation.** Captions never carry speaker labels; published transcripts only sometimes show turn-taking. Attribute speakers by inference in Phase 2. **If the user explicitly needs guaranteed speaker labels or verbatim-exact quotes, skip Tier 1** and transcribe with diarisation (Tier 2/3).
- **Proper nouns are unverified — resolve them per `_shared-rules.md` §15 "Names and speakers"** (the page's human-written text outranks the transcript body on identity; split `$BODY` at the transcript heading, then compare stem tokens across the two halves — a single grep cannot tell agreement from divergence). Applies to both Tier-1 sources: 1a's transcript is often auto-generated despite being published, and 1b's captions have no second machine source to cross-check. Digest-specific: run that comparison **before** a name enters the digest, and **never invent** or silently pass a garbled name through.
- **Timestamps:** captions always carry them; published transcripts only sometimes (handle per Phase 2).
- **Cleanup:** a Tier-1-only run still leaves the caption VTT in `$TMP`; use the same validated, exact-prefix cleanup contract as *Transcription core* Step 6.

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

#### Tier 3 — transcribe in the cloud (`$transcribecloud`)

No usable Tier-1 transcript, and the *Engine fork* selects **cloud** (CPU + audio > ~30 min, or a batch, or an explicit cloud/RunPod request). The fork has already surfaced the paid-vs-slow trade-off and got the user's okay. **Execute the *Engine fork → "If cloud is chosen"* bullets** — they are the single source of truth for the handoff. In brief:

1. **Invoke `$transcribecloud`** with a target it accepts — a YouTube URL, or (for any non-YouTube source) the audio downloaded to `$TMP/podcast_digest_$SAFE_ID.<ext>` and passed as a local file path — using `--output "$CLOUD_OUT"`, `--no-published`, and the confirmed diarisation/language flags.
2. **Read the single transcript file inside `$CLOUD_OUT`** into context.
3. **Discard** `$CLOUD_OUT` and any `$TMP/podcast_digest_$SAFE_ID.*` in cleanup (Step 6).

### Phase 2 — Synthesise the digest (cruxes-first)

From the in-context transcript, produce, in this order:

1. **`## Cruxes` (2–4).** The non-obvious, contested, or surprising moments — disagreements, claims that update a prior, strong assertions. Each crux:
   - 1–3 sentences capturing the *substance* of the exchange (synthesis, not a quote dump);
   - **speaker attribution** — when the transcript is **diarised** (Tier 2/3 with an HF token), resolve `Speaker 1/2` to real names from the episode metadata; if you can't confidently map a label to a person, attribute by role ("the host" / "the guest"). When the transcript is **not diarised** — any Tier-1 source (captions / published transcript), or a Tier-2/3 run without a token — there are no reliable speaker labels, and **a Tier-1a transcript's own labels are not an exception** (auto-generated ones guess by voice clustering). Resolve them per `_shared-rules.md` §15 "Names and speakers" — scan the human-written half for lines carrying a leading timestamp, which is the segment map; the *heading* outline is usually navigational and carries no times, so a non-empty outline is not a map — then conversational cues, and omit attribution on a crux rather than guess. Say which case applies in the report, and flag mislabelling you corrected rather than presenting the transcript's labels as sound;
   - a **jump-to timestamp** at the start of that exchange, in the transcript's own format (`[MM:SS]` under an hour, `[H:MM:SS]` above). (Available from WhisperX in Tier 2/3 and from caption VTT in Tier 1b; a Tier-1a published transcript has them only if it carried them — otherwise omit timestamps and note this once.)
2. **`## Claims & Facts`.** The "got-the-content" insurance layer — capture all *major* claims, frameworks, named entities, numbers, and recommendations as tight bullets, **grouped by theme/segment**. Omit banter, ads, repetition, and purely illustrative anecdotes unless they carry the argument. Synthesis over transcription — this is not a re-transcription. "Comprehensive" means every load-bearing point, not every sentence.
3. **No verdict.** No rating, no star score, no "worth listening?" line. Purely descriptive — the user decides.

### Phase 3 — Choose destination, then duplicate-check

The duplicate-check must grep the *actual* destination, so choose it first.

1. **Choose destination (no hardwired path).** Propose a save folder — default inferred from the current working directory; if a podcast/notes folder already exists at or under the CWD, offer it (detect, never create or assume). Propose a filename too. Both are user-overridable. If there's no obvious local content folder, **ask** rather than guessing.
2. **Duplicate-check the chosen folder:** grep it (recursively) for the source URL, then for 2–3 distinctive title keywords plus the speaker surname. A pre-existing file for the same episode (even one tagged `transcript` rather than `digest`) is a legitimate hit → surface it and ask whether to write the digest alongside, update, or skip. Never silently duplicate.

### Phase 4 — Write the digest

Write to the destination chosen in Phase 3. If the destination is inside the resolved vault, draft outside the vault and install it through `locked-edit.sh`: use `--append` when the file is missing; for an approved update or overwrite, re-read the existing file and use a unique literal OLD block with `--replace`. Never write a vault file directly. Outside the vault, use the normal Codex file-edit workflow.

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
- **Locale:** do not hardcode a spelling dialect — follow the applicable `AGENTS.md` locale.
- No running index — each digest is a standalone file.

### Phase 5 — Verify & report

1. Confirm the file exists at the expected path.
2. Report: the file path; **which of the three tiers acquired the transcript** (e.g. "Tier 1a — published transcript", "Tier 1b — captions (YouTube auto/manual)", "Tier 2 — local WhisperX, diarised", "Tier 3 — cloud") and why lower tiers were skipped or failed; whether timestamps are present; any gaps (e.g. "Tier-1 captions — non-diarised, speakers attributed by inference; proper nouns unverified", "couldn't resolve the Pocket Casts audio — used the user-supplied YouTube link", "published transcript had no timestamps, cruxes are untimestamped", "no diarisation — HF token absent, attributed by role").

## Pocket Casts (`pca.st`) audio resolution

`yt-dlp` has no Pocket Casts extractor, so don't point it at a `pca.st` URL. This step only **resolves a media URL** — the Transcription core then downloads and transcribes it:

1. **Scrape the pca.st episode page** (`_shared-rules.md` §26 ladder: static extract → fetch MCP → Codex web tooling) for an `og:audio` / enclosure URL. This also harvests episode metadata.
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

- **Self-contained on the local path; optional installed-skill delegation on the cloud path.** The local transcription core runs without delegating. The cloud engine may invoke `$transcribecloud` only when that Codex skill is installed; otherwise the branch is explicitly unavailable.
- **Synthesis over transcription.** The digest must be more useful than the raw audio — distil, don't copy.
- **Never invent.** Don't fabricate a date, number, name, or quote that isn't in the transcript or verified metadata. Omit or flag instead.
- **Descriptive, never evaluative.** The skill reports what's in the episode; the user decides whether to listen.

---

**Skill monitor:** Also follow the instructions in `~/.codex/skills/_skill-monitor.md`.
