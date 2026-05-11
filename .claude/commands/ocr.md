---
name: ocr
aliases: [screenshot, read-screenshots]
description: Extract text and structured content from image screenshots (chat logs, social-feed posts, documents). Defaults to local easyocr extraction with a text-only Claude post-pass for chat structuring; Vision is used only where image interpretation is required (moments image descriptions) or when explicitly requested.
---

# OCR — Screenshots to Text

Extract text and structured content from one or many screenshots. The default engine is **local easyocr** (no images sent to Vision); a text-only Claude pass handles sender attribution, translation, and dedup for chat content. **Vision** (Claude's multimodal Read) is reserved for `--type=moments` (where image descriptions are part of the output) or when explicitly opted in via `--engine=vision`. This default flips the previous behaviour to avoid Vision's per-image dimension cap (~2000px) and per-batch image-count limits that bite on large screenshot runs.

## When to use

When the user wants structured text extracted from screenshots. Typical triggers: "OCR these screenshots", "pull the text out of this", "process my chat screenshots", a directory path containing screenshots, or a single `.png`/`.jpg` path. The three supported content templates are:

- **chat** — messaging-app conversations (WhatsApp, Signal, iMessage, WeChat, etc.)
- **moments** — social-feed posts with caption + images per post
- **generic** — anything else (documents, receipts, UI screenshots, signage)

## Prerequisites

- `magick` (ImageMagick) — required for preprocessing. Install with `sudo apt install imagemagick` or equivalent.
- `easyocr` CLI — required for the default engine. Install with `pip install --user easyocr` (or pipx). Verify with `command -v easyocr`. First run downloads model weights (~100 MB per language); subsequent runs are offline. CPU-only is fine but slow on large batches; if `python3 -c "import torch; print(torch.cuda.is_available())"` reports `True`, pass `--gpu True` automatically.
- `Pillow` (PIL) — required when `--bubble-colors` is in play (chat-engine sender attribution by bubble background colour). `pip install --user Pillow` if missing. Verify with `python3 -c "from PIL import Image"`. If absent and `--bubble-colors` is requested, fall back to bbox attribution with a one-line warning.
- A multimodal Claude model (only required when `--engine=vision` is selected or `--type=moments` falls through to Vision for image descriptions).

**Engine resolution order at runtime:**

1. If `--engine` is explicit, honour it; if the named engine is missing, stop with an install hint.
2. Otherwise (`--engine=auto`, the default), pick per type:
   - `--type=generic` / `--raw` → easyocr only.
   - `--type=chat` → easyocr extraction → text-only Claude post-pass (no images in context).
   - `--type=moments` → Vision (image descriptions are part of the output template).
3. If the resolved engine's binary is missing, fail with a one-line install instruction.

**Alternative engine (manual, not wired):** `tesseract` is a no-Python fallback if easyocr isn't available. The Debian/Ubuntu Chinese packs are `tesseract-ocr-chi-sim` (Simplified), `tesseract-ocr-chi-tra` (Traditional), and the `-vert` variants for vertical script. Invocation is roughly `tesseract input.jpg - -l chi_sim+eng`. Output quality on phone screenshots is materially worse than easyocr — only reach for it when easyocr can't be installed.

## Arguments

`$ARGUMENTS` — a file path, directory, or glob. If none is provided, ask the user.

Flags (parsed from arguments):

- `--type=chat|moments|generic` — content template. **Default `generic`.** No autodetection — the output formats differ materially, so the user must be explicit for `chat`/`moments`.
- `--engine=auto|easyocr|vision` — extraction engine. **Default `auto`** (resolved per the table in Prerequisites). `easyocr` forces local extraction across all types (image descriptions for moments will be marked unavailable). `vision` forces the legacy Vision path; use when easyocr quality is insufficient (low-resolution scans, unusual scripts) or when a moments run needs the original interpretation pass.
- `--contact=NAME` — used only with `--type=chat`: the name of the non-self participant. If omitted for chat, ask once before Phase 3.
- `--lang=CODE[,CODE…]` — easyocr language codes. Default `en` for English-only sources; for mixed Chinese + English (the common case), pass `--lang=ch_sim,en` (or `ch_tra,en` for Traditional). If omitted and the user's locale/context suggests CJK content, ask once. Ignored when `--engine=vision`.
- `--bubble-colors=me:COLOR,contact:COLOR` — chat-only, easyocr-only. Sender attribution by sampling the bubble background colour behind each OCR'd text bbox, rather than by left/right bbox position. Massively more reliable on messaging apps that don't use strict left/right alignment (WeChat, iMessage when avatars are off, Telegram dark themes). `COLOR` is one of: a named alias (`green`, `white`, `grey`, `blue`, `dark-grey`, `black`), an `#RRGGBB` hex, or `auto` to probe the first preprocessed image. Both sides must be specified. Falls back to bbox attribution with a warning if Pillow is unavailable or sampling fails. **Presets worth remembering** in Notes. If omitted on chat, the bbox heuristic is used (works reasonably for strict left/right layouts; misfires on wide-bubble apps like WeChat).
- `--max-width=N` — explicit override for resize width in px. If omitted, resolve from `--type`: `chat=900`, `moments=600`, `generic=900`. Chat is text-dense and needs a higher width; moments are visual-heavy and tolerate a smaller width.
- `--quality=N` — JPEG quality for preprocessing. Default `85`.
- `--out=PATH` — output file path. If omitted, ask at save time.
- `--no-preprocess` — skip the resize step. Valid when every source file is already under the Read-hook threshold (Vision path) or when easyocr can read the originals directly (easyocr is largely indifferent to file size; preprocessing mostly helps it run faster).
- `--preprocess-only` — stop after Phase 2. Emit the resized-dir path and exit; skip Phases 3–5 entirely. Intended for use by other skills that delegate preprocessing to `/ocr` but handle extraction themselves (e.g. `/tinder`). Not interactive in this mode.
- `--no-translate` — skip translation for non-English text. By default the easyocr → Claude post-pass adds translations for chat; Vision adds them inline per its existing rules.
- `--raw` — valid only with `--type=generic`. Dump visible text verbatim with no translation and no layout structuring. Under easyocr this is the natural `--detail 0 --paragraph True` output; under Vision this disables the interpretation layer. If passed with chat/moments, warn and ignore.

## Workflow

### Phase 1: Validate

1. Resolve `$ARGUMENTS` to a sorted list of image files matching extensions `.png .jpg .jpeg .webp .heic .heif` (case-insensitive). Sort by filename — phone screenshots are typically timestamp-encoded (e.g. `Screenshot_20260417-153045.png`). Fall back to mtime if filenames don't sort meaningfully.
2. If zero images match, stop and tell the user.
3. If `--type=chat` and `--contact` is absent, ask the user for the contact name now (before preprocessing).
4. If more than ~25 images, warn the user that a single-turn batch read may exceed the context budget. Suggest splitting into chunks of ≤25.
5. Check the Read-hook threshold. Read `~/.claude/hooks/check-file-size.sh` (or the project-local equivalent) to determine the current byte limit; if the hook is absent, assume 200 KB. Check each source file's size. If any exceed the threshold, preprocessing is required — unless `--no-preprocess` is passed, in which case stop with a message naming the offender.

### Phase 2: Preprocess

Skip this phase entirely if `--no-preprocess` was passed and every source file is already under the threshold.

1. Compute `DST="<source>/_ocr_resized"` (underscore prefix avoids collision with any user-created `resized/`). `mkdir -p "$DST"`.
2. Resolve `WIDTH` from `--max-width` or the type-based default. Resolve `Q` from `--quality` (default 85).
3. Run mogrify per extension (to avoid brace-expansion and nullglob pitfalls). The skill emits something like:
   ```bash
   SRC="<source directory>"
   DST="$SRC/_ocr_resized"
   WIDTH=900
   Q=85
   mkdir -p "$DST"
   shopt -s nullglob nocaseglob
   for ext in png jpg jpeg webp heic heif; do
     files=("$SRC"/*."$ext")
     if [ ${#files[@]} -gt 0 ]; then
       magick mogrify -path "$DST" -resize "${WIDTH}x" -quality "$Q" -format jpg "${files[@]}"
     fi
   done
   shopt -u nullglob nocaseglob
   ```
4. Verify every file in `$DST` is under the Read-hook threshold (`stat -c%s`). For any that remain over, re-run `magick` on that single file with progressively smaller widths: 720 → 640 → 512 → 448. Stop when it fits.
5. Report briefly: `"N files, source avg X MB → resized avg Y KB, width Wpx, quality Q."`
6. **If `--preprocess-only`, stop here.** Emit one final line — `"Preprocessed → <absolute DST path>"` — and end the skill. No Vision read, no transcript, no interactive prompt. Callers (e.g. `/tinder`) consume the DST path and handle extraction themselves.

### Phase 3: Extract

Resolve the engine per the Prerequisites table. The branches:

#### 3a. Engine = easyocr

For each preprocessed image, run easyocr and persist a sidecar JSON next to the image:

```bash
easyocr -l <lang-csv> -f "$img" --detail 1 --paragraph False \
        --gpu "$GPU" > "${img%.*}.ocr.json"
```

- `--detail 1` returns per-line `[bbox, text, confidence]`. We need bboxes for chat sender-side heuristics.
- `--paragraph False` keeps lines discrete so the post-pass can group on its own terms.
- `$GPU` is `True` if CUDA was detected at startup, else `False`.

Build the assembled text:

- **generic** — concatenate lines top-to-bottom by bbox y-centre. If `--raw`, emit verbatim with no further processing. Otherwise the optional Claude post-pass (text-only, no images in context) adds inline translation in parentheses unless `--no-translate`.
- **chat** — group lines into messages using one of two sender-attribution heuristics:
  - **bubble-colour (preferred when `--bubble-colors=` is passed)**: for each OCR text bbox, sample pixels inside the bbox using Pillow, filter out dark text pixels (channels all < 130), and average the remainder = bubble background colour. Classify by colour distance against the two declared colours. Resolve named aliases (`green` → `(95, 180, 80)`-ish range, `white` → `(248-255, 248-255, 248-255)`, etc.) and hex into RGB triples first. `auto` mode samples a known text-bbox region from screenshot 1 and asks the user to confirm "is this Me (green-ish) or Contact (white-ish)?" before locking in.
  - **bbox left-edge fallback (default)**: lines whose bbox left-edge ≤ ~220px on a 900px-wide resized image are attributed to `--contact`; lines whose right-edge ≥ ~680px are "Me"; ambiguous lines fall into a centre band (timestamps, system messages, date dividers) and become italicised placeholders.
  Then run a text-only Claude post-pass to: stitch wrapped lines into messages, regex-extract `HH:MM` timestamps, add translations, and dedup across screenshots (using the same algorithm as the Vision path, but operating on extracted text instead of re-reading images). The post-pass receives only the assembled text blob, never the images — this is what sidesteps Vision's image limits.
- **moments** — easyocr extracts caption text only. Image descriptions are marked `**Images:** N (descriptions unavailable in easyocr engine — re-run with --engine=vision for per-image descriptions)`. If the user actually needs descriptions, recommend re-running with `--engine=vision` on a chunked subset rather than synthesising fake descriptions.

Confidence floor: if the median easyocr confidence across the batch is below `0.5`, surface a one-line warning before the transcript and suggest `--engine=vision` for affected files. Don't auto-fall-back — the user should make the trade explicitly.

#### 3b. Engine = vision

**Batch-load strategy.** Read *all* preprocessed images in a single turn — issue one Read call per image in parallel within one assistant turn. Then emit the full transcript in the following turn. This makes cross-screenshot dedup a single inference pass rather than stateful bookkeeping across multiple turns. Only chunk if Phase 1 step 4 warned about context budget. Note: Vision currently rejects images with any dimension >2000px and may reject batches above its rolling per-batch image count — preprocessing should keep widths well under that, but if a run loops on a dimension error, abort and re-run with `--engine=easyocr` rather than retry/compact.

Output template depends on `--type`:

**chat** — block format per message:

```
**<Sender>** [HH:MM]
<original text>
*<translation, if non-English>*
```

Rules:
- **Sender resolution hierarchy:** (a) a visible name label in the screenshot (common in group chats) → (b) position heuristic (sender-side/right-aligned bubbles → "Me"; received/left-aligned → the `--contact` name) → (c) `--contact` + "Me" as the final fallback.
- `[HH:MM]` timestamp is included **only when visible in the screenshot**. Most messaging apps only render timestamps on gap-triggered messages; omit the timestamp field for messages that don't have one.
- Media placeholders use brackets: `[sticker: smiling cat]`, `[voice message, 0:12]`, `[photo]`, `[video]`, `[file: filename.pdf]`, `[location]`, `[contact card]`.
- Translation lines use italics. Skip the translation line if text is already in the target language or if `--no-translate` is passed.
- **Dedup algorithm (overlap between consecutive screenshots).** Scrolling screenshots usually share the last 1–2 messages of the previous screenshot. Compare the last 3 messages of screenshot K with the first 3 of K+1. A message matches if `(sender, timestamp-if-present, text)` are identical. Drop any exact-match prefix from K+1. If timestamps are absent and the text is short (<10 chars, e.g. an emoji reaction), require `(sender, text)` match. Record the number of duplicates dropped in the output metadata.

**moments** — block per post:

```
## Post <N> — <date if visible>
**Caption:** <original>
*<translation if non-English>*
**Location:** <if visible>
**Images:** <count>
1. <description of image 1>
2. <description of image 2>
...

**Signal:** <1–2 sentences on what this post reveals: context, activity, social cues, named entities>
```

Post boundaries are detected from visible feed-UI separators (horizontal rules, author/timestamp headers). A single post may span multiple screenshots when it has many images.

**generic** — transcribe visible text preserving rough layout. Non-English gets inline translation in parentheses unless `--no-translate` is passed. If `--raw` is passed, skip translation and skip interpretation — text-only, one block per visible text region.

### Phase 4: Assemble and display

1. Compose the full transcript with a metadata header:

   ```markdown
   # <type> extract — <YYYY-MM-DD>

   **Source:** `<source path>`
   **Screenshots:** <N>
   **Date processed:** <YYYY-MM-DD>
   **Type:** <chat|moments|generic>
   **Engine:** <easyocr|vision>   (lang: <codes>, median confidence: <C>) — easyocr only
   **Preprocessing:** resized to <W>px @ quality <Q> → avg <X> KB
   **Duplicates dropped:** <N>   (chat only)

   ---

   <extracted content>
   ```

2. Display the transcript to the user.
3. Ask what they want to do next:
   1. **Save** — ask where (propose a default based on type + source location) and the filename.
   2. **Discuss** — summarise, extract action items, answer questions, pull quotes.
   3. **Both** — save first, then discuss.

   Wait for the user's response before proceeding.

4. On save: write the markdown file at the agreed path. Do not auto-append to user-curated files unless they explicitly ask — chat-log extracts in particular should land in their own dated file, not merged into a curated log.

### Phase 5: Optional discussion

Whatever the user asked for in Phase 4 — summary, action items, Q&A, pattern spotting.

## Notes

- **Bubble-colour calibration.** Before locking in `--bubble-colors`, sample the actual pixel values on one preprocessed screenshot at a known sender region and a known contact region — messaging apps drift their palettes across versions and themes, and named aliases are starting points, not ground truth. If the two sides are too close in colour space to discriminate cleanly (e.g. both white in some chat apps without theme contrast), fall back to bbox attribution.
- easyocr handles Chinese (`ch_sim`, `ch_tra`), Japanese (`ja`), Korean (`ko`), Cyrillic, Arabic, and ~80 other scripts; pass them as a CSV via `--lang`. Vision handles the same set without language flags. Tesseract requires per-language packages (see Prerequisites).
- The easyocr default exists because Vision has hard per-image dimension and per-batch count limits that compaction does not clear. If a Vision run hits "image exceeds the dimension limit" or refuses to read the batch, do not /compact and retry — end the session and re-run with `--engine=easyocr`.
- Preprocessing is a workaround for the Read-hook byte threshold and Vision's dimension cap. easyocr is largely indifferent to file size, but resizing still helps it run faster on CPU. If the host environment's hook exempts images, `--no-preprocess` is safe.
- For batches above ~25 images on the Vision path, prefer splitting into chunks. easyocr scales linearly on CPU without an upper bound; the practical limit is wall-clock time.
- Dedup is intentionally conservative — exact-match only. If consecutive screenshots have overlapping content that isn't bit-identical (slight crop shift, different timestamp formatting), the dedup won't merge them and the operator must clean up manually.
- This skill doesn't wire tesseract or PaddleOCR. If a verifiable text layer for archival is ever required, add a parallel engine flag and merge its output into the metadata header rather than the transcript body — don't blend engines mid-transcript.
