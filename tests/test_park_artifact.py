#!/usr/bin/env python3
"""Regression tests for proportional park artefact preparation."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


HELPER = Path(__file__).parents[1] / ".claude/scripts/park-artifact.py"
SPEC = importlib.util.spec_from_file_location("park_artifact", HELPER)
assert SPEC is not None and SPEC.loader is not None
park_artifact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(park_artifact)


class ParkArtifactTests(unittest.TestCase):
    def test_atomic_bytes_uses_umask_mode_for_missing_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "new.json"
            previous_umask = os.umask(0o027)
            try:
                park_artifact.atomic_bytes(target, b"new\n")
            finally:
                os.umask(previous_umask)

            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)

    def test_atomic_bytes_preserves_existing_target_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "existing.json"
            target.write_bytes(b"old\n")
            target.chmod(0o604)

            park_artifact.atomic_bytes(target, b"new\n")

            self.assertEqual(target.read_bytes(), b"new\n")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o604)

    def test_pdf_receipt_binds_source_metadata_and_review_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "textbook.pdf"
            source.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n")

            def fake_run(command, **_kwargs):
                if command[0] == "pdftotext":
                    Path(command[-1]).write_text("chapter text\n", encoding="utf-8")
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                return SimpleNamespace(returncode=0, stdout="Pages:          1000\n", stderr="")

            with mock.patch.object(
                park_artifact.subprocess, "run", side_effect=fake_run
            ):
                receipt = park_artifact.prepare(source, source, root / "state")

            self.assertEqual(receipt["media_type"], "application/pdf")
            self.assertEqual(receipt["pages"], 1000)
            self.assertEqual(receipt["review_lines"], 1)
            self.assertEqual(receipt["text_status"], "available")
            self.assertEqual(
                Path(receipt["source_snapshot"]).read_bytes(), source.read_bytes()
            )
            self.assertEqual(
                Path(receipt["review_path"]).read_text(encoding="utf-8"),
                "chapter text\n",
            )

    def test_textless_pdf_is_recorded_without_claiming_text_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scan.pdf"
            source.write_bytes(b"%PDF-1.4\n%%EOF\n")

            def fake_run(command, **_kwargs):
                if command[0] == "pdftotext":
                    Path(command[-1]).write_bytes(b"")
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                return SimpleNamespace(returncode=0, stdout="Pages:          12\n", stderr="")

            with mock.patch.object(
                park_artifact.subprocess, "run", side_effect=fake_run
            ):
                receipt = park_artifact.prepare(source, source, root / "state")

            self.assertEqual(receipt["text_status"], "empty")
            self.assertEqual(receipt["review_lines"], 0)

    def test_fresh_extraction_replaces_stale_review_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "manual.pdf"
            source.write_bytes(b"%PDF-1.4\n%%EOF\n")
            digest = park_artifact.sha256_bytes(source.read_bytes())
            review = root / "state/reviews" / f"{digest}.pdf.txt"
            review.parent.mkdir(parents=True)
            review.write_text("stale\n", encoding="utf-8")

            def fake_run(command, **_kwargs):
                if command[0] == "pdftotext":
                    Path(command[-1]).write_text("fresh\n", encoding="utf-8")
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                return SimpleNamespace(returncode=0, stdout="Pages:          2\n", stderr="")

            with mock.patch.object(
                park_artifact.subprocess, "run", side_effect=fake_run
            ):
                receipt = park_artifact.prepare(source, source, root / "state")

            self.assertEqual(Path(receipt["review_path"]).read_text(), "fresh\n")

    def test_valid_digest_receipt_reuses_index_without_reextracting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "textbook.pdf"
            source.write_bytes(b"%PDF-1.4\n%%EOF\n")

            def fake_run(command, **_kwargs):
                if command[0] == "pdftotext":
                    Path(command[-1]).write_text("indexed once\n", encoding="utf-8")
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                return SimpleNamespace(returncode=0, stdout="Pages:          1000\n", stderr="")

            with mock.patch.object(
                park_artifact.subprocess, "run", side_effect=fake_run
            ) as first_run:
                first = park_artifact.prepare(source, source, root / "state")
            with mock.patch.object(park_artifact.subprocess, "run") as second_run:
                second = park_artifact.prepare(source, source, root / "state")

            self.assertEqual(first["review_sha256"], second["review_sha256"])
            self.assertEqual(first_run.call_count, 2)
            second_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
