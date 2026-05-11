---
name: provenance
description: Flag this session for cryptographic provenance hashing at end-of-day
parameters:
  - "--tag TAG" - Manual project/manuscript tag
  - "--files FILE1 FILE2..." - Work product files to hash
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

If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

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
FLAG_FILE="$FLAG_DIR/${TODAY}-${SAFE_TAG}.md"
```

**If the flag file already exists** (repeat `/provenance` call in the same session): read it, merge any new work products into the existing list (no duplicates), update the timestamp, and rewrite. Do not create a second flag file.

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

**Skip files already hashed:** If the flag file already has an entry for a given file in "Hashed Immediately", skip it — don't re-hash or re-stamp. If the file has been *edited* since the last hash (user explicitly says so), re-hash it and update ALL three artefacts:
1. The flag file's "Hashed Immediately" entry (new hash + new timestamp)
2. The provenance log row in `07 System/AI Provenance Log.md` (new hash AND new timestamp — both fields, not just the hash)
3. The OTS stamp (re-stamp the file, overwriting the previous `.ots` proof)

**Initial hash** (no existing entry in flag file):

```bash
for DOC in "${FINAL_PRODUCTS[@]}"; do
  if [[ -f "$DOC" ]]; then
    DOC_HASH=$(sha256sum "$DOC" | awk '{print $1}')
    DOC_SHORT="${DOC_HASH:0:16}"
    RELATIVE_PATH="${DOC#${VAULT}/}"

    # OTS stamp with date-prefixed filename
    if command -v ots &>/dev/null; then
      SAFE_NAME=$(basename "$DOC" .md | tr ' ' '-' | tr '[:upper:]' '[:lower:]')
      mkdir -p "{VAULT}/07 System/Provenance"
      ots stamp "$DOC" 2>/dev/null && \
        mv "${DOC}.ots" "{VAULT}/07 System/Provenance/${TODAY}-${SAFE_NAME}.ots" 2>/dev/null
    fi

    # Append to provenance log immediately
    ROW="| $TIMESTAMP | $PROJECT_TAG | $RELATIVE_PATH | \`$DOC_SHORT\` | pending |"
    # Use the append_row function (flock + awk pattern from goodnight)
  fi
done
```

**Re-hash** (file edited since last hash — existing entry in flag file and provenance log):

```bash
# 1. Compute new hash
DOC_HASH=$(sha256sum "$DOC" | awk '{print $1}')
DOC_SHORT="${DOC_HASH:0:16}"
NEW_TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')

# 2. Update flag file "Hashed Immediately" entry (new hash + new timestamp)
# Use Edit tool to replace the old hash line

# 3. Update provenance log row — BOTH hash AND timestamp (use flock)
flock "{VAULT}/07 System/.provenance-lock" \
  sed -i "s|$OLD_SHORT.*$RELATIVE_PATH|$NEW_TIMESTAMP | $PROJECT_TAG | $RELATIVE_PATH | \`$DOC_SHORT\` | pending |" \
  "{VAULT}/07 System/AI Provenance Log.md"

# 4. Re-stamp with OTS (overwrites previous .ots file at same path)
ots stamp "$DOC" 2>/dev/null && \
  mv "${DOC}.ots" "{VAULT}/07 System/Provenance/${TODAY}-${SAFE_NAME}.ots" 2>/dev/null
```

Transcript and session log hashing is always deferred to `/goodnight` — they're not final yet.

### 6. Display Confirmation

```
✓ Provenance flagged
  Tag: [tag]
  Work products: N files
    [relative/path/to/file.md] — hashed now: [hash]... (OTS: pending)
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
2. Hash any work products listed but not yet hashed (check "Hashed Immediately" section)
3. Hash session transcript (now exported and final)
4. Hash session log (now final)
5. OTS stamp all newly hashed files
6. Append all entries to `07 System/AI Provenance Log.md`
7. Delete the processed flag file

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
- **OTS is best-effort.** Requires network access to Bitcoin calendar servers. Graceful degradation if offline or `ots` not installed.

## Integration

- **Creates:** Flag files in `07 System/Provenance/pending/`, entries in `07 System/AI Provenance Log.md` (for immediately-hashed work products), `.ots` proofs in `07 System/Provenance/`
- **Processed by:** `/goodnight` (step 17), `/weekly-hygiene` (provenance section)
- **Verified by:** `/weekly-hygiene` (provenance verification section)

## Example JAMA Derm Disclosure

> "The author used Claude Sonnet 4.5 (Anthropic, San Francisco, CA) on 17 Feb 2026 to assist with structuring arguments and refining prose in this letter. All content, interpretations, and conclusions remain the author's responsibility. Full session transcript and cryptographic proof (SHA256 + OpenTimestamps) available upon request."
