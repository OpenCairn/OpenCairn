---
name: transcribecloud
aliases: [cloud-transcribe, runpod-transcribe]
description: Batch transcribe audio/video on RunPod GPU cloud — for large jobs or when no local GPU is available
---

# Cloud Transcribe — Batch Audio to Text via RunPod

Batch transcribe audio or video files using WhisperX on a RunPod GPU instance. Use this instead of `/transcribe` when:
- No local GPU and total audio > 30 minutes
- Batch of multiple files (5+)
- User explicitly requests cloud/RunPod transcription

## Arguments

`$ARGUMENTS` — one or more of:
- YouTube URLs (individual videos or playlists)
- Local file paths or directories containing audio/video files
- `--diarize` / `--diarise` — enable speaker diarisation
- `--speakers N` — exact speaker count (implies diarisation)
- `--output PATH` — vault directory for transcripts (default: alongside source, or user-specified)

If no arguments provided, ask the user what to transcribe and where to store results.

## Prerequisites

- `runpodctl` installed and configured with API key
- SSH ed25519 key added to RunPod (`runpodctl ssh add-key --key-file ~/.ssh/id_ed25519.pub`)
- RunPod account with credits loaded

Check with:
```bash
command -v runpodctl && runpodctl get pod
```

If `runpodctl` is missing, point user to: `wget -qO runpodctl https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64 && chmod +x runpodctl && sudo mv runpodctl /usr/local/bin/`

Reference doc for RunPod setup details: check your vault for a RunPod setup/usage guide if you have one.

## Workflow

### Phase 1: Scope the job

1. **Parse arguments** — separate URLs, file paths, and flags.
2. **For YouTube URLs:** Use `yt-dlp --flat-playlist --print "%(duration)s %(title)s"` to get video count and total duration. Handle playlists (expand to individual videos). Report the inventory to the user.
3. **For local files:** Count files and get total duration via `ffprobe`.
4. **Determine source type:**
   - `youtube` — URLs only, will download directly on pod (faster, no local transfer needed)
   - `local` — local files, will need `runpodctl send/receive` transfer to pod
   - `mixed` — both; download URLs on pod, transfer local files separately
5. **Report to user:** file count, total duration, estimated pod time (~1 min setup + ~1 min per hour of audio on A4000), estimated cost.
6. **Confirm output location** with user if not specified via `--output`.

### Phase 2: Provision pod

1. Create pod:
```bash
runpodctl create pod \
  --name "whisperx-batch" \
  --gpuType "NVIDIA RTX A4000" \
  --gpuCount 1 \
  --templateId "runpod-torch-v240" \
  --imageName "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04" \
  --containerDiskSize 30 \
  --volumeSize 0 \
  --startSSH \
  --communityCloud \
  --cost 0.17
```

2. **Extract pod ID** from the response.

3. **Ask the user for SSH connection info.** Tell the user:
   > Pod created. I need the SSH connection info from the RunPod web UI.
   > Go to runpod.io > Pods > whisperx-batch > Connect.
   > **Preferred:** Copy the "SSH over exposed TCP" line (looks like `ssh root@IP -p PORT -i ~/.ssh/id_ed25519`).
   > **Fallback:** If no TCP option, copy the proxy SSH line (`PODID-HASH@ssh.runpod.io`).

4. Wait for user to provide SSH info. Determine connection method:
   - **If TCP (has IP + port):** Use direct SSH — supports SCP/SFTP, no PTY hack needed. Store `root@IP -p PORT` for all commands.
   - **If proxy (has `@ssh.runpod.io`):** Use PTY wrapper (`script -qec 'ssh -tt ...'`). No SCP — use `runpodctl send/receive` for file transfer.

5. **Wait for pod to initialise** (1-3 min after "RUNNING" status). Test SSH connectivity:
```bash
# TCP:
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30 -i ~/.ssh/id_ed25519 root@IP -p PORT "echo ready"
# Proxy:
script -qec 'ssh -tt -o StrictHostKeyChecking=no -o ConnectTimeout=30 -i ~/.ssh/id_ed25519 SSH_TARGET "echo ready; exit"' /dev/null
```
Retry up to 5 times with 15s gaps if connection fails.

### Phase 3: Setup pod environment

Run all commands via SSH. If using exposed TCP, standard `ssh ... "command"` works. If using proxy, use the PTY wrapper (see RunPod setup doc for `script -qec` pattern).

1. **Install dependencies:**
```bash
apt-get update -qq && apt-get install -y -qq ffmpeg && \
pip install -q yt-dlp whisperx --no-deps && \
pip install -q faster-whisper transformers huggingface_hub pandas nltk omegaconf pyannote-audio && \
pip install -q torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu124 --force-reinstall --no-cache-dir && \
pip install -q 'ctranslate2>=4.5.0'
```

2. **Set runtime environment:**
```bash
export LD_LIBRARY_PATH=/usr/local/lib/python3.11/dist-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH
```

3. **Verify CUDA + WhisperX:**
```bash
python3 -c "import torch; assert torch.cuda.is_available(); import whisperx; print('OK')"
```
If this fails, read the RunPod setup doc for troubleshooting. Do not proceed until verified.

### Phase 4: Get audio onto pod

