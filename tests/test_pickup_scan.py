"""Check the pickup scanner's seven-column interface with optional metadata."""
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / '.claude/scripts/pickup-scan.sh'


class PickupScanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.logs = self.root / 'logs'
        self.logs.mkdir()

    def scan(self, sections, *options):
        (self.logs / '2026-01-02.md').write_text('# Session fixture\n\n' + sections)
        result = subprocess.run(
            ['bash', str(SCANNER), '--days=36500', *options, str(self.logs)],
            text=True, capture_output=True, check=True)
        self.assertEqual(result.stderr, '')
        rows = [line.split('\t') for line in result.stdout.splitlines()]
        self.assertTrue(all(len(row) == 7 for row in rows), rows)
        return rows

    def section(self, *, number=1, time='09:00am', project='Project Alpha',
                summary='Continue the reviewed change.', loops=1):
        heading = f'## Session {number} - Fixture pickup'
        if time:
            heading += f' ({time})'
        project_line = f'[[03 Projects/{project}]]' if project else 'None'
        return (heading + '\n\n### Summary\n' + summary +
                '\n\n### Next Steps / Open Loops\n' + '- Continue fixture work\n' * loops +
                '\n### Pickup Context\n**Project:** ' + project_line + '\n')

    def test_optional_metadata_keeps_each_column_in_place(self):
        for time, project, summary, loops in [
            ('09:00am', 'Project Alpha', 'Continue the reviewed change.', 1),
            ('09:00am', '', 'Keep this summary in its own column.', 0),
            ('', 'Project Alpha', 'Timestamp is absent.', 1),
            ('', '', '', 0),
            ('09:00am', 'Project Alpha', '', 0),
        ]:
            with self.subTest(time=time, project=project, summary=summary):
                rows = self.scan(self.section(time=time, project=project,
                                              summary=summary, loops=loops))
                self.assertEqual(rows, [['2026-01-02', '1', 'Fixture pickup', time,
                                         project, str(loops), summary]])

    def test_hidden_project_filter_uses_project_even_without_time(self):
        hidden = self.root / 'hidden.txt'
        hidden.write_text('Project Alpha\n0\n')
        rows = self.scan(
            self.section(number=1, time='', project='Project Alpha') + '\n' +
            self.section(number=2, project='', loops=0),
            '--hidden-file=' + str(hidden))
        self.assertEqual([row[1] for row in rows], ['2'])
        self.assertEqual(rows[0][4:6], ['', '0'])

    def test_summary_normalisation_preserves_unicode_and_backslashes(self):
        summary = 'Keep café\\draft\tverbatim.'
        rows = self.scan(self.section(project='', summary=summary))
        self.assertEqual(rows[0][6], 'Keep café\\draft verbatim.')


if __name__ == '__main__':
    unittest.main()
