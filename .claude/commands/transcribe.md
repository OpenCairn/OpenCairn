---
name: transcribe
aliases: [transcription, whisper]
description: Transcribe audio files using WhisperX (distil-large-v3) with optional speaker diarisation
---

# Transcribe — Audio to Text

Transcribe audio files using WhisperX with distil-large-v3, locally. Optional speaker diarisation via pyannote.

## When to use

When the user wants to transcribe an audio recording (voice memo, meeting, interview, lecture). Typical triggers: "transcribe this", "what does this recording say", a file path ending in .m4a/.mp3/.wav/.ogg/.flac/.webm.

## Prerequisites

- Python venv with `whisperx` installed at `~/venvs/whisperx/`
- `ffmpeg` installed (for audio decoding)
- For diarisation: HuggingFace token (via `HF_TOKEN` env var or `huggingface-cli login`). The user must have accepted the pyannote model licenses at huggingface.co/pyannote/speaker-diarization-3.1, huggingface.co/pyannote/speaker-diarization-community-1, and huggingface.co/pyannote/segmentation-3.0.

If any prerequisite is missing, tell the user what to install and stop.

## Arguments

`$ARGUMENTS` — path to the audio file, optionally followed by flags. If no path is provided, ask the user.

Flags (parsed from arguments):
- `--diarize` or `--diarise` — enable speaker diarisation
- `--speakers N` — exact number of speakers (implicitly enables diarisation)
- `--min-speakers N` / `--max-speakers N` — speaker count range (implicitly enables diarisation)

## Workflow

### Phase 1: Validate

1. Confirm the audio file exists at the given path.
2. Check prerequisites are installed:
   ```bash
   ~/venvs/whisperx/bin/python3 -c "import whisperx" && command -v ffmpeg
   ```
3. If checks fail, report what's missing and stop.
4. Get the audio duration:
   ```bash
   ffprobe -v quiet -show_entries format=duration -of csv=p=0 "INPUT_FILE_PATH"
   ```
5. Check for GPU:
   ```bash
   ~/venvs/whisperx/bin/python3 -c "import torch; print(torch.cuda.is_available())"
   ```
6. Determine if diarisation was requested (check for `--diarize`, `--diarise`, `--speakers`, `--min-speakers`, or `--max-speakers` in arguments — any of these enables diarisation).
7. If diarisation requested, verify HF token is available:
   ```bash
   ~/venvs/whisperx/bin/python3 -c "from huggingface_hub import HfApi; HfApi().whoami()" 2>/dev/null && echo "ok" || echo "no_token"
   ```
   If no token, tell the user to run `huggingface-cli login` or set `HF_TOKEN` and stop.
8. **Background decision:** If no GPU and (duration > 120s OR diarisation is enabled), tell the user the estimated wait and run as a **background task**. Diarisation on CPU is slow (~2-3x audio length on top of transcription time).

### Phase 2: Transcribe

Run via Bash. If running as a background task (per Phase 1 step 8), no timeout is needed. Otherwise, set a timeout proportional to the audio duration and whether diarisation is enabled. **Redirect stderr to a temp file** (not /dev/null). On success, discard it. On failure, read it for diagnostics.

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

   **Without diarisation:** Insert a paragraph break wherever the gap between one segment's end and the next segment's start exceeds 1.5 seconds. Concatenate segment text within each paragraph.

   **With diarisation:** Iterate over the **words** array (not segments), since a single segment often contains multiple speakers. Group consecutive words by speaker. Start a new paragraph when the speaker label changes OR when the gap between consecutive words exceeds 1.5 seconds. Prefix each paragraph with the speaker label in bold:
   ```
   **Speaker 1:** First speaker's text here spanning one or more words.

   **Speaker 2:** Second speaker responds with their text.

   **Speaker 1:** First speaker continues after the other.
   ```
   Map raw labels (`SPEAKER_00`, `SPEAKER_01`, ...) to `Speaker 1`, `Speaker 2`, etc. in order of first appearance. The words array is found at `segments[].words[]`, each with `word`, `start`, `end`, `score`, and `speaker` keys.

3. **Display** the formatted transcript to the user.

4. **If diarisation was used**, ask the user if they want to rename any speakers (e.g. "Speaker 1 is actually Dr Smith"). Apply renames before saving.

5. **Save** the transcript as a markdown file alongside the audio file (same directory, same base name, `.md` extension). Format:

   ```markdown
   # Transcript: {filename}

   **Source:** `{full path to audio file}`
   **Date transcribed:** {YYYY-MM-DD}
   **Model:** whisperx / distil-large-v3
   **Diarisation:** {yes (N speakers) | no}

   ---

   {formatted transcript text}
   ```

6. If the transcript is very long, ask the user if they want a summary.

## Notes

- WhisperX uses faster-whisper (CTranslate2 backend) which is faster than HF Transformers for inference.
- GPU (CUDA) is used automatically if available; falls back to CPU with int8 quantisation.
- Models are cached after first download (~1.5GB for distil-large-v3, ~2-4GB for pyannote diarisation models).
- On CPU without diarisation: ~0.6x realtime. With diarisation on CPU: add ~2-3x audio length.
- On GPU: transcription is near-instant; diarisation adds ~20-30 min per hour of audio.
- Diarisation accuracy is best with 2-3 speakers in clear audio. Specify `--speakers N` when you know the count.
