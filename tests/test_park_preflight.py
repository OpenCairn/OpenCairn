import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / '.claude/scripts/park-preflight.py'


class ParkPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.config = self.root / 'config'
        self.home = self.root / 'home'
        self.home.mkdir()
        (self.vault / '.claude/scripts').mkdir(parents=True)
        for name in ['resolve-vault.sh', 'session-ledger.sh', 'lib-session.sh']:
            shutil.copyfile(ROOT / '.claude/scripts' / name, self.vault / '.claude/scripts' / name)
        self.now = self.vault / '01 Now'
        self.now.mkdir()
        self.week = self.now / 'This Week.md'
        self.tickler = self.now / 'Tickler.md'
        self.week.write_text('# Week\n- [ ] Alpha task\n- [x] Completed task\n')
        self.tickler.write_text('# Tickler\n- [ ] Beta task\n')
        self.state = self.config / '.session-state'
        self.state.mkdir(parents=True)
        self.ledger = self.state / 'event-root.tsv'
        self.ledger.write_text('2026-01-01T00:00:00Z\tWrite\t/fixture/note.md\tmain\n')
        self.env = isolate_session(os.environ.copy(), self.config, 'wrong-inherited')
        self.env.update(HOME=str(self.home), VAULT_PATH=str(self.vault))
        (self.home / 'sentinel').write_text('unchanged')

    def invoke(self, prompt='/park', args=(), **event):
        payload = {'hook_event_name': 'UserPromptSubmit', 'prompt': prompt,
                   'session_id': 'event-root', 'cwd': str(self.root),
                   'transcript_path': str(self.root / 'transcript.jsonl'), **event}
        result = subprocess.run([sys.executable, str(SCRIPT), *args], input=json.dumps(payload),
                         env=self.env, text=True, capture_output=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def bundle(self, **kwargs):
        data = json.loads(self.invoke(**kwargs).stdout)
        if 'hookSpecificOutput' in data:
            hook = data['hookSpecificOutput']
            self.assertEqual(hook['hookEventName'], 'UserPromptSubmit')
            return json.loads(hook['additionalContext'].split('\n', 1)[1])
        return data

    def test_genuine_and_expanded_requests(self):
        prompts = ['/park', '/park --quick', '/checkpoint', '$park', '$checkpoint --quick',
            '<command-name>/park</command-name>\n<command-args>--quick</command-args>',
            '<command-message>checkpoint</command-message>\n<command-name>/checkpoint</command-name>',
            '<skill><name>park</name><instructions>Capture session</instructions></skill>']
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                data = self.bundle(prompt=prompt)
                self.assertEqual(data['kind'], 'park-preflight')
                self.assertFalse(data['final_dedup_complete'])

    def test_quoted_code_pasted_instructions_questions_other_event_no_output(self):
        for prompt in ['Explain /park', 'How does /park work?', '"/park"', "'/park'", '`/park`',
                       '```\n/park\n```', '> /park', '# Instructions\n/park',
                       '/park\nthen do something', '/parking', '/park?', '/park --quick?', '/park is a command in this pasted instruction',
                       '<instructions><command-name>/park</command-name></instructions>']:
            with self.subTest(prompt=prompt):
                self.assertEqual(self.invoke(prompt).stdout, '')
        self.assertEqual(self.invoke(hook_event_name='Stop').stdout, '')

    def test_event_root_ledger_and_complete_actual_command_receipts(self):
        data = self.bundle()
        self.assertEqual(data['session']['id'], 'event-root')
        ledger = data['ledger']
        self.assertEqual(ledger['state'], 'checked_nonempty')
        self.assertIn('/fixture/note.md', ledger['receipt']['stdout'])
        self.assertEqual(ledger['receipt']['argv'], ['bash', str(self.vault / '.claude/scripts/session-ledger.sh'), '--read'])
        self.assertEqual(ledger['receipt']['cwd'], str(self.root))
        self.assertEqual(ledger['receipt']['exit_status'], 0)
        self.assertEqual(base64.b64decode(ledger['receipt']['stdout_base64']).decode(), ledger['receipt']['stdout'])
        self.assertEqual(ledger['receipt']['stderr'], '')
        self.assertIn('TZ=', data['clock']['receipt']['stdout'])
        self.assertEqual(data['clock']['receipt']['argv'][0], 'date')
        for entry in data['task_candidates']:
            self.assertEqual(entry['state'], 'checked_nonempty')
            self.assertTrue(entry['source']['sha256'])
        self.assertIn('Alpha task', data['task_candidates'][0]['receipt']['stdout'])
        self.assertNotIn('Completed task', data['task_candidates'][0]['receipt']['stdout'])

    def test_missing_and_checked_empty_are_distinct(self):
        self.ledger.unlink()
        self.week.write_text('# Empty\n- [x] done\n')
        self.tickler.unlink()
        data = self.bundle()
        self.assertEqual(data['ledger']['state'], 'no_ledger')
        self.assertEqual(data['task_candidates'][0]['state'], 'checked_empty')
        self.assertEqual(data['task_candidates'][0]['receipt']['exit_status'], 1)
        self.assertEqual(data['task_candidates'][1]['state'], 'missing')
        self.assertEqual(data['task_candidates'][1]['receipt']['exit_status'], 2)
        self.assertTrue(data['task_candidates'][1]['receipt']['stderr'])
        self.ledger.write_text('')
        self.assertEqual(self.bundle()['ledger']['state'], 'checked_empty')

    def test_missing_session_invalid_vault_and_command_errors_are_unknown(self):
        data = self.bundle(session_id='')
        self.assertEqual(data['ledger']['state'], 'unknown_session')
        self.assertEqual(data['ledger']['receipt']['exit_status'], 1)
        self.env.pop('VAULT_PATH')
        data = self.bundle()
        self.assertEqual(data['vault']['state'], 'unknown')
        self.assertEqual(data['task_candidates'], [])
        self.env['VAULT_PATH'] = str(self.vault)
        (self.vault / '.claude/scripts/session-ledger.sh').write_text('echo unsupported >&2\nexit 3\n')
        data = self.bundle()
        self.assertEqual(data['ledger']['state'], 'error')
        self.assertEqual(data['ledger']['receipt']['stderr'], 'unsupported\n')

    def test_missing_rg_is_error_not_checked_empty(self):
        bindir = self.root / 'bin'
        bindir.mkdir()
        for cmd in ['bash', 'dirname', 'date', 'head', 'cut', 'awk']:
            (bindir / cmd).symlink_to(shutil.which(cmd))
        self.env['PATH'] = str(bindir)
        data = self.bundle()
        for entry in data['task_candidates']:
            self.assertEqual(entry['state'], 'error')
            self.assertEqual(entry['receipt']['status'], 'command_error')
            self.assertIsNone(entry['receipt']['exit_status'])

    def test_timeout_retains_partial_stdout_stderr(self):
        (self.vault / '.claude/scripts/session-ledger.sh').write_text(
            'printf partial; printf diagnostic >&2; sleep 1\n')
        data = self.bundle(args=['--timeout', '0.05'])
        self.assertEqual(data['ledger']['state'], 'error')
        receipt = data['ledger']['receipt']
        self.assertEqual(receipt['status'], 'timeout')
        self.assertEqual(receipt['stdout'], 'partial')
        self.assertEqual(receipt['stderr'], 'diagnostic')

    def test_complete_large_receipts_are_not_silently_trimmed(self):
        body = 'A' * 20000
        diagnostic = 'B' * 12000
        (self.vault / '.claude/scripts/session-ledger.sh').write_text(
            "printf '%s' '" + body + "'; printf '%s' '" + diagnostic + "' >&2; exit 4\n")
        data = self.bundle()
        receipt = data['ledger']['receipt']
        self.assertEqual(data['ledger']['state'], 'error')
        self.assertEqual(receipt['stdout'], body)
        self.assertEqual(receipt['stderr'], diagnostic)
        self.assertEqual(base64.b64decode(receipt['stdout_base64']), body.encode())
        self.assertEqual(base64.b64decode(receipt['stderr_base64']), diagnostic.encode())
        self.assertEqual(receipt['output_bytes'], 32000)

    def test_revalidation_detects_changed_sources_and_missing_surfaces(self):
        bundle = self.bundle()
        path = self.root / 'bundle.json'
        path.write_text(json.dumps(bundle))
        data = json.loads(self.invoke(args=['--revalidate', str(path)]).stdout)
        self.assertTrue(data['source_hashes_match'])
        self.assertFalse(data['final_dedup_complete'])
        self.week.write_text('- [ ] Changed task\n')
        data = json.loads(self.invoke(args=['--revalidate', str(path)]).stdout)
        self.assertFalse(data['source_hashes_match'])
        self.assertIn(str(self.week), data['invalidated_sources'])
        self.assertEqual(data['action'], 'fresh_read_and_dedup_before_writing')
        self.week.unlink()
        data = json.loads(self.invoke(args=['--revalidate', str(path)]).stdout)
        self.assertFalse(data['source_hashes_match'])

    def test_manual_mode_uses_explicit_parent_and_no_home_vault_writes(self):
        def snapshot(directory):
            return {str(p.relative_to(directory)): p.read_bytes()
                    for p in directory.rglob('*') if p.is_file()}
        before = {str(p): snapshot(p) for p in [self.home, self.vault, self.config]}
        data = self.bundle(args=['--manual', '--session-id', 'event-root', '--cwd', str(self.root)])
        self.assertEqual(data['session']['source'], 'manual_explicit')
        self.assertEqual(data['ledger']['state'], 'checked_nonempty')
        self.assertEqual(before, {str(p): snapshot(p) for p in [self.home, self.vault, self.config]})


if __name__ == '__main__':
    unittest.main()
