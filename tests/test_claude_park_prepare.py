import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

REPO = Path(__file__).parents[1]
SCRIPT = REPO / '.claude/scripts/park-prepare.py'
spec = importlib.util.spec_from_file_location('claude_park_prepare', SCRIPT)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class ClaudeParkPrepareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.vault = self.base / 'vault'
        self.scripts = self.vault / '.claude/scripts'
        self.scripts.mkdir(parents=True)
        for name in ['park-verify.sh', 'backfill-files-updated.sh', 'lib-lock.sh', 'lib-session.sh']:
            shutil.copy2(REPO / '.claude/scripts' / name, self.scripts / name)
        self.note = self.vault / 'Context - Example.md'
        self.note.write_text('# Result\n\nVerified content.\n')
        self.log = self.vault / 'log.md'
        self.log.write_text('# Sessions\n\n## Session 1 - Example\n\n'
            '### Summary\nCompleted example work.\n\n'
            '### Key Insights / Decisions\n- Keep it.\n\n'
            '### Next Steps / Open Loops\nNone — work completed.\n\n'
            '### Files Created\n- Context - Example.md - result\n\n'
            '### Files Updated\n- log.md - record\n\n'
            '### Pickup Context\n**For next session:** None.\n**Project:** None\n')
        self.config = self.base / 'config'
        self.root = self.config / '.session-state/fixture.park-prepare'
        env = mock.patch.dict(os.environ, {
            'CLAUDE_CONFIG_DIR': str(self.config), 'CODEX_HOME': str(self.base / 'codex'),
            'OPENCAIRN_SESSION_ID': 'fixture', 'CLAUDE_CODE_SESSION_ID': 'fixture',
            'CODEX_THREAD_ID': 'fixture', 'VAULT_PATH': str(self.vault)})
        env.start()
        self.addCleanup(env.stop)
        self.args = SimpleNamespace(vault=str(self.vault), session_log=str(self.log), number=1)
        self.handoff = {'propagation': 'Checked nil: no changed identifiers in the fixture.'}

    def run_prepare(self):
        with mock.patch('sys.stdout', io.StringIO()):
            return prepare.prepare(self.args, self.handoff)

    def outputs(self, name):
        return sorted(self.root.glob('*/' + name))

    def test_real_backfill_verifier_and_current_session_packet(self):
        other = self.vault / 'other.md'
        other.write_text('# Other result\n')
        self.handoff['backfill'] = ['- other.md - additional result']
        self.log.write_text(self.log.read_text() + '\n## Session 2 - Other work\n\nPRIVATE-OTHER-SESSION\n')
        self.assertEqual(self.run_prepare(), 0)
        packet = self.outputs('audit-inputs.md')[0].read_text()
        self.assertIn('Verified content.', packet)
        self.assertIn('# Other result', packet)
        self.assertNotIn('PRIVATE-OTHER-SESSION', packet)
        self.assertIn('- other.md - additional result', self.log.read_text())
        manifest = json.loads(self.outputs('manifest.json')[0].read_text())
        self.assertEqual(len(manifest['paths']), 3)

    def test_failure_and_review_produce_no_dispatch_packet(self):
        for message in ['FAIL lint: broken\nRESULT: FAIL', 'REVIEW closure: pending\nRESULT: REVIEW']:
            with self.subTest(message=message):
                verifier = self.scripts / 'park-verify.sh'
                verifier.write_text('#!/bin/sh\ncat <<\'EOF\'\n' + message + '\nEOF\n' + ('exit 1\n' if message.startswith('FAIL') else ''))
                with self.assertRaises(ValueError):
                    self.run_prepare()
        self.assertEqual(self.outputs('audit-inputs.md'), [])
        self.assertTrue(all(json.loads(p.read_text())['status'] == 'failed' for p in self.outputs('timing.json')))

    def test_concurrent_write_cannot_pass(self):
        (self.scripts / 'park-verify.sh').write_text('#!/bin/sh\nprintf changed > "$1/Context - Example.md"\nprintf "RESULT: PASS\\n"\n')
        with self.assertRaisesRegex(ValueError, 'Input changed'):
            self.run_prepare()
        self.assertEqual(self.outputs('audit-inputs.md'), [])

    def test_unknown_coverage_cannot_silently_inline_a_file(self):
        self.handoff['coverage'] = [{'path': 'wrong-path.md', 'kind': 'nonlocal'}]
        with self.assertRaisesRegex(ValueError, 'absent'):
            self.run_prepare()

    def test_nonlocal_file_is_not_inlined_or_leaked_through_verifier(self):
        self.note.write_text('SECRET-MUST-NOT-BE-COPIED- [ ] joined checkbox\n')
        self.handoff['coverage'] = [{'path': str(self.note), 'kind': 'nonlocal'}]
        self.assertEqual(self.run_prepare(), 0)
        self.assertNotIn('SECRET-MUST-NOT-BE-COPIED', self.outputs('audit-inputs.md')[0].read_text())
        self.assertNotIn('SECRET-MUST-NOT-BE-COPIED', self.outputs('verify.txt')[0].read_text())
        self.assertIn('content checks excluded', self.outputs('verify.txt')[0].read_text())

    def test_contradictory_coverage_aliases_are_rejected(self):
        self.handoff['coverage'] = [{'path': self.note.name, 'kind': 'nonlocal'},
                                    {'path': str(self.note), 'kind': 'nonlocal'}]
        with self.assertRaisesRegex(ValueError, 'Duplicate resolved coverage'):
            self.run_prepare()

    def test_large_unclassified_file_requires_explicit_coverage(self):
        self.note.write_text('x' * (prepare.MAX_INLINE + 1))
        with self.assertRaisesRegex(ValueError, 'Explicit large'):
            self.run_prepare()

    def test_reference_receipt_is_hash_bound(self):
        import subprocess
        source = self.base / 'reference.txt'
        source.write_text('Reference source text\n')
        r = subprocess.run(['python3', str(REPO / '.claude/scripts/park-artifact.py'),
                            '--source', str(source), '--original', str(source), '--state-dir', str(self.base / 'artifacts')], capture_output=True, text=True, check=True)
        receipt = json.loads(r.stdout)
        self.log.write_text(self.log.read_text().replace('### Files Updated\n', f'### Files Updated\n- {source} - reference\n'))
        self.handoff['coverage'] = [{'path': str(source), 'kind': 'reference', 'receipt': receipt['receipt_path'], 'targets': ['opening passage']}]
        self.assertEqual(self.run_prepare(), 0)
        source.write_text('changed source')
        with self.assertRaisesRegex(ValueError, 'Stale artefact'):
            self.run_prepare()

    def test_reused_reference_receipt_displays_current_alias(self):
        import subprocess
        source = self.base / 'reference.txt'
        source.write_text('Reference source text\n')
        alias = self.base / 'installed.txt'
        alias.symlink_to(source)
        result = subprocess.run(
            ['python3', str(REPO / '.claude/scripts/park-artifact.py'),
             '--source', str(source), '--original', str(source),
             '--state-dir', str(self.base / 'artifacts')],
            capture_output=True, text=True, check=True)
        receipt = json.loads(result.stdout)
        receipt_path = Path(receipt['receipt_path'])
        cache_before = receipt_path.read_bytes()
        self.log.write_text(self.log.read_text().replace(
            '### Files Updated\n', f'### Files Updated\n- {alias} - reference\n'))
        self.handoff['coverage'] = [
            {'path': str(alias), 'kind': 'reference',
             'receipt': str(receipt_path), 'targets': ['opening passage']}]
        self.assertEqual(self.run_prepare(), 0)
        packet = self.outputs('audit-inputs.md')[0].read_text()
        self.assertIn('"original_path": "' + str(alias) + '"', packet)
        self.assertEqual(receipt_path.read_bytes(), cache_before)

    def test_retry_backfill_does_not_duplicate_and_refreshes_snapshot(self):
        other = self.vault / 'other.md'
        other.write_text('# Other\n')
        self.handoff['backfill'] = ['- other.md - result']
        self.run_prepare()
        self.note.write_text('# Corrected\n')
        self.run_prepare()
        self.assertEqual(self.log.read_text().count('- other.md - result'), 1)
        self.assertEqual(len(self.outputs('audit-inputs.md')), 2)
        self.assertTrue(any('# Corrected' in p.read_text() for p in self.outputs('audit-inputs.md')))

    def test_new_outputs_follow_umask_and_source_modes_survive(self):
        self.note.chmod(0o640)
        self.log.chmod(0o640)
        old = os.umask(0o027)
        try:
            self.run_prepare()
        finally:
            os.umask(old)
        self.assertEqual(self.outputs('audit-inputs.md')[0].stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.note.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o640)

    def test_missing_report_rejected_before_backfill(self):
        self.handoff = {'backfill': ['- absent.md - bad']}
        before = self.log.read_bytes()
        with self.assertRaisesRegex(ValueError, 'propagation'):
            self.run_prepare()
        self.assertEqual(self.log.read_bytes(), before)

    def test_symlink_aliases_survive_physical_input_deduplication(self):
        link = self.vault / 'installed.md'
        link.symlink_to(self.note)
        self.log.write_text(self.log.read_text().replace('### Files Updated\n',
                                                        '### Files Updated\n- installed.md - installed link\n'))
        self.run_prepare()
        manifest = json.loads(self.outputs('manifest.json')[0].read_text())
        row = next(r for r in manifest['paths'] if r['path'] == str(self.note))
        self.assertEqual(set(row['aliases']), {str(self.note), str(link)})

    def test_auto_receipts_batch_explicit_binary_and_large_inspection(self):
        image = self.vault / 'plot.png'
        image.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        self.note.write_text('x' * (prepare.MAX_INLINE + 1))
        self.log.write_text(self.log.read_text().replace('### Files Updated\n',
                                                        '### Files Updated\n- plot.png - rendered plot\n'))
        self.handoff['coverage'] = [
            {'path': str(image), 'kind': 'large', 'receipt': 'auto', 'targets': ['Rendered plot']},
            {'path': str(self.note), 'kind': 'large', 'receipt': 'auto', 'targets': ['Authored result']},
        ]
        self.assertEqual(self.run_prepare(), 0)
        packet = self.outputs('audit-inputs.md')[0].read_text()
        self.assertIn('Rendered plot', packet)
        self.assertIn('Authored result', packet)
        receipts = list(self.root.glob('*/artifacts/receipts/*.json'))
        self.assertEqual(len(receipts), 2)
        for path in receipts:
            receipt = json.loads(path.read_text())
            self.assertTrue(Path(receipt['source_snapshot']).is_relative_to(self.root))
            self.assertEqual(prepare.sha(Path(receipt['source_snapshot'])), receipt['source_sha256'])

    def test_auto_receipt_does_not_waive_inspection_targets(self):
        self.handoff['coverage'] = [{'path': str(self.note), 'kind': 'large', 'receipt': 'auto'}]
        with self.assertRaisesRegex(ValueError, 'explicit inspection targets'):
            self.run_prepare()

    def test_explicit_bounded_semantic_coverage_overrides_forward_link_proof(self):
        older = self.vault / 'older.md'
        older.write_text('# Earlier record\n\nMeaning-bearing content.\n')
        self.log.write_text(self.log.read_text().replace(
            '### Files Updated\n', '### Files Updated\n- older.md - correction\n'))
        self.handoff['coverage'] = [{'path': 'older.md', 'kind': 'semantic'}]
        with mock.patch.object(prepare, 'forward_link_proof') as finder:
            self.assertEqual(self.run_prepare(), 0)
        finder.assert_not_called()
        packet = self.outputs('audit-inputs.md')[0].read_text()
        self.assertIn('Meaning-bearing content.', packet)
        self.assertNotIn('Mechanical forward-link insertion only', packet)

    def test_fixture_writer_ledger_and_receipts_stay_in_fixture_state(self):
        import subprocess
        result = subprocess.run([str(REPO / '.claude/scripts/locked-edit.sh'),
                                 str(self.note), '--append'],
                                input='Fixture addition.\n', capture_output=True,
                                text=True, env=os.environ.copy(), check=True)
        self.assertIn('Locked edit applied', result.stdout)
        state = self.config / '.session-state'
        ledger = state / 'fixture.tsv'
        self.assertIn('\tlocked-edit\t' + str(self.note) + '\tcodex:fixture', ledger.read_text())
        receipts = list((state / 'fixture.locked-edit-receipts').glob('receipt.*'))
        self.assertTrue(receipts)
        for receipt in receipts:
            self.assertTrue(receipt.is_relative_to(self.base))
            self.assertEqual(json.loads(receipt.read_text())['target'], str(self.note))


if __name__ == '__main__':
    unittest.main()
