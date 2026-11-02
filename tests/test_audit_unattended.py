import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class AuditUnattendedTests(unittest.TestCase):
    def test_contract_limits_and_scratch_location(self) -> None:
        for rel in (".claude/commands/audit.md", "codex/skills/audit/SKILL.md"):
            with self.subTest(render=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                section = text.split("## Unattended runs", 1)[1].split("## Instructions", 1)[0]
                self.assertIn("`review_rounds`", section)
                self.assertIn("after-fixes candidate, unreviewed", section)
                self.assertIn("`extra_paid_budget`", section)
                self.assertIn("Grok skipped: paid budget 0", section)
                self.assertIn('TMPDIR="<run state dir>" mktemp', section)
                self.assertIn("an interactive audit ignores this section", section)
                self.assertIn("default `~/.local/state/<run-id>/`", section)
                loop = text.split("### Phase 4: Fix and Re-audit", 1)[1]
                self.assertRegex(loop, r"unattended run the contract's `review_rounds` ends the loop")


if __name__ == "__main__":
    unittest.main()
