import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / '.claude/scripts/parboil-check.sh'
WIRE = ROOT / '.claude/scripts/wire-park-hooks.sh'


class ParboilCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name)
        self.state = self.config / '.session-state'
        self.state.mkdir()
        self.sid = 'fixture-session'
        self.ledger = self.state / f'{self.sid}.tsv'
        self.ledger.write_text('2026-01-01T00:00:00Z\tWrite\t/tmp/one.md\tmain\n' * 3)
        self.transcript = self.config / 'transcript.jsonl'
        self.records = []
        self.add('assistant', [{'type': 'text', 'text': 'Working.'}], 160000)
        self.env = {**isolate_session(os.environ.copy(), self.config, self.sid),
                    'VAULT_PATH': str(self.config),
                    'OPENCAIRN_PARBOIL_TOKENS': '150000',
                    'OPENCAIRN_PARBOIL_INTERVAL_TOKENS': '50000'}

    def add(self, role, content, tokens=0):
        self.records.append({'type': role, 'message': {'role': role,
            'content': content, 'usage': {'input_tokens': tokens}}})
        self.transcript.write_text(''.join(json.dumps(r) + '\n' for r in self.records))

    def hook(self, prompt='Continue.', event='UserPromptSubmit', **kwargs):
        payload = {'session_id': self.sid, 'transcript_path': str(self.transcript),
                   'hook_event_name': event, 'prompt': prompt, **kwargs}
        r = subprocess.run(['bash', str(HOOK)], input=json.dumps(payload),
            text=True, capture_output=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def complete(self):
        self.add('user', '/park')
        self.hook(event='Stop', last_assistant_message='✓ Session 1 saved: session.md\n\nParked.\n')
        self.add('user', 'Work on the next item.')

    def test_ordinary_written_session_triggers(self):
        self.assertIn('<parboil-trigger', self.hook())

    def test_direct_park_does_not_trigger_or_spend_retry_slot(self):
        self.assertEqual(self.hook('/park --quick'), '')
        self.assertFalse((self.state / f'{self.sid}.parboil.state').exists())

    def test_expanded_park_prompt_does_not_trigger(self):
        self.assertEqual(self.hook('<command-name>/park</command-name>\n<command-args/>'), '')

    def test_active_park_in_transcript_is_suppressed(self):
        self.add('user', '/park')
        self.add('assistant', [{'type': 'text', 'text': 'Checking the session.'}], 220000)
        self.assertEqual(self.hook(), '')

    def test_active_request_survives_more_than_token_tail(self):
        self.add('user', '/park')
        for _ in range(205):
            self.records.append({'type': 'assistant', 'message': {
                'content': [{'type': 'text', 'text': 'Checking.'}],
                'usage': {'input_tokens': 220000}}})
        self.transcript.write_text(''.join(json.dumps(r) + '\n' for r in self.records))
        self.assertEqual(self.hook(), '')

    def test_tool_results_do_not_release_active_park(self):
        self.add('user', '/park')
        self.add('user', [{'type': 'tool_result', 'content': 'Done'}])
        self.assertEqual(self.hook(), '')

    def test_question_about_park_and_tool_output_are_not_request(self):
        self.add('user', 'Did you /park?')
        self.add('user', [{'type': 'tool_result', 'content': '/park'}])
        self.assertIn('<parboil-trigger', self.hook())

    def test_fenced_completion_example_is_not_completion(self):
        self.add('user', '/park')
        self.hook(event='Stop', last_assistant_message='```text\n✓ Session 1 saved: log.md\nParked.\n```')
        self.add('user', 'Continue working.')
        self.assertIn('<parboil-trigger', self.hook())

    def test_completion_observation_does_not_emit_shadow_snapshot(self):
        self.assertEqual(self.hook(event='Stop', last_assistant_message='Parked.'), '')

    def test_parent_workflow_completion_observed_without_explicit_request(self):
        self.hook(event='Stop', last_assistant_message='✓ Session 1 saved: session.md\n\nParked.\n')
        self.assertEqual(self.hook(), '')

    def test_tool_output_cannot_record_completion(self):
        self.hook(event='PostToolUse', last_assistant_message='✓ Session 1 saved: session.md\n\nParked.\n')
        self.assertIn('<parboil-trigger', self.hook())

    def test_completed_park_suppressed_until_new_write(self):
        self.complete()
        self.assertEqual(self.hook(), '')
        with self.ledger.open('a') as f:
            f.write('2026-01-01T00:00:01Z\tWrite\t/tmp/two.md\tmain\n')
        self.assertIn('<parboil-trigger', self.hook())

    def test_prepark_snapshot_does_not_delay_new_postpark_work(self):
        self.hook()
        (self.state / f'{self.sid}.parboil.md').write_text('existing draft')
        self.complete()
        with self.ledger.open('a') as f:
            f.write('2026-01-01T00:00:01Z\tWrite\t/tmp/two.md\tmain\n')
        self.assertIn('<parboil-trigger', self.hook())

    def test_unfinished_or_quoted_park_is_not_completion(self):
        self.hook(event='Stop', last_assistant_message='The /park instruction says "Parked.".')
        self.assertIn('<parboil-trigger', self.hook())

    def test_old_session_log_alone_does_not_suppress_later_work(self):
        (self.config / 'session-log.md').write_text('## Session 1\nParked.')
        self.assertIn('<parboil-trigger', self.hook())

    def test_later_user_turn_releases_interrupted_park(self):
        self.add('user', '/park')
        self.add('user', 'Work on the next item.')
        self.assertIn('<parboil-trigger', self.hook())

    def test_disabled_hook_stays_silent(self):
        self.env['OPENCAIRN_PARBOIL_TOKENS'] = '0'
        self.assertEqual(self.hook(), '')

    def test_no_new_writes_do_not_refresh_draft(self):
        self.hook()
        (self.state / f'{self.sid}.parboil.md').write_text('existing draft')
        self.add('assistant', [{'type': 'text', 'text': 'Thinking.'}], 240000)
        self.assertEqual(self.hook(), '')

    def test_wire_add_and_remove_completion_observer(self):
        for mode in ('add', 'add', 'remove'):
            args = ['bash', str(WIRE)] + (['--remove'] if mode == 'remove' else [])
            r = subprocess.run(args, env=self.env, text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads((self.config / 'settings.json').read_text())
            stops = [h for b in data.get('hooks', {}).get('Stop', [])
                     for h in b['hooks'] if h['command'].endswith('/parboil-check.sh')]
            self.assertEqual(len(stops), 0 if mode == 'remove' else 1)


if __name__ == '__main__':
    unittest.main()
