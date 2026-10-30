#!/usr/bin/env python3
"""Regression tests for proportional park artefact preparation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
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
    @unittest.skipUnless(sys.platform == "linux", "uses Linux address-space limits")
    def test_large_sparse_binary_and_cache_fit_bounded_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "large.gguf"
            size = 256 * 1024 * 1024
            with source.open("wb") as handle:
                handle.write(b"GGUF\x00\xff")
                handle.truncate(size)
            limit = 128 * 1024 * 1024
            runner = (
                "import resource,runpy,sys; "
                f"resource.setrlimit(resource.RLIMIT_AS, ({limit}, {limit})); "
                "sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
            )
            command = [sys.executable, "-c", runner, str(HELPER), "--source", str(source),
                       "--state-dir", str(root / "state")]
            digest = hashlib.sha256()
            with source.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            first = None
            for attempt in range(2):
                result = subprocess.run(command, text=True, capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stderr)
                receipt = json.loads(result.stdout)
                self.assertEqual(receipt["source_sha256"], digest.hexdigest())
                self.assertEqual(receipt["bytes"], size)
                self.assertEqual(receipt["text_status"], "unsupported")
                self.assertIsNone(receipt["review_path"])
                if attempt == 0:
                    first = receipt
                else:
                    self.assertEqual(receipt, first)
            snapshot = Path(receipt["source_snapshot"])
            with snapshot.open("r+b") as handle:
                handle.seek(size - 1)
                handle.write(b"x")
            rejected = subprocess.run(command, text=True, capture_output=True, timeout=60)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("digest-addressed artefact is corrupt", rejected.stderr)
            # A large valid UTF-8 source also needs a complete, bounded text probe.
            with source.open("r+b") as handle:
                handle.write(b"plain:")
            text_result = subprocess.run(command, text=True, capture_output=True, timeout=60)
            self.assertEqual(text_result.returncode, 0, text_result.stderr)
            text_receipt = json.loads(text_result.stdout)
            self.assertEqual(text_receipt["media_type"], "text/plain")
            self.assertEqual(text_receipt["text_status"], "available")
            self.assertEqual(text_receipt["review_lines"], 1)
            text_cached = subprocess.run(command, text=True, capture_output=True, timeout=60)
            self.assertEqual(text_cached.returncode, 0, text_cached.stderr)
            self.assertEqual(json.loads(text_cached.stdout), text_receipt)

    @unittest.skipUnless(sys.platform == "linux", "uses Linux address-space limits")
    def test_large_pdf_extraction_fits_bounded_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.pdf"
            source.write_bytes(b"%PDF-1.4\n%%EOF\n")
            runner = """
import resource, runpy, sys
from pathlib import Path
from types import SimpleNamespace
limit = 128 * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
helper = runpy.run_path(sys.argv[1])
def fake_run(command, **kwargs):
    if command[0] == "pdftotext":
        with Path(command[-1]).open("wb") as handle:
            handle.write(b"extracted text")
            handle.truncate(256 * 1024 * 1024)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    return SimpleNamespace(returncode=0, stdout="Pages: 1\\n", stderr="")
helper["subprocess"].run = fake_run
source = Path(sys.argv[2])
receipt = helper["prepare"](source, source, Path(sys.argv[3]))
print(helper["json"].dumps(receipt))
"""
            result = subprocess.run(
                [sys.executable, "-c", runner, str(HELPER), str(source), str(root / "state")],
                text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt["media_type"], "application/pdf")
            self.assertEqual(receipt["pages"], 1)
            self.assertEqual(receipt["text_status"], "available")
            self.assertEqual(receipt["review_lines"], 1)
            self.assertEqual(Path(receipt["review_path"]).stat().st_size, 256 * 1024 * 1024)

    def test_text_line_counts_and_late_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "text.txt"
            # Exercise CRLF and a multibyte separator at streamed read boundaries.
            text = "a" * (1024 * 1024 - 1) + "\r\n" + "\u2028" + "b\rnext\vlast"
            source.write_text(text, encoding="utf-8")
            receipt = park_artifact.prepare(source, source, root / "state")
            self.assertEqual(receipt["review_lines"], len(text.splitlines()))
            self.assertEqual(receipt["text_status"], "available")
            with source.open("ab") as handle:
                handle.write(b"\xff")
            invalid = park_artifact.prepare(source, source, root / "state")
            self.assertEqual(invalid["text_status"], "unsupported")
            self.assertIsNone(invalid["review_path"])

    def test_source_changed_during_snapshot_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_bytes(b"original")
            expected = hashlib.sha256(b"original").hexdigest()
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(SystemExit, "source changed during artefact preparation"):
                park_artifact.persist_digest_file(root / "snapshots", expected, source)
            self.assertEqual(list((root / "snapshots").iterdir()), [])

    def test_tampered_cached_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_text("original\n", encoding="utf-8")
            receipt = park_artifact.prepare(source, source, root / "state")
            Path(receipt["source_snapshot"]).write_text("modified\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "digest-addressed artefact is corrupt"):
                park_artifact.prepare(source, source, root / "state")

    def test_original_symlink_spelling_is_retained_with_shared_physical_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.txt'
            source.write_text('Shared source bytes\n')
            installed = root / 'installed.txt'
            installed.symlink_to(source)
            first = park_artifact.prepare(source, source, root / 'state')
            linked = park_artifact.prepare(installed, installed, root / 'state')
            self.assertEqual(linked['original_path'], str(installed))
            self.assertEqual(linked['source_snapshot'], first['source_snapshot'])

    def test_png_and_tar_receipts_remain_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            png = root / "image.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
            payload = root / "payload.txt"
            payload.write_text("fixture\n", encoding="utf-8")
            archive = root / "bundle.tar"
            with tarfile.open(archive, "w") as handle:
                handle.add(payload, arcname="payload.txt")

            expected = {png: "image/png", archive: "application/x-tar"}
            for source, media_type in expected.items():
                with self.subTest(source=source.name):
                    receipt = park_artifact.prepare(source, source, root / "state")
                    self.assertEqual(receipt["media_type"], media_type)
                    self.assertEqual(receipt["text_status"], "unsupported")
                    self.assertIsNone(receipt["review_path"])
                    self.assertEqual(
                        Path(receipt["source_snapshot"]).read_bytes(),
                        source.read_bytes(),
                    )

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
            Path(second["review_path"]).write_text("tampered index\n", encoding="utf-8")
            with mock.patch.object(
                park_artifact.subprocess, "run", side_effect=fake_run
            ) as repaired_run:
                repaired = park_artifact.prepare(source, source, root / "state")
            self.assertEqual(repaired_run.call_count, 2)
            self.assertEqual(Path(repaired["review_path"]).read_text(), "indexed once\n")


if __name__ == "__main__":
    unittest.main()
