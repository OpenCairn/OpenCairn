---
name: transcribecloud
description: Batch transcribe audio/video on RunPod GPU cloud — for large jobs or when no local GPU is available
---

# Cloud Transcribe — Batch Audio to Text via RunPod

Batch transcribe audio or video files using WhisperX on a RunPod GPU instance. Use this instead of `$transcribe` when:
- No local GPU and total audio > 30 minutes
- Batch of multiple files (5+)
- User explicitly requests cloud/RunPod transcription

## Codex execution and authorisation

Read supporting files relative to this skill directory. Resolve `VAULT_PATH` with `"$VAULT_PATH/.claude/scripts/resolve-vault.sh"` before vault work; stop on failure. Every vault write uses `locked-edit.sh`, including transcript bodies and the batch index.

Scope and estimate first. Before provisioning, present the chosen GPU, cloud tier, live quoted rate, expected total and output directory. Honour an already-authorised paid run or budget; otherwise obtain the user's choice before spending. A local-to-cloud suggestion alone is not permission to rent a pod. Do not re-ask for a destination or speaker names already supplied.

Use a unique local scratch directory and retain its literal path across calls, along with the source manifest and created pod ID. Shell variables do not persist between exec calls. Track local long-running commands through Codex exec sessions and poll their exit status; remote setup/transcription stays detached on the pod as documented in `references/runpod.md`. Poll in intervals of at most 60 seconds and keep the user informed.

Only delete pods created for this job. Retrieve and validate results before normal deletion; on an aborted run salvage partial results when possible, then terminate the job's pod. An error does not waive cleanup. If termination cannot be verified, report the pod ID and unresolved billing state. Never claim stopped means deleted.

## Arguments

The free-text arguments following the skill invocation — one or more of:
- YouTube URLs (individual videos or playlists)
- Local file paths or directories containing audio/video files
- `--diarize` / `--diarise` — enable speaker diarisation
- `--speakers N` — exact speaker count (implies diarisation)
- `--output PATH` — output directory for transcripts (default: alongside source, or user-specified)
- `--raw` — skip the LLM cleanup pass (save unprocessed WhisperX output)
- `--language LANG` — force a Whisper language code (default `en`); set to `auto` for Whisper autodetect.
- `--no-published` — skip the published-transcript check (Phase 1.5) for single-source runs; go straight to the cloud pipeline

If no arguments provided, ask the user what to transcribe and where to store results.

## Prerequisites

- `runpodctl` installed and configured with API key
- SSH ed25519 key added to RunPod (`runpodctl ssh add-key --key-file ~/.ssh/id_ed25519.pub`)
- RunPod account with credits loaded

Check with:
```bash
command -v runpodctl && runpodctl pod list
```

If `runpodctl` is missing, report the prerequisite and use the official RunPod installation documentation. Any installation must obey the active package cooldown policy; do not bypass it with a direct binary download.

**Network-reachability note:** if the user is on a restricted network (e.g. behind GFW from China), direct SSH to RunPod datacenter IPs may silently time out (ping may work but the SSH port is filtered). In that case, fall back to proxy SSH via `ssh.runpod.io` — test reachability of that host first before spending pod time. See Phase 2 for handling.

## Workflow

### Phase 1: Scope the job

1. **Parse arguments** — separate URLs, file paths, and flags.
2. **For YouTube URLs:** Use `yt-dlp --flat-playlist --print "%(duration)s %(title)s"` to get video count and total duration. Handle playlists (expand to individual videos). Report the inventory to the user.
3. **For local files:** run `command -v ffprobe` before provisioning; if absent, report the missing dependency and stop. Then enumerate the exact requested files and get total duration via `ffprobe`. Extract audio from video formats absent from the batch script’s supported extensions before transfer. Give duplicate basenames distinct staging names and retain their original paths in the manifest so files cannot overwrite each other.
4. **Determine source type:**
   - `youtube` — URLs only, will download directly on pod (faster, no local transfer needed)
   - `local` — local files, will need transfer to pod (scp over exposed TCP, else `runpodctl send/receive` — Phase 4)
   - `mixed` — both; download URLs on pod, transfer local files separately
