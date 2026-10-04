#!/usr/bin/env bash
# Add forward link ("Next session:" or "Continued in:") to a previous session's Pickup Context
# Usage: add-forward-link.sh [--continued-in] <session-file> <prev-session-num> <new-session-num> <new-session-topic> [<target-date-file>]
#
# --continued-in: Insert a "Continued in:" link instead of "Next session:".
#                 Use when a later session continues work from a non-adjacent earlier session.
#
# <target-date-file> is the session file where the NEW session lives (for cross-day links).
# If omitted, assumes same file as <session-file> (same-day link).
#
# Examples:
#   # Same-day link:
#   add-forward-link.sh "06 Archive/OpenCairn/Session Logs/2025-03-15.md" 5 6 "API Refactor"
#   # Cross-day link (prev session on Mar 15, new session on Mar 16):
#   add-forward-link.sh "06 Archive/OpenCairn/Session Logs/2025-03-15.md" 5 1 "Morning Check-in" "2025-03-16.md"
#   # Continued-in link (Session 3 continues work from Session 1):
#   add-forward-link.sh --continued-in "06 Archive/OpenCairn/Session Logs/2025-03-15.md" 1 3 "API Refactor Part 2"
#
# Platform: Linux, macOS, Windows (Git Bash). Uses flock where available, mkdir-based fallback otherwise.
# Internal read-only modes: --verify-receipt <receipt> <file>, --find-proof <file> <session-id>.

set -euo pipefail

# --- Portable file locking (shared library) ---
source "$(dirname "$0")/lib-lock.sh"
source "$(dirname "$0")/lib-session.sh"

# Shared read-only proof validation used by both Park harnesses.
if [ "${1:-}" = "--verify-receipt" ] || [ "${1:-}" = "--find-proof" ]; then
    python3 - "$@" <<'PY'
import hashlib, json, os, pathlib, re, sys
def sha(data): return hashlib.sha256(data).hexdigest()
def check(condition):
    if not condition: raise ValueError("invalid forward-link proof")
def validate(receipt, target, current=True):
    receipt_bytes = receipt.read_bytes()
    item = json.loads(receipt_bytes)
    check(item['schema'] == 1 and item['kind'] == 'forward-link')
    check(pathlib.Path(item['target']).resolve() == target.resolve())
    pre = pathlib.Path(item['pre_snapshot']).read_bytes()
    check(sha(pre) == item['pre_sha256'])
    prev, new = item['source_session_number'], item['target_session_number']
    check(type(prev) is int and prev > 0 and type(new) is int and new > 0)
    topic = item['topic']; check('\n' not in topic and '\r' not in topic)
    date = item['target_date']; check(re.fullmatch(r'\d{4}-\d{2}-\d{2}', date))
    label = {'next':'Next session','continued':'Continued in'}[item['link_type']]
    line = f'**{label}:** [[06 Archive/OpenCairn/Session Logs/{date}]] (Session {new} - {topic})\n'.encode()
    check(item['inserted_line'].encode() == line)
    lines = pre.splitlines(keepends=True)
    starts = [i for i,v in enumerate(lines) if re.match(rb'^## Session '+str(prev).encode()+rb' - ',v)]
    check(len(starts) == 1)
    start = starts[0]
    end = next((i for i in range(start+1,len(lines)) if lines[i].startswith(b'## Session ')),len(lines))
    metadata = [i for i in range(start,end) if re.match(rb'^\*\*(Project|Continues|Previous session|For next session|Next session|Continued in):\*\*',lines[i])]
    check(metadata or lines[start].rstrip().endswith(b'[Q]'))
    if not lines[start].rstrip().endswith(b'[Q]'):
        pickup=[i for i in range(start,end) if lines[i].rstrip()==b'### Pickup Context']
        check(len(pickup)==1 and max(metadata)>pickup[0])
    offset = sum(map(len,lines[:max(metadata)+1 if metadata else start+3]))
    post = pre[:offset]+line+pre[offset:]
    check(item['insertion_offset'] == offset and sha(post) == item['post_sha256'])
    if current: check(target.read_bytes() == post)
    target_log = target.parent / (date+'.md')
    check(str(target_log.resolve()) == item['target_log'])
    check(len(re.findall(rb'^## Session '+str(new).encode()+rb' - ',target_log.read_bytes(),re.M))==1)
    item['receipt_path'] = str(receipt.resolve())
    item['receipt_sha256'] = sha(receipt_bytes)
    return item
