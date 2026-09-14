"""Regression contract for the paired Files-list writer instructions."""
from pathlib import Path
import unittest

ROOT = Path(__file__).parents[1]
PAIR = (ROOT / '.claude/commands/park.md', ROOT / 'codex/skills/park/SKILL.md')


class ParkFilesContractTests(unittest.TestCase):
    def test_files_format_is_explicit_at_each_writer(self):
        for path in PAIR:
            with self.subTest(path=path):
                text = path.read_text(encoding='utf-8')
                body = text.split('### 3. Write the session log', 1)[1].split('**Write it:**', 1)[0]
                for section in ('Created', 'Updated', 'Deleted'):
                    row = body.split('### Files ' + section, 1)[1].split('\n\n', 1)[0]
                    self.assertIn('one path per line', row)
                    self.assertIn('never brace-expand or comma-group', row)
                self.assertIn('full vault-relative paths', body)
                self.assertIn('absolute or `~`-prefixed paths outside the vault', body)

    def test_touched_reconciles_inventory_and_deduplicates_paths(self):
        for path in PAIR:
            with self.subTest(path=path):
                step = path.read_text(encoding='utf-8').split('### 8. Backfill + mechanical verification', 1)[1].split('### 9.', 1)[0]
                self.assertIn('session-ledger.sh --read', step)
                self.assertIn('Step 2 inventory', step)
                self.assertIn('propagation', step)
                self.assertIn('deduplicate', step)
                self.assertIn('same resolved path', step)
                self.assertIn('distinct installed/source paths', step)


if __name__ == '__main__':
    unittest.main()