5. **Check GPU availability and pick one** — don't hardcode a card; query and select. Run:
   ```bash
   runpodctl gpu list
   ```
   **Select on the `available` field, not `stockStatus`.** `stockStatus: Low` does **not** mean unavailable — it is a depth hint. On a typical day most of the fleet reads `Low` while every entry still carries `available: true` and deploys fine. Treat stock as a tiebreaker only, and escalate a tier solely on an actual capacity error at create time ("This machine does not have the resources to deploy your pod"). Filtering the list down to `High`/`Medium` can exclude the entire cheap tier and push you into a needlessly expensive card.

   Pick an available GPU with enough VRAM for `large-v3` and the requested batch size, using the live quoted rate and supported cloud tier. The source workflow's candidate order is A4000 → RTX 3090 → A5000 → RTX 4090 → A40 → L40S; use actual availability and pricing to decide. Check `communityCloud` before selecting COMMUNITY; a secure-only card must use SECURE. Reconfirm if a capacity retry would exceed the authorised cost.
6. **Report to user:** file count, total duration, chosen GPU + cloud tier, estimated pod time (allow for dependency/model downloads plus transcription; use the source workflow’s approximate 15–30× realtime GPU range, not a guarantee), estimated cost.
7. **Confirm output location** only if absent from the request and not reasonably determined by its stated destination.

### Phase 1.5: Published-transcript check (single-source runs only)

A cloud run **costs money**, so the bar to spend pod time is *higher* than for local `$transcribe`: a free published transcript should win even more decisively here — including a publisher-ASR one, since "published" does not entail "human-edited" (§15 "Names and speakers" governs what you may then claim about it). Run this check after scoping (so single-vs-batch is known) and **before** provisioning a pod.

**Gate — skip this phase entirely unless ALL of the following hold:**
- The job is a **single source** — exactly one YouTube video (not a playlist) or one named podcast/talk episode. Skip for multi-file jobs, directories, playlists, or `mixed` sources — a per-file published check doesn't fit a batch and isn't worth the latency.
- `--no-published` was **not** passed.
- The source has a plausible online origin (YouTube URL, or a podcast episode the user named/linked). Skip for opaque local files with no obvious published page.
- Diarisation was **not** requested via `--diarize`/`--diarise`/`--speakers N` — a published transcript cannot satisfy a diarisation request (a user-supplied transcript URL still wins, per `$transcribe` Phase 0 step 1).

When the gate passes, read `../transcribe/SKILL.md` and run its **full discover → validate → choose** logic from Phase 0 steps 1–5 (user-supplied URL wins; else scan the YouTube description / show-notes / one web search; validate it's a *full verbatim transcript*, not show-notes or a summary; present the choice and wait — don't auto-pick). The only cloud-specific change to the choice framing: option 2 is **"run WhisperX on a paid RunPod GPU"**, so state the *dollar* cost of the cloud run alongside the fidelity tradeoff.

**If the user picks the published transcript:** the body is already at `<BODY_FILE>` from the **`_shared-rules-content.md` §15 extractor** (run during the validate step above — §15's printed `BODY=` path, reconstructable from the URL). Do **not** enter Phase 8's `For each JSON transcript file` loop (there is no JSON here), and run no LLM cleanup pass — the body is appended verbatim per §14, whoever produced it. Confirm the output dir/filename here if Phase 1 step 7 didn't (its prompt assumes a cloud run; the episode title is a sensible default filename). Stage the header and append `<BODY_FILE>` directly from disk using the locked save procedure in Phase 8 step 5. Do not route the published body through context or LLM cleanup. Header: **Date acquired** replaces **Date transcribed** for this run. **Source** = transcript URL, add an **Original media:** line for the YouTube/audio URL, **Model:** default `published transcript (provenance unverified)`, upgraded to `(source-provided, auto-generated)` on a disclaimer match near the transcript heading, or to `(human-edited)` only on a positive claim of editing (§15's three-value ladder; the unverified default is what stops a null selecting the stronger claim). Mark **Diarisation** and **Cleanup** `n/a` (or drop them), keep **Duration** only if known. Don't print the whole body to the conversation. **Names and speaker labels** in the header, filename or report follow §15 "Names and speakers" (human-written page text outranks the transcript body on identity). **Skip Phases 2–8's loop entirely — no pod is provisioned, no money spent.** Otherwise continue to Phase 2.

