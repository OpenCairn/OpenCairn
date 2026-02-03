---
name: checkpoint
aliases: [waypoint, save]
description: Mid-session state capture - persist progress without ending the session
parameters:
  - "--compact" - Run /compact after checkpointing (for heavy context sessions)
---

# Checkpoint - Mid-Session State Capture

You are capturing current session progress WITHOUT ending the session. This is a waypoint, not a destination.

## Philosophy

**Checkpoint vs Park:**
- `/park` = "I'm done for now, capture and close" (updates WIP, bidirectional links, goodbye)
- `/checkpoint` = "Save progress, keep going" (same session format, no WIP, no links, continue working)

The session file format is **identical** - pickup can find both. The difference is intent and what happens after.

Use checkpoint when:
- Before a risky operation (in case of crash)
- When context is getting heavy but you want to continue
- When you've digested a lot and want it persisted to vault
- Before switching sub-topics within same session
- Anxiety about losing progress (the flag itself provides relief)

## Instructions

### Phase 1: Setup

0. **Resolve vault path:**
   ```bash
   if [[ -z "${VAULT_PATH:-}" ]]; then
     echo "VAULT_PATH not set"; exit 1
   elif [[ ! -d "$VAULT_PATH" ]]; then
     echo "VAULT_PATH=$VAULT_PATH not found"; exit 1
   else
     echo "VAULT_PATH=$VAULT_PATH OK"
   fi
   ```

1. **Get current timestamp:**
   ```bash
   date +"%Y-%m-%d"  # for file path
   date +"%I:%M:%S%p" | tr '[:upper:]' '[:lower:]'  # for session timestamp
   ```

2. **Check today's session file** to find current session number:
   - Read `$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md`
   - Find the highest session number
   - If no file exists, this is Session 1

### Phase 2: Generate Session Content

3. **Scan the conversation** for:
   - What's been accomplished since session start (or last checkpoint)
   - Key decisions or insights
   - Open loops / pending items
   - Files created or modified
   - Related project (if applicable)

4. **Generate session summary** using the standard format:

```markdown
## Session N - [Topic/Name] ([Time with seconds - HH:MM:SSam/pm])

### Summary
[2-4 sentence narrative of what was accomplished. Focus on outcomes and decisions.]

### Key Insights / Decisions
[Bullet list of important realisations, architectural choices, or decisions made]
[Omit section if no notable insights]

### Next Steps / Open Loops
- [ ] Specific actionable item with clear next action
- [ ] Another open loop that needs attention
[Each item should be actionable and specific enough to resume without re-reading entire conversation]

### Files Created
- path/to/file.md - [purpose/description]
[Omit section if no files created]

### Files Updated
- path/to/file.md - [what changed and why]
[Omit section if no files updated]

### Pickup Context
**For next session:** [One clear sentence about where to pick up - the very next action to take]
**Project:** [[03 Projects/Project Name]] (if applicable)
```

**Project linking rules** (same as park):
- **Finite work** → link to `03 Projects/[name].md` (or `Backlog/`)
- **Ongoing area work** → link to `04 Areas/[path]/[name].md`
- **Never link to:** WIP sections, Resources, or Archive

### Phase 3: Write Session

5. **Write the session** using the write-session script:

   **If session file already exists (append):**
   ```bash
   cat << 'EOF' | ~/.claude/scripts/write-session.sh "$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md"
   ## Session N - [Topic] ([Time])

   [Session content here]
   EOF
   ```

   **If first session of the day (create):**
   ```bash
   cat << 'EOF' | ~/.claude/scripts/write-session.sh "$VAULT_PATH/06 Archive/Claude Sessions/YYYY-MM-DD.md" --create
   ## Session 1 - [Topic] ([Time])

   [Session content here]
   EOF
   ```

### Phase 4: Completion

6. **Display confirmation:**
   ```
   ✓ Checkpoint saved: 06 Archive/Claude Sessions/YYYY-MM-DD.md
   ✓ Session N - [Topic]
   ✓ Open loops documented: N items

   Session continues. Context preserved.
   ```

7. **Handle --compact flag** (if specified):
   - After displaying confirmation, run `/compact`
   - The checkpoint in the vault means even after compaction, progress is recoverable via `/pickup`
   - Display:
     ```
     Running /compact...
     ```

## What Checkpoint Does NOT Do

Unlike `/park`, checkpoint:
- **No WIP update** - session isn't ending, WIP stays as-is
- **No bidirectional links** - no "Previous session:" or "Next session:" links
- **No quality gate** - that's a closing ritual, not mid-session
- **No tier detection** - checkpoints are always worth doing properly (you don't checkpoint trivial work)

## Guidelines

- **Same format as park:** Pickup will find checkpointed sessions identically to parked ones
- **Append is fine:** Multiple checkpoints in one day create multiple sessions (Session 1, 2, 3...)
- **Keep it scannable:** Bullet points, not paragraphs
- **Explicit continuation:** Always end with "Session continues" - psychological signal
- **Compact integration:** Use `--compact` when context is heavy. Checkpoint first (vault persistence), then compact (fresh context). Best of both worlds.

## Triggers

This command should trigger when the user says:
- "checkpoint"
- "save progress"
- "plant a flag"
- "capture this"
- "don't want to lose this"
