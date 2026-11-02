#!/usr/bin/env python3
"""Read-only Park startup receipts, not final task deduplication or write approval."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

TASK_PATTERN = r'^\s*[-*+]\s+\[ \]\s'
SID_PATTERN = r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}'


def park_request(prompt):
    if not isinstance(prompt, str):
        return False
    prompt = prompt.strip()
    # One direct command line. Questions, quotations and code are not requests.
    if re.fullmatch(r'[/$](?:park|checkpoint)(?:[ \t]+--[^\n?`\'"<>]+)?', prompt):
        return True
    # Harness expansion metadata must lead the prompt, not occur in pasted prose.
    if re.match(r'^<skill>\s*<name>(?:park|checkpoint)</name>', prompt):
        return prompt.endswith('</skill>')
    match = re.match(r'^(?:<command-message>(park|checkpoint)</command-message>\s*)?'
                     r'<command-name>/(park|checkpoint)</command-name>(?:\s|$)', prompt)
    return bool(match and (not match[1] or match[1] == match[2]))


def source(path):
    if path is None:
        return {'path': None, 'state': 'unknown', 'sha256': None}
    try:
        raw = path.read_bytes()
        return {'path': str(path), 'state': 'checked',
                'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    except FileNotFoundError:
        return {'path': str(path), 'state': 'missing', 'sha256': None}
    except OSError as exc:
        return {'path': str(path), 'state': 'error', 'sha256': None, 'error': str(exc)}


def bash_executable() -> str:
    """Bash for helper scripts; on Windows prefer Git Bash over System32's WSL launcher."""
    if os.name == 'nt':
        for root in (os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'),
                     os.environ.get('LOCALAPPDATA')):
            for suffix in ('Git/bin/bash.exe', 'Programs/Git/bin/bash.exe'):
                if root and (Path(root) / suffix).is_file():
                    return str(Path(root) / suffix)
    return 'bash'


def run(argv, cwd, env, timeout):
    started = time.perf_counter()
    status, code, out, err = 'command_error', None, b'', b''
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        try:
            out, err = process.communicate(timeout=timeout)
            status = 'completed'
        except subprocess.TimeoutExpired:
            # Kill the command group too: shell children must not outlive the bound.
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
            except ProcessLookupError:
                pass
            out, err = process.communicate()
            status = 'timeout'
        code = process.returncode
    except OSError as exc:
        err = str(exc).encode('utf-8', 'backslashreplace')
    return {'argv': argv, 'cwd': str(cwd), 'status': status, 'exit_status': code,
            'stdout': out.decode('utf-8', 'backslashreplace'),
            'stderr': err.decode('utf-8', 'backslashreplace'),
            'stdout_base64': base64.b64encode(out).decode('ascii'),
            'stderr_base64': base64.b64encode(err).decode('ascii'),
            'output_bytes': len(out) + len(err),
            'milliseconds': round((time.perf_counter() - started) * 1000, 3)}


def unchanged(before, after):
    return before['state'] == after['state'] == 'checked' and before['sha256'] == after['sha256']


