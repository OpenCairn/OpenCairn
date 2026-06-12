---
name: provenance
description: Flag this session for cryptographic provenance hashing at end-of-day
argument-hint: "[--tag TAG] [--files FILE1 FILE2...]"
---

# Provenance - Flag Session for Cryptographic Audit Trail

You are flagging this session as provenance-worthy. This creates a lightweight flag file that `/goodnight` will process (hashing files, OTS-stamping, and logging). Optionally, work products that are already final can be hashed immediately.

## When To Use

Invoke `/provenance` when a session produces something worth proving existed at a point in time:
- Original hypotheses or novel intellectual contributions
- Journal submissions, letters, or formal documents
- Evidence archives
- Anything you might later need to establish priority or satisfy AI disclosure requirements

Most sessions don't need provenance. Don't invoke this for routine work.

## What Gets Hashed (Provenance Hierarchy)

1. **Work products** (highest value) — deliverable documents, hypotheses, analyses, letters. What you'd show a journal editor or use to establish intellectual priority. Can be hashed immediately (if final) or deferred to `/goodnight`.
2. **Session transcripts** (high integrity) — verbatim conversation exports. Prove the thinking happened and when. Won't drift after export. May contain sensitive/personal content — the hash proves existence; you don't hand over the transcript unless challenged. Hashed at `/goodnight` (after export).
3. **Session logs** (supporting context) — curated daily summaries. Append-only during the day, so only hashed at `/goodnight` when final.

## Instructions

### 1. Resolve Vault Path

