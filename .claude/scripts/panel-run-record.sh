#!/usr/bin/env bash
# panel-run-record.sh - derive one run-index line for a cross-model panel run from its seat files,
# optionally archive the run directory into the vault and append the line to the Panel Seat Ledger.
#
# Usage:
#   panel-run-record.sh <run_dir> --skill <audit|second-opinion> --round <n> --target "<what was reviewed>"
#                       [--claude-agent <agent id>] [--claude-model <id>] [--vault <path>] [--archive]
#
# Seat files in <run_dir> (round 1: <seat>.out/.err/.time/.exit; round N>1: <seat>-rN.*), seats claude gemini codex grok.
# Derived, never typed: despatched (any file for the seat), returned (.out non-empty and .exit absent or 0),
# model ids (Codex: "model:" line of codex.err, falling back to round 1; Grok: usage line of grok.err;
# Gemini: <run_dir>/gemini.model written at despatch, else ~/.gemini/settings.json tagged "(now)";
# Claude: the seat's own transcript via --claude-agent (~/.claude/projects/*/<session>/subagents/agent-<id>.jsonl:
# model field and first-to-last timestamp), else claude.json (Codex lane), else claude.model, else --claude-model),
# wall seconds (.time, or the transcript / usage line), Grok cost, and whether synthesis*.md is present.
# The line carries NO findings: if the seat question is reopened, code from the archived seat files, not from the synthesis.
#
# --archive copies <run_dir> to <vault>/06 Archive/OpenCairn/Panel Runs/<date>-<hhmmss>-<session8>-r<n>/ (never merging
# into an existing directory; .md inside renamed .txt so it is not indexed as a note). Round N>1 copies its -rN files into
# the round-1 archive named in <run_dir>/.archive-path when that exists. The line is then appended to
# <vault>/07 System/Panel Seat Ledger.md under lock (created atomically with a header if missing). Every run is archived
# and indexed, whatever the seat count: the line carries despatched and returned, and the coder filters.
# Platform: Linux, macOS, Windows (Git Bash). Needs python3.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib-session.sh"
RUN_DIR=""; SKILL=""; ROUND=1; TARGET=""; CLAUDE_MODEL=""; CLAUDE_AGENT=""; VAULT="${VAULT_PATH:-}"; ARCHIVE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill) SKILL="$2"; shift 2 ;;
    --round) ROUND="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --claude-model) CLAUDE_MODEL="$2"; shift 2 ;;
    --claude-agent) CLAUDE_AGENT="$2"; shift 2 ;;
    --vault) VAULT="$2"; shift 2 ;;
    --archive) ARCHIVE=1; shift ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) if [[ -z "$RUN_DIR" ]]; then RUN_DIR="$1"; shift; else echo "Unexpected argument: $1" >&2; exit 1; fi ;;
  esac
done
[[ -d "$RUN_DIR" && -n "$SKILL" && -n "$TARGET" ]] || { echo "Usage: $0 <run_dir> --skill <audit|second-opinion> --round <n> --target \"<what>\" [--claude-agent <id>] [--claude-model <id>] [--vault <path>] [--archive]" >&2; exit 1; }
TARGET="${TARGET//|//}"
SID="$(_session_id)"; SID8="${SID:0:8}"; [[ -n "$SID8" ]] || SID8="unknown"
DATE="$(date +%F)"
RECORD="$(RUN_DIR="$RUN_DIR" SKILL="$SKILL" ROUND="$ROUND" TARGET="$TARGET" CLAUDE_MODEL="$CLAUDE_MODEL" CLAUDE_AGENT="$CLAUDE_AGENT" SID="$SID" SID8="$SID8" DATE="$DATE" python3 - <<'PY'
import os, re, json, glob, collections, datetime
rd=os.environ['RUN_DIR']; r=int(os.environ['ROUND']); suf='' if r==1 else f'-r{r}'
seats=['claude','gemini','codex','grok']; cap={'claude':'Claude','gemini':'Gemini','codex':'Codex','grok':'Grok'}
def f(seat,ext,s=suf): return os.path.join(rd, f'{seat}{s}.{ext}')
def rd_(p):
    try: return open(p, errors='replace').read()
    except Exception: return ''
desp=[s for s in seats if any(os.path.exists(f(s,e)) for e in ('out','err','time','exit','json'))]
def returned(s):
    if not (os.path.exists(f(s,'out')) and os.path.getsize(f(s,'out'))>0): return False
    ex=rd_(f(s,'exit')).strip(); return ex in ('','0')
ret=[s for s in desp if returned(s)]
models={}; wall={}; cost='none'
for s in desp:
    t=rd_(f(s,'time')).strip(); wall[s]=t if re.fullmatch(r'\d+',t) else '?'
m=re.search(r'^model:\s*(\S+)', rd_(f('codex','err')), re.M) or re.search(r'^model:\s*(\S+)', rd_(f('codex','err','')), re.M)
models['codex']=m.group(1) if m else 'unknown'
g=None
for line in rd_(f('grok','err')).splitlines():
    mm=re.match(r'^grok\s+(\S+)\s+([\d.]+)s\s+\$([\d.]+)', line.strip())
    if mm: g=mm
if g:
    models['grok']=g.group(1); cost=f'${float(g.group(3)):.3f}'
    if wall.get('grok','?')=='?': wall['grok']=str(round(float(g.group(2))))
else: models['grok']='unknown'
gm=rd_(os.path.join(rd,'gemini.model')).strip()
if gm: models['gemini']=gm
else:
    try: models['gemini']=(json.load(open(os.path.expanduser('~/.gemini/settings.json'))).get('model',{}).get('name') or 'gemini-default')+'(now)'
    except Exception: models['gemini']='gemini-default(now)'