def bundle(cwd, env, sid, provenance, timeout):
    result = {'kind': 'park-preflight', 'session': {'id': sid, 'source': provenance},
              'final_dedup_complete': False,
              'dedup_scope': 'unchecked task candidates in fixed This Week/Tickler files only; no final loop needles or semantic review',
              'action': 'fresh_read_and_dedup_before_writing', 'dependencies': []}
    result['clock'] = {'receipt': run(['date', '+%Y-%m-%dT%H:%M:%S%z TZ=%Z'], cwd, env, timeout)}
    configured = env.get('VAULT_PATH')
    resolver = Path(configured) / '.claude/scripts/resolve-vault.sh' if configured else None
    before = source(resolver)
    receipt = run([bash_executable(), str(resolver)], cwd, env, timeout) if resolver else None
    after = source(resolver)
    result['vault'] = {'state': 'unknown', 'path': None, 'source': after, 'receipt': receipt}
    result['task_candidates'] = []
    result['ledger'] = {'state': 'unknown_vault', 'source': source(None), 'receipt': None}
    if (not receipt or receipt['status'] != 'completed' or receipt['exit_status'] != 0
            or not unchanged(before, after)):
        return result
    match = re.fullmatch(r'VAULT_PATH=(.+)\n?', receipt['stdout'])
    if not match or not Path(match[1]).is_dir():
        return result
    vault = Path(match[1]).resolve()
    result['vault'].update(state='checked', path=str(vault))
    scripts = vault / '.claude/scripts'
    result['dependencies'] = [source(scripts / name) for name in ['session-ledger.sh', 'lib-session.sh']]
    config = Path(env.get('CLAUDE_CONFIG_DIR') or str(Path.home() / '.claude'))
    ledger_path = config / '.session-state' / f'{sid}.tsv' if sid else None
    before = source(ledger_path)
    receipt = run([bash_executable(), str(scripts / 'session-ledger.sh'), '--read'], cwd, env, timeout)
    after = source(ledger_path)
    ledger_state = 'error'
    if not sid:
        ledger_state = 'unknown_session'
    elif receipt['status'] == 'completed' and receipt['exit_status'] == 0:
        if 'NOTE: no ledger for this session' in receipt['stdout'] and after['state'] == 'missing':
            ledger_state = 'no_ledger'
        elif unchanged(before, after):
            total = re.search(r'^TOTAL\t(\d+) file\(s\)\t(\d+) write\(s\)$', receipt['stdout'], re.M)
            if total:
                ledger_state = 'checked_nonempty' if int(total[2]) else 'checked_empty'
    result['ledger'] = {'state': ledger_state, 'source': after, 'receipt': receipt,
                        'session_binding': {'OPENCAIRN_SESSION_ID': sid}}
    for name in ['This Week.md', 'Tickler.md']:
        path = vault / '01 Now' / name
        before = source(path)
        receipt = run(['rg', '--hidden', '--no-ignore', '--no-heading', '--line-number',
                       '-e', TASK_PATTERN, '--', str(path)], cwd, env, timeout)
        after = source(path)
        state = 'error'
        if after['state'] == 'missing':
            state = 'missing'
        elif (unchanged(before, after) and receipt['status'] == 'completed'
                and not receipt['stderr']):
            if receipt['exit_status'] == 0 and receipt['stdout']:
                state = 'checked_nonempty'
            elif receipt['exit_status'] == 1 and not receipt['stdout']:
                state = 'checked_empty'
        result['task_candidates'].append({'state': state, 'source': after, 'receipt': receipt})
    return result


def revalidate(path):
    """This checks freshness only; matching hashes do not complete dedup."""
    result = {'kind': 'park-preflight-revalidation', 'source_hashes_match': False,
              'final_dedup_complete': False, 'action': 'fresh_read_and_dedup_before_writing',
              'invalidated_sources': []}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['kind'] != 'park-preflight' or data['vault']['state'] != 'checked':
            raise ValueError('bundle has no checked vault')
        entries = [data['vault'], data['ledger'], *data['task_candidates']]
        records = [item['source'] for item in entries] + data['dependencies']
        if len(data['task_candidates']) != 2 or not records:
            raise ValueError('bundle lacks startup surfaces')
        for record in records:
            locator = record['path']
            if record['state'] != 'checked' or not locator or not unchanged(record, source(Path(locator))):
                result['invalidated_sources'].append(locator)
        if data['ledger']['state'] not in ('checked_nonempty', 'checked_empty') or any(
                item['state'] not in ('checked_nonempty', 'checked_empty') for item in data['task_candidates']):
            result['error'] = 'startup lookup was not fully checked'
        else:
            result['source_hashes_match'] = not result['invalidated_sources']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result['error'] = str(exc)
    return result


def bounded(value, limit=240):
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[:limit] + '...'


