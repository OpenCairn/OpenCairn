import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/locked-edit.sh"
SESSION = "locked-edit-delete-section-test"

try:
    from session_isolation import isolate_session
except ImportError:  # `python -m unittest tests.<module>` from the repo root
    from tests.session_isolation import isolate_session


MONDAY = (
    "## Mon 1 — Deep work\n"
    "\n"
    "- [x] first item\n"
    "- [x] second item\n"
    "\n"
    "### Evening\n"
    "\n"
    "```bash\n"
    "# a comment, not a heading\n"
    "## Tue 2 — Errands\n"
    "```\n"
    "- [x] third item\n"
)
PLAN = (
    "# This Week\n"
    "\n"
    "Intro line.\n"
    "\n"
    + MONDAY
    + "\n"
    "## Tue 2 — Errands\n"
    "\n"
    "- [ ] fourth item\n"
)


class LockedEditDeleteSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.config = self.root / "config"
        self.target = self.vault / "This Week.md"
        self.target.write_text(PLAN, encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def environment(self) -> dict[str, str]:
        environment = isolate_session(os.environ.copy(), self.config, SESSION)
        environment["VAULT_PATH"] = str(self.vault)
        return environment

    def run_show(self, heading: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), str(self.target), "--show-section", heading],
            stdin=subprocess.DEVNULL,
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

    def section_sha(self, heading: str) -> str:
        """The hash a caller holds after reading the section, or a dummy one."""
        shown = self.run_show(heading)
        if shown.returncode != 0:
            return "0" * 64
        return shown.stderr.strip().rsplit(" ", 1)[-1]

    def run_delete(
        self, heading: str, replacement: str = "", sha: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        if sha is None:
            sha = self.section_sha(heading)
        return subprocess.run(
            [str(SCRIPT), str(self.target), "--delete-section", heading, sha],
            input=replacement,
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

    def text(self) -> str:
        return self.target.read_text(encoding="utf-8")

    def test_collapses_a_section_to_the_replacement_and_prints_the_removed_block(self) -> None:
        summary = "## Mon 1 — Deep work ✅\nShipped the draft. [[Reports/Mon|Full report]]\n"

        result = self.run_delete("## Mon 1 — Deep work", summary)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.text(),
            "# This Week\n\nIntro line.\n\n"
            + summary
            + "\n## Tue 2 — Errands\n\n- [ ] fourth item\n",
        )
        self.assertEqual(result.stdout, MONDAY + "\n")
        self.assertIn("Locked edit applied", result.stderr)

    def test_empty_stdin_deletes_the_section_and_its_trailing_blank_lines(self) -> None:
        result = self.run_delete("## Mon 1 — Deep work")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.text(),
            "# This Week\n\nIntro line.\n\n## Tue 2 — Errands\n\n- [ ] fourth item\n",
        )
        self.assertEqual(result.stdout, MONDAY + "\n")

    def test_section_runs_to_end_of_file(self) -> None:
        result = self.run_delete("## Tue 2 — Errands", "## Tue 2 — Errands ✅\nDone.")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.text(),
            "# This Week\n\nIntro line.\n\n" + MONDAY + "\n## Tue 2 — Errands ✅\nDone.\n",
        )
        self.assertEqual(result.stdout, "## Tue 2 — Errands\n\n- [ ] fourth item\n")

    def test_subsection_ends_at_a_higher_level_heading(self) -> None:
        self.target.write_text(
            "## Day\n\n### Morning\n- a\n\n#### Detail\n- b\n\n## Next\n- c\n",
            encoding="utf-8",
        )

        result = self.run_delete("### Morning")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.text(), "## Day\n\n## Next\n- c\n")
        self.assertEqual(result.stdout, "### Morning\n- a\n\n#### Detail\n- b\n\n")

    def test_writes_a_replace_shaped_receipt_and_one_ledger_row(self) -> None:
        summary = "## Mon 1 — Deep work ✅\nDone.\n"

        result = self.run_delete("## Mon 1 — Deep work", summary)

        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.config / ".session-state"
        rows = (state / f"{SESSION}.tsv").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1)
        self.assertIn("\tlocked-edit\t", rows[0])
        receipts = list((state / f"{SESSION}.locked-edit-receipts").iterdir())
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual(receipt["mode"], "--replace")
        self.assertEqual(receipt["invoked_mode"], "--delete-section")
        self.assertEqual(receipt["old_text"], MONDAY)
        self.assertEqual(receipt["new_text"], summary)
        self.assertEqual(
            receipt["pre_sha256"], hashlib.sha256(PLAN.encode("utf-8")).hexdigest()
        )
        self.assertEqual(
            receipt["post_sha256"], hashlib.sha256(self.target.read_bytes()).hexdigest()
        )
        self.assertEqual(receipt["changed_ranges"][0]["before_start"], 5)
        self.assertEqual(receipt["changed_ranges"][0]["before_end"], 16)

    def test_missing_heading_leaves_file_untouched(self) -> None:
        for heading in ("## Wed 3 — Absent", "## Mon 1", "## Mon 1 — Deep work "):
            with self.subTest(heading=heading):
                result = self.run_delete(heading, "replacement\n")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.text(), PLAN)
                self.assertEqual(result.stdout, "")

    def test_heading_inside_a_code_fence_is_not_a_section(self) -> None:
        self.target.write_text("# Top\n\n```\n## Fenced\n```\n", encoding="utf-8")

        result = self.run_delete("## Fenced")

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.text(), "# Top\n\n```\n## Fenced\n```\n")

    def test_fence_still_open_at_end_of_file_writes_nothing(self) -> None:
        # A line opening with three backticks and never closed would otherwise
        # hide every later heading and stretch the section to end of file.
        week = (
            "# This Week\n\n"
            "## Mon 1\n- [x] ran it\n```inline``` is how you quote\n\n"
            "## Tue 2\n- [ ] keep tuesday\n\n"
            "## Wed 3\n- [ ] keep wednesday\n"
        )
        self.target.write_text(week, encoding="utf-8")

        shown = self.run_show("## Mon 1")
        result = self.run_delete("## Mon 1", "## Mon 1 ✅\nDone.\n")

        self.assertEqual(shown.returncode, 2, shown.stderr)
        self.assertEqual(shown.stdout, "")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("code fence", result.stderr)
        self.assertEqual(self.text(), week)
        self.assertEqual(result.stdout, "")

    def test_duplicate_heading_is_ambiguous(self) -> None:
        duplicated = PLAN + "\n## Mon 1 — Deep work\n- again\n"
        self.target.write_text(duplicated, encoding="utf-8")

        result = self.run_delete("## Mon 1 — Deep work")

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(self.text(), duplicated)
        self.assertEqual(result.stdout, "")

    def test_rejects_arguments_that_are_not_one_heading_line(self) -> None:
        for heading in ("Mon 1 — Deep work", "##Mon", "## Mon\n## Tue", "####### Seven", ""):
            with self.subTest(heading=heading):
                result = self.run_delete(heading)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(self.text(), PLAN)

    def test_requires_the_heading_and_the_section_hash(self) -> None:
        for arguments in ([], ["## Mon 1 — Deep work"], ["## Mon 1 — Deep work", "not-a-hash"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [str(SCRIPT), str(self.target), "--delete-section", *arguments],
                    input="replacement\n",
                    check=False,
                    capture_output=True,
                    text=True,
                    env=self.environment(),
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(self.text(), PLAN)

    def test_show_section_prints_the_section_and_its_hash_without_writing(self) -> None:
        result = self.run_show("## Mon 1 — Deep work")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, MONDAY + "\n")
        digest = hashlib.sha256((MONDAY + "\n").encode("utf-8")).hexdigest()
        self.assertEqual(result.stderr.strip(), f"Section sha256: {digest}")
        self.assertEqual(self.text(), PLAN)
        self.assertFalse((self.config / ".session-state").exists())

    def test_line_added_by_another_writer_after_the_read_blocks_the_collapse(self) -> None:
        sha = self.section_sha("## Mon 1 — Deep work")
        changed = PLAN.replace("- [x] third item\n", "- [x] third item\n- [x] added by another writer\n")
        self.target.write_text(changed, encoding="utf-8")

        result = self.run_delete("## Mon 1 — Deep work", "## Mon 1 — Deep work ✅\nDone.\n", sha)

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("changed", result.stderr)
        self.assertEqual(self.text(), changed)
        self.assertIn("- [x] added by another writer\n", self.text())
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
