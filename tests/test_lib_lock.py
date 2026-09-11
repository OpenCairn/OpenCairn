import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
LIB_LOCK = ROOT / ".claude/scripts/lib-lock.sh"


class LibLockFallbackTests(unittest.TestCase):
    def test_old_live_lock_is_never_reaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            lock_file = tmp_path / "record.lock"
            lock_dir = tmp_path / "record.lock.d"
            lock_dir.mkdir()
            (lock_dir / "owner").write_text(
                f"pid={os.getpid()} host={socket.gethostname()} acquired=1\n",
                encoding="utf-8",
            )
            old = time.time() - 3600
            os.utime(lock_dir, (old, old))

            # Supply only the commands needed by the mkdir branch, deliberately
            # omitting flock so the portable fallback is exercised.
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            for command in ("mkdir", "sleep", "sed"):
                resolved = shutil.which(command)
                assert resolved is not None
                (bin_dir / command).symlink_to(resolved)

            result = subprocess.run(
                [
                    "/bin/bash",
                    "-c",
                    'source "$1"; _lock "$2" 1',
                    "bash",
                    str(LIB_LOCK),
                    str(lock_file),
                ],
                text=True,
                capture_output=True,
                env={**os.environ, "PATH": str(bin_dir)},
                timeout=4,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("no automatic stale-lock removal", result.stderr)
            self.assertTrue(lock_dir.is_dir())
            self.assertTrue((lock_dir / "owner").is_file())


if __name__ == "__main__":
    unittest.main()
