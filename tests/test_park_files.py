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


class VaultInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="park-inventory-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.env = os.environ.copy()
        self.env.update({
            "HOME": str(self.root / "home"),
            "CLAUDE_CONFIG_DIR": str(self.root / "claude"),
            "CODEX_HOME": str(self.root / "codex"),
            "OPENCAIRN_SESSION_ID": "synthetic-inventory",
            "CLAUDE_CODE_SESSION_ID": "synthetic-inventory",
            "CODEX_THREAD_ID": "synthetic-inventory",
        })

    def write(self, name: str) -> Path:
        path = self.vault / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
        return path

    def git(self, *args: str, old: bool = False) -> str:
        env = self.env.copy()
        if old:
            env.update({"GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
                        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"})
        result = subprocess.run(
            ["git", "-C", str(self.vault), "-c", "commit.gpgsign=false", *args],
            env=env, capture_output=True, text=True, check=True,
        )
        return result.stdout

    def init_git(self) -> None:
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")

    def inventory(self, *repos: Path) -> str:
        result = subprocess.run(
            [str(SCRIPT), str(self.vault), "-m", "5", *map(str, repos)],
            env=self.env, capture_output=True, text=True, check=True,
        )
        return result.stdout

    def test_vault_body_candidates_reach_deep_notes_and_prune_metadata(self) -> None:
        for name in ("03 Projects/Example/deep/note.md", "04 Areas/Example.md",
                     "05 Resources/source.txt", "06 Archive/Example/note.md",
                     "07 System/Context.md", "Clippings/article.md", "root-note.md"):
            path = self.write(name)
            self.assertIn("[vault]\t" + str(path) + "\n", self.inventory())
        hidden = self.write(".git/objects/metadata.md")
        state = self.write("04 Areas/.session-state/internal.md")
        transient = self.write("01 Now/day.md")
        output = self.inventory()
        self.assertNotIn(str(hidden), output)
        self.assertNotIn(str(state), output)
        self.assertIn("[transient]\t" + str(transient), output)
        self.assertIn("[vault]\t" + str(transient), output)

    def test_transient_roots_include_binary_and_deep_text_work(self) -> None:
        paths = [self.write("02 Inbox/source/report.pdf"),
                 self.write("01 Now/working/deep/result.txt")]
        output = self.inventory()
        for path in paths:
            self.assertIn("[vault]\t" + str(path) + "\n", output)

    def test_working_tree_deletes_and_staged_moves_keep_old_paths(self) -> None:
        self.init_git()
        deleted = self.write("04 Areas/deleted.md")
        self.write("03 Projects/old.md")
        self.git("add", ".")
        self.git("commit", "-qm", "Baseline", old=True)
        deleted.unlink()
        self.git("mv", "03 Projects/old.md", "03 Projects/new.md")
        output = self.inventory()
        self.assertIn(f"[git-diff]\t{self.vault}\tD\t04 Areas/deleted.md\n", output)
        self.assertIn(f"[git-diff]\t{self.vault}\tR100\t03 Projects/old.md\t03 Projects/new.md\n", output)

    def test_recent_autosaves_preserve_intermediate_move_and_delete_candidates(self) -> None:
        self.init_git()
        self.write("04 Areas/old.md")
        self.git("add", ".")
        self.git("commit", "-qm", "Baseline", old=True)
        self.git("mv", "04 Areas/old.md", "04 Areas/intermediate.md")
        self.git("commit", "-qm", "Auto-save move")
        self.git("rm", "04 Areas/intermediate.md")
        self.git("commit", "-qm", "Auto-save delete")
        self.assertEqual(self.git("status", "--short"), "")
        output = self.inventory()
        self.assertIn(f"[git-history]\t{self.vault}\tD\t04 Areas/intermediate.md\n", output)
        self.assertIn(f"[git-history]\t{self.vault}\tR100\t04 Areas/old.md\t04 Areas/intermediate.md\n", output)
        # The old baseline's creation falls outside the requested window.
        self.assertNotIn(f"[git-history]\t{self.vault}\tA\t04 Areas/old.md", output)


if __name__ == "__main__":
    unittest.main()
