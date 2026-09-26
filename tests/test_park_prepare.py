"""Integration checks for batched park review preparation."""
from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

REPO = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location('park_prepare', REPO / 'codex/skills/park/scripts/park-review.py')
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


class ParkPrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.vault = self.base / 'vault'
        scripts = self.vault / '.claude/scripts'
        scripts.mkdir(parents=True)
        self.verifier = scripts / 'park-verify.sh'
        shutil.copy2(REPO / '.claude/scripts/park-verify.sh', self.verifier)
        self.note = self.vault / 'note.md'
        self.note.write_text('# Example\n\nUseful result.\n')
        self.log = self.vault / 'log.md'
        self.log.write_text(
            '# Sessions\n\n## Session 1 - Example\n\n'
            '### Summary\nUseful work completed.\n\n'
            '### Key Insights / Decisions\n- Keep the result.\n\n'
            '### Next Steps / Open Loops\nNone — work completed.\n\n'
            '### Files Created\n- note.md - result\n\n'
            f'### Files Updated\n- {self.note} - duplicate spelling of same path\n- log.md - record\n\n'
            '### Pickup Context\n**For next session:** None.\n**Project:** None\n')
        self.config = self.base / 'config'
        self.root = self.config / '.session-state/fixture.park-review'
        self.env = mock.patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': str(self.config)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.args = SimpleNamespace(session_id='fixture', vault=str(self.vault), session_log=str(self.log), number=1)
        self.handoff = {
            'classifications': [['--path', 'note.md', '--semantic'], ['--path', 'log.md', '--semantic']],
            'captures': [{'kind': 'propagation', 'label': 'fixture', 'text': 'Checked nil: no changed identifiers.'}],
            'identifiers': []}

    def prepare(self, handoff=None):
        output = io.StringIO()
        with mock.patch('sys.stdin', io.StringIO(json.dumps(self.handoff if handoff is None else handoff))), mock.patch('sys.stdout', output):
            result = review.cmd_prepare(self.args)
        return result, output.getvalue()

    def test_real_verifier_and_brief_cover_deduplicated_session_paths(self):
        result, output = self.prepare()
        self.assertEqual(result, 0)
        manifest = json.loads((self.root / 'review-brief-manifest.json').read_text())
        self.assertEqual({x['path'] for x in manifest['full_read']}, {str(self.note), str(self.log)})
        self.assertIn('touched paths from session Files lists: 2', output)
        timing = json.loads(next((self.root / 'prepare-runs').glob('*.json')).read_text())
        self.assertEqual(timing['status'], 'passed')
        self.assertEqual([x['name'] for x in timing['steps']], ['classify-1', 'classify-2', 'capture', 'verify', 'build'])

    def test_failure_stops_before_build_and_records_failed_stage(self):
        self.note.write_text('# Broken\n\n\n\nbody\n')
        with self.assertRaises(SystemExit):
            self.prepare()
        self.assertFalse((self.root / 'review-brief.md').exists())
        timing = json.loads(next((self.root / 'prepare-runs').glob('*.json')).read_text())
        self.assertEqual(timing['status'], 'failed')
        self.assertEqual(timing['steps'][-1]['name'], 'verify')

    def test_review_exit_zero_requires_triage(self):
        self.verifier.write_text('#!/bin/sh\nprintf "%s\\n" "REVIEW closure: still pending" "RESULT: REVIEW (0 fail, 1 review)"\n')
        with self.assertRaisesRegex(SystemExit, 'explicit triage'):
            self.prepare()
        self.assertFalse((self.root / 'review-brief.md').exists())

    def test_verifier_cannot_hide_a_concurrent_content_change(self):
        self.verifier.write_text('#!/bin/sh\nprintf "changed\\n" > "$1/note.md"\nprintf "RESULT: PASS\\n"\n')
        with self.assertRaisesRegex(SystemExit, 'input changed'):
            self.prepare()
        self.assertFalse((self.root / 'review-brief.md').exists())

    def test_empty_handoff_cannot_manufacture_propagation(self):
        with self.assertRaisesRegex(SystemExit, 'no propagation receipt'):
            self.prepare({})

    def test_all_capture_inputs_checked_before_any_write(self):
        self.handoff['captures'].append({'kind': 'verifier', 'label': 'fake', 'text': 'PASS'})
        with self.assertRaisesRegex(SystemExit, 'cannot fabricate'):
            self.prepare()
        self.assertFalse(self.root.exists())

    def test_abbreviated_vault_override_is_rejected(self):
        self.handoff['classifications'][0] += ['--va', str(self.base)]
        with self.assertRaisesRegex(SystemExit, 'override'):
            self.prepare()
        self.assertFalse(self.root.exists())

    def test_retry_deduplicates_exact_evidence_but_keeps_distinct_excerpts(self):
        self.handoff['captures'] += [
            {'kind': 'evidence', 'label': 'reference', 'source': 'fixture', 'provenance': 'primary', 'text': text}
            for text in ['first fact', 'second fact']]
        self.prepare()
        self.prepare()
        evidence = [x for x in review.load_captures(self.root) if x['kind'] == 'evidence']
        self.assertEqual([x['text'] for x in evidence], ['first fact', 'second fact'])

    def test_corrected_retry_rebuilds_against_new_bytes(self):
        self.prepare()
        first = json.loads((self.root / 'review-brief-manifest.json').read_text())
        self.note.write_text('# Example\n\nCorrected result.\n')
        self.prepare()
        second = json.loads((self.root / 'review-brief-manifest.json').read_text())
        old = next(x for x in first['full_read'] if x['path'] == str(self.note))
        new = next(x for x in second['full_read'] if x['path'] == str(self.note))
        self.assertNotEqual(old['sha256'], new['sha256'])
        self.assertEqual(Path(new['snapshot_path']).read_text(), self.note.read_text())


if __name__ == '__main__':
    unittest.main()
