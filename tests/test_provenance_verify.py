"""Real fixture controls for the read-only provenance resolution ladder."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / '.claude/scripts/provenance-verify.py'


class ProvenanceVerifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        self.artifacts = self.vault / '07 System/.Provenance'
        self.artifacts.mkdir(parents=True)
        self.log = self.vault / '07 System/AI Provenance Log.md'
        self.log.write_text('| Date | Tag | File | SHA256 | OTS |\n| --- | --- | --- | --- | --- |\n')
        self.env = dict(os.environ, HOME=str(self.root / 'home'),
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        fake = bin_dir / 'ots'
        fake.write_text('#!/usr/bin/env python3\nimport pathlib,sys\n'
                        'print("File sha256 hash: "+pathlib.Path(sys.argv[-1]).read_text().strip())\n')
        fake.chmod(0o755)
        self.env['PATH'] = str(bin_dir) + os.pathsep + os.environ['PATH']

    def row(self, rel, content, status='none (ots unavailable)', tag='fixture'):
        short = hashlib.sha256(content).hexdigest()[:16]
        with self.log.open('a') as out:
            out.write(f'| 2001-01-01 | {tag} | {rel} | `{short}` | {status} |\n')
        return short

    def run_verify(self):
        before = {p.relative_to(self.vault).as_posix(): (p.read_bytes(), p.stat().st_mode)
                  for p in self.vault.rglob('*') if p.is_file()}
        result = subprocess.run([sys.executable, str(SCRIPT), '--vault', str(self.vault)],
                                env=self.env, capture_output=True, text=True, timeout=20)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        after = {p.relative_to(self.vault).as_posix(): (p.read_bytes(), p.stat().st_mode)
                 for p in self.vault.rglob('*') if p.is_file()}
        self.assertEqual(after, before, 'read-only inspection changed fixture bytes/modes')
        return json.loads(result.stdout)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.vault), *args], env=self.env,
                              capture_output=True, text=True, check=True).stdout

    def init_git(self):
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')

    def commit_file(self, rel, message):
        self.git('add', '--', rel)
        self.git('commit', '-qm', message, '--only', '--', rel)

    def test_live_snapshot_missing_and_invalid_counts_are_discriminating(self):
        content = b'known source\n'
        source = self.vault / 'Notes/Current.md'
        source.parent.mkdir()
        source.write_bytes(content)
        self.row('Notes/Current.md', content)
        old = b'previous source\n'
        short = self.row('Notes/Missing.md', old)
        (self.artifacts / f'2001-01-01-Missing-{short}.snapshot.md').write_bytes(old)
        self.row('Notes/Absent.md', b'not retained\n')
        with self.log.open('a') as out:
            out.write('| 2001-01-01 | fixture | Bad.md | `1234` | pending |\n')
        before = self.log.read_bytes()
        result = self.run_verify()
        self.assertEqual([r['content_state'] for r in result['rows']],
                         ['MATCH', 'VERIFIED_SNAPSHOT', 'MISSING', 'INVALID'])
        self.assertTrue(result['rows'][1]['locator_stale'])
        self.assertEqual(result['counts']['records'], 4)
        self.assertEqual(sum(result['counts']['content'].values()), 4)
        self.assertEqual(self.log.read_bytes(), before)

    def test_legacy_name_proof_uses_existing_identity_resolver(self):
        content = b'attested legacy source\n'
        short = self.row('Example.md', content, status='confirmed (lite)')
        snapshot = self.artifacts / f'2001-01-01-Example-{short[:8]}.snapshot.md'
        snapshot.write_bytes(content)
        (self.artifacts / 'Example.md.ots').write_text(hashlib.sha256(content).hexdigest())
        result = self.run_verify()
        row = result['rows'][0]
        self.assertEqual(row['content_state'], 'VERIFIED_SNAPSHOT')
        self.assertEqual(row['evidence']['selection'], 'legacy')
        self.assertEqual(row['evidence']['status'], 'confirmed')
        self.assertEqual(row['bitcoin_verification'], 'not-run')

    def test_ambiguous_legacy_proofs_remain_an_evidence_gap(self):
        content = b'legacy with duplicate proofs\n'
        short = self.row('Example.md', content, status='pending')
        (self.artifacts / f'legacy-{short[:8]}.snapshot.md').write_bytes(content)
        for name in ('Example.md.ots', 'Example.ots'):
            (self.artifacts / name).write_text(hashlib.sha256(content).hexdigest())
        row = self.run_verify()['rows'][0]
        self.assertEqual(row['content_state'], 'VERIFIED_SNAPSHOT')
        self.assertNotIn('evidence', row)
        self.assertIn('2 matching legacy proofs', row['evidence_error'])
        self.assertEqual(row['bitcoin_verification'], 'not-run')

    def test_authoritative_broken_locator_does_not_fall_back_to_older_snapshot(self):
        content = b'attested\n'
        short = self.row('Notes/Missing.md', content)
        (self.artifacts / f'legacy-{short}.snapshot.md').write_bytes(content)
        locator = json.dumps({'snapshot': '07 System/.Provenance/gone.snapshot.md', 'proof': None})
        with self.log.open('a') as out:
            out.write(f'| 2001-01-01 | fixture | Notes/Missing.md | `{short}` | evidence: {locator} |\n')
        result = self.run_verify()
        row = result['rows'][0]
        self.assertEqual(row['content_state'], 'MISSING')
        self.assertIn('evidence_error', row)
        self.assertEqual(result['counts']['annotations'], 1)

    def test_selected_snapshot_recovers_content_without_claiming_proof_identity(self):
        content = b'attested with absent proof\n'
        short = self.row('Notes/Missing.md', content, status='pending')
        snapshot = self.artifacts / f'selected-{short}.snapshot.md'
        snapshot.write_bytes(content)
        locator = json.dumps({'snapshot': snapshot.relative_to(self.vault).as_posix(), 'proof': None})
        with self.log.open('a') as out:
            out.write(f'| 2001-01-01 | fixture | Notes/Missing.md | `{short}` | evidence: {locator} |\n')
        result = self.run_verify()
        row = result['rows'][0]
        self.assertEqual(row['content_state'], 'VERIFIED_SNAPSHOT')
        self.assertIn('evidence_error', row)
        self.assertEqual(row['bitcoin_verification'], 'not-run')
        self.assertTrue(result['triage_required'])

    def test_git_current_path_rung_uses_local_historical_blob(self):
        self.init_git()
        content = b'first bytes\n'
        source = self.vault / 'Notes/Example.md'
        source.parent.mkdir()
        source.write_bytes(content)
        self.commit_file('Notes/Example.md', 'first')
        self.row('Notes/Example.md', content)
        source.write_text('changed\n')
        result = self.run_verify()
        row = result['rows'][0]
        self.assertEqual(row['content_state'], 'VERIFIED_GIT')
        self.assertEqual(row['git']['rung'], 'path')
        self.assertEqual(row['git']['path'], 'Notes/Example.md')
        self.assertFalse(row['locator_stale'])

    def test_bare_root_live_mismatch_uses_its_resolved_git_path(self):
        self.init_git()
        content = b'bare first bytes\n'
        source = self.vault / 'Example.md'
        source.write_bytes(content)
        self.commit_file('Example.md', 'bare first')
        self.row('Example.md', content)
        source.write_text('changed\n')
        row = self.run_verify()['rows'][0]
        self.assertEqual(row['content_state'], 'VERIFIED_GIT')
        self.assertEqual(row['git']['rung'], 'path')
        self.assertEqual(row['git']['path'], 'Example.md')

    def test_session_date_and_transcript_aliases_resolve_documented_locations(self):
        fixtures = [('2001-01-01.md', '06 Archive/OpenCairn/Session Logs/2001/2001-01-01.md'),
                    ('2001-01-02-transcript.md', '06 Archive/OpenCairn/.Session Transcripts/2001-01-02.md')]
        for alias, rel in fixtures:
            source = self.vault / rel
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(alias)
            self.row(alias, alias.encode())
        result = self.run_verify()
        self.assertEqual([r['content_state'] for r in result['rows']], ['MATCH', 'MATCH'])
        self.assertEqual([r['resolved_file'] for r in result['rows']], [rel for _, rel in fixtures])

    def test_ambiguous_matching_live_copies_do_not_pick_one(self):
        content = b'duplicate bytes\n'
        self.row('Old/Example.md', content)
        for directory in ('A', 'B'):
            source = self.vault / directory / 'Example.md'
            source.parent.mkdir()
            source.write_bytes(content)
        row = self.run_verify()['rows'][0]
        self.assertEqual(row['content_state'], 'MISSING')
        self.assertEqual(sorted(row['ambiguous_live_candidates']), ['A/Example.md', 'B/Example.md'])

    def test_git_basename_rung_handles_unicode_space_and_bracket_paths(self):
        self.init_git()
        content = b'older-name bytes\n'
        old = self.vault / 'Old/Éxample [draft] - source.md'
        old.parent.mkdir()
        old.write_bytes(content)
        self.commit_file(old.relative_to(self.vault).as_posix(), 'old location')
        self.row('New/Éxample [draft] - source.md', content)
        old.unlink()
        result = self.run_verify()
        row = result['rows'][0]
        self.assertEqual(row['content_state'], 'VERIFIED_GIT')
        self.assertEqual(row['git']['rung'], 'basename')
        self.assertEqual(row['git']['path'], 'Old/Éxample [draft] - source.md')
        self.assertTrue(row['locator_stale'])

    def test_partial_clone_configuration_is_not_implicitly_fetched(self):
        self.init_git()
        self.git('config', 'remote.fixture.promisor', 'true')
        self.row('Missing.md', b'not in local history\n')
        result = self.run_verify()
        self.assertFalse(result['git_history_available'])
        self.assertEqual(result['rows'][0]['git_search'],
                         {'available': False, 'matched': False, 'blobs_tried': 0})

    def test_missing_git_does_not_prevent_local_digest_inspection(self):
        source = self.vault / 'Example.md'
        source.write_text('local bytes\n')
        self.row('Example.md', source.read_bytes())
        self.env['PATH'] = str(self.root / 'no-git')
        result = self.run_verify()
        self.assertFalse(result['git_history_available'])
        self.assertEqual(result['rows'][0]['content_state'], 'MATCH')

    def test_latest_status_annotations_and_supersession_are_not_extra_attestations(self):
        content = b'old\n'
        old = self.row('Note.md', content)
        self.row('Note.md', content, status='confirmed')
        new = self.row('Note.md', b'new\n')
        with self.log.open('a') as out:
            out.write(f'| 2001-01-02 | fixture | Note.md | `{new}` | supersedes `{old}` |\n')
        result = self.run_verify()
        self.assertEqual(result['counts']['records'], 2)
        self.assertEqual(result['counts']['annotations'], 1)
        self.assertTrue(result['rows'][0]['historical'])
        self.assertEqual(result['rows'][0]['status'], 'confirmed')
        self.assertFalse(result['rows'][1]['historical'])

    def test_unknown_status_cannot_hide_behind_an_earlier_valid_row(self):
        content = b'known bytes\n'
        short = self.row('Note.md', content)
        with self.log.open('a') as out:
            out.write(f'| 2001-01-02 | fixture | Note.md | `{short}` | invented status |\n')
            out.write('| malformed | cells |\n')
        result = self.run_verify()
        self.assertEqual(result['counts']['records'], 2)
        self.assertEqual(result['counts']['content'], {'INVALID': 2})
        self.assertTrue(result['triage_required'])

    def test_git_miss_reports_real_positive_control_blob_count(self):
        self.init_git()
        source = self.vault / 'Old/Example.md'
        source.parent.mkdir()
        source.write_text('different known blob\n')
        self.commit_file('Old/Example.md', 'known blob')
        source.unlink()
        self.row('New/Example.md', b'absent bytes\n')
        result = self.run_verify()
        row = result['rows'][0]
        self.assertEqual(row['content_state'], 'MISSING')
        self.assertTrue(result['git_history_available'])
        self.assertFalse(row['git_search']['matched'])
        self.assertEqual(row['git_search']['blobs_tried'], 1)

    def test_live_relocation_requires_unique_matching_digest_not_first_basename(self):
        content = b'expected\n'
        self.row('Old/Example.md', content)
        for directory, data in [('A', b'wrong\n'), ('B', content)]:
            p = self.vault / directory / 'Example.md'
            p.parent.mkdir()
            p.write_bytes(data)
        result = self.run_verify()
        row = result['rows'][0]
        self.assertEqual(row['content_state'], 'MATCH')
        self.assertEqual(row['resolved_file'], 'B/Example.md')
        self.assertTrue(row['locator_stale'])


if __name__ == '__main__':
    unittest.main()
