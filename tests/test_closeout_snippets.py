"""Run the closeout prompt's actual shell recipes on isolated inputs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
CLOSEOUTS = (ROOT / '.claude/commands/_closeout.md', ROOT / 'codex/skills/_closeout.md')
PARKS = (ROOT / '.claude/commands/park.md', ROOT / 'codex/skills/park/SKILL.md')
GOODNIGHTS = (ROOT / '.claude/commands/goodnight.md', ROOT / 'codex/skills/goodnight/SKILL.md')


def recipe(path: Path, marker: str) -> str:
    text = path.read_text(encoding='utf-8')
    match = re.search(r'<!-- BEGIN ' + marker + r' -->\s*```bash\n(.*?)\n```\s*<!-- END ' + marker + r' -->', text, re.S)
    if match is None:
        raise AssertionError(f'{path}: missing executable {marker} recipe')
    return match.group(1)


def run_bash(script: str, root: Path, **values: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(values)
    env['TMPDIR'] = str(root)
    return subprocess.run(['bash', '-c', script.replace('{VAULT}', str(root/'vault'))], cwd=root, env=env, text=True, capture_output=True, timeout=20)


class CloseoutSnippetTests(unittest.TestCase):
    def test_session_extraction_stops_at_concurrent_entry_and_keeps_complete_paths(self):
        for source in CLOSEOUTS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                log = root / 'day.md'
                # Terminal entry intentionally has no final newline. N=1 must not match N=10.
                log.write_text('## Session 1 - Assigned\n### Summary\nOwn work\n'
                               '### Files Created\n- `04 Areas/Context - fixture.md` - purpose\n'
                               '### Files Updated\n- `/tmp/tool` (remote) - remote fixture\n'
                               '### Files Deleted\n- `04 Areas/Old - fixture.md` (deleted) - removal\n'
                               '### Pickup Context\n**Project:** None\n'
                               '## Session 10 - Concurrent\n### Summary\nForeign work\n'
                               '### Files Updated\n- `04 Areas/Foreign.md` - foreign', encoding='utf-8')
                suffix = '\nprintf "BLOCK=%s\\nPATHS=%s\\nCOUNT=%s\\n" "$SESSION_BLOCK" "$SESSION_PATHS" "${#TOUCHED[@]}"'
                result = run_bash(recipe(source, 'SESSION EXTRACT') + suffix, root, SESSION_LOG=str(log), N='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                fields = dict(line.split('=', 1) for line in result.stdout.splitlines())
                self.assertNotIn('Foreign work', Path(fields['BLOCK']).read_text())
                self.assertEqual(Path(fields['PATHS']).read_text().splitlines(),
                                 ['04 Areas/Context - fixture.md', '/tmp/tool', '04 Areas/Old - fixture.md'])
                self.assertEqual(fields['COUNT'], '6', 'three repeated --touched/path pairs')
                last = run_bash(recipe(source, 'SESSION EXTRACT') + suffix, root, SESSION_LOG=str(log), N='10')
                self.assertEqual(last.returncode, 0, last.stderr)
                final = dict(line.split('=', 1) for line in last.stdout.splitlines())
                self.assertIn('Foreign work', Path(final['BLOCK']).read_text())
                self.assertNotIn('Own work', Path(final['BLOCK']).read_text())

    def test_session_extraction_refuses_absent_duplicate_and_malformed_rows(self):
        for source in CLOSEOUTS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); log = root/'day.md'
                for body, number in [('## Session 10 - Other\n', '1'),
                                     ('## Session 1 - A\n## Session 1 - B\n', '1'),
                                     ('## Session 1 - A\n### Files Updated\n- `unterminated - bad\n', '1')]:
                    log.write_text(body)
                    result = run_bash(recipe(source, 'SESSION EXTRACT') + '\necho MUST_NOT_RUN', root,
                                      SESSION_LOG=str(log), N=number)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn('MUST_NOT_RUN', result.stdout)
                    self.assertIn('ERROR:', result.stderr)

    def test_live_search_reaches_ignored_hidden_text_without_short_substring_flood(self):
        for source in PARKS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); vault = root/'vault'; vault.mkdir()
                (vault/'.gitignore').write_text('*\n!*.md\n!*/\n')
                for name, text in [('04 Areas/driver.py', 'UPS group\n'),
                                   ('04 Areas/.hidden/config.toml', 'UPS\n'),
                                   ('04 Areas/noise.txt', 'BACKUPS\n'),
                                   ('06 Archive/frozen.md', 'UPS\n'),
                                   ('04 Areas/photo.xmp', 'UPS\n')]:
                    path = vault/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
                out, err = root/'raw.out', root/'raw.err'
                result = run_bash(recipe(source, 'LIVE SEARCH'), root, VAULT=str(vault), NEEDLE='UPS',
                                  MATCH_MODE='word', RAW_OUT=str(out), RAW_ERR=str(err))
                self.assertEqual(result.returncode, 0, result.stderr)
                hits = out.read_text().splitlines()
                self.assertEqual(len(hits), 2)
                self.assertTrue(any('.hidden/config.toml' in line for line in hits))
                self.assertTrue(any('driver.py' in line for line in hits))
                self.assertNotIn('BACKUPS', out.read_text())
                self.assertIn('exit_status: 0', result.stdout)
                # A reused receipt path is an error, not silent truncation/overwrite.
                reused = run_bash(recipe(source, 'LIVE SEARCH'), root, VAULT=str(vault), NEEDLE='UPS',
                                  MATCH_MODE='word', RAW_OUT=str(out), RAW_ERR=str(err))
                self.assertEqual(reused.returncode, 2)
                self.assertEqual(len(out.read_text().splitlines()), 2)
                miss = run_bash(recipe(source, 'LIVE SEARCH'), root, VAULT=str(vault), NEEDLE='absent-subject',
                                MATCH_MODE='fixed', RAW_OUT=str(root/'miss.out'), RAW_ERR=str(root/'miss.err'))
                self.assertEqual(miss.returncode, 0, miss.stderr)
                self.assertIn('exit_status: 1', miss.stdout)
                self.assertEqual((root/'miss.out').read_bytes(), b'')

    def test_completion_lookup_binds_subject_generation_and_report_hash(self):
        for source in CLOSEOUTS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); config = root/'config'; state = config/'.session-state'
                run = state/'fixture.park-review/runs/generation'; run.mkdir(parents=True)
                receipts = state/'.park-audit-receipts'; receipts.mkdir()
                log = root/'day.md'; log.write_text('## Session 1 - Fixture\n')
                (run/'review-brief-manifest.json').write_text(json.dumps({'session_log':str(log), 'session_number':1,
                                                                        'run_generation':'generation'}))
                report = 'Fixture evidence\nTerminal state: clean\n'
                receipt = {'run_generation':'generation', 'status':'clean', 'report':report,
                           'report_sha256':hashlib.sha256(report.encode()).hexdigest()}
                rp = receipts/'audit.json'; rp.write_text(json.dumps(receipt))
                env = dict(CLAUDE_CONFIG_DIR=str(config), SESSION_LOG=str(log), N='1')
                good = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
                self.assertEqual(good.returncode, 0, good.stderr)
                self.assertIn('ACCEPTED\t', good.stdout)
                wrong = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **dict(env, N='2'))
                self.assertIn('NO_ACCEPTED_RECEIPT', wrong.stdout)
                self.assertNotIn('ACCEPTED\t', wrong.stdout)
                receipt['report'] += 'tampered'
                rp.write_text(json.dumps(receipt))
                bad = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
                self.assertIn('NO_ACCEPTED_RECEIPT', bad.stdout)
                legacy = state/'legacy.closeout/report.md'; legacy.parent.mkdir()
                legacy.write_text(f'Session log: {log}\nSession number: 1\nClose-out accepted: clean\nTerminal state: clean\n')
                candidate = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
                self.assertIn('LEGACY_CANDIDATE\t', candidate.stdout)
                self.assertNotIn('ACCEPTED\t', candidate.stdout)


if __name__ == '__main__':
    unittest.main()
