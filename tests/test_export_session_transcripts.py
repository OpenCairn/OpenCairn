import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/export-session-transcripts.py"


class ExportSessionTranscriptsTests(unittest.TestCase):
    def make_codex_rollout(self, home: Path, cwd: Path) -> Path:
        rollout = (
            home
            / ".codex/sessions/2026/08/16"
            / "rollout-2026-08-16T10-00-00-019c1234-5678-7abc-9def-0123456789ab.jsonl"
        )
        rollout.parent.mkdir(parents=True)
        records = [
            {
                "timestamp": "2026-08-16T00:00:00Z",
                "type": "session_meta",
                "payload": {"id": "019c1234-5678-7abc-9def-0123456789ab", "cwd": str(cwd)},
            },
            {
                "timestamp": "2026-08-16T00:00:01Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "Codex-only prompt"},
            },
            {
                "timestamp": "2026-08-16T00:00:02Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Codex-only response"}],
                },
            },
        ]
        rollout.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        return rollout

    def run_exporter(self, home: Path, vault: Path, cwd: Path, *args: str):
        env = os.environ.copy()
        env["HOME"] = str(home)
        return subprocess.run(
            ["python3", str(SCRIPT), str(vault), "--days", "7", *args],
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def assert_codex_export(self, vault: Path, rollout: Path) -> None:
        date_str = datetime.fromtimestamp(rollout.stat().st_mtime).strftime("%Y-%m-%d")
        output = vault / "06 Archive/OpenCairn/.Session Transcripts" / f"{date_str}.md"
        self.assertTrue(output.is_file())
        text = output.read_text(encoding="utf-8")
        self.assertIn("Codex-only prompt", text)
        self.assertIn("Codex-only response", text)
        self.assertFalse((vault / "06 Archive/Claude").exists())

    def test_all_projects_works_without_claude_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            vault = root / "vault"
            cwd = root / "project"
            cwd.mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)

            result = self.run_exporter(home, vault, cwd, "--all-projects")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("0 Claude project(s), 1 Codex rollout(s)", result.stdout)
            self.assert_codex_export(vault, rollout)

    def test_cwd_scoped_export_works_without_claude_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            vault = root / "vault"
            cwd = root / "project"
            cwd.mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)

            result = self.run_exporter(home, vault, cwd)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Session source: Codex rollouts", result.stdout)
            self.assert_codex_export(vault, rollout)


if __name__ == "__main__":
    unittest.main()
