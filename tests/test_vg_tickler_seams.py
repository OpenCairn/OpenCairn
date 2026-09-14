"""Synthetic regression checks for write-tickler.sh section boundaries."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / ".claude/scripts/write-tickler.sh"
ITEM = r"- [ ] Synthetic reminder -> [[fixture]] literal \n and \t"
PREFIX = "# Tickler\n\nSynthetic prose.\n\n\nKeep these prose blanks.\n\n---\n"
EARLY = "## 2030-01-10\n- [ ] Early task\n\nEarly notes.\n"
LATE = "## 2030-01-30\n- [x] Later task\n\n\nLater notes.\n"


class TicklerSeams(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tickler-seams-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.tickler = root / "synthetic-vault" / "01 Now" / "Tickler.md"
        self.tickler.parent.mkdir(parents=True)
        config = root / "claude-config"
        config.mkdir()
        self.env = {
            "PATH": os.defpath,
            "HOME": str(root),
            "CLAUDE_CONFIG_DIR": str(config),
            "OPENCAIRN_SESSION_ID": "synthetic-tickler-seams",
        }

    def run_writer(self, date, item=ITEM):
        return subprocess.run(
            ["bash", str(SCRIPT), str(self.tickler), date, item],
            env=self.env, cwd=self.temp.name, capture_output=True, text=True,
            timeout=15,
        )

    def check_write(self, source, date, expected):
        self.tickler.write_text(source)
        result = self.run_writer(date)
        self.assertEqual(result.returncode, 0, result.stderr)
        if expected.endswith(ITEM + "\n"):
            expected += "\n"  # Retained Lane4 terminal blank convention.
        self.assertEqual(self.tickler.read_text(), expected)
        self.assertEqual(result.stdout, f"Tickler item added: {date}\n")

    def test_insert_before(self):
        for gap in ("", "\n", "\n\n", " \t\n\n"):
            with self.subTest(gap=repr(gap)):
                self.check_write(
                    PREFIX + gap + EARLY + "\n" + LATE + "\n\n",
                    "2030-01-01",
                    PREFIX + "\n## 2030-01-01\n" + ITEM + "\n\n"
                    + EARLY + "\n" + LATE + "\n\n",
                )

    def test_insert_between(self):
        for gap in ("", "\n", "\n\n", " \t\n\n"):
            with self.subTest(gap=repr(gap)):
                self.check_write(
                    PREFIX + "\n" + EARLY + gap + LATE,
                    "2030-01-20",
                    PREFIX + "\n" + EARLY + "\n## 2030-01-20\n"
                    + ITEM + "\n\n" + LATE,
                )

    def test_insert_after(self):
        for gap in ("", "\n", "\n\n", " \t\n\n"):
            with self.subTest(gap=repr(gap)):
                self.check_write(
                    PREFIX + "\n" + EARLY + "\n" + LATE + gap,
                    "2030-02-01",
                    PREFIX + "\n" + EARLY + "\n" + LATE
                    + "\n## 2030-02-01\n" + ITEM + "\n",
                )

    def test_existing_date_positive_control_preserves_spacing(self):
        source = PREFIX + "\n\n" + EARLY + "\n\n" + LATE + "\n\n"
        self.check_write(
            source, "2030-01-10",
            source.replace("## 2030-01-10\n", "## 2030-01-10\n" + ITEM + "\n"),
        )

    def test_invalid_date_failure_leaves_file_unchanged(self):
        source = PREFIX + "\n" + EARLY + "\n\n" + LATE
        self.tickler.write_text(source)
        result = self.run_writer("2030/01/20")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Date must be YYYY-MM-DD", result.stdout)
        self.assertEqual(self.tickler.read_text(), source)
        self.assertFalse(Path(str(self.tickler) + ".tmp").exists())

    def test_first_date_after_divider(self):
        self.check_write(
            PREFIX + "\n\n", "2030-01-20",
            PREFIX + "\n## 2030-01-20\n" + ITEM + "\n",
        )

    def test_new_file_template(self):
        result = self.run_writer("2030-01-20")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.tickler.read_text()
        self.assertTrue(text.startswith("# Tickler\n"))
        self.assertTrue(text.endswith("\n---\n\n## 2030-01-20\n" + ITEM + "\n\n"))
        self.assertNotIn("---\n\n\n##", text)

    def test_append_without_final_newline(self):
        self.check_write(
            PREFIX + "\n" + EARLY.rstrip("\n"), "2030-02-01",
            PREFIX + "\n" + EARLY + "\n## 2030-02-01\n" + ITEM + "\n",
        )


if __name__ == "__main__":
    unittest.main()
