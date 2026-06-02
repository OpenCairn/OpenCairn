---
name: ocr-hand
aliases: [handwriting, transcribe-handwriting]
description: Transcribe handwritten pages (scanned PDFs or photos) using multi-model vision consensus — preprocess, run Claude + Gemini + GPT in parallel, merge by word-level alignment, flag disagreements for review.
---

# OCR-Hand — Handwriting Transcription

Transcribe handwritten pages from scanned PDFs or photographs. Uses OpenCV preprocessing and multi-model vision consensus (Claude, Gemini, GPT) to push accuracy beyond what any single model achieves alone. Models make different errors on cursive handwriting — word-level alignment across their outputs surfaces disagreements for human review while auto-resolving the majority.

## When to use

When the user has handwritten notes (scanned PDFs, photos of notebooks/journals) and wants them transcribed to text. Typical triggers: "transcribe my handwriting", "OCR these journal pages", "read my notes", a path to a scanned PDF.

Not for printed text, screenshots, or typed documents — use `/ocr` for those.

## Prerequisites

- `pdftoppm` (poppler-utils) — PDF page extraction. `sudo apt install poppler-utils`.
- `convert` (ImageMagick) — image resizing/compression.
- Python 3 with OpenCV (`pip install opencv-python-headless`) — preprocessing.
- `gemini` CLI — second model. Verify with `gemini --version`.
- `codex` CLI — third model. Verify with `codex --version`.
- If a CLI can't handle image input via its tool layer, fall back to the corresponding Python SDK (`pip install google-genai` or `pip install openai`) with a small Python script calling the vision API directly.

## Instructions

### Phase 0: Input discovery

1. The user provides one or more file paths. Accept PDFs (scanned) or image files (PNG, JPG).
2. Count pages: for PDFs, run `pdfinfo <file> | grep Pages`. Report total page count to the user.
3. **Cost estimation.** Before confirming, calculate expected cost: `pages × models × ~cost-per-vision-call`. Report to the user: "N pages × 3 models = ~M vision calls. Estimated cost: ~$X. Proceed?" Adjust model count if a CLI fallback means fewer models are available.
4. If total pages > 20, warn about wall-clock time and confirm before proceeding.

### Phase 1: Extract & preprocess