cm=''
aid=os.environ.get('CLAUDE_AGENT'); sid=os.environ.get('SID')
if aid and sid:
    for p in glob.glob(os.path.expanduser(f'~/.claude/projects/*/{sid}/subagents/agent-{aid}.jsonl')):
        c=collections.Counter(); ts=[]
        for line in open(p, errors='replace'):
            try: o=json.loads(line)
            except Exception: continue
            msg=o.get('message') if isinstance(o,dict) else None
            if isinstance(msg,dict) and msg.get('role')=='assistant' and msg.get('model'): c[msg['model']]+=1
            if isinstance(o,dict) and o.get('timestamp'): ts.append(o['timestamp'])
        if c: cm=c.most_common(1)[0][0]
        if ts and wall.get('claude','?')=='?':
            try:
                d=datetime.datetime.fromisoformat(ts[-1].replace('Z','+00:00'))-datetime.datetime.fromisoformat(ts[0].replace('Z','+00:00'))
                wall['claude']=str(int(d.total_seconds()))
            except Exception: pass
if not cm:
    try:
        cj=json.load(open(f('claude','json'))); cm=cj.get('model') or ''
        if not cm and isinstance(cj.get('modelUsage'),dict) and cj['modelUsage']: cm=next(iter(cj['modelUsage']))
    except Exception: pass
cm=cm or rd_(os.path.join(rd,'claude.model')).strip() or os.environ.get('CLAUDE_MODEL') or 'unknown'
models['claude']=cm
synth='yes' if glob.glob(os.path.join(rd,'synthesis*')) else 'no'
def lst(xs): return ' '.join(cap[s] for s in xs) if xs else 'none'
line=(f"- {os.environ['DATE']} | {os.environ['SKILL']} | run {os.environ['SID8']} | round {r} | target: {os.environ['TARGET']} | "
      f"despatched: {lst(desp)} | returned: {lst(ret)} | models: " + (' '.join(f"{cap[s]}={models[s]}" for s in desp) or 'none') +
      " | wall s: " + (' '.join(f"{cap[s]} {wall[s]}" for s in desp) or 'none') + f" | grok {cost if 'grok' in desp else 'none'} | synthesis: {synth}")
print(line)
PY
)"
EVIDENCE="$RUN_DIR"
if [[ $ARCHIVE -eq 1 ]]; then
  [[ -n "$VAULT" && -d "$VAULT" ]] || { echo "--archive needs a vault: pass --vault or set VAULT_PATH" >&2; echo "$RECORD | evidence: $RUN_DIR"; exit 1; }
  if [[ -x "$HERE/check-archive-layout.sh" ]] && ! "$HERE/check-archive-layout.sh" --enforce "$VAULT" >/dev/null 2>&1; then
    echo "archive layout gate failed (check-archive-layout.sh --enforce); not archiving" >&2; echo "$RECORD | evidence: $RUN_DIR"; exit 1
  fi
  ! ls "$RUN_DIR"/synthesis* >/dev/null 2>&1 && echo "warning: no synthesis*.md in $RUN_DIR; write the synthesis and terminal state there before recording" >&2
  MARK="$RUN_DIR/.archive-path"
  if [[ "$ROUND" -gt 1 && -f "$MARK" && -d "$VAULT/$(cat "$MARK")" ]]; then
    EVIDENCE="$(cat "$MARK")"; DEST="$VAULT/$EVIDENCE"
    find "$RUN_DIR" -maxdepth 1 -name "*-r$ROUND.*" -exec cp -a {} "$DEST"/ \;
    for md in "$DEST"/*-r"$ROUND".md; do [[ -e "$md" ]] && mv "$md" "${md%.md}.txt"; done
  else
    STAMP="$(date +%H%M%S)"; BASE="06 Archive/OpenCairn/Panel Runs/$DATE-$STAMP-$SID8-r$ROUND"; EVIDENCE="$BASE"; n=1
    while [[ -e "$VAULT/$EVIDENCE" ]]; do EVIDENCE="$BASE-$n"; n=$((n+1)); done   # never merge into an existing archive
    DEST="$VAULT/$EVIDENCE"; mkdir -p "$DEST"
    cp -a "$RUN_DIR"/. "$DEST"/
    for md in "$DEST"/*.md; do [[ -e "$md" ]] && mv "$md" "${md%.md}.txt"; done
    printf '%s\n' "$EVIDENCE" > "$MARK"
  fi
  LEDGER="$VAULT/07 System/Panel Seat Ledger.md"
  HEADER='# Panel Seat Ledger

One index line per cross-model panel run, appended by `panel-run-record.sh` from the archived seat files under `06 Archive/OpenCairn/Panel Runs/`. If the seat question is reopened, code from those files, not from a synthesis. Fields: date | skill | run <session id> | round | target | despatched | returned | models | wall s | grok cost | synthesis present | evidence path.

## Ledger
'
  if [[ ! -f "$LEDGER" ]]; then
    if ! printf '%s\n%s\n' "$HEADER" "$RECORD | evidence: $EVIDENCE" | "$HERE/locked-edit.sh" "$LEDGER" --replace-whole MISSING >/dev/null 2>&1; then
      printf '%s\n' "$RECORD | evidence: $EVIDENCE" | "$HERE/locked-edit.sh" "$LEDGER" --append >/dev/null   # someone created it first; just append
    fi
  else
    printf '%s\n' "$RECORD | evidence: $EVIDENCE" | "$HERE/locked-edit.sh" "$LEDGER" --append >/dev/null
  fi
fi
echo "$RECORD | evidence: $EVIDENCE"
