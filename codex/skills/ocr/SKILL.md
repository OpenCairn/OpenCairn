---
name: ocr
description: Extract text and structured content from image screenshots (chat logs, social-feed posts, documents). Defaults to local easyocr extraction with a text-only Codex post-pass for chat structuring; image inspection is used only where visual interpretation is required or explicitly requested.
---

# OCR — Screenshots to Text

Extract text and structured content from one or many screenshots. The default engine is **local easyocr** (no images sent to an image model); a text-only Codex pass handles sender attribution, translation, and dedup for chat content. Codex image inspection is reserved for `--type=moments` (where image descriptions are part of the output) or when explicitly opted in via `--engine=vision`.

## When to use

When the user wants structured text extracted from screenshots. Typical triggers: "OCR these screenshots", "pull the text out of this", "process my chat screenshots", a directory path containing screenshots, or a single `.png`/`.jpg` path. The three supported content templates are:

- **chat** — messaging-app conversations (WhatsApp, Signal, iMessage, WeChat, etc.)
- **moments** — social-feed posts with caption + images per post
- **generic** — anything else (documents, receipts, UI screenshots, signage)

The skill also has a **live-capture mode** (`--capture=adb`) for when the user wants a long chat scraped directly off an Android phone over USB instead of supplying pre-existing screenshots. Triggers: "OCR the conversation with X on my phone", "scrape this thread", "scroll through and capture the whole chat". See Phase 0 for the capture workflow. Live capture requires the phone to be connected, authorised for ADB, and already on the target screen — the skill doesn't navigate the app for you. **Capture proceeds from the current scroll position forward (downward)** — to capture a whole thread the user must first scroll to the oldest message they want; confirm this before starting, or a run from the latest messages produces a near-empty transcript that looks successful.

## Prerequisites

Check these prerequisites; do not install packages automatically. If the user asks for installation, follow the active package-manager policy and cooldown hook rather than bypassing it.

- `magick` (ImageMagick) — required for preprocessing. Install with `sudo apt install imagemagick` or equivalent.
- `easyocr` CLI — required for the default engine. Install with `pip install --user easyocr` (or pipx). Verify it actually *runs* with `easyocr -h` — a bare `command -v easyocr` is not enough, because a stale `~/.local/bin` shim from a since-upgraded Python prints `ModuleNotFoundError` despite being on PATH; reinstall under the current interpreter if so. First run downloads model weights (~100 MB per language); subsequent runs are offline. CPU-only is fine but slow on large batches. GPU is easyocr's default and it falls back to CPU automatically when CUDA is absent; note the CLI's `--gpu False` is a no-op (argparse `type=bool` quirk — any non-empty string parses True), so to force CPU use the Python wrapper (`gpu=False`) instead.
- `Pillow` (PIL) — required when `--bubble-colors` is in play (chat-engine sender attribution by bubble background colour). `pip install --user Pillow` if missing. Verify with `python3 -c "from PIL import Image"`. If absent and `--bubble-colors` is requested, fall back to bbox attribution with a one-line warning.
- A Codex session with image-input support (only required when `--engine=vision` is selected or `--type=moments` needs image descriptions).

**Engine resolution order at runtime:**

1. If `--engine` is explicit, honour it; if the named engine is missing, stop with an install hint.
2. Otherwise (`--engine=auto`, the default), pick per type:
   - `--type=generic` / `--raw` → easyocr only.
   - `--type=chat` → easyocr extraction → text-only Codex post-pass (no images in context).
   - `--type=moments` → Codex image inspection (image descriptions are part of the output template).
3. If the resolved engine's binary is missing, fail with a one-line install instruction.

**Alternative engine (manual, not wired):** `tesseract` is a no-Python fallback if easyocr isn't available. The Debian/Ubuntu Chinese packs are `tesseract-ocr-chi-sim` (Simplified), `tesseract-ocr-chi-tra` (Traditional), and the `-vert` variants for vertical script. Invocation is roughly `tesseract input.jpg - -l chi_sim+eng`. Output quality on phone screenshots is materially worse than easyocr — only reach for it when easyocr can't be installed.

## Arguments

Interpret the free-text arguments following `$ocr` as a file path, directory, or glob. If none is provided, ask the user. **When `--capture=adb` is passed, the positional path is the OUTPUT directory for new captures, not an existing input source.**

Flags (parsed from arguments):

