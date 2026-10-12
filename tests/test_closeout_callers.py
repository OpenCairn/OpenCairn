"""Exercise Goodnight's authored records through the retained close-out helpers.

Reviewer answers below are simulated protocol inputs, not an independent audit.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tests.session_isolation import isolate_session

ROOT = Path(__file__).parents[1]
SCRIPTS = ROOT / '.claude/scripts'
REVIEW = ROOT / 'codex/skills/park/scripts/park-review.py'


class CloseoutCallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.config = self.root / 'config'
        self.env = isolate_session(os.environ.copy(), self.config, 'closeout-fixture')
        self.env['VAULT_PATH'] = str(self.vault)
        self.env['HOME'] = str(self.root / 'home')
        self.week = self.vault / '01 Now/This Week.md'
        self.week.parent.mkdir(parents=True)
        self.week.write_text('# This Week\n\n## Tomorrow\n- [ ] Continue fixture task\n')
        (self.week.parent / 'Tickler.md').write_text('# Tickler\n')

    def run_cmd(self, args, body=None, expected=0):
        result = subprocess.run([str(a) for a in args], input=body, text=True,
                                capture_output=True, env=self.env, cwd=self.root)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def helper(self, *args, body=None, expected=0):
        return self.run_cmd([sys.executable, REVIEW, *args], body, expected)

    def make_record(self, lane, catchup, day):
        source = ROOT / (f'codex/skills/goodnight/SKILL.md' if lane == 'codex'
                         else '.claude/commands/goodnight.md')
        skill = source.read_text()
        start = skill.index('### C1.' if catchup else '### 14. Append')
        tail = skill[start:]
        # Read the actual session-writer heredoc, then provide concrete fixture values.
        body = re.search(r"cat << 'EOF'[^\n]*write-session.sh[^\n]*\n(.*?)\n\s*EOF", tail, re.S).group(1)
        body = textwrap.dedent(body)
        report_rel = f'06 Archive/OpenCairn/Daily Reports/{day}.md'
        report = self.vault / report_rel
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text('# Daily Report\n\n## Sessions\n1. Fixture close-out\n')
        body = re.sub(r'^\[.*\]$', 'Fixture close-out recorded.', body, flags=re.M)
        body = re.sub(r'^- \[Daily Report.*\]$', f'- {report_rel} - Daily report', body, flags=re.M)
        body = body.replace('YYYY-MM-DD', day)
        body = re.sub(r'^- \[.*\]$', 'None', body, flags=re.M)
        body = re.sub(r'\*\*For next session:\*\*.*', '**For next session:** Continue fixture task.', body)
        body = re.sub(r'\*\*Project:\*\*.*', '**Project:** None', body)
        log = self.vault / f'06 Archive/OpenCairn/Session Logs/{day}.md'
        log.parent.mkdir(parents=True, exist_ok=True)
        topic = 'Goodnight catch-up via $morning' if catchup else 'Goodnight: Fixture'
        self.run_cmd(['bash', SCRIPTS / 'write-session.sh', log, '--auto-number', topic, '09:00am'], body + '\n')
        self.assertNotIn('### Next Steps / Open Loops', log.read_text())
        return log, report

    def verify_and_build(self, log, report, *, include_week=True):
        args = ['run-verifier', '--', SCRIPTS / 'park-verify.sh', self.vault, log, '1', '--touched', report]
        if include_week:
            args += ['--touched', self.week]
        result = self.helper(*args)
        self.assertIn('RESULT: PASS', result.stdout)
        self.helper('capture', '--kind', 'propagation', '--label', 'Goodnight propagation',
                    body='NEW report and session entry; task retained under Tomorrow. Fixture checked.\n')
        self.helper('capture', '--kind', 'evidence', '--source', 'goodnight caller contract',
                    '--label', 'Goodnight acceptance checks', '--provenance', 'primary',
                    body='Preserve unfinished tasks and the pre-routing plan; export only after clean review.\n')
        result = self.helper('build', '--vault', self.vault, '--session-log', log, '--number', '1')
        brief = Path(re.search(r'^Reviewer brief: (.+)$', result.stdout, re.M).group(1))
        manifest = json.loads((brief.parent / 'review-brief-manifest.json').read_text())
        self.assertIn('goodnight caller contract', brief.read_text())
        self.assertEqual(manifest['session_log'], str(log))
        self.assertEqual(manifest['session_number'], 1)
        return manifest, result

    def test_nightly_and_catchup_records_use_same_verifier(self):
        for lane in ('claude', 'codex'):
            for catchup in (False, True):
                with self.subTest(lane=lane, catchup=catchup):
                    day = f'2001-01-{1 + (lane == "codex") * 2 + catchup:02d}'
                    self.helper('begin-run')
                    log, report = self.make_record(lane, catchup, day)
                    self.run_cmd(['bash', SCRIPTS / 'backfill-files-updated.sh', log, '1'],
                                 '- 01 Now/This Week.md - Retained unfinished task\n')
                    for path in (log, report, self.week):
                        self.helper('classify', '--vault', self.vault, '--path', path,
                                    '--semantic', '--reason', 'fixture close-out')
                    manifest, result = self.verify_and_build(log, report)
                    self.assertIn('Reviewer brief:', result.stdout)
                    self.assertIn('Continue fixture task', self.week.read_text())
                    attest = '\n'.join(f"ATTEST {item['sha256']} {item['path']}" for item in manifest['full_read'])
                    self.helper('record-audit', '--reviewer', 'fixture-simulated', '--from-brief',
                                body=attest + '\nTerminal state: findings\n', expected=1)
                    accepted = self.helper('record-audit', '--reviewer', 'fixture-simulated', '--from-brief',
                                           body=attest + '\nTerminal state: clean\n')
                    self.assertIn('Audit receipt:', accepted.stdout)


    def test_omitted_post_log_write_is_not_a_clean_verifier_receipt(self):
        self.helper('begin-run')
        log, report = self.make_record('codex', True, '2001-02-01')
        result = self.helper('run-verifier', '--', SCRIPTS / 'park-verify.sh', self.vault, log, '1',
                             '--touched', report, '--touched', self.week, expected=1)
        self.assertIn('FAIL backfill', result.stdout)
        self.assertNotIn('RESULT: PASS', result.stdout)
        self.helper('capture', '--kind', 'propagation', '--label', 'Fixture', body='Checked fixture.\n')
        self.helper('build', '--vault', self.vault, '--session-log', log, '--number', '1', expected=1)

    def test_new_date_generation_does_not_reuse_prior_propagation(self):
        self.helper('begin-run')
        log, report = self.make_record('codex', True, '2001-03-01')
        self.helper('capture', '--kind', 'propagation', '--label', 'Prior day', body='Prior day only.\n')
        self.helper('begin-run')
        log, report = self.make_record('codex', True, '2001-03-02')
        self.helper('run-verifier', '--', SCRIPTS / 'park-verify.sh', self.vault, log, '1', '--touched', report)
        result = self.helper('build', '--vault', self.vault, '--session-log', log, '--number', '1', expected=1)
        self.assertIn('propagation', result.stderr.lower())


if __name__ == '__main__':
    unittest.main()