def summary(data, receipt_path, raw):
    """Bounded status fields only; the complete receipt stays in the file."""
    def command(receipt):
        if not receipt:
            return None
        return {'status': receipt['status'], 'exit_status': receipt['exit_status'],
                'output_bytes': receipt['output_bytes']}

    def surface(entry):
        src = entry['source']
        return {'path': bounded(src['path']), 'state': entry['state'],
                'source_state': src['state'], 'sha256': src['sha256'],
                'command': command(entry.get('receipt'))}

    ledger = surface(data['ledger'])
    total = re.search(r'^TOTAL\t(\d+) file\(s\)\t(\d+) write\(s\)$',
                      (data['ledger'].get('receipt') or {}).get('stdout', ''), re.M)
    ledger['records'] = {'files': int(total[1]), 'writes': int(total[2])} if total else None
    tasks = []
    for entry in data['task_candidates']:
        item = surface(entry)
        item['records'] = len(entry['receipt']['stdout'].splitlines()) if entry.get('receipt') else None
        tasks.append(item)
    vault = data['vault']
    return {'kind': 'park-preflight-summary', 'receipt': bounded(receipt_path),
            'receipt_sha256': hashlib.sha256(raw).hexdigest(), 'receipt_bytes': len(raw),
            'session': {'id': bounded(data['session']['id']), 'source': data['session']['source']},
            'clock': bounded((data['clock']['receipt'] or {}).get('stdout', '').strip(), 80),
            'final_dedup_complete': data['final_dedup_complete'], 'action': data['action'],
            'vault': {'state': vault['state'], 'path': bounded(vault['path']),
                      'resolver_sha256': vault['source']['sha256'], 'command': command(vault['receipt'])},
            'ledger': ledger, 'task_candidates': tasks,
            'dependencies': [{'path': bounded(item['path']), 'state': item['state'], 'sha256': item['sha256']}
                             for item in data['dependencies']]}


def write_receipt(path, data, vault):
    """Write the complete bundle to a new file outside the vault; never replace one."""
    target = path.absolute()
    if vault and (target.parent.resolve() == Path(vault) or Path(vault) in target.parent.resolve().parents):
        raise ValueError(f'receipt path is inside the vault: {target}')
    raw = (json.dumps(data, ensure_ascii=True) + '\n').encode('ascii')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(raw)
    return raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual', action='store_true', help='explicit setup call, e.g. Codex first tool call')
    parser.add_argument('--session-id', help='actual parent id in manual mode')
    parser.add_argument('--cwd', type=Path, help='manual command working directory')
    parser.add_argument('--timeout', type=float, default=2.0, help='per command seconds, maximum 10')
    parser.add_argument('--revalidate', type=Path, help='check source hashes of a saved stdout bundle')
    parser.add_argument('--receipt', type=Path, help='manual mode: write the raw bundle to this new path and print a bounded summary')
    args = parser.parse_args()
    if not 0 < args.timeout <= 10:
        parser.error('timeout must be greater than zero and at most 10 seconds')
    if args.receipt and not args.manual:
        parser.error('--receipt requires --manual')
    if args.revalidate:
        print(json.dumps(revalidate(args.revalidate), ensure_ascii=True))
        return 0
    env = os.environ.copy()
    if args.manual:
        sid = args.session_id or env.get('OPENCAIRN_SESSION_ID') or env.get('CLAUDE_CODE_SESSION_ID') or env.get('CODEX_THREAD_ID') or ''
        provenance = 'manual_explicit' if args.session_id else 'manual_environment'
        cwd = (args.cwd or Path.cwd()).resolve()
    else:
        try:
            event = json.load(sys.stdin)
        except (ValueError, OSError):
            return 0
        if not isinstance(event, dict) or event.get('hook_event_name') != 'UserPromptSubmit' or not park_request(event.get('prompt')):
            return 0
        sid = event.get('session_id', '')
        provenance = 'UserPromptSubmit.session_id'
        event_cwd = event.get('cwd')
        cwd = Path(event_cwd).resolve() if isinstance(event_cwd, str) and event_cwd else Path.cwd()
    sid = sid if isinstance(sid, str) and re.fullmatch(SID_PATTERN, sid) else ''
    # Never let an inherited child/other session replace the actual event parent.
    for name in ('OPENCAIRN_SESSION_ID', 'CLAUDE_CODE_SESSION_ID', 'CODEX_THREAD_ID'):
        env.pop(name, None)
    if sid:
        env['OPENCAIRN_SESSION_ID'] = sid
    data = bundle(cwd, env, sid, provenance, args.timeout)
    if args.manual and args.receipt:
        try:
            raw = write_receipt(args.receipt, data, data['vault']['path'])
        except (OSError, ValueError) as exc:
            print(f'ERROR: receipt not written: {exc}', file=sys.stderr)
            return 2
        output = summary(data, args.receipt.absolute(), raw)
    elif args.manual:
        output = data
    else:
        output = {'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit',
                  'additionalContext': 'Park startup receipts (not final dedup):\n' + json.dumps(data, ensure_ascii=True)}}
    print(json.dumps(output, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
