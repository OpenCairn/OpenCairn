---
name: transcribecloud
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

If `runpodctl` is missing, point user to: `wget -qO runpodctl https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64 && chmod +x runpodctl && sudo mv runpodctl /usr/local/bin/`

**Network-reachability note:** if the user is on a restricted network (e.g. behind GFW from China), direct SSH to RunPod datacenter IPs may silently time out (ping may work but the SSH port is filtered). In that case, fall back to proxy SSH via `ssh.runpod.io` — test reachability of that host first before spending pod time. See Phase 2 for handling.

## Workflow

### Phase 1: Scope the job

1. **Parse arguments** — separate URLs, file paths, and flags.
2. **For YouTube URLs:** Use `yt-dlp --flat-playlist --print "%(duration)s %(title)s"` to get video count and total duration. Handle playlists (expand to individual videos). Report the inventory to the user.
3. **For local files:** Count files and get total duration via `ffprobe`.
4. **Determine source type:**
   - `youtube` — URLs only, will download directly on pod (faster, no local transfer needed)
   - `local` — local files, will need transfer to pod (scp over exposed TCP, else `runpodctl send/receive` — Phase 4)
   - `mixed` — both; download URLs on pod, transfer local files separately
5. **Check GPU availability and pick one** — don't hardcode a card; query and select. Run:
   ```bash
   runpodctl gpu list
   ```
   **Select on the `available` field, not `stockStatus`.** `stockStatus: Low` does **not** mean unavailable — it is a depth hint. On a typical day most of the fleet reads `Low` while every entry still carries `available: true` and deploys fine. Treat stock as a tiebreaker only, and escalate a tier solely on an actual capacity error at create time ("This machine does not have the resources to deploy your pod"). Filtering the list down to `High`/`Medium` can exclude the entire cheap tier and push you into a needlessly expensive card.

   Pick the cheapest GPU with `available: true` from this priority list (all have sufficient VRAM for `large-v3`, ~3 GB):
   - RTX A4000 (~USD 0.17/hr community) — cheapest
   - RTX 3090 (~USD 0.22/hr community) — reliable fallback
   - A5000 (~USD 0.35/hr community) — next tier up
   - RTX 4090 (~USD 0.40/hr community, ~USD 0.69/hr secure) — fastest mid-range
   - A40 (~USD 0.44/hr, **secure only**) — 48 GB, frequently High stock when the tier above is thin. Note `communityCloud: false`: a `--cloud-type COMMUNITY` create against it will fail, so pair it with `--cloud-type SECURE`.
   - L40S (~USD 0.80–1.00/hr) — expensive, only if nothing cheaper available

   Secure-cloud variants cost ~2× community but provision faster and more reliably. For jobs under ~1 hour of audio, the hourly difference is negligible at job total cost. Some GPUs are secure-only (`communityCloud: false`) — check that field before choosing a cloud tier.
6. **Report to user:** file count, total duration, chosen GPU + cloud tier, estimated pod time (~1 min setup + ~1 min per hour of audio on mid-tier GPU), estimated cost.
7. **Confirm output location** with user if not specified via `--output`.

### Phase 1.5: Published-transcript check (single-source runs only)

A cloud run **costs money**, so the bar to spend pod time is *higher* than for local `/transcribe`: a free human-edited published transcript should win even more decisively here. Run this check after scoping (so single-vs-batch is known) and **before** provisioning a pod.

**Gate — skip this phase entirely unless ALL of the following hold:**
- The job is a **single source** — exactly one YouTube video (not a playlist) or one named podcast/talk episode. Skip for multi-file jobs, directories, playlists, or `mixed` sources — a per-file published check doesn't fit a batch and isn't worth the latency.
- `--no-published` was **not** passed.
- The source has a plausible online origin (YouTube URL, or a podcast episode the user named/linked). Skip for opaque local files with no obvious published page.

When the gate passes, run the **full discover → validate → choose** logic from `/transcribe` Phase 0 steps 1–5 (user-supplied URL wins; else scan the YouTube description / show-notes / one web search; validate it's a *full verbatim transcript*, not show-notes or a summary; present the choice and wait — don't auto-pick). The only cloud-specific change to the choice framing: option 2 is **"run WhisperX on a paid RunPod GPU"**, so state the *dollar* cost of the cloud run alongside the fidelity tradeoff.

**If the user picks the published transcript:** the body is already at `<BODY_FILE>` from the **`_shared-rules.md` §15 extractor** (run during the validate step above — §15's printed `BODY=` path, reconstructable from the URL). Do **not** enter Phase 8's `For each JSON transcript file` loop (there is no JSON here), and run no LLM cleanup pass — it is already human-edited. Confirm the output dir/filename here if Phase 1 step 7 didn't (its prompt assumes a cloud run; the episode title is a sensible default filename). Write **only the header** with the editor (Phase 8 step 5's header block), then **append the body straight from the file** — `printf '\n' >> "<note>.md" && cat "<BODY_FILE>" >> "<note>.md"` (`_shared-rules.md` §14, no `Edit` afterward); do **not** use Phase 8 step 5's `{formatted transcript text}` staging (that is for in-context WhisperX output). Header: **Source** = transcript URL, add an **Original media:** line for the YouTube/audio URL, **Model:** `published transcript (human-edited)`, mark **Diarisation** and **Cleanup** `n/a` (or drop them), keep **Duration** only if known. Don't print the whole body to the conversation. **Skip Phases 2–8's loop entirely — no pod is provisioned, no money spent.** Otherwise continue to Phase 2.

### Phase 2: Provision pod

1. Create pod (new `runpodctl pod create` syntax — old `runpodctl create pod` with flags like `--gpuType`/`--imageName`/`--communityCloud`/`--cost` is deprecated and will fail):
```bash
runpodctl pod create \
  --name "whisperx-batch" \
  --gpu-id "NVIDIA GeForce RTX 3090" \
  --gpu-count 1 \
  --image "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04" \
  --container-disk-in-gb 30 \
  --ports "22/tcp,8888/http" \
  --cloud-type COMMUNITY
```
Substitute `--gpu-id` with the chosen GPU from Phase 1 step 5. `--image` and `--template-id` are **either/or** per `runpodctl pod create --help` ("create a pod either from a template or by specifying an image directly") — this skill pins the image directly because the Phase 3 dep pins are tied to it; do not also pass `--template-id` (the template `runpod-torch-v240` resolves to this same image and is only the fallback if image-only creation ever fails). Use `--cloud-type SECURE` if community cloud has no capacity (error: "This machine does not have the resources to deploy your pod"). The `--ports "22/tcp"` is required — without it, SSH isn't bridged.

2. **Extract pod ID** from the response JSON.

3. **Get SSH connection info.** Prefer the API (automatable), fall back to web UI only if needed:
   ```bash
   runpodctl pod get <POD_ID>
   ```
   This returns `ssh.ip`, `ssh.port`, and a full `ssh_command` line — no manual web UI step needed for the exposed-TCP path. Note: `uptimeSeconds` may be `0` for a few minutes after creation (API lag); the web UI dashboard is the source of truth for "is the pod actually running."

   **Only if direct TCP is unreachable from the user's network** (common on restricted networks like GFW — test with `nc -zv <ip> <port>`): fall back to proxy SSH via `ssh.runpod.io`. The proxy's `PODID-HASH` is only in the web UI — ask the user to copy the `ssh PODID-HASH@ssh.runpod.io -i ~/.ssh/id_ed25519` line from Pods > whisperx-batch > Connect.

