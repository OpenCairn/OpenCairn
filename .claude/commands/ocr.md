---
name: ocr
description: Extract text and structured content from image screenshots (chat logs, social-feed posts, documents). Defaults to local easyocr extraction with a text-only Claude post-pass for chat structuring; Vision is used only where image interpretation is required (moments image descriptions) or when explicitly requested.
---

# OCR — Screenshots to Text

Extract text and structured content from one or many screenshots. The default engine is **local easyocr** (no images sent to Vision); a text-only Claude pass handles sender attribution, translation, and dedup for chat content. **Vision** (Claude's multimodal Read) is reserved for `--type=moments` (where image descriptions are part of the output) or when explicitly opted in via `--engine=vision`. This default flips the previous behaviour to avoid Vision's per-image dimension cap (~2000px) and per-batch image-count limits that bite on large screenshot runs.

## When to use

When the user wants structured text extracted from screenshots. Typical triggers: "OCR these screenshots", "pull the text out of this", "process my chat screenshots", a directory path containing screenshots, or a single `.png`/`.jpg` path. The three supported content templates are:

- **chat** — messaging-app conversations (WhatsApp, Signal, iMessage, WeChat, etc.)
- **moments** — social-feed posts with caption + images per post
- **generic** — anything else (documents, receipts, UI screenshots, signage)

The skill also has a **live-capture mode** (`--capture=adb`) for when the user wants a long chat scraped directly off an Android phone over USB instead of supplying pre-existing screenshots. Triggers: "OCR the conversation with X on my phone", "scrape this thread", "scroll through and capture the whole chat". See Phase 0 for the capture workflow. Live capture requires the phone to be connected, authorised for ADB, and already on the target screen — the skill doesn't navigate the app for you.

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

`$ARGUMENTS` — a file path, directory, or glob. If none is provided, ask the user. **When `--capture=adb` is passed, this argument is interpreted as the OUTPUT directory for new captures, not an existing input source — see the live-capture flags below.**

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

**Live-capture flags (only meaningful with `--capture=adb`):**

- `--capture=adb` — drive an attached Android device to capture screenshots from its foreground app before running the OCR pipeline. The first positional argument is treated as the OUTPUT directory for captures (created if missing) rather than an input path. Prefer a path outside any synced vault/repo (e.g. `~/tmp/<name>/`) — raw screencaps are ~2 MB each on modern phones and accumulate fast.
- `--device=ID` — ADB device serial. If omitted and exactly one authorised device is connected, pick it; if multiple, stop and require explicit selection.
- `--swipe-delta=N` — vertical scroll per gesture in native pixels (default ≈ 50% of detected screen height). Values that would push the swipe end-point above the top crop boundary (~12% of screen height) are clamped silently; if your delta needs to exceed `y_high − 12% of height`, raise `y_high` instead. The capture loop emits a one-line stderr warning the first time the clamp fires.
- `--swipe-duration=MS` — gesture duration in milliseconds (default 700). Slower = less kinetic carry; fast flicks below ~400 ms overshoot and skip content even at the same delta.
- `--swipe-sleep=S` — settle delay after each swipe in seconds (default 1.8). Allows momentum to dissipate AND gives the app time to lazy-load newly visible content.
- `--max-frames=N` — hard cap on capture iterations (default 80). Long chats may need 200+; raise as needed.
- `--no-smoke-test` — skip the 3-frame calibration step. Don't use on first runs against a new app/theme — params calibrated on one device/app rarely transfer cleanly.

**Flag-to-shell-variable convention for the bash snippets below:** hyphens become underscores, the `--` prefix is dropped. `--swipe-delta=900` → `$swipe_delta=900`, `--max-frames=120` → `$max_frames=120`, etc.

**Composition with `--preprocess-only`:** `--capture=adb --preprocess-only` runs Phase 0 (capture) + Phase 2 (mogrify resize) then exits, emitting the resized-dir path. Phases 3–5 are skipped. Useful for delegator skills that want fresh captures but handle OCR themselves.

## Workflow

### Phase 0: Live capture (only when `--capture=adb`)

Skip entirely if `--capture=adb` is not set; proceed to Phase 1 with `$ARGUMENTS` as an existing screenshot path/directory.

Drive an attached Android device to produce screenshots from its foreground app, alternating screencap and swipe-up gestures until end-of-content is detected. The first positional argument is the OUTPUT directory for captures.

**Android only.** ADB is an Android tool. There is no equivalent path for iOS — iOS users must capture screenshots manually on the phone and supply them as an existing directory (the rest of Phases 1–5 still work). The skill has no iPhone-detection logic; if the user describes their device as an iPhone, route them to manual capture immediately rather than running pre-flight (`adb devices` will return empty and Phase 0a will fail with no useful diagnostic).

#### 0a. Pre-flight

1. **ADB present:** `command -v adb` or stop with install hint.
2. **Single authorised device:** `adb devices` → expect exactly one line ending in `device`. If `unauthorized`, ask the user to confirm the ADB prompt on the phone. If multiple authorised devices, require `--device=ID` and list candidates.
3. **Device awake, not dozing:** `adb -s $DEV shell dumpsys power | grep mWakefulness` must report `Awake`. If `Dozing`/`Asleep`, send `KEYCODE_POWER` and re-check. If the phone is locked behind a PIN/biometric, ADB cannot unlock — stop and ask the user to unlock and bring the app to foreground.
4. **Foreground app matches expectation:** `adb -s $DEV shell dumpsys window | grep mCurrentFocus` should contain the package the user is scraping. **Don't navigate the app via ADB** — that risks destroying the user's current scroll position. If focus reports `NotificationShade` or similar (often from prior keystrokes), send `KEYCODE_BACK` to dismiss. If that fails to recover, ask the user to fix state manually rather than guessing. Note also that activity names like `LauncherUI` may host the chat view as a sub-window — don't rely on activity name alone to mean "wrong screen"; check with the user if uncertain.
5. **Screen dimensions:** `adb -s $DEV shell wm size` → parse `<width>x<height>` (e.g. `1080x2410`). Use these to scale swipe coordinates; never hardcode.

#### 0b. Smoke test (3 captures, then **STOP and ask the user**)

Run the loop in 0d for exactly 3 iterations with no termination check. **This phase is not self-verifying — present the measurements below to the user and wait for their decision before proceeding to the full sweep.** Do not advance autonomously even if the numbers look fine to you; today's calibration loops in real sessions have routinely needed 2–3 user-driven tuning rounds.

1. **Frame 001 spot check:** is the app on the expected screen? Scrolled where the user said it was?
2. **Swipe advance measurement.** Concrete recipe:
   - Run Phase 2 preprocessing (`magick mogrify -resize 900x -quality 85 -format jpg`) on just frames 001–003 into a temp dir.
   - Read each resized jpg via Claude Vision (the resized files are typically ~100–200 KB and clear the Read hook).
   - Pick a visual landmark visible in both frame 001 and frame 002 — a date divider, a distinctive bubble, an image preview. Note the y-pixel position of the landmark in each (the displayed image dimensions are reported by the Read tool).
   - Compute displayed-delta = y(frame 001) − y(frame 002). Scale to native: `native_advance = displayed_delta × native_height / resized_height` (e.g. for a 900×2008 resize of a 1080×2410 source: multiply by 2410/2008 ≈ 1.20).
   - Aim for **40–60% of usable screen height** (screen height minus status bar minus app header minus compose bar — roughly `height × 0.71` on a typical Android phone). Below ~30% wastes captures and operator time; above ~70% risks skipping content.
3. **Bubble palette sanity (for `--type=chat`).** Sample background pixels in known sender/contact regions on frame 001 with `magick "$frame" -crop 1x1+X+Y txt:- | tail -1`. Compare against the `--bubble-colors` named-alias defaults. **Also sample a known-background pixel (interior of conversation area away from any bubble) to detect theme: values in `#E0–F0` → light theme; `#10–20` → dark theme.** If divergent from named aliases (app theme variant, version drift), override with hex on the full-run invocation (e.g. `--bubble-colors=me:#9EEA6A,contact:#FFFFFF`).
4. **Optional preview OCR pass on the 3 smoke frames.** Validates end-to-end OCR quality, sender attribution direction, and translation post-pass before committing to the full sweep. Cost: tens of seconds on CPU easyocr.
5. **Present and wait.** Report the measured advance (as native px and as % of usable height), the sampled palette and detected theme, and whether the preview OCR (if run) looks sane. Ask the user: continue with current params, or tune `--swipe-delta` / `--swipe-duration` / `--swipe-sleep` and re-run the smoke test? Do not interpret silence as approval.

If anything is off, tune and re-run the smoke test. Cheaper to iterate at 3 frames than 30.

#### 0c. Swipe geometry

- **Direction:** swipe from a `y_high` near the bottom of the conversation area to a `y_low` near the top. This scrolls the view *downward* — newer content appears at the bottom. For most messaging apps, capturing a thread from oldest to newest means starting at the top of history and scrolling forward.
- **Delta:** vertical pixel distance between `y_high` and `y_low`, default ≈ 50% of screen height. Larger delta = fewer captures needed but higher overshoot risk.
- **Duration:** **700 ms or more.** A fast flick (≤400 ms) at the *same* delta induces kinetic carry that visibly overshoots intended content, dropping messages. Slow gestures stick to the input delta. This is the single most common cause of skipped-content runs.
- **Sleep after:** 1.8 s default. Allows momentum to settle AND gives the app time to lazy-load newly visible content (which may shift layout if it pops in late). Drop below 1.5 s only with confidence the app finishes layout quickly.
- **Native coordinates:** ADB input uses native pixels (from `wm size`). Don't confuse with any resized-preview width used elsewhere in the skill.

#### 0d. Capture loop with cropped-md5 termination

```bash
DEV="$device"                       # from --device or auto-picked
DST="$capture_dir"                  # first positional arg under --capture=adb
mkdir -p "$DST"

# 1. Derive screen dimensions (don't hardcode)
SIZE=$(adb -s "$DEV" shell wm size | grep -oE '[0-9]+x[0-9]+' | head -1)
width="${SIZE%x*}"
height="${SIZE#*x}"

# 2. Swipe geometry from flags (with defaults)
swipe_delta="${swipe_delta:-$((height / 2))}"        # default ~50% of screen height
swipe_duration="${swipe_duration:-700}"              # ms; ≥700 keeps kinetic carry low
swipe_sleep="${swipe_sleep:-1.8}"                    # seconds settle time
y_high=$(( height * 79 / 100 ))                      # start ~79% down (above compose bar)
y_low=$(( y_high - swipe_delta ))
y_floor=$(( height * 12 / 100 ))
if [ "$y_low" -lt "$y_floor" ]; then
  echo "warning: --swipe-delta=$swipe_delta exceeds usable scroll range; clamping y_low to $y_floor (effective delta: $((y_high - y_floor)))" >&2
  y_low=$y_floor
fi

# 3. Crop bounds for termination hash — fractions of screen height, not absolute px,
#    so it scales across phones/tablets. Drop top ~12% (status bar + app header,
#    which contain time-varying elements) and bottom ~17% (compose bar).
CROP_W=$width
CROP_Y=$(( height * 12 / 100 ))
CROP_H=$(( height * 71 / 100 ))

n=0
prev_hash=""
MAX_ITER="${max_frames:-80}"

while [ "$n" -lt "$MAX_ITER" ]; do
  n=$((n+1))
  printf -v i "%03d" "$n"
  out="$DST/frame_$i.png"
  adb -s "$DEV" exec-out screencap -p > "$out"

  # CRITICAL: pipe to pnm:- not png:-.
  # png:- embeds a fresh tIME chunk on every magick invocation, breaking hash determinism
  # on byte-identical input. pnm has no timestamp metadata.
  cur_hash=$(magick "$out" -crop "${CROP_W}x${CROP_H}+0+${CROP_Y}" pnm:- 2>/dev/null \
             | md5sum | awk '{print $1}')

  if [ "$cur_hash" = "$prev_hash" ] && [ -n "$prev_hash" ]; then
    rm "$out"; n=$((n-1))
    echo "End of thread at iteration $n"
    break
  fi

  prev_hash="$cur_hash"
  adb -s "$DEV" shell input swipe $((width/2)) "$y_high" $((width/2)) "$y_low" "$swipe_duration"
  sleep "$swipe_sleep"
done
```

Use `exec-out screencap -p` (not `shell screencap`) to avoid CRLF mangling of the PNG byte stream.

#### 0e. Resumability and theme drift

- **Resuming after partial failure:** if the loop exits early (USB disconnect, MAX_ITER hit, user interrupt), the next invocation can resume from the current phone position. Load `prev_hash` from the last existing frame's cropped pnm hash and continue numbering from `n+1`. Pre-flight (0a) must still pass before resumption.
- **Theme drift mid-capture:** OS auto-dark-mode (light↔dark) can flip mid-run on long captures that span sundown/sunrise. Bubble-colour palettes flip with the theme; a single `--bubble-colors` flag fits one theme only. Detect by sampling a known-background pixel (interior of conversation area, offset to avoid bubbles/avatars) on the first and last frames — values in the `#E0–F0` (light) range vs `#10–20` (dark) range indicate a transition. Split affected frames into per-theme subdirs and OCR each with its own `--bubble-colors` flag; or force the OS theme to a fixed value before re-running.

#### 0f. Operator note — rejection doesn't always cancel

If the operator submits the capture loop as a foreground `Bash` call and the user clicks reject, the shell may have already been dispatched to a background runner and continue writing files and sending swipes regardless. The "tool use rejected" message reflects user intent, not the actual process state. **Verify side effects via `ps -ef | grep adb`, `ls $DST`, and `adb -s $DEV shell dumpsys window | grep mCurrentFocus` before claiming the loop stopped.** Wait for the eventual completion notification to confirm the run is actually over.

After Phase 0 completes, proceed to Phase 1 with the capture directory as the input source.

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

**Re-use existing helpers first.** Before writing fresh scripts for batch OCR + chat assembly, check whether the user has ready-to-run implementations on hand. Common locations to probe: `command -v chat-ocr-batch.py` (and `chat-ocr-attribute.py`, `chat-ocr-stitch.py`); a personal scripts directory referenced in the user's CLAUDE.md; `~/.claude/commands/`-adjacent helpers; `~/bin/`. If they exist, prefer running them over re-deriving — they will already be tuned for the messenger / theme combination they were first written against, and re-running is cheaper than re-writing. If they don't exist, write fresh per the sketches below; consider naming them with the same conventions so they're discoverable next time.

**Throughput note:** the easyocr CLI loads the model fresh on every invocation (~5–10 s on CPU). For batches ≳ 30 frames, the model-load overhead dominates wall time. Drop to a Python wrapper that imports `easyocr.Reader` once and loops over frames in-process — typically 5–10× faster end-to-end. Sketch:

```python
import easyocr, json, sys
from pathlib import Path
reader = easyocr.Reader(['ch_sim','en'], gpu=False)  # adjust langs
for img in sorted(Path(sys.argv[1]).glob('*.jpg')):
    result = reader.readtext(str(img), detail=1, paragraph=False)
    out = [{'bbox':[[int(p[0]),int(p[1])] for p in b],'text':t,'conf':float(c)} for b,t,c in result]
    img.with_suffix('.ocr.json').write_text(json.dumps(out, ensure_ascii=False))
```

Build the assembled text:

- **generic** — concatenate lines top-to-bottom by bbox y-centre. If `--raw`, emit verbatim with no further processing. Otherwise the optional Claude post-pass (text-only, no images in context) adds inline translation in parentheses unless `--no-translate`.
- **chat** — group lines into messages using one of two sender-attribution heuristics:
  - **bubble-colour (preferred when `--bubble-colors=` is passed)**: for each OCR text bbox, sample pixels inside the bbox using Pillow. **The filter direction depends on theme** — text and background have inverted luminance between light and dark modes:
    - **Light theme** (app uses light backgrounds with dark text): filter OUT pixels where all channels < 130 (those are dark text); the remaining pixels are the bubble background.
    - **Dark theme** (app uses dark backgrounds with light text): filter OUT pixels where all channels > 200 (those are light text); the remaining pixels are the bubble background.
    Detect theme by sampling a known-background pixel (interior of conversation area, offset from any bubble or avatar) on frame 001 — if luminance < ~60 across all channels, treat as dark theme; if > ~200, light. Document the chosen direction in the run metadata so a future operator inspecting the output knows which way the filter went.
    Average the remaining pixels = bubble background colour. Classify by colour distance against the two declared colours. Resolve named aliases (`green` → `(95, 180, 80)`-ish range, `white` → `(248-255, 248-255, 248-255)`, `dark-grey` → `(45, 45, 45)`-ish range, `black` → `(15, 15, 15)`-ish range, etc.) and hex into RGB triples first. `auto` mode samples a known text-bbox region from screenshot 1 and asks the user to confirm sender attribution before locking in.
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

## Skill Monitor

As you execute this skill, follow `_skill-monitor.md` (same commands directory as this file): watch for gaps, and propose specific edits to this skill at the end.
