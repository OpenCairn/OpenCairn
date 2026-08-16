import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/park-verify.sh"


class ParkVerifyTests(unittest.TestCase):
    def test_root_path_none_and_session_log_reverse_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "01 Now").mkdir(parents=True)
            (vault / "01 Now/This Week.md").write_text("# This Week\n", encoding="utf-8")
            (vault / "01 Now/Tickler.md").write_text("# Tickler\n", encoding="utf-8")
            log = vault / "06 Archive/OpenCairn/Session Logs/2026-08-16.md"
            log.parent.mkdir(parents=True)

            with tempfile.NamedTemporaryFile(
                dir="/tmp", prefix="opencairn-park-verify-", delete=False
            ) as handle:
                root_file = Path(handle.name)
            self.addCleanup(root_file.unlink, missing_ok=True)

            relative_log = log.relative_to(vault)
            log.write_text(
                "\n".join(
                    [
                        "## Session 1 - Test",
                        "### Summary",
                        "Done.",
                        "### Files Created",
                        "- None",
                        "### Files Updated",
                        f"- {root_file} - root-level artefact",
                        f"- {relative_log} - session record",
                        "### Pickup Context",
                        "**For next session:** None",
                        "**Project:** None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(SCRIPT),
                    str(vault),
                    str(log),
                    "1",
                    "--touched",
                    str(root_file),
                    "--touched",
                    str(log),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RESULT: PASS", result.stdout)
            self.assertNotIn("//tmp/", result.stdout)
            self.assertNotIn("--touched None", result.stdout)


if __name__ == "__main__":
    unittest.main()