- `--type=chat|moments|generic` — content template. **Default `generic`.** No autodetection — the output formats differ materially, so the user must be explicit for `chat`/`moments`.
- `--engine=auto|easyocr|vision` — extraction engine. **Default `auto`** (resolved per the table in Prerequisites). `easyocr` forces local extraction across all types (image descriptions for moments will be marked unavailable). `vision` forces the legacy Vision path; use when easyocr quality is insufficient (low-resolution scans, unusual scripts) or when a moments run needs the original interpretation pass.
- `--contact=NAME` — used only with `--type=chat`: the name of the non-self participant. If omitted for chat, ask once before Phase 3.
- `--lang=CODE[,CODE…]` — easyocr language codes. Default `en` for English-only sources; for mixed Chinese + English (the common case), pass `--lang=ch_sim,en` (or `ch_tra,en` for Traditional). If omitted and the user's locale/context suggests CJK content, ask once. Ignored when `--engine=vision`.
- `--bubble-colors=me:COLOR,contact:COLOR` — chat-only, easyocr-only. Sender attribution by sampling the bubble background colour behind each OCR'd text bbox, rather than by left/right bbox position. Massively more reliable on messaging apps that don't use strict left/right alignment (WeChat, iMessage when avatars are off, Telegram dark themes). `COLOR` is one of: a named alias (`green`, `white`, `grey`, `blue`, `dark-grey`, `black`), an `#RRGGBB` hex, or `auto` to probe the first preprocessed image. Both sides must be specified. Falls back to bbox attribution with a warning if Pillow is unavailable or sampling fails. **Presets worth remembering** in Notes. If omitted on chat, the bbox heuristic is used (works reasonably for strict left/right layouts; misfires on wide-bubble apps like WeChat).
- `--max-width=N` — explicit override for resize width in px. If omitted, resolve from `--type`: `chat=900`, `moments=600`, `generic=900`. Chat is text-dense and needs a higher width; moments are visual-heavy and tolerate a smaller width.
- `--quality=N` — JPEG quality for preprocessing. Default `85`.
- `--out=PATH` — output file path. If omitted, ask at save time.
- `--no-preprocess` — skip the resize step. Valid when Codex image inspection accepts the originals, or when easyocr can read them directly (easyocr is largely indifferent to file size; preprocessing mostly helps it run faster).
- `--preprocess-only` — stop after Phase 2. Emit the resized-dir path and exit; skip Phases 3–5 entirely. Intended for use by other skills that invoke `$ocr` for preprocessing but handle extraction themselves. Not interactive in this mode.
- `--no-translate` — skip translation for non-English text. By default the easyocr → Claude post-pass adds translations for chat; Vision adds them inline per its existing rules.
- `--raw` — valid only with `--type=generic`. Dump visible text verbatim with no translation and no layout structuring. Under easyocr this is the natural `--detail 0 --paragraph True` output; under Vision this disables the interpretation layer. If passed with chat/moments, warn and ignore.

**Live-capture flags (only meaningful with `--capture=adb`):**

- `--capture=adb` — drive an attached Android device to capture screenshots from its foreground app before running the OCR pipeline. The first positional argument is treated as the OUTPUT directory for captures (created if missing) rather than an input path. Require a path outside the resolved vault and prefer a scratch location such as `~/tmp/<name>/`; raw screencaps are large and this loop cannot satisfy a per-file vault locking contract.
- `--device=ID` — ADB device serial. If omitted and exactly one authorised device is connected, pick it; if multiple, stop and require explicit selection.
- `--swipe-delta=N` — vertical scroll per gesture in native pixels (default ≈ 35% of detected screen height, i.e. ≈ 50% of the usable conversation area — see 0c). Values that would push the swipe end-point above the top crop boundary (~12% of screen height) are clamped to it; if your delta needs to exceed `y_high − 12% of height`, raise `y_high` instead. The capture loop emits a one-line stderr warning the first time the clamp fires.
- `--swipe-duration=MS` — gesture duration in milliseconds (default 700). Slower = less kinetic carry; fast flicks below ~400 ms overshoot and skip content even at the same delta.
- `--swipe-sleep=S` — settle delay after each swipe in seconds (default 1.8). Allows momentum to dissipate AND gives the app time to lazy-load newly visible content.
- `--max-frames=N` — hard cap on capture iterations (default 80). Long chats may need 200+; raise as needed.
- `--no-smoke-test` — skip the 3-frame calibration step. Don't use on first runs against a new app/theme — params calibrated on one device/app rarely transfer cleanly.

**Flag-to-shell-variable convention for the bash snippets below:** hyphens become underscores, the `--` prefix is dropped. `--swipe-delta=900` → `$swipe_delta=900`, `--max-frames=120` → `$max_frames=120`, etc.

**Composition with `--preprocess-only`:** `--capture=adb --preprocess-only` runs Phase 0 (capture) + Phase 2 (mogrify resize) then exits, emitting the resized-dir path. Phases 3–5 are skipped. Useful for delegator skills that want fresh captures but handle OCR themselves.

## Workflow

### Phase 0: Live capture (only when `--capture=adb`)

Skip entirely if `--capture=adb` is not set; proceed to Phase 1 with the positional argument as an existing screenshot path/directory.