4. Determine connection method:
   - **Direct TCP (ip + port from API):** standard `ssh ... "command"` works; supports SCP/SFTP.
   - **Proxy SSH (`@ssh.runpod.io`):** use PTY wrapper `script -qec 'ssh -tt ...'`. No SCP — use `runpodctl send/receive` for file transfer.

5. **Wait for pod to initialise.** Test SSH connectivity with retries:
```bash
# TCP:
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -i ~/.ssh/id_ed25519 root@IP -p PORT "echo ready"
# Proxy:
script -qec 'ssh -tt -o StrictHostKeyChecking=no -o ConnectTimeout=15 -i ~/.ssh/id_ed25519 SSH_TARGET "echo ready; exit"' /dev/null
```
Boot timing: pods typically ready in 1–3 min (community or secure). If SSH times out past that, see diagnostic tree below before assuming the pod is broken.

#### Diagnosing SSH failures

Connection-timeout symptoms are ambiguous — the same error can mean (a) sshd hasn't bound yet (wait), (b) network routing to this datacenter is filtered from your client (switch approach), or (c) pod is genuinely stuck (delete and retry). Don't skip to (c) — one real session burned ~25 min deleting pods for what turned out to be (b).

**Decision tree when SSH to direct TCP times out:**

1. **Check pod state and elapsed time.** `runpodctl pod get <POD_ID>` — note `createdAt`. If <2 min elapsed, just wait. Re-test at 3 and 5 min.

2. **Is it you or is it the pod?** Test `ssh.runpod.io:22` reachability:
   ```bash
   nc -zv -w 5 ssh.runpod.io 22
   ```
   - **Succeeds** → your network can reach RunPod's global proxy endpoint. Direct-TCP failure then points to a specific-datacenter-subnet filter OR an sshd bind issue. Proceed to step 3.
   - **Also fails** → your general network connectivity to RunPod is broken. Nothing pod-side will fix this. Escalate (VPN, different network, etc.).

3. **Test the pod's direct IP:**
   ```bash
   ping -c 3 -W 5 <POD_IP>
   ```
   - **Ping works but SSH port times out** → most likely sshd inside container hasn't bound yet. Wait up to **8 min** from `createdAt`. If still failing past that threshold, sshd inside the container is not binding — unverified whether this is a per-host issue (retry same config may work) or a template issue (switch templates). One real session saw this fail 3× across US-TX/Czech/India on `runpod-torch-v240`, so if it persists across two retries, switch templates rather than continuing to burn pod time.
   - **Ping also fails (100% packet loss)** → datacenter IP range is filtered from your network (common on GFW-restricted networks for US/EU subnets; Asia-Pacific and India datacenters tend to be reachable). Do not delete and retry in the same region — the whole subnet is blocked. Options:
     - Delete and recreate in a different datacenter via `--data-center-ids "AP-IN-1"` (or another reachable region per `runpodctl datacenter list`).
     - Switch to proxy SSH — ask user for `PODID-HASH@ssh.runpod.io` line from web UI (proxy routes through the `ssh.runpod.io` endpoint, bypassing the per-datacenter subnet filter).

4. **If `uptimeSeconds` stays 0 for >5 min** with `desiredStatus: RUNNING` — pod is stuck in community-cloud allocation queue (rarer on secure cloud). Delete and retry on `--cloud-type SECURE`; don't wait it out.

**Hard cap:** don't spend >10 min debugging a single pod. Delete and try a different config. GPU + cloud + region is a 3-dimensional search space — move across it rather than waiting.

### Phase 3: Setup pod environment

Run all commands via SSH. If using exposed TCP, standard `ssh ... "command"` works. If using proxy, use the `script -qec 'ssh -tt ...'` PTY wrapper shown in Phase 2 step 5.

1. **Install dependencies (pins are MANDATORY — see note below):**
```bash
apt-get update -qq && apt-get install -y -qq ffmpeg && \
pip install -q 'numpy<2.0' && \
pip install -q yt-dlp 'whisperx==3.4.2' --no-deps && \
pip install -q 'faster-whisper==1.2.1' 'transformers==4.40.2' 'huggingface_hub==0.24.7' pandas nltk omegaconf 'pyannote-audio==3.3.2' matplotlib && \
pip install -q torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu124 --force-reinstall --no-cache-dir && \
pip install -q 'ctranslate2>=4.5.0'
```

**Why pinned:** upstream whisperx jumped to 3.8.x (requires torch 2.8+, pyannote-audio 4.x) and pyannote-audio jumped to 4.0.x (breaking Inference API). Both happened between 2026-04-21 and 2026-04-22. Unpinned installs resolve to the newest wheels and break at runtime. The pin set above is the mid-2024 constellation that works with the cu124 image. If you bump any of these, re-validate end-to-end (not just imports) — SETUP_OK below is necessary but not sufficient.

2. **Transfer Hugging Face token to pod (required for gated diarisation model):**

   Skip this step if `--diarize`/`--speakers N` is *not* requested — only diarisation hits the gated `pyannote/speaker-diarization-3.1`. With diarisation, fresh pods have no HF auth and the `DiarizationPipeline(...)` call returns `None` at runtime — `Pipeline.from_pretrained` swallows the 401 and prints a "Could not download" notice on stderr that isn't easy to spot under `nohup`.

   The `huggingface_hub` Python library writes the token to `~/.cache/huggingface/token` on **all three platforms** (Linux, macOS, Windows) — it doesn't honour `XDG_CACHE_HOME` or `LOCALAPPDATA`. So the source path is portable; only the local shell syntax differs:

   ```bash
   # Linux / macOS / Git Bash on Windows / WSL — bash or zsh:
   ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'mkdir -p /root/.cache/huggingface'
   scp -i ~/.ssh/id_ed25519 -P PORT ~/.cache/huggingface/token \
       root@IP:/root/.cache/huggingface/token
   ```

   ```powershell
   # Windows PowerShell 5.1 / PowerShell 7+ (uses built-in OpenSSH, present since Win10):
   ssh -i "$HOME\.ssh\id_ed25519" root@IP -p PORT 'mkdir -p /root/.cache/huggingface'
   scp -i "$HOME\.ssh\id_ed25519" -P PORT "$HOME\.cache\huggingface\token" `
       root@IP:/root/.cache/huggingface/token
   ```

   **If the local token file doesn't exist:** run `huggingface-cli login` on the local machine first (works identically on all three platforms via `pip install huggingface_hub`). Alternative if a token is in the env (`HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN`) locally but not on disk: `printf %s "$HF_TOKEN" | ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'mkdir -p /root/.cache/huggingface && cat > /root/.cache/huggingface/token'` — the pipe expands the variable **locally**; a single-quoted remote `echo "$HF_TOKEN"` would expand on the *pod* (where it's unset) and silently write an empty file.

   **Over proxy SSH (no SCP — Phase 2 step 4):** transfer the token file with `runpodctl send ~/.cache/huggingface/token` locally, then on the pod `mkdir -p /root/.cache/huggingface && cd /root/.cache/huggingface && runpodctl receive <code>` — using the detached-send pairing-code pattern from Phase 6.

   **One-time per HF account:** also visit https://hf.co/pyannote/speaker-diarization-3.1 (and its gated dependency https://hf.co/pyannote/segmentation-3.0 — see `/transcribe`'s prerequisites) once and click "Accept" on each user-conditions page. The token grants auth; the click grants the gating agreement. Without the click, the same token returns 403 and the pipeline silently becomes `None`.

3. **Runtime environment — cudnn library path.** Every whisperx invocation on the pod needs:
```bash
export LD_LIBRARY_PATH=/usr/local/lib/python3.11/dist-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH
```
   **Each SSH command is a fresh shell — a bare `export` in one call does NOT persist to later calls** (and the pod's `.bashrc` interactive guard means appending it there doesn't reach non-interactive SSH shells either). The step 4 verify commands and the Phase 5 launch command below carry this export inline; if you compose any other whisperx-running command, prefix it yourself.

4. **Verify CUDA + WhisperX + pyannote glue (don't skip):**

If diarisation is *not* requested, the short form (no token, no gated pipeline):
```bash
export LD_LIBRARY_PATH=/usr/local/lib/python3.11/dist-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH
python3 -c "import torch; assert torch.cuda.is_available(); import whisperx; from pyannote.audio import Model; from whisperx.vads import Pyannote; Pyannote(torch.device('cuda'), token=None, vad_onset=0.500, vad_offset=0.363); Model.from_pretrained('pyannote/wespeaker-voxceleb-resnet34-LM'); print('SETUP_OK')"
```

If diarisation **is** requested, also exercise the gated pipeline so a missing token / unaccepted agreement fails here, not 90s into the transcription run:
```bash
export LD_LIBRARY_PATH=/usr/local/lib/python3.11/dist-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH
python3 << 'PYEOF'
import os
tk_path = os.path.expanduser("~/.cache/huggingface/token")
assert os.path.exists(tk_path), "HF token missing on pod — re-run Phase 3 step 2"
os.environ["HF_TOKEN"] = open(tk_path).read().strip()
os.environ["HUGGING_FACE_HUB_TOKEN"] = os.environ["HF_TOKEN"]

