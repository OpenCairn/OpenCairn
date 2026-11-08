"""Objective contracts for the CLI-unavailable weekly hygiene scan."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.claude/scripts/hygiene-links.py'
spec = importlib.util.spec_from_file_location('hygiene_links', SCRIPT)
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class HygieneLinksTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, path, body):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def run_scan(self, root=None):
        result = subprocess.run([sys.executable, str(SCRIPT), str(root or self.root)],
                                capture_output=True, text=True)
        return result, json.loads(result.stdout)

    def test_archive_versions_duplicate_and_target_normalisation(self):
        self.write('03 Projects/Workshop.md', '[[04 Areas/Garden#Plans|alias]] '
                   '[[Missing  ]] [[06 Archive/Old Note]] [[Garden]] [[#Local]]\n'
                   '[[Folder/Leading ]] [[Folder/With.md]] [[café]]\n')
        self.write('04 Areas/Garden.md', '[[Workshop]]')
        self.write('04 Areas/Quiet Note.md', '')
        self.write('04 Areas/From Archive.md', '')
        self.write('04 Areas/Duplicate.md', '')
        self.write('03 Projects/Cold/Duplicate.md', '')
        self.write('04 Areas/café.md', '')
        self.write('06 Archive/Old Note.md', '[[From Archive]] [[Duplicate]] [[Archive Missing]]')
        self.write('.stversions/Shadow.md', '[[Quiet Note]] [[Versions Missing]]')
        self.write('04 Areas/.stversions/Copy.md', '[[Another Missing]]')
        result, data = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data['unresolved_targets'], ['Leading', 'Missing', 'With.md'])
        self.assertEqual(data['orphan_paths'], ['04 Areas/Quiet Note.md'])
        self.assertEqual(data['notes_scanned'], 8)
        self.assertEqual(data['deadends'], 'unavailable (CLI unavailable)')

    def test_symlink_is_read_but_not_an_orphan_candidate(self):
        self.write('05 Resources/Target.md', '[[Missing]]')
        link = self.root / '03 Projects/Alias.md'
        link.parent.mkdir(parents=True)
        link.symlink_to('../05 Resources/Target.md')
        result, data = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data['unresolved_targets'], ['Missing'])
        self.assertEqual(data['orphan_paths'], [])
        self.assertEqual(data['notes_scanned'], 2)

    def test_exclusions_are_grep_bre_on_relative_findings(self):
        self.write('03 Projects/Workshop.md', '[[Missing Note]] [[Hidden Note]]')
        self.write('04 Areas/Quiet Note.md', '')
        for exclusions, expected in [
            ('', (['Hidden Note', 'Missing Note'], ['03 Projects/Workshop.md', '04 Areas/Quiet Note.md'])),
            ('# comment\n\n', (['Hidden Note', 'Missing Note'], ['03 Projects/Workshop.md', '04 Areas/Quiet Note.md'])),
            ('^/\nHidden Note\\|Missing Note\nQuiet Note\n', ([], ['03 Projects/Workshop.md'])),
        ]:
            with self.subTest(exclusions=exclusions):
                self.write('.claude/hygiene-excludes', exclusions)
                result, data = self.run_scan()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((data['unresolved_targets'], data['orphan_paths']), expected)

    def test_empty_vault_is_distinct_from_missing(self):
        result, data = self.run_scan()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data['unresolved_targets'], [])
        self.assertEqual(data['orphan_paths'], [])
        result, data = self.run_scan(self.root / 'missing')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(result.stderr)
        self.assertEqual(data['status'], 'unavailable')
        self.assertIsNone(data['unresolved_targets'])
        self.assertIsNone(data['orphan_paths'])

    def test_invalid_exclusions_fail_even_without_findings(self):
        self.write('.claude/hygiene-excludes', '[\n')
        result, data = self.run_scan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('filter failed', result.stderr)
        self.assertIsNone(data['unresolved_targets'])

    def test_unreadable_note_excludes_and_enumeration_propagate(self):
        self.write('03 Projects/Workshop.md', '[[Missing]]')
        with patch.object(Path, 'read_bytes', side_effect=PermissionError('fixture read denied')):
            with self.assertRaises(PermissionError):
                scanner.scan(self.root)
        def denied_walk(root, onerror):
            onerror(PermissionError('fixture enumeration denied'))
            return iter(())
        with patch.object(scanner.os, 'walk', side_effect=denied_walk):
            with self.assertRaises(PermissionError):
                scanner.scan(self.root)
        self.write('.claude/hygiene-excludes', 'Missing')
        original = Path.read_bytes
        def read(path):
            if path.name == 'hygiene-excludes':
                raise PermissionError('fixture exclusions denied')
            return original(path)
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaises(PermissionError):
                scanner.scan(self.root)

    def test_failed_grep_is_not_empty_findings(self):
        self.write('.claude/hygiene-excludes', 'anything')
        with patch.object(scanner.subprocess, 'run', return_value=
                          subprocess.CompletedProcess([], 2, b'', b'fixture grep failed')):
            with self.assertRaisesRegex(OSError, 'fixture grep failed'):
                scanner.scan(self.root)

    def test_binary_markdown_fails_instead_of_partial_results(self):
        self.write('04 Areas/Binary.md', '[[Missing]]\0')
        result, data = self.run_scan()
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(data['orphan_paths'])


if __name__ == '__main__':
    unittest.main()