try:
    if sys.argv[1] == '--verify-receipt':
        check(len(sys.argv) == 4)
        result = validate(pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3]))
    else:
        check(len(sys.argv) == 4 and re.fullmatch(r'[A-Za-z0-9._-]+',sys.argv[3]))
        target = pathlib.Path(sys.argv[2]).resolve(); sid = sys.argv[3]
        state = pathlib.Path(os.environ.get('CLAUDE_CONFIG_DIR',pathlib.Path.home()/'.claude'))/'.session-state'
        ledger = state/(sid+'.tsv')
        rows = [v.split('\t') for v in ledger.read_text().splitlines()]
        matched = [r for r in rows if len(r)>=3 and pathlib.Path(r[2]).resolve()==target]
        # A last-operation proof cannot excuse earlier meaning-bearing writes.
        check(bool(matched) and all(len(r)==4 and r[1]=='add-forward-link' for r in matched))
        proofs = []
        for receipt in (state/(sid+'.forward-link-receipts')).glob('*.json'):
            try:
                candidate=validate(receipt,target,current=False)
                check(candidate['session_id']==sid)
                proofs.append(candidate)
            except (AssertionError,KeyError,ValueError,OSError): pass
        check(len(proofs)==len(matched))
        edges={p['pre_sha256']:p for p in proofs}
        check(len(edges)==len(proofs))
        posts={p['post_sha256'] for p in proofs}
        heads=[p for p in proofs if p['pre_sha256'] not in posts]
        check(len(heads)==1)
        chain=[]; cursor=heads[0]['pre_sha256']
        while cursor in edges:
            proof=edges.pop(cursor);chain.append(proof);cursor=proof['post_sha256']
        check(not edges and cursor==sha(target.read_bytes()))
        result={'kind':'forward-link-chain','receipts':chain,
            'pre_snapshot':chain[0]['pre_snapshot'],'pre_sha256':chain[0]['pre_sha256'],
            'post_sha256':chain[-1]['post_sha256'],
            'inserted_line':''.join(p['inserted_line'] for p in chain)}
    print(json.dumps(result))
except (AssertionError,KeyError,ValueError,OSError) as exc:
    print('Forward-link proof unavailable or changed; use normal coverage.',file=sys.stderr)
    raise SystemExit(1)
PY
    exit $?
fi

# Parse --continued-in flag
LINK_TYPE="next"
if [ "${1:-}" = "--continued-in" ]; then
    LINK_TYPE="continued"
    shift
fi

