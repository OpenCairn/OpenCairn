#!/usr/bin/env bash
# Deterministic compatibility gate for the shared-agent archive namespace.
#
# Usage:
#   check-archive-layout.sh [--status|--enforce] [VAULT]
#
# --status prints one machine-readable state and always exits 0.
# --enforce (default) exits non-zero unless new-layout workflows are safe.

set -euo pipefail

ARCHIVE_BUNDLE_VERSION=3 # archive-bundle-v3

MODE="--enforce"
if [[ "${1:-}" == "--status" || "${1:-}" == "--enforce" ]]; then
    MODE="$1"
    shift
fi

VAULT="${1:-${VAULT_PATH:-}}"
if [[ -z "$VAULT" || ! -d "$VAULT" ]]; then
    echo "ARCHIVE_LAYOUT=invalid-vault"
    [[ "$MODE" == "--status" ]] && exit 0
    echo "OpenCairn could not resolve the vault. Set VAULT_PATH to the vault root." >&2
    exit 24
fi

OLD_DIR="$VAULT/06 Archive/Claude"
NEW_DIR="$VAULT/06 Archive/OpenCairn"
OLD_LOCATOR_PATTERN='06 Archive/Claude(?=/|$|["'"'"'\]})>,;:])'
OLD_WINDOWS_LOCATOR_PATTERN='06 Archive\\Claude(?=\\|$|["'"'"'\]})>,;:])'
JOURNAL="$VAULT/07 System/.OpenCairn Migration/archive-namespace-opencairn-v1.json"
MIGRATION_HELPER="$(dirname "$0")/archive-namespace-migration.py"
LEGACY_LOCATOR_EXEMPT_MARKER='<!-- opencairn: legacy-locator-exempt -->'

