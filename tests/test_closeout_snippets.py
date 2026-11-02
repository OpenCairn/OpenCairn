"""Run the closeout prompt's actual shell recipes on isolated inputs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
CLOSEOUTS = (ROOT / '.claude/commands/_closeout.md', ROOT / 'codex/skills/_closeout.md')
PARKS = (ROOT / '.claude/commands/park.md', ROOT / 'codex/skills/park/SKILL.md')
GOODNIGHTS = (ROOT / '.claude/commands/goodnight.md', ROOT / 'codex/skills/goodnight/SKILL.md')
PARK_REVIEW = ROOT / 'codex/skills/park/scripts/park-review.py'


def recipe(path: Path, marker: str) -> str:
    text = path.read_text(encoding='utf-8')
    match = re.search(r'<!-- BEGIN ' + marker + r' -->\s*```bash\n(.*?)\n```\s*<!-- END ' + marker + r' -->', text, re.S)
    if match is None:
        raise AssertionError(f'{path}: missing executable {marker} recipe')
    return match.group(1)


def run_bash(script: str, root: Path, **values: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.pop('VAULT', None)  # Recipes must bind the resolved vault within their own call.
    # Session-scoped state stays inside the fixture, never the real config directory.
    env['CLAUDE_CONFIG_DIR'] = str(root/'config'); env['OPENCAIRN_SESSION_ID'] = 'snippet-fixture'
    env.update(values)
    lib = root/'vault/.claude/scripts/lib-session.sh'
    if 'lib-session.sh' in script and not lib.exists():
        lib.parent.mkdir(parents=True, exist_ok=True)
        lib.write_bytes((ROOT/'.claude/scripts/lib-session.sh').read_bytes())
    env['TMPDIR'] = str(root)
    return subprocess.run(['bash', '-c', script.replace('{VAULT}', str(root/'vault'))], cwd=root, env=env, text=True, capture_output=True, timeout=20)


SECTION_REFERENCE = re.compile(
    r'((?:\*\*[^*]+\*\*(?:,\s*|\s+and\s+)?)+)\s+in the \[shared close-out protocol\]'
    r"|shared protocol(?:’|')s ((?:\*\*[^*]+\*\*(?:,\s*|\s+and\s+)?)+)")


class CloseoutSnippetTests(unittest.TestCase):
    def test_caller_section_references_resolve_in_sibling_closeout(self):
        for caller in (*PARKS, *GOODNIGHTS):
            closeout = CLOSEOUTS[0] if caller.parent.name == 'commands' else CLOSEOUTS[1]
            with self.subTest(caller=caller):
                headings = set(re.findall(r'^#{2,3} (.+?)\s*$', closeout.read_text(encoding='utf-8'), re.M))
                cited = set()
                for match in SECTION_REFERENCE.finditer(caller.read_text(encoding='utf-8')):
                    cited.update(re.findall(r'\*\*([^*]+)\*\*', match.group(1) or match.group(2)))
                self.assertIn('Inventory', cited, 'reference pattern must still match the caller prose')
                self.assertEqual(sorted(cited - headings), [])

    def test_codex_goodnight_propagation_is_one_structured_capture(self):
        step = re.search(r'^\*\*Prepare and verify:\*\*.*$', GOODNIGHTS[1].read_text(encoding='utf-8'), re.M).group(0)
        self.assertIn("shared protocol's **Propagation receipts**", step)
        self.assertNotIn('capture --kind propagation', step, 'a second prose capture would supersede the receipts')
        labels = re.findall(r'--label "([^"]+)"', step)
        propagation_label = next(label for label in labels if 'propagation' in label.lower())
        acceptance_label = next(label for label in labels if 'acceptance' in label.lower())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root/'vault'; vault.mkdir()
            env = {'PATH': os.environ.get('PATH', os.defpath), 'HOME': str(root), 'VAULT_PATH': str(vault),
                   'CLAUDE_CONFIG_DIR': str(root/'config'), 'OPENCAIRN_SESSION_ID': 'goodnight-fixture'}

            def review(*args, body=None):
                result = subprocess.run([sys.executable, str(PARK_REVIEW), *map(str, args)], env=env,
                                        input=body, text=True, capture_output=True, timeout=60)
                return result

            def ok(*args, body=None):
                result = review(*args, body=body)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result

            ok('begin-run')
            note, log = vault/'note.md', vault/'log.md'
            note.write_text('Fixture subject retained.\n')
            log.write_text('## Session 1 - Goodnight: Fixture\n\n### Summary\nClosed the day.\n\n'
                           '### Files Created\nNone\n\n'
                           f'### Files Updated\n- `{note}` - routed task\n- `{log}` - record\n\n'
                           '### Pickup Context\n**For next session:** None.\n**Project:** None\n')
            for path in (note, log):
                ok('classify', '--vault', vault, '--path', path, '--semantic', '--reason', 'fixture close-out')
            # The order the Codex Goodnight step prescribes: search, receipts, acceptance checks, verify, build.
            argv = ['rg', '--hidden', '--no-ignore', '-n', '-F', '-i', '--', 'Fixture subject', '.']
            searched = subprocess.run(argv, cwd=vault, capture_output=True, timeout=20)
            self.assertEqual(searched.returncode, 0, searched.stderr)
            out, err = root/'search.out', root/'search.err'
            out.write_bytes(searched.stdout); err.write_bytes(searched.stderr)
            ok('capture', '--kind', 'enumeration', '--label', 'Final needles',
               body=json.dumps({'needles': [{'needle': 'Fixture subject', 'match_mode': 'phrase'}]}))
            ok('capture', '--kind', 'propagation', '--label', propagation_label, body=json.dumps({
                'report': 'Fixture subject: one live hit, current.', 'searches': [{
                    'needle': 'Fixture subject', 'match_mode': 'phrase', 'exit_status': searched.returncode,
                    'command': shlex.join(argv), 'cwd': str(vault),
                    'stdout_file': str(out), 'stderr_file': str(err)}]}))
            ok('capture', '--kind', 'evidence', '--source', 'goodnight caller contract', '--label',
               acceptance_label, '--provenance', 'primary', body='Carry unfinished tasks intact.\n')
            ok('run-verifier', '--', sys.executable, '-c', "print('RESULT: PASS')")
            build = ('build', '--vault', vault, '--session-log', log, '--number', '1', '--check-dependencies')
            self.assertIn('Reviewer brief:', ok(*build).stdout)
            # Control: the superseded prose capture becomes the latest receipt and fails the coverage gate.
            ok('capture', '--kind', 'propagation', '--label', propagation_label, body='Prose-only result.\n')
            stale = review(*build)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn('no structured executed-search set', stale.stderr)

    def test_claude_saved_report_is_the_lookup_candidate_its_prose_names(self):
        source = CLOSEOUTS[0]
        text = source.read_text(encoding='utf-8')
        lookup = text.split('### Completion lookup', 1)[1]
        self.assertIn("this harness's current record, not a legacy one", lookup)
        self.assertNotIn('lists legacy saved reports', lookup)
        self.assertNotIn('known accepted log/N in these same stores returns `ACCEPTED`', lookup)
        saving = re.search(r'^After the final clean report.*$', text, re.M).group(0)
        header = re.findall(r'`([A-Z][A-Za-z0-9 -]+: <[^>]+>|Close-out accepted: clean)`', saving)
        self.assertEqual(len(header), 5, header)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); config = root/'config'; log = root/'day.md'
            log.write_text('## Session 1 - Fixture\n')
            brief = config/'.session-state/fixture.closeout/day-1-brief.md'
            brief.parent.mkdir(parents=True); brief.write_text('Reviewed brief\n')
            values = {'Session log': str(log), 'Session number': '1', 'Brief path': str(brief),
                      'Brief SHA-256': hashlib.sha256(brief.read_bytes()).hexdigest()}
            lines = [line if '<' not in line else line.split(':', 1)[0] + ': ' + values[line.split(':', 1)[0]]
                     for line in header]
            report = brief.with_name('day-1-report.md')
            report.write_text('\n'.join(lines) + '\nRESULT: PASS\nTerminal state: clean\n')
            env = dict(CLAUDE_CONFIG_DIR=str(config), SESSION_LOG=str(log))
            found = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env, N='1')
            self.assertEqual(found.returncode, 0, found.stderr)
            self.assertEqual(found.stdout.splitlines(), ['NO_ACCEPTED_RECEIPT', f'LEGACY_CANDIDATE\t{report}'])
            wrong = run_bash(recipe(source, 'COMPLETION LOOKUP'), root, **env, N='2')
            self.assertEqual(wrong.stdout.splitlines(), ['NO_ACCEPTED_RECEIPT'])

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
                suffix = '\nprintf "BLOCK=%s\\nPATHS=%s\\n" "$SESSION_BLOCK" "$SESSION_PATHS"'
                result = run_bash(recipe(source, 'SESSION EXTRACT') + suffix, root, SESSION_LOG=str(log), N='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if not line.startswith('SESSION_'))
                self.assertNotIn('Foreign work', Path(fields['BLOCK']).read_text())
                self.assertEqual(Path(fields['PATHS']).read_text().splitlines(),
                                 ['04 Areas/Context - fixture.md', '/tmp/tool', '04 Areas/Old - fixture.md'])
                last = run_bash(recipe(source, 'SESSION EXTRACT') + suffix, root, SESSION_LOG=str(log), N='10')
                self.assertEqual(last.returncode, 0, last.stderr)
                final = dict(line.split('=', 1) for line in last.stdout.splitlines() if not line.startswith('SESSION_'))
                self.assertIn('Foreign work', Path(final['BLOCK']).read_text())
                self.assertNotIn('Own work', Path(final['BLOCK']).read_text())

    def test_session_extraction_skips_none_placeholder_rows(self):
        suffix = '\nprintf "PATHS=%s\\n" "$SESSION_PATHS"'
        for source in CLOSEOUTS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); vault = root/'vault'; vault.mkdir(); log = vault/'day.md'
                (vault/'a.md').write_text('edited\n')
                # Placeholder forms the verifier or backfill writer reads as an empty list.
                log.write_text('## Session 1 - Fixture\n### Summary\nx\n### Files Created\n- None\n'
                               '### Files Updated\n- `a.md` - edit\n- none\n- None.\n'
                               '- None (nothing else)\n### Files Deleted\n- None - nothing removed\n'
                               '### Pickup Context\n**Project:** None\n', encoding='utf-8')
                result = run_bash(recipe(source, 'SESSION EXTRACT') + suffix, root, SESSION_LOG=str(log), N='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                paths = [l.split('=', 1)[1] for l in result.stdout.splitlines() if l.startswith('PATHS=')]
                self.assertEqual(Path(paths[0]).read_text().splitlines(), ['a.md'])
                # Negative controls: real paths that merely begin with the word stay rows.
                log.write_text('## Session 1 - Fixture\n### Files Created\n- None (draft).md - real\n'
                               '- Nonesuch.md - real\n- `None` - explicit backticked path\n', encoding='utf-8')
                kept = run_bash(recipe(source, 'SESSION EXTRACT') + suffix, root, SESSION_LOG=str(log), N='1')
                self.assertEqual(kept.returncode, 0, kept.stderr)
                paths = [l.split('=', 1)[1] for l in kept.stdout.splitlines() if l.startswith('PATHS=')]
                self.assertEqual(Path(paths[0]).read_text().splitlines(),
                                 ['None (draft).md', 'Nonesuch.md', 'None'])

    def test_extracted_touched_list_passes_verifier_with_none_files_section(self):
        # End to end with the real verifier: `- None` must not become `--touched None`.
        suffix = '\nprintf "PATHS=%s\\n" "$SESSION_PATHS"'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root/'vault'; vault.mkdir(); log = vault/'day.md'
            (vault/'a.md').write_text('edited\n')
            log.write_text('## Session 1 - Fixture\n### Summary\nx\n### Key Insights\nx\n'
                           '### Files Created\n- None\n### Files Updated\n- `a.md` - edit\n'
                           '### Pickup Context\n**Project:** None\n', encoding='utf-8')
            for source in CLOSEOUTS:
                with self.subTest(source=source):
                    result = run_bash(recipe(source, 'SESSION EXTRACT') + suffix, root, SESSION_LOG=str(log), N='1')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    paths = next(l[6:] for l in result.stdout.splitlines() if l.startswith('PATHS='))
                    args = [arg for p in Path(paths).read_text().splitlines() for arg in ('--touched', p)]
                    self.assertEqual(args, ['--touched', 'a.md'])
                    verify = subprocess.run([str(ROOT/'.claude/scripts/park-verify.sh'), str(vault), str(log), '1', *args],
                                            env=dict(os.environ, HOME=str(root)), stdin=subprocess.DEVNULL,
                                            text=True, capture_output=True, timeout=60)
                    self.assertNotIn('FAIL', verify.stdout)
                    self.assertIn('RESULT: PASS', verify.stdout)

    def test_session_extraction_outputs_survive_separate_shell_calls(self):
        # Each Bash/Codex tool call is a fresh shell: producer and consumers run in separate bash -c.
        for source in CLOSEOUTS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); vault = root/'vault'; scripts = vault/'.claude/scripts'; scripts.mkdir(parents=True)
                (scripts/'lib-session.sh').write_bytes((ROOT/'.claude/scripts/lib-session.sh').read_bytes())
                stub = scripts/'park-verify.sh'
                stub.write_text('#!/usr/bin/env bash\necho STUB_RAN\nprintf "ARG=%s\\n" "$@"\n'); stub.chmod(0o755)
                wrapper = root/'park-review.py'
                wrapper.write_text('import subprocess, sys\nsys.exit(subprocess.call(sys.argv[sys.argv.index("--")+1:]))\n')
                log = vault/'day.md'
                log.write_text('## Session 1 - Fixture\n### Summary\nAll three items closed.\n'
                               '### Files Created\n- None\n### Files Updated\n- `a.md` - edit\n- `b - c.md` - edit\n'
                               '### Pickup Context\n**Project:** None\n', encoding='utf-8')
                env = dict(CLAUDE_CONFIG_DIR=str(root/'config'), OPENCAIRN_SESSION_ID='split-fixture')
                produced = run_bash(recipe(source, 'SESSION EXTRACT'), root, **env, SESSION_LOG=str(log), N='1')
                self.assertEqual(produced.returncode, 0, produced.stderr)
                printed = dict(l.split('=', 1) for l in produced.stdout.splitlines() if l.startswith('SESSION_'))
                self.assertEqual(sorted(printed), ['SESSION_BLOCK', 'SESSION_PATHS'], produced.stdout)
                state = root/'config/.session-state/split-fixture.closeout'
                for path in printed.values():
                    self.assertTrue(Path(path).is_file())
                    self.assertTrue(Path(path).is_relative_to(state), path)
                # Deterministic: a rerun after a fix rewrites the same files.
                again = run_bash(recipe(source, 'SESSION EXTRACT'), root, **env, SESSION_LOG=str(log), N='1')
                self.assertEqual(dict(l.split('=', 1) for l in again.stdout.splitlines() if l.startswith('SESSION_')), printed)
                # Verifier consumer in its own call, with no variable inherited from the producer.
                template = recipe(source, 'VERIFY')
                placeholder = '"<SESSION_PATHS path printed by Assigned-session extraction>"'
                self.assertIn(placeholder, template)
                consumer = re.sub(r'^\s*--ident .*$', lambda _: '  --ident "fixture" \\', template, flags=re.M)
                consumer = consumer.replace('"<session log>" N', f'"{log}" 1')
                fresh = dict(CLAUDE_CONFIG_DIR=str(root/'config'), PARK_REVIEW=str(wrapper))
                verified = run_bash(consumer.replace(placeholder, shlex.quote(printed['SESSION_PATHS'])), root, **fresh)
                self.assertEqual(verified.returncode, 0, verified.stderr)
                args = [l[4:] for l in verified.stdout.splitlines() if l.startswith('ARG=')]
                self.assertEqual(args[-4:], ['--touched', 'a.md', '--touched', 'b - c.md'])
                # Control: a missing path list stops before the verifier runs with no --touched.
                missing = run_bash(consumer.replace(placeholder, shlex.quote(str(root/'absent.txt'))), root, **fresh)
                self.assertNotEqual(missing.returncode, 0)
                self.assertNotIn('STUB_RAN', missing.stdout)
                # Final evidence check consumer: the durability scan reads the retained block in its own call.
                scanned = run_bash(recipe(source, 'DURABILITY SCAN'), root, SCAN_INPUT=printed['SESSION_BLOCK'])
                self.assertEqual(scanned.returncode, 0, scanned.stderr)
                self.assertIn('All three items closed', scanned.stdout)
                self.assertNotIn('Concurrent', Path(printed['SESSION_BLOCK']).read_text())

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
                # H in the seat's report is this printed count of the raw stdout, not a hand count.
                self.assertIn(f'records: {len(hits)}\n', result.stdout)
                # A reused receipt path is an error, not silent truncation/overwrite.
                reused = run_bash(recipe(source, 'LIVE SEARCH'), root, NEEDLE='UPS',
                                  MATCH_MODE='word', RAW_OUT=str(out), RAW_ERR=str(err))
                self.assertEqual(reused.returncode, 2)
                self.assertEqual(len(out.read_text().splitlines()), 2)
                miss = run_bash(recipe(source, 'LIVE SEARCH'), root, NEEDLE='absent-subject',
                                MATCH_MODE='fixed', RAW_OUT=str(root/'miss.out'), RAW_ERR=str(root/'miss.err'))
                self.assertEqual(miss.returncode, 0, miss.stderr)
                self.assertIn('exit_status: 1', miss.stdout)
                self.assertIn('records: 0\n', miss.stdout)
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

    def test_live_search_ignores_user_ripgrep_config(self):
        for source in PARKS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); vault = root/'vault'
                note = vault/'04 Areas/note.md'; note.parent.mkdir(parents=True)
                note.write_text('a long line naming the subject phrase in full\n')
                config = root/'ripgreprc'
                config.write_text('--max-columns=5\n--glob=!**/04 Areas/**\n')
                out, err = root/'raw.out', root/'raw.err'
                result = run_bash(recipe(source, 'LIVE SEARCH'), root, NEEDLE='subject phrase',
                                  MATCH_MODE='phrase', RAW_OUT=str(out), RAW_ERR=str(err),
                                  RIPGREP_CONFIG_PATH=str(config))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('exit_status: 0', result.stdout)
                self.assertEqual(out.read_text(),
                                 './04 Areas/note.md:1:a long line naming the subject phrase in full\n')
                self.assertIn('records: 1\n', result.stdout)

    def test_oversized_ignored_source_uses_separate_supplemental_receipt(self):
        for source in PARKS:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); vault = root/'vault'; vault.mkdir()
                subprocess.run(['git', 'init', '-q', str(vault)], check=True, capture_output=True)
                (vault/'.gitignore').write_text('*.py\n')
                small, large = vault/'small.py', vault/'large.py'
                small.write_text('subject phrase\n')
                with large.open('wb') as handle:
                    handle.write(b'padding\n' * (3 * 1024 * 1024 // 8))
                    handle.write(b'subject phrase\n')
                ignored = subprocess.run(['git', '-C', str(vault), 'check-ignore', '-q', str(large)])
                self.assertEqual(ignored.returncode, 0)
                self.assertGreater(large.stat().st_size, 2 * 1024 * 1024)
                out, err = root/'primary.out', root/'primary.err'
                primary = run_bash(recipe(source, 'LIVE SEARCH'), root, NEEDLE='subject phrase',
                                   MATCH_MODE='phrase', RAW_OUT=str(out), RAW_ERR=str(err))
                self.assertEqual(primary.returncode, 0, primary.stderr)
                self.assertEqual(out.read_text(), './small.py:1:subject phrase\n')
                supplemental_out, supplemental_err = root/'supplemental.out', root/'supplemental.err'
                command = ['rg', '--hidden', '--no-ignore', '-n', '-F', '-i', '--', 'subject phrase', str(large)]
                supplemental = subprocess.run(command, cwd=vault, text=True, capture_output=True, timeout=20)
                supplemental_out.write_text(supplemental.stdout); supplemental_err.write_text(supplemental.stderr)
                self.assertEqual(supplemental.returncode, 0, supplemental.stderr)
                self.assertIn('subject phrase', supplemental_out.read_text())
                self.assertEqual(len(supplemental_out.read_text().splitlines()), 1)
                # The additional raw streams stay separate from the required default receipt.
                self.assertEqual(out.read_text(), './small.py:1:subject phrase\n')
                self.assertEqual(supplemental_err.read_bytes(), b'')

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
