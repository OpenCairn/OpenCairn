"""Fixture tests for the report-only correction-recurrence checks in /weekly-hygiene."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.claude/scripts'
TASK = '- [ ] Fixture task alpha'


def run(args, env, cwd=None):
    return subprocess.run(['bash', *map(str, args)], text=True, capture_output=True,
                          env=env, cwd=cwd)


def count(stdout, label):
    for line in stdout.splitlines():
        if line.startswith(label + ': '):
            return int(line.split(': ', 1)[1])
    raise AssertionError(f'no {label} line in:\n{stdout}')


class FixtureVault:
    def __init__(self, root):
        self.root = Path(root)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')

    def git(self, *args, date=None):
        env = {**os.environ}
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(['git', '-C', str(self.root), *args], check=True,
                       capture_output=True, env=env)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self, date):
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'auto-save', date=date)
        return subprocess.run(['git', '-C', str(self.root), 'rev-parse', '--short', 'HEAD'],
                              check=True, capture_output=True, text=True).stdout.strip()


class WindowCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = FixtureVault(self.tmp.name)
        # TZ=UTC for the process; HYGIENE_TZ must govern the window regardless.
        self.env = {**os.environ, 'VAULT_PATH': self.tmp.name, 'TZ': 'UTC',
                    'HYGIENE_TZ': 'Etc/GMT-10'}


class ResurrectedRoutedLinesTests(WindowCase):
    def setUp(self):
        super().setUp()
        v = self.vault
        v.write('01 Now/This Week.md', f'# This Week\n\n{TASK}\n')
        v.commit('2026-03-09T12:00:00+10:00')
        # Routed out just after local midnight (previous day in UTC), re-added minutes later.
        v.write('01 Now/This Week.md', '# This Week\n\n')
        v.write('04 Areas/Topic Home.md', f'# Topic\n\n{TASK}\n')
        self.routed = v.commit('2026-03-11T00:10:00+10:00')
        v.write('01 Now/This Week.md', f'# This Week\n\n{TASK}\n')
        self.readded = v.commit('2026-03-11T00:20:00+10:00')

    def hits(self, since, until, tz=None):
        env = {**self.env, **({'HYGIENE_TZ': tz} if tz else {})}
        r = run([SCRIPTS / 'resurrected-routed-lines.sh', since, until], env)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return count(r.stdout, 'ROUTED-THEN-RESURRECTED'), r.stdout

    def test_bare_dates_are_inclusive_local_days(self):
        for since, until in [('2026-03-11', '2026-03-11'), ('2026-03-11', '2026-03-17'),
                             ('2026-03-10', '2026-03-11'), ('2026-03-11T00:00', '2026-03-11T23:59')]:
            n, out = self.hits(since, until)
            self.assertEqual(n, 1, f'{since}..{until}\n{out}')
            self.assertIn(self.routed, out)
            self.assertIn(self.readded, out)
            self.assertIn('04 Areas/Topic Home.md |', out)

    def test_windows_without_the_event_are_clean(self):
        for since, until in [('2026-03-02', '2026-03-08'), ('2026-03-12', '2026-03-18'),
                             ('2026-03-10', '2026-03-10')]:
            self.assertEqual(self.hits(since, until)[0], 0, f'{since}..{until}')

    def test_zone_override_moves_the_day(self):
        self.assertEqual(self.hits('2026-03-10', '2026-03-10', tz='UTC')[0], 1)
        self.assertEqual(self.hits('2026-03-11', '2026-03-11', tz='UTC')[0], 0)

    def test_plain_carry_forward_is_ignored(self):
        v = self.vault
        v.write('01 Now/This Week.md', '# This Week\n\n')
        v.commit('2026-03-12T09:00:00+10:00')
        v.write('01 Now/This Week.md', f'# This Week\n\n{TASK}\n')
        v.commit('2026-03-12T09:10:00+10:00')
        self.assertEqual(self.hits('2026-03-12', '2026-03-12')[0], 0)

    def test_non_repository_is_unavailable_not_zero(self):
        with tempfile.TemporaryDirectory() as plain:
            r = run([SCRIPTS / 'resurrected-routed-lines.sh', '2026-03-11', '2026-03-11'],
                    {**self.env, 'VAULT_PATH': plain})
            self.assertEqual(r.returncode, 2)
            self.assertIn('unavailable', r.stdout)


class LocatorRotgunTests(WindowCase):
    def setUp(self):
        super().setUp()
        v = self.vault
        v.write('06 Archive/OpenCairn/Session Logs/2026-03-11.md', '# Log\n')
        v.write('04 Areas/Out of scope.md', '# Area\n')
        v.commit('2026-03-10T12:00:00+10:00')
        v.write('06 Archive/OpenCairn/Session Logs/2026-03-11.md',
                '# Log\n- Fixed the row at Example Log line 88.\n- Finished the second run.\n')
        v.write('04 Areas/Out of scope.md', '# Area\n- See line 4 of the source.\n')
        self.before = v.commit('2026-03-11T00:15:00+10:00')
        v.write('06 Archive/OpenCairn/Session Logs/2026-03-11.md',
                '# Log\n- Fixed the row under the Example Log heading.\n- Finished the second run.\n')
        self.after = v.commit('2026-03-11T09:00:00+10:00')

    def rows(self, rev, extra_env=None):
        r = run([SCRIPTS / 'locator-rotguns.sh', '2026-03-11', '2026-03-11', rev],
                {**self.env, **(extra_env or {})})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return count(r.stdout, 'LOCATOR-ROTGUNS'), r.stdout

    def test_both_outcomes(self):
        n, out = self.rows(self.before)
        self.assertEqual(n, 1, out)
        self.assertIn('Example Log line 88', out)
        self.assertNotIn('second run', out)          # ordinals are not locators
        self.assertNotIn('Out of scope', out)        # area docs are out of scope
        self.assertEqual(self.rows(self.after)[0], 0)

    def test_ignore_list(self):
        ignore = Path(self.tmp.name) / '.claude/hygiene-locator-ignore'
        ignore.parent.mkdir(parents=True, exist_ok=True)
        ignore.write_text('# frozen targets\n\nExample Log line\n')
        n, out = self.rows(self.before)
        self.assertEqual(n, 0, out)
        self.assertIn('ignored by pattern: 1', out)

    def test_empty_ignore_file_drops_nothing(self):
        ignore = Path(self.tmp.name) / '.claude/hygiene-locator-ignore'
        ignore.parent.mkdir(parents=True, exist_ok=True)
        ignore.write_text('# comments only\n\n')
        self.assertEqual(self.rows(self.before)[0], 1)


class HostedDocCallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.projects = Path(self.tmp.name)
        self.env = {**os.environ, 'TZ': 'UTC', 'HYGIENE_TZ': 'Etc/GMT-10'}

    def transcript(self, name, first_ts, records):
        lines = [{'type': 'user', 'timestamp': first_ts}] + records
        (self.projects / f'{name}.jsonl').write_text(
            ''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in lines))

    def run_check(self, since, until):
        r = run([SCRIPTS / 'hosted-doc-calls.sh', since, until, self.projects], self.env)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return count(r.stdout, 'SESSIONS-WITH-HOSTED-DOC-CALLS'), r.stdout

    def test_each_hit_asks_for_a_request_check(self):
        call = {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'id': 'toolu_1', 'name': 'Artifact', 'input': {}}]}}
        mention = {'type': 'system', 'tools': 'Artifact mcp__claude_ai_Claude_Docs__create'}
        # 2026-03-10 20:00 UTC is 2026-03-11 local in the fixture zone.
        self.transcript('aaaa', '2026-03-10T20:00:00.000Z', [call])
        self.transcript('bbbb', '2026-03-11T02:00:00.000Z', [call, call])
        self.transcript('cccc', '2026-03-11T03:00:00.000Z', [mention])
        n, out = self.run_check('2026-03-11', '2026-03-11')
        self.assertEqual(n, 2, out)
        rows = [l for l in out.splitlines() if l.startswith('2026-')]
        self.assertEqual(len(rows), 2, out)
        for row in rows:
            self.assertTrue(row.endswith('-> check whether the user asked'), row)
        self.assertNotIn('cccc', out)
        self.assertEqual(self.run_check('2026-03-12', '2026-03-18')[0], 0)


if __name__ == '__main__':
    unittest.main()
