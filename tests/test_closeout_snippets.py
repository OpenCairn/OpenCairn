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
    env.pop('VAULT', None)  # Recipes must bind the resolved vault within their own call.
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
                result = run_bash(recipe(source, 'LIVE SEARCH'), root, NEEDLE='UPS',
                                  MATCH_MODE='word', RAW_OUT=str(out), RAW_ERR=str(err))
                self.assertEqual(result.returncode, 0, result.stderr)
                hits = out.read_text().splitlines()
                self.assertEqual(len(hits), 2)
                self.assertTrue(any('.hidden/config.toml' in line for line in hits))
                self.assertTrue(any('driver.py' in line for line in hits))
                self.assertNotIn('BACKUPS', out.read_text())
                self.assertIn('exit_status: 0', result.stdout)
                # A reused receipt path is an error, not silent truncation/overwrite.
                reused = run_bash(recipe(source, 'LIVE SEARCH'), root, NEEDLE='UPS',
                                  MATCH_MODE='word', RAW_OUT=str(out), RAW_ERR=str(err))
                self.assertEqual(reused.returncode, 2)
                self.assertEqual(len(out.read_text().splitlines()), 2)
                miss = run_bash(recipe(source, 'LIVE SEARCH'), root, NEEDLE='absent-subject',
                                MATCH_MODE='fixed', RAW_OUT=str(root/'miss.out'), RAW_ERR=str(root/'miss.err'))
                self.assertEqual(miss.returncode, 0, miss.stderr)
                self.assertIn('exit_status: 1', miss.stdout)
                self.assertEqual((root/'miss.out').read_bytes(), b'')
                # Dangling symlinks still occupy receipt names; neither the link nor its target is overwritten.
                for occupied in ('stdout', 'stderr'):
                    link = root/f'dangling-{occupied}'
                    target = root/f'absent-{occupied}'
                    link.symlink_to(target)
                    raw_out = link if occupied == 'stdout' else root/'fresh.out'
                    raw_err = link if occupied == 'stderr' else root/'fresh.err'
                    blocked = run_bash(recipe(source, 'LIVE SEARCH'), root, NEEDLE='UPS', MATCH_MODE='word',
                                       RAW_OUT=str(raw_out), RAW_ERR=str(raw_err))
                    self.assertEqual(blocked.returncode, 2)
                    self.assertIn('ERROR: receipt path already exists', blocked.stderr)
                    self.assertTrue(link.is_symlink())
                    self.assertFalse(target.exists())

    def test_collapse_counts_leaf_items_and_excludes_closeout_sessions(self):
        for source in GOODNIGHTS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); report, log = root/'report.md', root/'day.md'
                report.write_text("# Report\n## Today's Plan\n## Day\n- Administration\n"
                                  "  - ✓ Finished child\n  - Open child\n- ✓ Finished standalone\n"
                                  "## Sessions\n1. Example\n")
                log.write_text('## Session 1 - Work\n## Session 2 - Goodnight: Fixture\n'
                               '## Session 3 - Late work\n## Session 4 - Goodnight catch-up via $morning')
                result = run_bash(recipe(source, 'COLLAPSE COUNTS'), root, REPORT=str(report), SESSION_LOG=str(log))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), 'planned_leaf_items=3 closed_leaf_items=2 recorded_work_sessions=2')
                # Empty plan does not silently borrow bullets from Sessions.
                report.write_text("## Today's Plan\n## Day\n## Sessions\n- ✓ Not a plan item\n")
                empty = run_bash(recipe(source, 'COLLAPSE COUNTS'), root, REPORT=str(report), SESSION_LOG=str(log))
                self.assertIn('planned_leaf_items=0 closed_leaf_items=0', empty.stdout)
                # Duplicate numbers are a failed check rather than a usable inflated tally.
                log.write_text('## Session 1 - One\n## Session 1 - Duplicate\n')
                invalid = run_bash(recipe(source, 'COLLAPSE COUNTS'), root, REPORT=str(report), SESSION_LOG=str(log))
                self.assertNotEqual(invalid.returncode, 0)
                self.assertIn('ERROR: duplicate', invalid.stderr)

    def test_durability_scan_has_distinct_candidate_and_empty_observations(self):
        for source in CLOSEOUTS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); span = root/'span.md'
                span.write_text('All three items are pending; the latter goes tomorrow.\n')
                positive = run_bash(recipe(source, 'DURABILITY SCAN'), root, SCAN_INPUT=str(span))
                self.assertEqual(positive.returncode, 0, positive.stderr)
                self.assertIn('1:All three items', positive.stdout)
                self.assertIn('Durability scan: 0', positive.stdout)
                span.write_text('Stable action with an absolute destination.\n')
                negative = run_bash(recipe(source, 'DURABILITY SCAN'), root, SCAN_INPUT=str(span))
                self.assertEqual(negative.returncode, 0, negative.stderr)
                self.assertIn('Durability scan: 1', negative.stdout)
                failed = run_bash(recipe(source, 'DURABILITY SCAN'), root, SCAN_INPUT=str(root/'missing'))
                self.assertNotEqual(failed.returncode, 0)

    def test_completion_retention_copies_verified_bytes_and_refuses_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root/'vault'; scripts = vault/'.claude/scripts'; scripts.mkdir(parents=True)
            (scripts/'lib-session.sh').write_bytes((ROOT/'.claude/scripts/lib-session.sh').read_bytes())
            config = root/'config'; log = root/'day.md'; log.write_text('## Session 1 - Example\n')
            brief = root/'brief.snapshot'; brief.write_bytes(b'reviewed brief\n')
            manifest = root/'manifest.snapshot'
            bd = hashlib.sha256(brief.read_bytes()).hexdigest()
            manifest.write_text(json.dumps({'session_log':str(log), 'session_number':1, 'run_generation':'fixture', 'brief_sha256':bd, 'schema':3, 'completion_binding':1}))
            report = f'Evidence-bearing clean report\nCOMPLETE {bd}\nTerminal state: clean\n'
            r = {'schema':3,'kind':'completion','completion':True,'completion_binding':1,
                 'status':'clean','session_log':str(log),'session_number':1,'run_generation':'fixture',
                 'report':report,'report_sha256':hashlib.sha256(report.encode()).hexdigest(),
                 'brief_snapshot':str(brief),'brief_sha256':bd,'manifest_snapshot':str(manifest),
                 'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}
            receipt = root/'audit-fixture.json'; receipt.write_text(json.dumps(r))
            env = dict(CLAUDE_CONFIG_DIR=str(config), OPENCAIRN_SESSION_ID='snippet-fixture',
                       SESSION_LOG=str(log), N='1', ACCEPTED_RECEIPT=str(receipt))
            source = ROOT/'codex/skills/_closeout.md'
            result = run_bash(recipe(source, 'COMPLETION RETENTION'), root, **env)
            self.assertEqual(result.returncode, 0, result.stderr)
            bundles = list((config/'.session-state').glob('*.closeout/**/audit-receipt.json'))
            self.assertEqual(len(bundles), 1)
            bundle = bundles[0].parent
            self.assertEqual(bundles[0].read_bytes(), receipt.read_bytes())
            self.assertEqual((bundle/'review-report.md').read_text(), report)
            # Bundle snapshots remain usable after the original native scratch is removed.
            brief.unlink(); manifest.unlink()
            lookup = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
            self.assertIn('ACCEPTED\t', lookup.stdout)
            # Collision cannot silently rewrite a retained accepted report.
            (bundle/'review-report.md').write_text('different retained bytes')
            brief.write_bytes(b'reviewed brief\n'); manifest.write_text(json.dumps({'session_log':str(log), 'session_number':1, 'run_generation':'fixture', 'brief_sha256':bd, 'schema':3, 'completion_binding':1}))
            collision = run_bash(recipe(source, 'COMPLETION RETENTION'), root, **env)
            self.assertNotEqual(collision.returncode, 0)
            self.assertIn('ERROR: retained evidence collision', collision.stderr)
            self.assertEqual((bundle/'review-report.md').read_text(), 'different retained bytes')

    def test_completion_lookup_binds_subject_generation_and_report_hash(self):
        for source in CLOSEOUTS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); config = root/'config'; state = config/'.session-state'
                run = state/'fixture.park-review/runs/generation'; run.mkdir(parents=True)
                receipts = state/'.park-audit-receipts'; receipts.mkdir()
                log = root/'day.md'; log.write_text('## Session 1 - Fixture\n')
                brief = run/'brief.snapshot'; brief.write_bytes(b'Exact reviewed brief\n')
                bd = hashlib.sha256(brief.read_bytes()).hexdigest()
                manifest = {'session_log':str(log), 'session_number':1, 'run_generation':'generation', 'brief_sha256':bd, 'schema':3, 'completion_binding':1}
                mp = run/'manifest.snapshot'; mp.write_text(json.dumps(manifest))
                (run/'review-brief-manifest.json').write_text(json.dumps(manifest))
                report = f'Fixture evidence\nCOMPLETE {bd}\nTerminal state: clean\n'
                receipt = {'schema':3, 'kind':'completion', 'completion':True, 'completion_binding':1,
                           'run_generation':'generation', 'status':'clean', 'report':report,
                           'session_log':str(log), 'session_number':1,
                           'brief_snapshot':str(brief), 'brief_sha256':bd,
                           'manifest_snapshot':str(mp), 'manifest_sha256':hashlib.sha256(mp.read_bytes()).hexdigest(),
                           'report_sha256':hashlib.sha256(report.encode()).hexdigest()}
                rp = receipts/'audit.json'; rp.write_text(json.dumps(receipt))
                env = dict(CLAUDE_CONFIG_DIR=str(config), SESSION_LOG=str(log), N='1')
                good = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
                self.assertEqual(good.returncode, 0, good.stderr)
                self.assertIn('ACCEPTED\t', good.stdout)
                # The accepted immutable manifest survives a newer mutable generation manifest.
                (run/'review-brief-manifest.json').write_text(json.dumps(dict(manifest, session_number=2)))
                still = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
                self.assertIn('ACCEPTED\t', still.stdout)
                # A same-generation source-only import is not a completion receipt.
                rp.write_text(json.dumps(dict(receipt, kind='source-attestation', completion=False)))
                standalone = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
                self.assertIn('NO_ACCEPTED_RECEIPT', standalone.stdout)
                self.assertNotIn('ACCEPTED\t', standalone.stdout)
                rp.write_text(json.dumps(dict(receipt, completion_binding=True)))
                malformed_binding = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
                self.assertIn('NO_ACCEPTED_RECEIPT', malformed_binding.stdout)
                rp.write_text(json.dumps(receipt))
                # Explicit legacy-review imports retain a manual path, not an automatic completion.
                rp.write_text(json.dumps(dict(receipt, kind='legacy-review', completion=False)))
                historical = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env)
                self.assertIn('LEGACY_CANDIDATE\t', historical.stdout)
                self.assertNotIn('ACCEPTED\t', historical.stdout)
                rp.write_text(json.dumps(receipt))
                # A well-formed non-object receipt is ignored without breaking the lookup.
                (receipts/'malformed.json').write_text('[]')
                wrong = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **dict(env, N='2'))
                self.assertIn('NO_ACCEPTED_RECEIPT', wrong.stdout)
                self.assertNotIn('ACCEPTED\t', wrong.stdout)
                receipt['report'] = receipt['report'].replace('Fixture evidence', 'Tampered evidence')
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
