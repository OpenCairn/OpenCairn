#!/usr/bin/env python3
"""Passive park timing from local transcripts; explicit close-out/review annotations.

No idle-gap estimate, transcript text export, network, or inferred human effort.
See park-metrics-guide.md for boundaries and interpretation.
"""
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone, timedelta
try:
    import fcntl
except ImportError:  # Windows: no fcntl; metrics writes run unlocked there
    fcntl = None
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import tempfile

VERSION = 6
SLOW_MINUTES, WAIT_MINUTES = 30, 60


def stamp():
    return datetime.now(timezone.utc).isoformat()


def epoch(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def text(content):
    if isinstance(content, str):
        return content
    return '\n'.join(x.get('text', '') for x in (content or []) if isinstance(x, dict))


def prompt_mode(value):
    value = value.strip()
    if re.match(r'<skill>\s*<name>park</name>', value):
        return 'full'
    if re.fullmatch(r'[$/]park(?:\s+[^\n]*)?', value):
        return 'quick-requested' if value.split()[1:] == ['--quick'] else 'full'
    # Command envelope after prose typed before /park: the envelope's own tags
    # start their lines. A quoted mention sits inside backticks or mid-sentence.
    unquoted = re.sub(r'`[^`]*`', '', value)
    if re.search(r'(?m)^<command-name>/park</command-name>', unquoted):
        args = re.search(r'(?m)^<command-args>(.*?)</command-args>', unquoted, re.S)
        return 'quick-requested' if args and args[1].strip() == '--quick' else 'full'
    return None


def skill_mode(name, args):
    # Claude Code expands /park through the Skill tool when it follows prose.
    if name != 'Skill' or not isinstance(args, dict) or args.get('skill') != 'park':
        return None
    return 'quick-requested' if str(args.get('args') or '').strip() == '--quick' else 'full'


def user_text(value):
    # Injected skills, context, task notifications and tool results aren't requests.
    return bool(value.strip()) and not value.lstrip().startswith('<')


def parked(value):
    return bool(re.search(r'(?im)^\s*(?:\*\*)?(?:quick )?parked\b|✓\s*Merged into Session', value))


def extract(path, harness, since):
    rows, errors, active = [], [], None
    sid = path.stem
    turn = None
    seen_calls = set()
    models = set()
    current_model = None
    latest_ts = None
    last_request = None  # (ts, line) of the most recent genuine user request
    total = invalid = 0

    def start(ts, number, mode):
        nonlocal active, seen_calls, models
        if epoch(ts) < epoch(since):
            return
        rid = hashlib.sha256(f'{harness}:{sid}:{ts}'.encode()).hexdigest()[:16]
        active = dict(id=rid, harness=harness, session_id=sid, transcript=str(path),
                      start_line=number, started_at=ts, ended_at=None, wall_seconds=None,
                      mode=mode, status='no_completion_observed', boundary=None,
                      tool_calls=0, tool_error_results=0, prepare_calls=0)
        active['_turn'] = msg.get('internal_chat_message_metadata_passthrough', {}).get('turn_id', turn)
        seen_calls = set()
        models = {current_model} if current_model else set()

    def close():
        nonlocal active
        if active:
            active['models'] = sorted(models)
            if active['ended_at']:
                active['wall_seconds'] = round(epoch(active['ended_at']) - epoch(active['started_at']), 3)
            rows.append(active)
            active = None

    # Undecodable bytes become replacement characters, so a line cut mid-character is a parse error, not a crash.
    with path.open(encoding='utf-8', errors='replace') as stream:
        for number, line in enumerate(stream, 1):
            total += 1
            try:
                e = json.loads(line)
                bad = None if isinstance(e, dict) else 'not a JSON object'
            except json.JSONDecodeError:
                bad = 'invalid JSON'
            if bad:
                # Only the final line can lack its newline: a transcript mid-write or cut short.
                tail = not line.endswith('\n')
                invalid += not tail
                errors.append({'path': str(path), 'line': number,
                               'kind': 'incomplete_final_line' if tail else 'invalid_line',
                               'error': 'incomplete final line (transcript mid-write or cut short)' if tail else bad})
                continue
            ts = e.get('timestamp')
            if not ts:
                continue
            latest_ts = max(latest_ts or ts, ts)
            p = e.get('payload', {})
            kind = e.get('type')
            if harness == 'codex' and kind == 'session_meta':
                sid = p.get('id', p.get('session_id', sid))
                if isinstance(p.get('source'), dict) and 'subagent' in p['source']:
                    return [], errors
            if harness == 'codex' and kind == 'event_msg' and p.get('type') == 'task_started':
                turn = p.get('turn_id')
            if harness == 'codex' and kind == 'turn_context':
                current_model = p.get('model', current_model)
            if e.get('isSidechain'):
                continue
            msg = e.get('message', {}) if harness == 'claude' else p
            role = e.get('type') if harness == 'claude' else p.get('role')
            content = msg.get('content', [])
            request = None
            if harness == 'claude' and role == 'user' and not e.get('isMeta') and not e.get('isCompactSummary'):
                if not (isinstance(content, list) and any(x.get('type') == 'tool_result' for x in content if isinstance(x, dict))):
                    request = text(content)
            elif harness == 'codex' and kind == 'response_item' and p.get('type') == 'message' and role == 'user':
                request = text(content)
            elif harness == 'codex' and kind == 'event_msg' and p.get('type') == 'user_message':
                request = p.get('message', '')
            if request is not None:
                mode = prompt_mode(request)
                if (mode and request.lstrip().startswith('<skill>') and active
                        and active['ended_at'] is None and active['_turn'] == turn):
                    continue  # expansion of the already observed park request
                # Some Codex versions emit both user-message representations.
                if mode and active and epoch(ts) - epoch(active['started_at']) < 2 and active['tool_calls'] == 0:
                    continue
                if mode or user_text(request):
                    close()
                    last_request = (ts, number)
                if mode:
                    start(ts, number, mode)
            if harness == 'claude' and role == 'assistant' and isinstance(content, list):
                for x in content:
                    mode = skill_mode(x.get('name'), x.get('input')) if x.get('type') == 'tool_use' else None
                    if not mode:
                        continue
                    if active and active['ended_at'] is None:
                        break  # expansion of the already observed park request
                    close()
                    # The run starts at the user request that produced the invocation.
                    start(*(last_request or (ts, number)), mode)
                    break
            if not active:
                continue
            if harness == 'codex' and kind == 'turn_context' and p.get('model'):
                models.add(p['model'])
            if harness == 'claude' and role == 'assistant' and msg.get('model'):
                models.add(msg['model'])
            calls = []
            if harness == 'claude' and role == 'assistant' and isinstance(content, list):
                calls = [(x.get('id'), x.get('name'), x.get('input', {})) for x in content if x.get('type') == 'tool_use']
            if harness == 'codex' and kind == 'response_item' and p.get('type') in ('function_call', 'custom_tool_call'):
                calls = [(p.get('call_id', p.get('id')), p.get('name'), p.get('arguments', p.get('input', '')))]
            for cid, name, args in calls:
                if cid in seen_calls:
                    continue
                seen_calls.add(cid)
                active['tool_calls'] += 1
                argstr = args if isinstance(args, str) else json.dumps(args)
                if name in ('Bash', 'exec', 'exec_command') and re.search(r'python3[^\n;]*park-(?:review\.py[^\n;]*\bprepare\b|prepare\.py[^\n;]*--vault)', argstr):
                    active['prepare_calls'] += 1
            if harness == 'claude' and role == 'user' and isinstance(content, list):
                active['tool_error_results'] += sum(bool(x.get('is_error')) for x in content if x.get('type') == 'tool_result')
            if harness == 'codex' and kind == 'response_item' and p.get('type') in ('function_call_output', 'custom_tool_call_output'):
                # Only explicit tool error flags; shell exit codes inside text are not inferred.
                active['tool_error_results'] += int(bool(p.get('is_error')))
            final = None
            if harness == 'codex' and kind == 'event_msg' and p.get('type') in ('task_complete', 'task_completed'):
                if not active['_turn'] or p.get('turn_id') == active['_turn']:
                    final = p.get('last_agent_message', '')
                    active['boundary'] = 'task_complete'
            elif harness == 'codex' and kind == 'response_item' and role == 'assistant' and p.get('phase') == 'final':
                final = text(content)
                active['boundary'] = 'final_response'
            elif harness == 'claude' and role == 'assistant' and msg.get('stop_reason') == 'end_turn' and text(content):
                # Keep the LAST final response, including async audit continuations,
                # until a genuine new user request. Never close on an idle gap.
                final = text(content)
                active['boundary'] = 'end_turn'
            if final is not None:
                active['ended_at'] = ts
                active['end_line'] = number
                active['status'] = 'parked' if parked(final) else 'response_returned'
    close()
    for row in rows:
        row.pop('_turn', None)
    # A source with no readable event is dated by its modification time instead.
    latest = epoch(latest_ts) if latest_ts else path.stat().st_mtime
    if not rows and latest < epoch(since):
        errors = []  # Corruption wholly outside the requested event-date window.
    elif invalid > total - invalid:
        # The parser cannot read this source: one bounded entry, and the only kind that fails collection.
        errors = [{'path': str(path), 'line': next(e['line'] for e in errors if e['kind'] == 'invalid_line'),
                   'kind': 'unreadable_source',
                   'error': f'unreadable source: {invalid} of {total} lines are invalid JSON'}]
    # Malformed data invalidates measurements from this file, not silently zero errors.
    if errors:
        for row in rows:
            row['parse_incomplete'] = True
    return rows, errors


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        mask = os.umask(0)
        os.umask(mask)
        mode = 0o666 & ~mask
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.metrics-')
    os.fchmod(fd, mode)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, indent=2)
            out.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read(path, fallback):
    return json.loads(path.read_text()) if path.exists() else fallback


