import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
RENDERS = (
    ".claude/commands/weekly-hygiene.md",
    "codex/skills/weekly-hygiene/SKILL.md",
    ".claude/commands/weekly-review.md",
    "codex/skills/weekly-review/SKILL.md",
)


class WeeklyUnattendedModeTests(unittest.TestCase):
    def test_unattended_section_names_contract_state_dir_and_date(self) -> None:
        for rel in RENDERS:
            with self.subTest(render=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                match = re.search(r"^\*\*Unattended mode\*\*.*?(?=\n\n(?!- ))", text, re.S | re.M)
                self.assertIsNotNone(match, "no Unattended mode section")
                section = match.group(0)
                self.assertIn("contract template", section)
                self.assertIn("only when the user explicitly asks", section)
                self.assertIn("$OPENCAIRN_RUN_STATE/<run-id>/", section)
                self.assertIn("default `~/.local/state/<run-id>/`", section)
                self.assertIn('date +"%a %d %b %H:%M %Z"', section)
                self.assertIsNone(re.search(r"good (morning|evening|night)", text, re.I))


if __name__ == "__main__":
    unittest.main()
