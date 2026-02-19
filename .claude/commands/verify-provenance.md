---
name: verify-provenance
description: Verify integrity of AI Provenance Log - check hashes and OTS proofs
---

# Verify Provenance - Audit Trail Integrity Check

You are verifying the integrity of the AI Provenance Log by recomputing session file hashes, comparing against logged values, and checking OpenTimestamps proofs.

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

### 2. Read Provenance Log

```bash
PROVENANCE_LOG="$VAULT_PATH/06 Archive/Provenance/AI Provenance Log.md"
if [[ ! -f "$PROVENANCE_LOG" ]]; then
  echo "No provenance log found at $PROVENANCE_LOG"
  exit 0
fi
```

Read the file. Parse all table rows after the `|---|---|---|---|---|` header separator. Each row has format:
```
| Timestamp | Project | Session | SHA256 (first 16) | OTS |
```

Extract from each row:
- **Session filename** (e.g., `2026-02-17.md`)
- **Logged hash** (first 16 hex chars, may be wrapped in backticks)
- **OTS status** (`pending`, `confirmed`, or `—`)

### 3. Verify Each Entry

For each entry, perform three checks:

**3a. File existence:**
```bash
SESSION_FILE="$VAULT_PATH/06 Archive/Claude Sessions/$SESSION_FILENAME"
if [[ ! -f "$SESSION_FILE" ]]; then
  echo "MISSING: $SESSION_FILENAME"
  # Record as MISSING, continue to next entry
fi
```

**3b. Hash verification:**
```bash
CURRENT_HASH=$(sha256sum "$SESSION_FILE" | awk '{print $1}')
CURRENT_SHORT="${CURRENT_HASH:0:16}"

if [[ "$CURRENT_SHORT" == "$LOGGED_HASH" ]]; then
  echo "MATCH: $SESSION_FILENAME ($PROJECT_TAG)"
else
  echo "MISMATCH: $SESSION_FILENAME ($PROJECT_TAG)"
  echo "  Logged:  $LOGGED_HASH"
  echo "  Current: $CURRENT_SHORT"
  echo "  (File was edited after provenance was logged)"
fi
```

**3c. OTS verification (if applicable):**
```bash
OTS_FILE="$VAULT_PATH/06 Archive/Provenance/${SESSION_FILENAME%.md}.ots"
if [[ -f "$OTS_FILE" ]]; then
  # Try to upgrade pending proofs first
  ots upgrade "$OTS_FILE" 2>/dev/null

  # Then verify (-f points to the actual session file, since .ots was moved to Provenance/)
  OTS_RESULT=$(ots verify -f "$SESSION_FILE" "$OTS_FILE" 2>&1)
  if echo "$OTS_RESULT" | grep -q "Success"; then
    echo "OTS CONFIRMED: $SESSION_FILENAME"
    # If log still says "pending", could update to "confirmed" (optional)
  elif echo "$OTS_RESULT" | grep -q "Pending"; then
    echo "OTS PENDING: $SESSION_FILENAME (not yet confirmed by Bitcoin blockchain)"
  else
    echo "OTS FAILED: $SESSION_FILENAME"
    echo "  $OTS_RESULT"
    # Note: OTS failure on non-final entries of the day is expected.
    # End-of-day primacy means only the last stamp's proof survives.
    # Earlier entries (park before goodnight) will show OTS FAILED
    # because the proof was overwritten by the later stamp.
  fi
else
  if [[ "$LOGGED_OTS" != "—" ]]; then
    echo "OTS MISSING: $SESSION_FILENAME (logged as '$LOGGED_OTS' but .ots file not found)"
  fi
fi
```

### 4. Display Summary

```
## Provenance Verification Report

Entries checked: N
✓ Hash matches: N
✗ Hash mismatches: N (files edited after logging)
? Missing files: N
⏳ OTS pending: N
✓ OTS confirmed: N
— OTS not stamped: N

[If any mismatches:]
### Mismatches
| Session | Project | Logged Hash | Current Hash |
|---|---|---|---|
| 2026-02-17.md | JAMA Derm Letter | `a1b2c3d4e5f67890` | `f9e8d7c6b5a43210` |

[If any missing files:]
### Missing Files
- 2026-01-15.md (Project: Travel 2026) — file may have been archived or deleted
```

### 5. Offer Fixes (optional)

If mismatches found, offer:
> "Hash mismatches mean session files were edited after provenance was logged. Options:
> 1. **Re-hash** — update log entries with current hashes (loses original proof)
> 2. **Leave as-is** — mismatches are documented, original timestamps preserved
> 3. **Investigate** — show diff between logged and current state"

If OTS proofs are pending and upgradeable, offer:
> "N OTS proofs upgraded from 'pending' to 'confirmed'. Update log entries?"

## Guidelines

- **Read-only by default:** Verification doesn't modify any files unless user explicitly approves fixes
- **Non-destructive:** Never delete or overwrite session files or OTS proofs
- **Batch operation:** Checks ALL entries in one pass, not one-by-one
- **OTS upgrade is safe:** `ots upgrade` just adds blockchain confirmation to existing proof file — doesn't change the timestamp or hash
- **Run periodically:** Good practice to run `/verify-provenance` weekly or before any publication submission to catch stale hashes early

## Integration

- **Reads:** `06 Archive/Provenance/AI Provenance Log.md`, session files in `06 Archive/Claude Sessions/`, OTS proofs in `06 Archive/Provenance/`
- **May update:** Provenance Log (if user approves re-hashing or OTS status updates)
- **Complements:** `/provenance` (creates entries), `/park` `/checkpoint` `/goodnight` (auto-creates entries)