@contextmanager
def locked(state):
    state.mkdir(parents=True, exist_ok=True)
    with (state / '.lock').open('a') as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def sources(claude, codex):
    # Top-level sessions only: reviewer transcripts must not become parent runs.
    return [('claude', p) for p in sorted((claude / 'projects').glob('*/*.jsonl'))] + [
        ('codex', p) for sub in ('sessions', 'archived_sessions') for p in sorted((codex / sub).rglob('*.jsonl'))]


def carry(cache, present):
    """Cached entries a re-parse cannot rebuild: their source is no longer on disk."""
    kept = {}
    for key, entry in cache.get('files', {}).items():
        if key in present or not entry.get('rows'):
            continue
        # Row fields are unchanged since schema 5; a bump that changes them migrates here.
        if cache.get('version') != VERSION:
            entry.setdefault('carried_from_schema', cache.get('version'))
            for row in entry['rows']:
                row.setdefault('carried_from_schema', cache.get('version'))
        entry['fingerprint'] = None  # a source that returns is parsed afresh
        kept[key] = entry
    return kept


def collect(args):
    with locked(args.state):
        cache = read(args.state / 'cache.json', {})
        files = sources(args.claude_root, args.codex_root)
        current = {str(p) for _, p in files}
        if cache.get('version') != VERSION or cache.get('since') != args.since:
            # Sources on disk are parsed again below; measurements of removed ones exist only here.
            cache = {'version': VERSION, 'since': args.since, 'files': carry(cache, current)}
        changed = 0
        for harness, path in files:
            stat = path.stat()
            fingerprint = [stat.st_size, stat.st_mtime_ns]
            old = cache['files'].get(str(path), {})
            # mtime is a cache invalidator only; event timestamps define inclusion.
            if old.get('fingerprint') == fingerprint and not old.get('errors'):
                continue
            rows, errors = extract(path, harness, args.since)
            cache['files'][str(path)] = dict(fingerprint=fingerprint, rows=rows, errors=errors, harness=harness)
            changed += 1
        # The window check applies to carried rows: a parse already leaves out earlier requests.
        rows = [r for data in cache['files'].values() for r in data['rows']
                if epoch(r['started_at']) >= epoch(args.since)]
        unique = {r['id']: r for r in rows}
        annotations = read(args.state / 'annotations.json', {})
        for row in unique.values():
            row['source_present'] = row['transcript'] in current
            row['reported'] = annotations.get(row['id'], {})
        counts = {h: sum(kind == h for kind, _ in files) for h in ('claude', 'codex')}
        missing = [h for h in args.require_harness if not counts[h]]
        errors = [e for key, v in cache['files'].items() if key in current for e in v['errors']]
        unreadable = sorted({e['path'] for e in errors if e['kind'] == 'unreadable_source'})
        data = dict(schema=VERSION, collected_at=stamp(), since=args.since,
                    sources_by_harness=counts, missing_required_harnesses=missing,
                    files_detected=len(files), files_reparsed=changed,
                    errors=errors, unreadable_sources=unreadable,
                    runs=sorted(unique.values(), key=lambda r: r['started_at']))
        atomic(args.state / 'cache.json', cache)
        atomic(args.state / 'runs.json', data)
        print(json.dumps({k: v for k, v in data.items() if k != 'runs'}))
        print(f"Runs: {len(data['runs'])}; data: {args.state / 'runs.json'}")
        # An incomplete final line or an isolated invalid line is reported above and
        # marks its runs parse_incomplete; it cannot be repaired by rerunning, so it
        # does not fail the run. An unreadable source means the parser is not reading
        # that transcript at all.
        return bool(unreadable or missing or not files)