```bash
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `_shared-rules.md` from this skill's own commands directory (`~/.claude/commands/` or `{VAULT}/.claude/commands/`, whichever exists) and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

### 2. Determine Tag

**If `--tag TAG` provided:** Use that tag exactly.

**Otherwise:** Auto-detect from conversation context, then prompt:
> Auto-detected tag: [tag]
>
> Confirm, edit, or skip?

### 3. Identify Work Products

**If `--files` provided:** Use those paths.

**Otherwise:** Ask:
> Which files from this session are deliverables to hash?
> (These are the documents you'd show to establish priority or satisfy disclosure.)

Accept a list of file paths. Convert each to a vault-relative path (e.g., `05 Resources/Commentary/filename.md`).

### 4. Write or Update Flag File

```bash
TODAY=$(date +"%Y-%m-%d")
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
FLAG_DIR="{VAULT}/07 System/Provenance/pending"
mkdir -p "$FLAG_DIR"
SAFE_TAG=$(echo "$PROJECT_TAG" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
[[ -z "$SAFE_TAG" ]] && SAFE_TAG="untagged"   # punctuation/non-ASCII-only tags would otherwise yield "YYYY-MM-DD-.md"
FLAG_FILE="$FLAG_DIR/${TODAY}-${SAFE_TAG}.md"
```

**If the flag file already exists** (repeat `/provenance` call in the same session): read it, merge any new work products into the existing list (no duplicates), update the timestamp, and rewrite. Do not create a second flag file. Merge means exactly: union of the `## Work Products` lists, every existing `## Hashed Immediately` entry preserved untouched, frontmatter `timestamp` bumped to now.

**If the flag file does not exist:** create it.

Flag file format:
```markdown
---
date: YYYY-MM-DD
timestamp: YYYY-MM-DD HH:MM:SS TZ (updated on each /provenance call)
tag: Project Tag Here
---

## Work Products
- 05 Resources/Commentary/filename.md
- 05 Resources/Commentary/other-file.md

## Hashed Immediately
- 05 Resources/Commentary/filename.md — `abc123def456` (OTS: pending) [YYYY-MM-DD HH:MM]
```

The timestamp in frontmatter reflects the most recent `/provenance` call. The "Hashed Immediately" entries include their own timestamps so each hash is traceable to when it was taken.

### 5. Hash Final Work Products (optional, immediate)

If any work products are already final (won't be edited further), hash them now and record in the flag file's "Hashed Immediately" section. Also OTS-stamp them.

**Skip files already hashed:** If the flag file already has an entry for a given file in "Hashed Immediately", skip it — don't re-hash or re-stamp. If the file has been *edited* since the last hash (user explicitly says so), run the re-hash path below.

**⛔ The provenance log is append-only.** Never rewrite an existing row's hash or timestamp — the earlier attestation is exactly what establishes priority, and a log whose normal operation includes rewriting rows is indistinguishable from a tampered one. A re-hash appends a NEW row and marks the old row's OTS column `superseded`.

**Initial hash** (no existing entry in flag file). Run as ONE Bash call — variables set in a prior Bash tool call don't survive to the next — with `PROJECT_TAG` and the file list bound at the top of the same block:

```bash
TODAY=$(date +"%Y-%m-%d")
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
PROJECT_TAG="<tag from Step 2>"
FINAL_PRODUCTS=("<absolute path 1>" "<absolute path 2>")

for DOC in "${FINAL_PRODUCTS[@]}"; do
  [[ -f "$DOC" ]] || { echo "MISSING: $DOC"; continue; }
  # cut, not awk '{print ...}' — the slash-command loader substitutes bare $0-$9 as argument placeholders
  DOC_HASH=$(sha256sum "$DOC" | cut -d' ' -f1)
  DOC_SHORT="${DOC_HASH:0:16}"
  RELATIVE_PATH="${DOC#{VAULT}/}"
  SAFE_NAME=$(basename "$DOC" .md | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')

  mkdir -p "{VAULT}/07 System/Provenance"
  # Preimage snapshot — a hash without the exact bytes proves nothing. The work product is a
  # living document; once it's edited, this snapshot is the only copy that matches the proof.
  # Explicit existence guards, not cp/mv -n (deprecated in newer coreutils, non-portable).
  SNAP="{VAULT}/07 System/Provenance/${TODAY}-${SAFE_NAME}-${DOC_SHORT:0:8}.snapshot.md"
  [[ -e "$SNAP" ]] || cp "$DOC" "$SNAP"

  # OTS stamp — the logged status comes from the OUTCOME, never assumed. DOC_SHORT in the
  # proof name prevents same-basename collisions. Don't suppress stderr — a stamp failure's
  # reason gets reported, not buried.
  OTS_DEST="{VAULT}/07 System/Provenance/${TODAY}-${SAFE_NAME}-${DOC_SHORT:0:8}.ots"
  OTS_STATUS="none (ots unavailable)"
  if command -v ots &>/dev/null; then
    if ots stamp "$DOC"; then
      if [[ -e "$OTS_DEST" ]]; then
        rm "${DOC}.ots"   # identical content already proven today — keep the EARLIER proof (priority)
      else
        mv "${DOC}.ots" "$OTS_DEST"
      fi
      OTS_STATUS="pending"
    else
      OTS_STATUS="none (stamp failed)"
    fi
  fi
  echo "| $TIMESTAMP | $PROJECT_TAG | $RELATIVE_PATH | \`$DOC_SHORT\` | $OTS_STATUS |"
done
```

Append each emitted row to the log via `locked-edit.sh --append` (`_shared-rules.md` §5 — all of the log's writers serialise on its canonical lock):

```bash
printf '%s\n' "<row emitted above>" | "{VAULT}/.claude/scripts/locked-edit.sh" "{VAULT}/07 System/AI Provenance Log.md" --append
```

**Re-hash** (file edited since last hash — existing entry in flag file and provenance log):

1. **Re-run the initial-hash block** for the file. The new hash gives the snapshot and `.ots` new `DOC_SHORT`-suffixed filenames, so the original proof and snapshot are untouched; append the new row to the log as above.
2. **Mark the OLD row superseded:** Read the log, copy the old row **verbatim**, and `locked-edit.sh --replace` it with the identical row, OTS column rewritten to `superseded`. Literal match only — no regex, no sed.
3. **Update the flag file's "Hashed Immediately" entry** to the new hash + timestamp (the original attestation lives on in the log and in its snapshot/proof files).

Transcript and session log hashing is always deferred to `/goodnight` — they're not final yet.

### 6. Display Confirmation

```
✓ Provenance flagged
  Tag: [tag]
  Work products: N files
    [relative/path/to/file.md] — hashed now: [hash]... (OTS: [pending / none (ots unavailable) / none (stamp failed)])
    [relative/path/to/other.md] — deferred to /goodnight
  Transcript: deferred to /goodnight
  Session log: deferred to /goodnight

  Flag: 07 System/Provenance/pending/YYYY-MM-DD-tag.md
  → /goodnight will process this flag and complete hashing.
```

## Processing (by other skills)

### `/goodnight` (step 17)

Processes today's flag files:
1. Read each flag in `07 System/Provenance/pending/` matching today's date
2. Hash any work products listed but not yet hashed (check "Hashed Immediately" section). **For entries already in "Hashed Immediately", re-hash and compare against the recorded hash** — a silent edit between the immediate hash and goodnight is otherwise undetectable; on mismatch, announce it and run the Step 5 re-hash path (superseding row), don't skip silently
3. Hash session transcript (now exported and final)
4. Hash session log (now final)
5. OTS stamp all newly hashed files
6. Append all entries to `07 System/AI Provenance Log.md` (via `locked-edit.sh --append`, per Step 5)
7. Delete the flag file **only after verifying every listed item has a log row** — a partially processed flag (missing rows) stays in `pending/` for `/weekly-hygiene`'s straggler pass

### `/weekly-hygiene` (provenance section)

Catches stragglers and verifies:
1. Process any remaining flags in `pending/` (missed goodnights) — hash everything listed, using the flag's date for context
2. Verify all existing provenance log entries (re-hash, compare, check OTS proofs)
3. Report findings in the hygiene report

## Guidelines

- **Manual only.** `/provenance` is never called automatically. You invoke it when the session produces something worth proving.
- **Lightweight.** The flag is a small markdown file. Heavy lifting (transcript/session log hashing, OTS stamping) happens at `/goodnight`.
- **Work products can be hashed immediately** if they're final, giving you the strongest proof (hash taken at creation time, not end of day).
- **Idempotent.** Multiple `/provenance` calls in the same session with the same tag merge new work products into the existing flag file — no duplicates, no second flag. If the tag changes between calls, a separate flag file is created (different tags = different provenance entries).
- **Relative paths.** Work products are logged with vault-relative paths (e.g., `05 Resources/Commentary/file.md`) to avoid collisions and enable verification from any machine.
- **Append-only log.** Rows are never rewritten — re-hashes append a superseding row and mark the old one `superseded`. A mutable log can't be distinguished from a tampered one.
- **Snapshots preserve the preimage.** Each immediate hash copies the exact hashed bytes to `07 System/Provenance/` beside the `.ots` proof — without them, the first edit to the living document makes the proof unverifiable.
- **OTS is best-effort, and the log says so honestly.** Requires network access to Bitcoin calendar servers. The OTS column records the outcome — `pending` only when a stamp actually succeeded; `none (ots unavailable)` / `none (stamp failed)` otherwise — so a missing proof never masquerades as a pending one.

## Integration

- **Creates:** Flag files in `07 System/Provenance/pending/`, entries in `07 System/AI Provenance Log.md` (for immediately-hashed work products), `.ots` proofs and `.snapshot.md` preimages in `07 System/Provenance/`
- **Processed by:** `/goodnight` (step 17), `/weekly-hygiene` (provenance section)
- **Verified by:** `/weekly-hygiene` (provenance verification section)

## Example AI Disclosure (journal submission)

> "The author used Claude Sonnet 4.5 (Anthropic, San Francisco, CA) on 17 Feb 2026 to assist with structuring arguments and refining prose in this letter. All content, interpretations, and conclusions remain the author's responsibility. Full session transcript and cryptographic proof (SHA256 + OpenTimestamps) available upon request."
