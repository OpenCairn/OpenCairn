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


if __name__ == "__main__":
    unittest.main()
