import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/locked-ingress.sh"


class LockedIngressTests(unittest.TestCase):
    def run_ingress(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), *args], check=False, capture_output=True, text=True
        )

    def test_copies_binary_file_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            destination_parent = vault / "04 Areas/Media"
            destination_parent.mkdir(parents=True)
            source = root / "source.bin"
            source.write_bytes(b"\x00\xffpayload")
            source.chmod(0o640)
            target = destination_parent / "source.bin"

            result = self.run_ingress(str(vault), str(source), str(target))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual(os.stat(target).st_mode & 0o777, 0o640)
            self.assertTrue(source.exists())

    def test_moves_directory_from_outside_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            parent = vault / "04 Areas/Media"
            parent.mkdir(parents=True)
            source = root / "recording-set"
            source.mkdir()
            (source / "clip.wav").write_bytes(b"RIFF")
            target = parent / "recording-set"

            result = self.run_ingress(str(vault), str(source), str(target), "--move")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((target / "clip.wav").read_bytes(), b"RIFF")
            self.assertFalse(source.exists())

    def test_refuses_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            vault.mkdir()
            source = root / "source.bin"
            source.write_bytes(b"new")
            target = vault / "target.bin"
            target.write_bytes(b"old")

            result = self.run_ingress(str(vault), str(source), str(target))

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_bytes(), b"old")


if __name__ == "__main__":
    unittest.main()
