---
name: ocr
aliases: [screenshot, read-screenshots]
description: Extract text and structured content from image screenshots (chat logs, social-feed posts, documents) via Claude Vision, with ImageMagick preprocessing to stay under the Read-hook file-size threshold.
---

# OCR — Screenshots to Text

Extract text and structured content from one or many screenshots via Claude's multimodal Read, with ImageMagick preprocessing to keep resized images under the Read-hook file-size threshold. No separate OCR engine — Vision handles mixed-language content (e.g. Chinese + English), stickers, and visual context in one pass.

## When to use

When the user wants structured text extracted from screenshots. Typical triggers: "OCR these screenshots", "pull the text out of this", "process my chat screenshots", a directory path containing screenshots, or a single `.png`/`.jpg` path. The three supported content templates are:

- **chat** — messaging-app conversations (WhatsApp, Signal, iMessage, WeChat, etc.)
- **moments** — social-feed posts with caption + images per post
- **generic** — anything else (documents, receipts, UI screenshots, signage)

## Prerequisites

- `magick` (ImageMagick) — required for preprocessing. Install with `sudo apt install imagemagick` or equivalent.
- A multimodal Claude model (Claude Code's default Read tool reads images natively when run on a vision-capable model).

If `magick` is missing, tell the user what to install and stop.

## Arguments

`$ARGUMENTS` — a file path, directory, or glob. If none is provided, ask the user.

Flags (parsed from arguments):

- `--type=chat|moments|generic` — content template. **Default `generic`.** No autodetection — the output formats differ materially, so the user must be explicit for `chat`/`moments`.
- `--contact=NAME` — used only with `--type=chat`: the name of the non-self participant. If omitted for chat, ask once before Phase 3.
- `--max-width=N` — explicit override for resize width in px. If omitted, resolve from `--type`: `chat=900`, `moments=600`, `generic=900`. Chat is text-dense and needs a higher width; moments are visual-heavy and tolerate a smaller width.
- `--quality=N` — JPEG quality for preprocessing. Default `85`.
- `--out=PATH` — output file path. If omitted, ask at save time.
- `--no-preprocess` — skip the resize step. Only valid when every source file is already under the Read-hook threshold.
- `--preprocess-only` — stop after Phase 2. Emit the resized-dir path and exit; skip Phases 3–5 entirely. Intended for use by other skills that delegate preprocessing to `/ocr` but handle Vision extraction themselves (e.g. `/tinder`). Not interactive in this mode.
- `--no-translate` — skip inline translation for non-English text.
- `--raw` — valid only with `--type=generic`. Dump visible text verbatim with no translation and no layout structuring. If passed with chat/moments, warn and ignore — Vision is already the interpretation layer for those, so "raw" is meaningless.

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

### Phase 3: Extract via Vision

**Batch-load strategy.** Read *all* preprocessed images in a single turn — issue one Read call per image in parallel within one assistant turn. Then emit the full transcript in the following turn. This makes cross-screenshot dedup a single inference pass rather than stateful bookkeeping across multiple turns. Only chunk if Phase 1 step 4 warned about context budget.

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

- Vision handles Chinese, Japanese, Korean, Arabic, Cyrillic, and other non-Latin scripts natively. No additional language packs required (unlike tesseract).
- Preprocessing is a workaround for a Read-hook byte threshold — the hook is a text-context guard that happens to apply to images. If the host environment's hook exempts images or has a higher image threshold, `--no-preprocess` is safe to use.
- For batches above ~25 images, prefer splitting into chunks. The Vision model handles many images per turn, but total context grows linearly.
- Dedup is intentionally conservative — exact-match only. If consecutive screenshots have overlapping content that isn't bit-identical (slight crop shift, different timestamp formatting), the dedup won't merge them and the operator must clean up manually.
- This skill doesn't run a separate OCR engine (tesseract, PaddleOCR, etc.). Those are useful when you need a verifiable text layer for search or archival — if that becomes a requirement, add a parallel `--engine=tesseract` flag and merge its output into the metadata header rather than the transcript body.