Drive an attached Android device to produce screenshots from its foreground app, alternating screencap and swipe-up gestures until end-of-content is detected. The first positional argument is the OUTPUT directory for captures.

**Android only.** ADB is an Android tool. There is no equivalent path for iOS — iOS users must capture screenshots manually on the phone and supply them as an existing directory (the rest of Phases 1–5 still work). The skill has no iPhone-detection logic; if the user describes their device as an iPhone, route them to manual capture immediately rather than running pre-flight (`adb devices` will return empty and Phase 0a will fail with no useful diagnostic).

#### 0a. Pre-flight

1. **ADB present:** `command -v adb` or stop with install hint.
2. **Single authorised device:** `adb devices` → expect exactly one line ending in `device`. If `unauthorized`, ask the user to confirm the ADB prompt on the phone. If multiple authorised devices, require `--device=ID` and list candidates.
3. **Device awake, not dozing — and kept awake for the whole run:** `adb -s $DEV shell dumpsys power | grep mWakefulness` must report `Awake`. If `Dozing`/`Asleep`, send `KEYCODE_POWER` and re-check. If the phone is locked behind a PIN/biometric, ADB cannot unlock — stop and ask the user to unlock and bring the app to foreground. **Then neutralise the display timeout before capturing anything:** read it with `adb -s $DEV shell settings get system screen_off_timeout` (milliseconds), and if the sweep or any pause within it could exceed that, set `adb -s $DEV shell svc power stayon true` for the duration and restore `svc power stayon false` when the run ends. The swipe stream keeps the device awake *during* an uninterrupted loop, so the timeout bites in the gaps — between the smoke test and the full sweep, or while frames are being inspected. **A display that switches off mid-run does not stop the capture:** `screencap` keeps returning valid, non-empty, all-black PNGs and `input swipe` keeps scrolling the app underneath them, so the thread advances while the capture goes blind. The 0d blank-frame guard catches this, but only after the fact — the setting is what prevents it.
4. **Foreground app — report, don't adjudicate:** run `adb -s $DEV shell dumpsys window | grep mCurrentFocus`, show the focus string to the user verbatim, and ask them to confirm it's the thread they want scraped. The skill has no expected-package value to test against, and activity names like `LauncherUI` may host the chat view as a sub-window, so a name that looks wrong often isn't — the user's confirmation is the pass/fail criterion. **Don't navigate the app via ADB** — that risks destroying the user's current scroll position. The one exception: if focus reports `NotificationShade` or similar (often from prior keystrokes), send `KEYCODE_BACK` to dismiss and re-check; if that fails to recover, ask the user to fix state manually rather than guessing.
5. **Screen dimensions:** `adb -s $DEV shell wm size` → parse `<width>x<height>` (e.g. `1080x2410`). Use these to scale swipe coordinates; never hardcode.
6. **OCR model weights present:** the first easyocr run per language downloads ~100 MB of weights. Trigger it now, before capturing anything — run easyocr once over any small image with the run's `--lang` codes, or run the 0b preview OCR pass (step 4 there), which is mandatory on a first run for this reason. Discovering the download is impossible (offline, no disk, proxy) after an 80-frame capture wastes the whole sweep.

#### 0b. Smoke test (3 captures, then **STOP and ask the user**)

Run the loop in 0d with `max_frames=3` (the duplicate-hash termination check is harmless at this scale — mid-thread frames never collide). **This phase is not self-verifying — present the measurements below to the user and wait for their decision before proceeding to the full sweep.** Do not advance autonomously even if the numbers look fine to you; today's calibration loops in real sessions have routinely needed 2–3 user-driven tuning rounds.

1. **Frame 001 spot check:** is the app on the expected screen? Scrolled where the user said it was?
2. **Swipe advance measurement — measure it, don't eyeball it.** Vision Reads report image dimensions, not the coordinates of things inside the image, so any landmark y-position read off a screenshot is a guess that then propagates into `native_advance`. Cross-correlate the raw frames instead: take a strip from frame 002 and find the offset at which it best matches frame 001.

   ```bash
   A=$DST/frame_001.png; B=$DST/frame_002.png
   S=$(( height * 4 / 100 ))            # strip height
   Y0=$(( height * 55 / 100 ))          # strip taken from mid-content on frame 002
   magick "$B" -crop "${width}x${S}+0+${Y0}" +repage /tmp/strip.png
   best=""; best_d=""
   for d in $(seq $(( height * 10 / 100 )) 8 $(( height * 75 / 100 ))); do
     y=$(( Y0 + d )); [ $(( y + S )) -le "$height" ] || break
     m=$(magick "$A" -crop "${width}x${S}+0+${y}" +repage /tmp/cand.png \
         && magick compare -metric RMSE /tmp/strip.png /tmp/cand.png null: 2>&1 | awk '{print $1}')
     if [ -z "$best" ] || [ "${m%.*}" -lt "${best%.*}" ]; then best=$m; best_d=$d; fi
   done
   echo "native_advance=$best_d  (RMSE $best)"
   ```

   `best_d` is the native-pixel advance directly — no rescaling. A flat RMSE curve with no clear minimum means the strip landed on empty background or the app re-rendered; move `Y0` onto message content and retry rather than trusting the number.
   - Aim for **40–60% of usable screen height** (screen height minus status bar minus app header minus compose bar — roughly `height × 0.71` on a typical Android phone). Below ~30% wastes captures and operator time; above ~70% risks skipping content.
