"""The locator migrator must preserve append-only provenance history."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class ProvenanceMigrationTests(unittest.TestCase):
    def test_rewrite_preserves_log_and_finishes_live_locator_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / 'vault'
            scripts = vault / '.claude/scripts'
            scripts.mkdir(parents=True)
            editor = Path(os.environ.get('PROVENANCE_EDITOR_SOURCE', REPO / '.claude/scripts')).resolve()
            for name in ('lib-lock.sh', 'lib-session.sh'):
                shutil.copy2(REPO / '.claude/scripts' / name, scripts / name)
            shutil.copy2(editor / 'locked-edit.sh', scripts / 'locked-edit.sh')
            writer = editor / 'write-provenance.py'
            if 'PROVENANCE_EDITOR_SOURCE' in os.environ:
                self.assertTrue(writer.is_file(), 'qualified guard requires its actual writer')
            if writer.is_file():
                shutil.copy2(writer, scripts / writer.name)
            (vault / '03 Projects').mkdir()
            (vault / '06 Archive/OpenCairn').mkdir(parents=True)
            log = vault / '07 System/AI Provenance Log.md'
            log.parent.mkdir()
            original = b'| 2001-02-03 | synthetic | 06 Archive/Claude/Session Logs/2001-02-03.md | `0123456789abcdef` | none |\n'
            protected = [log,
                         vault / '06 Archive/Backup/07 System/AI Provenance Log.md',
                         vault / '06 Archive/Backup/07 sYsTeM/Ai PrOvEnAnCe LoG.md',
                         vault / '06 Archive/Backup/07 sYsTeM/.pRoVeNaNcE/x.snapshot.md']
            for path in protected:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)
            target = vault / 'unscanned/record.md'
            target.parent.mkdir()
            target.write_bytes(original)
            alias = vault / '06 Archive/Alias/07 System/AI Provenance Log.md'
            alias.parent.mkdir(parents=True)
            try:
                alias.symlink_to(target)
            except (OSError, NotImplementedError):
                self.assertEqual(os.name, 'nt', 'POSIX qualification requires the symlink case')
                alias = None
            if alias is not None:
                protected.append(alias)
            note = vault / '03 Projects/Example.md'
            note.write_text('[[06 Archive/Claude/Session Logs/2001-02-03]]\n')
            env = dict(os.environ, VAULT_PATH=str(vault), CLAUDE_CONFIG_DIR=str(Path(tmp) / 'config'),
                       OPENCAIRN_SESSION_ID='provenance-migration-test', CODEX_THREAD_ID='provenance-migration-test',
                       CLAUDE_CODE_SESSION_ID='provenance-migration-test')
            command = [sys.executable, str(REPO / '.claude/scripts/archive-namespace-migration.py'), 'rewrite', str(vault)]
            first = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(json.loads(first.stdout)['count'], 1)
            for path in protected:
                self.assertEqual(path.read_bytes(), original, str(path))
            if alias is not None:
                self.assertTrue(alias.is_symlink())
            self.assertEqual(note.read_text(), '[[06 Archive/OpenCairn/Session Logs/2001-02-03]]\n')
            second = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertEqual(json.loads(second.stdout)['count'], 0)
            for path in protected:
                self.assertEqual(path.read_bytes(), original, str(path))
            if alias is not None:
                self.assertTrue(alias.is_symlink())


if __name__ == '__main__':
    unittest.main()
