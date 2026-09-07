import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

from tests.test_locked_edit_move import MOCK_OBSIDIAN


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/set-project-status.py"
PARK_REVIEW = Path(__file__).parents[1] / "codex/skills/park/scripts/park-review.py"


class SetProjectStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault = self.root / "vault"
        for folder in (
            "01 Now",
            "03 Projects",
            "04 Areas/Example",
            "06 Archive/OpenCairn/Session Logs",
            "07 System",
        ):
            (self.vault / folder).mkdir(parents=True, exist_ok=True)
        (self.vault / "07 System/Vault Organisation Principles.md").write_text(
            "**Active project cap: 5**\n", encoding="utf-8"
        )
        self.obsidian = self.root / "obsidian"
        self.obsidian.write_text(textwrap.dedent(MOCK_OBSIDIAN), encoding="utf-8")
        self.obsidian.chmod(0o755)
        self.config = self.root / "config"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def environment(self) -> dict[str, str]:
        return {
            **os.environ,
            "VAULT_PATH": str(self.vault),
            "OBSIDIAN_CLI": str(self.obsidian),
            "CLAUDE_CONFIG_DIR": str(self.config),
            "OPENCAIRN_SESSION_ID": "status-test",
            "LOCKED_EDIT_MOVE_TIMEOUT_SECONDS": "1",
            "LOCKED_EDIT_OBSIDIAN_CALL_TIMEOUT_SECONDS": "1",
        }

    def run_status(self, destination: str, action: str = "--apply") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(SCRIPT),
                "--vault",
                str(self.vault),
                "--project",
                "Example",
                "--to",
                destination,
                action,
            ],
            text=True,
            capture_output=True,
            check=False,
            env=self.environment(),
        )

    def test_cools_project_heals_live_and_archive_links_and_imports_receipt(self) -> None:
        source = self.vault / "03 Projects/Example.md"
        source.write_text("# Example\n", encoding="utf-8")
        live = self.vault / "04 Areas/Example/Index.md"
        live.write_text("[[03 Projects/Example]]\n", encoding="utf-8")
        archived = self.vault / "06 Archive/OpenCairn/Session Logs/Old.md"
        archived.write_text("[[03 Projects/Example]]\n\n\n\nHistoric spacing.\n", encoding="utf-8")

        result = self.run_status("cold")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(source.exists())
        self.assertTrue((self.vault / "03 Projects/Cold/Example.md").is_file())
        self.assertEqual(live.read_text(encoding="utf-8"), "[[03 Projects/Cold/Example]]\n")
        self.assertEqual(
            archived.read_text(encoding="utf-8"),
            "[[03 Projects/Cold/Example]]\n\n\n\nHistoric spacing.\n",
        )
        payload = json.loads(result.stdout)
        receipt = Path(payload["move_receipt"])
        self.assertTrue(receipt.is_file())
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(receipt_payload["schema"], 2)
        self.assertEqual(len(receipt_payload["affected_files"]), 2)

        imported = subprocess.run(
            [sys.executable, str(PARK_REVIEW), "import-move-heals", "--vault", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
            env=self.environment(),
        )
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertIn("1 move(s), 2 link-healed file(s)", imported.stdout)
        manifest = json.loads(
            (
                self.config
                / ".session-state/status-test.park-review/files.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(manifest[str(live.resolve())]["mode"], "mechanical")
        self.assertEqual(manifest[str(archived.resolve())]["mode"], "mechanical")

    def test_dry_run_does_not_mutate(self) -> None:
        source = self.vault / "03 Projects/Example.md"
        source.write_text("# Example\n", encoding="utf-8")
        result = self.run_status("cold", "--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(source.is_file())
        self.assertFalse((self.vault / "03 Projects/Cold/Example.md").exists())
        plan = json.loads(result.stdout)
        self.assertTrue(plan["destination_directory_will_create"])

    def test_activation_reads_cap_from_vault_principles(self) -> None:
        (self.vault / "03 Projects/Cold").mkdir()
        (self.vault / "03 Projects/Cold/Example.md").write_text("# Example\n", encoding="utf-8")
        (self.vault / "07 System/Vault Organisation Principles.md").write_text(
            "**Active project cap: 2**\n", encoding="utf-8"
        )
        for number in range(2):
            (self.vault / f"03 Projects/Active {number}.md").write_text("# Active\n", encoding="utf-8")

        result = self.run_status("active", "--dry-run")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("active-project cap of 2", result.stderr)

    def test_prefix_sharing_project_link_is_not_rewritten(self) -> None:
        source = self.vault / "03 Projects/Example.md"
        source.write_text("# Example\n", encoding="utf-8")
        reference = self.vault / "04 Areas/Example/Index.md"
        reference.write_text(
            "[[03 Projects/Example]]\n[[03 Projects/Example Notes]]\n",
            encoding="utf-8",
        )

        result = self.run_status("cold")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            reference.read_text(encoding="utf-8"),
            "[[03 Projects/Cold/Example]]\n[[03 Projects/Example Notes]]\n",
        )


if __name__ == "__main__":
    unittest.main()
