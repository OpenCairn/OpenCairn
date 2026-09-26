# RunPod execution reference

Read after the job scope and paid-run authorisation in `../SKILL.md`. Paths below are on the pod unless marked local. Keep local scratch output separate from vault destinations.

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
   Read `ssh.ip`, `ssh.port`, and `ssh_command` from the response where available. Treat missing fields or zero uptime as incomplete status, not proof of a dead pod; cross-check the pod detail/status view and an actual SSH readiness probe.

   **Only if direct TCP is unreachable from the user's network** (common on restricted networks like GFW — test with `nc -zv <ip> <port>`): fall back to proxy SSH via `ssh.runpod.io`. RunPod's REST API returns the proxy command (documented; not yet exercised here): `curl -s -H "Authorization: Bearer $RUNPOD_API_KEY" https://api.runpod.io/v2/pods/<POD_ID> | jq -r .ssh.proxy.command`. If that call fails, ask the user to copy the `ssh PODID-HASH@ssh.runpod.io -i ~/.ssh/id_ed25519` line from Pods > whisperx-batch > Connect.

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
   Ping and TCP probe results describe reachability from this client only. Neither ping failure nor a zero uptime counter proves filtering, a stopped sshd, or an allocation stall. Check the pod's actual status/logs and test the advertised proxy route before changing config. If the UI is needed, inspect the connected browser when available; ask for the connection line only when it cannot be obtained through available tools.

4. **Persistent failure:** after checking status and both reachable connection routes, retry a different cloud tier or datacenter only within the authorised budget. Record and terminate the failed job pod before creating another. Do not delete unrelated pods.

**Hard cap:** don't spend >10 min debugging a single pod. Salvage any results, terminate that pod, and retry only within the authorised budget; otherwise stop. GPU + cloud + region is a 3-dimensional search space — move across it rather than waiting.

### Phase 3: Setup pod environment

Run all commands via SSH. If using exposed TCP, standard `ssh ... "command"` works. If using proxy, use the `script -qec 'ssh -tt ...'` PTY wrapper shown in Phase 2 step 5.

1. **Install dependencies (pins are MANDATORY — see note below).** Honour the active package cooldown policy for all installations, including remote commands; if denied, use a supported resolver-wide route or stop at the policy boundary. Do not disguise the install as an SSH command to evade a hook. This pulls several GB of wheels (the cu124 torch wheel alone is ~2.5 GB) and dominates pod setup time — it routinely outlasts the exec call timeout. So **write it to a script and run it detached, polling a log**, exactly as Phase 5 does; a blocking foreground SSH call will be killed mid-install and leave a half-populated `site-packages`.

```bash
# Write the install script on the pod (quoted heredoc — nothing expands locally):
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'cat > /workspace/setup.sh' <<'SETUP'
set -e
apt-get update -qq && apt-get install -y -qq ffmpeg
pip install -q 'numpy<2.0'
# torch FIRST, from the PyTorch index. pyannote-audio depends on torch; if torch isn't already
# satisfied, pip resolves the newest torch (multi-GB, plus nvidia-* libs) from PyPI — and PyPI's
# CDN is slow from some pod hosts (~100-300 KB/s observed while download.pytorch.org gave 40 MB/s
# on the same pod). With 2.4.1 pre-installed the constraint is satisfied and nothing is fetched.
pip install -q torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu124
echo "TORCH_STAGE_OK $(python3 -c 'import torch; print(torch.__version__)')"
pip install -q yt-dlp 'whisperx==3.4.2' --no-deps
pip install -q 'faster-whisper==1.2.1' 'transformers==4.40.2' 'huggingface_hub==0.24.7' pandas nltk omegaconf 'pyannote-audio==3.3.2' matplotlib
echo "DEPS_STAGE_OK $(python3 -c 'import torch; print(torch.__version__)')"
# Guard: if the dependency step bumped torch anyway, restore the pinned cu124 build (fast index).
python3 -c 'import torch; assert torch.__version__.startswith("2.4.1")' 2>/dev/null || \
  pip install -q torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu124 --force-reinstall --no-cache-dir
pip install -q 'ctranslate2>=4.5.0'
echo INSTALL_OK
SETUP

# Launch detached — returns in <1s:
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT \
  'cd /workspace; nohup bash setup.sh </dev/null > /workspace/setup.log 2>&1 &'
```

