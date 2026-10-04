"""Synthetic bullet-normalisation checks for update-session-section.sh."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / '.claude/scripts/update-session-section.sh'
HEAD = '## Session 1 - Fixture\n\n### Summary\nDone\n\n'
TAIL = '\n### Pickup Context\nNone\n'


class UpdateSessionSectionBulletTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='section-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / 'log.md'
        self.env = {'PATH': os.defpath, 'HOME': str(self.root),
                    'VAULT_PATH': str(self.root),
                    'CLAUDE_CONFIG_DIR': str(self.root / 'config'),
                    'OPENCAIRN_SESSION_ID': 'synthetic-section'}

    def run_helper(self, before, incoming, section, *flags):
        self.log.write_text(before)
        result = subprocess.run(['bash', str(HELPER), str(self.log), '1', section, *flags],
                                input=incoming, text=True, capture_output=True,
                                env=self.env, cwd=self.root, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        return self.log.read_text()

    def test_file_list_rows_carry_exactly_one_bullet(self):
        shapes = ('A.md - changed', '- A.md - changed', '  - A.md - changed',
                  '\t- A.md - changed', '* A.md - changed', '+ A.md - changed',
                  '- - A.md - changed', '-\tA.md - changed')
        for section in ('Files Created', 'Files Updated'):
            for existing in ('None\n', '', '- Z.md - original\n'):
                for flags in ((), ('--replace',)):
                    for shape in shapes:
                        with self.subTest(section=section, existing=existing,
                                          flags=flags, shape=shape):
                            before = HEAD + '### ' + section + '\n' + existing + TAIL
                            after = self.run_helper(before, shape + '\nB.md - later row\n',
                                                    section, *flags)
                            kept = existing if existing.startswith('- Z') and not flags else ''
                            self.assertEqual(after, HEAD + '### ' + section + '\n' + kept
                                             + '- A.md - changed\n- B.md - later row\n' + TAIL)

    def test_dash_led_filename_and_checkbox_rows_are_not_mangled(self):
        before = HEAD + '### Files Created\nNone\n' + TAIL
        after = self.run_helper(before, '-option.md - new\n- [x] B.md - done\n', 'Files Created')
        self.assertEqual(after, before.replace('None\n', '- -option.md - new\n- [x] B.md - done\n', 1))

    def test_none_placeholder_can_still_be_written(self):
        before = HEAD + '### Files Created\n- A.md - mistaken\n' + TAIL
        for placeholder in ('None', 'None (nothing created)'):
            with self.subTest(placeholder=placeholder):
                after = self.run_helper(before, placeholder + '\n', 'Files Created', '--replace')
                self.assertEqual(after, HEAD + '### Files Created\n' + placeholder + '\n' + TAIL)

    def test_prose_sections_are_left_verbatim(self):
        before = HEAD + '### Files Created\nNone\n' + TAIL
        body = '\nFurther work: fixed the parser.\n  indented continuation\n* starred note\n'
        after = self.run_helper(before, body, 'Summary')
        self.assertEqual(after, before.replace('Done\n', 'Done\n' + body))
        pickup = '**For next session:** Continue\n  - nested detail\n'
        after = self.run_helper(before, pickup, 'Pickup Context', '--replace')
        self.assertEqual(after, before.replace('### Pickup Context\nNone\n',
                                               '### Pickup Context\n' + pickup + '\n'))


if __name__ == '__main__':
    unittest.main()
