import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import time
import unittest


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/locked-edit.sh"


MOCK_OBSIDIAN = r"""#!/usr/bin/env python3
import os
from pathlib import Path
import sys
import time

args = sys.argv[1:]
vault = Path(os.environ["VAULT_PATH"])

if args == ["help", "move"]:
    marker = os.environ.get("MOCK_EMPTY_HELP_ONCE")
    if marker and not Path(marker).exists():
        Path(marker).touch()
        raise SystemExit(0)
    hang_marker = os.environ.get("MOCK_HANG_HELP_ONCE")
    if hang_marker and not Path(hang_marker).exists():
        Path(hang_marker).touch()
        time.sleep(3)
    print("move file=<name> path=<path> to=<path>")
    raise SystemExit(0)
if args == ["version"]:
    print("1.13.7")
    raise SystemExit(0)
if args == ["vault", "info=path"]:
    print(os.environ.get("MOCK_ACTIVE_VAULT", str(vault)))
    raise SystemExit(0)
if args and args[0] == "move":
    values = dict(item.split("=", 1) for item in args[1:])
    source_rel = values["path"]
    destination_rel = values["to"]
    source = vault / source_rel
    destination = vault / destination_rel
    time.sleep(float(os.environ.get("MOCK_DELAY", "0")))
    behaviour = os.environ.get("MOCK_MOVE_BEHAVIOUR", "complete")
    if behaviour == "none":
        raise SystemExit(0)
    if behaviour == "copy-only":
        destination.write_bytes(source.read_bytes())
        raise SystemExit(0)
    os.replace(source, destination)
    if behaviour == "complete-no-heal":
        raise SystemExit(0)
    old_no_ext = source_rel[:-3] if source_rel.lower().endswith(".md") else source_rel
    new_no_ext = destination_rel[:-3] if destination_rel.lower().endswith(".md") else destination_rel
    for note in vault.rglob("*.md"):
        text = note.read_text(encoding="utf-8")
        updated = text.replace(old_no_ext, new_no_ext).replace(source_rel, destination_rel)
        if updated != text:
            note.write_text(updated, encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(2)
"""


class LockedEditMoveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        (self.vault / "Old").mkdir()
        (self.vault / "New").mkdir()
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.obsidian = self.bin_dir / "obsidian"
        self.obsidian.write_text(textwrap.dedent(MOCK_OBSIDIAN), encoding="utf-8")
        self.obsidian.chmod(0o755)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def environment(self, **extra: str) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "VAULT_PATH": str(self.vault),
                "OBSIDIAN_CLI": str(self.obsidian),
                "LOCKED_EDIT_MOVE_TIMEOUT_SECONDS": "1",
                "LOCKED_EDIT_OBSIDIAN_CALL_TIMEOUT_SECONDS": "1",
            }
        )
        environment.update(extra)
        return environment

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def run_move(
        self, source: Path, destination: Path, expected: str | None = None, **env: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(SCRIPT),
                str(source),
                "--move",
                str(destination),
                expected or self.digest(source),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(**env),
        )

    def test_moves_with_hash_and_heals_path_qualified_links(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination = self.vault / "New" / "Incident.md"
        source.write_text("incident body\n", encoding="utf-8")
        original_hash = self.digest(source)
        reference = self.vault / "Reference.md"
        reference.write_text(
            "[[Old/Incident]]\n[incident](Old/Incident.md)\n", encoding="utf-8"
        )

        result = self.run_move(source, destination)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(source.exists())
        self.assertTrue(destination.exists())
        self.assertEqual(self.digest(destination), original_hash)
        self.assertEqual(
            reference.read_text(encoding="utf-8"),
            "[[New/Incident]]\n[incident](New/Incident.md)\n",
        )

    def test_refuses_destination_collision(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination = self.vault / "New" / "Incident.md"
        source.write_text("source\n", encoding="utf-8")
        destination.write_text("destination\n", encoding="utf-8")

        result = self.run_move(source, destination)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_text(encoding="utf-8"), "source\n")
        self.assertEqual(destination.read_text(encoding="utf-8"), "destination\n")

    def test_retries_an_intermittently_empty_cli_probe(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination = self.vault / "New" / "Incident.md"
        source.write_text("source\n", encoding="utf-8")
        marker = self.root / "empty-help-observed"

        result = self.run_move(source, destination, MOCK_EMPTY_HELP_ONCE=str(marker))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(marker.exists())
        self.assertFalse(source.exists())
        self.assertTrue(destination.exists())

    def test_times_out_and_retries_a_hung_cli_probe(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination = self.vault / "New" / "Incident.md"
        source.write_text("source\n", encoding="utf-8")
        marker = self.root / "hung-help-observed"

        result = self.run_move(source, destination, MOCK_HANG_HELP_ONCE=str(marker))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(marker.exists())
        self.assertFalse(source.exists())
        self.assertTrue(destination.exists())

    def test_refuses_stale_source_hash(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination = self.vault / "New" / "Incident.md"
        source.write_text("current\n", encoding="utf-8")

        result = self.run_move(source, destination, "0" * 64)

        self.assertEqual(result.returncode, 2)
        self.assertTrue(source.exists())
        self.assertFalse(destination.exists())

    def test_refuses_source_and_destination_path_escapes(self) -> None:
        outside = self.root / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        inside = self.vault / "Old" / "Incident.md"
        inside.write_text("inside\n", encoding="utf-8")

        source_escape = self.run_move(outside, self.vault / "New" / "Outside.md")
        destination_escape = self.run_move(inside, self.root / "escaped.md")

        self.assertNotEqual(source_escape.returncode, 0)
        self.assertNotEqual(destination_escape.returncode, 0)
        self.assertTrue(outside.exists())
        self.assertTrue(inside.exists())
        self.assertFalse((self.root / "escaped.md").exists())

    def test_refuses_missing_obsidian_cli(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination = self.vault / "New" / "Incident.md"
        source.write_text("source\n", encoding="utf-8")

        result = self.run_move(
            source, destination, OBSIDIAN_CLI=str(self.root / "missing-obsidian")
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(source.exists())
        self.assertFalse(destination.exists())

    def test_refuses_incomplete_move(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination = self.vault / "New" / "Incident.md"
        source.write_text("source\n", encoding="utf-8")

        result = self.run_move(source, destination, MOCK_MOVE_BEHAVIOUR="copy-only")

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(source.exists())
        self.assertTrue(destination.exists())

    def test_refuses_complete_move_with_an_unhealed_old_path_link(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination = self.vault / "New" / "Incident.md"
        source.write_text("source\n", encoding="utf-8")
        reference = self.vault / "Reference.md"
        reference.write_text("[[Old/Incident]]\n", encoding="utf-8")

        result = self.run_move(source, destination, MOCK_MOVE_BEHAVIOUR="complete-no-heal")

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(source.exists())
        self.assertTrue(destination.exists())
        self.assertIn("Old path-qualified links remain", result.stderr)

    def test_concurrent_moves_serialize_on_the_source_lock(self) -> None:
        source = self.vault / "Old" / "Incident.md"
        destination_a = self.vault / "New" / "Incident A.md"
        destination_b = self.vault / "New" / "Incident B.md"
        source.write_text("source\n", encoding="utf-8")
        expected = self.digest(source)
        environment = self.environment(MOCK_DELAY="0.5")

        command_a = [str(SCRIPT), str(source), "--move", str(destination_a), expected]
        command_b = [str(SCRIPT), str(source), "--move", str(destination_b), expected]
        first = subprocess.Popen(
            command_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment
        )
        time.sleep(0.1)
        second = subprocess.Popen(
            command_b, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment
        )
        first_stdout, first_stderr = first.communicate(timeout=10)
        second_stdout, second_stderr = second.communicate(timeout=10)

        outcomes = sorted([first.returncode, second.returncode])
        self.assertEqual(outcomes, [0, 2], (first_stderr, second_stderr))
        self.assertFalse(source.exists())
        self.assertEqual(sum(path.exists() for path in (destination_a, destination_b)), 1)
        self.assertTrue(first_stdout or second_stdout)


if __name__ == "__main__":
    unittest.main()
