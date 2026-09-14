import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPTS = (
    ROOT / ".claude/scripts/backfill-files-updated.sh",
    ROOT / ".claude/scripts/update-session-section.sh",
    ROOT / ".claude/scripts/write-session.sh",
)


class SessionStdinTimeoutTests(unittest.TestCase):
    def test_unclosed_stdin_pipe_times_out_before_locking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session_file = Path(tmp) / "2026-09-06.md"
            invocations = (
                (SCRIPTS[0], str(session_file), "1"),
                (SCRIPTS[1], str(session_file), "1", "Summary"),
                (SCRIPTS[2], str(session_file)),
            )
            env = os.environ.copy()
            env["OPENCAIRN_STDIN_TIMEOUT_SECONDS"] = "1"
            env.update(
                CLAUDE_CONFIG_DIR=tmp,
                OPENCAIRN_SESSION_ID="stdin-timeout-fixture",
                CODEX_THREAD_ID="stdin-timeout-fixture",
                CLAUDE_CODE_SESSION_ID="stdin-timeout-fixture",
            )

            for argv in invocations:
                with self.subTest(script=argv[0].name):
                    proc = subprocess.Popen(
                        argv,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        env=env,
                    )
                    proc.wait(timeout=4)
                    assert proc.stdin is not None
                    proc.stdin.close()
                    assert proc.stdout is not None
                    assert proc.stderr is not None
                    stdout = proc.stdout.read()
                    stderr = proc.stderr.read()
                    proc.stdout.close()
                    proc.stderr.close()

                    self.assertEqual(proc.returncode, 2, stdout + stderr)
                    self.assertIn("Timed out after 1s waiting for stdin to close", stderr)
                    self.assertFalse((session_file.parent / ".lock").exists())


class SessionSectionPayloadTests(unittest.TestCase):
    ORIGINAL = (
        "## Session 1 - Fixture\n\n### Summary\n\nOriginal summary.\n\n"
        "### Files Updated\n\nOriginal files.\n\n"
        "## Session 2 - Other\n\n### Summary\n\nOther session.\n"
    )

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.session_file = self.directory / "session.md"
        self.env = dict(
            os.environ,
            CLAUDE_CONFIG_DIR=temporary.name,
            OPENCAIRN_SESSION_ID="section-payload-fixture",
            CODEX_THREAD_ID="section-payload-fixture",
            CLAUDE_CODE_SESSION_ID="section-payload-fixture",
        )

    def run_payload(self, payload: str, replace: bool) -> subprocess.CompletedProcess:
        self.session_file.write_text(self.ORIGINAL)
        self.session_file.chmod(0o640)
        return subprocess.run(
            [str(SCRIPTS[1]), str(self.session_file), "1", "Summary"]
            + (["--replace"] if replace else []),
            input=payload,
            text=True,
            capture_output=True,
            env=self.env,
            timeout=10,
        )

    def test_boundary_payloads_rejected_before_mutation(self) -> None:
        boundaries = ("### Files Updated", "### ", "## Session 8 - Injected", "## Session ")
        for replace in (False, True):
            for boundary in boundaries:
                for payload in (
                    boundary + "\nInjected body.\n",
                    "Ordinary body.\n" + boundary,
                    boundary + "\n" + "x" * 100000 + "\n",
                ):
                    with self.subTest(replace=replace, boundary=boundary, size=len(payload)):
                        result = self.run_payload(payload, replace)
                        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn("section or session boundary", result.stderr)
                        self.assertEqual(self.session_file.read_bytes(), self.ORIGINAL.encode())
                        self.assertEqual(self.session_file.stat().st_mode & 0o777, 0o640)
                        self.assertEqual(set(self.directory.iterdir()), {self.session_file})

    def test_ordinary_body_preserved_in_both_modes(self) -> None:
        payload = (
            "Ordinary body with inline ### text and ## Session text; 100% preserved.\n"
            "#### Detail\nAllowed nested detail.\n"
            "  ### Indented text\n###\n###\tTab is not a space\n"
            "## Session\n## Sessions are ordinary text\n"
            "Literal backslash: \\n and \\t; trailing spaces.  \n"
        )
        for replace in (False, True):
            with self.subTest(replace=replace):
                result = self.run_payload(payload, replace)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                after = self.session_file.read_text()
                self.assertIn(payload, after)
                self.assertTrue(after.startswith("## Session 1 - Fixture\n\n### Summary\n"))
                self.assertEqual("Original summary." in after, not replace)
                boundary = "### Files Updated\n"
                self.assertEqual(after.count(boundary), 1)
                self.assertEqual(after.split(boundary, 1)[1], self.ORIGINAL.split(boundary, 1)[1])
                self.assertEqual(self.session_file.stat().st_mode & 0o777, 0o640)


if __name__ == "__main__":
    unittest.main()