**For YouTube URLs (source type `youtube` or `mixed`):**
```bash
mkdir -p /workspace/audio
yt-dlp -x --audio-format mp3 --audio-quality 5 -o "/workspace/audio/%(title)s.%(ext)s" [URLS...]
```

**For local files (source type `local` or `mixed`):**
```bash
# On pod (in one SSH session):
cd /workspace && runpodctl receive

# Locally (simultaneously, in a separate terminal):
runpodctl send /path/to/audio/directory
```

**Verify downloads:**
```bash
ls -la /workspace/audio/*.mp3 | wc -l
```
Report count to user. If any files failed, list which ones and ask whether to proceed with what succeeded or abort.

### Phase 5: Batch transcribe

Write and execute this Python script on the pod:

```python
import os, json, glob, time
os.environ["TQDM_DISABLE"] = "1"

import torch, whisperx

device = "cuda"
compute_type = "float16"
batch_size = 16
diarize = DIARIZE  # True or False
num_speakers = NUM_SPEAKERS  # int or None
audio_dir = "/workspace/audio"
output_dir = "/workspace/transcripts"
os.makedirs(output_dir, exist_ok=True)

# Load model ONCE
model = whisperx.load_model("distil-large-v3", device, compute_type=compute_type)
align_model, align_metadata = None, None

if diarize:
    from whisperx.diarize import DiarizationPipeline
    diarize_model = DiarizationPipeline(
        model_name="pyannote/speaker-diarization-3.1", device=device
    )

files = sorted(glob.glob(os.path.join(audio_dir, "*.mp3")))
print(f"Found {len(files)} files to transcribe")

for i, audio_file in enumerate(files, 1):
    basename = os.path.splitext(os.path.basename(audio_file))[0]
    print(f"[{i}/{len(files)}] {basename}...", end=" ", flush=True)
    t0 = time.time()

    audio = whisperx.load_audio(audio_file)
    result = model.transcribe(audio, batch_size=batch_size)
    language = result["language"]

    # Load alignment model once (after first transcription determines language)
    if align_model is None:
        align_model, align_metadata = whisperx.load_align_model(
            language_code=language, device=device
        )

    result = whisperx.align(
        result["segments"], align_model, align_metadata, audio, device
    )

    if diarize:
        diarize_segments = diarize_model(
            audio, num_speakers=num_speakers,
        )
        result = whisperx.assign_word_speakers(diarize_segments, result)

    out_path = os.path.join(output_dir, f"{basename}.json")
    with open(out_path, "w") as f:
        json.dump({"segments": result["segments"], "language": language}, f)

    elapsed = time.time() - t0
    print(f"{elapsed:.1f}s")

print("Done.")
```

Replace `DIARIZE` and `NUM_SPEAKERS` with actual values from arguments.

### Phase 6: Retrieve results

```bash
# On pod:
cd /workspace && tar czf transcripts.tar.gz transcripts/
runpodctl send transcripts.tar.gz

# Locally (simultaneously):
cd /tmp && runpodctl receive
tar xzf transcripts.tar.gz
```

### Phase 7: Destroy pod

```bash
runpodctl remove pod PODID
```

Do this immediately after retrieving results. Confirm destruction to the user. **Do not leave the pod running.**

### Phase 8: Post-process to markdown

For each JSON transcript file:

1. **Parse segments.**
2. **Format transcript text:**
   - **Without diarisation:** Insert paragraph break wherever gap between segments exceeds 1.5 seconds. Concatenate segment text within each paragraph.
   - **With diarisation:** Group consecutive words by speaker. New paragraph on speaker change or >1.5s gap. Prefix each paragraph with speaker label in bold (`**Speaker 1:**`). Map `SPEAKER_00` → `Speaker 1` etc. in order of first appearance. Ask user if they want to rename speakers.

3. **Save as markdown** in the output directory:

```markdown
# Transcript: {title}

**Source:** `{URL or file path}`
**Date transcribed:** {YYYY-MM-DD}
**Model:** whisperx / distil-large-v3
**Diarisation:** {yes (N speakers) | no}

---

{formatted transcript text}
```

4. **Create index file** (`00 - Index.md`) with wikilinks to all transcripts, sorted by filename.

5. **Ask user** if they want a synthesis document (thematic summary mapping key concepts to their use case). If yes, read all transcripts and generate one.

## Notes

- **Performance (RTX A4000):** 40-100x realtime. 5 hours of audio transcribes in ~5-8 minutes.
- **Cost:** ~$0.17/hr on-demand. Typical batch job: $0.03-0.10.
- **SSH hash blocker:** The `PODID-HASH` for SSH is only available from the RunPod web UI, not the API or CLI. This is a manual step every time.
- **WhisperX install order is critical:** `--no-deps` prevents torch breakage. The torch reinstall after pyannote-audio is mandatory. See RunPod setup doc for details.
- **yt-dlp on pod vs local:** For YouTube URLs, always download directly on the pod — datacenter bandwidth is faster and eliminates the transfer step. Only use local download + `runpodctl send` for files that are already on disk.
- **`runpodctl send/receive`:** P2P transfer. Must run `send` and `receive` simultaneously from both sides. Works for both files and directories.
- **Pod lifecycle:** Always destroy the pod when done. `runpodctl remove pod PODID`. Stopped pods still incur disk charges.
