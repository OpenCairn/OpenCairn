"""Behavioural checks for retained Lane 4 fixes."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_isolation import isolate_session

ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / '.claude/scripts'


class Lane4RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = isolate_session(os.environ.copy(), self.root / 'state', 'lane4-fixture')
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        self.env['VAULT_PATH'] = str(self.vault)

    def run_script(self, name, *args, body=None):
        return subprocess.run([str(SCRIPTS / name), *map(str, args)], input=body,
                              env=self.env, text=True, capture_output=True, timeout=20)

    def ledger(self):
        return self.root / 'state/.session-state/lane4-fixture.tsv'

    def test_fenced_session_headings_do_not_inflate_number(self):
        log = self.vault / 'log.md'
        log.write_text('## Session 4 - Real\n```md\n## Session 99 - Example\n```\n'
                       '~~~md\n## Session 88 - Example\n~~~\n## Session 2 - Earlier\n')
        result = self.run_script('next-session-number.sh', log)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '5')

    def test_ingress_ledgers_landed_target_and_refusal_adds_no_row(self):
        source = self.root / 'source.bin'; source.write_bytes(b'payload')
        os.utime(source, (1, 1))
        target = self.vault / 'target.bin'
        result = self.run_script('locked-ingress.sh', self.vault, source, target)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = self.ledger().read_text()
        self.assertIn(f'\tlocked-ingress\t{target}\t?', row)
        self.assertEqual(target.stat().st_mtime, 1)
        rejected = self.run_script('locked-ingress.sh', self.vault, source, target)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(self.ledger().read_text(), row)

    @unittest.skipIf(not hasattr(os, 'geteuid') or os.geteuid() == 0,
                     'requires non-root POSIX directory permissions')
    def test_failed_move_cleanup_still_ledgers_installed_target(self):
        parent = self.root / 'readonly'; parent.mkdir()
        source = parent / 'source.bin'; source.write_bytes(b'payload')
        target = self.vault / 'target.bin'
        parent.chmod(0o500)
        try:
            result = self.run_script('locked-ingress.sh', self.vault, source, target, '--move')
        finally:
            parent.chmod(0o700)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('target installed but source retained', result.stderr)
        self.assertEqual(target.read_bytes(), b'payload')
        self.assertTrue(source.exists())
        self.assertIn(f'\tlocked-ingress\t{target}\t?', self.ledger().read_text())

    def test_tickler_writer_self_ledgers(self):
        target = self.vault / 'Tickler.md'
        result = self.run_script('write-tickler.sh', target, '2026-09-14', '- [ ] Fixture')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'\twrite-tickler\t{target}\t?', self.ledger().read_text())

    def test_tool_and_agent_names_are_exact_members(self):
        ledger = self.ledger(); ledger.parent.mkdir(parents=True)
        ledger.write_text('2026-09-14T00:00:00Z\tMultiEdit\t/tmp/note\tagent-12\n'
                          '2026-09-14T00:00:01Z\tEdit\t/tmp/note\tagent-1\n'
                          '2026-09-14T00:00:02Z\tEdit\t/tmp/note\tagent-1\n')
        result = self.run_script('session-ledger.sh', '--read')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('3x MultiEdit,Edit', result.stdout)
        self.assertIn('agent-12,agent-1', result.stdout)

    def test_created_path_stays_out_of_updated_and_noop_succeeds(self):
        log = self.vault / 'log.md'
        log.write_text('## Session 1 - Fixture\n\n### Summary\nDone\n\n'
                       '### Files Created\n- new.md - created\n\n'
                       '### Files Updated\nNone\n\n### Pickup Context\nNone\n')
        result = self.run_script('backfill-files-updated.sh', log, 1,
                                 body='- new.md - later fix\n- old.md - changed\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('skipped (already listed in Created/Updated): new.md', result.stdout)
        self.assertEqual(log.read_text().count('- new.md'), 1)
        self.assertIn('- old.md - changed', log.read_text())
        before = log.read_bytes()
        noop = self.run_script('backfill-files-updated.sh', log, 1, body='- old.md - repeated\n')
        self.assertEqual(noop.returncode, 0, noop.stderr)
        self.assertEqual(log.read_bytes(), before)

    def test_line_count_includes_final_unterminated_line(self):
        spec = importlib.util.spec_from_file_location('review', ROOT / 'codex/skills/park/scripts/park-review.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        path = self.root / 'source'; path.write_bytes(b'a\nb')
        self.assertEqual(module.count_lines(path), 2)
        path.write_bytes(b''); self.assertEqual(module.count_lines(path), 0)

    def test_files_parser_keeps_quoted_and_unquoted_spaced_names(self):
        target = self.vault / 'Context - Example.md'; target.write_text('Body\n')
        log = self.vault / 'log.md'
        for path in (str(target), '`' + str(target) + '`'):
            log.write_text('## Session 1 - Fixture\n### Summary\nDone\n'
                           '### Files Created\nNone\n### Files Updated\n'
                           '- ' + path + ' - changed - description\n'
                           '### Pickup Context\n**Project:** None\n')
            result = self.run_script('park-verify.sh', self.vault, log, 1,
                                     '--touched', target)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS backfill: --touched covers every path', result.stdout)
            self.assertNotIn('REVIEW backfill:', result.stdout)
