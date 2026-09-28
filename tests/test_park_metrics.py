import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import os
import stat

spec = importlib.util.spec_from_file_location('metrics', Path(__file__).resolve().parents[1]/'.claude/scripts/park-metrics.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MetricsTests(unittest.TestCase):
    def parse(self, events, harness='claude', raw=''):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'session.jsonl'
            p.write_text(''.join(json.dumps(e)+'\n' for e in events)+raw)
            return m.extract(p, harness, '2026-09-01T00:00:00Z')

    def claude(self, ts, role, content, stop=None, **extras):
        return dict(timestamp='2026-09-26T'+ts+'Z', type=role,
                    message=dict(content=content, stop_reason=stop), **extras)

    def codex(self, ts, kind, **payload):
        return dict(timestamp='2026-09-26T'+ts+'Z', type=kind, payload=payload)

    def test_async_continuation_and_idle_do_not_shorten_park(self):
        rows, errors = self.parse([
            self.claude('10:00:00', 'user', '<command-name>/park</command-name>'),
            self.claude('10:00:00', 'user', [{'type':'text','text':'# Park - expanded instructions'}], isMeta=True),
            self.claude('10:01:00', 'assistant', [{'type':'text','text':'Waiting for audit'}], 'end_turn'),
            self.claude('10:20:00', 'user', '<task-notification>done</task-notification>'),
            self.claude('10:25:00', 'assistant', [{'type':'text','text':'Parked.'}], 'end_turn'),
            self.claude('11:00:00', 'user', 'What next?'),
            self.claude('11:01:00', 'assistant', [{'type':'text','text':'A new task'}], 'end_turn')])
        self.assertFalse(errors)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['wall_seconds'], 1500)
        self.assertEqual(rows[0]['status'], 'parked')

    def test_codex_task_complete_and_duplicate_prompt(self):
        rows, _ = self.parse([
            self.codex('10:00:00', 'session_meta', id='abc'),
            self.codex('10:00:00', 'event_msg', type='task_started', turn_id='turn'),
            self.codex('10:00:01', 'response_item', type='message', role='user', content=[{'text':'$park'}]),
            self.codex('10:00:01.100', 'event_msg', type='user_message', message='$park'),
            self.codex('10:05:00', 'event_msg', type='task_complete', turn_id='other', last_agent_message='Parked.'),
            self.codex('10:30:01', 'event_msg', type='task_complete', turn_id='turn', last_agent_message='Parked.')], 'codex')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['wall_seconds'], 1800)

    def test_multiple_parks_and_missing_completion(self):
        rows, _ = self.parse([
            self.claude('10:00:00', 'user', '/park --quick'),
            self.claude('10:01:00', 'assistant', [{'type':'text','text':'Quick parked.'}], 'end_turn'),
            self.claude('11:00:00', 'user', '/park'),
            self.claude('11:01:00', 'user', 'Cancel that')])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['mode'], 'quick-requested')
        self.assertIsNone(rows[1]['wall_seconds'])

    def test_quoted_and_injected_mentions_are_not_runs(self):
        rows, _ = self.parse([
            self.claude('10:00:00', 'user', 'Please explain /park'),
            self.claude('10:01:00', 'user', '<skill>Use $park later</skill>'),
            self.claude('10:02:00', 'user', '/park', isSidechain=True)])
        self.assertEqual(rows, [])

    def test_tool_errors_and_calls_deduplicated(self):
        block = [{'type':'tool_use','id':'t','name':'Bash','input':{'command':'false'}}]
        rows, _ = self.parse([
            self.claude('10:00:00', 'user', '/park'),
            self.claude('10:01:00', 'assistant', block, 'tool_use'),
            self.claude('10:01:01', 'assistant', block, 'tool_use'),
            self.claude('10:01:02', 'user', [{'type':'tool_result','is_error':True,'content':'failed'}]),
            self.claude('10:02:00', 'assistant', [{'type':'text','text':'Blocked'}], 'end_turn')])
        self.assertEqual(rows[0]['tool_calls'], 1)
        self.assertEqual(rows[0]['tool_error_results'], 1)
        self.assertEqual(rows[0]['status'], 'response_returned')

    def test_corrupt_tail_is_visible_not_success(self):
        rows, errors = self.parse([self.claude('10:00:00', 'user', '/park')], raw='{"partial":')
        self.assertTrue(errors)
        self.assertTrue(rows[0]['parse_incomplete'])

    def test_unknown_human_time_not_inferred(self):
        rows, _ = self.parse([self.claude('10:00:00', 'user', '/park')])
        self.assertNotIn('human_review_minutes', rows[0])
        with self.assertRaises(Exception):
            m.nonnegative('nan')

    def test_standalone_skill_invocation_and_expansion(self):
        skill = '<skill>\n<name>park</name>\n<path>/skills/park/SKILL.md</path></skill>'
        rows, _ = self.parse([
            self.codex('10:00:00', 'event_msg', type='task_started', turn_id='turn'),
            self.codex('10:00:01', 'response_item', type='message', role='user', content=[{'text': skill}]),
            self.codex('10:20:01', 'event_msg', type='task_complete', turn_id='turn', last_agent_message='Parked.')], 'codex')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['wall_seconds'], 1200)
        rows, _ = self.parse([
            self.codex('10:00:00', 'event_msg', type='task_started', turn_id='turn'),
            self.codex('10:00:01', 'response_item', type='message', role='user', content=[{'text': '$park --quick'}]),
            self.codex('10:00:04', 'response_item', type='message', role='user', content=[{'text': skill}]),
            self.codex('10:01:01', 'event_msg', type='task_complete', turn_id='turn', last_agent_message='Quick parked.')], 'codex')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['mode'], 'quick-requested')

    def test_repeated_standalone_skills_are_distinct_runs(self):
        events = []
        skill = '<skill>\n<name>park</name>\n</skill>'
        for hour, turn in [('10', 'one'), ('11', 'two')]:
            events.extend([
                self.codex(hour+':00:00', 'event_msg', type='task_started', turn_id=turn),
                self.codex(hour+':00:01', 'response_item', type='message', role='user', content=[{'text':skill}]),
                self.codex(hour+':20:01', 'response_item', type='message', role='assistant', phase='final', content=[{'text':'Parked.'}]),
                self.codex(hour+':20:01', 'event_msg', type='task_complete', turn_id=turn, last_agent_message='Parked.')])
        rows, _ = self.parse(events, 'codex')
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['wall_seconds'] for r in rows], [1200,1200])

    def test_modes_and_exact_quick_arguments(self):
        self.assertEqual(m.prompt_mode('$park --quick foo'), 'full')
        self.assertEqual(m.prompt_mode('$park --quick'), 'quick-requested')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'record.json'
            oldmask = os.umask(0o027)
            try:
                m.atomic(path, {'a': 1})
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
                path.chmod(0o600)
                m.atomic(path, {'a': 2})
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            finally:
                os.umask(oldmask)

    def test_cli_collection_annotation_and_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript = root/'claude/projects/example/real-id.jsonl'
            transcript.parent.mkdir(parents=True)
            transcript.write_text(''.join(json.dumps(e)+'\n' for e in [
                self.claude('10:00:00', 'user', '/park')]))
            base = [sys.executable, str(Path(m.__file__)), '--state', str(root/'state'),
                    '--claude-root', str(root/'claude'), '--codex-root', str(root/'codex')]
            def run(*args):
                return subprocess.run(base+list(args), capture_output=True, text=True, check=True)
            run('collect', '--since', '2026-09-01T00:00:00Z')
            data = json.loads((root/'state/runs.json').read_text())
            rid = data['runs'][0]['id']
            run('record', '--harness', 'claude', '--session-id', 'real-id', '--outcome', 'completed',
                '--review-rounds', '2', '--correction-rounds', '1', '--confirmed-findings', '3')
            self.assertIsNone(data['runs'][0]['wall_seconds'])
            with transcript.open('a') as out:
                out.write(json.dumps(self.claude('10:20:00', 'assistant', [{'type':'text','text':'Parked.'}], 'end_turn'))+'\n')
            run('collect', '--since', '2026-09-01T00:00:00Z')
            run('record', '--run-id', rid, '--human-review-minutes', '4')
            run('collect', '--since', '2026-09-01T00:00:00Z')
            data = json.loads((root/'state/runs.json').read_text())
            self.assertEqual(data['files_reparsed'], 0)
            self.assertEqual(len(data['runs']), 1)
            self.assertEqual(data['runs'][0]['reported']['confirmed_findings'], 3)
            self.assertEqual(data['runs'][0]['reported']['human_review_minutes'], 4)
            self.assertIn('20.0 min', run('report').stdout)
            absent = subprocess.run(base+['collect','--since','2026-09-01T00:00:00Z','--require-harness','codex'], capture_output=True)
            self.assertNotEqual(absent.returncode, 0)
            self.assertEqual(json.loads((root/'state/runs.json').read_text())['missing_required_harnesses'], ['codex'])
            transcript.write_text(transcript.read_text() + '{"broken":')
            bad = subprocess.run(base+['collect','--since','2026-09-01T00:00:00Z'], capture_output=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertTrue(json.loads((root/'state/runs.json').read_text())['errors'])


if __name__ == '__main__':
    unittest.main()
