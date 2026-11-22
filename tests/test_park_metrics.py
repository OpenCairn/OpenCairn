import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import os
import stat
from datetime import datetime, timezone, timedelta

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
        self.assertEqual([(e['line'], e['kind']) for e in errors], [(2, 'incomplete_final_line')])
        self.assertTrue(rows[0]['parse_incomplete'])

    def test_invalid_line_is_not_described_as_a_final_line(self):
        # A damaged line in the middle, and a complete but invalid last line, are not a transcript mid-write.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'session.jsonl'
            good = [json.dumps(self.claude(ts, 'user', text)) for ts, text in
                    (('10:00:00', '/park'), ('10:01:00', 'next'), ('10:02:00', 'more'))]
            path.write_text(good[0]+'\n{"cut": {"mid-k{"second": 1}\n'+good[1]+'\n'+good[2]+'\nnot json\n')
            rows, errors = m.extract(path, 'claude', '2026-09-01T00:00:00Z')
        self.assertEqual([(e['line'], e['kind'], e['error']) for e in errors],
                         [(2, 'invalid_line', 'invalid JSON'), (5, 'invalid_line', 'invalid JSON')])
        self.assertTrue(rows[0]['parse_incomplete'])

    def test_unreadable_source_is_one_bounded_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'session.jsonl'
            path.write_text('plain text\n'*40 + json.dumps({'no': 'timestamp'}) + '\n')
            _, errors = m.extract(path, 'claude', '2026-09-01T00:00:00Z')
            self.assertEqual(errors, [{'path': str(path), 'line': 1, 'kind': 'unreadable_source',
                                       'error': 'unreadable source: 40 of 41 lines are invalid JSON'}])
            # No readable event: the file's modification time decides whether it is in the window.
            os.utime(path, (0, 0))
            self.assertEqual(m.extract(path, 'claude', '2026-09-01T00:00:00Z'), ([], []))

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

    def test_prose_then_skill_tool_park_is_one_run(self):
        skill_call = [{'type':'tool_use','id':'s1','name':'Skill','input':{'skill':'park','args':''}}]
        expansion = [{'type':'tool_result','tool_use_id':'s1','content':'<command-message>park is running…</command-message>\n<command-name>/park</command-name>'}]
        rows, errors = self.parse([
            self.claude('10:00:00', 'user', "Thanks, that's done.\n/park"),
            self.claude('10:00:05', 'assistant', skill_call, 'tool_use'),
            self.claude('10:00:05', 'user', expansion),
            self.claude('10:20:00', 'assistant', [{'type':'text','text':'Parked.'}], 'end_turn')])
        self.assertFalse(errors)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['mode'], 'full')
        self.assertEqual(rows[0]['started_at'], '2026-09-26T10:00:00Z')
        self.assertEqual(rows[0]['wall_seconds'], 1200)
        self.assertEqual(rows[0]['status'], 'parked')
        quick = [{'type':'tool_use','id':'s2','name':'Skill','input':{'skill':'park','args':'--quick'}}]
        rows, _ = self.parse([
            self.claude('10:00:00', 'user', 'Wrap up please. /park --quick'),
            self.claude('10:00:05', 'assistant', quick, 'tool_use'),
            self.claude('10:01:00', 'assistant', [{'type':'text','text':'Quick parked.'}], 'end_turn')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['mode'], 'quick-requested')
        # Envelope + Skill expansion in the same turn is still one run; other skills never start one.
        rows, _ = self.parse([
            self.claude('10:00:00', 'user', '<command-name>/park</command-name>'),
            self.claude('10:00:05', 'assistant', skill_call, 'tool_use'),
            self.claude('10:20:00', 'assistant', [{'type':'text','text':'Parked.'}], 'end_turn'),
            self.claude('11:00:00', 'user', 'Now the morning routine'),
            self.claude('11:00:05', 'assistant', [{'type':'tool_use','id':'s3','name':'Skill','input':{'skill':'morning'}}], 'tool_use'),
            self.claude('11:05:00', 'assistant', [{'type':'text','text':'Done.'}], 'end_turn')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['wall_seconds'], 1200)

    def test_command_envelope_after_prose(self):
        rows, _ = self.parse([
            self.claude('10:00:00', 'user', 'One more note first.\n<command-message>park is running…</command-message>\n<command-name>/park</command-name>\n<command-args>--quick</command-args>'),
            self.claude('10:01:00', 'assistant', [{'type':'text','text':'Quick parked.'}], 'end_turn')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['mode'], 'quick-requested')
        self.assertEqual(rows[0]['wall_seconds'], 60)

    def test_quoted_command_envelope_is_not_a_run(self):
        self.assertIsNone(m.prompt_mode(
            'Please explain this literal XML: `<command-name>/park</command-name>`'))
        self.assertIsNone(m.prompt_mode(
            'The log showed <command-name>/park</command-name> mid-sentence, what is it?'))
        self.assertIsNone(m.prompt_mode(
            'In backticks:\n`<command-message>park is running…</command-message>\n<command-name>/park</command-name>`'))
        # Real envelopes, with or without prose before them, still count.
        self.assertEqual(m.prompt_mode(
            'One more note first.\n<command-message>park is running…</command-message>\n'
            '<command-name>/park</command-name>\n<command-args>--quick</command-args>'), 'quick-requested')
        self.assertEqual(m.prompt_mode('<command-name>/park</command-name>'), 'full')
        rows, _ = self.parse([
            self.claude('10:00:00', 'user', 'Please explain this literal XML: `<command-name>/park</command-name>`'),
            self.claude('10:01:00', 'assistant', [{'type':'text','text':'It is the envelope.'}], 'end_turn')])
        self.assertEqual(rows, [])

    def test_record_finds_skill_tool_park(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript = root/'claude/projects/example/skill-id.jsonl'
            transcript.parent.mkdir(parents=True)
            transcript.write_text(''.join(json.dumps(e)+'\n' for e in [
                self.claude('10:00:00', 'user', 'All done here.\n/park'),
                self.claude('10:00:05', 'assistant', [{'type':'tool_use','id':'s1','name':'Skill','input':{'skill':'park','args':''}}], 'tool_use'),
                self.claude('10:20:00', 'assistant', [{'type':'text','text':'Parked.'}], 'end_turn')]))
            base = [sys.executable, str(Path(m.__file__)), '--state', str(root/'state'),
                    '--claude-root', str(root/'claude'), '--codex-root', str(root/'codex')]
            result = subprocess.run(base+['record', '--harness', 'claude', '--session-id', 'skill-id', '--outcome', 'completed'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('run_id', result.stdout)

    def test_record_prints_minutes_since_the_park_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = datetime.now(timezone.utc) - timedelta(minutes=10)
            transcript = root/'claude/projects/example/live-id.jsonl'
            transcript.parent.mkdir(parents=True)
            transcript.write_text(json.dumps(dict(timestamp=started.isoformat().replace('+00:00', 'Z'), type='user',
                                                  message=dict(content='/park', stop_reason=None)))+'\n')
            base = [sys.executable, str(Path(m.__file__)), '--state', str(root/'state'),
                    '--claude-root', str(root/'claude'), '--codex-root', str(root/'codex')]
            def run(*args):
                return json.loads(subprocess.run(base+list(args), capture_output=True, text=True, check=True).stdout)
            closed = run('record', '--harness', 'claude', '--session-id', 'live-id', '--outcome', 'completed', '--review-rounds', '2')
            self.assertGreaterEqual(closed['elapsed_minutes'], 10.0)
            self.assertLess(closed['elapsed_minutes'], 11.0)
            self.assertEqual(closed['reported']['review_rounds'], 2)
            # A later annotation by run ID is not a close-out reading.
            subprocess.run(base+['collect', '--since', '2026-09-01T00:00:00Z'], capture_output=True, check=True)
            later = run('record', '--run-id', closed['run_id'], '--human-review-minutes', '4')
            self.assertNotIn('elapsed_minutes', later)

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

    def collection(self, root, body):
        transcript = root/'claude/projects/example/real-id.jsonl'
        transcript.parent.mkdir(parents=True)
        transcript.write_bytes(body if isinstance(body, bytes) else body.encode())
        base = [sys.executable, str(Path(m.__file__)), '--state', str(root/'state'),
                '--claude-root', str(root/'claude'), '--codex-root', str(root/'codex')]
        result = subprocess.run(base+['collect', '--since', '2026-09-01T00:00:00Z'], capture_output=True, text=True)
        report = subprocess.run(base+['report'], capture_output=True, text=True, check=True).stdout
        return result, json.loads((root/'state/runs.json').read_text()), report

    def test_isolated_parse_errors_are_reported_without_failing_collection(self):
        park = json.dumps(self.claude('10:00:00', 'user', '/park'))+'\n'
        done = json.dumps(self.claude('10:20:00', 'assistant', [{'type':'text','text':'Parked.'}], 'end_turn'))+'\n'
        for name, body, kind in (('mid-write tail', park+done+'{"broken":', 'incomplete_final_line'),
                                 # A tail cut inside a multi-byte character is not valid UTF-8.
                                 ('tail cut mid-character', (park+done).encode()+b'{"text": "\xe2\x9c', 'incomplete_final_line'),
                                 ('damaged line', park+'{"cut": {"mid-k{"second": 1}\n'+done, 'invalid_line'),
                                 ('line that is not an object', park+'[1,2]\n'+done, 'invalid_line')):
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                result, data, report = self.collection(Path(tmp), body)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([e['kind'] for e in data['errors']], [kind])
                self.assertEqual(data['unreadable_sources'], [])
                self.assertIn('"errors": [{', result.stdout)
                self.assertIn(f'parse errors 1 ({kind} 1)', report)
                # The affected run stays visible and out of the timing summary.
                self.assertTrue(data['runs'][0]['parse_incomplete'])
                self.assertNotIn('explicit parked responses', report)

    def test_unreadable_source_fails_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, data, report = self.collection(Path(tmp), 'plain text\n'*3)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(len(data['unreadable_sources']), 1)
            self.assertEqual([e['kind'] for e in data['errors']], ['unreadable_source'])
            self.assertIn('parse errors 1 (unreadable_source 1)', report)

    def history(self, root):
        # Two sessions with one parked run each; returns their transcripts and a collect/record runner.
        paths = [root/f'claude/projects/example/{name}.jsonl' for name in ('removed', 'present')]
        paths[0].parent.mkdir(parents=True)
        for path, hour in zip(paths, ('10', '12')):
            path.write_text(''.join(json.dumps(e)+'\n' for e in [
                self.claude(hour+':00:00', 'user', '/park'),
                self.claude(hour+':20:00', 'assistant', [{'type':'text','text':'Parked.'}], 'end_turn')]))
        base = [sys.executable, str(Path(m.__file__)), '--state', str(root/'state'),
                '--claude-root', str(root/'claude'), '--codex-root', str(root/'codex')]
        def run(*args, since='2026-09-01T00:00:00Z'):
            subprocess.run(base+list(args)+(['--since', since] if args == ('collect',) else []),
                           capture_output=True, text=True, check=True)
            data = json.loads((root/'state/runs.json').read_text())
            return data, {Path(r['transcript']).stem: r for r in data['runs']}
        return paths, run

    def test_schema_change_keeps_runs_whose_source_is_gone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (removed, present), run = self.history(root)
            _, before = run('collect')
            run('record', '--run-id', before['removed']['id'], '--review-rounds', '2')
            body = removed.read_text()
            removed.unlink()
            # A cache written by the previous schema; the changed count shows which rows are parsed again.
            cache = json.loads((root/'state/cache.json').read_text())
            cache['version'] = m.VERSION - 1
            for entry in cache['files'].values():
                entry['rows'][0]['tool_calls'] = 99
            (root/'state/cache.json').write_text(json.dumps(cache))
            for attempt in ('first collection on the new schema', 'next collection'):
                with self.subTest(attempt):
                    data, runs = run('collect')
                    self.assertEqual(data['schema'], m.VERSION)
                    self.assertEqual(sorted(runs), ['present', 'removed'])
                    kept = runs['removed']
                    self.assertEqual(kept['id'], before['removed']['id'])
                    self.assertEqual(kept['wall_seconds'], 1200)
                    self.assertEqual(kept['tool_calls'], 99)
                    self.assertFalse(kept['source_present'])
                    self.assertEqual(kept['carried_from_schema'], m.VERSION - 1)
                    self.assertEqual(kept['reported']['review_rounds'], 2)
                    # A source still on disk is parsed again, not carried.
                    self.assertEqual(runs['present']['tool_calls'], 0)
                    self.assertNotIn('carried_from_schema', runs['present'])
            self.assertEqual(data['files_reparsed'], 0)
            # The source comes back: its runs are parsed under the current schema.
            removed.write_text(body)
            data, runs = run('collect')
            self.assertEqual(len(data['runs']), 2)
            self.assertEqual(runs['removed']['id'], before['removed']['id'])
            self.assertEqual(runs['removed']['tool_calls'], 0)
            self.assertTrue(runs['removed']['source_present'])
            self.assertNotIn('carried_from_schema', runs['removed'])

    def test_window_change_keeps_runs_whose_source_is_gone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (removed, present), run = self.history(root)
            _, before = run('collect')
            removed.unlink()
            _, runs = run('collect', since='2026-08-01T00:00:00Z')
            self.assertEqual(sorted(runs), ['present', 'removed'])
            self.assertEqual(runs['removed']['wall_seconds'], 1200)
            self.assertNotIn('carried_from_schema', runs['removed'])
            # A window starting after both requests leaves them out of the dataset, not out of the cache.
            data, runs = run('collect', since='2026-09-27T00:00:00Z')
            self.assertEqual(data['runs'], [])
            _, runs = run('collect')
            self.assertEqual({k: r['id'] for k, r in runs.items()}, {k: r['id'] for k, r in before.items()})

    def summarise(self, runs, *args, collected_at=None, since='2026-09-01T00:00:00Z'):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)/'state'
            state.mkdir()
            rows = [dict(id=str(i), harness=h, started_at=day+'T12:00:00Z', wall_seconds=minutes and minutes*60,
                         mode=mode, status=status, **extra)
                    for i, (h, day, minutes, mode, status, extra) in enumerate(runs)]
            (state/'runs.json').write_text(json.dumps(dict(
                schema=m.VERSION, collected_at=collected_at or m.stamp(), since=since, errors=[], runs=rows)))
            return subprocess.run([sys.executable, str(Path(m.__file__)), '--state', str(state), 'summary', *args],
                                  capture_output=True, text=True)

    def test_summary_by_harness_and_iso_week(self):
        full = lambda h, day, minutes, **extra: (h, day, minutes, 'full', 'parked', extra)
        # Wednesdays at noon UTC: the same ISO week in every time zone.
        runs = [full('claude', '2026-09-30', v) for v in (5, 10, 15, 20, 25, 30, 35, 40, 45, 60)] + [
            full('claude', '2026-09-30', 61), full('claude', '2026-09-30', 400),
            full('codex', '2026-09-30', 12),
            full('codex', '2026-09-23', 90),
            full('claude', '2026-09-16', 7),                       # before the requested weeks
            full('claude', '2026-09-30', 9, parse_incomplete=True),
            ('claude', '2026-09-30', 3, 'quick-requested', 'parked', {}),
            ('claude', '2026-09-30', 8, 'full', 'response_returned', {}),
            ('codex', '2026-09-23', None, 'full', 'no_completion_observed', {})]
        result = self.summarise(runs, '--weeks', '2', '--until', '2026-10-04')
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertTrue(lines[0].endswith('parse errors 0'), lines[0])
        self.assertEqual(lines[2], '2026-W40 | claude: n 10, median 27.5, p90 45.0, >=30 min 5, over 60 min 2'
                                   ' | codex: n 1, median 12.0, p90 12.0, >=30 min 0, over 60 min 0')
        self.assertEqual(lines[3], '2026-W39 | codex: n 0, over 60 min 1')
        self.assertEqual(len(lines), 5)
        # Every run in the requested weeks is in a row or named in the exclusion line.
        self.assertIn('Runs over 60 min include waits and are counted apart', lines[4])
        self.assertTrue(lines[4].endswith('quick 1; returned or unfinished 2; parse-incomplete 1.'), lines[4])

    def test_summary_names_empty_weeks_stale_data_and_short_windows(self):
        result = self.summarise([], '--weeks', '3', '--until', '2026-10-04',
                                collected_at='2026-10-01T00:00:00+00:00', since='2026-09-25T00:00:00Z')
        lines = result.stdout.splitlines()
        self.assertRegex(lines[0], r'; STALE: collected \d+ days ago; collection window starts after 2026-W38 began')
        self.assertEqual(lines[2:5], ['2026-W40 | no parked full runs', '2026-W39 | no parked full runs',
                                      '2026-W38 | no parked full runs'])
        fresh = self.summarise([], '--weeks', '1').stdout.splitlines()
        self.assertNotIn('STALE', fresh[0])
        self.assertTrue(fresh[2].endswith('(to date) | no parked full runs'), fresh[2])
        self.assertNotEqual(self.summarise([], '--weeks', '0').returncode, 0)
        with tempfile.TemporaryDirectory() as tmp:
            missing = subprocess.run([sys.executable, str(Path(m.__file__)), '--state', str(Path(tmp)/'state'), 'summary'],
                                     capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1)
        self.assertIn('No collection yet', missing.stderr)

    def test_park_completion_messages_quote_the_recorded_cost(self):
        # Both templates carry the line, sourced from the field record prints; no extra call.
        root = Path(__file__).resolve().parents[1]
        for rel in ('.claude/commands/park.md', 'codex/skills/park/SKILL.md'):
            with self.subTest(rel):
                text = (root/rel).read_text(encoding='utf-8')
                closeout = text[text.index('### Measurement close-out'):text.index('### 12. Full-path completion message')]
                self.assertIn('park-metrics.py" record ', closeout)
                self.assertIn('`elapsed_minutes`', closeout)
                self.assertIn('omit it if recording failed', closeout)
                self.assertEqual(text.count('park-metrics.py"'), 1)
                for start, end in (('#### Quick success path', 'Quick parked.'),
                                   ('### 12. Full-path completion message', 'Parked.')):
                    block = text[text.index(start):]
                    block = block[:block.index(end)]
                    self.assertEqual(block.count('\n✓ Transcript exported: N sessions\n⏱ Park: N min, R review rounds\n'), 1)

    def test_weekly_review_quotes_both_summary_rows(self):
        root = Path(__file__).resolve().parents[1]
        for rel in ('.claude/commands/weekly-review.md', 'codex/skills/weekly-review/SKILL.md'):
            with self.subTest(rel):
                text = (root/rel).read_text(encoding='utf-8')
                step = text[text.index('   **Park cost (when collected):**'):text.index('   **Personal planning configuration:**')]
                self.assertIn('park-metrics.py" summary --weeks 2`', step)
                self.assertIn('`No collection yet` means no collector is set up: skip silently', step)
                # The newest row is the week in progress, so the completed week is quoted with it.
                self.assertIn('quote both week rows, newest first', step)
                self.assertIn('no threshold, verdict or task', step)
                self.assertEqual(len(step.strip().splitlines()), 2)
                friction = text[text.index('## Attention & Friction'):text.index('## Key Insights & Patterns')]
                self.assertIn("otherwise omit this line:]\n**Park cost:** <newest week's row>; <previous week's row>[; <header flag>]\n", friction)
                self.assertEqual(friction.count('**Park cost:**'), 1)


if __name__ == '__main__':
    unittest.main()