**Poll** every ~45–60s, same protocol as Phase 5 (the `sleep` runs inside the SSH call, so the tool blocks for the interval):
```bash
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'sleep 45; wc -l < /workspace/setup.log; tail -n 20 /workspace/setup.log'
```
- Final line `INSTALL_OK` → continue to step 2. `TORCH_STAGE_OK` / `DEPS_STAGE_OK` mark the stages; the torch stage should finish in ~1–2 min (fast index) and the deps stage is the one that varies with the host's PyPI throughput.
- Log frozen with no `INSTALL_OK` → check the process is actually gone before calling it dead — `ps -C bash -o pid=,etime=,args= | rg 'bash setup[.]sh$'` (**not** `pgrep -f` / `pkill -f`: inside an SSH command the remote shell's own cmdline contains the pattern, so `pgrep -f` always "finds" a process and `pkill -f` kills your session with exit 255 while the target survives). `pip -q` is legitimately quiet for minutes on a large wheel. Process gone + no `INSTALL_OK` → read the tail for the failing line. `set -e` aborts on the first failure and pip re-runs are idempotent, so relaunching the same script after a kill or a fixed error resumes safely.
- Deps stage slow → measure rather than guess: `du -sb /tmp /root/.cache/pip` twice, 30 s apart, gives the effective download rate, and `ls -t /tmp/pip-unpack-*/` shows which wheel is in flight. Under ~500 KB/s is a slow-PyPI host; the remaining deps are ~200 MB, so budget ~15–25 min (23 min observed at ~200 KB/s) and let it run — re-provisioning costs about the same with no guarantee of a better host. If a `torch*.whl` or `nvidia_*.whl` appears in the in-flight list, the torch-first ordering above was lost — kill pip by PID and relaunch.

Over proxy SSH, wrap each call in the Phase 2 step 5 PTY form; a stdin-piped heredoc doesn't survive that wrapper, so transfer `setup.sh` with `runpodctl send` (Phase 4 pattern) instead of piping it.

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

   **One-time per HF account:** also visit https://hf.co/pyannote/speaker-diarization-3.1 (and its gated dependency https://hf.co/pyannote/segmentation-3.0 — see `$transcribe`'s prerequisites) once and click "Accept" on each user-conditions page. The token grants auth; the click grants the gating agreement. Without the click, the same token returns 403 and the pipeline silently becomes `None`.

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

**For URLs (source type `youtube` or `mixed` — YouTube or any other yt-dlp-supported site, e.g. LinkedIn event replays, Vimeo):** run these **on the pod** via SSH (same transport as Phase 3) — not locally; downloading on the pod is the whole point (datacenter bandwidth, no transfer step):
```bash
mkdir -p /workspace/audio
yt-dlp -f "bestaudio[ext=m4a]/bestaudio/best" -x --audio-format mp3 --audio-quality 5 \
  -o "/workspace/audio/%(id)s.%(ext)s" [URLS...]
```
**Critical:** the `-f "bestaudio[ext=m4a]/bestaudio/best"` flag is mandatory — without it, yt-dlp selects the best *video* stream and extracts audio afterwards, downloading e.g. 1.2 GB of video just to produce a 50 MB MP3. The `-x --audio-format mp3` alone does NOT constrain the download format. The trailing `/best` is the fallback for sites that publish only muxed streams (LinkedIn event replays are HLS video+audio with no audio-only rendition): without it yt-dlp aborts with "Requested format is not available" instead of taking the muxed stream. YouTube still resolves to the audio-only rendition first.

**Filename convention:** use `%(id)s.%(ext)s` (video ID), not `%(title)s.%(ext)s`. Titles often contain characters that break shell globs or are clickbait — the video ID is a stable identifier that makes post-processing easier. Preserve the original title in the output markdown metadata instead — and **persist the `id → title → URL → duration` mapping from Phase 1's inventory to a local file now** (e.g. `/tmp/yt-sources.json`): Phase 8's headers need the titles, and conversation context may not reliably carry them that far.

**Anti-bot mitigation for batches >5 URLs:** YouTube's anti-bot ("Sign in to confirm you're not a bot") kicks in partway through large bursts from a single IP. Two ways to mitigate — both run **locally first**, because the pod has no browser and no live YouTube session. Pick one:

**Option 1: download on the pod with site-scoped cookies, only when their transfer is authorised.** Export locally to a restricted scratch file, retain only the required origin's cookie domains (including Netscape `#HttpOnly_` lines), and inspect the remaining domain names without printing cookie values. Never transfer the whole browser cookie jar. Upload only the filtered file, then pass its pod path to `yt-dlp --cookies` with `--sleep-interval 3 --max-sleep-interval 8` and the audio format selector above. Delete local and remote cookie scratch files when no longer needed. If the authorised domains are unclear, use Option 2.

**Option 2 (default when cookie transfer is not authorised): download locally with browser cookies, then transfer the MP3s to the pod.**
Run locally:
```bash
yt-dlp --cookies-from-browser brave --sleep-interval 3 --max-sleep-interval 8 \
  -f "bestaudio[ext=m4a]/bestaudio" -x --audio-format mp3 -o "%(id)s.%(ext)s" [URLS...]
# Then transfer via scp or runpodctl send to /workspace/audio on the pod.
```
Slower (local bandwidth bound) but doesn't require pushing a cookies file into the pod.

**Browser + proxy notes (apply to both options):** substitute `brave` with `chrome`, `chromium`, or `firefox` based on what's installed (`find ~/.config ~/.mozilla -name "Cookies" -o -name "cookies.sqlite" 2>/dev/null` to check). If the user's browser goes through a SOCKS5 proxy (e.g. VPN), use the same proxy with `--proxy socks5://127.0.0.1:1080` so the IP the cookies were issued against matches the request IP — otherwise YouTube may still flag it. If using Option 1 (cookies file on pod), the pod will be making requests from a datacenter IP — cookies alone may not be enough if the account is tied to a residential IP; if that fails, switch to Option 2.

**For local files (source type `local` or `mixed`):**

If pod has exposed TCP SSH, use SCP (simpler, one-shot; transfer only the exact manifest-listed files, with unique basenames, and `/workspace/audio` must be created first — the YouTube branch's `mkdir` didn't run on a local-only job):
```bash
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'mkdir -p /workspace/audio'
scp -i ~/.ssh/id_ed25519 -P PORT "<EXACT_STAGED_AUDIO_FILE>" root@IP:/workspace/audio/
```

**Measure the transfer before trusting it.** Residential uplinks can be two orders of magnitude slower than the pod's ingress (12 KB/s observed against a pod that downloaded at 40 MB/s). Sample the destination size on the pod twice, ~20 s apart (`stat -c %s /workspace/audio/<file>`), and compute the rate. If the ETA exceeds a few minutes and the file was itself downloaded from a URL, kill the scp and switch to the URL branch above — the pod fetches from the origin instead. For a login-gated origin, export cookies locally and **filter to that site's domain** before uploading (retain only that origin’s required cookie domains, including Netscape `#HttpOnly_` entries; verify domain names without printing values); the filtered file is a few KB, so its upload is instant. Without a URL, shrink the payload first (`ffmpeg -vn -ac 1 -ar 16000 -b:a 32k` — Whisper resamples to 16 kHz mono anyway) and accept the wait.

Otherwise use `runpodctl send/receive` (works over proxy SSH too). `send` prints a one-time pairing code and **blocks until the receiver connects** — so keep the local sender in a tracked exec session, capture the code, then run `receive <code>` on the other side and collect both exit statuses (don't try to hold two blocking foreground commands at once):
```bash
# Locally — launch this in a tracked Codex exec session (use a unique scratch log):
runpodctl send /path/to/audio/directory > "<SCRATCH>/rp-send.log" 2>&1
# In another exec call, read the code while that session is running:
rg -o 'runpodctl receive [a-z0-9-]*' "<SCRATCH>/rp-send.log"

# On pod (one SSH session), using the captured code:
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'mkdir -p /workspace/audio && cd /workspace/audio && runpodctl receive <code>'
```

**Verify downloads:** compare the exact staged filename set with the source manifest, and probe each file with `ffprobe`. A matching count alone cannot detect a replaced or missing file. Report the verified count to the user. If any files failed, list which ones and ask whether to proceed with what succeeded or abort.

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

**Poll protocol.** The launch returns immediately — the batch is still running. Re-run the poll below every ~45–60s; the `sleep` runs *inside* the SSH call, so the exec call blocks for the interval (this is the wait mechanism — do not busy-loop back-to-back):

```bash
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'sleep 45; wc -l < /workspace/transcribe.log; tail -n 80 /workspace/transcribe.log'
```

The leading `wc -l` is the line count — compare it across consecutive polls to tell a *running* log (advancing) from a *dead* one (frozen). Classify each poll — **do not proceed to Phase 6 until you reach Success:**
- **Success** — the log's final line is `Done.` → continue to Phase 6.
- **Failure (crash)** — the log contains `Traceback (most recent call last)` → an unhandled exception (includes the diarisation `AssertionError`); stop, diagnose, don't retrieve. Match this specific marker, **not** a bare `Error` / `None` substring — benign output ("0 errors", "language: None") contains those and would false-trigger. On diarisation runs, if the traceback names a gated model / HF-auth / `401` / `403` / `None` pipeline, it's the missing-token failure — re-do Phase 3 steps 2 & 4 (the failure the Phase 3 note warns is easy to miss under `nohup`).
- **Failure (silent death)** — no `Traceback`, no `Done.`, but the line count has **not advanced** across ~2 consecutive polls. A SIGKILL/OOM (`Killed` prints to the now-exited launch shell, never the redirected log), a `SystemExit` abort (e.g. the no-audio-files guard), or an upstream-tool fatal all present as a *frozen* log with no marker. **Before declaring death, check the process is actually gone:** `ps -C python3 -o pid=,etime=,args= | rg 'python3 transcribe[.]py$'` in the same SSH call (not `pgrep -f` — see the Phase 3 poll note on self-matching) — a live process + frozen log is *still running*, not dead. Two legitimate quiet windows: the first-run `large-v3` weight download (~3 GB, tqdm disabled) after the `Loading ASR model` line, and any single file's transcription, which emits nothing between its `[i/N] name...` line and its elapsed-time line. Process gone + stalled count = died → pull `tail -n 200`, diagnose; don't wait the full ceiling.
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
    if os.path.exists(out_path):  # resume only a complete, parseable prior output
        with open(out_path) as f:
            previous = json.load(f)
        if not isinstance(previous.get("segments"), list) or not previous.get("language"):
            raise RuntimeError(f"Invalid resume output: {out_path}")
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

    pending_path = out_path + ".partial"
    with open(pending_path, "w") as f:
        json.dump(output_obj, f)
    os.replace(pending_path, out_path)

    elapsed = time.time() - t0
    # Per-file status manifest (.jsonl so Phase 6's *.json count ignores it)
    with open(os.path.join(output_dir, "manifest.jsonl"), "a") as mf:
        mf.write(json.dumps({"file": basename, "status": "ok", "elapsed_s": round(elapsed, 1)}) + "\n")
    print(f"{elapsed:.1f}s", flush=True)

print("Done.", flush=True)
```

Replace `DIARIZE`, `NUM_SPEAKERS`, and `LANGUAGE` with actual values from arguments. `LANGUAGE` defaults to `"en"`; set to `None` only when `--language auto` was passed.

### Phase 6: Retrieve results

**Gate:** only enter this phase once the Phase 5 poll reached the **Success** state (`Done.` is the log's final line, no traceback). Phase 5 now launches detached, so a premature tar would ship a partial or empty archive and Phase 7 would then destroy the pod mid-run. Compare the JSON basename set with the exact expected input set and parse every JSON before tarring. A count alone cannot detect duplicate basenames or corrupt output.

If the pod has exposed TCP SSH, prefer plain SCP (one-shot, no pairing dance — mirrors Phase 4's transfer preference):
```bash
ssh -i ~/.ssh/id_ed25519 root@IP -p PORT 'cd /workspace && tar czf transcripts.tar.gz transcripts/'
scp -i ~/.ssh/id_ed25519 -P PORT root@IP:/workspace/transcripts.tar.gz "<SCRATCH>/"
# Inspect archive members first; reject absolute paths, traversal, and symlinks.
tar tzf "<SCRATCH>/transcripts.tar.gz"
tar xzf "<SCRATCH>/transcripts.tar.gz" -C "<SCRATCH>"
```

Over proxy SSH, use `runpodctl send/receive` with the detached-send pattern (see Phase 4 — `send` blocks and prints a one-time pairing code; here the *pod* sends, so launch it detached on the pod, grep the code from its log, then receive locally):
```bash
# On pod (one SSH call): tar, then detached send
ssh ... 'cd /workspace && tar czf transcripts.tar.gz transcripts/ && nohup runpodctl send transcripts.tar.gz > /workspace/rp-send.log 2>&1 &'
ssh ... 'sleep 2; rg -o "runpodctl receive [a-z0-9-]*" /workspace/rp-send.log'   # capture the code

# Locally, with the captured code:
cd "<SCRATCH>" && runpodctl receive <code>
# Validate archive members before extraction as above.
tar xzf transcripts.tar.gz
```

**After retrieval, validate locally:** every expected input has one parseable JSON with a segments list and language. Compare archive checksums across pod and local copy. Empty segments need an explicit silent-audio finding; treat unexplained empty output as a failure. Preserve the manifest and raw JSON until markdown saves pass.

**If voice references are in use AND you don't have a pinned Phase-8 venv locally, run Phase 8 matching on-pod BEFORE Phase 7 destroy.** Read `voice-references.md` in this reference directory. The pod has the exact pinned pyannote + wespeaker model weights cached; destroying first and then setting up a local env from scratch will retry the dep-triage we just recovered from.

### Phase 7: Destroy pod

```bash
runpodctl pod delete <POD_ID>
```

Do this immediately after validated retrieval and any required on-pod voice matching. Verify with a successful authenticated `runpodctl pod list` that the exact job pod ID is absent; if using `pod get`, only an explicit not-found result establishes deletion, not a network/authentication error. Confirm destruction only after that check. On error or cancellation, salvage partial outputs where possible, then delete the job pod; report an unresolved deletion with its ID. **Do not leave the pod running while doing local cleanup or synthesis.**

