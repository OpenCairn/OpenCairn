import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from session_isolation import isolate_session

SCRIPT = Path(__file__).parents[1] / '.claude/scripts/provenance-write.py'


class ProvenanceWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.artifacts = self.vault / '07 System/.Provenance'
        (self.artifacts / 'pending').mkdir(parents=True)
        self.log = self.vault / '07 System/AI Provenance Log.md'
        self.log.write_text('| Timestamp | Tag | File | SHA256 | OTS |\n| --- | --- | --- | --- | --- |\n')
        self.doc = self.vault / '03 Projects/Example.md'
        self.doc.parent.mkdir()
        self.doc.write_bytes(b'first exact bytes\n')
        self.env = isolate_session(os.environ.copy(), self.root / 'state', 'provenance-fixture')
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        ots = bin_dir / 'ots'
        ots.write_text('''#!/usr/bin/env python3
import hashlib, os, pathlib, sys
if sys.argv[1] == 'stamp':
 if os.environ.get('OTS_FAIL'): sys.exit(1)
 p = pathlib.Path(sys.argv[2]); pathlib.Path(str(p)+'.ots').write_text(hashlib.sha256(p.read_bytes()).hexdigest())
elif sys.argv[1] == 'info':
 print('File sha256 hash: ' + pathlib.Path(sys.argv[2]).read_text())
''')
        ots.chmod(0o755)
        self.env['PATH'] = str(bin_dir) + os.pathsep + self.env['PATH']

    def run_writer(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPT), '--vault', str(self.vault), *args],
                                text=True, capture_output=True, env=self.env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def attest(self, file=None, *extra):
        return json.loads(self.run_writer('attest', '--file', str(file or self.doc), '--tag', 'Example',
                                         '--date', '2026-01-02', *extra).stdout)

    def append(self, digest, status='pending', snapshot=None, proof=None, ok=True):
        args = ['append', '--file', '03 Projects/Example.md', '--tag', 'Example', '--hash', digest,
                '--status', status]
        if snapshot: args += ['--snapshot', str(snapshot)]
        if proof: args += ['--proof', str(proof)]
        return self.run_writer(*args, ok=ok)

    def test_rejects_non_16_hex_and_log_injection_without_changing_log(self):
        before = self.log.read_bytes()
        for digest in ['abcdef123456789', 'g' * 16, 'a' * 17]:
            self.append(digest, ok=False)
        self.run_writer('attest', '--file', str(self.doc), '--tag', 'bad|tag', '--date', '2026-01-02', ok=False)
        self.assertEqual(self.log.read_bytes(), before)

    def test_pending_requires_exact_snapshot_and_matching_proof(self):
        digest = hashlib.sha256(self.doc.read_bytes()).hexdigest()[:16]
        snap = self.artifacts / f'2026-01-02-example-{digest}.snapshot.md'
        proof = snap.with_name(f'2026-01-02-example-{digest}.ots')
        before = self.log.read_bytes()
        self.append(digest, ok=False)
        snap.write_bytes(b'different')
        self.append(digest, snapshot=snap, proof=proof, ok=False)
        snap.write_bytes(self.doc.read_bytes())
        self.append(digest, snapshot=snap, proof=proof, ok=False)
        proof.write_text('b' * 64)
        self.append(digest, snapshot=snap, proof=proof, ok=False)
        self.assertEqual(self.log.read_bytes(), before)
        proof.write_text(hashlib.sha256(snap.read_bytes()).hexdigest())
        self.append(digest, snapshot=snap, proof=proof)

    def test_attest_preserves_exact_preimage_and_does_not_stamp_live_file(self):
        original = self.doc.read_bytes()
        record = self.attest()
        self.assertEqual(record['status'], 'pending')
        snapshot = Path(record['snapshot'])
        self.assertEqual(snapshot.read_bytes(), original)
        self.assertFalse(Path(str(self.doc) + '.ots').exists())
        self.doc.write_bytes(b're-exported')
        self.assertEqual(snapshot.read_bytes(), original)
        self.assertTrue(Path(record['proof']).exists())
        receipts = list((self.root / 'state/.session-state').rglob('*'))
        self.assertTrue(receipts)
        self.assertTrue(all(str(path).startswith(str(self.root)) for path in receipts))

    def test_supersession_appends_relationship_without_rewriting_old_row(self):
        old = self.attest()
        before = self.log.read_bytes()
        old_proof = Path(old['proof']).read_bytes()
        self.doc.write_bytes(b'edited bytes')
        new = self.attest(None, '--supersedes', old['hash'])
        self.assertTrue(self.log.read_bytes().startswith(before))
        self.assertIn(f"supersedes `{old['hash']}`", self.log.read_text())
        self.assertNotEqual(old['hash'], new['hash'])
        self.assertEqual(Path(old['proof']).read_bytes(), old_proof)
        self.assertEqual(Path(old['snapshot']).read_bytes(), b'first exact bytes\n')

    def test_missing_superseded_row_is_rejected_before_any_log_append(self):
        before = self.log.read_bytes()
        self.run_writer('attest', '--file', str(self.doc), '--tag', 'Example', '--date', '2026-01-02',
                        '--supersedes', 'a' * 16, ok=False)
        self.assertEqual(self.log.read_bytes(), before)

    def test_ots_unavailable_is_honest_and_preserves_snapshot(self):
        self.env['PATH'] = '/usr/bin:/bin'
        record = self.attest()
        self.assertEqual(record['status'], 'none (ots unavailable)')
        self.assertEqual(Path(record['snapshot']).read_bytes(), self.doc.read_bytes())
        self.assertIsNone(record['proof'])
        self.assertNotIn('| pending |', self.log.read_text())

    def test_stamp_failure_is_honest_and_preserves_snapshot(self):
        self.env['OTS_FAIL'] = '1'
        record = self.attest()
        self.assertEqual(record['status'], 'none (stamp failed)')
        self.assertEqual(Path(record['snapshot']).read_bytes(), self.doc.read_bytes())
        self.assertNotIn('| pending |', self.log.read_text())

    def test_flag_remains_incomplete_until_all_work_transcript_log_rows_exist(self):
        flag = self.artifacts / 'pending/2026-01-02-example.md'
        flag.write_text('---\ndate: 2026-01-02\ntag: Example\n---\n\n## Work Products\n- 03 Projects/Example.md\n\n## Hashed Immediately\n')
        self.attest()
        self.run_writer('check-flag', '--flag', str(flag), ok=False)
        transcript = self.vault / '06 Archive/OpenCairn/.Session Transcripts/2026-01-02.md'
        session_log = self.vault / '06 Archive/OpenCairn/Session Logs/2026-01-02.md'
        for target in (transcript, session_log):
            target.parent.mkdir(parents=True)
            target.write_text('complete record\n')
        self.attest(transcript)
        self.run_writer('check-flag', '--flag', str(flag), ok=False)
        self.attest(session_log)
        result = self.run_writer('check-flag', '--flag', str(flag))
        self.assertTrue(json.loads(result.stdout)['complete'])
        self.assertTrue(flag.exists())  # the checker never deletes anything
        Path(self.attest()['proof']).unlink()
        self.run_writer('check-flag', '--flag', str(flag), ok=False)

    def test_literal_prescribed_commands_positive_and_negative(self):
        import re
        repo = SCRIPT.parents[2]
        def blocks(path):
            return re.findall(r'```bash\n(.*?)```', (repo / path).read_text(), re.S)
        provenance = blocks('.claude/commands/provenance.md')
        counterpart = blocks('codex/skills/provenance/SKILL.md')
        initial = next(b for b in provenance if 'FINAL_PRODUCTS=' in b)
        annotate = next(b for b in provenance if '--status "confirmed"' in b)
        finish = next(b for b in provenance if 'provenance-finish.sh' in b)
        for command in (initial, annotate, finish):
            self.assertIn(command, counterpart)
        scripts = self.vault / '.claude/scripts'
        scripts.parent.mkdir()
        scripts.symlink_to(SCRIPT.parent, target_is_directory=True)
        def shell(command, replacements, ok):
            command = command.replace('{VAULT}', str(self.vault))
            for key, value in replacements.items(): command = command.replace(key, str(value))
            result = subprocess.run(['bash', '-c', command], env=self.env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, ok, result.stderr)
            return result
        bindings = {'<verified YYYY-MM-DD>': '2026-01-02', '<tag from Step 2>': 'Example',
                    '<absolute path 1>': self.doc, '<absolute path 2>': self.doc}
        record = json.loads(shell(initial, bindings, True).stdout.splitlines()[-1])
        before = self.log.read_bytes()
        shell(initial, dict(bindings, **{'<absolute path 1>': self.vault / 'missing'}), False)
        self.assertEqual(self.log.read_bytes(), before)
        annotation = {'<tag>': 'Example', '<vault-relative file>': '03 Projects/Example.md',
                      '<16-hex hash>': record['hash'], '<absolute snapshot path>': record['snapshot'],
                      '<absolute .ots path>': record['proof']}
        shell(annotate, annotation, True)
        before = self.log.read_bytes()
        shell(annotate, dict(annotation, **{'<16-hex hash>': record['hash'][:-1]}), False)
        self.assertEqual(self.log.read_bytes(), before)
        flag = self.artifacts / 'pending/2026-01-02-example.md'
        flag.write_text('---\ndate: 2026-01-02\ntag: Example\n---\n\n## Work Products\n- 03 Projects/Example.md\n')
        shell(finish, {'<absolute flag path>': flag}, False)
        self.assertTrue(flag.exists())
        for rel in ('06 Archive/OpenCairn/.Session Transcripts/2026-01-02.md',
                    '06 Archive/OpenCairn/Session Logs/2026-01-02.md'):
            target = self.vault / rel; target.parent.mkdir(parents=True)
            target.write_text('complete record'); self.attest(target)
        shell(finish, {'<absolute flag path>': flag}, True)
        self.assertFalse(flag.exists())
        hygiene = blocks('.claude/commands/weekly-hygiene.md')
        hygiene_counterpart = blocks('codex/skills/weekly-hygiene/SKILL.md')
        snapshots = next(b for b in hygiene if 'VERIFIED via snapshot:' in b)
        proofs = next(b for b in hygiene if 'matching proofs' in b)
        for command in (snapshots, proofs): self.assertIn(command, hygiene_counterpart)
        out = shell(snapshots, {'<logged 16-hex short hash>': record['hash']}, True)
        self.assertIn('VERIFIED via snapshot:', out.stdout)
        out = shell(snapshots, {'<logged 16-hex short hash>': 'a' * 16}, True)
        self.assertIn('NO MATCH:', out.stdout)
        proof_bindings = {'<logged 16-hex short hash>': record['hash'],
                          '<File column>': '03 Projects/Example.md', '<resolved target path>': self.doc}
        self.assertIn('1 matching proofs', shell(proofs, proof_bindings, True).stdout)
        self.assertIn('0 matching proofs', shell(proofs, dict(proof_bindings, **{'<logged 16-hex short hash>': 'a' * 16}), True).stdout)

    def test_finish_flag_holds_canonical_lock_and_retains_incomplete_flags(self):
        flag = self.artifacts / 'pending/2026-01-02-example.md'
        flag.write_text('---\ndate: 2026-01-02\ntag: Example\n---\n\n## Work Products\n- 03 Projects/Example.md\n')
        finish = SCRIPT.with_name('provenance-finish.sh')
        def run():
            return subprocess.run([str(finish), str(self.vault), str(flag)], env=self.env,
                                  capture_output=True, text=True)
        self.attest()
        self.assertNotEqual(run().returncode, 0)
        self.assertTrue(flag.exists())
        for rel in ('06 Archive/OpenCairn/.Session Transcripts/2026-01-02.md',
                    '06 Archive/OpenCairn/Session Logs/2026-01-02.md'):
            target = self.vault / rel
            target.parent.mkdir(parents=True)
            target.write_text('complete record')
            self.attest(target)
        self.doc.write_text('changed after attestation')
        self.assertNotEqual(run().returncode, 0)
        self.assertTrue(flag.exists())
        self.attest()
        lock = flag.with_name('.' + flag.name + '.lock')
        with lock.open('w') as stream:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
            process = subprocess.Popen([str(finish), str(self.vault), str(flag)], env=self.env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            with self.assertRaises(subprocess.TimeoutExpired):
                process.communicate(timeout=0.3)
            self.assertTrue(flag.exists())
            fcntl.flock(stream, fcntl.LOCK_UN)
            stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertTrue(json.loads(stdout)['complete'])
        self.assertFalse(flag.exists())

    def test_flag_rejects_changed_target_and_wrong_tag_rows(self):
        flag = self.artifacts / 'pending/2026-01-02-example.md'
        flag.write_text('---\ndate: 2026-01-02\ntag: Other\n---\n\n## Work Products\n- 03 Projects/Example.md\n')
        self.attest()
        result = self.run_writer('check-flag', '--flag', str(flag), ok=False)
        self.assertIn('03 Projects/Example.md', result.stdout)
        self.assertTrue(flag.exists())


if __name__ == '__main__':
    unittest.main()
