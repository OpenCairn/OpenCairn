import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session

SCRIPT = Path(__file__).parents[1] / '.claude/scripts/harness-semantics-check.py'


class SemanticsCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = isolate_session(os.environ.copy(), self.root / 'config', 'fixture')
        self.env.update(HOME=str(self.root / 'home'), VAULT_PATH=str(self.root / 'vault'),
                        XDG_CACHE_HOME=str(self.root / 'cache'))
        Path(self.env['VAULT_PATH']).mkdir()
        self.manifest = self.root / 'manifest.json'
        self.baseline = {'verified_against': '2.1.10', 'evidence': ['fixture.md#record'],
                         'claims': ['fixture behavior']}
        self.manifest.write_text(json.dumps(self.baseline))
        self.cli = self.root / 'claude'
        self.stub("printf '2.1.11 (Claude Code)\\n'")

    def stub(self, command):
        self.cli.write_text('#!/bin/sh\n' + command + '\n')
        self.cli.chmod(0o755)

    def argv(self, *args):
        return [sys.executable, str(SCRIPT), '--manifest', str(self.manifest),
                '--claude', str(self.cli), *args]

    def run_check(self, *args):
        result = subprocess.run(self.argv(*args), env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_drift_warns_once_and_never_changes_manifest(self):
        original = self.manifest.read_bytes()
        self.assertIn('2.1.10 -> 2.1.11', self.run_check())
        self.assertEqual(self.run_check(), '')
        self.assertEqual(self.manifest.read_bytes(), original)
        self.stub("printf '2.1.12 (Claude Code)\\n'")
        self.assertIn('2.1.12', self.run_check())
        self.baseline['verified_against'] = '2.1.9'
        self.manifest.write_text(json.dumps(self.baseline))
        self.assertIn('2.1.9 -> 2.1.12', self.run_check())

    def test_matching_version_is_silent(self):
        self.stub("printf '2.1.10 (Claude Code)\\n'")
        self.assertEqual(self.run_check(), '')
        self.assertFalse(Path(self.env['XDG_CACHE_HOME']).exists())

    def test_missing_unknown_invalid_are_unverified(self):
        for content in [None, '{}', '{broken', json.dumps({'verified_against': 'unknown'}),
                        json.dumps({'verified_against': '2.1.10', 'evidence': [], 'claims': []})]:
            if content is None:
                self.manifest.unlink(missing_ok=True)
            else:
                self.manifest.write_text(content)
            self.assertIn('unverified', self.run_check())

    def test_version_errors_are_not_success(self):
        for command in ["echo malformed", "echo '2.1.10 (Claude Code)'; echo failure >&2; exit 7",
                        'sleep 1']:
            self.stub(command)
            self.assertIn('cannot observe', self.run_check('--timeout', '0.05'))
        self.cli.unlink()
        self.assertIn('cannot observe', self.run_check())

    def test_simultaneous_starts_warn_exactly_once(self):
        processes = [subprocess.Popen(self.argv(), env=self.env, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(8)]
        results = [p.communicate(timeout=5) for p in processes]
        self.assertTrue(all(p.returncode == 0 for p in processes))
        self.assertEqual(sum('2.1.10 -> 2.1.11' in out for out, _ in results), 1)

    def test_cache_in_vault_rejected_without_writing(self):
        vault = Path(self.env['VAULT_PATH'])
        before = list(vault.rglob('*'))
        self.assertIn('cache unavailable', self.run_check('--cache-dir', str(vault / 'cache')))
        self.assertEqual(list(vault.rglob('*')), before)


if __name__ == '__main__':
    unittest.main()