3. **Bubble palette sanity (for `--type=chat`).** Nothing in Phase 0 derives bubble coordinates, so get them before sampling: inspect frame 001 with Codex image tooling (resize first if the tool rejects the original), show it to the user, and have them nominate three points — one inside their own bubble, one inside a contact bubble, and one on bare conversation background. Convert points back to native coordinates if the inspected image was resized, then sample each with `magick "$frame" -crop 1x1+X+Y txt:- | tail -1`.
4. **Preview OCR pass on the 3 smoke frames — mandatory on a first run** (see 0a step 6: it forces the model-weights download while a re-capture is still cheap), optional afterwards. Validates end-to-end OCR quality, sender attribution direction, and translation post-pass before committing to the full sweep. Cost: tens of seconds on CPU easyocr, plus the one-off weights download.
5. **Present and wait.** Report the measured advance (as native px and as % of usable height), the sampled palette and detected theme, and whether the preview OCR (if run) looks sane. Ask the user: continue with current params, or tune `--swipe-delta` / `--swipe-duration` / `--swipe-sleep` and re-run the smoke test? Do not interpret silence as approval.

If anything is off, tune and re-run the smoke test. Cheaper to iterate at 3 frames than 30.

**Transition to the full sweep.** The smoke test has already scrolled the phone 3 frames past the start. On approval with unchanged swipe params, **resume — don't restart**: keep frames 001–003, continue the 0d loop from `n=4` with `prev_hash` loaded from frame 003's cropped-pnm hash (the 0e resume mechanics). If the user tunes swipe params, the smoke frames no longer match the full-run geometry: delete them and ask the user to re-position the chat at the starting point before the fresh run.

#### 0c. Swipe geometry

- **Direction:** swipe from a `y_high` near the bottom of the conversation area to a `y_low` near the top. This scrolls the view *downward* — newer content appears at the bottom. For most messaging apps, capturing a thread from oldest to newest means starting at the top of history and scrolling forward.
- **Delta:** vertical pixel distance between `y_high` and `y_low`, default ≈ 35% of screen height — which is ≈ 50% of the usable conversation area (~71% of screen height), the middle of the 40–60% aim band in 0b. Larger delta = fewer captures needed but higher overshoot risk; anything above ~50% of screen height sits outside the aim band.
- **Duration:** **700 ms or more.** A fast flick (≤400 ms) at the *same* delta induces kinetic carry that visibly overshoots intended content, dropping messages. Slow gestures stick to the input delta. This is the single most common cause of skipped-content runs.
- **Sleep after:** 1.8 s default. Allows momentum to settle AND gives the app time to lazy-load newly visible content (which may shift layout if it pops in late). Drop below 1.5 s only with confidence the app finishes layout quickly.
- **Native coordinates:** ADB input uses native pixels (from `wm size`). Don't confuse with any resized-preview width used elsewhere in the skill.

#### 0d. Capture loop with cropped-md5 termination

**Bind the two inputs before emitting the snippet.** They are not derived anywhere in the loop: substitute the device serial resolved in 0a.2 (or `--device`) and the output directory from the first positional argument, as literals. Refuse to run the loop with either unset — an empty `DEV` makes every `adb` call fail and the loop reports a false end-of-thread.

