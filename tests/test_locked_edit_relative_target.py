import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / ".claude/scripts/locked-edit.sh"


class RelativeTargetTests(unittest.TestCase):
    def test_relative_target_is_refused_with_absolute_candidates(self):
        with tempfile.TemporaryDirectory() as vault, tempfile.TemporaryDirectory() as elsewhere:
            note = Path(vault) / "01 Now" / "This Week.md"
            note.parent.mkdir()
            note.write_text("hello\n")
            env = {**os.environ, "VAULT_PATH": vault}
            r = subprocess.run(["bash", str(SCRIPT), "01 Now/This Week.md", "--append"], input="x\n",
                               capture_output=True, text=True, cwd=elsewhere, env=env)
            self.assertEqual(r.returncode, 1)
            self.assertIn("Target must be an absolute path", r.stderr)
            self.assertIn(f"candidate (absent): {elsewhere}/01 Now/This Week.md", r.stderr)
            self.assertIn(f"candidate (exists): {vault}/01 Now/This Week.md", r.stderr)
            self.assertEqual(note.read_text(), "hello\n")
            self.assertFalse((Path(elsewhere) / "01 Now").exists())


if __name__ == "__main__":
    unittest.main()
