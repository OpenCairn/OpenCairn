"""Exercise the documented existing-binary replacement route with opaque bytes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/locked-edit.sh"


class BinaryReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.target = self.vault / "Report - print.pdf"
        self.before = b"%PDF-1.7\n\x00\xfforiginal\r\n"
        self.target.write_bytes(self.before)
        self.target.chmod(0o640)
        self.snapshot = hashlib.sha256(self.before).hexdigest()
        self.state = self.root / "state"
        self.env = isolate_session(os.environ.copy(), self.state, "binary-replacement")
        self.env["VAULT_PATH"] = str(self.vault)
        self.staged = self.root / "render.pdf"
        # Non-UTF-8, NULs, separator-looking bytes and trailing newlines must survive.
        self.staged.write_bytes(bytes(range(256)) + b"\n========OPENCAIRN-LOCKED-EDIT-SEP========\n\n")

    def replace(self):
        with self.staged.open("rb") as payload:
            return subprocess.run(
                ["bash", str(SCRIPT), str(self.target), "--replace-whole", self.snapshot],
                stdin=payload, capture_output=True, env=self.env, timeout=20,
            )

    def test_preserves_bytes_mode_and_records_binary_hashes(self):
        result = self.replace()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_bytes(), self.staged.read_bytes())
        if os.name != "nt":
            self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        receipts = [json.loads(p.read_text()) for p in self.state.rglob("receipt.*")]
        matching = [r for r in receipts if r.get("target") == str(self.target.resolve())]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["pre_sha256"], self.snapshot)
        self.assertEqual(matching[0]["post_sha256"], hashlib.sha256(self.staged.read_bytes()).hexdigest())

    def test_stale_snapshot_preserves_competing_binary(self):
        competing = b"\x00\xfeanother writer\n"
        self.target.write_bytes(competing)
        result = self.replace()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b"Target changed since snapshot read", result.stderr)
        self.assertEqual(self.target.read_bytes(), competing)
        self.assertFalse(list(self.state.rglob("receipt.*")))

    def test_removed_target_is_not_silently_recreated(self):
        self.target.unlink()
        result = self.replace()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b"found MISSING", result.stderr)
        self.assertFalse(self.target.exists())
        self.assertFalse(list(self.state.rglob("receipt.*")))


if __name__ == "__main__":
    unittest.main()
