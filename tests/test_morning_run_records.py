"""Run the morning "Unrecorded unattended runs" recipe (both renders) against a synthetic vault and run roots."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).parents[1]
RENDERS = (ROOT / '.claude/commands/morning.md', ROOT / 'codex/skills/morning/SKILL.md')
RUN_IDS = ('run-1', 'run-1-retry', 'run-2', 'run-3', 'v1.2-run')
NOTE = ('Recorded run-1-retry here.\n'
        'Also run-2.\n'
        'Ledger at ~/.claude/runs/v1.2-run/ledger\n'
        'Not run-3_old, run-3-b or run-3.x either.\n')


def recipe(path: Path) -> str:
    blocks = [textwrap.dedent(b) for b in re.findall(r'^ *```bash\n(.*?)^ *```', path.read_text(encoding='utf-8'), re.S | re.M)
              if 'UNRECORDED' in b]
    if len(blocks) != 1:
        raise AssertionError(f'{path}: expected one UNRECORDED recipe, found {len(blocks)}')
    return blocks[0]


@unittest.skipUnless(shutil.which('bash') and shutil.which('rg'), 'needs bash and ripgrep')
class UnrecordedRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runs = self.root / 'runs'
        for run_id in RUN_IDS:
            (self.runs / run_id).mkdir(parents=True)
        self.vault = self.root / 'vault'
        self.vault.mkdir()
        (self.vault / 'note.md').write_text(NOTE, encoding='utf-8')

    def run_recipe(self, render: Path, vault: Path) -> str:
        script = recipe(render).replace('{VAULT}', str(vault))
        env = dict(os.environ, OPENCAIRN_RUN_DIRS=str(self.runs))
        result = subprocess.run(['bash', '-c', script], cwd=self.root, env=env, text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_ids_match_only_on_exact_id_boundaries(self):
        for render in RENDERS:
            with self.subTest(render=render):
                out = self.run_recipe(render, self.vault)
                self.assertEqual(sorted(re.findall(r'^UNRECORDED (.*)$', out, re.M)), ['run-1', 'run-3'], out)

    def test_search_error_reports_not_checked(self):
        for render in RENDERS:
            with self.subTest(render=render):
                out = self.run_recipe(render, self.root / 'missing-vault')
                self.assertIn('Run records: not checked (rg exit 2)', out)
                self.assertNotIn('UNRECORDED', out)


if __name__ == '__main__':
    unittest.main()
