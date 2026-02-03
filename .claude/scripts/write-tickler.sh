#!/bin/bash
# Write item to Tickler.md under a date header with flock-based locking
# Usage: write-tickler.sh <tickler-file> <date> <item>
#   date: YYYY-MM-DD format
#   item: The tickler item text (should include "- [ ] " prefix and any links)
#
# Examples:
#   ~/.claude/scripts/write-tickler.sh "$VAULT_PATH/01 Now/Tickler.md" "2026-02-09" "- [ ] Task → [[link]]"
#
# Behavior:
#   - Creates file with template if missing
#   - Creates date header if missing (inserted in chronological order)
#   - Appends item under the date header

set -euo pipefail

if [ $# -lt 3 ]; then
    echo "Usage: $0 <tickler-file> <date> <item>"
    echo "  date: YYYY-MM-DD format"
    echo "  item: Full item line including '- [ ] ' prefix"
    exit 1
fi

TICKLER_FILE="$1"
TARGET_DATE="$2"
ITEM="$3"

# Validate date format
if ! [[ "$TARGET_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "Error: Date must be YYYY-MM-DD format, got: $TARGET_DATE"
    exit 1
fi

# Derive lock file path (same directory as tickler file)
LOCK_DIR="$(dirname "$TICKLER_FILE")"
LOCK_FILE="$LOCK_DIR/.tickler-lock"

# Ensure lock directory exists
mkdir -p "$LOCK_DIR"
touch "$LOCK_FILE"

# Template for new Tickler file
read -r -d '' TEMPLATE << 'ENDTEMPLATE' || true
# Tickler

*Date-triggered reminders. Items surface in /morning and /pickup when their date arrives.*

---

## How to use

Add items under date headers (YYYY-MM-DD format). When date <= today, /morning and /pickup will surface them.

Once actioned, either:
- Delete the item (if done)
- Move to WIP (if it needs ongoing tracking)
- Reschedule (move to a future date header)

**Overdue items:** If a date passes without action, the item keeps surfacing (with "overdue" warning). Either do it, reschedule it, or delete it — do not let stale ticklers accumulate.

Empty date sections can be deleted.

---

ENDTEMPLATE

# Write with flock for atomicity
(
    flock -w 10 200 || { echo "Failed to acquire lock"; exit 1; }

    # Create file if missing
    if [ ! -f "$TICKLER_FILE" ]; then
        printf "%s\n" "$TEMPLATE" > "$TICKLER_FILE"
    fi

    # Use awk to insert item in correct place
    awk -v target="$TARGET_DATE" -v item="$ITEM" '
    BEGIN {
        in_content = 0
        found_target = 0
        inserted = 0
        last_divider_line = 0
    }

    # Track when we pass the last --- divider
    /^---$/ {
        last_divider_line = NR
    }

    # After printing each line, check if we need to insert
    {
        # Are we in the content section (after last divider)?
        # We detect this by checking if we have seen a divider and current line is after it

        # Check if this line is a date header in content section
        if (NR > last_divider_line && last_divider_line > 0 && /^## [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) {
            current_date = substr($0, 4)  # Extract YYYY-MM-DD from "## YYYY-MM-DD"

            # If this is our target date, mark it
            if (current_date == target) {
                found_target = 1
                print
                # Print the item right after the header
                print item
                inserted = 1
                next
            }

            # If this date is later than target and we have not inserted yet
            if (!inserted && current_date > target) {
                # Insert new header + item before this line
                print ""
                print "## " target
                print item
                inserted = 1
            }
        }

        print
    }

    END {
        # If we never inserted (target date is latest or no dates exist)
        if (!inserted) {
            print ""
            print "## " target
            print item
        }
    }
    ' "$TICKLER_FILE" > "$TICKLER_FILE.tmp"

    mv "$TICKLER_FILE.tmp" "$TICKLER_FILE"

) 200>"$LOCK_FILE"

echo "Tickler item added: $TARGET_DATE"
