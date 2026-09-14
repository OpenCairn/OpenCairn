"""Synthetic backfill regressions; no live state or non-standard imports."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / '.claude/scripts/backfill-files-updated.sh'

class BackfillBodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='backfill-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / 'log.md'
        self.env = {'PATH': os.defpath, 'HOME': str(self.root),
                    'VAULT_PATH': str(self.root),
                    'CLAUDE_CONFIG_DIR': str(self.root / 'config'),
                    'OPENCAIRN_SESSION_ID': 'synthetic-backfill'}

    def run_helper(self, before, incoming, session='1'):
        self.log.write_text(before)
        self.log.chmod(0o640)
        result = subprocess.run(['bash', str(HELPER), str(self.log), session],
                                input=incoming, text=True, capture_output=True,
                                env=self.env, cwd=self.root, timeout=15)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o640)
        self.assertEqual(result.stderr, '')
        return result, self.log.read_text()

    def assert_skipped(self, before, incoming, path):
        result, after = self.run_helper(before, incoming)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(after, before)
        self.assertIn('skipped (already listed in Created/Updated): ' + path, result.stdout)
        self.assertIn('All files already listed, nothing to backfill', result.stdout)

    def test_final_existing_row_is_deduplicated(self):
        prefix = '## Session 1 - Fixture\n### Files Updated\n- A.md - original\n- B.md - original'
        for suffix in ('', '\n', '\n### Notes\nKeep\n', '\n\n### Notes\nKeep\n'):
            with self.subTest(suffix=suffix):
                self.assert_skipped(prefix + suffix, '- B.md - incoming\n', 'B.md')

    def test_fresh_row_appends_after_final_existing_row(self):
        prefix = '## Session 1 - Fixture\n### Files Updated\n- A.md - original\n- B.md - original'
        for suffix in ('', '\n', '\n### Notes\nKeep\n', '\n\n### Notes\nKeep\n'):
            with self.subTest(suffix=suffix):
                result, after = self.run_helper(prefix + suffix, '- C.md - incoming\n')
                self.assertEqual(result.returncode, 0)
                expected = prefix + '\n- C.md - incoming\n' + suffix.removeprefix('\n')
                self.assertEqual(after, expected)

    def test_following_session_does_not_seed_dedup(self):
        before = ('## Session 1 - Fixture\n### Files Updated\nNone\n'
                  '## Session 2 - Other\n- A.md - other\n- B.md - other\n### Summary\nKeep\n')
        result, after = self.run_helper(before, '- A.md - incoming\n')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(after, before.replace('None\n', '- A.md - incoming\n'))
        self.assertNotIn('skipped', result.stdout)

    def test_append_stays_in_target_session(self):
        before = ('## Session 1 - Fixture\n### Files Updated\n- Z.md - current\n'
                  '## Session 2 - Other\n- A.md - other\n- B.md - other\n### Summary\nKeep\n')
        result, after = self.run_helper(before, '- C.md - incoming\n')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(after, before.replace('- Z.md - current\n', '- Z.md - current\n- C.md - incoming\n'))

    def test_empty_section_never_captures_next_heading(self):
        for tail in ('', '\n', '\n### Notes\nKeep\n', '\n## Session 2 - Other\n### Notes\nKeep\n'):
            with self.subTest(tail=tail):
                before = '## Session 1 - Fixture\n### Files Updated' + tail
                result, after = self.run_helper(before, '- C.md - incoming\n')
                self.assertEqual(result.returncode, 0)
                self.assertEqual(after, '## Session 1 - Fixture\n### Files Updated\n- C.md - incoming\n' + tail.removeprefix('\n'))

    def test_paths_only_and_backticks_dedup_across_spellings(self):
        for path in ('alpha.md', '-option.md', 'Notes/Context - Example.md', 'tools/check', 'tools/check - release'):
            rows = ['- `' + path + '`', '- `' + path + '` - changed - detail']
            if path != 'tools/check - release':
                rows.extend(['- ' + path, '- ' + path + ' - changed - detail'])
            for existing in rows:
                for incoming in rows:
                    with self.subTest(path=path, existing=existing, incoming=incoming):
                        before = '## Session 1 - Fixture\n### Files Updated\n' + existing + '\n\n### Notes\nKeep\n'
                        self.assert_skipped(before, incoming + '\n', path)

    def test_created_exclusion_and_normalized_paths_remain(self):
        before = ('## Session 1 - Fixture\n### Files Created\n- `Notes/Context - Example.md`\n'
                  '### Files Updated\nNone\n\n### Notes\nKeep\n')
        incoming = '- ' + str(self.root / 'Notes/Context - Example.md') + ' - later edit\n'
        self.assert_skipped(before, incoming, str(self.root / 'Notes/Context - Example.md'))

    def test_batch_dedup_and_literal_leading_bullets(self):
        before = '## Session 1 - Fixture\n### Files Updated\nNone\n\n### Notes\nKeep\n'
        first = '- Notes/Context - Example.md - 100% done - literal \\n and \\t'
        result, after = self.run_helper(before, first + '\n- `Notes/Context - Example.md`\n- tools/check\n')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(after, before.replace('None', first + '\n- tools/check'))
        self.assertIn('skipped (already listed in Created/Updated): Notes/Context - Example.md', result.stdout)

    def test_unrecognised_body_is_preserved(self):
        before = '## Session 1 - Fixture\n### Files Updated\nNone\n\n### Notes\nKeep\n'
        incoming = 'Preserved prose\n- `unterminated path\n'
        result, after = self.run_helper(before, incoming)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(after, before.replace('None\n', incoming))

    def test_missing_session_fails_without_mutation(self):
        before = '## Session 1 - Fixture\n### Files Updated\nNone\n'
        result, after = self.run_helper(before, '- A.md\n', '999')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(after, before)
        self.assertIn('Could not find Session 999 heading', result.stdout)

    def test_empty_input_remains_successful_noop(self):
        before = '## Session 1 - Fixture\n### Files Updated\nNone\n'
        result, after = self.run_helper(before, '')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(after, before)
        self.assertIn('No file list provided on stdin', result.stdout)

if __name__ == '__main__':
    unittest.main()