def annotate(args):
    with locked(args.state):
        data = read(args.state / 'runs.json', {'runs': []})
        rows = data['runs']
        if args.run_id:
            selected = [r for r in rows if r['id'] == args.run_id]
        else:
            sid = args.session_id or os.environ.get('CLAUDE_CODE_SESSION_ID' if args.harness == 'claude' else 'CODEX_THREAD_ID')
            # Parse the current transcript directly: no dependency on timer freshness.
            selected = []
            for harness, p in sources(args.claude_root, args.codex_root):
                if harness == args.harness and sid and sid in p.name:
                    found, errors = extract(p, harness, '1970-01-01T00:00:00+00:00')
                    if errors:
                        raise ValueError('Current transcript has parse errors; retry after its write completes')
                    selected.extend(found)
            selected = sorted(selected, key=lambda r: r['started_at'])[-1:]
        if len(selected) != 1:
            raise ValueError('No unique park run found; use a run ID from the report or supply the actual harness session ID')
        row = selected[0]
        fields = {key: getattr(args, key) for key in ('review_rounds', 'correction_rounds', 'confirmed_findings',
                  'human_review_minutes', 'human_corrections', 'outcome') if getattr(args, key) is not None}
        if not fields:
            raise ValueError('Supply at least one measurement; missing values are not zero')
        annotations = read(args.state / 'annotations.json', {})
        entry = annotations.setdefault(row['id'], {})
        entry.update(fields)
        entry['recorded_at'] = stamp()
        atomic(args.state / 'annotations.json', annotations)
        out = {'run_id': row['id'], 'reported': entry}
        if not args.run_id:
            # Close-out reading, request to this command; the collector measures to the final response.
            out['elapsed_minutes'] = round((datetime.now(timezone.utc).timestamp() - epoch(row['started_at'])) / 60, 1)
        print(json.dumps(out))


