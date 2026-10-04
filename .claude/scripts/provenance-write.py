#!/usr/bin/env python3
"""Append validated provenance attestations; never edit previous log bytes.

All vault writes use the adjacent canonical lock wrappers. OTS runs on an
outside-vault staged preimage, so a live target can change without losing the
bytes that were stamped. check-flag is read-only and never removes a flag.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parent
STATUSES = ('pending', 'confirmed', 'none (ots unavailable)', 'none (stamp failed)')


def short_hash(value: str) -> str:
    if not re.fullmatch(r'[0-9a-f]{16}', value):
        raise ValueError('hash must be exactly 16 lowercase hexadecimal characters')
    return value


def cell(value: str) -> str:
    if not value or any(c in value for c in '|\r\n`'):
        raise ValueError('empty or unsafe table cell')
    return value


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
        return h.hexdigest()


def relative(vault: Path, value: str) -> str:
    p = Path(value).expanduser()
    p = p if p.is_absolute() else vault / p
    p = p.resolve()
    return cell(p.relative_to(vault).as_posix())


def rows(log: Path) -> list[list[str]]:
    if not log.exists():
        return []
    result = []
    for line in log.read_text().splitlines():
        fields = [part.strip() for part in line.split('|')]
        if len(fields) == 7 and re.fullmatch(r'`[0-9a-f]{16}`', fields[4]):
            result.append(fields[1:-1])
    return result


def proof_matches(proof: Path, snapshot: Path) -> bool:
    if not proof.is_file() or not shutil.which('ots'):
        return False
    info = subprocess.run(['ots', 'info', str(proof)], text=True, capture_output=True)
    # The Python OTS client's local info command exposes the full file digest.
    found = re.search(r'File sha256 hash:\s*([0-9a-f]{64})', info.stdout, re.I)
    return info.returncode == 0 and bool(found) and found.group(1).lower() == digest(snapshot)


def validate_evidence(vault: Path, value: str, status: str, snapshot: Path, proof: Path | None) -> None:
    short_hash(value)
    snapshot = snapshot.resolve()
    snapshot.relative_to(vault / '07 System/.Provenance')
    if '.snapshot' not in snapshot.name or not snapshot.is_file() or digest(snapshot)[:16] != value:
        raise ValueError('matching byte-exact provenance snapshot required')
    if proof is not None or status in ('pending', 'confirmed'):
        if proof is None:
            raise ValueError('pending/confirmed requires an existing matching .ots proof')
        proof = proof.resolve()
        proof.relative_to(vault)
        if proof.suffix != '.ots' or not proof_matches(proof, snapshot):
            raise ValueError('pending/confirmed requires an existing matching .ots proof (ots info)')


def append(vault: Path, rel: str, tag: str, value: str, status: str,
           snapshot: Path, proof: Path | None, supersedes: str | None) -> dict:
    cell(tag)
    cell(rel)
    snapshot = snapshot.resolve()
    proof = proof.resolve() if proof else None
    validate_evidence(vault, value, status, snapshot, proof)
    log = vault / '07 System/AI Provenance Log.md'
    existing = rows(log)
    if supersedes:
        short_hash(supersedes)
        if supersedes == value or not any(r[1:4] == [tag, rel, f'`{supersedes}`'] and r[4] in STATUSES for r in existing):
            raise ValueError('superseded attestation must exist for this tag/file and a different hash')
    timestamp = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
    additions = []
    attestations = [r for r in existing if r[1:4] == [tag, rel, f'`{value}`'] and r[4] in STATUSES]
    if not attestations or attestations[-1][4] != status:
        additions.append(f'| {timestamp} | {tag} | {rel} | `{value}` | {status} |\n')
    relationship = f'supersedes `{supersedes}`' if supersedes else None
    if relationship and not any(r[1:] == [tag, rel, f'`{value}`', relationship] for r in existing):
        additions.append(f'| {timestamp} | {tag} | {rel} | `{value}` | {relationship} |\n')
    # Separate annotation rows keep the five-column attestation table compatible.
    # Record the chosen bytes durably; a later process must not pick the old proof.
    locator = 'evidence: ' + json.dumps({'snapshot': relative(vault, str(snapshot)),
                                       'proof': relative(vault, str(proof)) if proof else None},
                                      sort_keys=True)
    locators = [r for r in existing if r[1:4] == [tag, rel, f'`{value}`'] and r[4].startswith('evidence: ')]
    if not locators or locators[-1][4] != locator:
        additions.append(f'| {timestamp} | {tag} | {rel} | `{value}` | {locator} |\n')
    if additions:
        # The wrapper guarantees the single newline boundary; prepend no blank.
        payload = ''.join(additions)
        subprocess.run([str(SCRIPTS / 'locked-edit.sh'), str(log), '--append'],
                       input=payload, text=True, check=True, stdout=sys.stderr)
    return {'file': rel, 'hash': value, 'status': status, 'snapshot': str(snapshot),
            'proof': str(proof) if proof else None, 'supersedes': supersedes}


def ingress(vault: Path, source: Path, target: Path) -> None:
    result = subprocess.run([str(SCRIPTS / 'locked-ingress.sh'), str(vault), str(source), str(target)],
                            capture_output=True, text=True)
    if result.returncode:
        # A concurrent equivalent ingress is safe; conflicting bytes are not.
        if source.is_file() and target.is_file() and digest(source) == digest(target):
            return
        if source.is_dir() and target.is_dir():
            return
        raise ValueError(result.stderr.strip() or 'provenance ingress failed')
    if result.stdout:
        print(result.stdout, file=sys.stderr, end='')


def attest(vault: Path, args: argparse.Namespace) -> dict:
    rel = relative(vault, args.file)
    cell(args.tag)
    date.fromisoformat(args.date)
    source = vault / rel
    if not source.is_file():
        raise ValueError(f'missing target: {rel}')
    if args.supersedes:
        short_hash(args.supersedes)
        if not any(r[1:4] == [args.tag, rel, f'`{args.supersedes}`'] and r[4] in STATUSES
                   for r in rows(vault / '07 System/AI Provenance Log.md')):
            raise ValueError('superseded attestation not found for this tag/file')
    with tempfile.TemporaryDirectory(prefix='opencairn-provenance-') as temporary:
        staging = Path(temporary)
        preimage = staging / source.name
        shutil.copyfile(source, preimage)
        full_hash = digest(preimage)
        value = full_hash[:16]
        recorded = rows(vault / '07 System/AI Provenance Log.md')
        if any(r[1:4] == [args.tag, rel, f'`{value}`'] and r[4].startswith('evidence: ')
               for r in recorded):
            prior = locate(vault, args.tag, rel, value)
            if digest(Path(prior['snapshot'])) != full_hash:
                raise ValueError('selected snapshot differs from staged target')
            if prior['status'] in ('pending', 'confirmed'):
                return append(vault, rel, args.tag, value, prior['status'], Path(prior['snapshot']),
                              Path(prior['proof']), args.supersedes)
        safe_name = re.sub('[^a-z0-9-]', '', source.stem.lower().replace(' ', '-')) or 'file'
        artifacts = vault / '07 System/.Provenance'
        if not artifacts.is_dir():
            empty = staging / 'empty'
            empty.mkdir()
            ingress(vault, empty, artifacts)
        base = f'{args.date}-{safe_name}-{value}'
        snapshot = artifacts / f'{base}.snapshot{source.suffix}'
        proof = artifacts / f'{base}.ots'
        if snapshot.exists():
            if digest(snapshot) != full_hash:
                raise ValueError('existing snapshot differs; refusing to overwrite')
        else:
            ingress(vault, preimage, snapshot)
        status = 'none (ots unavailable)'
        if proof.exists():
            if not proof_matches(proof, snapshot):
                raise ValueError('existing proof does not match snapshot; refusing to overwrite')
            # Preserve a previously confirmed status; stamping is not verification.
            status = 'confirmed' if any(r[1:] == [args.tag, rel, f'`{value}`', 'confirmed']
                                        for r in rows(vault / '07 System/AI Provenance Log.md')) else 'pending'
        elif shutil.which('ots'):
            stamped = subprocess.run(['ots', 'stamp', str(preimage)], stdout=sys.stderr)
            staged_proof = Path(str(preimage) + '.ots')
            status = 'none (stamp failed)'
            if stamped.returncode == 0 and proof_matches(staged_proof, preimage):
                ingress(vault, staged_proof, proof)
                status = 'pending'
        return append(vault, rel, args.tag, value, status, snapshot,
                      proof if proof.exists() else None, args.supersedes)


def locate(vault: Path, tag: str, rel: str, value: str) -> dict:
    """Resolve chosen evidence without writing or asserting Bitcoin verification."""
    short_hash(value)
    cell(tag)
    matching = [r for r in rows(vault / '07 System/AI Provenance Log.md')
                if r[1:4] == [tag, rel, f'`{value}`']]
    attestations = [r for r in matching if r[4] in STATUSES]
    if not attestations:
        raise ValueError('attestation not found for tag/file/hash')
    status = attestations[-1][4]
    locators = [r[4] for r in matching if r[4].startswith('evidence: ')]
    if locators:
        data = json.loads(locators[-1].removeprefix('evidence: '))
        if not isinstance(data, dict) or set(data) != {'snapshot', 'proof'}:
            raise ValueError('invalid evidence locator annotation')
        for key, path in data.items():
            if path is None and key == 'proof':
                continue
            if not isinstance(path, str) or Path(path).is_absolute():
                raise ValueError('evidence locator must use vault-relative paths')
            if relative(vault, path) != path:
                raise ValueError('invalid evidence locator path')
        snapshot = vault / data['snapshot']
        proof = vault / data['proof'] if data['proof'] else None
        # A broken selected locator is an integrity gap, not a reason to use
        # another proof that happens to share the same source digest.
        validate_evidence(vault, value, status, snapshot, proof)
        selection = 'annotation'
    else:
        artifacts = vault / '07 System/.Provenance'
        snapshots = [p for p in sorted(artifacts.glob('*.snapshot*'))
                     if p.is_file() and digest(p)[:16] == value]
        if not snapshots:
            raise ValueError('matching retained snapshot not found')
        snapshot, proof = snapshots[0], None
        if status in ('pending', 'confirmed'):
            candidates = set(artifacts.glob(f'*-{value}.ots'))
            candidates.update(artifacts.glob(f'*-{value[:8]}.ots'))
            basename = Path(rel).name
            candidates.update([artifacts / (basename + '.ots'),
                               artifacts / (Path(basename).stem + '.ots'),
                               vault / (rel + '.ots')])
            candidates.update(artifacts / (p.name.split('.snapshot', 1)[0] + '.ots')
                              for p in snapshots)
            proofs = [p for p in sorted(candidates) if proof_matches(p, snapshot)]
            if len(proofs) != 1:
                raise ValueError(f'{len(proofs)} matching legacy proofs; require an explicit evidence annotation')
            proof = proofs[0]
        validate_evidence(vault, value, status, snapshot, proof)
        selection = 'legacy'
    return {'file': rel, 'hash': value, 'status': status, 'snapshot': str(snapshot),
            'proof': str(proof) if proof else None, 'selection': selection}


def evidence_for(vault: Path, tag: str, rel: str, value: str) -> bool:
    try:
        locate(vault, tag, rel, value)
        return True
    except (ValueError, OSError):
        return False


def check_flag(vault: Path, flag: Path) -> dict:
    flag = flag.resolve()
    flag.relative_to(vault / '07 System/.Provenance/pending')
    text = flag.read_text()
    frontmatter = re.match(r'\A---\n(.*?)\n---(?:\n|$)', text, re.S)
    if not frontmatter:
        raise ValueError('flag requires date/tag frontmatter')
    day = re.search(r'^date:\s*(\d{4}-\d{2}-\d{2})\s*$', frontmatter[1], re.M)
    tag = re.search(r'^tag:\s*(.+)$', frontmatter[1], re.M)
    products = re.search(r'^## Work Products\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not day or not tag or not products:
        raise ValueError('flag requires date, tag and Work Products section')
    day = day[1]
    date.fromisoformat(day)
    tag = cell(tag[1].strip())
    targets = []
    for line in products[1].splitlines():
        if not line.strip():
            continue
        if not line.startswith('- '):
            raise ValueError('unexpected Work Products line')
        targets.append(relative(vault, line[2:].strip()))
    targets.append(f'06 Archive/OpenCairn/.Session Transcripts/{day}.md')
    session = f'06 Archive/OpenCairn/Session Logs/{day}.md'
    archived = f'06 Archive/OpenCairn/Session Logs/{day[:4]}/{day}.md'
    targets.append(archived if not (vault / session).exists() and (vault / archived).exists() else session)
    recorded = rows(vault / '07 System/AI Provenance Log.md')
    missing = []
    for target in dict.fromkeys(targets):
        source = vault / target
        value = digest(source)[:16] if source.is_file() else None
        # A different tag's attestation or stale pre-export hash cannot clear this flag.
        candidates = [r for r in recorded if r[1:4] == [tag, target, f'`{value}`'] and r[4] in STATUSES]
        if not candidates or not evidence_for(vault, tag, target, value):
            missing.append(target)
    return {'complete': not missing, 'flag': str(flag), 'missing': missing}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('attest', 'append'):
        sub = commands.add_parser(command)
        sub.add_argument('--file', required=True)
        sub.add_argument('--tag', required=True)
        sub.add_argument('--supersedes')
        if command == 'attest':
            sub.add_argument('--date', required=True, help='attestation context day (YYYY-MM-DD)')
        else:
            sub.add_argument('--hash', required=True)
            sub.add_argument('--status', choices=STATUSES, required=True)
            sub.add_argument('--snapshot', required=True)
            sub.add_argument('--proof')
    commands.add_parser('check-flag').add_argument('--flag', required=True)
    locator = commands.add_parser('locate', help='read-only chosen evidence lookup; does not verify Bitcoin attestation')
    for field in ('tag', 'file', 'hash'):
        locator.add_argument('--' + field, required=True)
    args = parser.parse_args()
    try:
        vault = Path(args.vault).expanduser().resolve(strict=True)
        if args.command == 'attest':
            result = attest(vault, args)
        elif args.command == 'append':
            result = append(vault, relative(vault, args.file), args.tag, args.hash, args.status,
                            Path(args.snapshot), Path(args.proof) if args.proof else None, args.supersedes)
        elif args.command == 'locate':
            result = locate(vault, args.tag, relative(vault, args.file), args.hash)
        else:
            result = check_flag(vault, Path(args.flag))
        print(json.dumps(result))
        return 2 if result.get('complete') is False else 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
