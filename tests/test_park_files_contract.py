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
                self.assertIn('[shared close-out protocol]', step)
                support = path.parent / ('../_closeout.md' if path.name == 'SKILL.md' else '_closeout.md')
                step += support.read_text(encoding='utf-8')
                self.assertIn('session-ledger.sh --read', step)
                self.assertIn('initial inventory', step)
                self.assertIn('propagation', step)
                self.assertIn('deduplicate', step)
                self.assertIn('same resolved path', step)
                self.assertIn('distinct installed/source paths', step)

    def test_inventory_names_extra_roots_and_remote_writes(self):
        for path in (ROOT / '.claude/commands/_closeout.md', ROOT / 'codex/skills/_closeout.md'):
            with self.subTest(path=path):
                section = path.read_text(encoding='utf-8').split('## Inventory', 1)[1].split('## Coverage', 1)[0]
                self.assertIn('[--root DIR ...]', section)
                self.assertIn('`# roots searched:`', section)
                self.assertIn('`~/.local/bin`', section)
                self.assertIn('`/etc`', section)
                self.assertIn('recall-only class', section)
                self.assertIn('`[remote]` row', section)

    def test_inventory_requires_ls_on_each_path_and_resolves_missing_as_moves(self):
        for path in (ROOT / '.claude/commands/_closeout.md', ROOT / 'codex/skills/_closeout.md'):
            with self.subTest(path=path):
                section = path.read_text(encoding='utf-8').split('## Inventory', 1)[1].split('## Coverage', 1)[0]
                self.assertIn('`ls -l -- "<exact path>"`', section)
                self.assertIn('lags fresh binaries and renames', section)
                self.assertIn('move to resolve', section)
                self.assertIn('full old path', section)
                self.assertIn('never write an unannotated local Files row for a path `ls` cannot find', section)

if __name__ == '__main__':
    unittest.main()