```bash
DEV="<device serial from 0a.2 or --device>"
DST="<output directory from the first positional argument>"
case "$DEV$DST" in *"<"*) echo "substitute DEV and DST before running" >&2; exit 1;; esac
case "$DST" in /*) ;; *) echo "DST must be an absolute path" >&2; exit 1;; esac
[ "$DST" != "/" ] && [ "$DST" != "$HOME" ] || { echo "refusing broad capture destination" >&2; exit 1; }
# Phase 0 has already established that DST is outside the resolved vault.
mkdir -p "$DST"

# 1. Derive screen dimensions (don't hardcode)
SIZE=$(adb -s "$DEV" shell wm size | grep -oE '[0-9]+x[0-9]+' | head -1)
width="${SIZE%x*}"
height="${SIZE#*x}"

# 2. Swipe geometry from flags (with defaults)
swipe_delta="${swipe_delta:-$((height * 71 / 200))}"  # ~35% of screen = ~50% of usable
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
EMPTY_MD5=$(printf '' | md5sum | awk '{print $1}')   # hash of zero-byte input

while [ "$n" -lt "$MAX_ITER" ]; do
  n=$((n+1))
  printf -v i "%03d" "$n"
  out="$DST/frame_$i.png"
  if ! adb -s "$DEV" exec-out screencap -p > "$out" || [ ! -s "$out" ]; then
    rm -f "$out"; n=$((n-1))
    echo "screencap failed at iteration $((n+1)) — capture is TRUNCATED, not complete" >&2
    break
  fi

  # BLANK-FRAME GUARD: a display-off frame is a VALID, non-empty, all-black PNG. It passes
  # the size test above and hashes deterministically, so two in a row satisfy the duplicate-
  # hash test below and get reported as end-of-thread — a silent truncation that looks clean.
  # Discriminate on standard deviation, NOT mean brightness: a true-black dark theme has a
  # low mean (a #111111 page background means ~17) and would false-trip a brightness floor,
  # but any real UI has spatial variance while a blank frame has none.
  sd=$(magick "$out" -colorspace Gray -format "%[fx:standard_deviation*255]" info:)
  # An empty $sd means magick failed or is absent. Without this branch `[ "" -lt 3 ]`
  # errors with "integer expression expected", the if falls through to the else, and the
  # guard SILENTLY DOES NOT FIRE — reinstating the exact silent truncation it exists to
  # prevent. A guard that cannot run is a stop condition, not a pass.
  if [ -z "$sd" ]; then
    rm -f "$out"; n=$((n-1))
    echo "blank-frame guard could not run (magick returned nothing) at iteration $((n+1)) — capture is TRUNCATED, not complete" >&2
    break
  fi
  if [ "${sd%.*}" -lt 3 ]; then
    rm -f "$out"; n=$((n-1))
    echo "blank frame (stddev $sd) at iteration $((n+1)) — display off; capture is TRUNCATED, not complete" >&2
    break
  fi

  # CRITICAL: pipe to pnm:- not png:-.
  # png:- embeds a fresh tIME chunk on every magick invocation, breaking hash determinism
  # on byte-identical input. pnm has no timestamp metadata.
  cur_hash=$(magick "$out" -crop "${CROP_W}x${CROP_H}+0+${CROP_Y}" pnm:- \
             | md5sum | awk '{print $1}')

  # md5 of empty input is a fixed constant; two unreadable frames in a row would
  # otherwise look like a duplicate and be reported as end-of-thread.
  if [ "$cur_hash" = "$EMPTY_MD5" ]; then
    rm -f "$out"; n=$((n-1))
    echo "unreadable frame at iteration $((n+1)) — capture is TRUNCATED, not complete" >&2
    break
  fi

  if [ "$cur_hash" = "$prev_hash" ] && [ -n "$prev_hash" ]; then
    rm "$out"; n=$((n-1))
    echo "End of thread at iteration $n"
    break
  fi

  prev_hash="$cur_hash"
  # Progress heartbeat: a long sweep is otherwise silent for many minutes, which is
  # indistinguishable from a hang. Emit on stderr so stdout stays clean for callers.
  [ $(( n % 10 )) -eq 0 ] && echo "  [$n/$MAX_ITER] frames, ${SECONDS}s elapsed" >&2
  adb -s "$DEV" shell input swipe $((width/2)) "$y_high" $((width/2)) "$y_low" "$swipe_duration"
  sleep "$swipe_sleep"
done
echo "captured $n frames in ${SECONDS}s" >&2
```

Use `exec-out screencap -p` (not `shell screencap`) to avoid CRLF mangling of the PNG byte stream.

**Only the duplicate-hash exit means end-of-thread.** Exiting at `n == MAX_ITER`, or on any failure guard (screencap error / unreadable frame / blank frame), leaves a truncated capture — say so explicitly and ask the user whether to resume (raise `--max-frames`, or fix the device state, then continue per 0e) before OCRing what looks like, but is not, the full thread.

**A duplicate-hash exit at an implausibly low frame count is a failure until proven otherwise.** End-of-thread after a handful of frames, on a thread the user described as long, is the signature of a blank-frame or stuck-app run. Before reporting completion, Read the last retained frame and confirm **the identity of its bottom-most message** — timestamp and content — against the newest traffic the user expects. **Position is not evidence.** A chat viewport always renders some message against the compose bar, mid-thread exactly as at the end, so "a message sits above the compose bar" is confirmatory-only: it is equally true under "reached the end" and under "went blind three frames in", which is precisely the pair being distinguished. Only *which* message it is separates them. The frame count alone cannot distinguish them either.