def collected(args):
    data = read(args.state / 'runs.json', None)
    if data is None:
        raise ValueError('No collection yet; run collect')
    kinds = {}
    for e in data['errors']:
        kind = e.get('kind', 'unclassified')
        kinds[kind] = kinds.get(kind, 0) + 1
    detail = ' (' + ', '.join(f'{k} {n}' for k, n in sorted(kinds.items())) + ')' if kinds else ''
    return data, f"Collected {data['collected_at']}; window from {data['since']}; parse errors {len(data['errors'])}{detail}"


def p90(values):
    return sorted(values)[math.ceil(.9*len(values))-1]


def iso_week(day):
    year, number, _ = day.isocalendar()
    return f'{year}-W{number:02d}'


def summary(args):
    if args.weeks < 1:
        raise ValueError('--weeks must be at least 1')
    data, header = collected(args)
    last = args.until or date.today()
    monday = last - timedelta(days=last.weekday())
    weeks = [iso_week(monday - timedelta(weeks=i)) for i in range(args.weeks)]  # newest first
    age = datetime.now(timezone.utc).timestamp() - epoch(data['collected_at'])
    if age > 86400:
        header += f'; STALE: collected {age/86400:.0f} days ago'
    first = datetime.combine(monday - timedelta(weeks=args.weeks-1), datetime.min.time()).timestamp()
    if epoch(data['since']) > first:
        header += f'; collection window starts after {weeks[-1]} began: early weeks incomplete'
    timed, waits = {}, {}
    skipped = {'quick': 0, 'returned or unfinished': 0, 'parse-incomplete': 0}
    for r in data['runs']:
        key = (iso_week(datetime.fromtimestamp(epoch(r['started_at']))), r['harness'])
        if key[0] not in weeks:
            continue
        if r['mode'] != 'full':
            skipped['quick'] += 1
        elif r['status'] != 'parked' or r['wall_seconds'] is None:
            skipped['returned or unfinished'] += 1
        elif r.get('parse_incomplete'):
            skipped['parse-incomplete'] += 1
        elif r['wall_seconds'] > WAIT_MINUTES * 60:
            waits[key] = waits.get(key, 0) + 1
        else:
            timed.setdefault(key, []).append(r['wall_seconds']/60)
    print(header)
    print('Parked full runs by ISO week (local time), newest first; minutes')
    for week in weeks:
        cells = []
        for harness in ('claude', 'codex'):
            values, over = timed.get((week, harness), []), waits.get((week, harness), 0)
            if values:
                cells.append(f'{harness}: n {len(values)}, median {statistics.median(values):.1f}, p90 {p90(values):.1f}, '
                             f'>={SLOW_MINUTES} min {sum(v >= SLOW_MINUTES for v in values)}, over {WAIT_MINUTES} min {over}')
            elif over:
                cells.append(f'{harness}: n 0, over {WAIT_MINUTES} min {over}')
        label = week + (' (to date)' if week == iso_week(date.today()) else '')
        print(' | '.join([label] + (cells or ['no parked full runs'])))
    print(f'Runs over {WAIT_MINUTES} min include waits and are counted apart: n, median, p90 and >={SLOW_MINUTES} min cover '
          f'runs of {WAIT_MINUTES} min or less. Also outside these figures: ' + '; '.join(f'{k} {n}' for k, n in skipped.items()) + '.')


