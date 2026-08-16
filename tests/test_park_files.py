import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/park-files.sh"


class ParkFilesTests(unittest.TestCase):
    def test_codex_skills_are_candidates_but_system_skills_are_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            (vault / "01 Now").mkdir(parents=True)
            (vault / "02 Inbox").mkdir()
            claude = root / "claude"
            (claude / "commands").mkdir(parents=True)
            (claude / "scripts").mkdir()
            codex = root / "codex"
            personal = codex / "skills/park/SKILL.md"
            personal.parent.mkdir(parents=True)
            personal.write_text("personal\n", encoding="utf-8")
            system = codex / "skills/.system/internal/SKILL.md"
            system.parent.mkdir(parents=True)
            system.write_text("system\n", encoding="utf-8")

            env = os.environ.copy()
            env["CLAUDE_CONFIG_DIR"] = str(claude)
            env["CODEX_HOME"] = str(codex)
            result = subprocess.run(
                [str(SCRIPT), str(vault), "-m", "5"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertIn(str(personal), result.stdout)
            self.assertNotIn(str(system), result.stdout)

    def test_selected_user_runtime_files_are_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            (vault / "01 Now").mkdir(parents=True)
            (vault / "02 Inbox").mkdir()
            claude = root / "claude"
            (claude / "commands").mkdir(parents=True)
            (claude / "scripts").mkdir()
            codex = root / "codex"
            (codex / "skills").mkdir(parents=True)
            home = root / "home"
            libexec = home / ".local/libexec/task-helper"
            libexec.parent.mkdir(parents=True)
            libexec.write_text("#!/bin/sh\n", encoding="utf-8")
            unit = home / ".config/systemd/user/task.service"
            unit.parent.mkdir(parents=True)
            unit.write_text("[Service]\n", encoding="utf-8")
            unit_link = unit.with_name("default.target.wants-task.service")
            unit_link.symlink_to(unit)
            kwin = home / ".config/kwinoutputconfig.json"
            kwin.write_text("{}\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["CLAUDE_CONFIG_DIR"] = str(claude)
            env["CODEX_HOME"] = str(codex)
            result = subprocess.run(
                [str(SCRIPT), str(vault), "-m", "5"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertIn(str(libexec), result.stdout)
            self.assertIn(str(unit), result.stdout)
            self.assertIn(str(unit_link), result.stdout)
            self.assertIn(str(kwin), result.stdout)


if __name__ == "__main__":
    unittest.main()
