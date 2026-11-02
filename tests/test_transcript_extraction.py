"""Run the published-transcript recipes in _shared-rules-content.md §15 on saved page fixtures."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).parents[1]
RULES = (ROOT / '.claude/commands/_shared-rules-content.md', ROOT / 'codex/skills/_shared-rules-content.md')
FIXTURES = ROOT / 'tests/fixtures/transcript-extraction'
# Synthetic page with the structure of a WordPress transcript template: an <article> whose <header> holds a "Transcript for ..." H1,
# show notes and a timestamped chapter list below it, then one <div class="ts-segment"> per speaker turn.
WORDPRESS = FIXTURES / 'wordpress-ts-segment.html'
GHOST = """<html><head><title>Episode</title></head><body><article class="post">
<section class="gh-content">
<p>Show notes: Jane Doe joins to talk about tides.</p>
<div class="kg-card kg-embed-card"><iframe src="https://example.invalid/player"></iframe></div>
<div><p>Resources: <a href="https://example.invalid/tides">a tide table</a>.</p></div>
<h2>Transcript</h2>
<p><strong>Jane Doe:</strong> Tides follow the moon, <span class="hl">mostly</span>.</p>
<p><strong>Host:</strong> Mostly?</p>
</section></article></body></html>
"""
GHOST_BODY = ('Show notes: Jane Doe joins to talk about tides.\n\n'
              'Resources: [a tide table](https://example.invalid/tides).\n\n'
              '## Transcript\n\n'
              '**Jane Doe:** Tides follow the moon, mostly.\n\n'
              '**Host:** Mostly?')
TOOLS = all(shutil.which(tool) for tool in ('bash', 'pandoc', 'rg', 'awk', 'sed', 'cksum')) and all(
    importlib.util.find_spec(module) for module in ('bs4', 'lxml'))


def recipe(path: Path, needle: str) -> str:
    """The fenced bash block of §15 containing needle, dedented when it sits under a list item."""
    section = path.read_text(encoding='utf-8').split('## 15. ', 1)[1].split('\n## ', 1)[0]
    found = [textwrap.dedent(block) for block in re.findall(r'^ *```bash\n(.*?)^ *```', section, re.S | re.M)
             if needle in block]
    if len(found) != 1:
        raise AssertionError(f'{path}: expected one §15 recipe containing {needle!r}, found {len(found)}')
    return found[0]


class RecipeParityTests(unittest.TestCase):  # reads the rules files only; no tools needed
    def test_recipes_match_across_harnesses(self):
        for needle in ('SLUG=', 'BOUND=', 'rg -o "${TURN:?'):
            with self.subTest(needle=needle):
                self.assertEqual(recipe(RULES[0], needle), recipe(RULES[1], needle))


@unittest.skipUnless(TOOLS, 'needs bash, pandoc, ripgrep, python bs4 + lxml')
class TranscriptExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fake = self.root / 'bin/curl'  # serve the fixture instead of fetching: copy $PAGE to the -o path
        fake.parent.mkdir()
        fake.write_text('#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && { cp "$PAGE" "$2"; exit; }; shift; done\n'
                        'cat "$PAGE"\n')
        fake.chmod(0o755)

    def run_bash(self, script: str, **env: str) -> subprocess.CompletedProcess:
        full = dict(os.environ, PATH=f"{self.root/'bin'}{os.pathsep}{os.environ.get('PATH', os.defpath)}",
                    TMPDIR=str(self.root), **env)
        result = subprocess.run(['bash', '-c', script], cwd=self.root, env=full, text=True, capture_output=True,
                                timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def extract(self, rules: Path, page: Path, url: str) -> tuple[str, Path]:
        result = self.run_bash(recipe(rules, 'SLUG=').replace('<URL>', url), PAGE=str(page))
        body = Path(re.search(r'^BODY=(.*)$', result.stdout, re.M).group(1))
        return result.stdout, body

    def split(self, rules: Path, body: Path) -> str:
        return self.run_bash(recipe(rules, 'BOUND=') + 'echo "TURN=$TURN"\n', BODY=str(body)).stdout

    def test_header_wrapper_does_not_leak(self):
        for rules in RULES:
            with self.subTest(rules=rules):
                out, body = self.extract(rules, WORDPRESS, 'https://example.invalid/episode-transcript')
                text = body.read_text(encoding='utf-8')
                self.assertNotIn('<div', text)
                self.assertRegex(out, r'(?m)^0$', 'leak count')
                self.assertTrue(text.startswith('# Transcript for Tides and Orbits'))

    def test_each_speaker_turn_keeps_its_own_line(self):
        for rules in RULES:
            with self.subTest(rules=rules):
                out, body = self.extract(rules, WORDPRESS, 'https://example.invalid/episode-transcript')
                text = body.read_text(encoding='utf-8')
                self.assertEqual(len(re.findall(r'\[\(\d\d:\d\d:\d\d\)\]', text)), 8)
                turns = re.findall(r'^(Avery Host|Blake Guest|Casey Guest) \[\(\d', text, re.M)
                self.assertEqual(len(turns), 8, 'one line per speaker turn')
                longest = re.search(r'^longest line: (\d+)$', out, re.M)
                self.assertIsNotNone(longest, 'the gate reports the longest line')
                self.assertLess(int(longest.group(1)), 1000)

    def test_boundary_puts_show_notes_and_chapter_list_in_human_half(self):
        for rules in RULES:
            with self.subTest(rules=rules):
                _, body = self.extract(rules, WORDPRESS, 'https://example.invalid/episode-transcript')
                lines = body.read_text(encoding='utf-8').split('\n')
                out = self.split(rules, body)
                bound = int(re.search(r'^boundary line: (\d+)$', out, re.M).group(1))
                self.assertTrue(lines[bound - 1].startswith('Avery Host [(00:00:00)]'), lines[bound - 1])
                human = '\n'.join(lines[:bound - 1])
                self.assertIn('human generated', human)
                chapters = re.findall(r'(?m)^[^a-z0-9]*\(?\**\[?[0-9]{1,2}:[0-9]{2}', human)
                self.assertEqual(len(chapters), 15, 'timestamped chapter list sits in the human half')

    def test_speaker_labels_name_the_participants(self):
        for rules in RULES:
            with self.subTest(rules=rules):
                _, body = self.extract(rules, WORDPRESS, 'https://example.invalid/episode-transcript')
                out = self.split(rules, body)
                env = dict(BODY=str(body), BOUND=re.search(r'^boundary line: (\d+)$', out, re.M).group(1),
                           TURN=re.search(r'^TURN=(.*)$', out, re.M).group(1))
                labels = self.run_bash(recipe(rules, 'rg -o "${TURN:?'), **env).stdout.split('\n')
                counts = {line.split(None, 1)[1]: int(line.split()[0]) for line in labels if line.strip()}
                self.assertEqual(counts, {'Avery Host': 6, 'Blake Guest': 1, 'Casey Guest': 1})

    def test_split_fails_when_nothing_human_written_precedes_the_candidate(self):
        cases = {
            'title heading only': '# Transcript\n\nJust prose with no labelled turns.\n',
            'leaked wrapper above heading': '<div class="entry-header">\n\n## Transcript\n\nProse.\n',
        }
        for rules in RULES:
            for name, text in cases.items():
                with self.subTest(rules=rules, case=name):
                    body = self.root / 'body.md'
                    body.write_text(text, encoding='utf-8')
                    self.assertIn('SPLIT FAILED', self.split(rules, body))

    def test_label_first_chapter_list_is_not_a_speaker_turn(self):
        chapters = 'Show notes: Jane Doe on tides.\n\nIntro (0:00)\n\n**Tides (5:12)**\n\nThe moon [(10:30)](#moon)\n\n'
        cases = {
            'no transcript follows': (chapters + 'Thanks for listening.\n', None),
            'labelled turns follow': (chapters + 'Jane Doe (0:00) Tides follow the moon.\n\nHost (0:15) Mostly?\n', 9),
        }
        for rules in RULES:
            for name, (text, bound) in cases.items():
                with self.subTest(rules=rules, case=name):
                    body = self.root / 'body.md'
                    body.write_text(text, encoding='utf-8')
                    out = self.split(rules, body)
                    if bound is None:
                        self.assertIn('SPLIT FAILED', out)
                    else:
                        self.assertIn(f'boundary line: {bound}\n', out)

    def test_labels_check_requires_bound(self):
        for rules in RULES:
            with self.subTest(rules=rules):
                self.assertIn('"${BOUND:?', recipe(rules, 'rg -o "${TURN:?'))

    def test_ghost_page_output_and_boundary_unchanged(self):
        page = self.root / 'ghost.html'
        page.write_text(GHOST, encoding='utf-8')
        for rules in RULES:
            with self.subTest(rules=rules):
                _, body = self.extract(rules, page, 'https://example.invalid/ghost-episode/')
                self.assertEqual(body.read_text(encoding='utf-8').strip(), GHOST_BODY)
                self.assertIn('boundary line: 5\n', self.split(rules, body))


if __name__ == '__main__':
    unittest.main()