import torch
assert torch.cuda.is_available()
import whisperx
from pyannote.audio import Model, Pipeline
from whisperx.vads import Pyannote

Pyannote(torch.device("cuda"), token=None, vad_onset=0.500, vad_offset=0.363)
Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM")

p = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=os.environ["HF_TOKEN"],
)
assert p is not None, (
    "diarisation pipeline returned None — token invalid OR user-conditions at "
    "https://hf.co/pyannote/speaker-diarization-3.1 not accepted for this HF account"
)
print("SETUP_OK")
PYEOF
```

The VAD load exercises the whisperx×pyannote×huggingface_hub glue that bare `import whisperx` doesn't. The wespeaker `Model.from_pretrained` exercises pyannote's auth/download path that Phase 5's embedding extractor relies on (this model is **not** gated). The `Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", ...)` is the gated check — its `None`-on-failure behaviour is why a missing token slipped through SETUP_OK historically. A passing import but failing VAD load is the failure mode that slipped through on 2026-04-21; a passing VAD load but `None` diarisation pipeline is the failure mode that slipped through up to 2026-04-27.

### Phase 4: Get audio onto pod

**For YouTube URLs (source type `youtube` or `mixed`):** run these **on the pod** via SSH (same transport as Phase 3) — not locally; downloading on the pod is the whole point (datacenter bandwidth, no transfer step):
```bash
mkdir -p /workspace/audio
yt-dlp -f "bestaudio[ext=m4a]/bestaudio" -x --audio-format mp3 --audio-quality 5 \
  -o "/workspace/audio/%(id)s.%(ext)s" [URLS...]
```
**Critical:** the `-f "bestaudio[ext=m4a]/bestaudio"` flag is mandatory — without it, yt-dlp selects the best *video* stream and extracts audio afterwards, downloading e.g. 1.2 GB of video just to produce a 50 MB MP3. The `-x --audio-format mp3` alone does NOT constrain the download format.

**Filename convention:** use `%(id)s.%(ext)s` (video ID), not `%(title)s.%(ext)s`. Titles often contain characters that break shell globs or are clickbait — the video ID is a stable identifier that makes post-processing easier. Preserve the original title in the output markdown metadata instead — and **persist the `id → title → URL → duration` mapping from Phase 1's inventory to a local file now** (e.g. `/tmp/yt-sources.json`): Phase 8's headers need the titles, and conversation context may not reliably carry them that far.

**Anti-bot mitigation for batches >5 URLs:** YouTube's anti-bot ("Sign in to confirm you're not a bot") kicks in partway through large bursts from a single IP. Two ways to mitigate — both run **locally first**, because the pod has no browser and no live YouTube session. Pick one:

**Option 1 (preferred): export cookies to a file locally, then transfer to pod.**
Run locally:
```bash
yt-dlp --cookies-from-browser brave --cookies /tmp/yt-cookies.txt --skip-download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
# Then copy cookies.txt to pod (adjust SSH path):
scp -i ~/.ssh/id_ed25519 -P PORT /tmp/yt-cookies.txt root@IP:/workspace/yt-cookies.txt
# Or via runpodctl send/receive if using proxy SSH.
# Delete local copy when done: rm /tmp/yt-cookies.txt
```
Then on the pod:
```bash
yt-dlp --cookies /workspace/yt-cookies.txt --sleep-interval 3 --max-sleep-interval 8 \
  -f "bestaudio[ext=m4a]/bestaudio" -x --audio-format mp3 -o "/workspace/audio/%(id)s.%(ext)s" [URLS...]
```
This keeps the "download on pod" architecture (fast datacenter bandwidth) while authenticating the requests.

**Privacy caveat:** the exported cookies file contains **all** browser cookies in Netscape format, not just YouTube's. Uploading it to a cloud pod means session tokens for every site you've logged into are on that pod until destruction. Mitigations: (a) filter the file to YouTube-only entries before upload — `grep -E '^(# |(#HttpOnly_)?([a-z0-9.-]*\.)?(youtube|google)\.com[[:space:]])' /tmp/yt-cookies.txt > /tmp/yt-only-cookies.txt` — note the `#HttpOnly_` alternate: Netscape-format exports prefix HttpOnly cookie *lines* with `#HttpOnly_`, and YouTube's key auth cookies (e.g. `LOGIN_INFO`, `SSID`) are HttpOnly, so a filter matching only `^# |^\.youtube` silently strips the very cookies that authenticate; or (b) use Option 2 if privacy concerns outweigh the speed win.

**Option 2 (fallback): download locally with browser cookies, then transfer the MP3s to the pod.**
Run locally:
```bash
yt-dlp --cookies-from-browser brave --sleep-interval 3 --max-sleep-interval 8 \
  -f "bestaudio[ext=m4a]/bestaudio" -x --audio-format mp3 -o "%(id)s.%(ext)s" [URLS...]
# Then transfer via scp or runpodctl send to /workspace/audio on the pod.
```
Slower (local bandwidth bound) but doesn't require pushing a cookies file into the pod.

**Browser + proxy notes (apply to both options):** substitute `brave` with `chrome`, `chromium`, or `firefox` based on what's installed (`find ~/.config ~/.mozilla -name "Cookies" -o -name "cookies.sqlite" 2>/dev/null` to check). If the user's browser goes through a SOCKS5 proxy (e.g. VPN), use the same proxy with `--proxy socks5://127.0.0.1:1080` so the IP the cookies were issued against matches the request IP — otherwise YouTube may still flag it. If using Option 1 (cookies file on pod), the pod will be making requests from a datacenter IP — cookies alone may not be enough if the account is tied to a residential IP; if that fails, switch to Option 2.

**For local files (source type `local` or `mixed`):**

