---
name: transcribe
aliases: [transcription, whisper]
description: Transcribe audio files or YouTube videos using WhisperX (distil-large-v3) with optional speaker diarisation
---

# Transcribe — Audio to Text

Transcribe audio files using WhisperX with distil-large-v3, locally. Optional speaker diarisation via pyannote.

## When to use

When the user wants to transcribe an audio recording (voice memo, meeting, interview, lecture) or a YouTube video. Typical triggers: "transcribe this", "what does this recording say", a file path ending in .m4a/.mp3/.wav/.ogg/.flac/.webm, or a YouTube URL.

## Prerequisites

- Python venv with `whisperx` installed at `~/venvs/whisperx/`
- `ffmpeg` installed (for audio decoding)
- For YouTube URLs: `yt-dlp` installed
- For diarisation: HuggingFace token (via `HF_TOKEN` env var or `huggingface-cli login`). The user must have accepted the pyannote model licences at huggingface.co/pyannote/speaker-diarization-3.1, huggingface.co/pyannote/speaker-diarization-community-1, and huggingface.co/pyannote/segmentation-3.0.

If any prerequisite is missing, tell the user what to install and stop.

## Arguments

`$ARGUMENTS` — path to the audio file or a YouTube URL, optionally followed by flags. If no path is provided, ask the user.

Flags (parsed from arguments):
- `--diarize` or `--diarise` — enable speaker diarisation
- `--speakers N` — exact number of speakers (implicitly enables diarisation)
- `--min-speakers N` / `--max-speakers N` — speaker count range (implicitly enables diarisation)
- `--raw` — skip LLM cleanup pass (save unprocessed WhisperX output)
- `--no-timestamps` — omit timestamps from output

## Workflow

### Phase 1: Validate

1. **Determine source type.** If the argument is a YouTube URL (contains `youtube.com/watch` or `youtu.be/`), this is a YouTube source. Otherwise, confirm the audio file exists at the given path.
2. Check prerequisites are installed:
   ```bash
   ~/venvs/whisperx/bin/python3 -c "import whisperx" && command -v ffmpeg
   ```
   If YouTube source, also check: `command -v yt-dlp`
3. If checks fail, report what's missing and stop.
4. **If YouTube source** (steps a-c are independent — run in parallel):
   a. Get the video title: `yt-dlp --print title "URL"`
   b. Download audio as WAV: `yt-dlp -f "bestaudio[abr<=64]/worstaudio" -x --audio-format wav -o "/tmp/yt_transcribe_%(id)s.%(ext)s" "URL"`
      - Whisper resamples to 16kHz mono internally, so a ≤64kbps source (typically YouTube format 249 @ 49kbps Opus) is plenty for transcription. Unconstrained `bestaudio` pulls format 401 (~100-250MB for typical videos, GB-scale for long ones) and is painfully slow on a slow link.
   c. Download auto-generated English captions (if available) for cross-referencing during cleanup:
      ```bash
      yt-dlp --write-auto-sub --sub-lang en --sub-format srt --skip-download -o "/tmp/yt_subs_%(id)s" "URL"
      ```
      If no English auto-captions are available (e.g. non-English video), retry with `--sub-lang` matching the video's language if known, or omit `--sub-lang` to get whatever is available. If still nothing, proceed without — this is a best-effort enhancement.
   d. Set `INPUT_FILE_PATH` to the downloaded WAV path.
   e. Store the YouTube URL and video title for use in the output metadata.
5. Get the audio duration:
   ```bash
   ffprobe -v quiet -show_entries format=duration -of csv=p=0 "INPUT_FILE_PATH"
   ```
6. Check for GPU:
   ```bash
   ~/venvs/whisperx/bin/python3 -c "import torch; print(torch.cuda.is_available())"
   ```
7. Determine if diarisation was requested (check for `--diarize`, `--diarise`, `--speakers`, `--min-speakers`, or `--max-speakers` in arguments — any of these enables diarisation).
8. If diarisation requested, verify HF token is available:
   ```bash
   ~/venvs/whisperx/bin/python3 -c "from huggingface_hub import HfApi; HfApi().whoami()" 2>/dev/null && echo "ok" || echo "no_token"
   ```
   If no token, tell the user to run `huggingface-cli login` or set `HF_TOKEN` and stop.
