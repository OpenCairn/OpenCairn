#!/usr/bin/env bash
# panel-run-record.sh - derive one run-index line for a cross-model panel run from its seat files,
# optionally archive the run directory into the vault and append the line to the Panel Seat Ledger.
#
# Usage:
#   panel-run-record.sh <run_dir> --skill <audit|second-opinion> --round <n> --target "<what was reviewed>"
#                       [--claude-agent <agent id>] [--claude-model <id>] [--vault <path>] [--archive]
#
# Seat files in <run_dir> (round 1: <seat>.out/.err/.time/.exit; round N>1: <seat>-rN.*), seats claude gemini codex grok.
# Derived, never typed, from the round's own files: despatched (any file for the seat in that round), returned (.out
# non-empty and .exit absent or 0), model ids (Codex: "model:" line of codex[-rN].err; Grok: usage line of grok[-rN].err;
# Gemini: gemini[-rN].model written at despatch, else ~/.gemini/settings.json tagged "(now)"; Claude: the seat's own
# transcript via --claude-agent (~/.claude/projects/*/<session>/subagents/agent-<id>.jsonl: model field, and wall seconds
# from the timestamps after the previously recorded round's end, kept in <run_dir>/.claude-rN.transcript-end), else
# claude[-rN].json (Codex lane), else claude[-rN].model, else --claude-model), wall seconds (.time, or the transcript /
# usage line), Grok cost, and whether the round's synthesis (synthesis.md for round 1, synthesis-rN.md for round N>1, with
# synthesis.md taken in its place under a warning) is present. A round-N model file falls back to its round-1 file;
# wall seconds never do. A despatched seat whose .out is missing or empty, or whose .exit is non-zero, is left out of
# `returned:` and named in a stderr warning; when no seat returned the line is still written and the exit status is 2.
# The line carries NO findings: if the seat question is reopened, code from the archived seat files, not from the synthesis.
#
# --archive copies <run_dir> to <vault>/06 Archive/OpenCairn/Panel Runs/<date>-<hhmmss>-<session8>-r<n>/ (never merging
# into an existing directory). Round N>1 copies only its -rN files into the round-1 archive named in <run_dir>/.archive-path,
# else into the newest round-1 archive of this session that holds no round-N files yet, else into a new -rN directory holding
# the whole run directory; a round N>1 without synthesis-rN.md has synthesis.md archived as synthesis-rN.md, never over the
# archived round-1 copy. Files keep their names and extensions (archives written before 2026-10-15 hold .md files renamed
# .txt: read synthesis.txt there). Directory choice and copy run under the lock <vault>/06 Archive/OpenCairn/.Panel Runs.lock
# (lib-lock.sh, the canonical lock path for the Panel Runs directory). The line is then appended to
# <vault>/07 System/Panel Seat Ledger.md under lock (created atomically with a header if missing). Every run is archived
# and indexed, whatever the seat count: the line carries despatched and returned, and the coder filters.
# Platform: Linux, macOS, Windows (Git Bash). Needs python3.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/lib-session.sh"
source "$HERE/lib-lock.sh"
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
NORET=0
RECORD="$(RUN_DIR="$RUN_DIR" SKILL="$SKILL" ROUND="$ROUND" TARGET="$TARGET" CLAUDE_MODEL="$CLAUDE_MODEL" CLAUDE_AGENT="$CLAUDE_AGENT" SID="$SID" SID8="$SID8" DATE="$DATE" python3 - <<'PY'
import os, re, sys, json, glob, collections, datetime
rd=os.environ['RUN_DIR']; r=int(os.environ['ROUND']); suf='' if r==1 else f'-r{r}'
seats=['claude','gemini','codex','grok']; cap={'claude':'Claude','gemini':'Gemini','codex':'Codex','grok':'Grok'}
def f(seat,ext,s=suf): return os.path.join(rd, f'{seat}{s}.{ext}')
def f1(seat,ext):  # the round's file, else the round-1 file (model ids only)
    return f(seat,ext) if os.path.exists(f(seat,ext)) else f(seat,ext,'')
