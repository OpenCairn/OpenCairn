#!/usr/bin/env python3
"""Batch Claude Park backfill, verification and audit-input assembly."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

MAX_INLINE = 65536


def fail(message):
    raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def resolve(raw, vault):
    p = Path(raw).expanduser()
    return (p if p.is_absolute() else vault / p).resolve()


def session_block(text, number):
    starts = list(re.finditer(rf'^## Session {number} - .*$', text, re.M))
    if len(starts) != 1:
        fail('Expected exactly one matching session')
    start = starts[0].start()
    end = re.search(r'^## Session \d+ - ', text[starts[0].end():], re.M)
    block = text[start:starts[0].end() + end.start() if end else len(text)]
    sections = {}
    matches = list(re.finditer(r'^### (.+)$', block, re.M))
    for i, m in enumerate(matches):
        heading = m.group(1)
        if heading in sections:
            fail(f'Duplicate section: {heading}')
        sections[heading] = block[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(block)].strip()
    return block, sections


def file_rows(sections, vault, coverage):
    rows = []
    for heading in ('Files Created', 'Files Updated', 'Files Deleted'):
        for line in sections.get(heading, '').splitlines():
            if not line.startswith('- '):
                continue
            value = line[2:].strip()
            if value == 'None':
                continue
            if value.startswith('`'):
                m = re.fullmatch(r'`([^`]+)`(?: - .*)?', value)
                if not m:
                    fail(f'Malformed Files row: {line}')
                name = m.group(1)
            else:
                splits = [m.start() for m in re.finditer(' - ', value)]
                candidates = [value] + [value[:i] for i in reversed(splits)]
                name = next((x for x in candidates if x in coverage or resolve(x, vault).exists()),
                            value[:splits[-1]] if splits else value)
            kind = (coverage.get(name) or coverage.get(str(resolve(name, vault))) or {}).get('kind')
            if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*://', name) and kind != 'nonlocal':
                fail(f'Explicit nonlocal coverage required: {name}')
            key = name if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*://', name) else str(resolve(name, vault))
            if any(r['path'] == key and r['deleted'] != (heading == 'Files Deleted') for r in rows):
                fail(f'Path is both retained and deleted: {name}')
            if not any(r['path'] == key for r in rows):
                rows.append({'path': key, 'raw': name, 'deleted': heading == 'Files Deleted'})
    return rows


def validate_handoff(data):
    allowed = {'backfill', 'identifiers', 'coverage', 'evidence', 'prestate', 'propagation'}
    if not isinstance(data, dict) or set(data) - allowed:
        fail('Unknown handoff fields')
    if not isinstance(data.get('propagation'), str) or not data['propagation'].strip():
        fail('Supply the real propagation report or checked-nil result')
    for key in allowed - {'propagation'}:
        if not isinstance(data.get(key, []), list):
            fail(f'{key} must be a list')
    for key in ('backfill', 'identifiers'):
        for value in data.get(key, []):
            if not isinstance(value, str) or not value.strip() or '\n' in value or '\r' in value:
                fail(f'Invalid {key} entry')
            if key == 'backfill' and not value.startswith('- '):
                fail('Backfill entries must be Files-list rows')
    coverage = {}
    for item in data.get('coverage', []):
        if not isinstance(item, dict) or set(item) - {'path', 'kind', 'receipt', 'targets'}:
            fail('Invalid coverage entry')
        if not isinstance(item.get('path'), str) or not item['path'] or item['path'] in coverage:
            fail('Coverage paths must be nonempty and unique')
        if item.get('kind') not in {'reference', 'large', 'nonlocal'}:
            fail('Coverage kind must be reference, large or nonlocal')
        if item['kind'] != 'nonlocal' and not isinstance(item.get('receipt'), str):
            fail('Reference/large coverage needs a park-artifact receipt')
        if not isinstance(item.get('targets', []), list) or not all(isinstance(x, str) and x.strip() for x in item.get('targets', [])):
            fail('Inspection targets must be nonempty strings')
        if item['kind'] == 'large' and not item.get('targets'):
            fail('Large semantic artefacts need explicit inspection targets')
        coverage[item['path']] = item
    for key in ('evidence', 'prestate'):
        for item in data.get(key, []):
            if not isinstance(item, dict) or set(item) - {'label', 'source', 'text', 'provenance'}:
                fail(f'Invalid {key} entry')
            if not all(isinstance(item.get(k), str) and item[k].strip() for k in ('label', 'source', 'text')):
                fail(f'{key} needs label, source and text')
            if item.get('provenance') not in {'primary', 'secondary', 'unverified'}:
                fail(f'{key} needs provenance')
    return coverage


def prepare(args, data):
    vault = Path(args.vault).expanduser().resolve(strict=True)
    log = resolve(args.session_log, vault)
    if args.number < 1 or not log.is_relative_to(vault):
        fail('Invalid session number or log outside the vault')
    coverage = validate_handoff(data)
    canonical_coverage = {}
    for name, item in coverage.items():
        key = name if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*://', name) else str(resolve(name, vault))
        if key in canonical_coverage:
            fail(f'Duplicate resolved coverage path: {name}')
        canonical_coverage[key] = item
    coverage = canonical_coverage
    session_block(log.read_text(), args.number)
    sid = os.environ.get('OPENCAIRN_SESSION_ID') or os.environ.get('CLAUDE_CODE_SESSION_ID') or os.environ.get('CODEX_THREAD_ID')
    if not sid or not re.fullmatch(r'[A-Za-z0-9._-]+', sid):
        fail('A valid harness session id is required')
    state = (Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home() / '.claude')) / '.session-state' / f'{sid}.park-prepare').resolve()
    if state.is_relative_to(vault):
        fail('Preparation output must be outside the vault')
    out = state / uuid.uuid4().hex
    out.mkdir(parents=True)
    timing = {'status': 'running', 'steps': []}
    started = time.monotonic()

    def command(name, argv, text=None):
        before = time.monotonic()
        r = subprocess.run(argv, input=text, capture_output=True, text=True,
                           env={**os.environ, 'VAULT_PATH': str(vault)})
        timing['steps'].append({'name': name, 'seconds': time.monotonic() - before, 'returncode': r.returncode})
        (out / f'{name}.txt').write_text(r.stdout + r.stderr)
        print(r.stdout, end='')
        if r.returncode:
            fail(f'{name} failed ({r.returncode}); inspect {out / (name + ".txt")}')
        return r.stdout

    try:
        if data.get('backfill'):
            command('backfill', [str(vault / '.claude/scripts/backfill-files-updated.sh'), str(log), str(args.number)], '\n'.join(data['backfill']) + '\n')
        log_bytes = log.read_bytes()
        block, sections = session_block(log_bytes.decode('utf-8'), args.number)
        rows = file_rows(sections, vault, coverage)
        used_names = {r['raw'] for r in rows} | {r['path'] for r in rows}
        if set(coverage) - used_names:
            fail('Coverage names a path absent from this session Files list')
        checks = {str(log): hashlib.sha256(log_bytes).hexdigest()}
        chunks = [f'# Audit inputs — Session {args.number}\n\nVault: `{vault}`\nLog: `{log}`\n\n## Session record\n\n{block}']
        reference_args = []
        for row in rows:
            path = Path(row['path'])
            item = coverage.get(row['raw']) or coverage.get(row['path']) or {}
            if item.get('kind') == 'nonlocal':
                chunks.append(f'## Nonlocal: {row["raw"]}\n\nReview through the supplied evidence only.')
                continue
            if row['deleted']:
                if path.exists():
                    fail(f'Deleted file still exists: {path}')
                checks[str(path)] = None
                continue
            digest = sha(path)
            checks[str(path)] = digest
            chunks.append(f'## File: {path}\n\nSHA-256: `{digest}`')
            if path == log:
                chunks.append('Review the Session record above; other sessions are outside scope.')
            elif item.get('kind') in {'reference', 'large'}:
                receipt_path = Path(item['receipt']).expanduser().resolve()
                receipt = json.loads(receipt_path.read_text())
                snapshot = Path(receipt.get('source_snapshot', ''))
                if receipt.get('source_sha256') != digest or not snapshot.is_file() or sha(snapshot) != digest:
                    fail(f'Stale artefact receipt: {path}')
                review_path = receipt.get('review_path')
                if review_path and sha(Path(review_path)) != receipt.get('review_sha256'):
                    fail(f'Stale extracted review copy: {path}')
                checks[str(receipt_path)] = sha(receipt_path)
                checks[str(snapshot)] = digest
                if review_path:
                    checks[review_path] = receipt['review_sha256']
                chunks.append('Targeted inspection only; extraction is not whole-source coverage.\n\n' + json.dumps({'receipt': receipt, 'targets': item.get('targets', [])}, ensure_ascii=False, indent=2))
                if item['kind'] == 'reference' and not path.is_relative_to(vault):
                    reference_args += ['--reference', str(path), digest]
            else:
                with path.open('rb') as f:
                    content = f.read(MAX_INLINE + 1)
                if len(content) > MAX_INLINE or b'\x00' in content or content.startswith(b'%PDF-'):
                    fail(f'Explicit large/reference/nonlocal coverage required: {path}')
                if hashlib.sha256(content).hexdigest() != digest:
                    fail(f'File changed during preparation: {path}')
                chunks.append(content.decode('utf-8'))
        argv = [str(vault / '.claude/scripts/park-verify.sh'), str(vault), str(log), str(args.number)]
        for row in rows:
            argv += ['--touched', row['path']]
            if (coverage.get(row['raw']) or coverage.get(row['path']) or {}).get('kind') == 'nonlocal':
                argv += ['--nonlocal', row['path']]
        for ident in data.get('identifiers', []):
            argv += ['--ident', ident]
        result = command('verify', argv + reference_args)
        if re.search(r'^REVIEW\b', result, re.M):
            fail('Verifier REVIEW requires triage before audit dispatch')
        if not re.search(r'^RESULT: PASS\b', result, re.M):
            fail('Verifier did not report PASS')
        chunks.append('## Propagation\n\n' + data['propagation'])
        chunks.append('## Mechanical verification\n\n' + result)
        for key in ('evidence', 'prestate'):
            for item in data.get(key, []):
                chunks.append(f'## {key}: {item["label"]}\n\n[{item["provenance"]}] {item["source"]}\n\n{item["text"]}')
        if any((sha(Path(p)) if Path(p).is_file() else None) != h for p, h in checks.items()):
            fail('Input changed during preparation; reconcile and rerun')
        packet = out / 'audit-inputs.md'
        packet.write_text('\n\n'.join(chunks).rstrip() + '\n')
        (out / 'manifest.json').write_text(json.dumps({'inputs': checks, 'packet_sha256': sha(packet), 'paths': rows}, indent=2))
        timing['status'] = 'passed'
        print(f'Audit inputs: {packet}\nSHA-256: {sha(packet)}\nPreparation passed; independent audit still required.')
        return 0
    except BaseException:
        timing['status'] = 'failed'
        raise
    finally:
        timing['seconds'] = time.monotonic() - started
        (out / 'timing.json').write_text(json.dumps(timing, indent=2))
        print(f'Preparation timing: {out / "timing.json"}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vault', required=True)
    p.add_argument('--session-log', required=True)
    p.add_argument('--number', type=int, required=True)
    args = p.parse_args()
    try:
        return prepare(args, json.load(sys.stdin))
    except (ValueError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
