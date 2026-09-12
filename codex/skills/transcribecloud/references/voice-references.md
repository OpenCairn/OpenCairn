## Voice references (optional, recommended for recurring speakers)

Diarisation labels are just `SPEAKER_00`, `SPEAKER_01`, etc. — which physical human each cluster corresponds to has to be inferred. The default pipeline uses "first appearance in time" which breaks when the user isn't the first to speak. A pre-computed voice embedding for each known recurring speaker lets the pipeline match clusters to names deterministically.

**Where reference files live:** the default location is `$VAULT_PATH/voice-references` — set the `VOICE_REF_DIR` env var to point elsewhere (e.g. a sub-area of the vault). Store `.m4a` or `.wav` files there — one per known speaker; the filename stem (e.g. `alice`) becomes the speaker name in the transcript. **Resolve the directory with this block — do not skip it, and do not improvise a full-vault `find` (slow over a large vault):**

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
# Stop if resolution fails; use the verified VAULT_PATH.
ref_dir="${VOICE_REF_DIR:-$VAULT_PATH/voice-references}"
if [ -d "$ref_dir" ]; then
    printf 'voice refs: %s\n' "$ref_dir"
else
    printf 'No voice-reference directory at %s; use Speaker N unless another location is supplied.\n' "$ref_dir"
fi
```

The block **echoes** the resolved path — read it out of that output and **substitute the literal path** into every later command (the transfer below, and the Phase 8 script's `ref_dir`). Shell state does not persist between exec calls, so a later `"$ref_dir"` is empty; and on the pod neither `VAULT_PATH` nor `VOICE_REF_DIR` exists (ssh doesn't forward them), so a pod-side re-derivation resolves to a non-existent `/root/...` path. Both failures are silent — every cluster quietly degrades to `Speaker N`. A missing reference directory means use `Speaker N`. Failure to resolve the vault itself is an error and must stop vault work.

**Capture spec:** 20–30s of clean solo speech from each known speaker. Natural conversational register (not reading aloud — reading voice differs meaningfully). No background music, no second speaker bleed-through, no heavy compression. A phone voice-memo .m4a is fine.

**Pipeline split:** Phase 5 (on-pod) writes one embedding vector per diarised cluster into the JSON under `cluster_embeddings`, plus per-cluster longest-span durations under `cluster_span_durations` (used for diarisation-quality flags). Phase 8 loads reference embeddings for known speakers, computes cosine similarity, and assigns names above threshold — with quality flags if span distribution is skewed.

**Phase 5 embedding extraction is wired and empirically validated (2026-04-22).** See the script in Phase 5. It uses the same embedding model (`pyannote/wespeaker-voxceleb-resnet34-LM`) that `pyannote/speaker-diarization-3.1` uses internally, so cluster vs reference embeddings live in the same space. Extraction fails gracefully if the span is too short or the audio slice errors out. See **Implementation status** at the end of this section for exactly which pieces were executed vs. logic-checked only.

**Where Phase 8 runs (choose one):**

- **On-pod, before destruction (recommended for occasional use).** Deps are already installed and model weights cached. **First transfer the voice-reference files to the pod** — they live in the local vault and are not on the pod otherwise (`scp -i ~/.ssh/id_ed25519 -P PORT "<RESOLVED_REF_DIR>"/*.{m4a,wav} root@IP:/workspace/voice-refs/` after a `mkdir -p`, substituting the literal path the resolver echoed — not `$ref_dir`, which is empty in a new Bash call — or `runpodctl send` over proxy) — and hard-code the script's `ref_dir` to that pod path, else it finds 0 references and silently degrades every cluster to `Speaker N`. Then run the script below on the pod, capture the name map, then destroy. No local env setup needed. This is what validated end-to-end on 2026-04-22.
- **Locally in an existing compatible venv (for repeat runs on old JSONs without a pod).** Verify the actual Python and package versions before using it: this code requires numpy 1.x and pyannote-audio 3.3.2 with the matching torch and huggingface_hub pins in `runpod.md`. Do not recreate it with an unverified system Python or silently upgrade dependencies. If no compatible environment exists, prefer on-pod matching before destruction; otherwise keep `Speaker N` and report the missing optional matcher. Installations remain subject to the package cooldown policy.

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
# 4. ref_dir = "<literal path>"   # hard-code it: the resolver's echoed path when running locally,
#    #                              the pod path (e.g. /workspace/voice-refs) when running on-pod.
#    #                              Do NOT re-derive from VAULT_PATH/VOICE_REF_DIR — those are unset
#    #                              on the pod (ssh doesn't forward env), and the fallback resolves to
#    #                              a non-existent /root/... path, silently yielding {}.
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

**Historical Claude-source validation (not a new Codex runtime test):**

Empirically validated 2026-04-22 against a 46-min 2-speaker recording:
- Pin set (Phase 3 install line) — installed cleanly, all imports resolved, end-to-end run succeeded
- Three Phase 5 code fixes — `Model.from_pretrained()` before `Inference()`, `torch.device("cuda")` not string, WAV conversion before `embed.crop()`
- Core embedding + cosine math — Speaker A cluster 0.9273, Speaker B 0.1349, mis-clustered 0.6718, noise 0.2924

The source reports these as logic-checked only, NOT executed end-to-end in that historical run:
- Skip-existing resume + `manifest.jsonl` per-file status in the Phase 5 script, the input-enumeration-before-model-load reorder, the per-language alignment-model cache, and the inline `LD_LIBRARY_PATH` launch prefix (all added in the 2026-07-19 audit)
- `cluster_span_durations` save + the "save before wav conversion" ordering (added post-validation)
- Phase 8 `assign_names` quality-flag system (suspect/low-confidence/ok) — the 50× ratio heuristic was logic-traced against today's data points but the function itself wasn't run
- Phase 3 verify one-liner in its exact concatenated form (pieces tested individually, not as one command)
- Local venv recipe for Phase 8 (not set up or tested on this laptop)

Caught and fixed 2026-04-27 against a fresh secure-cloud RTX 4090 pod (Linux client):
- HF token transfer (Phase 3 step 2) and `use_auth_token=` plumbing through Phase 5's `DiarizationPipeline` — the 2026-04-22 "validated end-to-end" pod must have had the token cached from a prior session, because a clean pod with no token returns `None` from `Pipeline.from_pretrained` and the 2026-04-22 SETUP_OK check (VAD + wespeaker only, neither gated) couldn't see it.
- Cross-platform token-source documentation (Linux/macOS/Git-Bash bash and Windows PowerShell variants); `huggingface_hub` writes to `~/.cache/huggingface/token` on all three platforms regardless of `XDG_CACHE_HOME`/`LOCALAPPDATA`. Windows-side commands logic-checked, NOT executed end-to-end on Windows.

First real-use of the untested pieces will likely surface minor issues — trust but verify.