If pod has exposed TCP SSH, use SCP (simpler, one-shot; the glob matches every extension the Phase 5 script accepts, and `/workspace/audio` must be created first — the YouTube branch's `mkdir` didn't run on a local-only job):
```bash
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'mkdir -p /workspace/audio'
scp -i ~/.ssh/id_ed25519 -P PORT /path/to/audio/*.{mp3,m4a,wav,flac,ogg,opus} root@IP:/workspace/audio/
```

Otherwise use `runpodctl send/receive` (works over proxy SSH too). `send` prints a one-time pairing code and **blocks until the receiver connects** — so run it detached, capture the code, then run `receive <code>` on the other side (don't try to hold two blocking foreground commands at once):
```bash
# Locally — detached send; returns immediately:
nohup runpodctl send /path/to/audio/directory > /tmp/rp-send.log 2>&1 &
sleep 2 && grep -o 'runpodctl receive [a-z0-9-]*' /tmp/rp-send.log   # capture the code

# On pod (one SSH session), using the captured code:
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'mkdir -p /workspace/audio && cd /workspace/audio && runpodctl receive <code>'
```

**Verify downloads:**
```bash
ls /workspace/audio/ | wc -l
```
Report count to user. If any files failed, list which ones and ask whether to proceed with what succeeded or abort.

### Phase 5: Batch transcribe

Write this Python script to a file on the pod (e.g. `/workspace/transcribe.py` via `scp` or a heredoc), then **run it detached and poll a log file** — do **not** run it as a blocking foreground SSH command. Two reasons: (1) the first run downloads the `large-v3` weights (~3 GB), which routinely exceeds a 2-minute tool timeout before any transcription starts; (2) a foreground SSH run dies to `SIGHUP` if the connection drops, killing the whole batch. Detaching survives both.

```bash
# Launch detached on the pod. nohup ignores SIGHUP; </dev/null + redirected stdout/stderr
# stop SSH from staying tied to the channel, so this call returns in <1s:
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT \
  'export LD_LIBRARY_PATH=/usr/local/lib/python3.11/dist-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH; cd /workspace; nohup python3 transcribe.py </dev/null > /workspace/transcribe.log 2>&1 &'
# The inline export is mandatory — this is a fresh SSH shell; Phase 3 step 3's export did not persist.
# Proxy SSH: identical remote command, wrapped in the Phase 2 step 5 PTY form —
#   script -qec 'ssh -tt -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519 SSH_TARGET "export LD_LIBRARY_PATH=/usr/local/lib/python3.11/dist-packages/nvidia/cudnn/lib:\$LD_LIBRARY_PATH; cd /workspace; nohup python3 transcribe.py </dev/null > /workspace/transcribe.log 2>&1 & exit"' /dev/null
```

**Poll protocol.** The launch returns immediately — the batch is still running. Re-run the poll below every ~60–90s; the `sleep` runs *inside* the SSH call, so the Bash tool blocks for the interval (this is the wait mechanism — do not busy-loop back-to-back):

```bash
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'sleep 75; wc -l < /workspace/transcribe.log; tail -n 80 /workspace/transcribe.log'
```

The leading `wc -l` is the line count — compare it across consecutive polls to tell a *running* log (advancing) from a *dead* one (frozen). Classify each poll — **do not proceed to Phase 6 until you reach Success:**
- **Success** — the log's final line is `Done.` → continue to Phase 6.
- **Failure (crash)** — the log contains `Traceback (most recent call last)` → an unhandled exception (includes the diarisation `AssertionError`); stop, diagnose, don't retrieve. Match this specific marker, **not** a bare `Error` / `None` substring — benign output ("0 errors", "language: None") contains those and would false-trigger. On diarisation runs, if the traceback names a gated model / HF-auth / `401` / `403` / `None` pipeline, it's the missing-token failure — re-do Phase 3 steps 2 & 4 (the failure the Phase 3 note warns is easy to miss under `nohup`).
- **Failure (silent death)** — no `Traceback`, no `Done.`, but the line count has **not advanced** across ~2 consecutive polls. A SIGKILL/OOM (`Killed` prints to the now-exited launch shell, never the redirected log), a `SystemExit` abort (e.g. the no-audio-files guard), or an upstream-tool fatal all present as a *frozen* log with no marker. **Before declaring death, check the process is actually gone:** `pgrep -af 'python3 transcribe.py'` in the same SSH call — the first-run `large-v3` weight download (~3 GB, tqdm disabled) is legitimately quiet for minutes after the `Loading ASR model` line, and a live process + frozen log during that window is *still running*, not dead. Process gone + stalled count = died → pull `tail -n 200`, diagnose; don't wait the full ceiling.
- **Still running** — line count is **still advancing**, no `Done.` → keep polling. Hard ceiling `max(30 min, ~2× the Phase 1 runtime estimate)` as a final backstop.

The script itself:

```python
import os, json, time, subprocess, tempfile
os.environ["TQDM_DISABLE"] = "1"

# Load HF token from pod cache (Phase 3 step 2 copies it here from local ~/.cache/huggingface/token).
# Required for the gated pyannote/speaker-diarization-3.1 pipeline; harmless without diarisation.
_tk_path = os.path.expanduser("~/.cache/huggingface/token")
if os.path.exists(_tk_path):
    with open(_tk_path) as f:
        os.environ["HF_TOKEN"] = f.read().strip()
        os.environ["HUGGING_FACE_HUB_TOKEN"] = os.environ["HF_TOKEN"]
HF_TOKEN = os.environ.get("HF_TOKEN")  # None if not present; passed through to DiarizationPipeline below

import numpy as np
import torch, whisperx

device = "cuda"                    # whisperx API wants string
torch_device = torch.device(device)  # pyannote 3.3.2 wants torch.device
compute_type = "float16"
batch_size = 16
diarize = DIARIZE  # True or False
num_speakers = NUM_SPEAKERS  # int or None
language = LANGUAGE  # ISO code (e.g. "en", "es") or None for autodetect
audio_dir = "/workspace/audio"
output_dir = "/workspace/transcripts"
os.makedirs(output_dir, exist_ok=True)

# Enumerate inputs FIRST — cheap, and puts lines in the log before the quiet model download
_AUDIO_EXTS = (".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus")  # case-insensitive match below
files = sorted(
    os.path.join(audio_dir, f)
    for f in os.listdir(audio_dir)
    if f.lower().endswith(_AUDIO_EXTS)
)
print(f"Found {len(files)} files to transcribe", flush=True)
if not files:
    raise SystemExit(f"No audio files in {audio_dir} matching {_AUDIO_EXTS} — nothing to do.")

# Load ASR model ONCE
print("Loading ASR model (first run downloads ~3 GB — log may be quiet for a few minutes)...", flush=True)
model = whisperx.load_model("large-v3", device, compute_type=compute_type)  # cloud = accuracy; keep distil-large-v3 for local CPU only
align_models = {}  # per-language cache — a --language auto batch can mix languages

if diarize:
    assert HF_TOKEN, (
        "Diarisation requested but no HF token on pod — Phase 3 step 2 was skipped. "
        "pyannote/speaker-diarization-3.1 is gated and Pipeline.from_pretrained returns None silently on auth failure."
    )
    from whisperx.diarize import DiarizationPipeline
    diarize_model = DiarizationPipeline(
        model_name="pyannote/speaker-diarization-3.1",
        device=device,
        use_auth_token=HF_TOKEN,
    )
    assert diarize_model.model is not None, (
        "DiarizationPipeline.model is None — token rejected (likely user-conditions at "
        "hf.co/pyannote/speaker-diarization-3.1 not accepted for this HF account)"
    )

    # Embedding model for per-cluster voice prints (matches what diarization-3.1 uses internally).
    # pyannote 3.3.2 requires: load Model.from_pretrained first, THEN pass to Inference() —
    # the string-name constructor path silently stores the string and explodes at .crop() time.
    # And Inference wants a torch.device, not the string "cuda" (fix_reproducibility calls device.type).
    from pyannote.audio import Model, Inference
    from pyannote.core import Segment
    _embed_base = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM")
    embed_model = Inference(_embed_base, window="whole", device=torch_device)


def _ensure_wav(audio_file):
    """pyannote's embed.crop uses soundfile which can't read m4a/mp3/aac.
    Convert to a temp 16kHz mono wav if needed. Returns (path, is_temp) — caller deletes if temp."""
    if audio_file.lower().endswith(".wav"):
        return audio_file, False
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", audio_file,
         "-ar", "16000", "-ac", "1", tmp.name],
        check=True,
    )
    return tmp.name, True

def longest_span_per_speaker(segments):
    """From word-level diarised segments, return {speaker: (start, end)} for the
    longest contiguous single-speaker span. Used to seed a clean voice print.
    """
    longest = {}
    current = None  # (speaker, start, end)
    for seg in segments:
        for w in seg.get("words", []):
            sp, ws, we = w.get("speaker"), w.get("start"), w.get("end")
            if sp is None or ws is None or we is None:
                continue
            if current is None or current[0] != sp:
                if current is not None:
                    d = current[2] - current[1]
                    if d > longest.get(current[0], (0.0, 0.0, 0.0))[2]:
                        longest[current[0]] = (current[1], current[2], d)
                current = (sp, ws, we)
            else:
                current = (sp, current[1], we)
    if current is not None:
        d = current[2] - current[1]
        if d > longest.get(current[0], (0.0, 0.0, 0.0))[2]:
            longest[current[0]] = (current[1], current[2], d)
    return {sp: (s, e) for sp, (s, e, _) in longest.items()}


for i, audio_file in enumerate(files, 1):
    basename = os.path.splitext(os.path.basename(audio_file))[0]
    out_path = os.path.join(output_dir, f"{basename}.json")
    if os.path.exists(out_path):  # resume: a rerun after a crash skips completed files
        print(f"[{i}/{len(files)}] {basename}... skip (already transcribed)", flush=True)
        continue
    print(f"[{i}/{len(files)}] {basename}...", end=" ", flush=True)
    t0 = time.time()

    audio = whisperx.load_audio(audio_file)
    if language:
        result = model.transcribe(audio, batch_size=batch_size, language=language)
        detected_language = language
    else:
        result = model.transcribe(audio, batch_size=batch_size)
        detected_language = result["language"]

    # Load alignment model per language (cached) — with --language auto, files in one batch can differ
    if detected_language not in align_models:
        align_models[detected_language] = whisperx.load_align_model(
            language_code=detected_language, device=device
        )
    align_model, align_metadata = align_models[detected_language]

    result = whisperx.align(
        result["segments"], align_model, align_metadata, audio, device
    )

    output_obj = {"segments": result["segments"], "language": detected_language}

    if diarize:
        diarize_segments = diarize_model(audio, num_speakers=num_speakers)
        result = whisperx.assign_word_speakers(diarize_segments, result)
        output_obj["segments"] = result["segments"]

        # Compute one voice-print embedding per cluster from its longest
        # contiguous span. Non-fatal — if embedding fails, transcripts still save.
        cluster_embeddings = {}
        wav_for_embed, wav_is_temp = None, False
        try:
            spans = longest_span_per_speaker(result["segments"])
            # Save span durations immediately — these are useful for downstream quality flags
            # even if embedding extraction fails (e.g. if ffmpeg or soundfile errors).
            output_obj["cluster_span_durations"] = {sp: e - s for sp, (s, e) in spans.items()}
            # pyannote's soundfile backend can't read m4a/mp3/aac — convert once per file.
            wav_for_embed, wav_is_temp = _ensure_wav(audio_file)
            for speaker, (start, end) in spans.items():
                if end - start < 1.0:  # too short for a reliable embedding
                    continue
                try:
                    emb = embed_model.crop(wav_for_embed, Segment(start=start, end=end))
                    arr = emb.data if hasattr(emb, "data") else emb
                    cluster_embeddings[speaker] = np.asarray(arr).flatten().tolist()
                except Exception as e:
                    print(f"\n[cloud]   embed fail {speaker}: {e}", flush=True)
            output_obj["cluster_embeddings"] = cluster_embeddings
        except Exception as e:
            print(f"\n[cloud]   embedding pass skipped: {e}", flush=True)
        finally:
            if wav_is_temp and wav_for_embed:
                try: os.unlink(wav_for_embed)
                except Exception: pass

    with open(out_path, "w") as f:
        json.dump(output_obj, f)

    elapsed = time.time() - t0
    # Per-file status manifest (.jsonl so Phase 6's *.json count ignores it)
    with open(os.path.join(output_dir, "manifest.jsonl"), "a") as mf:
        mf.write(json.dumps({"file": basename, "status": "ok", "elapsed_s": round(elapsed, 1)}) + "\n")
    print(f"{elapsed:.1f}s")

print("Done.")
```

Replace `DIARIZE`, `NUM_SPEAKERS`, and `LANGUAGE` with actual values from arguments. `LANGUAGE` defaults to `"en"`; set to `None` only when `--language auto` was passed.

### Phase 6: Retrieve results

**Gate:** only enter this phase once the Phase 5 poll reached the **Success** state (`Done.` is the log's final line, no traceback). Phase 5 now launches detached, so a premature tar would ship a partial or empty archive and Phase 7 would then destroy the pod mid-run. As a cross-check, confirm the JSON count matches the input count before tarring: `ls /workspace/transcripts/*.json | wc -l`.

If the pod has exposed TCP SSH, prefer plain SCP (one-shot, no pairing dance — mirrors Phase 4's transfer preference):
```bash
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'cd /workspace && tar czf transcripts.tar.gz transcripts/'
scp -i ~/.ssh/id_ed25519 -P PORT root@IP:/workspace/transcripts.tar.gz /tmp/
cd /tmp && tar xzf transcripts.tar.gz
```

Over proxy SSH, use `runpodctl send/receive` with the detached-send pattern (see Phase 4 — `send` blocks and prints a one-time pairing code; here the *pod* sends, so launch it detached on the pod, grep the code from its log, then receive locally):
```bash
# On pod (one SSH call): tar, then detached send
ssh ... 'cd /workspace && tar czf transcripts.tar.gz transcripts/ && nohup runpodctl send transcripts.tar.gz > /workspace/rp-send.log 2>&1 &'
ssh ... 'sleep 2; grep -o "runpodctl receive [a-z0-9-]*" /workspace/rp-send.log'   # capture the code

# Locally, with the captured code:
cd /tmp && runpodctl receive <code>
tar xzf transcripts.tar.gz
```

**If voice references are in use AND you don't have a pinned Phase-8 venv locally, run Phase 8 matching on-pod BEFORE Phase 7 destroy.** See Voice references section. The pod has the exact pinned pyannote + wespeaker model weights cached; destroying first and then setting up a local env from scratch will retry the dep-triage we just recovered from.

### Phase 7: Destroy pod

```bash
runpodctl pod delete <POD_ID>
```

Do this immediately after retrieving results. Confirm destruction to the user. **Do not leave the pod running.**

### Phase 8: Post-process to markdown

For each JSON transcript file:

1. **Parse segments.**

2. **Format transcript text.** The gap-threshold (1.5s), timestamp-format, and monologue-fallback rules are deliberately duplicated from `/transcribe` Phase 3 step 2 — **those clauses must stay in sync; update both files together if they change**. The `speaker: None` fill and voice-reference name mapping below are cloud-only additions (no sync obligation):

   **Without diarisation:** Insert paragraph break wherever gap between segments exceeds 1.5 seconds. Concatenate segment text within each paragraph. Prefix each paragraph with a timestamp (`[MM:SS]` for <1hr, `[H:MM:SS]` for ≥1hr) derived from the first segment's `start`.

   **Monologue fallback.** For recordings longer than 5 minutes, after the initial split, check: is the paragraph count at least `duration_seconds / 120` (roughly one per two minutes)? If not, recompute — sort segment-to-segment gaps descending, let `N = min(floor(duration_seconds / 90), len(gaps))`, use `gaps_desc[N-1]` as the new threshold, re-split; if there are no gaps at all (`len(gaps) == 0`, e.g. a single segment), skip the fallback and keep the initial split. State the threshold used in your user-facing response.

   **With diarisation:** Iterate over the **words** array (not segments) — a single segment often contains multiple speakers. Before grouping, **forward/back-fill any words with `speaker: None`** from their nearest non-None neighbour (pyannote occasionally leaves words unassigned; treating `None` as a new speaker produces a spurious "Speaker 4+"). Then group consecutive words by speaker. Start a new paragraph on speaker change OR >1.5s gap. Prefix each paragraph with timestamp + speaker label in bold:
   ```
   [00:00] **Speaker 1:** First speaker's text.

   [00:45] **Speaker 2:** Second speaker responds.
   ```
   **Speaker name mapping.** The Phase 5 script saves a `cluster_embeddings` field in the JSON (one voice-print vector per diarised cluster, extracted from each cluster's longest contiguous span). If voice-reference files exist for any known speakers (see "Voice references" section below), run cosine similarity between each `cluster_embeddings` entry and each reference embedding. Assign the reference name to the closest match above the similarity threshold. Clusters without a high-confidence match fall back to `Speaker N` in order of first appearance. If `cluster_embeddings` is absent (older JSON, or embedding pass failed) or no voice references exist, use `Speaker N` for all clusters.

3. **LLM cleanup pass** (skip if `--raw` was passed):

   **This means reading the transcript paragraph by paragraph, not running regex patterns.** Regex handles known-entity capitalisation (city names, product names); homophones (peace/piece, their/there) and garbled proper nouns (WhisperX maps unfamiliar names to common English words) only surface by reading in context. A regex-only pass will miss these and produce a transcript that looks clean but isn't.

   Rules:
   - Fix non-words to their most likely intended word
   - Fix obvious grammar/punctuation errors introduced by the transcription model (not the speaker's actual grammar — ESL patterns, filler words, etc. stay)
   - Mark genuinely unclear sections as `[inaudible]` rather than guessing
   - For uncertain proper noun spellings (names of people, places), flag with `[?]` suffix so the user can correct — e.g. `Jayne Abernathy[?]`. **Don't silently guess at names** — the user will know the correct spelling and can fix the flagged ones in one pass.
   - Preserve the speaker's actual words and meaning — don't rewrite, paraphrase, or "improve"
   - Preserve timestamps exactly
   - Preserve speaker labels exactly
   - Do NOT fix the speaker's actual speech patterns (um, uh, repeated words, broken sentences) — these are features, not bugs

   Process the full transcript in a single pass. If the transcript exceeds ~50KB of text, split into ~20KB chunks with 2-paragraph overlap to preserve context at boundaries.

4. **If diarisation was used**, show the user a summary of each speaker (word count + first substantive utterance) and ask if they want to rename the `Speaker N` labels (e.g. "Speaker 1 is Mum, Speaker 3 is Dad"). Apply renames before saving.

5. **Save as markdown** in the output directory:

   > ⚠️ **Verbatim fidelity (`_shared-rules.md` §14):** the vault's formatting hook rewrites spelling in place on `Write`/`Edit` and corrupts the speaker's verbatim words. So **split the write**: header via the editor, body via the shell. Don't `Edit` the file afterwards — or rely on a path-level exclude for the output folder.

**Write the header only** with the editor tool (down to and including the `---`):

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

**Then append the body via the shell** so the hook never touches it (stage the formatted text to a temp file, then append):

```bash
cat > /tmp/transcript-body.md <<'BODY'
{formatted transcript text}
BODY
printf '\n' >> "<note>.md" && cat /tmp/transcript-body.md >> "<note>.md"
```

6. **If batch job (multiple files):** Create index file (`00 - Index.md`) with wikilinks to all transcripts, sorted by filename. Skip for single-file jobs.

7. **Ask user** if they want a synthesis document (thematic summary mapping key concepts to their use case). If yes, read all transcripts and generate one.

## Voice references (optional, recommended for recurring speakers)

Diarisation labels are just `SPEAKER_00`, `SPEAKER_01`, etc. — which physical human each cluster corresponds to has to be inferred. The default pipeline uses "first appearance in time" which breaks when the user isn't the first to speak. A pre-computed voice embedding for each known recurring speaker lets the pipeline match clusters to names deterministically.

**Where reference files live:** the default location is `$VAULT_PATH/voice-references` — set the `VOICE_REF_DIR` env var to point elsewhere (e.g. a sub-area of the vault). Store `.m4a` or `.wav` files there — one per known speaker; the filename stem (e.g. `alice`) becomes the speaker name in the transcript. **Resolve the directory with this block — do not skip it, and do not improvise a full-vault `find` (slow over a large vault):**

```bash
VAULT_PATH="${VAULT_PATH:-$HOME/Files}"                                    # env var may be unset in a fresh shell; if your setup has a vault resolver (`_shared-rules.md` §1), prefer its resolved path — the fallback here is acceptable only because this is a read-only lookup that degrades to Speaker N
ref_dir="${VOICE_REF_DIR:-$VAULT_PATH/voice-references}"                   # default; override VOICE_REF_DIR to relocate — no walk
[ -d "$ref_dir" ] || ref_dir=$(find "$VAULT_PATH" -maxdepth 5 -type d -name voice-references 2>/dev/null | head -1)  # fallback if not at the default
{ [ -n "$ref_dir" ] && [ -d "$ref_dir" ]; } && echo "voice refs: $ref_dir" || echo "no voice references found — speaker names will degrade to Speaker N"
```

Pass the resolved `$ref_dir` to Phase 8. If it comes back empty, that is the expected "no references" path — proceed with `Speaker N` labels, don't error.

**Capture spec:** 20–30s of clean solo speech from each known speaker. Natural conversational register (not reading aloud — reading voice differs meaningfully). No background music, no second speaker bleed-through, no heavy compression. A phone voice-memo .m4a is fine.

**Pipeline split:** Phase 5 (on-pod) writes one embedding vector per diarised cluster into the JSON under `cluster_embeddings`, plus per-cluster longest-span durations under `cluster_span_durations` (used for diarisation-quality flags). Phase 8 loads reference embeddings for known speakers, computes cosine similarity, and assigns names above threshold — with quality flags if span distribution is skewed.

**Phase 5 embedding extraction is wired and empirically validated (2026-04-22).** See the script in Phase 5. It uses the same embedding model (`pyannote/wespeaker-voxceleb-resnet34-LM`) that `pyannote/speaker-diarization-3.1` uses internally, so cluster vs reference embeddings live in the same space. Extraction fails gracefully if the span is too short or the audio slice errors out. See **Implementation status** at the end of this section for exactly which pieces were executed vs. logic-checked only.

**Where Phase 8 runs (choose one):**

- **On-pod, before destruction (recommended for occasional use).** Deps are already installed and model weights cached. **First transfer the voice-reference files to the pod** — they live in the local vault and are not on the pod otherwise (`scp -i ~/.ssh/id_ed25519 -P PORT "$ref_dir"/*.{m4a,wav} root@IP:/workspace/voice-refs/` after a `mkdir -p`, or `runpodctl send` over proxy) — and point the script's `ref_dir` at that pod path, else it finds 0 references and silently degrades every cluster to `Speaker N`. Then run the script below on the pod, capture the name map, then destroy. No local env setup needed. This is what validated end-to-end on 2026-04-22.
- **Locally in a pinned venv (for repeat runs on old JSONs without a pod).** The laptop's system Python has numpy 2.x and no pyannote, which will fail on the np.NaN path. Create a dedicated venv once:
  ```bash
  python3 -m venv ~/.venvs/whisperx-phase8
  source ~/.venvs/whisperx-phase8/bin/activate
  pip install 'numpy<2.0' 'pyannote-audio==3.3.2' 'huggingface_hub==0.24.7' matplotlib scipy torch torchaudio
  ```
  Activate before running Phase 8. CPU-only is fine (one embedding per ref + per cluster is cheap). **If a venv already exists at that path, verify the pins before trusting it** — it may have been created or upgraded outside this recipe, and a drifted numpy 2.x / pyannote 4.x fails exactly like the system Python:
  ```bash
  ~/.venvs/whisperx-phase8/bin/python -c "import numpy, pyannote.audio; assert numpy.__version__.startswith('1.'), f'numpy {numpy.__version__} — recreate the venv with the pins above'; print('pins ok')"
  ```

**Phase 8 matching code:**

```python
import glob, json, os, subprocess, tempfile
import numpy as np
import torch
from pyannote.audio import Model, Inference
from scipy.spatial.distance import cosine

SIMILARITY_THRESHOLD = 0.65  # validated 2026-04-22; see Threshold calibration below

def _name_from_path(ref_path):
    stem = os.path.splitext(os.path.basename(ref_path))[0]
    return stem.replace("-", " ").replace("_", " ").title()

def _ensure_wav(audio_file):
    """soundfile can't read m4a/mp3/aac — convert if needed."""
    if audio_file.lower().endswith(".wav"):
        return audio_file, False
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", audio_file,
         "-ar", "16000", "-ac", "1", tmp.name],
        check=True,
    )
    return tmp.name, True

def load_reference_embeddings(ref_dir, device="cpu"):
    """Cache reference embeddings keyed by display name. Runs once per session."""
    ref_dir = os.path.expanduser(ref_dir)  # glob does NOT expand ~
    base = Model.from_pretrained("pyannote/wespeaker-voxceleb-resnet34-LM")
    embed = Inference(base, window="whole", device=torch.device(device))
    refs = {}
    for ref_path in sorted(glob.glob(os.path.join(ref_dir, "*.m4a"))
                           + glob.glob(os.path.join(ref_dir, "*.wav"))):
        name = _name_from_path(ref_path)
        wav, is_temp = _ensure_wav(ref_path)
        try:
            out = embed(wav)
            arr = out.data if hasattr(out, "data") else out
            refs[name] = np.asarray(arr).flatten()
        finally:
            if is_temp:
                try: os.unlink(wav)
                except Exception: pass
    return refs

def assign_names(cluster_embeddings, ref_embeddings, span_durations=None,
                 threshold=SIMILARITY_THRESHOLD):
    """Returns {cluster_id: (display_name_or_None, best_sim, quality_flag)}.

    quality_flag is 'ok', 'low-confidence' (0.50-threshold), or 'suspect-cluster'
    (span distribution skewed — see diarisation-quality check below).
    """
    # Diarisation quality heuristic: if one span is ≥50× longer than another, or if
    # the shortest span is <5s while others are >60s, the short one is probably noise
    # and the long one is probably mixed. Flag both as suspect.
    suspect = set()
    if span_durations:
        durs = sorted(span_durations.values())
        if len(durs) >= 2 and durs[-1] > 0 and durs[0] < max(5.0, durs[-1] / 50.0):
            suspect = set(span_durations.keys())

    assignments = {}
    for cluster_id, centroid in cluster_embeddings.items():
        centroid = np.asarray(centroid)
        best_name, best_sim = None, -1.0
        for name, ref_emb in ref_embeddings.items():
            sim = 1.0 - cosine(centroid, ref_emb)
            if sim > best_sim:
                best_name, best_sim = name, sim
        name = best_name if best_sim >= threshold else None
        if cluster_id in suspect:
            flag = "suspect-cluster"
        elif name is None and best_sim >= 0.50:
            flag = "low-confidence"
        else:
            flag = "ok"
        assignments[cluster_id] = (name, best_sim, flag)
    return assignments

# Usage:
# 1. Load transcript JSON
# 2. embs = data.get("cluster_embeddings", {})
# 3. durs = data.get("cluster_span_durations", {})
# 4. vault = os.environ.get("VAULT_PATH") or os.path.expanduser("~/Files")
#    ref_dir = os.environ.get("VOICE_REF_DIR") or os.path.join(vault, "voice-references")  # pass through from the resolver above
#    refs = load_reference_embeddings(ref_dir) if os.path.isdir(ref_dir) else {}  # {} → degrade to Speaker N
#    NB: do NOT shell out to `find '$VAULT_PATH' ...` — single quotes pass the var literally and the find finds nothing.
# 5. assignments = assign_names(embs, refs, span_durations=durs)
# 6. When rendering markdown: if assignments[raw_speaker][0] is set AND flag == "ok",
#    use the name; otherwise fall back to Speaker N (first-appearance order) and
#    print the similarity + flag so the user can manually override if needed.
# 7. Always SHOW the user the assignments with similarities + flags before saving,
#    so they can override low-confidence or suspect-cluster matches.
```

**Skip when:** no reference files exist, or `cluster_embeddings` is absent from the JSON (older run, or on-pod embedding failed). The pipeline degrades to `Speaker N` labels.

**Threshold calibration (validated 2026-04-22 on a 46-min 2-speaker recording):**

| Cluster condition | Observed cosine similarity vs reference .m4a |
|---|---|
| Clean Speaker A cluster, 132s span | **0.9273** (correct match) |
| Clean Speaker B cluster, 121s span | **0.1349** (clean negative) |
| Mis-clustered span (458s, mixed both speakers) | 0.6718 (false positive at 0.65 threshold) |
| Noise span (1.2s, likely misdiarisation blip) | 0.2924 |

0.65 is appropriate for the clean case (separation margin of ~0.80). The false-positive case is a diarisation quality issue, not a threshold issue — a higher threshold (e.g. 0.75) would reject the mis-clustered case but also reject legitimate low-quality captures. Instead, use the `span_durations` quality heuristic in `assign_names` to flag suspect clusters regardless of their similarity score.

**Implementation status (be honest about what was run vs. what was logic-checked):**

Empirically validated 2026-04-22 against a 46-min 2-speaker recording:
- Pin set (Phase 3 install line) — installed cleanly, all imports resolved, end-to-end run succeeded
- Three Phase 5 code fixes — `Model.from_pretrained()` before `Inference()`, `torch.device("cuda")` not string, WAV conversion before `embed.crop()`
- Core embedding + cosine math — Speaker A cluster 0.9273, Speaker B 0.1349, mis-clustered 0.6718, noise 0.2924

Logic-checked only, NOT executed end-to-end in the validation run:
- Skip-existing resume + `manifest.jsonl` per-file status in the Phase 5 script, the input-enumeration-before-model-load reorder, the per-language alignment-model cache, and the inline `LD_LIBRARY_PATH` launch prefix (all added in the 2026-07-19 audit)
- `cluster_span_durations` save + the "save before wav conversion" ordering (added post-validation)
- Phase 8 `assign_names` quality-flag system (suspect/low-confidence/ok) — the 50× ratio heuristic was logic-traced against today's data points but the function itself wasn't run
- Phase 3 verify one-liner in its exact concatenated form (pieces tested individually, not as one command)
- Local venv recipe for Phase 8 (not set up or tested on this laptop)

Caught and fixed 2026-04-27 against a fresh secure-cloud RTX 4090 pod (Linux client):
- HF token transfer (Phase 3 step 2) and `use_auth_token=` plumbing through Phase 5's `DiarizationPipeline` — the 2026-04-22 "validated end-to-end" pod must have had the token cached from a prior session, because a clean pod with no token returns `None` from `Pipeline.from_pretrained` and the 2026-04-22 SETUP_OK check (VAD + wespeaker only, neither gated) couldn't see it.
- Cross-platform token-source documentation (Linux/macOS/Git-Bash bash and Windows PowerShell variants); `huggingface_hub` writes to `~/.cache/huggingface/token` on all three platforms regardless of `XDG_CACHE_HOME`/`LOCALAPPDATA`. Windows-side commands logic-checked, NOT executed end-to-end on Windows.

First real-use of the untested pieces will likely surface minor issues — trust but verify.

## Notes

- **Validated end-to-end (2026-04-22):** full pipeline including voice-reference matching validated on RTX 4090 SECURE against a 2-file 46-min recording set. First run of the voice-ref code path — the 2026-04-21 "validation" only covered transcribe+diarise; the embedding code was shipped same-day but never executed, so three bugs escaped until today (fixed in Phase 5 / Phase 8 code above). Also validated **that pinning is mandatory**: fresh unpinned installs today pulled whisperx 3.8.5 + pyannote-audio 4.0.4 which are mutually incompatible and break at `whisperx.load_model()`. Installation dep-conflict warnings for torch/torchvision are expected with `--no-deps` whisperx — ignore them if the Phase 3 SETUP_OK check (VAD + embed Model load) passes. Total pod time today ~26 min (including dep triage), cost ~USD 0.30. With the pinned install line the normal pod run should be back to ~12 min / ~USD 0.14.
- **Pin stability warning:** the pin set in Phase 3 is load-bearing. whisperx/pyannote-audio had simultaneous breaking releases 2026-04-22 (whisperx 3.8.x expects torch 2.8 and pyannote 4.x; pyannote 4.0.x changes the Inference API). numpy 2.0 removes `np.NaN` which pyannote 3.3.2 uses. huggingface_hub 0.25+ removes the `use_auth_token` decorator that pyannote 3.3.2 relies on. Transformers 4.46+ imports `is_offline_mode` from hub top-level which isn't exported. All of these are independent versioning decisions upstream — bumping any one usually cascades. Re-validate end-to-end when bumping. Pins are also tied to the **pod base image** (`runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04`) — the Phase 2 command pins that exact image tag, so drift only enters if you change the tag or fall back to the `runpod-torch-v240` template (whose backing image RunPod can update); either way the pin set may not co-install and the full dep-triage could recur.
- **Performance (GPU-dependent, `large-v3`):** ~15–30× realtime on RTX 3090 / 4090. 5 hours of audio transcribes in ~10–20 min on mid-tier cards. `distil-large-v3` was ~3–4× faster but less accurate — cloud now defaults to `large-v3` because the time/cost delta is noise at batch sizes under a few hours. Diarisation adds a few seconds per file on GPU at this scale (not ~20–30 min as an earlier draft claimed — today's 46-min batch diarised in ~20s on RTX 4090).
- **Cost:** ~USD 0.17–0.69/hr depending on GPU + cloud tier. Typical batch job under 3 hours of audio: USD 0.05–0.25 total.
- **SSH info retrieval:** `runpodctl pod get <id>` returns IP, port, and full `ssh_command` directly — no manual web UI step needed for exposed-TCP SSH. The old skill claim that "PODID-HASH is web-UI-only" applies only to the **proxy-SSH** path (`PODID-HASH@ssh.runpod.io`), which is still not in the API.
- **`runpodctl pod create` flag syntax:** deprecated `--gpuType`/`--gpuCount`/`--imageName`/`--containerDiskSize`/`--volumeSize`/`--startSSH`/`--communityCloud`/`--cost` have been replaced by `--gpu-id`/`--gpu-count`/`--image`/`--container-disk-in-gb`/`--volume-in-gb`/`--ssh`/`--cloud-type COMMUNITY|SECURE`. Old syntax will error with "unknown flag". `--cost` has no new-syntax equivalent.
- **yt-dlp `-x` is not format-selection:** `-x --audio-format mp3` extracts audio but does not constrain the download — yt-dlp will often pick the best video stream (1+ GB) and strip audio from it. Always pair with `-f "bestaudio[ext=m4a]/bestaudio"` to download audio-only.
- **YouTube anti-bot on batches:** >5 sequential URLs from one IP will trigger "Sign in to confirm you're not a bot." Use `--cookies-from-browser <browser>` and `--sleep-interval N` to mitigate. Match the proxy the cookies were issued through if the browser is behind one.
- **`stockStatus` is not availability:** most of the fleet commonly reads `Low` while still carrying `available: true` and deploying without issue. Select on `available`; use stock as a tiebreaker and escalate only on a real capacity error at create time. Always `runpodctl gpu list` first and pick from the priority tier (A4000 → RTX 3090 → A5000 → RTX 4090 → A40 secure-only → L40S; Phase 1 step 5 is canonical). Unreachable datacenter IPs (common from GFW-restricted networks) are a separate failure mode — check `ssh.runpod.io` reachability as a fallback signal.
- **Community-cloud allocation can stall:** if `uptimeSeconds` stays 0 for >5 min with `desiredStatus: RUNNING`, the pod is stuck in an allocation queue. Delete and retry on secure cloud (more expensive but provisions immediately). Don't burn >10 min on a stuck pod.
- **WhisperX install order is critical:** `--no-deps` prevents torch breakage. The torch reinstall after pyannote-audio is mandatory — pyannote-audio pulls a newer torch that breaks CUDA on the cu124-based pod image, so the final `pip install torch==2.4.1 --force-reinstall` restores the matching build.
- **yt-dlp on pod vs local:** For YouTube URLs, always download directly on the pod — datacenter bandwidth is faster and eliminates the transfer step. Only use local download + `runpodctl send` for files that are already on disk.
- **`runpodctl send/receive`:** P2P transfer. Both sides must be running at once — `send` blocks and prints a one-time pairing code; use the detached-send pattern (Phase 4 / Phase 6) rather than trying to hold two blocking foreground commands. Works for both files and directories.
- **Pod lifecycle:** Always destroy the pod when done. `runpodctl pod delete <POD_ID>`. Stopped pods still incur disk charges.

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and log observations at the end per that file.
