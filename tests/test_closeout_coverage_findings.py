import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class CloseoutCoverageFindingTests(unittest.TestCase):
    def test_coverage_finding_needs_a_cited_rerun_search(self) -> None:
        for rel in (".claude/commands/_closeout.md", "codex/skills/_closeout.md"):
            with self.subTest(render=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("**A coverage finding is closed by a re-run search, not by rewording.**", text)
                self.assertIn("would have caught the miss the finding names", text)
                self.assertIn("cite its argv and output", text)


if __name__ == "__main__":
    unittest.main()
