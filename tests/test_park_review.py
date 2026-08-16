#!/usr/bin/env python3
"""Regression tests for the Codex park review helper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


HELPER = Path(__file__).parents[1] / "codex/skills/park/scripts/park-review.py"
SPEC = importlib.util.spec_from_file_location("park_review", HELPER)
assert SPEC is not None and SPEC.loader is not None
park_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(park_review)


class ParkReviewTests(unittest.TestCase):
    def test_only_lint_is_an_accepted_verifier_failure_shape(self) -> None:
        self.assertTrue(
            park_review.verifier_failed_only_in_lint(
                {
                    "returncode": 1,
                    "text": "PASS sections: present\nFAIL lint: inherited blank lines\nRESULT: FAIL\n",
                }
            )
        )
        self.assertFalse(
            park_review.verifier_failed_only_in_lint(
                {
                    "returncode": 1,
                    "text": "FAIL lint: inherited blank lines\nFAIL backfill: missing\n",
                }
            )
        )

    def test_byte_identical_full_reads_share_one_read_group(self) -> None:
        digest = "a" * 64
        files = [
            {"path": "/repo/source.md", "sha256": digest, "reason": "source"},
            {"path": "/live/source.md", "sha256": digest, "reason": "live copy"},
        ]

        groups = park_review.group_full_reads(files)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["read_path"], "/repo/source.md")
        self.assertEqual(groups[0]["paths"], ["/repo/source.md", "/live/source.md"])
        self.assertEqual(groups[0]["reasons"], ["source", "live copy"])

    def test_files_list_keeps_hyphenated_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            target = vault / "07 System/Context - Technical Infrastructure.md"
            target.parent.mkdir(parents=True)
            target.write_text("fixture\n", encoding="utf-8")
            classifications = {str(target.resolve()): {"mode": "semantic"}}

            parsed = park_review.parse_file_lines(
                "- 07 System/Context - Technical Infrastructure.md - refreshed",
                vault,
                classifications,
            )

            self.assertEqual(
                parsed, ["07 System/Context - Technical Infrastructure.md"]
            )

    def test_joint_audit_receipt_is_invalidated_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_root = root / "audits"
            audit_root.mkdir()
            first = root / "first.md"
            second = root / "second.md"
            first.write_text("first\n", encoding="utf-8")
            second.write_text("second\n", encoding="utf-8")
            receipt = {
                "status": "clean",
                "captured_at": "2026-08-16T00:00:00+00:00",
                "files": [
                    {"path": str(first), "sha256": park_review.sha256(first)},
                    {"path": str(second), "sha256": park_review.sha256(second)},
                ],
            }
            (audit_root / "receipt.json").write_text(
                json.dumps(receipt), encoding="utf-8"
            )

            self.assertEqual(len(park_review.current_audit_receipts(audit_root)), 1)
            second.write_text("changed\n", encoding="utf-8")
            self.assertEqual(park_review.current_audit_receipts(audit_root), [])

    def test_attestation_binds_each_path_to_its_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.md"
            second = root / "second.md"
            first.write_text("first\n", encoding="utf-8")
            second.write_text("second\n", encoding="utf-8")
            first_hash = park_review.sha256(first)
            second_hash = park_review.sha256(second)
            files = [
                {"path": str(first), "sha256": first_hash},
                {"path": str(second), "sha256": second_hash},
            ]

            park_review.validate_report_attestations(
                f"ATTEST {first_hash} {first}\nATTEST {second_hash} {second}\n",
                files,
            )
            with self.assertRaises(SystemExit):
                park_review.validate_report_attestations(
                    f"ATTEST {second_hash} {first}\nATTEST {first_hash} {second}\n",
                    files,
                )


if __name__ == "__main__":
    unittest.main()