def report(args):
    data, header = collected(args)
    annotations = read(args.state / 'annotations.json', {})
    print(header)
    print(f"Sources: {data.get('sources_by_harness', {})}; missing required: {data.get('missing_required_harnesses', [])}")
    print('id | harness | start | wall min | boundary/status | review rounds | fixes | human min')
    for r in data['runs']:
        a = annotations.get(r['id'], {})
        wall = '-' if r['wall_seconds'] is None else f"{r['wall_seconds']/60:.1f}"
        print(f"{r['id']} | {r['harness']} | {r['started_at']} | {wall} | {r['boundary']}/{r['status']} | {a.get('review_rounds', '?')} | {a.get('confirmed_findings', '?')} | {a.get('human_review_minutes', '?')}")
    for harness in ('claude', 'codex'):
        for mode in ('full', 'quick-requested'):
            eligible = [r for r in data['runs'] if r['harness'] == harness and r['mode'] == mode and not r.get('parse_incomplete') and r['status'] == 'parked' and r['wall_seconds'] is not None]
            values = [r['wall_seconds']/60 for r in eligible]
            measured = sum('review_rounds' in annotations.get(r['id'], {}) for r in eligible)
            human = sum('human_review_minutes' in annotations.get(r['id'], {}) for r in eligible)
            if values:
                print(f'{harness}/{mode}: {len(values)} explicit parked responses; median {statistics.median(values):.1f} min; p90 {p90(values):.1f} min; review counts {measured}/{len(values)}; human minutes {human}/{len(values)}')
    print('Unknown (?) is not zero. Returned/unfinished and parse-incomplete runs excluded from timing summary. No causal speedup claim.')


def nonnegative(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError('must be finite and nonnegative')
    return number


def count(value):
    number = nonnegative(value)
    if not number.is_integer():
        raise argparse.ArgumentTypeError('must be a whole number')
    return int(number)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, default=Path.home()/'.local/state/opencairn/park-metrics')
    p.add_argument('--claude-root', type=Path, default=Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home()/'.claude')))
    p.add_argument('--codex-root', type=Path, default=Path(os.environ.get('CODEX_HOME', Path.home()/'.codex')))
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('collect')
    c.add_argument('--since', default=(datetime.now(timezone.utc)-timedelta(days=30)).date().isoformat()+'T00:00:00+00:00')
    c.add_argument('--require-harness', action='append', choices=['claude', 'codex'], default=[])
    sub.add_parser('report')
    s = sub.add_parser('summary')
    s.add_argument('--weeks', type=int, default=4)
    s.add_argument('--until', type=date.fromisoformat, help='last day covered, YYYY-MM-DD (default today)')
    a = sub.add_parser('record')
    a.add_argument('--run-id')
    a.add_argument('--session-id')
    a.add_argument('--harness', choices=['claude', 'codex'])
    for name in ('review-rounds', 'correction-rounds', 'confirmed-findings', 'human-corrections'):
        a.add_argument('--'+name, type=count)
    a.add_argument('--human-review-minutes', type=nonnegative)
    a.add_argument('--outcome', choices=['completed', 'blocked', 'aborted'])
    args = p.parse_args()
    try:
        return {'collect': collect, 'record': annotate, 'report': report, 'summary': summary}[args.command](args) or 0
    except (ValueError, OSError) as exc:
        p.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