### Phases 2–7: Run and retrieve

Read [references/runpod.md](references/runpod.md) now and execute Phases 2–7 in order: provision, setup, transfer, batch transcription, retrieval, destruction. Preserve the pinned image/dependency pairing. If optional voice references apply, read [references/voice-references.md](references/voice-references.md) before destroying the pod; matching may need its installed environment. Continue below only after local JSON validation and confirmed pod deletion.

### Phase 8: Post-process to markdown

For each JSON transcript file:

1. **Parse segments.**

2. **Format transcript text.** The gap-threshold (1.5s), timestamp-format, and monologue-fallback rules are deliberately duplicated from `$transcribe` Phase 3 step 2 — **those clauses must stay in sync; update both files together if they change**. Voice-reference name mapping is cloud-specific:

   **Without diarisation:** Insert paragraph break wherever gap between segments exceeds 1.5 seconds. Concatenate segment text within each paragraph. Prefix each paragraph with a timestamp (`[MM:SS]` for <1hr, `[H:MM:SS]` for ≥1hr) derived from the first segment's `start`.

   **Monologue fallback.** For recordings longer than 5 minutes, after the initial split, check: is the paragraph count at least `duration_seconds / 120` (roughly one per two minutes)? If not, recompute — sort segment-to-segment gaps descending, let `N = min(floor(duration_seconds / 90), len(gaps))`, use `gaps_desc[N-1]` as the new threshold, re-split; if there are no gaps at all (`len(gaps) == 0`, e.g. a single segment), skip the fallback and keep the initial split. State the threshold used in your user-facing response.

   **With diarisation:** `word` is the only guaranteed word key. Use `.get()` for optional timing and speaker fields; retain untimed text without inventing a timestamp or gap, borrowing timing from a timed neighbour for the paragraph. Iterate over the **words** array (not segments) — a single segment often contains multiple speakers. Before grouping, **forward/back-fill any words with `speaker: None`** from their nearest non-None neighbour (pyannote occasionally leaves words unassigned; treating `None` as a new speaker produces a spurious "Speaker 4+"). Then group consecutive words by speaker. Start a new paragraph on speaker change OR >1.5s gap. Prefix each paragraph with timestamp + speaker label in bold:
   ```
   [00:00] **Speaker 1:** First speaker's text.

   [00:45] **Speaker 2:** Second speaker responds.
   ```
   **Speaker name mapping.** The Phase 5 script saves a `cluster_embeddings` field in the JSON (one voice-print vector per diarised cluster, extracted from each cluster's longest contiguous span). If voice-reference files exist for any known speakers (see `references/voice-references.md`), run cosine similarity between each `cluster_embeddings` entry and each reference embedding. Use a reference name only when similarity exceeds the threshold and its quality flag is `ok`; show the assignment and score for correction. Low-confidence or suspect clusters retain `Speaker N`. Clusters without a high-confidence match fall back to `Speaker N` in order of first appearance. If `cluster_embeddings` is absent (older JSON, or embedding pass failed) or no voice references exist, use `Speaker N` for all clusters.

3. **LLM cleanup pass** (skip if `--raw` was passed):

   **This means reading the transcript paragraph by paragraph, not running regex patterns.** Regex handles known-entity capitalisation (city names, product names); homophones (peace/piece, their/there) and garbled proper nouns (WhisperX maps unfamiliar names to common English words) only surface by reading in context. A regex-only pass will miss these and produce a transcript that looks clean but isn't.

   Rules:
   - Fix non-words to their most likely intended word
   - Fix obvious grammar/punctuation errors introduced by the transcription model (not the speaker's actual grammar — ESL patterns, filler words, etc. stay)
   - Mark genuinely unclear sections as `[inaudible]` rather than guessing
   - For uncertain proper noun spellings (names of people, places), flag with `[?]` suffix so the user can correct — e.g. `Jayne Abernathy[?]`. **Don't silently guess at names** — the user will know the correct spelling and can fix the flagged ones in one pass. **But check the free human-written source before flagging:** if the source has an episode page or video description, its show notes / chapter list / resource links are typed by a person and **outrank the transcript** on spelling — grep that text for a distinctive fragment of the name (match a stem; the garbling is phonetic) and use the spelling it gives instead of a `[?]`.
   - Preserve the speaker's actual words and meaning — don't rewrite, paraphrase, or "improve"
   - Preserve timestamps exactly
   - Preserve speaker labels exactly
   - Do NOT fix the speaker's actual speech patterns (um, uh, repeated words, broken sentences) — these are features, not bugs

   Process the full transcript in a single pass. If the transcript exceeds ~50KB of text, split into ~20KB chunks with 2-paragraph overlap to preserve context at boundaries.

4. **If diarisation was used**, show the user a summary of each speaker (word count + first substantive utterance) and ask if they want to rename the `Speaker N` labels (e.g. "Speaker 1 is Mum, Speaker 3 is Dad"). Apply renames before saving.

5. **Save as markdown** in the output directory:

Stage the metadata header and transcript body in a unique scratch directory outside the vault. Preserve the body verbatim; do not run a spelling normaliser or rewrite the completed note through an editor. Read `../_shared-rules.md` §5 and `../_shared-rules-content.md` §14 before saving.

For a new vault note, assemble header + blank line + body into a staging file, then write that file in one locked append:

```bash
"$VAULT_PATH/.claude/scripts/locked-edit.sh" "<DESTINATION>" --append < "<STAGED_NOTE>"
```

Check for an existing destination before writing. Do not append a duplicate transcript or overwrite existing content; resolve a filename collision with the user unless the request already specifies replacement. For an authorised replacement use the locked wrapper's literal `--replace` mode, re-reading on exit 2 or 3. Outside the vault, write the staged bytes directly to the agreed destination. Check the write exit code and compare the saved body with the staged body byte-for-byte. Report success only after that comparison passes. The header's transcription date comes from `date +%F` for this run; a published transcript's acquisition date is not its original transcription date.

```markdown
# Transcript: {title}

**Source:** `{URL or file path}`
**Date transcribed:** {YYYY-MM-DD}
**Duration:** {MM:SS or H:MM:SS}
**Model:** whisperx / large-v3
**Diarisation:** {yes (N speakers: name1, name2, ...) | no}
**Cleanup:** {yes (LLM pass) | no (--raw)}

---
```

6. **If batch job (multiple files):** Create index file (`00 - Index.md`) with wikilinks to all transcripts, sorted by filename. Skip for single-file jobs.

7. **Ask user** if they want a synthesis document (thematic summary mapping key concepts to their use case). If yes, read all transcripts and generate one.

## Voice references

For recurring known speakers, read [references/voice-references.md](references/voice-references.md). It carries the optional reference lookup, embedding matching and quality flags. Missing references or failed embeddings degrade to `Speaker N`; names are suggestions requiring the documented quality checks, not verified identities.

## Notes

- Cloud uses multilingual `large-v3`; local `$transcribe` defaults to English-only `distil-large-v3`.
- Historical source-workflow validation is described in `references/voice-references.md`; this Codex port does not imply a new live GPU test.
- Model downloads and dependency setup can dominate short jobs. Use live RunPod quotes; historical prices are not a current estimate.
- Preserve the source workflow’s pinned image and dependency versions in `references/runpod.md`; verify CUDA, VAD and gated diarisation before the batch. Any version change needs end-to-end testing.

## Skill Monitor

As you execute this skill, follow `../_skill-monitor.md` (relative to this SKILL.md): watch for gaps, and log observations at the end per that file.
