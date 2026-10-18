import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CLAUDE = ROOT / ".claude/commands/park.md"
CODEX = ROOT / "codex/skills/park/SKILL.md"

LEDGER = "**Check / Missing ledger.**"
RULE = "**Check / Missing lines:**"
OMIT = "Omit either heading entirely when it has no items; never write `none`."
NO_FABRICATE = "never invent the missing value"
NO_MIDRUN_ASK = "do not stop the run to ask"
QUICK_LINE = "[Check: / Missing: lines per Step 12 — omitted when empty]"


def section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin + len(start))]


class ParkCheckMissingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.renderings = {
            "claude": CLAUDE.read_text(encoding="utf-8"),
            "codex": CODEX.read_text(encoding="utf-8"),
        }

    def test_full_completion_carries_conditional_check_and_missing(self) -> None:
        for lane, text in self.renderings.items():
            with self.subTest(lane=lane):
                step12 = text[text.index("### 12. Full-path completion message") :]
                self.assertIn("Check: ", step12)
                self.assertIn("Missing: ", step12)
                self.assertIn(RULE, step12)
                self.assertIn(OMIT, step12)
                # Lines sit before the closing word, not after the summary.
                self.assertLess(step12.index("Missing: "), step12.index("Parked."))

    def test_setup_collects_without_blocking_or_fabricating(self) -> None:
        for lane, text in self.renderings.items():
            with self.subTest(lane=lane):
                setup = section(text, "### 0. Setup", "### 1. Merge-continuation check")
                self.assertIn(LEDGER, setup)
                self.assertIn(NO_FABRICATE, setup)
                self.assertIn(NO_MIDRUN_ASK, setup)

    def test_quick_completion_mirrors_conditional_lines(self) -> None:
        for lane, text in self.renderings.items():
            with self.subTest(lane=lane):
                quick = section(text, "#### Quick success path", "Quick parked.")
                self.assertIn(QUICK_LINE, quick)

    def test_rule_text_is_identical_across_harnesses(self) -> None:
        def rule_paragraph(text: str) -> str:
            start = text.index(RULE)
            return text[start : text.index("\n", start)]

        self.assertEqual(
            rule_paragraph(self.renderings["claude"]),
            rule_paragraph(self.renderings["codex"]),
        )


if __name__ == "__main__":
    unittest.main()
