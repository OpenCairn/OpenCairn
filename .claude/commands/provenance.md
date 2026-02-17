---
name: provenance
description: Log cryptographic hash of current session for AI collaboration audit trail
parameters:
  - "--auto" - Auto-tag from session context (default)
  - "--tag TAG" - Manual project/manuscript tag
---

# Provenance - AI Collaboration Audit Trail

You are logging the current session to the AI Provenance Log with a cryptographic hash for future academic disclosure and audit defence.

## Purpose

When submitting work to journals (JAMA Derm, etc.) that require AI disclosure, or for any future use case requiring proof of AI collaboration:
1. **Accurate dates** — when Claude was used
2. **Scope** — which sessions touched which projects/manuscripts
3. **Cryptographic proof** — SHA256 hashes prove no tampering
4. **Trusted timestamps** — OpenTimestamps proofs anchored to Bitcoin blockchain (optional)
5. **Audit defence** — if questioned, produce session file + verify hash + OTS proof

## Manual vs Automatic Invocation

- **Manual (`/provenance`):** Always prompts for tag, always logs. Use when you know a session is worth logging regardless of `**Project:**` link.
- **Automatic (from `/park`, `/checkpoint`, `/goodnight`):** Tag-gated. Only fires if the session has a `**Project:**` link. No project = skip silently. No user prompt — tag auto-detected from project link.

## Instructions

### 1. Resolve Vault Path

```bash
if [[ -z "${VAULT_PATH:-}" ]]; then
  echo "VAULT_PATH not set"; exit 1
elif [[ ! -d "$VAULT_PATH" ]]; then
  echo "VAULT_PATH=$VAULT_PATH not found"; exit 1
else
  echo "VAULT_PATH=$VAULT_PATH OK"
fi
```

### 2. Get Current Date and Session File

```bash
TODAY=$(date +"%Y-%m-%d")
SESSION_FILE="$VAULT_PATH/06 Archive/Claude Sessions/$TODAY.md"
```

Check if session file exists:
```bash
if [[ ! -f "$SESSION_FILE" ]]; then
  echo "No session file for today ($TODAY) - nothing to log"
  # Skip gracefully, don't error
fi
```

If no session file exists yet, display "No session file to hash" and exit.

### 3. Determine Project/Manuscript Tag

**If `--tag TAG` parameter provided:** Use that tag exactly as given. Skip to step 4.

**If `--auto` (default):**
- Scan the conversation for context clues:
  - `**Project:**` links in session summaries
  - Project names mentioned (JAMA Derm Letter, Computational Photography, Travel 2026, etc.)
  - Main topic of work
- If multiple topics, choose the primary one
- If unclear, use session title as tag

**Prompt user for confirmation (manual invocation only):**
> Auto-detected tag: [tag]
>
> Confirm, edit, or skip?

- **Confirm** → proceed to step 4
- **Edit** → user provides replacement tag → proceed
- **Skip** → abort without logging

### 4. Check Idempotency

Before logging, check if this session + tag combination already exists:
```bash
PROVENANCE_LOG="$VAULT_PATH/07 System/AI Provenance Log.md"
if [[ ! -f "$PROVENANCE_LOG" ]]; then
  echo "Provenance log not found at $PROVENANCE_LOG — skipping"
  exit 0
fi

if grep -Fq "| $PROJECT_TAG | $TODAY.md |" "$PROVENANCE_LOG"; then
  echo "Already logged: $TODAY.md with tag '$PROJECT_TAG' — skipping duplicate"
  exit 0
fi
```

### 5. Compute Hash, Stamp, and Append (atomic)

**5a. Hash the session file:**
```bash
HASH=$(sha256sum "$SESSION_FILE" | awk '{print $1}')
SHORT_HASH="${HASH:0:16}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
```

**5b. OpenTimestamps (optional, non-blocking):**
```bash
OTS_STATUS="—"
if command -v ots &>/dev/null; then
  mkdir -p "$VAULT_PATH/07 System/Provenance"
  if ots stamp "$SESSION_FILE" 2>/dev/null; then
    mv "${SESSION_FILE}.ots" "$VAULT_PATH/07 System/Provenance/${TODAY}.ots" 2>/dev/null
    OTS_STATUS="pending"
  fi
fi
```

The `.ots` proof is initially "pending" — it becomes "confirmed" after ~2 hours when the Bitcoin block is mined. Run `ots upgrade` or `/verify-provenance` later to check confirmation status.

If `ots` is not installed or network is unavailable, skip silently (`OTS_STATUS` stays `—`).

**5c. Append table row with flock:**
```bash
ROW="| $TIMESTAMP | $PROJECT_TAG | $TODAY.md | \`$SHORT_HASH\` | $OTS_STATUS |"

flock -w 10 "$VAULT_PATH/07 System/.provenance-lock" bash -c "
  sed -i '/^|---|---|---|---|---|$/a\\
$ROW' '$PROVENANCE_LOG'
"
```

**Why flock:** Prevents race conditions when multiple sessions park simultaneously. Uses a separate lock file from the session lock (`06 Archive/Claude Sessions/.lock`) to avoid deadlock.

### 6. Display Confirmation

```
✓ Provenance logged
  Project: [tag]
  Session: [date].md
  Hash: [first 16 chars]...
  OTS: [pending/—]

Full log: 07 System/AI Provenance Log.md
```

## Guidelines

- **Manual `/provenance`:** Always prompts for tag confirmation. User can skip.
- **Automatic (park/checkpoint/goodnight):** Tag-gated by `**Project:**` link. No prompt. Silent skip if no project.
- **Idempotent:** Same session+tag combination never logged twice
- **Non-blocking:** Failures never prevent park/checkpoint/goodnight from completing
- **Hash reflects file state at time of logging:** If session file is manually edited after logging, hash becomes stale. This is a known limitation — not a bug. For audit purposes, don't edit session files after logging provenance.
- **OTS is best-effort:** Requires network access to Bitcoin calendar servers. Graceful degradation if offline or `ots` not installed.
- **Session file must exist:** If no session file yet (early in day), skip gracefully

## Integration

- **Creates:** Entries in `07 System/AI Provenance Log.md`, `.ots` proofs in `07 System/Provenance/`
- **Reads:** Current day's session file from `06 Archive/Claude Sessions/`
- **Called by:** `/park`, `/checkpoint`, `/goodnight` (automatic, tag-gated), user (manual, always logs)
- **Verified by:** `/verify-provenance`
- **Lock file:** `$VAULT_PATH/07 System/.provenance-lock` (separate from session lock)

## Example JAMA Derm Disclosure

> "The author used Claude Sonnet 4.5 (Anthropic, San Francisco, CA) on 17 Feb 2026 to assist with structuring arguments and refining prose in this letter. All content, interpretations, and conclusions remain the author's responsibility. Full session transcript and cryptographic proof (SHA256 + OpenTimestamps) available upon request."
