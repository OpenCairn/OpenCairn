#!/usr/bin/env python3
"""Read-only content/proof-identity inspection for weekly provenance hygiene.

No annotation, upgrade, stamp, network verification or flag mutation is performed.
JSON separates content recovery from retained-evidence gaps and Bitcoin verification.
Exit 0: content recovered with no evidence gaps; 1: rows need triage; 2: input/check error.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def writer_module():
    path = Path(__file__).with_name('provenance-write.py')
    spec = importlib.util.spec_from_file_location('provenance_writer', path)
    if spec is None or spec.loader is None:
        raise ValueError('adjacent provenance-write.py is required')
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def safe_path(vault: Path, value: str) -> Path:
    path = (vault / value).resolve()
    path.relative_to(vault)
    return path


def parse_log(path: Path, writer):
    latest, invalid, invalid_status, annotations, superseded = {}, [], {}, 0, set()
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.startswith('|') or not line.rstrip().endswith('|'):
            continue
        cells = [part.strip() for part in line.strip().split('|')[1:-1]]
        header = len(cells) == 5 and cells[1:4] == ['Tag', 'File', 'SHA256']
        if cells and (header or all(re.fullmatch(r'[-: ]+', c) for c in cells)):
            continue
        if len(cells) != 5:
            invalid.append({'line': number, 'content_state': 'INVALID', 'error': 'expected five provenance table cells'})
            continue
        timestamp, tag, file, raw_hash, raw_status = cells
        match = re.fullmatch(r'`([0-9a-f]{16})`', raw_hash)
        if not match:
            invalid.append({'line': number, 'tag': tag, 'file': file, 'content_state': 'INVALID',
                            'error': 'digest cell must be exactly 16 lowercase hex in backticks'})
            continue
        short = match[1]
        relationship = re.fullmatch(r'supersedes `([0-9a-f]{16})`', raw_status)
        if raw_status.startswith('evidence: ') or relationship:
            annotations += 1
            if relationship:
                superseded.add((tag, file, relationship[1]))
            continue
        try:
            status = writer.read_status(raw_status)
        except ValueError as error:
            invalid_status[(tag, file, short)] = {'line': number, 'tag': tag, 'file': file, 'hash': short,
                                                  'content_state': 'INVALID', 'error': str(error)}
            continue
        latest[(tag, file, short)] = {'line': number, 'tag': tag, 'file': file,
                                      'hash': short, 'status': status, 'raw_status': raw_status}
    for key, row in latest.items():
        row['historical'] = key in superseded or row['status'] == 'superseded'
    return [row for key, row in latest.items() if key not in invalid_status], invalid + list(invalid_status.values()), annotations


def visible_candidates(vault: Path, basename: str, include_archive: bool):
    for directory, children, files in os.walk(vault):
        children[:] = [n for n in children if n not in ('.git', '.stversions', '.Provenance')
                       and (include_archive or not (Path(directory) == vault and n == '06 Archive'))]
        if basename in files:
            candidate = Path(directory) / basename
            try:
                candidate.resolve().relative_to(vault)
            except ValueError:
                continue
            yield candidate


def resolve_live(vault: Path, file: str, short: str):
    logs = vault / '06 Archive/OpenCairn/Session Logs'
    transcript = re.fullmatch(r'([0-9]{4}-[0-9]{2}-[0-9]{2})-transcript\.md', file)
    dated = re.fullmatch(r'([0-9]{4})-[0-9]{2}-[0-9]{2}\.md', file)
    if transcript:
        preferred = [vault / '06 Archive/OpenCairn/.Session Transcripts' / (transcript[1] + '.md')]
    elif dated:
        preferred = [logs / file, logs / dated[1] / file]
    elif '/' in file:
        preferred = [safe_path(vault, file)]
    else:
        preferred = [logs / file, vault / file]
    history_path = preferred[0].relative_to(vault).as_posix()
    for path in preferred:
        path.resolve().relative_to(vault)
        if path.is_file():
            return path, digest(path), path.relative_to(vault).as_posix(), []
    candidates = []
    # An unqualified legacy name excludes frozen Archive; qualified moved paths
    # retain the documented archive reach. Never accept the first name alone.
    for path in visible_candidates(vault, preferred[0].name, '/' in file or bool(transcript or dated)):
        if digest(path)[:16] == short:
            candidates.append(path)
    if len(candidates) == 1:
        return candidates[0], digest(candidates[0]), history_path, []
    return None, None, history_path, [p.relative_to(vault).as_posix() for p in candidates]


class GitHistory:
    def __init__(self, vault):
        self.vault = vault
        self.env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')
        self.base = ['git', '--literal-pathspecs', '-C', str(vault), '-c', 'core.quotePath=false']
        try:
            check = self.run('rev-parse', '--show-toplevel')
            self.available = check.returncode == 0 and Path(check.stdout.decode().strip()).resolve() == vault
        except OSError:
            self.available = False
        if self.available:
            partial = self.run('config', '--get', 'extensions.partialClone')
            promisors = self.run('config', '--type=bool', '--get-regexp', r'^remote\..*\.promisor$')
            # Older Git may ignore GIT_NO_LAZY_FETCH. Do not inspect a configured
            # partial clone, where reading a missing object could fetch/write it.
            if partial.returncode not in (0, 1) or promisors.returncode not in (0, 1):
                self.available = False
            elif partial.returncode == 0 or any(line.rsplit(None, 1)[-1].lower() == b'true'
                                               for line in promisors.stdout.splitlines() if line.strip()):
                self.available = False
        self.blob_hashes = {}
        self.raw = None

    def run(self, *args):
        return subprocess.run([*self.base, *args], capture_output=True, env=self.env, check=False)

    def blob_hash(self, oid):
        if oid in self.blob_hashes:
            return self.blob_hashes[oid]
        process = subprocess.Popen([*self.base, 'cat-file', 'blob', oid],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)
        value = hashlib.sha256()
        assert process.stdout is not None
        for block in iter(lambda: process.stdout.read(1024 * 1024), b''):
            value.update(block)
        process.stdout.close()
        assert process.stderr is not None
        error = process.stderr.read()
        process.stderr.close()
        if process.wait() != 0:
            raise ValueError('git blob unavailable: ' + error.decode(errors='replace').strip())
        self.blob_hashes[oid] = value.hexdigest()
        return self.blob_hashes[oid]

    def find(self, rel, short):
        if not self.available:
            return {'available': False, 'matched': False, 'blobs_tried': 0}
        result = self.run('log', '--format=%H', '--', rel)
        if result.returncode:
            raise ValueError('git path history check failed: ' + result.stderr.decode(errors='replace'))
        tried, seen = 0, set()
        for commit in result.stdout.decode().splitlines():
            resolved = self.run('rev-parse', '-q', '--verify', commit + ':' + rel)
            if resolved.returncode:
                continue
            oid = resolved.stdout.decode().strip()
            if oid in seen:
                continue
            seen.add(oid)
            tried += 1
            if self.blob_hash(oid)[:16] == short:
                return {'matched': True, 'rung': 'path', 'commit': commit, 'path': rel, 'blobs_tried': tried}
        if self.raw is None:
            result = self.run('log', '--all', '--no-renames', '--format=', '--raw', '--no-abbrev', '-z')
            if result.returncode:
                raise ValueError('git basename history check failed: ' + result.stderr.decode(errors='replace'))
            self.raw = result.stdout.split(b'\0')
        for index, raw in enumerate(self.raw[:-1]):
            header = raw.lstrip(b'\n')
            if not header.startswith(b':'):
                continue
            fields = header.split()
            if len(fields) != 5:
                continue
            path = os.fsdecode(self.raw[index + 1])
            oid = fields[3].decode('ascii')
            if Path(path).name != Path(rel).name or not oid.strip('0') or oid in seen:
                continue
            seen.add(oid)
            tried += 1
            if self.blob_hash(oid)[:16] == short:
                return {'matched': True, 'rung': 'basename', 'path': path, 'blob': oid, 'blobs_tried': tried}
        return {'available': True, 'matched': False, 'blobs_tried': tried,
                'scope': 'current path and history entries sharing its basename'}


def inspect(vault: Path, log: Path):
    writer = writer_module()
    rows, invalid, annotations = parse_log(log, writer)
    history = GitHistory(vault)
    for row in rows:
        row['bitcoin_verification'] = 'not-run'
        row['locator_stale'] = False
        try:
            live, actual, rel, ambiguous = resolve_live(vault, row['file'], row['hash'])
            row['content_state'] = 'MATCH' if actual and actual[:16] == row['hash'] else ('MISMATCH' if live else 'MISSING')
            if live:
                row['resolved_file'] = live.relative_to(vault).as_posix()
                row['current_sha256'] = actual
                # Alias resolution (date/transcript) is normal, not a stale locator.
                row['locator_stale'] = row['resolved_file'] != rel and '/' in row['file']
            if ambiguous:
                row['ambiguous_live_candidates'] = ambiguous
            try:
                row['evidence'] = writer.locate(vault, row['tag'], row['file'], row['hash'])
            except (ValueError, OSError, json.JSONDecodeError) as error:
                row['evidence_error'] = str(error)
            if row['content_state'] != 'MATCH':
                if 'evidence' in row:
                    row['content_state'] = 'VERIFIED_SNAPSHOT'
                    row['snapshot'] = row['evidence']['snapshot']
                else:
                    # Proof identity can be unavailable while the selected snapshot
                    # still establishes content. Do not replace that chosen path.
                    selected = [r for r in writer.rows(log)
                                if r[1:4] == [row['tag'], row['file'], '`' + row['hash'] + '`']
                                and r[4].startswith('evidence: ')]
                    if selected:
                        try:
                            locator = json.loads(selected[-1][4].removeprefix('evidence: '))
                            if not isinstance(locator, dict) or set(locator) != {'snapshot', 'proof'}:
                                raise ValueError('invalid selected evidence locator')
                            snapshot = safe_path(vault, locator['snapshot'])
                            snapshot.relative_to((vault / '07 System/.Provenance').resolve())
                            candidates = [snapshot] if '.snapshot' in snapshot.name else []
                        except (TypeError, ValueError, KeyError):
                            candidates = []
                    else:
                        candidates = sorted((vault / '07 System/.Provenance').glob('*.snapshot*'))
                    for path in candidates:
                        if path.is_file() and digest(path)[:16] == row['hash']:
                            row['content_state'], row['snapshot'] = 'VERIFIED_SNAPSHOT', str(path)
                            break
                if row['content_state'] in ('MISSING', 'MISMATCH'):
                    found = history.find(rel, row['hash'])
                    row['git_search'] = found
                    if found['matched']:
                        row['content_state'], row['git'] = 'VERIFIED_GIT', found
                row['locator_stale'] = live is None
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            row['content_state'] = 'ERROR'
            row['error'] = str(error)
    for row in invalid:
        row['bitcoin_verification'] = 'not-run'
    result_rows = rows + invalid
    counts = {'records': len(result_rows), 'annotations': annotations,
              'content': dict(Counter(row['content_state'] for row in result_rows)),
              'evidence_gaps': sum('evidence_error' in row for row in rows),
              'historical': sum(row['historical'] for row in rows),
              'locator_stale': sum(row.get('locator_stale', False) for row in rows)}
    issues = counts['evidence_gaps'] or any(row['content_state'] in ('MISSING', 'MISMATCH', 'INVALID', 'ERROR')
                                          for row in result_rows)
    return {'schema': 1, 'scope': 'content digest and retained-proof identity; Bitcoin verification not run',
            'vault': str(vault), 'log': str(log), 'git_history_available': history.available,
            'counts': counts, 'rows': result_rows, 'triage_required': bool(issues)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', required=True)
    args = parser.parse_args()
    try:
        vault = Path(args.vault).expanduser().resolve(strict=True)
        result = inspect(vault, vault / '07 System/AI Provenance Log.md')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result['triage_required'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
