# Photo Review — Contact Sheet Browser

Review a directory of photos by generating contact sheet thumbnails, then iteratively narrow to a final selection.

## When to use

When the user wants to review, curate, or select from a batch of photos — too many to open individually. Typical triggers: "pick the best photos", "choose photos to send", "help me select", "review my exports".

## Prerequisites

- `imagemagick` installed (`montage`, `convert` commands)
- A directory of image files (JPG, PNG, etc.)

## Workflow

### Phase 1: Survey

1. **Count and list** the photos in the target directory:
   ```bash
   ls "<dir>" | wc -l
   ```

2. **Generate contact sheets** in batches of ~48-60 images using `montage`. Key settings tuned to stay under typical file-size hooks (~200KB output):
   ```bash
   cd "<dir>" && FILES=$(ls *.jpg | head -60 | tr '\n' ' ') && \
     montage -label '%f' -geometry 250x170+3+3 -tile 6x \
     -background white -font Helvetica -pointsize 9 \
     $FILES -quality 50 -resize 50% /tmp/photo-review/batch1.jpg
   ```
   - If output exceeds ~200KB, shrink further: `convert input.jpg -quality 35 -resize 40% output.jpg`
   - Process sequentially (not parallel) to avoid OOM on large batches
   - Label each thumbnail with filename (`-label '%f'`) so picks can be referenced later

3. **View all contact sheets** and note candidates by filename.

### Phase 2: Shortlist

4. **Create a shortlist contact sheet** at higher resolution for closer comparison:
   ```bash
   montage -label '%f' -geometry 400x300+4+4 -tile 4x \
     -background white -font Helvetica -pointsize 12 \
     <candidate files> -quality 40 -resize 40% /tmp/photo-review/shortlist.jpg
   ```

5. **Evaluate and refine** — cut duplicates, weak compositions, redundant subjects. Aim for variety across:
   - Time of day (day / golden hour / night)
   - Subject type (landscape / street / architecture / people / nature / art)
   - Mood and energy (grand vs intimate, polished vs textured)

### Phase 3: Final selection

6. **Create a final contact sheet** of the chosen photos for user approval.

7. **Copy selections** to a named subfolder:
   ```bash
   mkdir -p "<dir>/<selection name>" && \
     for f in <files>; do cp "<dir>/$f" "<dir>/<selection name>/"; done
   ```

## Selection principles

If the user has documented curation preferences in a Photography context file, read it first and apply their style. Otherwise, default to:
- **Anchor with hero shots** — the obvious "best" images that give the set structure
- **Prioritise variety** — no two photos doing the same job
- **Cut freely** — duplicates, second angles of the same scene, generic compositions

## Cleanup

Temp files go in `/tmp/photo-review/`. Clean up when done:
```bash
rm -rf /tmp/photo-review/
```

---

**Skill monitor:** Also follow the instructions in `.claude/commands/_skill-monitor.md`.
