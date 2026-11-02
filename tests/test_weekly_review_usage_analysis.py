import re
import shutil
import subprocess
import tempfile
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
                self.assertNotRegex(section, r"-g '(?!<glob>')")
                self.assertIn("already links `[[<note basename>]]`", section)
                self.assertNotIn("ISO week of `PERIOD_START`", section)
                self.assertIn("usage analysis configured; no unquoted note matched", section)

    def test_attention_and_friction_quotes_candidates_with_link(self) -> None:
        for rel in RENDERS:
            with self.subTest(render=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                match = re.search(r"^## Attention & Friction\n(.*?)(?=^## )", text, re.M | re.S)
                self.assertIsNotNone(match)
                block = match.group(1)
                self.assertIn("**Usage analysis** ([[<note basename>]])", block)
                self.assertIn('"<title>"', block)
                self.assertIn("up to three", block)
                self.assertIn("otherwise omit this line", block)

    @unittest.skipIf(shutil.which("rg") is None, "rg not installed")
    def test_latest_note_selection_runs(self) -> None:
        text = (ROOT / RENDERS[0]).read_text(encoding="utf-8")
        cmd = re.search(r"in one call, `([^`]+)`", text).group(1)
        with tempfile.TemporaryDirectory() as vault:
            v = Path(vault)
            for rel in ("a/Usage analysis - 2026-W44.md", "b/Usage analysis - 2026-W45.md", "Usage analysis - setup.md"):
                (v / rel).parent.mkdir(parents=True, exist_ok=True)
                (v / rel).write_text("x", encoding="utf-8")
            def run(glob: str) -> str:
                script = cmd.replace("{VAULT}", vault).replace("<glob>", glob)
                return subprocess.run(["bash", "-c", script], capture_output=True, text=True).stdout
            out = run("Usage analysis*.md")
            self.assertIn("rg=0", out)
            self.assertTrue(out.strip().endswith("b/Usage analysis - 2026-W45.md"), out)
            self.assertIn("rg=1", run("Nothing here*.md"))

    @unittest.skipIf(shutil.which("rg") is None, "rg not installed")
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
