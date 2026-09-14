import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from session_isolation import isolated_os_environ


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/write-tickler.sh"


class WriteTicklerTests(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.TemporaryDirectory()
        self.addCleanup(self.state.cleanup)
        self.enterContext(isolated_os_environ(Path(self.state.name), "writer-fixture"))

    def run_writer(self, body: str, date: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Tickler.md"
            target.write_text(body, encoding="utf-8")
            subprocess.run(
                [str(SCRIPT), str(target), date, "- [ ] fixture"],
                check=True,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            return target.read_text(encoding="utf-8")

    def test_middle_insert_normalises_both_section_seams(self) -> None:
        result = self.run_writer(
            "# Tickler\n\n---\n\n## 2026-08-01\n- [ ] earlier\n\n\n"
            "## 2026-08-03\n- [ ] later\n",
            "2026-08-02",
        )
        self.assertIn(
            "- [ ] earlier\n\n## 2026-08-02\n- [ ] fixture\n\n## 2026-08-03",
            result,
        )

    def test_tail_insert_has_one_blank_before_and_after(self) -> None:
        result = self.run_writer(
            "# Tickler\n\n---\n\n## 2026-08-01\n- [ ] earlier\n\n\n",
            "2026-08-02",
        )
        self.assertTrue(
            result.endswith("- [ ] earlier\n\n## 2026-08-02\n- [ ] fixture\n\n"),
            result,
        )


if __name__ == "__main__":
    unittest.main()
