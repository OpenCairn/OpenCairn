import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session

SCRIPT = Path(__file__).parents[1] / ".claude/scripts/locked-edit.sh"
SEP = "========OPENCAIRN-LOCKED-EDIT-SEP========"


class RelativeTargetTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name).resolve()
        self.vault = self.root / "vault"
        self.elsewhere = self.root / "elsewhere"
        self.vault.mkdir()
        self.elsewhere.mkdir()
        self.target = self.vault / "01 Now" / "Plan.md"
        self.target.parent.mkdir()
        self.target.write_text("# Plan\n\none\n", encoding="utf-8")
        self.config = self.root / "config"
        self.env = isolate_session(os.environ.copy(), self.config, "relative-target-test")
        self.env["VAULT_PATH"] = str(self.vault)

    def run_edit(self, target="01 Now/Plan.md", mode="--append", *args, payload="two\n", env=None):
        return subprocess.run(
            ["bash", str(SCRIPT), str(target), mode, *args],
            input=payload, capture_output=True, text=True, cwd=self.elsewhere,
            env=self.env if env is None else env,
        )

    def symlink(self, path, destination):
        try:
            path.symlink_to(destination, target_is_directory=destination.is_dir())
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"Symlinks unavailable: {exc}")

    def assert_rejected_without_changes(self, target, env=None):
        # Captures locks, receipts and new directories as well as file contents.
        def snapshot():
            return {str(p.relative_to(self.root)): (
                ("link", os.readlink(p)) if p.is_symlink() else
                ("dir",) if p.is_dir() else ("file", p.read_bytes())
            ) for p in self.root.rglob("*")}
        before = snapshot()
        result = self.run_edit(target, env=env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(snapshot(), before)
        return result

    def test_relative_target_uses_vault_even_when_cwd_has_same_file(self):
        other = self.elsewhere / "01 Now" / "Plan.md"
        other.parent.mkdir()
        other.write_text("wrong target\n")
        result = self.run_edit()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), "# Plan\n\none\ntwo\n")
        self.assertEqual(other.read_text(), "wrong target\n")
        self.assertFalse((other.parent / ".Plan.md.lock").exists())
        ledger = (self.config / ".session-state/relative-target-test.tsv").read_text()
        self.assertIn("\tlocked-edit\t" + str(self.target) + "\t", ledger)
        receipts = list((self.config / ".session-state/relative-target-test.locked-edit-receipts").iterdir())
        self.assertEqual(len(receipts), 1)
        self.assertEqual(json.loads(receipts[0].read_text())["target"], str(self.target))

    def test_all_non_move_modes_accept_relative_targets(self):
        original = "# Plan\n\none\n"
        digest = hashlib.sha256(original.encode()).hexdigest()
        cases = [
            ("--append", (), "two\n", original + "two\n"),
            ("--replace", (), "one\n" + SEP + "\ntwo\n", "# Plan\n\ntwo\n"),
            ("--replace-all", (), "one\n" + SEP + "\ntwo\n", "# Plan\n\ntwo\n"),
            ("--replace-many", (), json.dumps([{"old": "one", "new": "two"}]), "# Plan\n\ntwo\n"),
            ("--replace-whole", (digest,), "new file\n", "new file\n"),
            ("--show-section", ("# Plan",), "", original),
            ("--delete-section", ("# Plan", digest, "--no-replacement"), "", ""),
        ]
        for mode, args, payload, expected in cases:
            with self.subTest(mode=mode):
                self.target.write_text(original)
                result = self.run_edit("01 Now/Plan.md", mode, *args, payload=payload)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.target.read_text(), expected)
                if mode == "--show-section":
                    self.assertEqual(result.stdout, original)

    def test_new_relative_file_is_created_only_in_vault(self):
        for mode, args in [("--append", ()), ("--replace-whole", ("MISSING",))]:
            with self.subTest(mode=mode):
                relative = f"New/{mode}/Note.md"
                result = self.run_edit(relative, mode, *args, payload="new\n")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.vault / relative).read_text(), "new\n")
                self.assertFalse((self.elsewhere / "New").exists())

    def test_dot_segments_inside_vault_are_allowed(self):
        result = self.run_edit("./01 Now/../01 Now/Plan.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.target.read_text().endswith("two\n"))

    def test_traversal_and_sibling_prefix_escape_are_rejected(self):
        for path in ("../escaped.md", "new/../../escaped.md", "../vault-sibling/Note.md"):
            with self.subTest(path=path):
                result = self.assert_rejected_without_changes(path)
                self.assertIn("escapes VAULT_PATH", result.stderr)

    def test_symlink_escapes_are_rejected_including_missing_destinations(self):
        outside = self.root / "outside"
        outside.mkdir()
        note = outside / "Note.md"
        note.write_text("outside\n")
        self.symlink(self.vault / "link", outside)
        self.symlink(self.vault / "leaf.md", note)
        self.symlink(self.vault / "dangling.md", outside / "absent.md")
        for path in ("link/Note.md", "link/new/Note.md", "leaf.md", "dangling.md"):
            with self.subTest(path=path):
                result = self.assert_rejected_without_changes(path)
                self.assertIn("escapes VAULT_PATH", result.stderr)

    def test_symlinked_vault_and_inside_directory_are_allowed(self):
        alias = self.root / "vault-alias"
        self.symlink(alias, self.vault)
        self.symlink(self.vault / "inside", self.target.parent)
        env = dict(self.env, VAULT_PATH=str(alias))
        result = self.run_edit("inside/Plan.md", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.target.read_text().endswith("two\n"))
        self.assertIn(str(self.target), result.stdout)

    def test_inside_leaf_symlink_keeps_absolute_atomic_replace_semantics(self):
        alias = self.vault / "alias.md"
        self.symlink(alias, self.target)
        result = self.run_edit("alias.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(alias.is_symlink())
        self.assertEqual(alias.read_text(), "# Plan\n\none\ntwo\n")
        self.assertEqual(self.target.read_text(), "# Plan\n\none\n")

    def test_invalid_vault_fails_without_side_effects(self):
        for vault in (None, "", "relative-vault", str(self.root / "missing"), str(self.target)):
            with self.subTest(vault=vault):
                env = self.env.copy()
                if vault is None:
                    env.pop("VAULT_PATH")
                else:
                    env["VAULT_PATH"] = vault
                self.assert_rejected_without_changes("New/Note.md", env)

    def test_invalid_target_fails_before_reading_stdin(self):
        proc = subprocess.Popen(
            ["bash", str(SCRIPT), "../outside.md", "--append"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self.env, cwd=self.elsewhere, text=True,
        )
        try:
            self.assertEqual(proc.wait(timeout=5), 1)
            self.assertIn("escapes VAULT_PATH", proc.stderr.read())
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate()

    def test_empty_and_multiline_paths_are_rejected(self):
        for target in ("", "Note\n.md", "Note\r.md"):
            with self.subTest(target=target):
                self.assert_rejected_without_changes(target)

    def test_absolute_outside_target_still_works_without_vault(self):
        outside = self.root / "outside.md"
        env = self.env.copy()
        env.pop("VAULT_PATH")
        result = self.run_edit(outside, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outside.read_text(), "two\n")

    def test_relative_stale_snapshot_does_not_write(self):
        before = self.target.read_bytes()
        result = self.run_edit("01 Now/Plan.md", "--replace-whole", "0" * 64)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.target.read_bytes(), before)

    @unittest.skipUnless(os.name == "posix" and shutil.which("flock"), "requires flock")
    def test_relative_writer_respects_absolute_target_lock(self):
        import fcntl
        lock = self.target.parent / ".Plan.md.lock"
        with lock.open("w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            result = self.run_edit()
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("Failed to acquire lock", result.stderr)
            self.assertEqual(self.target.read_text(), "# Plan\n\none\n")
        result = self.run_edit()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), "# Plan\n\none\ntwo\n")


if __name__ == "__main__":
    unittest.main()