9. **Background decision:** If no GPU and (duration > 120s OR diarisation is enabled), tell the user the estimated wait and run as a **background task**. Diarisation on CPU is slow (~2-3x audio length on top of transcription time).

### Phase 2: Transcribe

Run via Bash. If running as a background task (per Phase 1 step 9), no timeout is needed. Otherwise, set a timeout proportional to the audio duration and whether diarisation is enabled. **Redirect stderr to a temp file** (not /dev/null). On success, discard it. On failure, read it for diagnostics.

Set these variables before substituting into the script:
- `INPUT_FILE_PATH` — the audio file path
- `DIARIZE` — `True` or `False`
- `NUM_SPEAKERS` — integer or `None`
- `MIN_SPEAKERS` — integer or `None`
- `MAX_SPEAKERS` — integer or `None`

```bash
STDERR_TMP=$(mktemp)
~/venvs/whisperx/bin/python3 << 'PYEOF' 2>"$STDERR_TMP"
import os, json
os.environ["TQDM_DISABLE"] = "1"

import torch
import whisperx

device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "int8"
batch_size = 16 if device == "cuda" else 4
audio_file = "INPUT_FILE_PATH"
diarize = DIARIZE
num_speakers = NUM_SPEAKERS
min_speakers = MIN_SPEAKERS
max_speakers = MAX_SPEAKERS

# 1. Transcribe
model = whisperx.load_model("distil-large-v3", device, compute_type=compute_type)
audio = whisperx.load_audio(audio_file)
result = model.transcribe(audio, batch_size=batch_size)
language = result["language"]

# 2. Align (word-level timestamps)
model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
result = whisperx.align(result["segments"], model_a, metadata, audio, device)

# 3. Diarize (optional)
if diarize:
    from whisperx.diarize import DiarizationPipeline
    diarize_model = DiarizationPipeline(model_name="pyannote/speaker-diarization-3.1", device=device)
    diarize_segments = diarize_model(
        audio,
        num_speakers=num_speakers,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )
    result = whisperx.assign_word_speakers(diarize_segments, result)

print(json.dumps({"segments": result["segments"], "language": language}))
PYEOF
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then cat "$STDERR_TMP"; fi
rm -f "$STDERR_TMP"
exit $EXIT_CODE
```

Replace the placeholder variables with actual values.

### Phase 3: Post-process and output

1. **Parse the segments JSON.**

2. **Format the transcript:**

   Determine the timestamp format from the audio duration: `[MM:SS]` for recordings under 1 hour, `[H:MM:SS]` for recordings 1 hour or longer. If `--no-timestamps` was passed, omit timestamps entirely.

   **Without diarisation:** Insert a paragraph break wherever the gap between one segment's end and the next segment's start exceeds 1.5 seconds. Concatenate segment text within each paragraph.

   **Monologue fallback.** For recordings longer than 5 minutes, after the initial split, check: is the paragraph count at least `duration_seconds / 120` (roughly one per two minutes)? If not, the source is a dense monologue without natural 1.5s pauses — recompute:

   1. Sort all segment-to-segment gaps in descending order.
   2. Let `N = min(floor(duration_seconds / 90), len(gaps_desc))` — target paragraph-break count (one break per ~90s), clamped to the number of available gaps.
   3. Use `gaps_desc[N-1]` as the new threshold and re-split.

   In your user-facing response, state the threshold actually used — either `(1.5s default)` or `(0.Xs — monologue fallback)` — so the choice is observable.

   Prefix each paragraph with a timestamp derived from the first segment's `start` field:
   ```
   [00:00] First paragraph of speech here.

   [01:23] Next paragraph after a gap.
   ```

   **With diarisation:** Iterate over the **words** array (not segments), since a single segment often contains multiple speakers. Group consecutive words by speaker. Start a new paragraph when the speaker label changes OR when the gap between consecutive words exceeds 1.5 seconds. Prefix each paragraph with a timestamp and speaker label in bold:
   ```
   [00:00] **Speaker 1:** First speaker's text here spanning one or more words.

   [00:45] **Speaker 2:** Second speaker responds with their text.

   [01:12] **Speaker 1:** First speaker continues after the other.
   ```
   The timestamp is derived from the `start` field of the first word in each paragraph group.

   Map raw labels (`SPEAKER_00`, `SPEAKER_01`, ...) to `Speaker 1`, `Speaker 2`, etc. in order of first appearance. The words array is found at `segments[].words[]`, each with `word`, `start`, `end`, `score`, and `speaker` keys.

