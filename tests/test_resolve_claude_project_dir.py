import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/resolve-claude-project-dir.sh"


def project_dir_name(path: Path) -> str:
    """Claude Code's naming: every non-alphanumeric character becomes '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


SESSION_VARS = ("OPENCAIRN_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")


def run(vault: Path, home: Path, cwd: Path, path: str = None,
        session: str = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env.pop("CLAUDE_CONFIG_DIR", None)
    for var in SESSION_VARS:  # the test host's own session must not leak in
        env.pop(var, None)
    if session is not None:
        env["CLAUDE_CODE_SESSION_ID"] = session
    if path is not None:
        env["PATH"] = path
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
        self.derived = self.projects / project_dir_name(self.vault)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_oops_memory_lookup_uses_session_from_foreign_cwd(self) -> None:
        # Execute the actual command snippet, with a conflicting cwd memory
        # directory: finding the resolver name alone would not prove routing.
        command = (SCRIPT.parents[1] / "commands/oops.md").read_text()
        phase = command.split("### Phase 2:", 1)[1].split("### Phase 3:", 1)[0]
        snippet = re.search(r"```bash\n(.*?)```", phase, re.S).group(1)
        scripts = self.vault / ".claude/scripts"
        scripts.mkdir(parents=True)
        for name in ("resolve-claude-project-dir.sh", "lib-session.sh"):
            shutil.copy2(SCRIPT.parent / name, scripts / name)
        launch = self.projects / "-launch-project"
        memory = launch / "memory"
        memory.mkdir(parents=True)
        (launch / "fixture-session.jsonl").write_text('{}\n')
        decoy = self.projects / project_dir_name(self.elsewhere) / "memory"
        decoy.mkdir(parents=True)
        env = os.environ.copy()
        env.update({"HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(self.home / ".claude")})
        for var in SESSION_VARS:
            env.pop(var, None)
        env["OPENCAIRN_SESSION_ID"] = "fixture-session"
        result = subprocess.run(
            ["bash", "-c", snippet.replace("{VAULT}", str(self.vault))],
            env=env, cwd=self.elsewhere, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MEMORY DIR: " + str(memory), result.stdout)
        self.assertNotIn(str(decoy), result.stdout)
        self.assertIn("this session's transcript", result.stderr)

        # Removing the only attribution leaves the decoy intact. No arbitrary
        # project memory may be offered as a fallback.
        (launch / "fixture-session.jsonl").unlink()
        result = subprocess.run(
            ["bash", "-c", snippet.replace("{VAULT}", str(self.vault))],
            env=env, cwd=self.elsewhere, capture_output=True, text=True,
        )
        self.assertNotIn("MEMORY DIR:", result.stdout)
        self.assertNotIn(str(decoy), result.stdout)
        self.assertIn("project dir: none", result.stderr)

    def test_derived_dir_found_from_foreign_cwd(self) -> None:
        self.derived.mkdir()
        (self.projects / "-some-other-project").mkdir()
        result = run(self.vault, self.home, self.elsewhere)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.derived)])
        self.assertIn("derived", result.stderr)

    def test_running_sessions_transcript_wins_over_the_vault_derived_dir(self) -> None:
        # Launched from /home/user with the vault as a subdirectory: the session's
        # transcript (and its memory/) live under the launch cwd's project dir.
        self.derived.mkdir()
        launch = self.projects / "-home-user"
        launch.mkdir()
        sid = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        (launch / f"{sid}.jsonl").write_text('{"type":"user","cwd":"/home/user"}\n', encoding="utf-8")
        result = run(self.vault, self.home, self.elsewhere, session=sid)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(launch)])
        self.assertIn("project dir: this session's transcript", result.stderr)

    def test_session_without_transcript_falls_through_to_the_derived_dir(self) -> None:
        self.derived.mkdir()
        (self.projects / "-home-user").mkdir()
        result = run(self.vault, self.home, self.elsewhere, session="no-such-session")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.derived)])
        self.assertIn("derived", result.stderr)

    def test_derived_dir_replaces_every_non_alphanumeric_character(self) -> None:
        vault = Path(self.tmp.name) / "review/my_vault dir"
        vault.mkdir(parents=True)
        derived = self.projects / project_dir_name(vault)
        self.assertNotIn("_", derived.name)
        self.assertNotIn(" ", derived.name)
        derived.mkdir()
        # The slash-and-dot-only rendering is a decoy: it must not be chosen.
        (self.projects / str(vault).replace("/", "-").replace(".", "-")).mkdir()
        result = run(vault, self.home, self.elsewhere)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(derived)])
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
    def test_sweep_ignores_transcripts_that_only_mention_the_vault_path(self) -> None:
        reader = self.projects / "-home-user-repos-tool"
        reader.mkdir()
        # A session elsewhere that read a vault file: the path appears, the cwd field does not.
        (reader / "abc.jsonl").write_text(
            '{"type":"user","cwd":"/home/user/repos/tool","message":"read %s/note.md"}\n' % self.vault,
            encoding="utf-8",
        )
        result = run(self.vault, self.home, self.elsewhere)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("project dir: none (", result.stderr)

    @unittest.skipIf(shutil.which("rg") is None, "rg required for the sweep")
    def test_sweep_with_two_cwd_matches_prints_both_and_exits_three(self) -> None:
        dirs = []
        for name in ("-home-user-repos-tool", "-home-user-other"):
            d = self.projects / name
            d.mkdir()
            (d / "abc.jsonl").write_text('{"type":"user","cwd":"%s"}\n' % self.vault, encoding="utf-8")
            dirs.append(str(d))
        result = run(self.vault, self.home, self.elsewhere)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(sorted(result.stdout.splitlines()), sorted(dirs))
        self.assertIn("project dir: ambiguous (2 candidates)", result.stderr)

    @unittest.skipIf(shutil.which("rg") is None, "rg required for the sweep")
    def test_nothing_found_exits_nonzero(self) -> None:
        (self.projects / "-home-user-unrelated").mkdir()
        result = run(self.vault, self.home, self.elsewhere)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("project dir: none (", result.stderr)
        self.assertNotIn("lookup failed", result.stderr)

    def test_missing_rg_is_a_lookup_failure_not_a_confirmed_absence(self) -> None:
        (self.projects / "-home-user-unrelated").mkdir()
        # A PATH holding only the tools the script needs besides rg.
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        for tool in ("bash", "sed", "dirname", "sort"):
            real = shutil.which(tool)
            self.assertIsNotNone(real, tool)
            (bin_dir / tool).symlink_to(real)
        result = run(self.vault, self.home, self.elsewhere, path=str(bin_dir))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("project dir: lookup failed (", result.stderr)
        self.assertIn("rg unavailable", result.stderr)
        self.assertNotIn("project dir: none", result.stderr)


if __name__ == "__main__":
    unittest.main()