**One legitimate short run exists — name it before diagnosing a fault.** If the user positioned the thread near its bottom (a catch-up capture of only the newest messages, rather than a whole-thread scrape), a 2–5 frame sweep is the correct result. That case is distinguished by the same Read, on message *identity* at both ends: the last frame's bottom-most message is the newest traffic the user expects, and the first frame's top is the starting point they named. Note the asymmetry — under a blind run the first frame also shows content the user recognises, because they positioned it, so the first-frame half carries no discriminating load by itself; the last-frame identity check is what separates the cases. Asserting either without the Read is how a truncated capture ships as complete.

#### 0e. Resumability and theme drift

- **Resuming after partial failure:** if the loop exits early (USB disconnect, MAX_ITER hit, user interrupt), the next invocation can resume from the current phone position. Load `prev_hash` from the last existing frame's cropped pnm hash and continue numbering from `n+1`. Pre-flight (0a) must still pass before resumption.
- **After a blank-frame exit, the phone is NOT where the last good frame says it is.** `input swipe` keeps registering with the display off, so every blind iteration still scrolled the app: the true position is ahead of the last retained frame by the number of swipes sent after it, and content in that span was never captured. Do not resume by numbering onward from the last frame — that silently drops the gap. Instead scroll *back* (swipe `y_low` → `y_high`) until a fresh screencap visibly overlaps content already held in the last retained frame, confirm the overlap by Reading it, then resume forward. Overlap is free (dedup removes it); a gap is unrecoverable without a second sweep. Never reason about the size of the gap from the swipe count alone — verify it visually.
- **Theme drift mid-capture:** OS auto-dark-mode (light↔dark) can flip mid-run on long captures that span sundown/sunrise. Bubble-colour palettes flip with the theme; a single `--bubble-colors` flag fits one theme only. Detect by sampling a known-background pixel (interior of conversation area, offset to avoid bubbles/avatars) on the first and last frames — values in the `#E0–F0` (light) range vs `#10–20` (dark) range indicate a transition. Split affected frames into per-theme subdirs and OCR each with its own `--bubble-colors` flag; or force the OS theme to a fixed value before re-running.

#### 0f. Operator note — interruption doesn't prove cancellation

If the capture loop was dispatched as a live Codex exec session, a user interruption may arrive after the process started. **Verify side effects via `ps -ef | rg '[a]db'`, `ls "$DST"`, and `adb -s "$DEV" shell dumpsys window | rg mCurrentFocus` before claiming the loop stopped.** Terminate the live exec session deliberately when cancellation is requested, then verify the process is gone.

After Phase 0 completes, proceed to Phase 1 with the capture directory as the input source.

### Phase 1: Validate

1. Resolve the positional path/glob to a sorted list of image files matching extensions `.png .jpg .jpeg .webp .heic .heif` (case-insensitive). Sort by filename — phone screenshots are typically timestamp-encoded. Fall back to mtime if filenames don't sort meaningfully.
2. If zero images match, stop and tell the user.
3. If `--type=chat` and `--contact` is absent, ask the user for the contact name now (before preprocessing). **Skip this prompt when `--preprocess-only` is set** — that mode is non-interactive and never reaches sender attribution.
4. **Vision path only:** if more than ~25 images, warn the user that a single-turn batch read may exceed the context budget and suggest splitting into chunks of ≤25. Skip this warning when the resolved engine is easyocr — no images enter context on that path.
5. Codex has no Claude Read-hook byte threshold to inspect. On image-inspection paths, preprocess by default to the configured width; if `--no-preprocess` is explicit, attempt the image read once and stop with the tool's actual error if it rejects the file. On an easyocr-only run, originals are acceptable but may be slower.

### Phase 2: Preprocess

Skip this phase entirely if `--no-preprocess` was passed and the Phase 1 size check allowed it. When skipped, every later reference to "preprocessed images" means the source originals.

1. Resolve `SRC` to the source directory (for a single file, its parent, while processing only that file). If `SRC` is inside the resolved vault, set `DST` to a new `mktemp -d` directory outside the vault; vault intermediates may not be written directly. Otherwise use `DST="$SRC/_ocr_resized"`, unless the source is a repository and the user prefers scratch. The Phase 3a `.ocr.json` sidecars live beside the preprocessed images in `DST`. Report the intermediate path and do not remove it before a delegating caller is finished.
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
4. **Only on paths that inspect images:** attempt the preprocessed image read. If Codex rejects a dimension or batch, downscale progressively (720 → 640 → 512 → 448) or split the batch. Skip this on easyocr-only runs.
5. Report briefly: `"N files, source avg X MB → resized avg Y KB, width Wpx, quality Q."`
6. **If `--preprocess-only`, stop here.** Emit one final line — `"Preprocessed → <absolute DST path>"` — and end the skill. No Vision read, no transcript, no interactive prompt. Delegating callers consume the DST path and handle extraction themselves.

