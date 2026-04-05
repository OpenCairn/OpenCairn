---
name: provenance
description: Log cryptographic hashes of session log and transcript for AI collaboration audit trail
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
"$VAULT_PATH/.claude/scripts/resolve-vault.sh"
```

   If error, abort. Read `~/.claude/commands/_shared-rules.md` and apply its rules throughout this skill. All code below uses `{VAULT}` as a placeholder — substitute the resolved vault path.

### 2. Get Current Date and Session Files

```bash
TODAY=$(date +"%Y-%m-%d")
SESSION_FILE="{VAULT}/06 Archive/Claude/Session Logs/$TODAY.md"
TRANSCRIPT_FILE="{VAULT}/06 Archive/Claude/Session Transcripts/$TODAY.md"
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
PROVENANCE_LOG="{VAULT}/07 System/AI Provenance Log.md"
if [[ ! -f "$PROVENANCE_LOG" ]]; then
  echo "Provenance log not found at $PROVENANCE_LOG — skipping"
  exit 0
fi

SKIP_SESSION=false
if grep -Fq "| $PROJECT_TAG | $TODAY.md |" "$PROVENANCE_LOG"; then
  echo "Already logged: $TODAY.md with tag '$PROJECT_TAG' — skipping duplicate"
  SKIP_SESSION=true
fi

SKIP_TRANSCRIPT=false
if grep -Fq "| $PROJECT_TAG | ${TODAY}-transcript.md |" "$PROVENANCE_LOG"; then
  echo "Already logged: ${TODAY}-transcript.md with tag '$PROJECT_TAG' — skipping duplicate"
  SKIP_TRANSCRIPT=true
fi

# If both already logged, nothing to do
if [[ "$SKIP_SESSION" == true && "$SKIP_TRANSCRIPT" == true ]]; then
  echo "Both session log and transcript already logged — skipping"
  exit 0
fi
# If session already logged but no transcript exists, also nothing to do
if [[ "$SKIP_SESSION" == true && ! -f "$TRANSCRIPT_FILE" ]]; then
  echo "Session log already logged, no transcript to hash — skipping"
  exit 0
fi
```

### 5. Hash Session Files
```bash
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S %Z')

# Hash session log
if [[ "$SKIP_SESSION" != true && -f "$SESSION_FILE" ]]; then
  HASH=$(sha256sum "$SESSION_FILE" | awk '{print $1}')
  SHORT_HASH="${HASH:0:16}"
fi

# Hash session transcript (if it exists)
HAS_TRANSCRIPT=false
if [[ "$SKIP_TRANSCRIPT" != true && -f "$TRANSCRIPT_FILE" ]]; then
  TRANSCRIPT_HASH=$(sha256sum "$TRANSCRIPT_FILE" | awk '{print $1}')
  TRANSCRIPT_SHORT="${TRANSCRIPT_HASH:0:16}"
  HAS_TRANSCRIPT=true
fi
```

Session transcripts are the verbatim conversation exports produced by `/park` step 14b and `/goodnight` step 16 (`export-session-transcripts.py`). They're higher-value provenance evidence than curated session logs because they capture the full, unedited interaction. Transcript hashing only fires when a transcript file exists — skips silently if not yet exported.

### 6. OpenTimestamps (optional, non-blocking)
```bash
OTS_STATUS="—"
if command -v ots &>/dev/null; then
  mkdir -p "{VAULT}/07 System/Provenance"
  # Stamp session log
  if [[ "$SKIP_SESSION" != true && -f "$SESSION_FILE" ]]; then
    if ots stamp "$SESSION_FILE" 2>/dev/null; then
      mv "${SESSION_FILE}.ots" "{VAULT}/07 System/Provenance/${TODAY}.ots" 2>/dev/null
      OTS_STATUS="pending"
    fi
  fi
  # Stamp transcript
  TRANSCRIPT_OTS_STATUS="—"
  if [[ "$HAS_TRANSCRIPT" == true ]]; then
    if ots stamp "$TRANSCRIPT_FILE" 2>/dev/null; then
      mv "${TRANSCRIPT_FILE}.ots" "{VAULT}/07 System/Provenance/${TODAY}-transcript.ots" 2>/dev/null
      TRANSCRIPT_OTS_STATUS="pending"
    fi
  fi
else
  TRANSCRIPT_OTS_STATUS="—"
fi
```

The `.ots` proof is initially "pending" — it becomes "confirmed" after ~2 hours when the Bitcoin block is mined. Run `ots upgrade` or `/verify-provenance` later to check confirmation status.

If `ots` is not installed or network is unavailable, skip silently (status stays `—`).

### 7. Append Table Rows
```bash
# Append session log row
if [[ "$SKIP_SESSION" != true && -f "$SESSION_FILE" ]]; then
  ROW="| $TIMESTAMP | $PROJECT_TAG | $TODAY.md | \`$SHORT_HASH\` | $OTS_STATUS |"

  # Use awk (not sed -i) for cross-platform compatibility (BSD sed requires different -i syntax)
  export _AWK_ROW="$ROW"
  flock -w 10 "{VAULT}/07 System/.provenance-lock" bash -c '
    awk "
      /^\|---\|---\|---\|---\|---\|$/ { print; print ENVIRON[\"_AWK_ROW\"]; next }
      { print }
    " "$1" > "$1.tmp" && mv "$1.tmp" "$1"
  ' _ "$PROVENANCE_LOG"
  unset _AWK_ROW
fi

# Append transcript row
if [[ "$HAS_TRANSCRIPT" == true ]]; then
  TRANSCRIPT_ROW="| $TIMESTAMP | $PROJECT_TAG | ${TODAY}-transcript.md | \`$TRANSCRIPT_SHORT\` | $TRANSCRIPT_OTS_STATUS |"

  export _AWK_ROW="$TRANSCRIPT_ROW"
  flock -w 10 "{VAULT}/07 System/.provenance-lock" bash -c '
    awk "
      /^\|---\|---\|---\|---\|---\|$/ { print; print ENVIRON[\"_AWK_ROW\"]; next }
      { print }
    " "$1" > "$1.tmp" && mv "$1.tmp" "$1"
  ' _ "$PROVENANCE_LOG"
  unset _AWK_ROW
fi
```

**Why flock:** Prevents race conditions when multiple sessions park simultaneously. Uses a separate lock file from the session lock (`06 Archive/Claude/Session Logs/.lock`) to avoid deadlock.

### 8. Display Confirmation

```
✓ Provenance logged
  Project: [tag]
  Session: [date].md — [first 16 chars]... (OTS: [pending/—])
  Transcript: [date]-transcript.md — [first 16 chars]... (OTS: [pending/—])
             [OR "not yet exported — will hash at /goodnight"]

Full log: 07 System/AI Provenance Log.md
```

If no transcript exists, display the "not yet exported" line. If session log was already logged (only transcript is new), display "already logged" for the session line.

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
- **Reads:** Current day's session log from `06 Archive/Claude/Session Logs/` and session transcript from `06 Archive/Claude/Session Transcripts/` (if exported)
- **Called by:** `/park`, `/checkpoint`, `/goodnight` (automatic, tag-gated), user (manual, always logs)
- **Verified by:** `/verify-provenance`
- **Lock file:** `{VAULT}/07 System/.provenance-lock` (separate from session lock)

## Example JAMA Derm Disclosure

> "The author used Claude Sonnet 4.5 (Anthropic, San Francisco, CA) on 17 Feb 2026 to assist with structuring arguments and refining prose in this letter. All content, interpretations, and conclusions remain the author's responsibility. Full session transcript and cryptographic proof (SHA256 + OpenTimestamps) available upon request."