if [ $# -lt 4 ]; then
    echo "Usage: $0 [--continued-in] <session-file> <prev-session-num> <new-session-num> <new-session-topic> [<target-date-file>]"
    exit 1
fi

SESSION_FILE="$1"
PREV_NUM="$2"
NEW_NUM="$3"
NEW_TOPIC="$4"
TARGET_DATE_FILE="${5:-}"

# Validate file exists
if [ ! -f "$SESSION_FILE" ]; then
    echo "Session file not found: $SESSION_FILE"
    exit 1
fi

# Derive the lock file path (same directory as session file)
LOCK_DIR="$(dirname "$SESSION_FILE")"
LOCK_FILE="$LOCK_DIR/.lock"

# Build the link text
# If target date file provided (cross-day link), use that for the date part.
# Otherwise derive from the source file (same-day link).
if [ -n "$TARGET_DATE_FILE" ]; then
    DATE_PART="$(basename "$TARGET_DATE_FILE" .md)"
else
    DATE_PART="$(basename "$SESSION_FILE" .md)"
fi
if [ "$LINK_TYPE" = "continued" ]; then
    NEW_SESSION_LINK="**Continued in:** [[06 Archive/OpenCairn/Session Logs/${DATE_PART}]] (Session ${NEW_NUM} - ${NEW_TOPIC})"
else
    NEW_SESSION_LINK="**Next session:** [[06 Archive/OpenCairn/Session Logs/${DATE_PART}]] (Session ${NEW_NUM} - ${NEW_TOPIC})"
fi

# Acquire lock
_lock "$LOCK_FILE" 10 || { echo "Failed to acquire lock" >&2; exit 1; }

# Find previous session heading
PREV_HEADING=$({ grep -n "^## Session ${PREV_NUM} - " "$SESSION_FILE" || true; } | head -1 | cut -d: -f1)
if [ -z "$PREV_HEADING" ]; then
    echo "Could not find Session ${PREV_NUM} heading"
    _unlock
    exit 1
fi

# Find session block boundaries
NEXT_HEADING=$(tail -n +$((PREV_HEADING + 1)) "$SESSION_FILE" | { grep -n "^## Session " || true; } | head -1 | cut -d: -f1)
if [ -n "$NEXT_HEADING" ]; then
    END_LINE=$((PREV_HEADING + NEXT_HEADING - 1))
else
    END_LINE=$(wc -l < "$SESSION_FILE")
fi

# Guard: Check if this specific link type already exists
if [ "$LINK_TYPE" = "continued" ]; then
    GUARD_PATTERN="^\*\*Continued in:\*\*.*Session ${NEW_NUM} - "
    GUARD_MSG="Continued in link to Session ${NEW_NUM} already exists, skipping"
else
    GUARD_PATTERN="^\*\*Next session:\*\*"
    GUARD_MSG="Session ${PREV_NUM} already has a Next session link, skipping"
fi
if sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | grep -q "$GUARD_PATTERN"; then
    echo "$GUARD_MSG"
    _unlock
    exit 0
fi

# Check if this is a Quick session (single line with [Q] marker)
SESSION_LINE=$(sed -n "${PREV_HEADING}p" "$SESSION_FILE")
if echo "$SESSION_LINE" | grep -q "\[Q\]$"; then
    # Quick session format:
    #   Line N:   ## Session X - Topic (time) [Q]
    #   Line N+1: (blank)
    #   Line N+2: Summary text
    #   Line N+3: **Previous session:** ... (optional)
    #
    # Find the last metadata line or insert after summary if no metadata
    INSERT_AFTER=$(sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | \
        { grep -n "^\*\*\(Project\|Continues\|Previous session\|For next session\|Next session\|Continued in\):\*\*" || true; } | tail -1 | cut -d: -f1)

    if [ -n "$INSERT_AFTER" ]; then
        INSERT_LINE=$((PREV_HEADING + INSERT_AFTER - 1))
    else
        INSERT_LINE=$((PREV_HEADING + 2))
    fi
else
    # Full session: find the last Pickup Context metadata line
    INSERT_AFTER=$(sed -n "${PREV_HEADING},${END_LINE}p" "$SESSION_FILE" | \
        { grep -n "^\*\*\(Project\|Continues\|Previous session\|For next session\|Next session\|Continued in\):\*\*" || true; } | tail -1 | cut -d: -f1)

    if [ -z "$INSERT_AFTER" ]; then
        echo "Could not find insertion point in Session ${PREV_NUM}"
        _unlock
        exit 1
    fi
    INSERT_LINE=$((PREV_HEADING + INSERT_AFTER - 1))
fi

# Preserve original file permissions (GNU stat on Linux/Git Bash, BSD stat on macOS)
ORIG_PERMS=$(stat -c '%a' "$SESSION_FILE" 2>/dev/null || stat -f '%Lp' "$SESSION_FILE" 2>/dev/null || echo "644")
PROOF_PRE=$(mktemp "${TMPDIR:-/tmp}/opencairn-forward-pre.XXXXXX")
cp "$SESSION_FILE" "$PROOF_PRE"

# Insert the forward link using awk (more robust than sed append)
# Use ENVIRON instead of -v to avoid backslash interpretation in topic names
export _AWK_LINE="$INSERT_LINE"
export _AWK_TEXT="$NEW_SESSION_LINK"
awk '
    NR == ENVIRON["_AWK_LINE"]+0 { print; print ENVIRON["_AWK_TEXT"]; next }
    { print }
' "$SESSION_FILE" > "${SESSION_FILE}.tmp" && mv "${SESSION_FILE}.tmp" "$SESSION_FILE"
unset _AWK_LINE _AWK_TEXT

# Restore permissions if they changed
chmod "$ORIG_PERMS" "$SESSION_FILE"

# Capture exact producer bytes while the existing session-directory lock holds.
# Proof/ledger failure is bookkeeping failure, never a failed landed insertion.
if ! python3 - "$PROOF_PRE" "$SESSION_FILE" "$(_session_id)" \
    "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.session-state" "$PREV_NUM" "$NEW_NUM" \
    "$NEW_TOPIC" "$LINK_TYPE" "$DATE_PART" "$NEW_SESSION_LINK" "$INSERT_LINE" \
    "$(_session_agent_id)" "${VAULT_PATH:-}" <<'PY'
import datetime, hashlib, json, os, pathlib, re, sys, uuid
def check(condition):
    if not condition: raise ValueError("invalid forward-link proof")
pre_path,target,sid,state,prev,new,topic,kind,date,line,index,agent,vault=sys.argv[1:]
if not sid: raise SystemExit(0)
check(re.fullmatch(r'[A-Za-z0-9._-]+',sid))
target=pathlib.Path(target).resolve(); state=pathlib.Path(state).resolve()
check(bool(vault) and not state.is_relative_to(pathlib.Path(vault).resolve()))
pre=pathlib.Path(pre_path).read_bytes(); post=target.read_bytes()
digest=lambda data:hashlib.sha256(data).hexdigest()
directory=state/(sid+'.forward-link-receipts'); directory.mkdir(parents=True,exist_ok=True)
snapshot=directory/(digest(pre)+'.snapshot')
if snapshot.exists(): check(snapshot.read_bytes()==pre)
else: snapshot.write_bytes(pre)
record={'schema':1,'kind':'forward-link','session_id':sid,'target':str(target),
    'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'pre_snapshot':str(snapshot),'pre_sha256':digest(pre),'post_sha256':digest(post),
    'source_session_number':int(prev),'target_session_number':int(new),
    'topic':topic,'link_type':kind,'target_date':date,'target_log':str((target.parent/(date+'.md')).resolve()),
    'inserted_line':line+'\n','insertion_offset':sum(map(len,pre.splitlines(keepends=True)[:int(index)]))}
path=directory/(uuid.uuid4().hex+'.json'); temporary=path.with_suffix('.tmp')
temporary.write_text(json.dumps(record,indent=2)+'\n');os.replace(temporary,path)
field=str(target).replace('\t',' ').replace('\n',' ').replace('\r',' ')
with (state/(sid+'.tsv')).open('a') as ledger:
    ledger.write(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')+'\tadd-forward-link\t'+field+'\t'+agent+'\n')
print('Forward-link receipt: '+str(path))
PY
then
    echo "WARNING: forward link landed without proof; use normal coverage" >&2
fi
rm -f "$PROOF_PRE"

_unlock

echo "Forward link added to Session ${PREV_NUM} -> Session ${NEW_NUM}"