3. **LLM cleanup pass** (skip if `--raw` was passed):

   Review the assembled transcript text and fix transcription errors. Rules:
   - Fix non-words to their most likely intended word (e.g. "seduptresses" → "seductresses")
   - Fix obvious grammar/punctuation errors introduced by the transcription model (not the speaker's actual grammar — ESL patterns, filler words, etc. stay)
   - Mark genuinely unclear sections as `[inaudible]` rather than guessing
   - Preserve the speaker's actual words and meaning — don't rewrite, paraphrase, or "improve"
   - Preserve timestamps exactly
   - Preserve speaker labels exactly
   - Do NOT fix the speaker's actual speech patterns (um, uh, repeated words, broken sentences) — these are features, not bugs

   **YouTube caption cross-reference** (if YouTube auto-captions were downloaded in Phase 1 step 4c):
   Before starting the cleanup pass, extract a focused comparison from the SRT captions. Parse the SRT to plain text, then identify words/phrases where the WhisperX and YouTube outputs diverge — especially proper nouns (names, institutions, products, technical terms). Build a short divergence list (e.g. "WhisperX: 'Mercore' / YouTube: 'Mercor'") and use it as a reference during cleanup. Do not load the entire SRT into context — the useful signal is in the divergences, not the full text.

   Neither source is authoritative — both are machine-generated and make different errors. Where one system produces a recognisable proper noun and the other produces a garbled version, prefer the recognisable one. Where both agree on a spelling that looks wrong (e.g. both say "Tyler Cowan" when context suggests "Tyler Cowen"), apply your own judgement. Where they disagree and neither is clearly right, flag with `[?]` or choose the more plausible option based on context.

   Process the full transcript in a single pass. If the transcript exceeds ~50KB of text, split into ~20KB chunks with 2-paragraph overlap to preserve context at boundaries.

4. **Display** the formatted transcript to the user.

5. **If diarisation was used**, ask the user if they want to rename any speakers (e.g. "Speaker 1 is actually Dr Smith"). Apply renames before saving.

6. **Ask what the user wants to do next.** Present the options:
   1. Save the transcript — ask where (suggest a default: for local audio files, same directory with `.md` extension; for YouTube, suggest a logical location if one is apparent from context, otherwise ask). Also ask if the user wants a specific filename or is happy with the default (video title / audio filename).
   2. Discuss the transcript — e.g. summarise it, extract key points, ask questions about the content, pull out action items.
   3. Both — save first, then discuss.

   Wait for the user's response before proceeding.

7. **Save** the transcript as a markdown file (if the user chose to save). Use the path and filename agreed in step 6.

   ```markdown
   # Transcript: {video title or filename}

   **Source:** `{YouTube URL or filename/path to audio file}`
   **Date transcribed:** {YYYY-MM-DD}
   **Duration:** {MM:SS or H:MM:SS}
   **Model:** whisperx / distil-large-v3
   **Diarisation:** {yes (N speakers) | no}
   **Cleanup:** {yes | no (--raw)}

   ---

   {formatted transcript text}
   ```

8. **If the user chose to discuss**, proceed with whatever they asked for (summary, Q&A, extraction, etc.).

## Notes

- WhisperX uses faster-whisper (CTranslate2 backend) which is faster than HF Transformers for inference.
- GPU (CUDA) is used automatically if available; falls back to CPU with int8 quantisation.
- Models are cached after first download (~1.5GB for distil-large-v3, ~2-4GB for pyannote diarisation models).
- On CPU without diarisation: ~0.2–0.6x realtime with distil-large-v3 (faster on modern multi-core CPUs; a 46-min batch ran in ~12 min wall time on one reference machine). With diarisation on CPU: add ~2-3x audio length.
- On GPU: transcription is near-instant; diarisation adds ~20-30 min per hour of audio.
- Diarisation accuracy is best with 2-3 speakers in clear audio. Specify `--speakers N` when you know the count.