### Phase 3: Extract

Resolve the engine per the Prerequisites table. The branches:

#### 3a. Engine = easyocr

**Sidecar contract.** Everything downstream (attribution, stitching, any helper script) reads `<image basename>.ocr.json` — a single JSON **array**, one object per detected line, keys `bbox` / `text` / `conf`. Produce it with the in-process wrapper below; that wrapper is the canonical extraction path, not an optimisation.

```python
import easyocr, json, sys
from pathlib import Path
reader = easyocr.Reader(['ch_sim','en'], gpu=False)  # adjust langs
for img in sorted(Path(sys.argv[1]).glob('*.jpg')):
    result = reader.readtext(str(img), detail=1, paragraph=False)
    out = [{'bbox':[[int(p[0]),int(p[1])] for p in b],'text':t,'conf':float(c)} for b,t,c in result]
    img.with_suffix('.ocr.json').write_text(json.dumps(out, ensure_ascii=False))
```

It also avoids the CLI's dominant cost: the `easyocr` binary loads the model fresh on every invocation (~5–10 s on CPU), which dominates wall time from roughly 30 frames up. Importing `easyocr.Reader` once and looping in-process is typically 5–10× faster end-to-end.

**The `easyocr` CLI is a one-off spot check only** — for eyeballing a single image, never for producing sidecars:

```bash
easyocr -l <lang codes, space-separated> -f "$img" --detail 1 --output_format json
```

Its output does **not** satisfy the sidecar contract on either axis: it is JSONL (one object per line, not an array) with keys `boxes` / `text` / `confident`. A consumer expecting `.ocr.json` skips such a file silently, so a whole run can produce an empty transcript with no error. If a CLI-produced dump has to be reused, convert it to the array/key contract above first rather than pointing a consumer at it.

- `-l` takes **space-separated** codes (`-l ch_sim en`), not a CSV — the skill's `--lang` flag is CSV for parsing convenience; split it before invoking.
- `--detail 1` returns per-line `[bbox, text, confidence]`. We need bboxes for chat sender-side heuristics.
- **Do NOT pass `--paragraph False`** — the flag is the same argparse `type=bool` trap as `--gpu`: any non-empty string (including `False`) parses True, which merges lines into paragraphs and destroys the discrete bboxes the chat heuristics need. The default is already `False`; omit the flag. (Passing `--paragraph True` for `--raw` output works, since `True` also parses True.)
- **`--output_format json` still doesn't give you a sidecar** — without it the CLI prints Python-repr tuples (single quotes), which isn't valid JSON at all; with it you get JSONL under the wrong keys. Anything a script will parse comes from the wrapper.
- GPU: don't pass `--gpu` — the default is True with automatic CPU fallback, and `--gpu False` is a no-op (see Prerequisites). Force CPU via the Python wrapper if needed.

**Re-use existing helpers first.** Before writing fresh scripts for batch OCR + chat assembly, check whether the user has ready-to-run implementations on hand. Probe `command -v chat-ocr-batch.py` (and related helpers), personal script directories referenced in applicable `AGENTS.md`, `~/bin/`, and the source skill's adjacent helper directories when present. Read each helper's source header before invoking it.

**This skill's flags do not propagate into helper scripts.** Assume nothing: such helpers are typically configured by *editing module-level constants* (languages, GPU on/off, the me/contact/background RGB triples) and take a single positional source directory — no argparse, so `--help` is swallowed as a path argument and the script may run against an empty glob instead of printing usage. **Read each helper's source header before invoking it**, not `--help`; then either match its configuration to this run's `--lang` / `--bubble-colors` values — editing the constants where they are hardcoded, or confirming the run's auto-detected choice where the helper reports one — or write fresh per the sketches above. Name new helpers by the same convention so they're discoverable next time.

Build the assembled text:

