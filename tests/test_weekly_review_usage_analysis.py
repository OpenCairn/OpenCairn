import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
RENDERS = (
    ".claude/commands/weekly-review.md",
    "codex/skills/weekly-review/SKILL.md",
)
KEY = "**Usage analysis notes:**"


class WeeklyReviewUsageAnalysisTests(unittest.TestCase):
    def test_step_two_reads_an_opt_in_usage_analysis_note(self) -> None:
        for rel in RENDERS:
            with self.subTest(render=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                match = re.search(r"^   \*\*Usage analysis \(optional\):\*\*\n(?:   - .*\n)+", text, re.M)
                self.assertIsNotNone(match, "no usage-analysis input in step 2")
                section = match.group(0)
                self.assertIn("Off by default.", section)
                self.assertIn(f"rg --no-config -F '{KEY}'", section)
                self.assertIn("no backticked value means the input is not configured: skip it silently", section)
                self.assertIn("LC_ALL=C sort -r", section)
                self.assertIn("`## Top candidates`", section)
                self.assertIn("`repeated-work` or `delegation`", section)
                # Producer-agnostic: no default glob naming a tool the template does not ship.
                self.assertNotIn("default", section.replace("Off by default", ""))
                self.assertNotRegex(section, r"`[^`]*-W\[0-9\]")

    def test_attention_and_friction_quotes_candidates_with_link(self) -> None:
        for rel in RENDERS:
            with self.subTest(render=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                match = re.search(r"^## Attention & Friction\n(.*?)(?=^## )", text, re.M | re.S)
                self.assertIsNotNone(match)
                block = match.group(1)
                self.assertIn("**Usage analysis** ([[<note basename>]])", block)
                self.assertIn('"<title>"', block)
                self.assertIn("otherwise omit this line", block)

    def test_template_key_is_off_by_default(self) -> None:
        path = ROOT / "07 System/Vault Organisation Principles.md"
        result = subprocess.run(["rg", "--no-config", "-F", KEY, str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        # The skill takes the first backticked value on the matched line; none means off.
        self.assertIsNone(re.search(r"`([^`]+)`", lines[0]))
        self.assertIn("off — no glob set", lines[0])


if __name__ == "__main__":
    unittest.main()
