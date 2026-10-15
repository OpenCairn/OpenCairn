import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/resolve-claude-project-dir.sh"


def run(vault: Path, home: Path, cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CLAUDE_CONFIG_DIR", None)
    return subprocess.run(
        ["bash", str(SCRIPT), str(vault)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
    )


@unittest.skipIf(shutil.which("bash") is None, "bash required")
class ResolveClaudeProjectDirTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.vault = root / "fixture.vault"
        self.vault.mkdir(parents=True)
        self.elsewhere = root / "elsewhere"
        self.elsewhere.mkdir()
        self.projects = self.home / ".claude/projects"
        self.projects.mkdir(parents=True)
        self.derived = self.projects / str(self.vault).replace("/", "-").replace(".", "-")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_derived_dir_found_from_foreign_cwd(self) -> None:
        self.derived.mkdir()
        (self.projects / "-some-other-project").mkdir()
        result = run(self.vault, self.home, self.elsewhere)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.derived)])
        self.assertIn("derived", result.stderr)

    @unittest.skipIf(shutil.which("rg") is None, "rg required for the sweep")
    def test_sweep_finds_project_dir_whose_transcript_names_vault(self) -> None:
        other = self.projects / "-home-user-repos-tool"
        other.mkdir()
        (other / "abc.jsonl").write_text(
            '{"type":"user","cwd":"%s"}\n' % self.vault, encoding="utf-8"
        )
        unrelated = self.projects / "-home-user-unrelated"
        unrelated.mkdir()
        (unrelated / "def.jsonl").write_text('{"cwd":"/home/user/unrelated"}\n', encoding="utf-8")
        # memory/ content must not count as a transcript
        (unrelated / "memory").mkdir()
        (unrelated / "memory/notes.jsonl").write_text(str(self.vault), encoding="utf-8")
        result = run(self.vault, self.home, self.elsewhere)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(other)])
        self.assertIn("sweep", result.stderr)

    @unittest.skipIf(shutil.which("rg") is None, "rg required for the sweep")
    def test_nothing_found_exits_nonzero(self) -> None:
        (self.projects / "-home-user-unrelated").mkdir()
        result = run(self.vault, self.home, self.elsewhere)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("none", result.stderr)


if __name__ == "__main__":
    unittest.main()
