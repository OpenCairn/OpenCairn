"""Exercise real closure output directly and through the receipt wrapper."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
VERIFY = ROOT / '.claude/scripts/park-verify.sh'
WRAPPER = ROOT / 'codex/skills/park/scripts/park-review.py'


class ClosureUtf8Tests(unittest.TestCase):
    def test_broken_encoder_fails_closed_only_when_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault = base / 'vault'
            (vault / '01 Now').mkdir(parents=True)
            (vault / '01 Now/This Week.md').write_text('- [ ] needle still open\n')
            log = vault / 'log.md'
            log.write_text('## Session 1 - Fixture\n### Summary\nDone\n'
                           '### Files Created\nNone\n### Files Updated\nNone\n'
                           '### Pickup Context\n**Project:** None\n')
            bindir = base / 'bin'
            bindir.mkdir()
            encoder = bindir / 'python3'
            encoder.write_text('#!/bin/sh\necho encoder-startup-failure >&2\nexit 42\n')
            encoder.chmod(0o755)
            for ident, expected in ((None, 0), ('absent', 0), ('needle', 1)):
                with self.subTest(ident=ident):
                    config = base / ('config-' + str(ident))
                    env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                               CLAUDE_CONFIG_DIR=str(config), OPENCAIRN_SESSION_ID='encoder-fixture',
                               CODEX_THREAD_ID='encoder-fixture', PYTHONDONTWRITEBYTECODE='1')
                    command = [str(VERIFY), str(vault), str(log), '1']
                    if ident is not None:
                        command += ['--ident', ident]
                    wrapped = subprocess.run([sys.executable, str(WRAPPER), 'run-verifier', '--', *command],
                                             env=env, capture_output=True, text=True)
                    self.assertEqual(wrapped.returncode, expected, wrapped.stdout + wrapped.stderr)
                    receipts = list((config / '.session-state/encoder-fixture.park-review/captures').glob('*.json'))
                    self.assertEqual(len(receipts), 1)
                    receipt = json.loads(receipts[0].read_text())
                    self.assertEqual(receipt['returncode'], expected)
                    if expected:
                        self.assertIn('encoder-startup-failure', receipt['text'])
                        self.assertIn('FAIL closure:', receipt['text'])
                        self.assertIn('RESULT: FAIL', receipt['text'])
                        self.assertNotIn('PASS closure:', receipt['text'])
                    else:
                        self.assertIn('RESULT: PASS', receipt['text'])
                        self.assertNotIn('encoder-startup-failure', receipt['text'])

    def test_character_boundary_and_receipt_status(self):
        for locale in ('C', 'C.UTF-8'):
            for char in ('a', 'é', '→', '😀'):
                for fail in (False, True):
                    with self.subTest(locale=locale, char=char, fail=fail), tempfile.TemporaryDirectory() as tmp:
                        base = Path(tmp)
                        vault = base / 'vault'
                        (vault / '01 Now').mkdir(parents=True)
                        # grep's '1:' plus this prefix places the character at column 100.
                        prefix = '- [ ] needle ' + 'x' * (99 - len('1:- [ ] needle '))
                        line = prefix + char + 'tail'
                        (vault / '01 Now/This Week.md').write_text(line + '\n', encoding='utf-8')
                        log = vault / 'log.md'
                        log.write_text('## Session 1 - Fixture\n### Summary\nDone\n'
                                       '### Files Created\nNone\n### Files Updated\nNone\n'
                                       '### Pickup Context\n' + ('' if fail else '**Project:** None\n'), encoding='utf-8')
                        env = dict(os.environ, HOME=str(base / 'home'), CLAUDE_CONFIG_DIR=str(base / 'config'),
                                   OPENCAIRN_SESSION_ID='closure-fixture', CLAUDE_CODE_SESSION_ID='closure-fixture',
                                   CODEX_THREAD_ID='closure-fixture', LC_ALL=locale, PYTHONUTF8='1',
                                   PYTHONDONTWRITEBYTECODE='1')
                        command = [str(VERIFY), str(vault), str(log), '1', '--ident', 'needle']
                        direct = subprocess.run(command, env=env, capture_output=True)
                        output = direct.stdout.decode('utf-8')
                        self.assertIn('1:' + prefix + char, output)
                        self.assertNotIn(char + 'tail', output)
                        self.assertEqual(direct.returncode, int(fail))
                        wrapped = subprocess.run([sys.executable, str(WRAPPER), 'run-verifier', '--', *command], env=env, capture_output=True)
                        self.assertEqual(wrapped.returncode, direct.returncode, wrapped.stderr.decode('utf-8'))
                        self.assertIn(output, wrapped.stdout.decode('utf-8'))
                        receipts = list((base / 'config/.session-state/closure-fixture.park-review/captures').glob('*.json'))
                        self.assertEqual(len(receipts), 1)
                        receipt = json.loads(receipts[0].read_text(encoding='utf-8'))
                        self.assertEqual(receipt['returncode'], direct.returncode)
                        self.assertIn(output, receipt['text'])
                        self.assertIn('REVIEW closure:', receipt['text'])
                        self.assertIn('RESULT: FAIL' if fail else 'RESULT: REVIEW', receipt['text'])


if __name__ == '__main__':
    unittest.main()