- **generic** — concatenate lines top-to-bottom by bbox y-centre. If `--raw`, invoke with `--detail 0 --paragraph True` instead (no bboxes needed) and emit the output verbatim with no further processing. Otherwise the optional Codex post-pass (text-only, no images in context) adds inline translation in parentheses unless `--no-translate`.
- **chat** — group lines into messages using one of two sender-attribution heuristics:
  - **bubble-colour (preferred when `--bubble-colors=` is passed)**: for each OCR text bbox, sample pixels inside the bbox using Pillow. **The filter direction depends on theme** — text and background have inverted luminance between light and dark modes:
    - **Light theme** (app uses light backgrounds with dark text): filter OUT pixels where all channels < 130 (those are dark text); the remaining pixels are the bubble background.
    - **Dark theme** (app uses dark backgrounds with light text): filter OUT pixels where all channels > 200 (those are light text); the remaining pixels are the bubble background.
    Detect theme by sampling a known-background pixel (interior of conversation area, offset from any bubble or avatar) on frame 001 — if luminance < ~60 across all channels, treat as dark theme; if > ~200, light. Document the chosen direction in the run metadata so a future operator inspecting the output knows which way the filter went.
    Average the remaining pixels = bubble background colour. Classify by colour distance against the two declared colours. Resolve named aliases (`green` → `(95, 180, 80)`-ish range, `white` → `(248-255, 248-255, 248-255)`, `dark-grey` → `(45, 45, 45)`-ish range, `black` → `(15, 15, 15)`-ish range, etc.) and hex into RGB triples first. `auto` mode samples a known text-bbox region from screenshot 1 and asks the user to confirm sender attribution before locking in.
  - **bbox left-edge fallback (default)**: thresholds are fractions of the *resolved* resize width `W` (the `--max-width` value, or a narrower one if Phase 2 step 4 downscaled a file) — never absolute pixels, or a single override collapses every line onto one side. Lines whose bbox left-edge ≤ `0.24 × W` are attributed to `--contact`; lines whose right-edge ≥ `0.755 × W` are "Me" (≈220px and ≈680px at the default `W=900`); ambiguous lines fall into a centre band (timestamps, system messages, date dividers) and become italicised placeholders.
  Then run a text-only Codex post-pass to stitch wrapped lines into messages, regex-extract `HH:MM` timestamps, add translations, and dedup across screenshots. The post-pass receives only the assembled text blob, never the images.
- **moments** — easyocr extracts caption text only. Image descriptions are marked `**Images:** N (descriptions unavailable in easyocr engine — re-run with --engine=vision for per-image descriptions)`. If the user actually needs descriptions, recommend re-running with `--engine=vision` on a chunked subset rather than synthesising fake descriptions.

Confidence floor: if the median easyocr confidence across the batch is below `0.5`, surface a one-line warning before the transcript and suggest `--engine=vision` for affected files. Don't auto-fall-back — the user should make the trade explicitly.

#### 3b. Engine = vision

**Batch-load strategy.** Inspect all preprocessed images in one turn, using parallel image reads where the Codex runtime permits. This makes cross-screenshot dedup one inference pass. Chunk when the batch is too large for the active image tool. If repeated image-read failures persist after one downscale/split attempt, stop and recommend `--engine=easyocr` rather than looping.

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
   1. **Save** — if `--out` was passed, save to that path without asking; otherwise ask where (propose a default based on type + source location) and the filename.
   2. **Discuss** — summarise, extract action items, answer questions, pull quotes.
   3. **Both** — save first, then discuss.

   Wait for the user's response before proceeding.

4. On save: if the agreed path is inside the resolved vault, draft outside the vault and install it with `locked-edit.sh`: use `--append` when missing; for an approved overwrite, re-read the current contents and use them as literal OLD with `--replace`. Outside the vault, use the normal Codex file-edit workflow. Do not auto-append to user-curated files unless explicitly asked.

### Phase 5: Optional discussion

Whatever the user asked for in Phase 4 — summary, action items, Q&A, pattern spotting.

## Notes

- **Bubble-colour calibration.** Before locking in `--bubble-colors`, sample the actual pixel values on one preprocessed screenshot at a known sender region and a known contact region — messaging apps drift their palettes across versions and themes, and named aliases are starting points, not ground truth. If the two sides are too close in colour space to discriminate cleanly (e.g. both white in some chat apps without theme contrast), fall back to bbox attribution.
- easyocr handles Chinese (`ch_sim`, `ch_tra`), Japanese (`ja`), Korean (`ko`), Cyrillic, Arabic, and ~80 other scripts; pass them as a CSV via `--lang`. Vision handles the same set without language flags. Tesseract requires per-language packages (see Prerequisites).
- The easyocr default avoids image-model batch and dimension limits. If image inspection repeatedly refuses a batch after one resize/split attempt, re-run with `--engine=easyocr`; context compaction does not change file dimensions.
- Preprocessing reduces image-tool failures and helps easyocr run faster on CPU. `--no-preprocess` is safe only when the active image tool accepts the originals or no image inspection is used.
- For batches above ~25 images on the Vision path, prefer splitting into chunks. easyocr scales linearly on CPU without an upper bound; the practical limit is wall-clock time.
- Dedup is intentionally conservative — exact-match only. If consecutive screenshots have overlapping content that isn't bit-identical (slight crop shift, different timestamp formatting), the dedup won't merge them and the operator must clean up manually.
- This skill doesn't wire tesseract or PaddleOCR. If a verifiable text layer for archival is ever required, add a parallel engine flag and merge its output into the metadata header rather than the transcript body — don't blend engines mid-transcript.

## Skill Monitor

As you execute this skill, follow `~/.codex/skills/_skill-monitor.md`: watch for gaps, and log observations at the end per that file.
