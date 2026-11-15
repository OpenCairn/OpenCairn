import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/locked-edit.sh"
SEP = "========OPENCAIRN-LOCKED-EDIT-SEP========"
SESSION = "locked-edit-replace-many-test"
PARK_REVIEW = Path(__file__).parents[1] / "codex/skills/park/scripts/park-review.py"

try:
    from session_isolation import isolate_session
except ImportError:  # `python -m unittest tests.<module>` from the repo root
    from tests.session_isolation import isolate_session


class LockedEditReplaceManyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.config = self.root / "config"
        self.target = self.vault / "Plan.md"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def environment(self) -> dict[str, str]:
        environment = isolate_session(os.environ.copy(), self.config, SESSION)
        environment["VAULT_PATH"] = str(self.vault)
        return environment

    def run_script(self, mode: str, payload: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPT), str(self.target), mode],
            input=payload,
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

    def run_many(self, pairs: object) -> subprocess.CompletedProcess[str]:
        payload = pairs if isinstance(pairs, str) else json.dumps(pairs, ensure_ascii=False)
        return self.run_script("--replace-many", payload)

    def receipts(self) -> list[dict]:
        root = self.config / ".session-state" / f"{SESSION}.locked-edit-receipts"
        items = [json.loads(path.read_text(encoding="utf-8")) for path in root.iterdir()]
        return sorted(items, key=lambda item: item["captured_at"])

    @staticmethod
    def sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def test_applies_every_pair_in_one_call(self) -> None:
        original = (
            "# Plan\n\n"
            "- [ ] first item\n"
            "- [ ] second \"quoted\" item \\ with $(shell) `ticks`\n\n"
            "block line one\nblock line two\n\n"
            "tail — unicode ✓\n"
        )
        self.target.write_text(original, encoding="utf-8")
        pairs = [
            {"old": "- [ ] first item", "new": "- [x] first item"},
            {
                "old": "second \"quoted\" item \\ with $(shell) `ticks`",
                "new": "second item\n  - nested\n" + SEP + "\n  - after separator",
            },
            {"old": "block line one\nblock line two\n\n", "new": ""},
            {"old": "unicode ✓", "new": "unicode ✗\n"},
        ]

        result = self.run_many(pairs)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.target.read_text(encoding="utf-8"),
            "# Plan\n\n"
            "- [x] first item\n"
            "- [ ] second item\n  - nested\n" + SEP + "\n  - after separator\n\n"
            "tail — unicode ✗\n\n",
        )
        self.assertIn("Locked edit applied", result.stdout)

    def test_pairs_match_the_original_content_not_each_other(self) -> None:
        self.target.write_text("alpha beta\n", encoding="utf-8")

        result = self.run_many(
            [{"old": "alpha", "new": "beta"}, {"old": "beta", "new": "gamma"}]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "beta gamma\n")

    def test_ledgers_once_and_writes_a_chained_receipt_per_pair(self) -> None:
        original = "one\ntwo\nthree\n"
        self.target.write_text(original, encoding="utf-8")

        result = self.run_many(
            [{"old": "one", "new": "1"}, {"old": "three", "new": "3"}]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        ledger = self.config / ".session-state" / f"{SESSION}.tsv"
        rows = ledger.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rows), 1)
        self.assertIn("\tlocked-edit\t", rows[0])
        receipts = self.receipts()
        self.assertEqual(len(receipts), 2)
        self.assertEqual({item["mode"] for item in receipts}, {"--replace"})
        self.assertEqual({item["invoked_mode"] for item in receipts}, {"--replace-many"})
        self.assertEqual(
            sorted((item["old_text"], item["new_text"]) for item in receipts),
            [("one", "1"), ("three", "3")],
        )
        self.assertEqual(receipts[0]["pre_sha256"], self.sha(original))
        self.assertEqual(receipts[0]["post_sha256"], receipts[1]["pre_sha256"])
        self.assertEqual(receipts[1]["post_sha256"], self.sha("1\ntwo\n3\n"))
        self.assertLess(receipts[0]["captured_at"], receipts[1]["captured_at"])

    def test_receipts_satisfy_the_park_mechanical_verifier(self) -> None:
        spec = importlib.util.spec_from_file_location("park_review", PARK_REVIEW)
        assert spec is not None and spec.loader is not None
        park_review = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(park_review)
        self.target.write_text(
            "see Old/Alpha here\nmiddle\nand Old/Beta there\n", encoding="utf-8"
        )
        replacements = [["Old/Alpha", "New/Alpha"], ["Old/Beta", "New/Beta"]]

        result = self.run_many([{"old": old, "new": new} for old, new in replacements])

        self.assertEqual(result.returncode, 0, result.stderr)
        verdict = park_review.verify_mechanical(
            self.target.resolve(),
            self.vault.resolve(),
            replacements,
            [],
            self.config / ".session-state" / f"{SESSION}.locked-edit-receipts",
        )
        self.assertTrue(verdict["ok"], verdict["failures"])
        self.assertEqual(len(verdict["receipts"]), 2)

    def test_missing_pair_leaves_file_untouched_and_names_the_pair(self) -> None:
        original = "one\ntwo\n"
        self.target.write_text(original, encoding="utf-8")

        result = self.run_many(
            [{"old": "one", "new": "1"}, {"old": "absent", "new": "x"}]
        )

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), original)
        self.assertIn("pair 2 of 2", result.stderr)
        self.assertIn("absent", result.stderr)
        self.assertNotIn("Locked edit applied", result.stdout)
        self.assertFalse((self.config / ".session-state").exists())

    def test_ambiguous_pair_leaves_file_untouched_and_names_the_pair(self) -> None:
        original = "same\nsame\nother\n"
        self.target.write_text(original, encoding="utf-8")

        result = self.run_many(
            [{"old": "same", "new": "x"}, {"old": "other", "new": "y"}]
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), original)
        self.assertIn("pair 1 of 2", result.stderr)

    def test_overlapping_pairs_are_refused(self) -> None:
        original = "alpha beta gamma\n"
        self.target.write_text(original, encoding="utf-8")

        result = self.run_many(
            [{"old": "alpha beta", "new": "x"}, {"old": "beta gamma", "new": "y"}]
        )

        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), original)
        self.assertIn("pairs 1 and 2 overlap", result.stderr)

    def test_malformed_payloads_are_usage_errors(self) -> None:
        original = "one\n"
        self.target.write_text(original, encoding="utf-8")
        payloads = [
            "not json",
            "[]",
            json.dumps({"old": "one", "new": "1"}),
            json.dumps([{"old": "one"}]),
            json.dumps([{"old": "", "new": "1"}]),
            json.dumps([{"old": "one", "new": 1}]),
            json.dumps([{"old": "one", "new": "1", "extra": "x"}]),
        ]

        for payload in payloads:
            with self.subTest(payload=payload):
                result = self.run_many(payload)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(self.target.read_text(encoding="utf-8"), original)

    def test_missing_target_is_a_stale_failure(self) -> None:
        result = self.run_many([{"old": "one", "new": "1"}])

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(self.target.exists())

    def test_single_replace_mode_is_unchanged(self) -> None:
        self.target.write_text("one\ntwo\n", encoding="utf-8")

        result = self.run_script("--replace", "one\n" + SEP + "\n1\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "1\ntwo\n")
        receipts = self.receipts()
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["mode"], "--replace")
        self.assertNotIn("invoked_mode", receipts[0])

    def test_no_temp_files_are_left_behind_without_a_session_id(self) -> None:
        self.target.write_text("alpha\nbeta\n", encoding="utf-8")
        scratch = self.root / "scratch"
        scratch.mkdir()
        environment = self.environment()
        del environment["OPENCAIRN_SESSION_ID"]
        environment["TMPDIR"] = str(scratch)

        result = subprocess.run(
            [str(SCRIPT), str(self.target), "--replace-many"],
            input=json.dumps([{"old": "alpha", "new": "ALPHA"}, {"old": "beta", "new": "BETA"}]),
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "ALPHA\nBETA\n")
        self.assertEqual(sorted(path.name for path in scratch.iterdir()), [])

        failed = subprocess.run(
            [str(SCRIPT), str(self.target), "--replace-many"],
            input=json.dumps([{"old": "absent", "new": "x"}]),
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(failed.returncode, 2, failed.stderr)
        self.assertEqual(sorted(path.name for path in scratch.iterdir()), [])

    def test_per_pair_receipts_are_private_to_the_user(self) -> None:
        self.target.write_text("alpha\nbeta\n", encoding="utf-8")

        result = self.run_many([{"old": "alpha", "new": "ALPHA"}, {"old": "beta", "new": "BETA"}])

        self.assertEqual(result.returncode, 0, result.stderr)
        root = self.config / ".session-state" / f"{SESSION}.locked-edit-receipts"
        modes = sorted(path.stat().st_mode & 0o777 for path in root.iterdir())
        self.assertEqual(modes, [0o600, 0o600])

    def test_receipt_storage_failure_is_reported_after_the_edit_lands(self) -> None:
        self.target.write_text("alpha\n", encoding="utf-8")
        state = self.config / ".session-state"
        state.mkdir(parents=True)
        # A file where the receipt directory belongs makes storage fail.
        (state / f"{SESSION}.locked-edit-receipts").write_text("", encoding="utf-8")

        result = self.run_many([{"old": "alpha", "new": "ALPHA"}])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "ALPHA\n")
        self.assertIn("WARNING: locked-edit receipt directory unavailable", result.stderr)


if __name__ == "__main__":
    unittest.main()
