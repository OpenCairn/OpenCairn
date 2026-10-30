"""Execute the planning-maintenance recipes against isolated ordinary-use controls."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
TREES = (ROOT / '.claude/commands', ROOT / 'codex/skills')


def recipe(path, marker):
    text = path.read_text()
    start = text.index(marker)
    start = text.index('```bash\n', start) + len('```bash\n')
    return text[start:text.index('```', start)]


class PlanningMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / 'vault'
        (self.vault / '03 Projects').mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(self.root / 'home'),
                        OPENCAIRN_TEMPLATE_DIR=str(self.root / 'template'))

    def run_recipe(self, code):
        return subprocess.run(['bash', '-c', code.replace('{VAULT}', str(self.vault))],
                              capture_output=True, text=True, env=self.env, timeout=15)

    def test_hub_age_uses_only_frontmatter_and_reports_check_failures(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                code = recipe(tree / ('weekly-hygiene.md' if tree.name == 'commands'
                                      else 'weekly-hygiene/SKILL.md'), 'Hub review age:')
                code = code.replace('W=<resolved window>; today=$(date +%F)',
                                    'W=14; today=2001-02-02')
                hub = self.vault / '03 Projects/Fixture.md'
                hub.write_text('# Fixture\nlast_reviewed: 2001-02-01\n')
                absent = self.run_recipe(code)
                self.assertEqual(absent.returncode, 0, absent.stderr)
                self.assertIn('last_reviewed absent', absent.stdout)
                hub.write_text('---\nlast_reviewed: 2001-02-01\n---\n# Fixture\n')
                present = self.run_recipe(code)
                self.assertEqual(present.returncode, 0, present.stderr)
                self.assertIn('1 days ago', present.stdout)
                self.assertNotIn('absent', present.stdout)
                hub.write_text('---\nlast_reviewed: not-a-date\n---\n')
                bad = self.run_recipe(code)
                self.assertNotEqual(bad.returncode, 0)
                self.assertIn('CHECK FAILED', bad.stdout + bad.stderr)
                self.assertNotIn('last_reviewed absent', bad.stdout)

    def test_pointer_recipe_rejects_prose_but_detects_real_missing_filename(self):
        commands = self.vault / '.claude/commands'
        commands.mkdir(parents=True)
        (commands / 'park.md').write_text('fixture\n')
        index = commands / '_shared-patterns.md'
        index.write_text('## Patterns\n- Valid → `park` plus `Cold/` and `command -v`\n')
        code = recipe(TREES[0] / 'weekly-hygiene.md', 'Scan every commands tree present')
        result = self.run_recipe(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('1 pointers, 0 stale', result.stdout)
        index.write_text(index.read_text() + '- Missing → `missing-skill`\n')
        bad = self.run_recipe(code)
        self.assertIn('STALE pointer: missing-skill', bad.stdout)
        self.assertIn('2 pointers, 1 stale', bad.stdout)

    def test_lock_recipe_reports_candidates_and_preserves_canonical_inode(self):
        lock = self.vault / '.Fixture.md.lock'
        lock.touch()
        os.utime(lock, (1, 1))
        inode = lock.stat().st_ino
        fallback = self.vault / '.Fixture.md.lock.d'
        fallback.mkdir()
        (fallback / 'owner').write_text('unverified fixture owner\n')
        for tree in TREES:
            with self.subTest(tree=tree):
                path = tree / ('weekly-hygiene.md' if tree.name == 'commands'
                               else 'weekly-hygiene/SKILL.md')
                code = recipe(path, '**Lock sentinels**')
                result = self.run_recipe(code)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(lock.exists(), result.stdout)
                self.assertEqual(lock.stat().st_ino, inode)
                self.assertIn('CANONICAL_LOCK_FILES=1', result.stdout)
                self.assertIn(str(lock), result.stdout)
                self.assertIn(str(fallback), result.stdout)
                self.assertTrue((fallback / 'owner').is_file())


if __name__ == '__main__':
    unittest.main()
