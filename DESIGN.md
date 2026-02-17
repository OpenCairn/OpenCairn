# CCO Design Document

Cross-cutting architecture and design decisions for the Claude Code + Obsidian (CCO) template. Individual commands document their own logic — this doc explains *why* things work the way they do and how the pieces connect.

---

## Architecture Overview

```
CLAUDE.md                          ← Session entry point (context routing)
  ↓
07 System/Context - *.md           ← Domain hubs (lazy-loaded per topic)
  ↓
Detail pages (Projects, Areas)     ← Specific knowledge (loaded on demand)

.claude/commands/*.md              ← Slash commands (rituals + tools)
.claude/scripts/*.sh               ← I/O workers (locking, atomic writes)
```

**Three layers:**
1. **Context layer** — CLAUDE.md routes to domain hubs, which route to detail pages. Hierarchical lazy-loading: Claude reads only what's relevant to the current prompt, not the whole vault.
2. **Command layer** — Slash commands that encode workflows as repeatable rituals. Commands are instructions for Claude (markdown), not scripts.
3. **Script layer** — Shell scripts that handle file I/O with locking and atomicity. Commands shell out to these for durable writes.

---

## Session Lifecycle

Sessions flow through a predictable lifecycle. Each stage has a dedicated command:

```
/morning → frame the day
    ↓
  work (conversation with Claude)
    ↓
/checkpoint → mid-session save (optional, repeatable)
    ↓
/park → end session, capture state
    ↓
/pickup → resume from where you left off
    ↓
/goodnight → end-of-day close-out
```

### What each stage produces

| Command | Session file | WIP update | Bidirectional links | OTS stamp | Quality gate |
|---------|-------------|-----------|-------------------|-----------|-------------|
| `/checkpoint` | Append | No | No | No | No |
| `/park` | Append | Yes | Yes | Yes | Yes |
| `/goodnight` | Append | Yes | Yes | Yes | No (different flow) |

**Key invariant:** `/checkpoint` is a subset of `/park`. Same session format, fewer side effects. Pickup finds both identically.

### Session file format

All sessions live in `06 Archive/Claude Sessions/YYYY-MM-DD.md`. Multiple sessions per day append to the same file. Each session gets a `## Session N` heading with summary, decisions, open loops, files touched, and pickup context.

### Bidirectional linking

`/park` and `/goodnight` create forward links ("Next session:") in the previous session's pickup context, creating a navigable chain. `/pickup` follows these chains to reconstruct continuity. The `add-forward-link.sh` script handles the insertion atomically.

**Cross-day links** require a 5th argument to the script (the target date file), because the previous session lives in a different file than the new session.

---

## Provenance Chain

Cryptographic audit trail for AI collaboration disclosure (journals, legal).

```
Session file → SHA256 hash → Provenance Log table → OTS stamp → Bitcoin blockchain
                                                          ↓
                                                   07 System/Provenance/DATE.ots
```

### Design Decisions

**End-of-day primacy.** Only the last OTS stamp of the day survives. `/checkpoint` hashes and logs but does NOT stamp (the file will change before day-end, making mid-session proofs unverifiable). `/park` and `/goodnight` hash, log, AND stamp. If goodnight runs after park, it overwrites park's `.ots` file. This is intentional — one verifiable proof per day is sufficient for disclosure purposes.

**Tag-gated auto-logging.** Provenance only fires automatically when a session has a `**Project:**` link in its pickup context. Admin, dating, and personal sessions are skipped. This keeps the log useful for publication audit trails without noise. Use `/provenance` manually to force-log any session.

**Idempotent.** Same session + tag combination is never logged twice. Checked via `grep -Fq` (fixed-string match, no regex interpretation).

**Non-blocking.** Provenance failures never prevent park/checkpoint/goodnight from completing. The audit trail is valuable but not worth losing session data over.

### OTS verification

`ots verify -f <session-file> <proof.ots>` — the `-f` flag is required because the `.ots` proof was moved from the sessions directory to `07 System/Provenance/`. Without `-f`, ots looks for the target file adjacent to the proof and fails.

For non-final entries of the day (e.g. a park entry that was later followed by goodnight), the OTS proof was overwritten. `/verify-provenance` will show "OTS FAILED" for these entries. This is expected under end-of-day primacy, not a bug.

---

## Concurrency Model

### Why locking matters

Users may run multiple Claude Code instances simultaneously (different terminal tabs, different machines synced via Syncthing). Without locking, concurrent writes to session files corrupt data.

### Lock architecture

Two separate lock files prevent deadlock:

