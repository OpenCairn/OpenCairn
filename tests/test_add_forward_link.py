import json
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session

SCRIPT = Path(__file__).parents[1] / '.claude/scripts/add-forward-link.sh'


class ForwardLinkProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        logs = self.vault / '06 Archive/OpenCairn/Session Logs'
        logs.mkdir(parents=True)
        self.log = logs / '2001-01-01.md'
        self.log.write_text('## Session 1 - Earlier\n\n### Summary\nOld prose.\n\n'
            '### Pickup Context\n**Project:** None\n')
        self.target = logs / '2001-01-02.md'
        self.target.write_text('## Session 2 - Later\n\n### Summary\nNew prose.\n')
        self.config = self.root / 'config'
        self.env = isolate_session(os.environ.copy(), self.config, 'forward-fixture')
        self.env['VAULT_PATH'] = str(self.vault)

    def produce(self):
        subprocess.run(['bash', str(SCRIPT), '--continued-in', str(self.log), '1', '2', 'Later',
                        self.target.name], env=self.env, capture_output=True, text=True, check=True)
        paths = list((self.config / '.session-state/forward-fixture.forward-link-receipts').glob('*.json'))
        self.assertEqual(len(paths), 1)
        return paths[0]

    def test_actual_producer_proof_reconstructs_only_metadata_insertion(self):
        before = self.log.read_bytes()
        receipt = self.produce()
        run = subprocess.run(['bash', str(SCRIPT), '--verify-receipt', str(receipt), str(self.log)],
                             env=self.env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        proof = json.loads(run.stdout)
        self.assertEqual(Path(proof['pre_snapshot']).read_bytes(), before)
        self.assertEqual(proof['source_session_number'], 1)
        self.assertEqual(proof['target_session_number'], 2)
        self.assertEqual(proof['target_log'], str(self.target))
        self.assertTrue(receipt.is_relative_to(self.root))
        self.assertFalse(receipt.is_relative_to(self.vault))
        self.log.write_text(self.log.read_text().replace('Old prose.', 'Changed prose.'))
        changed = subprocess.run(['bash', str(SCRIPT), '--verify-receipt', str(receipt), str(self.log)],
                                env=self.env, capture_output=True, text=True)
        self.assertNotEqual(changed.returncode, 0)

    def test_duplicate_guard_creates_no_new_proof(self):
        receipt = self.produce()
        subprocess.run(['bash', str(SCRIPT), '--continued-in', str(self.log), '1', '2', 'Later',
                        self.target.name], env=self.env, capture_output=True, text=True, check=True)
        self.assertEqual(list(receipt.parent.glob('*.json')), [receipt])

    def test_empty_config_uses_same_home_fallback_for_producer_and_lookup(self):
        self.env['HOME'] = str(self.root / 'home')
        self.env['CLAUDE_CONFIG_DIR'] = ''
        self.config = self.root / 'home/.claude'
        self.produce()
        found = subprocess.run(
            ['bash', str(SCRIPT), '--find-proof', str(self.log), 'forward-fixture'],
            env=self.env, capture_output=True, text=True)
        self.assertEqual(found.returncode, 0, found.stderr)
        proof = json.loads(found.stdout)
        self.assertEqual(proof['post_sha256'], __import__('hashlib').sha256(self.log.read_bytes()).hexdigest())

    def test_both_fresh_consumers_accept_proof_and_refuse_changed_or_other_writes(self):
        before = self.log.read_text()
        self.log.write_text(before.replace('Old prose.', 'Old prose.' + ' x' * 40000))
        receipt = self.produce()
        repo = SCRIPT.parents[2]
        scripts = self.vault / '.claude/scripts'
        scripts.mkdir(parents=True)
        for name in ['park-verify.sh', 'lib-lock.sh']:
            shutil.copy2(repo / '.claude/scripts' / name, scripts / name)
        self.target.write_text('## Session 2 - Later\n\n### Summary\nCompleted.\n\n'
            '### Key Insights / Decisions\nNone\n\n### Next Steps / Open Loops\nNone\n\n'
            '### Files Created\nNone\n\n### Files Updated\n- `' + str(self.log) + '` - link\n'
            '- `' + str(self.target) + '` - record\n\n'
            '### Pickup Context\n**For next session:** None\n**Project:** None\n')
        self.target.write_text(self.target.read_text() + '\n## Session 3 - Third\n\n### Summary\nThird record.\n')
        subprocess.run(['bash', str(SCRIPT), '--continued-in', str(self.log), '1', '3', 'Third',
                        self.target.name], env=self.env, capture_output=True, text=True, check=True)
        spec = importlib.util.spec_from_file_location('claude_prepare_fixture', repo / '.claude/scripts/park-prepare.py')
        claude = importlib.util.module_from_spec(spec); spec.loader.exec_module(claude)
        spec = importlib.util.spec_from_file_location('codex_review_fixture', repo / 'codex/skills/park/scripts/park-review.py')
        codex = importlib.util.module_from_spec(spec); spec.loader.exec_module(codex)
        args = SimpleNamespace(vault=str(self.vault), session_log=str(self.target), number=2)
        with mock.patch.dict(os.environ, self.env):
            with mock.patch('sys.stdout', io.StringIO()):
                self.assertEqual(claude.prepare(args, {'propagation':'Checked nil.'}), 0)
            packets = list((self.config / '.session-state/forward-fixture.park-prepare').glob('*/audit-inputs.md'))
            self.assertIn('Mechanical forward-link insertion only', packets[0].read_text())
            _, root, _, _ = codex.state_paths('forward-fixture')
            codex.capture_record(root, kind='propagation', label='fixture', text='Checked nil.', source=None, provenance=None)
            codex.capture_record(root, kind='verifier', label='fixture', text='RESULT: PASS', source=None, provenance=None, returncode=0)
            build = SimpleNamespace(**vars(args), session_id='forward-fixture', out=None)
            with mock.patch('sys.stdout', io.StringIO()):
                self.assertEqual(codex.cmd_build(build), 0)
            manifest = json.loads((root / 'review-brief-manifest.json').read_text())
            self.assertEqual([r['path'] for r in manifest['mechanical']], [str(self.log)])
            found = codex.forward_link_proof(self.vault, self.log, 'forward-fixture')
            self.assertEqual(len(found['receipts']), 2)
            codex.atomic_json(root / 'files.json', {str(self.log): {'mode':'semantic','reason':'explicit review'}})
            with mock.patch('sys.stdout', io.StringIO()):
                codex.cmd_build(build)
            explicit = json.loads((root / 'review-brief-manifest.json').read_text())
            self.assertEqual(explicit['mechanical'], [])
            (root / 'files.json').unlink()
            ordinary_log = self.target.read_text()
            self.target.write_text(ordinary_log.replace('### Files Created\nNone',
                                                       '### Files Created\n- `' + str(self.log) + '` - authored log'))
            with self.assertRaisesRegex(ValueError, 'Explicit large'):
                with mock.patch('sys.stdout', io.StringIO()):
                    claude.prepare(args, {'propagation':'Checked nil.'})
            self.target.write_text(ordinary_log)
            self.log.write_text(self.log.read_text().replace('Old prose.', 'Later prose.'))
            self.assertIsNone(codex.forward_link_proof(self.vault, self.log, 'forward-fixture'))
            with self.assertRaisesRegex(ValueError, 'Explicit large'):
                with mock.patch('sys.stdout', io.StringIO()):
                    claude.prepare(args, {'propagation':'Checked nil.'})
            with mock.patch('sys.stdout', io.StringIO()):
                codex.cmd_build(build)
            manifest = json.loads((root / 'review-brief-manifest.json').read_text())
            self.assertEqual(manifest['mechanical'], [])
            self.assertIn(str(self.log), [r['path'] for r in manifest['full_read']])

    def test_prior_meaning_bearing_session_write_does_not_become_automatic(self):
        subprocess.run([str(SCRIPT.parent / 'locked-edit.sh'), str(self.log), '--append'],
                       input='Earlier semantic delta.\n', env=self.env,
                       capture_output=True, text=True, check=True)
        self.produce()
        found = subprocess.run(['bash', str(SCRIPT), '--find-proof', str(self.log), 'forward-fixture'],
                               env=self.env, capture_output=True, text=True)
        self.assertNotEqual(found.returncode, 0)

    def test_intervening_foreign_semantic_write_breaks_the_forward_only_chain(self):
        self.produce()
        foreign = {**self.env, 'OPENCAIRN_SESSION_ID':'another-fixture'}
        subprocess.run([str(SCRIPT.parent / 'locked-edit.sh'), str(self.log), '--append'],
                       input='Intervening semantic delta.\n', env=foreign,
                       capture_output=True, text=True, check=True)
        self.target.write_text(self.target.read_text() + '\n## Session 3 - Third\n')
        subprocess.run(['bash', str(SCRIPT), '--continued-in', str(self.log), '1', '3', 'Third',
                        self.target.name], env=self.env, capture_output=True, text=True, check=True)
        found = subprocess.run(['bash', str(SCRIPT), '--find-proof', str(self.log), 'forward-fixture'],
                               env=self.env, capture_output=True, text=True)
        self.assertNotEqual(found.returncode, 0)

    def test_optimized_python_and_wrong_session_context_fail_closed(self):
        receipt = self.produce()
        data = json.loads(receipt.read_text()); data['source_session_number'] = 9
        receipt.write_text(json.dumps(data))
        checked = subprocess.run(['bash', str(SCRIPT), '--verify-receipt', str(receipt), str(self.log)],
                                 env={**self.env, 'PYTHONOPTIMIZE':'1'}, capture_output=True, text=True)
        self.assertNotEqual(checked.returncode, 0)

    def test_legacy_unknown_writer_row_is_not_ignored(self):
        self.produce()
        ledger = self.config / '.session-state/forward-fixture.tsv'
        with ledger.open('a') as f:
            f.write('2001-01-01T00:00:00Z\tEdit\t' + str(self.log) + '\n')
        found = subprocess.run(['bash', str(SCRIPT), '--find-proof', str(self.log), 'forward-fixture'],
                               env=self.env, capture_output=True, text=True)
        self.assertNotEqual(found.returncode, 0)

    def test_sanctioned_session_log_writes_before_link_cannot_be_auto_covered(self):
        scripts = SCRIPT.parent
        cases = [
            ('update-session-section.sh', [str(self.log), '1', 'Summary', '--replace'], 'Corrected prose.\n'),
            ('write-session.sh', [str(self.log)], '## Session 4 - Added\n\n### Summary\nNew authored entry.\n'),
            ('backfill-files-updated.sh', [str(self.log), '1'], '- note.md - authored result\n')]
        original = self.log.read_text().replace('### Pickup Context', '### Files Updated\nNone\n\n### Pickup Context')
        for script, argv, payload in cases:
            with self.subTest(script=script):
                # A distinct fixture session makes each actual producer case independent.
                sid = script.removesuffix('.sh') + '-fixture'
                env = isolate_session(os.environ.copy(), self.config / sid, sid)
                env['VAULT_PATH'] = str(self.vault)
                env['CODEX_THREAD_ID'] = 'actual-writer-fixture'
                self.log.write_text(original)
                subprocess.run(['bash', str(scripts / script), *argv], input=payload,
                               env=env, capture_output=True, text=True, check=True)
                subprocess.run(['bash', str(SCRIPT), '--continued-in', str(self.log), '1', '2', 'Later',
                                self.target.name], env=env, capture_output=True, text=True, check=True)
                checked = subprocess.run(['bash', str(SCRIPT), '--find-proof', str(self.log), sid],
                                         env=env, capture_output=True, text=True)
                self.assertNotEqual(checked.returncode, 0, checked.stdout)
                rows = (self.config / sid / '.session-state' / (sid + '.tsv')).read_text().splitlines()
                self.assertEqual([r.split('\t')[1] for r in rows], [script.removesuffix('.sh'), 'add-forward-link'])
                self.assertTrue(all(r.split('\t')[2] == str(self.log) for r in rows))
                self.assertTrue(all(r.split('\t')[3] == 'codex:actual-writer-fixture' for r in rows))

    def test_sanctioned_empty_and_identical_noops_do_not_create_ledger_rows(self):
        scripts = SCRIPT.parent
        self.log.write_text(self.log.read_text().replace('### Pickup Context', '### Files Updated\n- note.md - existing\n\n### Pickup Context'))
        for script, argv, body, expected in [
            ('write-session.sh', [str(self.log)], '', 1),
            ('update-session-section.sh', [str(self.log), '1', 'Summary'], '', 0),
            ('update-session-section.sh', [str(self.log), '1', 'Summary', '--replace'], 'Old prose.\n', 0),
            ('backfill-files-updated.sh', [str(self.log), '1'], '- note.md - duplicate\n', 3)]:
            with self.subTest(script=script, body=body):
                before = self.log.read_bytes()
                run = subprocess.run(['bash', str(scripts / script), *argv], input=body,
                                     env=self.env, capture_output=True, text=True)
                self.assertEqual(run.returncode, expected, run.stdout+run.stderr)
                self.assertEqual(self.log.read_bytes(), before)
                self.assertFalse((self.config / '.session-state/forward-fixture.tsv').exists())


if __name__ == '__main__':
    unittest.main()
