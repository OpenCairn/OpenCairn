#!/usr/bin/env python3
"""Prepare hash-bound local artefacts for proportional park inspection."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile
import tempfile


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Bound input buffers independently of the source or extracted text size.
CHUNK_BYTES = 1024 * 1024
LINE_SEPARATORS = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"


def file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def text_stats(path: Path) -> tuple[int, bool]:
    """Validate all UTF-8 and count str.splitlines() lines with bounded buffers."""
    boundaries = 0
    last = ""
    nonblank = False
    with path.open("r", encoding="utf-8", newline="") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), ""):
            boundaries += sum(chunk.count(mark) for mark in LINE_SEPARATORS)
            boundaries -= chunk.count("\r\n")
            if last == "\r" and chunk.startswith("\n"):
                boundaries -= 1
            last = chunk[-1]
            nonblank = nonblank or bool(chunk.strip())
    return boundaries + int(bool(last) and last not in LINE_SEPARATORS), nonblank


def target_mode(path: Path) -> int:
    if path.exists():
        return stat.S_IMODE(path.stat().st_mode)
    current_umask = os.umask(0)
    os.umask(current_umask)
    return 0o666 & ~current_umask


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = target_mode(path)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    atomic_bytes(path, payload)


def persist_digest_file(directory: Path, digest: str, source: Path) -> Path:
    path = directory / f"{digest}.snapshot"
    directory.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if file_digest(path)[0] != digest:
            fail(f"digest-addressed artefact is corrupt: {path}")
        return path
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=directory)
    try:
        os.fchmod(fd, target_mode(path))
        copied_digest = hashlib.sha256()
        with os.fdopen(fd, "wb") as output, source.open("rb") as input_file:
            for chunk in iter(lambda: input_file.read(CHUNK_BYTES), b""):
                copied_digest.update(chunk)
                output.write(chunk)
        if copied_digest.hexdigest() != digest:
            fail(f"source changed during artefact preparation: {source}")
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
    return path


def reusable_receipt(receipt_path: Path, source_digest: str) -> dict | None:
    if not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(receipt, dict) or receipt.get("schema") != 1:
        return None
    if receipt.get("source_sha256") != source_digest:
        return None
    source_snapshot = Path(str(receipt.get("source_snapshot", "")))
    if not source_snapshot.is_file() or file_digest(source_snapshot)[0] != source_digest:
        return None
    review_raw = receipt.get("review_path")
    review_digest = receipt.get("review_sha256")
    if review_raw is not None or review_digest is not None:
        review_path = Path(str(review_raw))
        if (
            not isinstance(review_digest, str)
            or not review_path.is_file()
            or file_digest(review_path)[0] != review_digest
        ):
            return None
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def pdf_pages(path: Path) -> int | None:
    try:
        result = subprocess.run(
            ["pdfinfo", str(path)], text=True, capture_output=True, check=False
        )
    except FileNotFoundError:
        fail("pdfinfo is required to inspect PDF artefacts")
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit {result.returncode}"
        fail(f"cannot inspect PDF metadata: {detail}")
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    return int(match.group(1)) if match else None


def extract_pdf(snapshot: Path, review_path: Path) -> tuple[str, int, str]:
    review_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{review_path.name}.", dir=review_path.parent
    )
    os.close(fd)
    try:
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(snapshot), tmp_name],
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            fail("pdftotext is required to inspect PDF artefacts")
        if result.returncode != 0:
            detail = result.stderr.strip() or f"exit {result.returncode}"
            fail(f"cannot extract PDF text: {detail}")
        extracted = Path(tmp_name)
        digest, _ = file_digest(extracted)
        try:
            lines, nonblank = text_stats(extracted)
        except UnicodeDecodeError as exc:
            fail(f"PDF text extraction is not UTF-8: {exc}")
        if not review_path.exists() or file_digest(review_path)[0] != digest:
            extracted.chmod(target_mode(review_path))
            os.replace(extracted, review_path)
        status = "available" if nonblank else "empty"
        return digest, lines, status
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def prepare(source: Path, original: Path, state_dir: Path) -> dict:
    if not source.is_file():
        fail(f"source file missing: {source}")
    source_digest, source_size = file_digest(source)
    receipt_path = state_dir / "receipts" / f"{source_digest}.json"
    cached = reusable_receipt(receipt_path, source_digest)
    if cached is not None:
        cached["original_path"] = os.path.abspath(original)
        return cached
    source_snapshot = persist_digest_file(state_dir / "sources", source_digest, source)
    with source_snapshot.open("rb") as handle:
        prefix = handle.read(8)
    receipt: dict[str, object] = {
        "schema": 1,
        "prepared_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds"),
        "original_path": os.path.abspath(original),
        "source_sha256": source_digest,
        "source_snapshot": str(source_snapshot),
        "bytes": source_size,
    }

    if prefix.startswith(b"%PDF-"):
        review_path = state_dir / "reviews" / f"{source_digest}.pdf.txt"
        review_digest, review_lines, text_status = extract_pdf(
            source_snapshot, review_path
        )
        receipt.update(
            {
                "media_type": "application/pdf",
                "pages": pdf_pages(source_snapshot),
                "review_path": str(review_path),
                "review_sha256": review_digest,
                "review_lines": review_lines,
                "text_status": text_status,
            }
        )
    elif prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        receipt.update(
            {
                "media_type": "image/png",
                "review_path": None,
                "review_sha256": None,
                "review_lines": None,
                "text_status": "unsupported",
            }
        )
    elif tarfile.is_tarfile(source_snapshot):
        receipt.update(
            {
                "media_type": "application/x-tar",
                "review_path": None,
                "review_sha256": None,
                "review_lines": None,
                "text_status": "unsupported",
            }
        )
    else:
        try:
            lines, _ = text_stats(source_snapshot)
        except UnicodeDecodeError:
            receipt.update(
                {
                    "media_type": "application/octet-stream",
                    "review_path": None,
                    "review_sha256": None,
                    "review_lines": None,
                    "text_status": "unsupported",
                }
            )
        else:
            receipt.update(
                {
                    "media_type": "text/plain",
                    "review_path": str(source_snapshot),
                    "review_sha256": source_digest,
                    "review_lines": lines,
                    "text_status": "available",
                }
            )

    receipt["receipt_path"] = str(receipt_path)
    atomic_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--original")
    parser.add_argument("--state-dir", required=True)
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    original = Path(args.original or args.source).expanduser().absolute()
    receipt = prepare(source, original, Path(args.state_dir).expanduser().resolve())
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
