---
name: transcribe
aliases: [transcription, whisper]
description: Transcribe audio files using Distil Whisper v3 and save the transcript to the vault
---

# Transcribe — Audio to Text

Transcribe audio files using distil-whisper/distil-large-v3 locally via Hugging Face Transformers.

## When to use

When the user wants to transcribe an audio recording (voice memo, meeting, interview, lecture). Typical triggers: "transcribe this", "what does this recording say", a file path ending in .m4a/.mp3/.wav/.ogg/.flac/.webm.

## Prerequisites

- Python packages: `transformers`, `torch`
- `ffmpeg` installed (for audio decoding)
- Model: `distil-whisper/distil-large-v3` (auto-downloaded on first use)

If any prerequisite is missing, tell the user what to install and stop.

## Arguments

`$ARGUMENTS` — path to the audio file. If not provided, ask the user.

## Workflow

### Phase 1: Validate

1. Confirm the audio file exists at the given path.
2. Check prerequisites are installed:
   ```bash
   python3 -c "import transformers, torch" && command -v ffmpeg
   ```
3. If checks fail, report what's missing and stop.
4. Get the audio duration:
   ```bash
   ffprobe -v quiet -show_entries format=duration -of csv=p=0 "INPUT_FILE_PATH"
   ```
5. Check for GPU:
   ```bash
   python3 -c "import torch; print(torch.cuda.is_available())"
   ```
6. If no GPU and duration > 120s, tell the user the estimated wait (~0.6x realtime, e.g. "12 min audio ≈ 7 min on CPU") and run the transcription as a **background task**.

### Phase 2: Transcribe

Run the transcription via Bash (timeout 600s). **Redirect stderr to /dev/null** to suppress model loading progress bars and library warnings that otherwise flood the output:

```bash
python3 << 'PYEOF' 2>/dev/null
import os, json
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"

import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if torch.cuda.is_available() else torch.float32
model_id = "distil-whisper/distil-large-v3"

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id, dtype=dtype, low_cpu_mem_usage=True
)
model.to(device)

processor = AutoProcessor.from_pretrained(model_id)

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    dtype=dtype,
    device=device,
)

result = pipe(
    "INPUT_FILE_PATH",
    generate_kwargs={"return_timestamps": True},
    return_timestamps=True,
)

chunks = result.get("chunks", [])
if chunks:
    print(json.dumps(chunks))
else:
    print(json.dumps([{"text": result["text"], "timestamp": [0, 0]}]))
PYEOF
```

Replace `INPUT_FILE_PATH` with the actual file path.

### Phase 3: Post-process and output

1. **Parse the chunks JSON.** Insert a paragraph break wherever the gap between one chunk's end timestamp and the next chunk's start timestamp exceeds 1.5 seconds. Concatenate chunk text within each paragraph.

2. **Display** the paragraphed transcript to the user.

3. **Save** the transcript as a markdown file alongside the audio file (same directory, same base name, `.md` extension). Format:

   ```markdown
   # Transcript: {filename}

   **Source:** `{full path to audio file}`
   **Date transcribed:** {YYYY-MM-DD}
   **Model:** distil-whisper/distil-large-v3

   ---

   {paragraphed transcript text}
   ```

4. If the transcript is very long, ask the user if they want a summary.

## Notes

- For files longer than ~10 minutes, the pipeline handles chunking automatically via Whisper's native long-form mechanism.
- GPU (CUDA) is used automatically if available; falls back to CPU.
- The model is ~1.5GB and cached after first download.
- On CPU, expect ~0.6x realtime processing (a 10 min file ≈ 6 min). On GPU, transcription is near-instant.