def rd_(p):
    try: return open(p, errors='replace').read()
    except Exception: return ''
desp=[s for s in seats if any(os.path.exists(f(s,e)) for e in ('out','err','time','exit','json'))]
def not_returned(s):  # '' when the seat returned, else the reason naming the file
    if not os.path.exists(f(s,'out')): return f"{os.path.basename(f(s,'out'))} missing"
    if os.path.getsize(f(s,'out'))==0: return f"{os.path.basename(f(s,'out'))} empty"
    ex=rd_(f(s,'exit')).strip(); return '' if ex in ('','0') else f"{os.path.basename(f(s,'exit'))} {ex}"
ret=[]
for s in desp:
    why=not_returned(s)
    if why: print(f"warning: {cap[s]} seat despatched, not returned ({why})", file=sys.stderr)
    else: ret.append(s)
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
gm=rd_(f1('gemini','model')).strip()
if gm: models['gemini']=gm
else:
    try: models['gemini']=(json.load(open(os.path.expanduser('~/.gemini/settings.json'))).get('model',{}).get('name') or 'gemini-default')+'(now)'
    except Exception: models['gemini']='gemini-default(now)'
cm=''
aid=os.environ.get('CLAUDE_AGENT'); sid=os.environ.get('SID')
if aid and sid:
    for p in glob.glob(os.path.expanduser(f'~/.claude/projects/*/{sid}/subagents/agent-{aid}.jsonl')):
        def iso(t): return datetime.datetime.fromisoformat(t.replace('Z','+00:00'))
        c=collections.Counter(); ts=[]
        for line in open(p, errors='replace'):
            try: o=json.loads(line)
            except Exception: continue
            msg=o.get('message') if isinstance(o,dict) else None
            if isinstance(msg,dict) and msg.get('role')=='assistant' and msg.get('model'): c[msg['model']]+=1
            if isinstance(o,dict) and o.get('timestamp'):
                try: ts.append(iso(o['timestamp']))
                except Exception: pass
        if c: cm=c.most_common(1)[0][0]
        # A resumed seat's transcript spans every round: this round starts after the previous recorded round's end.
        prev=rd_(os.path.join(rd, f'.claude-r{r-1}.transcript-end')).strip() if r>1 else ''
        if prev:
            try: ts=[t for t in ts if t>iso(prev)]
            except Exception: pass
        if ts:
            if wall.get('claude','?')=='?': wall['claude']=str(int((ts[-1]-ts[0]).total_seconds()))
            try: open(os.path.join(rd, f'.claude-r{r}.transcript-end'),'w').write(ts[-1].isoformat()+'\n')
            except Exception: pass
if not cm:
    try:
        cj=json.load(open(f1('claude','json'))); cm=cj.get('model') or ''
        if not cm and isinstance(cj.get('modelUsage'),dict) and cj['modelUsage']: cm=next(iter(cj['modelUsage']))
    except Exception: pass
cm=cm or rd_(f1('claude','model')).strip() or os.environ.get('CLAUDE_MODEL') or 'unknown'
models['claude']=cm
own=os.path.join(rd, 'synthesis.md' if r==1 else f'synthesis-r{r}.md')
if os.path.exists(own): synth='yes'
elif r>1 and os.path.exists(os.path.join(rd,'synthesis.md')):
    synth='yes'; print(f"warning: no synthesis-r{r}.md in {rd}; synthesis.md taken as round {r}'s synthesis (archived as synthesis-r{r}.md)", file=sys.stderr)
else:
    synth='no'; print(f"warning: no synthesis for round {r} in {rd}; write the synthesis and terminal state there before recording", file=sys.stderr)