legacy_files() {
    local roots=()
    local root
    local output
    local search_rc
    for root in "01 Now" "02 Inbox" "03 Projects" "04 Areas" \
        "05 Resources" "06 Archive" "07 System"; do
        [[ -e "$VAULT/$root" ]] && roots+=("$root")
    done
    [[ ${#roots[@]} -eq 0 ]] && return 0

    set +e
    output=$(
        cd "$VAULT"
        primary_output=$(rg -l --hidden --no-ignore -P \
            -e "$OLD_LOCATOR_PATTERN" -e "$OLD_WINDOWS_LOCATOR_PATTERN" "${roots[@]}" \
            -g '*.md' \
            -g '*.md.*' \
            -g '*.bak' \
            -g '*.backup' \
            -g '*.canvas' \
            -g '*.sh' \
            -g '*.py' \
            -g '*.json' \
            -g '*.toml' \
            -g '*.yaml' \
            -g '*.yml' \
            -g '*.txt' \
            -g '*.csv' \
            -g '*.tsv' \
            -g '*.tex' \
            -g '*.html' \
            -g '*.css' \
            -g '*.js' \
            -g '*.ini' \
            -g '*.conf' \
            -g '*.xml' \
            -g '*.org' \
            -g '*.svg' \
            -g '*.ipynb' \
            -g '!06 Archive/Claude/.Session Transcripts/**' \
            -g '!06 Archive/OpenCairn/.Session Transcripts/**' \
            -g '!07 System/.Provenance/**' \
            -g '!07 System/.OpenCairn Migration/**' \
            -g '!07 System/Migration Record.md' \
            -g '!*.lock')
        primary_rc=$?
        if [[ $primary_rc -ne 0 && $primary_rc -ne 1 ]]; then
            exit "$primary_rc"
        fi
        while IFS= read -r candidate; do
            [[ -z "$candidate" ]] && continue
            if ! rg -qF -- "$LEGACY_LOCATOR_EXEMPT_MARKER" "$candidate"; then
                printf '%s\n' "$candidate"
            fi
        done <<< "$primary_output"
        while IFS= read -r -d '' candidate; do
            set +e
            rg -q --text -U '\x00' -- "$candidate"
            nul_rc=$?
            if [[ $nul_rc -eq 0 ]]; then
                candidate_rc=1
            elif [[ $nul_rc -eq 1 ]]; then
                rg -q -P -e "$OLD_LOCATOR_PATTERN" -e "$OLD_WINDOWS_LOCATOR_PATTERN" -- "$candidate"
                candidate_rc=$?
            else
                candidate_rc=$nul_rc
            fi
            set -e
            if [[ $candidate_rc -eq 0 ]]; then
                if ! rg -qF -- "$LEGACY_LOCATOR_EXEMPT_MARKER" "$candidate"; then
                    printf '%s\n' "$candidate"
                fi
            elif [[ $candidate_rc -ne 1 ]]; then
                exit "$candidate_rc"
            fi
        done < <(
            find "${roots[@]}" -type f ! -name '?*.*' \
                ! -path '06 Archive/Claude/.Session Transcripts/*' \
                ! -path '06 Archive/OpenCairn/.Session Transcripts/*' \
                ! -path '07 System/.Provenance/*' \
                ! -path '07 System/.OpenCairn Migration/*' \
                ! -path '07 System/Migration Record.md' \
                -print0
        )
    )
    search_rc=$?
    set -e
    if [[ $search_rc -ne 0 && $search_rc -ne 1 ]]; then
        echo "OpenCairn legacy-locator search failed (rg exit $search_rc)." >&2
        return 1
    fi
    [[ -n "$output" ]] && printf '%s\n' "$output"
    return 0
}

if ! LEGACY_OUTPUT=$(legacy_files); then
    echo "ARCHIVE_LAYOUT=indeterminate"
    echo "ACTIONABLE_LEGACY_FILES=unknown"
    [[ "$MODE" == "--status" ]] && exit 0
    exit 24
fi
if [[ -n "$LEGACY_OUTPUT" ]]; then
    LEGACY_COUNT=$(printf '%s\n' "$LEGACY_OUTPUT" | LC_ALL=C sort -u | wc -l | tr -d ' ')
else
    LEGACY_COUNT=0
fi

if [[ -L "$NEW_DIR" ]]; then
    STATE="new-symlink-unsafe"
elif [[ -L "$OLD_DIR" ]]; then
    if [[ -d "$NEW_DIR" && "$OLD_DIR" -ef "$NEW_DIR" ]]; then
        STATE="legacy-symlink-alias"
    else
        STATE="legacy-symlink-unsafe"
    fi
elif [[ -d "$OLD_DIR" && -d "$NEW_DIR" ]]; then
    STATE="split"
elif [[ -d "$OLD_DIR" ]]; then
    STATE="old-only"
elif [[ -d "$NEW_DIR" ]]; then
    if [[ "$LEGACY_COUNT" -gt 0 ]]; then STATE="new-with-legacy-locators"; else STATE="new-only"; fi
else
    if [[ "$LEGACY_COUNT" -gt 0 ]]; then STATE="empty-with-legacy-locators"; else STATE="empty-clean"; fi
fi

JOURNAL_PHASE="absent"
if [[ -f "$JOURNAL" ]]; then
    set +e
    JOURNAL_PHASE=$("$MIGRATION_HELPER" journal-phase "$VAULT")
    journal_rc=$?
    set -e
    if [[ $journal_rc -ne 0 ]]; then
        JOURNAL_PHASE="invalid"
        STATE="indeterminate"
    elif [[ "$STATE" == "new-only" || "$STATE" == "empty-clean" ]] \
        && [[ "$JOURNAL_PHASE" != "complete" ]]; then
        STATE="pending-verification"
    elif [[ "$STATE" == "empty-clean" && "$JOURNAL_PHASE" == "complete" ]]; then
        STATE="indeterminate"
        VERIFY_OUTPUT='completed archive migration journal exists but 06 Archive/OpenCairn is missing'
        [[ "$MODE" == "--enforce" ]] && printf '%s\n' "$VERIFY_OUTPUT" >&2
    elif [[ "$STATE" == "new-only" && "$JOURNAL_PHASE" == "complete" ]]; then
        set +e
        VERIFY_OUTPUT=$("$MIGRATION_HELPER" verify-immutable "$VAULT" 2>&1)
        verify_rc=$?
        set -e
        if [[ $verify_rc -ne 0 ]]; then
            STATE="indeterminate"
            [[ "$MODE" == "--enforce" ]] && printf '%s\n' "$VERIFY_OUTPUT" >&2
        fi
    fi
fi

echo "ARCHIVE_LAYOUT=$STATE"
echo "ACTIONABLE_LEGACY_FILES=$LEGACY_COUNT"
echo "MIGRATION_JOURNAL_PHASE=$JOURNAL_PHASE"
[[ "$MODE" == "--status" ]] && exit 0

case "$STATE" in
    new-only|empty-clean)
        exit 0
        ;;
    old-only|new-with-legacy-locators|empty-with-legacy-locators)
        echo "OpenCairn archive migration required. Run /migrate in Claude Code or \$migrate in Codex before using this workflow." >&2
        exit 20
        ;;
    pending-verification)
        echo "OpenCairn archive migration is awaiting journal-backed verification. Run /migrate in Claude Code or \$migrate in Codex before using this workflow." >&2
        exit 20
        ;;
    split)
        echo "Both 06 Archive/Claude and 06 Archive/OpenCairn exist. Stop archive-backed work and run /migrate or \$migrate for split-archive reconciliation." >&2
        exit 21
        ;;
    legacy-symlink-alias)
        echo "06 Archive/Claude is a compatibility symlink to OpenCairn. Stop archive-backed work and run /migrate or \$migrate to retire the alias without traversing it." >&2
        exit 22
        ;;
    legacy-symlink-unsafe)
        echo "06 Archive/Claude is a symlink with an unsafe or unresolved target. Stop archive-backed work and run /migrate or \$migrate for inspection." >&2
        exit 23
        ;;
    new-symlink-unsafe)
        echo "06 Archive/OpenCairn is a symlink. Stop archive-backed work and run /migrate or \$migrate for inspection; the active archive root must remain inside the vault." >&2
        exit 23
        ;;
    *)
        echo "OpenCairn could not prove the archive layout safe. Run /migrate or \$migrate and inspect the reported journal/tool error." >&2
        exit 24
        ;;
esac
