"""Synthetic Files-list parser regressions; never use a live vault or config."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / ".claude/scripts/park-verify.sh"


class VerifyPathsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="verify-paths-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.config = self.root / "config"
        self.config.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = {
            "PATH": os.defpath,
            "HOME": str(self.home),
            "CLAUDE_CONFIG_DIR": str(self.config),
            "OPENCAIRN_SESSION_ID": "synthetic-verify-paths",
        }

    def create(self, path):
        target = self.vault / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Synthetic fixture.\n", encoding="utf-8")
        return target

    def verify(self, rows, touched=(), section="Updated"):
        lists = {"Created": "- None", "Updated": "- None", "Deleted": "- None"}
        lists[section] = "\n".join("- " + row for row in rows)
        log = self.vault / "sessions.md"
        log.write_text(
            "## Session 900001 - synthetic\n"
            "### Summary\nSynthetic parser check.\n"
            + "".join(f"### Files {name}\n{body}\n" for name, body in lists.items())
            + "### Pickup Context\n**Project:** Synthetic\n",
            encoding="utf-8",
        )
        args = ["bash", str(HELPER), str(self.vault), str(log), "900001"]
        for path in touched:
            args.extend(["--touched", path])
        result = subprocess.run(
            args, env=self.env, cwd=self.root, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
        )
        self.assertEqual(result.stderr, "")
        return result

    def assert_uncovered(self, result, path):
        self.assertEqual(result.returncode, 0, result.stdout)
        reviews = [line for line in result.stdout.splitlines() if line.startswith("REVIEW backfill:")]
        self.assertEqual(len(reviews), 1, result.stdout)
        self.assertTrue(reviews[0].endswith(": " + path + "; "), reviews[0])
        self.assertIn("RESULT: REVIEW", result.stdout)

    def test_existing_paths_only_separator_is_not_truncated(self):
        path = "03 Projects/Report - draft - final.md"
        self.create(path)
        # A shorter existing candidate must not win over the full filename.
        self.create("03 Projects/Report")
        for section in ("Created", "Updated", "Deleted"):
            with self.subTest(section=section):
                self.assert_uncovered(self.verify([path], section=section), path)

    def test_legacy_description_preserves_longest_existing_filename(self):
        path = "03 Projects/Report - draft - final.md"
        self.create(path)
        self.create("03 Projects/Report")
        self.assert_uncovered(self.verify([path + " - updated - synthetic detail"]), path)

    def test_valid_plain_and_wiki_paths_positive_controls(self):
        for path in ("03 Projects/Plain.md", "03 Projects/Report - draft.md"):
            self.create(path)
            for row in (path, path + " - updated", "[[" + path + "]]",
                        "[[" + path + "]] - updated", "[[" + path + "|label]] - updated"):
                with self.subTest(row=row):
                    result = self.verify([row], touched=[path])
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertIn("RESULT: PASS", result.stdout)
                    self.assert_uncovered(self.verify([row]), path)

    def test_missing_path_is_still_reported(self):
        path = "03 Projects/Missing.md"
        self.assert_uncovered(self.verify([path]), path)
        self.assert_uncovered(self.verify([path + " - legacy detail"]), path)
        wiki_path = "03 Projects/Missing - draft.md"
        self.assert_uncovered(self.verify(["[[" + wiki_path + "]] - detail"]), wiki_path)

    def test_missing_backfill_still_fails(self):
        path = "03 Projects/Unlisted - draft.md"
        self.create(path)
        result = self.verify(["03 Projects/Missing.md"], touched=[path])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL backfill: touched but absent", result.stdout)
        self.assertIn(path, result.stdout)
        self.assertIn("RESULT: FAIL", result.stdout)

    def test_absolute_relative_and_home_paths(self):
        path = "03 Projects/Report - draft.md"
        absolute = self.create(path)
        home_path = self.home / "Report - draft.md"
        home_path.write_text("Synthetic fixture.\n", encoding="utf-8")
        for row in (str(absolute), "./" + path, "~/Report - draft.md"):
            with self.subTest(row=row):
                self.assert_uncovered(self.verify([row + " - detail"]), row)

    def test_indented_row_still_requires_coverage(self):
        path = "03 Projects/Indented - record.md"
        self.create(path)
        # verify() supplies '- '; insert indentation in the raw row to exercise tolerance.
        result = self.verify([path])
        log = self.vault / "sessions.md"
        log.write_text(log.read_text().replace("- " + path, "  - " + path))
        result = subprocess.run(["bash", str(HELPER), str(self.vault), str(log), "900001"],
                                env=self.env, cwd=self.root, text=True, capture_output=True)
        self.assert_uncovered(result, path)

    def test_none_remains_empty(self):
        for row in ("None", "none - no files changed"):
            with self.subTest(row=row):
                result = self.verify([row])
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("RESULT: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