def lst(xs): return ' '.join(cap[s] for s in xs) if xs else 'none'
line=(f"- {os.environ['DATE']} | {os.environ['SKILL']} | run {os.environ['SID8']} | round {r} | target: {os.environ['TARGET']} | "
      f"despatched: {lst(desp)} | returned: {lst(ret)} | models: " + (' '.join(f"{cap[s]}={models[s]}" for s in desp) or 'none') +
      " | wall s: " + (' '.join(f"{cap[s]} {wall[s]}" for s in desp) or 'none') + f" | grok {cost if 'grok' in desp else 'none'} | synthesis: {synth}")
print(line)
if not ret:
    print(f"error: no seat returned for round {r} in {rd}; the line is still recorded, exit 2", file=sys.stderr); sys.exit(3)
PY
)" || { rc=$?; [[ $rc -eq 3 ]] && NORET=1 || exit "$rc"; }
EVIDENCE="$RUN_DIR"
if [[ $ARCHIVE -eq 1 ]]; then
  [[ -n "$VAULT" && -d "$VAULT" ]] || { echo "--archive needs a vault: pass --vault or set VAULT_PATH" >&2; echo "$RECORD | evidence: $RUN_DIR"; exit 1; }
  if [[ -x "$HERE/check-archive-layout.sh" ]] && ! "$HERE/check-archive-layout.sh" --enforce "$VAULT" >/dev/null 2>&1; then
    echo "archive layout gate failed (check-archive-layout.sh --enforce); not archiving" >&2; echo "$RECORD | evidence: $RUN_DIR"; exit 1
  fi
  RUNS_REL="06 Archive/OpenCairn/Panel Runs"; RUNS="$VAULT/$RUNS_REL"; mkdir -p "$RUNS"
  _lock "$(_lock_path_for "$RUNS")" 10 || { echo "archive lock busy: $RUNS; not archiving" >&2; echo "$RECORD | evidence: $EVIDENCE"; exit 1; }
  MARK="$RUN_DIR/.archive-path"; JOIN=""
  if [[ "$ROUND" -gt 1 ]]; then
    if [[ -f "$MARK" && -d "$VAULT/$(cat "$MARK")" ]]; then JOIN="$(cat "$MARK")"
    elif [[ "$SID8" != "unknown" ]]; then
      # Marker lost: the newest round-1 archive of this session that holds no round-N files yet.
      for d in "$RUNS"/*-"$SID8"-r1 "$RUNS"/*-"$SID8"-r1-*; do
        [[ -d "$d" ]] || continue
        if ! compgen -G "$d/*-r$ROUND.*" >/dev/null; then JOIN="$RUNS_REL/$(basename "$d")"; fi
      done
    fi
  fi
  if [[ -n "$JOIN" ]]; then
    EVIDENCE="$JOIN"; DEST="$VAULT/$EVIDENCE"
    find "$RUN_DIR" -maxdepth 1 -name "*-r$ROUND.*" -exec cp -a {} "$DEST"/ \;
    [[ ! -e "$RUN_DIR/synthesis-r$ROUND.md" && -f "$RUN_DIR/synthesis.md" ]] && cp -a "$RUN_DIR/synthesis.md" "$DEST/synthesis-r$ROUND.md"
  else
    STAMP="$(date +%H%M%S)"; BASE="$RUNS_REL/$DATE-$STAMP-$SID8-r$ROUND"; EVIDENCE="$BASE"; n=1
    while [[ -e "$VAULT/$EVIDENCE" ]]; do EVIDENCE="$BASE-$n"; n=$((n+1)); done   # never merge into an existing archive
    DEST="$VAULT/$EVIDENCE"; mkdir -p "$DEST"
    cp -a "$RUN_DIR"/. "$DEST"/
    [[ "$ROUND" -gt 1 ]] && echo "note: no round-1 archive of this session found; round $ROUND archived whole to $EVIDENCE" >&2
  fi
  printf '%s\n' "$EVIDENCE" > "$MARK"
  _unlock
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
[[ $NORET -eq 0 ]] || exit 2
