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

### 4. Key Paths

These are the canonical paths for all provenance operations. This command is the **single source of truth** — `/park`, `/checkpoint`, and `/goodnight` reference this command rather than duplicating logic.

```bash
PROVENANCE_LOG="$VAULT_PATH/06 Archive/Provenance/AI Provenance Log.md"
PROVENANCE_DIR="$VAULT_PATH/06 Archive/Provenance"
PROVENANCE_LOCK="$VAULT_PATH/06 Archive/Provenance/.lock"
# Table format: | Timestamp | Project | Session | SHA256 (first 16) | OTS |
# Sed anchor for appending rows: /^|---|---|---|---|---|$/a\
```

### 5. Check Idempotency

Before logging, check if this session + tag combination already exists:
```bash
if [[ ! -f "$PROVENANCE_LOG" ]]; then
  echo "Provenance log not found at $PROVENANCE_LOG — skipping"
  exit 0
fi

if grep -Fq "| $PROJECT_TAG | $TODAY.md |" "$PROVENANCE_LOG"; then
  echo "Already logged: $TODAY.md with tag '$PROJECT_TAG' — skipping duplicate"
  exit 0
fi
```

### 6. Compute Hash, Stamp, and Append (atomic)

**6a. Hash the session file:**
```bash
HASH=$(sha256sum "$SESSION_FILE" | awk '{print $1}')
SHORT_HASH="${HASH:0:16}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')
```

**6b. OpenTimestamps (optional, non-blocking):**

Only stamp on session-ending commands (`/park`, `/goodnight`). `/checkpoint` skips OTS because the file will change before day-end, making mid-session proofs unverifiable (end-of-day primacy).

```bash
OTS_STATUS="—"
if [[ "$SKIP_OTS" != "true" ]] && command -v ots &>/dev/null; then
  mkdir -p "$PROVENANCE_DIR"
  if ots stamp "$SESSION_FILE" 2>/dev/null; then
    mv "${SESSION_FILE}.ots" "$PROVENANCE_DIR/${TODAY}.ots" 2>/dev/null
    OTS_STATUS="pending"
  fi
fi
```

The `.ots` proof is initially "pending" — it becomes "confirmed" after ~2 hours when the Bitcoin block is mined. Run `ots upgrade` or `/verify-provenance` later to check confirmation status.

If `ots` is not installed or network is unavailable, skip silently (`OTS_STATUS` stays `—`).

**6c. Append table row with flock:**
```bash
ROW="| $TIMESTAMP | $PROJECT_TAG | $TODAY.md | \`$SHORT_HASH\` | $OTS_STATUS |"

flock -w 10 "$PROVENANCE_LOCK" bash -c "
  sed -i '/^|---|---|---|---|---|$/a\\
$ROW' '$PROVENANCE_LOG'
"
```

**Why flock:** Prevents race conditions when multiple sessions park simultaneously. Uses a separate lock file from the session lock (`06 Archive/Claude Sessions/.lock`) to avoid deadlock.

### 7. Display Confirmation

```
✓ Provenance logged
  Project: [tag]
  Session: [date].md
  Hash: [first 16 chars]...
  OTS: [pending/—]

Full log: 06 Archive/Provenance/AI Provenance Log.md
```

## Guidelines

- **Manual `/provenance`:** Always prompts for tag confirmation. User can skip.
- **Automatic (park/checkpoint/goodnight):** Tag-gated by `**Project:**` link. No prompt. Silent skip if no project.
- **Idempotent:** Same session+tag combination never logged twice
- **Non-blocking:** Failures never prevent park/checkpoint/goodnight from completing
- **Hash reflects file state at time of logging:** If session file is manually edited after logging, hash becomes stale. This is a known limitation — not a bug. For audit purposes, don't edit session files after logging provenance.
- **OTS is best-effort:** Requires network access to Bitcoin calendar servers. Graceful degradation if offline or `ots` not installed.
- **Session file must exist:** If no session file yet (early in day), skip gracefully

## Selective Disclosure

The hash covers the entire daily session file (all sessions, all projects). To share provenance for a specific project without exposing unrelated sessions (e.g. dating chats):

1. At submission time, extract the project-tagged sessions into a standalone file
2. Hash and OTS stamp the extract
3. Share the extract — the original full-file OTS proof provides backbone evidence of the timeline

No journal currently demands cryptographic verification, but having the capability is the point.

## Integration

- **Creates:** Entries in `06 Archive/Provenance/AI Provenance Log.md`, `.ots` proofs in `06 Archive/Provenance/`
- **Reads:** Current day's session file from `06 Archive/Claude Sessions/`
- **Called by:** `/park`, `/checkpoint`, `/goodnight` (automatic, tag-gated), user (manual, always logs)
- **Verified by:** `/verify-provenance`
- **Lock file:** `$VAULT_PATH/06 Archive/Provenance/.lock` (separate from session lock)
- **This command is the SSOT** for provenance logic. Callers reference it, not duplicate it.

## Example JAMA Derm Disclosure

> "The author used Claude Sonnet 4.5 (Anthropic, San Francisco, CA) on 17 Feb 2026 to assist with structuring arguments and refining prose in this letter. All content, interpretations, and conclusions remain the author's responsibility. Full session transcript and cryptographic proof (SHA256 + OpenTimestamps) available upon request."
