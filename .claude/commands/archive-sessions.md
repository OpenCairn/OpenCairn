---
name: archive-sessions
description: Organise old session files into year-based subdirectories - keeps archive manageable at scale
parameters:
  - "--older-than=N" - Archive sessions older than N days (default: 90)
  - "--year=YYYY" - Archive specific year's sessions
  - "--dry-run" - Show what would be moved without actually moving
---

# Archive Sessions - Session File Organization

You are organising the user's session archive. As sessions accumulate (1000+ files after 2 years), flat directory structure becomes unwieldy. This command moves old sessions into year-based subdirectories.

## Philosophy

Session files should be easily accessible while actively relevant (last 90 days), then organised by year for long-term retrieval. This balances:
- **Recent access:** Last 3 months flat in main directory (fast pickup scanning)
- **Long-term organization:** Older sessions in year folders (manageable, searchable)
- **Link preservation:** Obsidian links remain valid (relative paths work)

## Instructions

1. **Check current date** using bash `date` command:
   - Get current date: `date +"%Y-%m-%d"`
   - Calculate cutoff date based on `--older-than=N` parameter (default: 90 days)
   - Store for comparison

2. **Parse parameters:**
   - `--older-than=N`: Archive sessions older than N days (default: 90)
   - `--year=YYYY`: Archive all sessions from specific year (overrides --older-than)
   - `--dry-run`: Show moves without executing

3. **Scan session files:**
   - List all files in `06 Archive/Claude Sessions/`
   - Filter to `YYYY-MM-DD.md` pattern (exclude subdirectories)
   - For each file:
     - Extract date from filename
     - Compare to cutoff date or target year
     - Mark for archival if older than threshold

4. **Create year directories:**
   - For each year found in files-to-archive:
     - Create directory: `06 Archive/Claude Sessions/YYYY/`
     - Use `mkdir -p` (safe if exists)

5. **Move files** (or display if dry-run):
   - For each file marked for archival:
     - Source: `06 Archive/Claude Sessions/YYYY-MM-DD.md`
     - Destination: `06 Archive/Claude Sessions/YYYY/YYYY-MM-DD.md`
     - If dry-run: Display "Would move: [source] → [dest]"
     - If live: Move file
   - Preserve file permissions and timestamps

6. **Update daily/weekly review links** (optional, advanced):
   - Scan daily reviews and weekly syntheses
   - Update links from `[[06 Archive/Claude Sessions/YYYY-MM-DD#...]]`
   - To: `[[06 Archive/Claude Sessions/YYYY/YYYY-MM-DD#...]]`
   - **Note:** This is optional - Obsidian often finds moved files automatically

7. **Display summary:**

**Dry-run output:**
```
Archive Sessions - Dry Run
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Threshold: Sessions older than 90 days (before 2025-10-18)

Would move:
  2024:
    - 2024-12-15.md → 06 Archive/Claude Sessions/2024/
    - 2024-12-16.md → 06 Archive/Claude Sessions/2024/
    ... (127 files)

  2025 (through October):
    - 2025-01-01.md → 06 Archive/Claude Sessions/2025/
    - 2025-01-02.md → 06 Archive/Claude Sessions/2025/
    ... (289 files)

Total: 416 files to archive

To execute: /archive-sessions (without --dry-run)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Live output:**
```
Archive Sessions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Threshold: Sessions older than 90 days (before 2025-10-18)

Archiving sessions...
  Created: 06 Archive/Claude Sessions/2024/
  Created: 06 Archive/Claude Sessions/2025/

  Moved 127 files to 2024/
  Moved 289 files to 2025/

✓ Total archived: 416 files
✓ Directories: 06 Archive/Claude Sessions/2024/, 2025/
✓ Recent sessions (last 90 days): 47 files remain in main directory

Archive complete.

Note: Obsidian links should auto-update. If any links break, search
for the session file name and Obsidian will find it in the new location.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Guidelines

- **90-day threshold recommended:** Keeps 3 months of recent sessions accessible for pickup
- **Year-based folders:** `2024/`, `2025/`, etc. Simple and chronological
- **Obsidian link resilience:** Links use relative paths, work even after moving files
- **Dry-run first:** Always show preview before actual move, especially first time
- **Non-destructive:** Moves files, doesn't delete anything
- **Idempotent:** Safe to run multiple times (already-archived files skipped)

## When to Use This Command

**Use when:**
- Session directory has 300+ files (navigation becomes unwieldy)
- End of year (archive previous year's sessions for clean start)
- Preparing for long-term storage or backup
- Want to separate "archive" from "recent" sessions

**Don't use when:**
- Less than 90 days of sessions (not much benefit)
- Actively referencing old sessions (wait until work complete)

**Recommended frequency:**
- Annually (archive previous year at start of new year)
- Or as needed when directory exceeds 500 files

## Integration

- **Pickup command:** Still scans main directory + subdirectories (transparent to user)
- **Search:** Obsidian search works across all locations
- **Links:** Relative paths preserve links after move
- **Backup:** Cleaner structure for backup/sync tools

## Example Usage

```bash
# Preview what would be archived
/archive-sessions --dry-run

# Archive sessions older than 90 days
/archive-sessions

# Archive specific year
/archive-sessions --year=2024

# Custom threshold (6 months)
/archive-sessions --older-than=180

# Preview specific year
/archive-sessions --year=2023 --dry-run
```

## Technical Notes

**File patterns matched:**
- `YYYY-MM-DD.md` (e.g., `2024-12-15.md`)
- Already in subdirectories are skipped

**Directories created:**
- `06 Archive/Claude Sessions/YYYY/`

**Link format preserved:**
- `[[06 Archive/Claude Sessions/YYYY-MM-DD#Session 1]]` (old)
- `[[06 Archive/Claude Sessions/YYYY/YYYY-MM-DD#Session 1]]` (new)
- Obsidian auto-updates or finds via search

**Safety:**
- Uses `mv` (not `rm`), files never deleted
- Creates backups if concerned: `cp` before `mv`
- Dry-run available for validation

This keeps the archive manageable as it grows to thousands of sessions over years.
