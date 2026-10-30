"""Isolated regression controls for session helper boundaries and added modes."""
import os
import json
import shutil
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session

SCRIPTS = Path(__file__).parents[1] / ".claude/scripts"


class SessionHelperBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / "log.md"
        self.env = isolate_session(os.environ.copy(), self.root / "state", "boundary-fixture")
        self.env["VAULT_PATH"] = str(self.root)
        self.env["HOME"] = str(self.root / "home")

    def run_helper(self, helper, *args, body=""):
        return subprocess.run(
            ["bash", str(SCRIPTS / helper), str(self.log), *args],
            input=body, capture_output=True, text=True, env=self.env, timeout=20)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_replace_unterminated_terminal_section_removes_old_last_record(self):
        self.log.write_text("## Session 1 - Fixture\n### Pickup Context\n"
                            "**For next session:** Old\n**Project:** Old")
        self.log.chmod(0o640)
        result = self.run_helper("update-session-section.sh", "1", "Pickup Context", "--replace",
                                 body="**For next session:** New\n**Project:** None\n")
        self.assert_ok(result)
        after = self.log.read_text()
        self.assertEqual(after.count("**Project:**"), 1)
        self.assertNotIn("Old", after)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o640)

    def test_replace_without_blank_before_next_heading_removes_whole_body(self):
        self.log.write_text("## Session 1 - Fixture\n### Summary\nOld last record\n"
                            "### Pickup Context\n**Project:** None\n")
        result = self.run_helper("update-session-section.sh", "1", "Summary", "--replace",
                                 body="Replacement\n")
        self.assert_ok(result)
        self.assertNotIn("Old last record", self.log.read_text())
        self.assertEqual(self.log.read_text().count("### Pickup Context"), 1)

    def test_append_to_empty_section_does_not_cross_pickup_heading(self):
        self.log.write_text("## Session 1 - Fixture\n### Files Updated\n"
                            "### Pickup Context\n**Project:** None\n")
        result = self.run_helper("update-session-section.sh", "1", "Files Updated",
                                 body="`Notes/Plan - draft.md` - changed\n")
        self.assert_ok(result)
        after = self.log.read_text()
        self.assertLess(after.index("`Notes/Plan - draft.md`"), after.index("### Pickup Context"))

    def test_missing_file_sections_are_inserted_only_inside_selected_session(self):
        first = "## Session 1 - First\n### Summary\nFirst\n### Pickup Context\n**Project:** None\n"
        later = "## Session 10 - Later\n### Summary\nLater\n### Pickup Context\n**Project:** None\n"
        for section in ("Files Created", "Files Updated", "Files Deleted"):
            with self.subTest(section=section):
                self.log.write_text(first + later)
                result = self.run_helper("update-session-section.sh", "1", section,
                                         body="`Notes/Plan - draft.md` - changed\n")
                self.assert_ok(result)
                before_later, after_later = self.log.read_text().split("## Session 10", 1)
                self.assertLess(before_later.index("### " + section), before_later.index("### Pickup Context"))
                self.assertEqual("## Session 10" + after_later, later)
                self.assertEqual(before_later.count("### " + section), 1)

    def test_missing_file_section_without_pickup_fails_without_mutating(self):
        original = "## Session 1 - Fixture\n### Summary\nOriginal\n"
        self.log.write_text(original)
        result = self.run_helper("update-session-section.sh", "1", "Files Deleted", body="old.md - gone\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.log.read_text(), original)

    def test_rename_heading_is_exact_and_preserves_other_bytes_and_mode(self):
        original = ("## Session 1 - Old (10:20am)\n### Summary\nFirst\n"
                    "## Session 10 - Other (10:30am)\n### Summary\nFinal without newline")
        self.log.write_text(original)
        self.log.chmod(0o640)
        result = self.run_helper("update-session-section.sh", "--rename-heading", "1",
                                 "## Session 1 - Revised (10:20am)")
        self.assert_ok(result)
        self.assertEqual(self.log.read_text(), original.replace("## Session 1 - Old", "## Session 1 - Revised"))
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o640)
        ledger = self.root / "state/.session-state/boundary-fixture.tsv"
        self.assertEqual(len(ledger.read_text().splitlines()), 1)
        self.assert_ok(self.run_helper("update-session-section.sh", "--rename-heading", "1",
                                      "## Session 1 - Revised (10:20am)"))
        self.assertEqual(len(ledger.read_text().splitlines()), 1)

    def test_rename_heading_rejects_wrong_session_and_multiline_before_mutation(self):
        original = "## Session 1 - Old\n### Summary\nKeep\n"
        for heading in ("## Session 10 - Wrong", "## Session 1 - First\n## Session 2 - Injected"):
            with self.subTest(heading=heading):
                self.log.write_text(original)
                result = self.run_helper("update-session-section.sh", "--rename-heading", "1", heading)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.log.read_text(), original)

    def test_rename_heading_does_not_wait_for_stdin_to_close(self):
        self.log.write_text("## Session 1 - Old\n### Summary\nKeep\n")
        proc = subprocess.Popen(["bash", str(SCRIPTS / "update-session-section.sh"), str(self.log),
                                 "--rename-heading", "1", "## Session 1 - Renamed"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=self.env)
        try:
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stdin.close()
        stdout, stderr = proc.stdout.read(), proc.stderr.read()
        proc.stdout.close(); proc.stderr.close()
        self.assertEqual(proc.returncode, 0, stdout + stderr)

    def test_created_backfill_creates_section_and_preserves_existing_updated_row(self):
        original = ("## Session 1 - Fixture\n### Files Updated\n- old.md - existing\n"
                    "### Pickup Context\n**Project:** None\n"
                    "## Session 10 - Other\n### Files Created\n- later.md - unrelated\n")
        self.log.write_text(original)
        result = self.run_helper("backfill-files-updated.sh", "1", "--section", "Files Created",
                                 body="`Notes/Plan - draft.md` - new\nold.md - duplicate\n")
        self.assert_ok(result)
        first, rest = self.log.read_text().split("## Session 10", 1)
        self.assertIn("### Files Created\n- `Notes/Plan - draft.md` - new\n", first)
        self.assertEqual(first.count("- old.md"), 1)
        self.assertNotIn("old.md - duplicate", first)
        self.assertTrue(result.stdout.endswith("1 added, 1 skipped\n"), result.stdout)
        self.assertEqual("## Session 10" + rest, "## Session 10" + original.split("## Session 10", 1)[1])

    def test_default_backfill_can_create_missing_updated_section(self):
        self.log.write_text("## Session 1 - Fixture\n### Pickup Context\n**Project:** None")
        result = self.run_helper("backfill-files-updated.sh", "1", body="fresh.md - updated\n")
        self.assert_ok(result)
        after = self.log.read_text()
        self.assertLess(after.index("### Files Updated"), after.index("### Pickup Context"))
        self.assertIn("- fresh.md - updated", after)

    def test_deleted_backfill_mode_uses_deleted_section(self):
        self.log.write_text("## Session 1 - Fixture\n### Pickup Context\n**Project:** None\n")
        result = self.run_helper("backfill-files-updated.sh", "1", "--section", "Files Deleted",
                                 body="`Notes/Plan - old.md` - removed\n")
        self.assert_ok(result)
        self.assertIn("### Files Deleted\n- `Notes/Plan - old.md` - removed\n", self.log.read_text())
        self.assertNotIn("### Files Updated", self.log.read_text())

    @unittest.skipIf(sys.platform == "win32", "POSIX PATH fixture uses executable symlinks")
    def test_python_alias_only_supports_forward_proof_and_heading_rename(self):
        bin_dir = self.root / "alias-bin"
        bin_dir.mkdir()
        for name in ("bash", "env", "dirname", "basename", "grep", "sed", "awk", "head",
                     "tail", "wc", "flock", "mktemp", "cp", "mv", "chmod", "rm", "mkdir",
                     "date", "tr", "stat", "cat", "sort", "sleep", "uname", "id", "find",
                     "touch", "cut", "realpath", "readlink", "sha256sum"):
            executable = shutil.which(name)
            if executable:
                (bin_dir / name).symlink_to(executable)
        (bin_dir / "python").symlink_to(sys.executable)
        vault = self.root / "alias-vault"
        vault.mkdir()
        environment = dict(self.env, PATH=str(bin_dir), VAULT_PATH=str(vault))
        source = vault / "2001-01-01.md"
        source.write_text("## Session 1 - Original\n### Summary\nSaved\n"
                          "### Pickup Context\n**Project:** None\n")
        target = vault / "2001-01-02.md"
        target.write_text("## Session 2 - Later\n### Summary\nLater\n")
        result = subprocess.run(["bash", str(SCRIPTS / "add-forward-link.sh"), "--continued-in",
                                 str(source), "1", "2", "Later", target.name],
                                env=environment, capture_output=True, text=True, timeout=20)
        self.assert_ok(result)
        self.assertIn("**Continued in:**", source.read_text())
        receipts = [p for p in (self.root / "state").rglob("*.json")
                    if json.loads(p.read_text()).get("kind") == "forward-link"]
        self.assertEqual(len(receipts), 1)
        proof = subprocess.run(["bash", str(SCRIPTS / "add-forward-link.sh"), "--verify-receipt",
                                str(receipts[0]), str(source)], env=environment,
                               capture_output=True, text=True, timeout=20)
        self.assert_ok(proof)
        renamed = subprocess.run(["bash", str(SCRIPTS / "update-session-section.sh"), str(source),
                                  "--rename-heading", "1", "## Session 1 - Renamed"],
                                 env=environment, capture_output=True, text=True, timeout=20)
        self.assert_ok(renamed)
        self.assertTrue(source.read_text().startswith("## Session 1 - Renamed\n"))

    def test_concurrent_section_and_backfill_writers_preserve_session_boundaries(self):
        self.log.write_text("## Session 1 - First\n### Summary\nStart\n"
                            "### Pickup Context\n**Project:** None\n"
                            "## Session 10 - Later\n### Pickup Context\n**Project:** None\n")
        jobs = []
        for index in range(5):
            for helper, args, body in (
                ("update-session-section.sh", ["1", "Summary"], f"delta-{index}\n"),
                ("backfill-files-updated.sh", ["10", "--section", "Files Created"], f"file-{index}.md - new\n"),
            ):
                proc = subprocess.Popen(["bash", str(SCRIPTS / helper), str(self.log), *args],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, env=self.env)
                proc.stdin.write(body); proc.stdin.close()
                jobs.append(proc)
        for proc in jobs:
            proc.wait(timeout=20)
            stdout, stderr = proc.stdout.read(), proc.stderr.read()
            proc.stdout.close(); proc.stderr.close()
            self.assertEqual(proc.returncode, 0, stdout + stderr)
        first, later = self.log.read_text().split("## Session 10", 1)
        for index in range(5):
            self.assertEqual(first.count(f"delta-{index}"), 1)
            self.assertNotIn(f"file-{index}.md", first)
            self.assertEqual(later.count(f"file-{index}.md"), 1)
            self.assertNotIn(f"delta-{index}", later)


if __name__ == "__main__":
    unittest.main()
