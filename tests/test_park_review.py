#!/usr/bin/env python3
"""Regression tests for the Codex park review helper."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


HELPER = Path(__file__).parents[1] / "codex/skills/park/scripts/park-review.py"
SPEC = importlib.util.spec_from_file_location("park_review", HELPER)
assert SPEC is not None and SPEC.loader is not None
park_review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(park_review)


class ParkReviewTests(unittest.TestCase):
    def test_only_mechanical_receipts_can_preapprove_inherited_lint(self) -> None:
        manifest = {
            "/vault/approved.md": {
                "mode": "mechanical",
                "verification": {"accepted_inherited_lint": ["old lint"]},
            },
            "/vault/clean.md": {
                "mode": "mechanical",
                "verification": {"accepted_inherited_lint": []},
            },
            "/vault/semantic.md": {
                "mode": "semantic",
                "verification": {"accepted_inherited_lint": ["not enough"]},
            },
        }

        self.assertEqual(
            park_review.approved_inherited_lint_paths(manifest),
            {"/vault/approved.md"},
        )

    def test_accepts_only_exact_path_scoped_inherited_lint(self) -> None:
        first = "/vault/history one.md"
        second = "/vault/history two.md"
        output = (
            f"FAIL lint: {first} 12: 3+ blank lines; "
            "9: continued historical evidence\n"
            f"10: more evidence; {second} joined-list: 8: prose- [ ] item; \n"
            "RESULT: FAIL (1 fail, 0 review)\n"
        )

        accepted, paths = park_review.accepted_inherited_lint(
            output, [first, second]
        )

        self.assertTrue(accepted)
        self.assertEqual(paths, [first, second])

    def test_rejects_inherited_lint_acceptance_when_any_other_issue_exists(self) -> None:
        path = "/vault/history.md"
        cases = [
            (
                f"FAIL lint: {path} 12: 3+ blank lines; \n"
                "FAIL separator: leaked token\n"
                "RESULT: FAIL (2 fail, 0 review)\n"
            ),
            (
                f"FAIL lint: {path} 12: 3+ blank lines; \n"
                "REVIEW closure: still open\n"
                "RESULT: FAIL (1 fail, 1 review)\n"
            ),
            (
                f"FAIL lint: {path} 12: 3+ blank lines; \n"
                "RESULT: FAIL (1 fail, 0 review)\n"
            ),
        ]

        self.assertFalse(
            park_review.accepted_inherited_lint(cases[0], [path])[0]
        )
        self.assertFalse(
            park_review.accepted_inherited_lint(cases[1], [path])[0]
        )
        self.assertFalse(
            park_review.accepted_inherited_lint(cases[2], ["/vault/other.md"])[0]
        )

    def test_byte_identical_full_reads_share_one_read_group(self) -> None:
        digest = "a" * 64
        files = [
            {
                "path": "/repo/source.md",
                "snapshot_path": "/snapshots/source",
                "sha256": digest,
                "reason": "source",
            },
            {
                "path": "/live/source.md",
                "snapshot_path": "/snapshots/source",
                "sha256": digest,
                "reason": "live copy",
            },
        ]

        groups = park_review.group_full_reads(files)

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["read_path"], "/snapshots/source")
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

    def test_snapshot_remains_stable_after_live_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "live.md"
            live.write_text("reviewed\n", encoding="utf-8")

            digest, snapshot = park_review.write_snapshot(root, live.read_bytes())
            live.write_text("changed later\n", encoding="utf-8")

            self.assertEqual(digest, park_review.sha256(snapshot))
            self.assertEqual(snapshot.read_text(encoding="utf-8"), "reviewed\n")

    def test_append_receipt_without_new_text_survives_later_line_shift(self) -> None:
        appended = "existing\nsession append\n"
        snapshot = "intro\nexisting\nsession append\n"
        append_digest = park_review.sha256_bytes(appended.encode())
        digest = park_review.sha256_bytes(snapshot.encode())
        receipts = [
            {
                "mode": "--append",
                "pre_sha256": "a" * 64,
                "post_sha256": append_digest,
                "new_text": None,
                "changed_ranges": [
                    {
                        "tag": "insert",
                        "before_start": 2,
                        "before_end": 1,
                        "after_start": 2,
                        "after_end": 2,
                    }
                ],
                "ranges_truncated": False,
                "unified_diff": "--- before\n+++ after\n@@ -0,0 +1 @@\n+session append\n",
                "diff_truncated": False,
            },
            {
                "mode": "--replace",
                "pre_sha256": append_digest,
                "post_sha256": digest,
                "new_text": "intro",
            },
        ]

        self.assertEqual(
            park_review.owned_locators(receipts, digest, snapshot),
            ["session append", "intro"],
        )

    def test_replace_whole_receipt_without_new_text_owns_snapshot(self) -> None:
        snapshot = "session replacement\n"
        digest = park_review.sha256_bytes(snapshot.encode())
        receipts = [
            {
                "mode": "--replace-whole",
                "pre_sha256": "a" * 64,
                "post_sha256": digest,
                "new_text": None,
            }
        ]

        self.assertEqual(
            park_review.owned_locators(receipts, digest, snapshot), [snapshot]
        )

    def test_append_line_starting_plus_plus_plus_is_not_diff_header(self) -> None:
        snapshot = "existing\n+++ session append\n"
        digest = park_review.sha256_bytes(snapshot.encode())
        receipts = [
            {
                "mode": "--append",
                "pre_sha256": "a" * 64,
                "post_sha256": digest,
                "new_text": None,
                "unified_diff": (
                    "--- before\n+++ after\n@@ -0,0 +1 @@\n++++ session append\n"
                ),
                "diff_truncated": False,
            }
        ]

        locators, complete = park_review.owned_locator_evidence(
            receipts, digest, snapshot
        )

        self.assertTrue(complete)
        self.assertEqual(locators, ["+++ session append"])

    def test_truncated_append_marks_ownership_evidence_incomplete(self) -> None:
        snapshot = "existing\nsession append\n"
        digest = park_review.sha256_bytes(snapshot.encode())
        receipts = [
            {
                "mode": "--append",
                "pre_sha256": "a" * 64,
                "post_sha256": digest,
                "new_text": None,
                "unified_diff": "+session append\n[diff truncated]\n",
                "diff_truncated": True,
            }
        ]

        locators, complete = park_review.owned_locator_evidence(
            receipts, digest, snapshot
        )

        self.assertFalse(complete)
        self.assertEqual(locators, [])

    def test_exact_same_session_supersession_remains_complete(self) -> None:
        snapshot = "final\n"
        first_digest = "b" * 64
        digest = park_review.sha256_bytes(snapshot.encode())
        receipts = [
            {
                "mode": "--replace",
                "pre_sha256": "a" * 64,
                "post_sha256": first_digest,
                "old_text": "old",
                "new_text": "interim",
                "old_text_truncated": False,
                "new_text_truncated": False,
            },
            {
                "mode": "--replace",
                "pre_sha256": first_digest,
                "post_sha256": digest,
                "old_text": "interim",
                "new_text": "final",
                "old_text_truncated": False,
                "new_text_truncated": False,
            },
        ]

        locators, complete = park_review.owned_locator_evidence(
            receipts, digest, snapshot
        )

        self.assertTrue(complete)
        self.assertEqual(locators, ["final"])

    def test_partial_same_session_supersession_remains_incomplete(self) -> None:
        snapshot = "interim long-tail\n"
        first_digest = "b" * 64
        digest = park_review.sha256_bytes(snapshot.encode())
        receipts = [
            {
                "mode": "--replace",
                "pre_sha256": "a" * 64,
                "post_sha256": first_digest,
                "old_text": "old",
                "new_text": "interim longtail",
            },
            {
                "mode": "--replace",
                "pre_sha256": first_digest,
                "post_sha256": digest,
                "old_text": "longtail",
                "new_text": "long-tail",
            },
        ]

        _, complete = park_review.owned_locator_evidence(receipts, digest, snapshot)

        self.assertFalse(complete)

    def test_build_points_reviewer_at_immutable_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / "config"
            state = config / ".session-state"
            root = state / "session.park-review"
            vault = base / "vault"
            target = vault / "target.md"
            log = vault / "log.md"
            target.parent.mkdir(parents=True)
            target.write_text("reviewed target\n", encoding="utf-8")
            log.write_text(
                "# Sessions\n\n"
                "## Session 1 - Fixture\n\n"
                "### Summary\nDone.\n\n"
                "### Key Insights / Decisions\n- None\n\n"
                "### Next Steps / Open Loops\n- None\n\n"
                "### Files Created\nNone\n\n"
                f"### Files Updated\n- {target} - reviewed\n- {log} - recorded\n\n"
                "### Pickup Context\n**For next session:** None.\n**Project:** None\n",
                encoding="utf-8",
            )
            captures = root / "captures"
            captures.mkdir(parents=True)
            park_review.atomic_json(
                root / "files.json",
                {
                    str(target): {"mode": "semantic", "reason": "fixture target"},
                    str(log): {"mode": "semantic", "reason": "fixture session log"},
                },
            )
            park_review.atomic_json(
                captures / "propagation.json",
                {"kind": "propagation", "captured_at": "1", "text": "checked"},
            )
            park_review.atomic_json(
                captures / "verifier.json",
                {
                    "kind": "verifier",
                    "captured_at": "2",
                    "text": "RESULT: PASS",
                    "returncode": 0,
                },
            )
            args = SimpleNamespace(
                session_id="session",
                vault=str(vault),
                session_log=str(log),
                number=1,
                out=None,
            )

            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}):
                self.assertEqual(park_review.cmd_build(args), 0)

            manifest = json.loads(
                (root / "review-brief-manifest.json").read_text(encoding="utf-8")
            )
            target_item = next(
                item for item in manifest["full_read"] if item["path"] == str(target)
            )
            snapshot = Path(target_item["snapshot_path"])
            self.assertEqual(snapshot.read_text(encoding="utf-8"), "reviewed target\n")
            target.write_text("changed live\n", encoding="utf-8")
            self.assertEqual(snapshot.read_text(encoding="utf-8"), "reviewed target\n")
            brief = (root / "review-brief.md").read_text(encoding="utf-8")
            self.assertIn(f"Read immutable snapshot once: `{snapshot}`", brief)
            self.assertNotIn(f"Read immutable snapshot once: `{target}`", brief)

    def test_traceable_disjoint_live_edit_keeps_snapshot_audit_nonreusable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / "config"
            state = config / ".session-state"
            root = state / "session.park-review"
            target = base / "target.md"
            before = "owned session line\nunrelated old\n"
            after = "owned session line\nunrelated new\n"
            target.write_text(before, encoding="utf-8")
            digest, snapshot = park_review.write_snapshot(root, target.read_bytes())
            manifest = {
                "schema": 1,
                "built_at": "2026-08-16T00:00:00+00:00",
                "full_read": [
                    {
                        "path": str(target),
                        "sha256": digest,
                        "snapshot_path": str(snapshot),
                        "owned_locators": ["owned session line"],
                    }
                ],
            }
            park_review.atomic_json(root / "review-brief-manifest.json", manifest)
            target.write_text(after, encoding="utf-8")
            other_receipts = state / "other.locked-edit-receipts"
            other_receipts.mkdir(parents=True)
            park_review.atomic_json(
                other_receipts / "receipt.json",
                {
                    "captured_at": "2026-08-16T00:01:00+00:00",
                    "target": str(target),
                    "mode": "--replace",
                    "pre_sha256": digest,
                    "post_sha256": park_review.sha256(target),
                    "old_text": "unrelated old",
                    "new_text": "unrelated new",
                },
            )
            report = f"ATTEST {digest} {target}\nTerminal state: clean\n"
            args = SimpleNamespace(
                session_id="session",
                vault=None,
                from_brief=True,
                file=None,
                reviewer="fixture",
            )

            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}), mock.patch(
                "sys.stdin", io.StringIO(report)
            ):
                self.assertEqual(park_review.cmd_record_audit(args), 0)

            receipts = list((state / ".park-audit-receipts").glob("*.json"))
            self.assertEqual(len(receipts), 1)
            recorded = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(recorded["files"], [])
            self.assertEqual(recorded["reviewed_files"][0]["path"], str(target))
            self.assertEqual(recorded["post_review_changes"][0]["path"], str(target))
            self.assertEqual(
                park_review.current_audit_receipts(state / ".park-audit-receipts"), []
            )

    def test_traceable_overlapping_live_edit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / "config"
            state = config / ".session-state"
            root = state / "session.park-review"
            target = base / "target.md"
            target.write_text("owned session line\n", encoding="utf-8")
            digest, snapshot = park_review.write_snapshot(root, target.read_bytes())
            park_review.atomic_json(
                root / "review-brief-manifest.json",
                {
                    "built_at": "2026-08-16T00:00:00+00:00",
                    "full_read": [
                        {
                            "path": str(target),
                            "sha256": digest,
                            "snapshot_path": str(snapshot),
                            "owned_locators": ["owned session line"],
                        }
                    ],
                },
            )
            target.write_text("owned session line [clarified]\n", encoding="utf-8")
            other_receipts = state / "other.locked-edit-receipts"
            other_receipts.mkdir(parents=True)
            park_review.atomic_json(
                other_receipts / "receipt.json",
                {
                    "captured_at": "2026-08-16T00:01:00+00:00",
                    "target": str(target),
                    "mode": "--replace",
                    "pre_sha256": digest,
                    "post_sha256": park_review.sha256(target),
                    "old_text": "owned session line",
                    "new_text": "owned session line [clarified]",
                },
            )
            report = f"ATTEST {digest} {target}\nTerminal state: clean\n"
            args = SimpleNamespace(
                session_id="session",
                vault=None,
                from_brief=True,
                file=None,
                reviewer="fixture",
            )

            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}), mock.patch(
                "sys.stdin", io.StringIO(report)
            ), self.assertRaises(SystemExit) as caught:
                park_review.cmd_record_audit(args)

            self.assertIn("overlapped session-owned content", str(caught.exception))

    def test_current_session_post_snapshot_edits_require_new_review(self) -> None:
        for mode, before, after, payload in (
            (
                "--append",
                "owned session line\n",
                "owned session line\nlate session line\n",
                {"new_text": "late session line\n"},
            ),
            (
                "--replace",
                "owned session line\nunrelated old\n",
                "owned session line\nunrelated new\n",
                {"old_text": "unrelated old", "new_text": "unrelated new"},
            ),
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                config = base / "config"
                state = config / ".session-state"
                root = state / "session.park-review"
                target = base / "target.md"
                target.write_text(before, encoding="utf-8")
                digest, snapshot = park_review.write_snapshot(root, target.read_bytes())
                park_review.atomic_json(
                    root / "review-brief-manifest.json",
                    {
                        "built_at": "2026-08-16T00:00:00+00:00",
                        "full_read": [
                            {
                                "path": str(target),
                                "sha256": digest,
                                "snapshot_path": str(snapshot),
                                "owned_locators": ["owned session line"],
                            }
                        ],
                    },
                )
                target.write_text(after, encoding="utf-8")
                own_receipts = state / "session.locked-edit-receipts"
                own_receipts.mkdir(parents=True)
                park_review.atomic_json(
                    own_receipts / "receipt.json",
                    {
                        "captured_at": "2026-08-16T00:01:00+00:00",
                        "target": str(target),
                        "mode": mode,
                        "pre_sha256": digest,
                        "post_sha256": park_review.sha256(target),
                        **payload,
                    },
                )
                report = f"ATTEST {digest} {target}\nTerminal state: clean\n"
                args = SimpleNamespace(
                    session_id="session",
                    vault=None,
                    from_brief=True,
                    file=None,
                    reviewer="fixture",
                )

                with mock.patch.dict(
                    os.environ, {"CLAUDE_CONFIG_DIR": str(config)}
                ), mock.patch("sys.stdin", io.StringIO(report)), self.assertRaises(
                    SystemExit
                ) as caught:
                    park_review.cmd_record_audit(args)

                self.assertIn("rebuild brief", str(caught.exception))

    def test_unreceipted_live_edit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / "config"
            state = config / ".session-state"
            root = state / "session.park-review"
            target = base / "target.md"
            target.write_text("owned session line\n", encoding="utf-8")
            digest, snapshot = park_review.write_snapshot(root, target.read_bytes())
            park_review.atomic_json(
                root / "review-brief-manifest.json",
                {
                    "built_at": "2026-08-16T00:00:00+00:00",
                    "full_read": [
                        {
                            "path": str(target),
                            "sha256": digest,
                            "snapshot_path": str(snapshot),
                            "owned_locators": ["owned session line"],
                        }
                    ],
                },
            )
            target.write_text("unreceipted change\n", encoding="utf-8")
            report = f"ATTEST {digest} {target}\nTerminal state: clean\n"
            args = SimpleNamespace(
                session_id="session",
                vault=None,
                from_brief=True,
                file=None,
                reviewer="fixture",
            )

            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}), mock.patch(
                "sys.stdin", io.StringIO(report)
            ), self.assertRaises(SystemExit) as caught:
                park_review.cmd_record_audit(args)

            self.assertIn("untraceable live change", str(caught.exception))

    def test_live_change_during_receipt_finalisation_invalidates_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / "config"
            state = config / ".session-state"
            root = state / "session.park-review"
            vault = base / "vault"
            target = vault / "target.md"
            target.parent.mkdir(parents=True)
            target.write_text("reviewed\n", encoding="utf-8")
            digest, snapshot = park_review.write_snapshot(root, target.read_bytes())
            park_review.atomic_json(
                root / "review-brief-manifest.json",
                {
                    "schema": 2,
                    "built_at": "2026-08-16T00:00:00+00:00",
                    "vault": str(vault),
                    "full_read": [
                        {
                            "path": str(target),
                            "sha256": digest,
                            "snapshot_path": str(snapshot),
                            "owned_locators": ["reviewed"],
                        }
                    ],
                },
            )
            report = f"ATTEST {digest} {target}\nTerminal state: clean\n"
            args = SimpleNamespace(
                session_id="session",
                vault=None,
                from_brief=True,
                file=None,
                reviewer="fixture",
            )
            real_atomic_json = park_review.atomic_json
            changed = False

            def mutate_after_pending_receipt(path: Path, data: object) -> None:
                nonlocal changed
                real_atomic_json(path, data)
                if (
                    not changed
                    and isinstance(data, dict)
                    and data.get("status") == "pending"
                    and path.parent.name == ".park-audit-receipts"
                ):
                    changed = True
                    target.write_text("raced\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(config)}), mock.patch(
                "sys.stdin", io.StringIO(report)
            ), mock.patch.object(
                park_review, "atomic_json", side_effect=mutate_after_pending_receipt
            ), self.assertRaises(SystemExit) as caught:
                park_review.cmd_record_audit(args)

            self.assertIn("changed during audit receipt finalisation", str(caught.exception))
            receipts = list((state / ".park-audit-receipts").glob("*.json"))
            self.assertEqual(len(receipts), 1)
            recorded = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(recorded["status"], "invalidated")

    def test_interruption_after_pending_receipt_never_publishes_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / "config"
            state = config / ".session-state"
            root = state / "session.park-review"
            target = base / "target.md"
            target.write_text("reviewed\n", encoding="utf-8")
            digest, snapshot = park_review.write_snapshot(root, target.read_bytes())
            park_review.atomic_json(
                root / "review-brief-manifest.json",
                {
                    "built_at": "2026-08-16T00:00:00+00:00",
                    "full_read": [
                        {
                            "path": str(target),
                            "sha256": digest,
                            "snapshot_path": str(snapshot),
                            "owned_locators": ["reviewed"],
                        }
                    ],
                },
            )
            report = f"ATTEST {digest} {target}\nTerminal state: clean\n"
            args = SimpleNamespace(
                session_id="session",
                vault=None,
                from_brief=True,
                file=None,
                reviewer="fixture",
            )
            real_atomic_json = park_review.atomic_json

            def interrupt_after_pending(path: Path, data: object) -> None:
                real_atomic_json(path, data)
                if (
                    isinstance(data, dict)
                    and data.get("status") == "pending"
                    and path.parent.name == ".park-audit-receipts"
                ):
                    raise RuntimeError("simulated interruption")

            with mock.patch.dict(
                os.environ, {"CLAUDE_CONFIG_DIR": str(config)}
            ), mock.patch("sys.stdin", io.StringIO(report)), mock.patch.object(
                park_review, "atomic_json", side_effect=interrupt_after_pending
            ), self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                park_review.cmd_record_audit(args)

            receipts = list((state / ".park-audit-receipts").glob("*.json"))
            self.assertEqual(len(receipts), 1)
            recorded = json.loads(receipts[0].read_text(encoding="utf-8"))
            self.assertEqual(recorded["status"], "pending")
            self.assertEqual(
                park_review.current_audit_receipts(state / ".park-audit-receipts"), []
            )


if __name__ == "__main__":
    unittest.main()
