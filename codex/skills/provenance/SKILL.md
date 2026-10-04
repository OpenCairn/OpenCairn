---
name: provenance
description: Flag this session for cryptographic provenance hashing at end-of-day
---


# Provenance - Flag Session for Cryptographic Audit Trail

**Scoped rule loading:** `_shared-rules-content.md` before snapshotting verbatim material. Read the applicable numbered sections at that point, from the same directory as the core `_shared-rules.md`; do not preload unrelated supplements.

You are flagging this session as provenance-worthy. This creates a lightweight flag file that `$goodnight` will process (hashing files, OTS-stamping, and logging). Optionally, work products that are already final can be hashed immediately.

## When To Use

Invoke `$provenance` when a session produces something worth proving existed at a point in time:
- Original hypotheses or novel intellectual contributions
- Journal submissions, letters, or formal documents
- Evidence archives
- Anything you might later need to establish priority or satisfy AI disclosure requirements

Most sessions don't need provenance. Don't invoke this for routine work.

## What Gets Hashed (Provenance Hierarchy)

1. **Work products** (highest value) — deliverable documents, hypotheses, analyses, letters. What you'd show a journal editor or use to establish intellectual priority. Can be hashed immediately (if final) or deferred to `$goodnight`.
2. **Session transcripts** (high integrity) — verbatim conversation exports. Prove the thinking happened and when. Re-export can change these bytes; verification of an older attestation requires a retained copy matching its digest. May contain sensitive/personal content — the hash proves existence; you don't hand over the transcript unless challenged. Hashed at `$goodnight` (after export).
3. **Session logs** (supporting context) — curated daily summaries. Append-only during the day, so only hashed at `$goodnight` when final.

## Instructions

### 1. Resolve Vault Path

```bash
"${VAULT_PATH:?VAULT_PATH not set}/.claude/scripts/resolve-vault.sh"
```

If error, abort. Read `~/.codex/skills/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path: the part after `VAULT_PATH=` in the resolver's output (`_shared-rules.md` §1).

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
PROJECT_TAG="<tag from Step 2>"
TODAY=$(date +"%Y-%m-%d")
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
FLAG_DIR="{VAULT}/07 System/.Provenance/pending"
SAFE_TAG=$(python3 - "$PROJECT_TAG" <<'PYTAG'
import hashlib, re, sys
original = sys.argv[1]
slug = re.sub(r'[^a-z0-9-]', '', original.lower().replace(' ', '-')) or 'untagged'
print(slug + '-' + hashlib.sha256(original.encode('utf-8')).hexdigest()[:16])
PYTAG
)
FLAG_FILE="$FLAG_DIR/${TODAY}-${SAFE_TAG}.md"
```

Before creating a new flag, read today's existing flags and reuse one only when its frontmatter `tag` exactly equals the original `PROJECT_TAG`; this also preserves an older unsuffixed flag. Never merge by sanitised filename alone. A filename occupied by a different tag is a conflict: preserve it and report the collision. Keep the original display tag in frontmatter and provenance rows; the suffix is filename identity only. Work-product snapshots/proofs use the writer's content digest identity, not this sanitised tag.

**If the flag file already exists** (repeat `$provenance` call in the same session): read it, merge any new work products into the existing list (no duplicates), update the timestamp, and rewrite it through `locked-edit.sh --replace` using the exact old file content. Do not create a second flag file. Merge means exactly: union of the `## Work Products` lists, every existing `## Hashed Immediately` entry preserved untouched, frontmatter `timestamp` bumped to now.

**If the flag file does not exist:** create it by piping the complete rendered block to `locked-edit.sh --append`; the wrapper creates absent files. Never redirect or edit a flag file directly.

Flag file format:
```markdown
---
date: YYYY-MM-DD
timestamp: YYYY-MM-DD HH:MM:SS TZ (updated on each $provenance call)
tag: Project Tag Here
---

## Work Products
- 05 Resources/Commentary/filename.md
- 05 Resources/Commentary/other-file.md

## Hashed Immediately
- 05 Resources/Commentary/filename.md — `abc123def4567890` (OTS: pending) [YYYY-MM-DD HH:MM]
```

The timestamp in frontmatter reflects the most recent `$provenance` call. The "Hashed Immediately" entries include their own timestamps so each hash is traceable to when it was taken.

### 5. Hash Final Work Products (optional, immediate)