| Lock file | Protects | Used by |
|-----------|----------|---------|
| `06 Archive/Claude Sessions/.lock` | Session file reads/writes | write-session.sh, add-forward-link.sh, goodnight session edits |
| `07 System/.provenance-lock` | Provenance log writes | All provenance operations |

**Why separate locks:** Provenance runs after session writes. If both used the same lock, the provenance step would deadlock waiting for a lock that the same process already holds (write-session.sh acquired it and it's still in scope).

### Why scripts, not inline bash

Early versions used inline `flock` commands in the command markdown. This caused a specific bug: Claude Code's permission system saves the entire bash command (including session content) as a permission pattern in `settings.local.json`. Multi-kilobyte session summaries inside flock commands bloated the settings file.

The fix: dedicated scripts (`write-session.sh`, `add-forward-link.sh`, `write-tickler.sh`) that receive content via stdin or arguments. The permission system only stores the short script invocation, not the payload.

### Why not the Edit tool

Claude Code's Edit tool has no file locking. It reads the file, computes a diff, and writes. If two instances Edit the same file simultaneously, one write silently overwrites the other. `flock` via Bash is the only safe concurrent write mechanism.

### Portable locking

Scripts use `flock` on Linux/macOS and fall back to `mkdir`-based locking on Windows (Git Bash). The `mkdir` approach is atomic on all filesystems — if the directory already exists, `mkdir` fails, which serves as a lock check.

---

## Context Loading

### Hierarchical lazy-loading

```
Level 0: CLAUDE.md          — Always loaded. Routes to everything else.
Level 1: Context hubs       — 07 System/Context - [Domain].md. Loaded per topic.
Level 2: Detail pages       — Projects, areas, specific files. Loaded on demand.
```

**Why:** Context tokens are expensive. A vault with 500+ notes can't be loaded entirely. Lazy-loading means Claude reads only what the current prompt requires, following links from CLAUDE.md → hub → detail as needed.

**The routing table** in CLAUDE.md maps topics to context files. When the user mentions "photography", Claude loads `Context - Photography.md`. When they mention "health", it loads `Context - Health & Optimisation.md`. Multiple topics trigger multiple loads.

### Works in Progress as entry point

`01 Now/Works in Progress.md` is the first file to check for any prompt that relates to an ongoing project. It has status, next actions, and links to recent sessions. From there, Claude follows links to project files and session archives as needed.

---

## Cross-Cutting Invariants

Rules that span multiple commands. Violating these causes bugs.

1. **Provenance runs before display.** In park (step 10 → 11), checkpoint (step 6 → 7), and goodnight (step 8a → 9), provenance logging happens before the completion message. The completion message includes provenance status — can't display it before computing it.

2. **Hash after all writes.** Provenance hashes the session file after it has been fully written AND forward-linked. Hashing before forward-linking means the hash doesn't include the bidirectional links, creating an immediate mismatch on verification.

3. **Scoped forward linking.** When inserting "Next session:" links, always scope to the specific previous session's heading block using line-number-based sed. Never use global `sed '/pattern/a ...'` — this matches every session in the file and creates duplicate insertions.

4. **Session lock before provenance lock.** When both locks are needed, always acquire the session lock first (via write-session.sh), release it, then acquire the provenance lock. Never hold both simultaneously.

5. **Working memory model (goodnight).** Session files are read once at the start of `/goodnight`, then treated as write-only. Mid-flow corrections from the user update working memory AND the files, but the files are never re-read. Re-reading would pull stale data and undo the user's corrections.

6. **Checkpoint is a subset of park.** Same session format, no WIP update, no bidirectional links, no OTS stamp, no quality gate. If checkpoint grows new features, they should be a strict subset of park's features.

---

## File Organisation

### Topic-keyed, not filetype-keyed

Files belong together by purpose, not by extension. A travel folder contains `.pdf`, `.md`, and `.png` — not separate Documents/Notes/Images trees.

### Path-keyed memories

Claude Code stores memories in `~/.claude/projects/` keyed to the absolute path of the working directory. Moving the vault to a different path makes memories appear lost. They're recoverable by copying `.md` files from the old path key to the new one.

---

## Extension Points

The template is designed to be customised:

- **Add commands** by creating `.claude/commands/your-command.md`
- **Add context hubs** by creating `07 System/Context - [Domain].md` and adding a routing entry to CLAUDE.md
- **Add scripts** for new I/O patterns that need locking (follow the portable locking pattern from existing scripts)
- **Provenance is optional** — if you don't need audit trails, the tag gate ensures it stays silent. Remove the provenance commands entirely if unwanted.
