import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
UPDATE = ROOT / ".claude/commands/update.md"


def block(marker: str) -> str:
    text = UPDATE.read_text(encoding="utf-8")
    start = text.index("```bash\n" + marker + "\n") + len("```bash\n")
    return text[start:text.index("\n```\n", start) + 1]


def run(script: str, cwd: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", script], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=60)


class UpdateInstallSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "vault"
        self.codex = self.tmp / "codex-home"
        (self.repo / "codex/skills/demo").mkdir(parents=True)
        (self.repo / "codex/skills/demo/SKILL.md").write_text("demo\n", encoding="utf-8")
        (self.repo / "notes.md").write_text("vault\n", encoding="utf-8")
        self.env = {**os.environ, "CODEX_HOME": str(self.codex), "HOME": str(self.tmp),
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
        for args in (["init", "-q"], ["add", "-A"],
                     ["commit", "-q", "-m", "base"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True, env=self.env)
        (self.codex / "skills/demo").mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def head(self) -> str:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, check=True,
                              capture_output=True, text=True).stdout.strip()

    def manifest(self) -> str:
        return block("# opencairn: install-manifest").replace(
            "<the immutable target commit>", self.head()).replace(
            "<installed-file-1> <installed-file-2> ...", "demo/SKILL.md")

    def test_clean_source_installs_and_records_head(self) -> None:
        (self.repo / "notes.md").write_text("vault edit outside codex/\n", encoding="utf-8")
        gate = run(block("# opencairn: install-source-gate"), self.repo, self.env)
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        shutil.copy2(self.repo / "codex/skills/demo/SKILL.md", self.codex / "skills/demo/SKILL.md")
        rec = run(self.manifest(), self.repo, self.env)
        self.assertEqual(rec.returncode, 0, rec.stdout + rec.stderr)
        data = json.loads((self.codex / "opencairn-install-manifest.json").read_text())
        entry = data["files"]["demo/SKILL.md"]
        self.assertEqual(entry["source_commit"], self.head())
        self.assertEqual(len(entry["sha256"]), 64)

    def test_dirty_or_untracked_source_is_refused(self) -> None:
        for name, mutate in (
            ("tracked", lambda: (self.repo / "codex/skills/demo/SKILL.md").write_text("edit\n")),
            ("untracked", lambda: (self.repo / "codex/skills/demo/extra.md").write_text("new\n")),
        ):
            with self.subTest(name):
                subprocess.run(["git", "stash", "-q", "--include-untracked"], cwd=self.repo,
                               env=self.env, check=True)
                self.assertEqual(run("git status --porcelain", self.repo, self.env).stdout, "")
                mutate()
                gate = run(block("# opencairn: install-source-gate"), self.repo, self.env)
                self.assertEqual(gate.returncode, 27)
                self.assertIn("Refusing to install", gate.stdout)
                self.assertIn("git stash push --include-untracked -- codex/", gate.stdout)

    def test_live_copy_differing_from_head_is_not_recorded(self) -> None:
        (self.codex / "skills/demo/SKILL.md").write_text("not the commit\n", encoding="utf-8")
        rec = run(self.manifest(), self.repo, self.env)
        self.assertEqual(rec.returncode, 28)
        self.assertFalse((self.codex / "opencairn-install-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