If any work products are already final (won't be edited further), hash them now and record in the flag file's "Hashed Immediately" section. Also OTS-stamp them.

**Skip files already hashed:** If the flag file already has an entry for a given file in "Hashed Immediately", skip it — don't re-hash or re-stamp. If the file has been *edited* since the last hash (user explicitly says so), run the re-hash path below.

**The provenance log is append-only.** All attestation writes go through `provenance-write.py`; never paste rows into the log or use `locked-edit.sh --replace` on an old attestation. The writer appends through the canonical `locked-edit.sh` lock, rejects hashes other than 16 lowercase hexadecimal characters, and requires a matching byte-exact snapshot. `pending` and `confirmed` also require an existing `.ots` whose full digest matches the snapshot (`ots info`, a local inspection).

**Initial hash:** bind the verified context date, tag and absolute file list in one shell call. The helper stages each target outside the vault, hashes and stamps those same bytes, and retains its snapshot/proof through `locked-ingress.sh`. OTS failure is recorded honestly as `none (stamp failed)`; absent OTS as `none (ots unavailable)`. A live-file edit or re-export cannot change the stamped preimage.

```bash
PROVENANCE_DAY="<verified YYYY-MM-DD>"
PROJECT_TAG="<tag from Step 2>"
FINAL_PRODUCTS=("<absolute path 1>" "<absolute path 2>")
for DOC in "${FINAL_PRODUCTS[@]}"; do
  python3 "{VAULT}/.claude/scripts/provenance-write.py" --vault "{VAULT}" attest \
    --date "$PROVENANCE_DAY" --tag "$PROJECT_TAG" --file "$DOC" || exit 1
done
```

Each successful call prints a JSON receipt with `file`, `hash`, `status`, `snapshot` and `proof`. Each append also records a separate `evidence: {"snapshot": "<vault-relative path>", "proof": "<vault-relative path or null>"}` annotation in the OTS column, keyed by the same tag/file/digest (`proof` is JSON `null` when absent). The latest recorded locator selects the retained evidence across processes after validation; it is not a verification status. An invalid/dangling selected locator fails closed instead of silently selecting an older proof. Record the receipt's 16-character hash/status in the flag's "Hashed Immediately" section through `locked-edit.sh`. The leading dot in `.Provenance` excludes frozen preimages from Obsidian indexing and link-healing; do not rename it. The helper retains each source extension and keys new artefact filenames by the full 16-character logged hash; existing snapshots/proofs are never overwritten. Legacy 8-character filename suffixes remain verifiable.

**Re-hash:** run the same `attest` command with `--supersedes "<old 16-hex hash>"`. It validates that the old attestation exists for this tag/file, appends the new attestation, and appends a relationship row whose OTS column is ``supersedes `<old hash>` ``. The old row and its earlier proof stay untouched. Update the flag's entry to the returned hash/status through `locked-edit.sh`; keep the flag on any failure.

**Verification annotations:** after a proof is independently verified, append a `confirmed` row using the validated writer rather than changing its earlier `pending` row. A locator repair likewise appends a row with the new relative file path, original hash, matching snapshot and the honestly observed status; never rewrite the historical locator. Use the retained snapshot and the actual selected proof, not newly hashed live bytes. After an immutable upgrade, select its new proof path; the writer durably records it without changing the earlier proof or row:

```bash
python3 "{VAULT}/.claude/scripts/provenance-write.py" --vault "{VAULT}" append \
  --tag "<tag>" --file "<vault-relative file>" --hash "<16-hex hash>" \
  --status "confirmed" --snapshot "<absolute snapshot path>" --proof "<absolute .ots path>"
```

**Legacy retention:** when an old unannotated row lacks a snapshot but its resolved source still matches the logged digest, `retain-legacy --tag <tag> --file <original File column> --hash <16hex> [--source <resolved source>] [--proof <existing proof>]` retains source-backed evidence without a new stamp or status row. It validates the existing tag/file/digest record, staged bytes and proof's full SHA256; only explicit historical no-proof status permits no proof. It appends an evidence-only locator under the canonical lock, preserving every historical row. Recovery commands and failure boundaries live in weekly-hygiene Step 13b; ordinary `attest`/`append` retain their strict new-attestation requirements.

Transcript and session log hashing is always deferred to `$goodnight` — they're not final yet.

### 6. Display Confirmation

```
✓ Provenance flagged
  Tag: [tag]
  Work products: N files
    [relative/path/to/file.md] — hashed now: [hash]... (OTS: [pending / none (ots unavailable) / none (stamp failed)])
    [relative/path/to/other.md] — deferred to $goodnight
  Transcript: deferred to $goodnight
  Session log: deferred to $goodnight

  Flag: 07 System/.Provenance/pending/YYYY-MM-DD-tag.md
  → $goodnight will process this flag and complete hashing.
```

## Processing (by other skills)

### `$goodnight` (step 17)

Processes today's flag files:
1. Read each flag in `07 System/.Provenance/pending/` matching today's date.
2. Attest each work product with Step 5's writer. Compare immediately recorded hashes to the current file first; on change, announce it and use `--supersedes` instead of skipping it.
3. After export/final writes, attest the transcript and session log with the same writer. Both retain exact snapshots because re-export and link-healing can change their live bytes.
4. Finish each flag through the completion wrapper:

```bash
"{VAULT}/.claude/scripts/provenance-finish.sh" "{VAULT}" "<absolute flag path>"
```

This takes the flag's canonical lock and removes it **only** after the validator finds a same-tag, current-digest attestation with a matching retained snapshot (and matching proof for pending/confirmed) for every work product, that date's transcript, and that date's session log. Missing targets/rows/evidence, changed bytes or failed validation return nonzero and leave the flag pending. It never removes a source, snapshot or proof. To inspect without removing, run `provenance-write.py --vault "{VAULT}" check-flag --flag "<absolute flag path>"`; stdout lists missing targets and exit 0 means complete.

### `$goodnight` Catch-up mode (invoked by `$morning`)

Missed-day provenance processing is owned by `$goodnight` C1.h. Read that section for ordering, date selection and missing-target guards.

### `$weekly-hygiene` (provenance section)

Catches stragglers and verifies:
1. Process any remaining flags in `pending/` (missed goodnights) — hash everything listed, using the flag's date for context
2. Verify all existing provenance log entries (re-hash, compare, check OTS proofs)
3. Report findings in the hygiene report

## Guidelines

- **Manual only.** `$provenance` is never called automatically. You invoke it when the session produces something worth proving.
- **Lightweight.** The flag is a small markdown file. Heavy lifting (transcript/session log hashing, OTS stamping) happens at `$goodnight`.
- **Work products can be hashed immediately** if they're final, giving you the strongest proof (hash taken at creation time, not end of day).
- **Idempotent.** Multiple `$provenance` calls in the same session with the same tag merge new work products into the existing flag file — no duplicates, no second flag. If the tag changes between calls, a separate flag file is created (different tags = different provenance entries).
- **Relative paths.** Work products are logged with vault-relative paths (e.g., `05 Resources/Commentary/file.md`) to avoid collisions and enable verification from any machine.
- **Append-only log.** Rows are never rewritten — re-hashes append a new attestation and a separate `supersedes` relationship. A mutable log can't be distinguished from a tampered one.
- **Snapshots preserve the preimage.** Every attestation retains the exact hashed bytes in `07 System/.Provenance/` beside the `.ots` proof — without them, the first edit to the living document makes the proof unverifiable.
- **OTS is best-effort, and the log says so honestly.** Requires network access to Bitcoin calendar servers. The OTS column records the outcome — `pending` only when a stamp actually succeeded; `none (ots unavailable)` / `none (stamp failed)` otherwise — so a missing proof never masquerades as a pending one.

## Integration

- **Creates:** Flag files in `07 System/.Provenance/pending/`, entries in `07 System/AI Provenance Log.md` (for immediately-hashed work products), `.ots` proofs and `.snapshot.*` preimages (the work product's own extension) in `07 System/.Provenance/`
- **Processed by:** `$goodnight` (Step 17; C1.h for catch-up invoked by `$morning`), `$weekly-hygiene` (provenance section)
- **Verified by:** `$weekly-hygiene` (provenance verification section)

## Example AI Disclosure (journal submission)

> "The author used Claude Sonnet 4.5 (Anthropic, San Francisco, CA) on 17 Feb 2026 to assist with structuring arguments and refining prose in this letter. All content, interpretations, and conclusions remain the author's responsibility. Full session transcript and cryptographic proof (SHA256 + OpenTimestamps) available upon request."