1. **Determine the Read-hook threshold.** Read `~/.claude/hooks/check-file-size.sh` (or project-local equivalent) to find the actual byte limit. If the hook is absent, assume **200KB** (the hook's real limit is 204800 bytes). Don't hardcode — the threshold may change.

2. **Extract pages from PDFs** as PNG:
   ```
   pdftoppm -png -r 300 "<input.pdf>" "<output-dir>/page"
   ```
   For image files, skip extraction — copy to the output dir directly.

3. **Assess each page** before preprocessing. Not all pages need enhancement — aggressive binarisation on a clean scan destroys thin strokes. Per page, check mean brightness and contrast (OpenCV `cv2.meanStdDev`):
   - Low contrast (stddev < 40) or low brightness (mean < 100): apply CLAHE + adaptive binarisation (Sauvola).
   - Skew detected (Hough transform, > 2 degrees): deskew.
   - Otherwise: resize only.

4. **Resize and compress** to sit comfortably under the Read-hook threshold (~200KB). Higher resolution improves OCR accuracy, so spend the headroom — don't undershoot to 80KB:
   ```
   convert "<page>.png" -resize 1000x1400 -quality 72 "<page>_ready.jpg"   # ~90–110KB, well under 200KB
   ```
   Verify each output (`stat -c%s`); for any over ~190KB, progressively shrink width 900→800→720→640, stopping when it fits. Width reduction preserves legibility better than dropping quality.

5. Output: a directory of preprocessed JPGs, one per page. Report: `"N pages, source avg X MB → resized avg Y KB, width Wpx."`

### Phase 2: Multi-model transcription

**Re-use existing helpers first.** Tuned reference scripts live in `~/.claude/scripts/ocr-hand/`: `gemini_ocr.py` (Gemini REST OCR) and `merge_ocr.py` (word-level 3-model merge). Prefer running these over re-deriving.

Run the **selected** models (per the sensitivity gate below) concurrently per page. Write the transcription prompt once to a scratch file; each model gets the same prompt text — Gemini receives it alongside the inline image, Claude and Codex receive it pointing at the staged image path. Keep the prompt text identical across models — framing asymmetry defeats consensus.

**Transcription prompt** (save to `mktemp -t ocr-hand-prompt.XXXXXX.md`):
```
Transcribe this handwritten page exactly as written. Preserve the author's line breaks and structure.

Rules:
- Mark any word you are uncertain about with [?] immediately after the word.
- Use bullet points (- ) where the original uses dashes, dots, or bullet markers.
- Preserve abbreviations, crossed-out text (use ~~strikethrough~~), and underlines (**bold**).
- If a word is completely illegible, write [illegible].
- Do not add interpretation, summaries, or corrections. Transcribe what is written.
```

**⛔ Sensitivity gate — choose the model set BEFORE despatch.** Multi-model consensus sends every page to external providers (Gemini → Google, Codex → OpenAI) on top of Anthropic. Assess the content first:
- **Innocuous** (lists, logistics, study notes, errands) → full panel (Claude + Gemini + Codex).
- **Intimate / sensitive** (private journaling, health, distress, named third parties, anything the author would not want sitting on a third-party API) → **Claude-only.** No external providers. Accept the higher manual-review rate as the privacy cost — `[?]` markers become the review mechanism instead of cross-model flags.
- **Mixed source** (e.g. a notebook with both to-do pages and personal entries) → classify per page; don't let one default carry sensitive pages to external APIs.
- **When unsure, ask the user before sending anything externally.** Don't infer consent from an earlier OK on innocuous pages.

**Despatch — the selected models, concurrently per page:**

1. **Claude** via Agent tool (`subagent_type: general-purpose`) — the agent reads the preprocessed image via Read and returns the transcription. Proven on handwriting at <200KB (the Read-hook limit). For the **Claude-only** path, the running instance can also transcribe inline (cheaper than spawning agents) for small batches; use agents/Workflow for large batches to keep context manageable.

2. **Gemini** — **do NOT use the `gemini` CLI for images.** It sandboxes file paths to `~` and refuses handwriting OCR (`_shared-rules.md` §10). Call the REST API with inline base64 via Python stdlib — no SDK install. `GEMINI_API_KEY` lives in env + `~/.gemini/.env`. Reference impl `gemini_ocr.py`:
   ```
   # gemini_ocr.py <image> <prompt_file> [model=gemini-2.5-flash]
   # POST generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=$GEMINI_API_KEY
   # body {contents:[{parts:[{text:<prompt>},{inline_data:{mime_type:"image/jpeg",data:<b64>}}]}], generationConfig:{temperature:0}}
   # print candidates[0].content.parts[0].text   (urllib, no deps)
   ```
   `gemini-2.5-flash` is accurate and cheap for handwriting; reserve `gemini-2.5-pro` for pages Flash struggles on.

3. **GPT (Codex)** — works directly via the CLI (`timeout: 300000`); pipe a prompt that names the absolute image path:
   ```
   cat <prompt-path> | codex exec --sandbox read-only --skip-git-repo-check -
   ```
   where the prompt says "Read the image at <abs-path> and transcribe…". Codex reads images fine (unlike Gemini's CLI). SDK fallback only if the CLI is unavailable: `openai` chat with a base64 `image_url` part.

**Fallback model count:** Two models still give useful consensus (2-agree = confident, disagree = flag). One model (incl. the Claude-only privacy path) → deliver single-model output with `[?]` markers as the review mechanism; skip the alignment step.

**Batch parallelisation:** For >10 pages, use a Workflow to run multiple pages concurrently (up to ~10-16 parallel agents). Don't process 85 pages sequentially.

**Progress reporting:** Emit `[page N/M] source.pdf p3 — Claude ✓ Gemini ✓ GPT ✓` as each page completes. On large batches, also report running stats: elapsed time, pages/min, estimated time remaining.

**Manifest for resumability.** Before starting the batch, write a manifest JSON to the output directory listing every page and its status:
```json
{"page": 1, "source": "journal.pdf", "preprocessed": true, "claude": "done", "gemini": "done", "gpt": "done", "merged": true}
{"page": 2, "source": "journal.pdf", "preprocessed": true, "claude": "done", "gemini": null, "gpt": null, "merged": false}
```
One JSON object per line (JSONL). Update after each step completes. If the run crashes at page 40, the next invocation reads the manifest and resumes from the first incomplete page. Don't reprocess pages already marked done.

**Error salvage per page.** If a model fails on a specific page (timeout, API error, garbled output), log the failure in the manifest and continue. A page with only 2 model outputs still merges usefully. A page with only 1 model output gets delivered with `[?]` markers. Don't block the entire batch on one page's failure.

### Phase 3: Alignment & merge

**This is the hardest part of the pipeline. Prototype on one page before scaling.**

Word-level alignment, not line-level (models break lines differently, disagree on bullets vs dashes, capitalise inconsistently):

1. **Pick a structural template.** Use one model's output (default: Claude) as the line-break and structure template. The other models contribute word-level corrections, not structural alternatives.

2. **Tokenise** each transcription into word sequences, normalising:
   - Strip leading/trailing punctuation per word.
   - Lowercase for comparison (preserve original case in output).
   - Collapse whitespace.

3. **Align word sequences** across models using `difflib.SequenceMatcher` on word lists (or Levenshtein-based alignment for robustness to insertions/deletions).

4. **Per-word voting:**
   - All models agree → emit as-is (high confidence).
   - 2 of 3 agree → emit majority spelling, no marker.
   - All disagree → emit Claude's version with `[REVIEW: Gemini="X" GPT="Y"]` inline.
   - Word present in one model but missing in others → flag `[REVIEW: only in Claude]`.

5. **Reconstruct** the merged text using the structural template's line breaks, with voted words substituted in.

6. **Output** per page: merged markdown with inline confidence markers.

### Phase 4: Concatenate & deliver

1. Compose the full transcript with a metadata header:

   ```markdown
   # Handwriting transcription — <YYYY-MM-DD>

   **Source:** `<source path(s)>`
   **Pages:** <N>
   **Date processed:** <YYYY-MM-DD>
   **Models:** <Claude, Gemini, GPT — list only those that produced output>
   **Preprocessing:** resized to <W>px, adaptive enhancement on <N> pages
   **Total words:** ~<N>
   **High confidence:** <X>%
   **Flagged [REVIEW]:** <X>%

   ---

   --- Page 1 (<source filename>) ---
   [merged transcription]

   --- Page 2 (<source filename>) ---
   [merged transcription]
   ...
   ```

2. Save to the same directory as the source PDFs unless the user specifies otherwise.

3. Tell the user: search for `[REVIEW]` to find the lines that need manual checking against the originals.

### Phase 5: Skill refinement

After the first real run, note what worked and what didn't:
- Did preprocessing help or hurt specific page types?
- Which model was most accurate on this handwriting?
- Did the alignment script produce clean merges or noisy ones?
- What was the actual `[REVIEW]` rate?

Update this skill with findings.

## Guidelines

- **Test on one page first.** Always run the full pipeline on a single page before batching. Compare merged output against single-model output to verify the consensus approach is adding value.
- **Don't over-preprocess.** Clean scans need only resizing. Aggressive binarisation on good input destroys thin pen strokes. The Phase 1 assessment step exists for this reason.
- **The merge script is the fragile part.** If word-level alignment produces too much noise on the test page, simplify: use Claude as primary with `[?]` markers, and only consult other models for the `[?]` words (targeted second opinion rather than full-page consensus).
- **Single-author handwriting is consistent.** After a few pages, the models will learn the author's letterforms from context. Later pages may be more accurate than earlier ones.
- **Preserve the original scans.** Never modify or delete the source PDFs/images. All work happens on extracted copies.
