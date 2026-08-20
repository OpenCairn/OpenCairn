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
import tempfile


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        target_mode = stat.S_IMODE(path.stat().st_mode)
    else:
        current_umask = os.umask(0)
        os.umask(current_umask)
        target_mode = 0o666 & ~current_umask
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, target_mode)
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


def persist_digest_bytes(directory: Path, digest: str, suffix: str, data: bytes) -> Path:
    path = directory / f"{digest}{suffix}"
    if path.exists() and path.read_bytes() != data:
        fail(f"digest-addressed artefact is corrupt: {path}")
    if not path.exists():
        atomic_bytes(path, data)
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
    if not source_snapshot.is_file() or sha256_bytes(source_snapshot.read_bytes()) != source_digest:
        return None
    review_raw = receipt.get("review_path")
    review_digest = receipt.get("review_sha256")
    if review_raw is not None or review_digest is not None:
        review_path = Path(str(review_raw))
        if (
            not isinstance(review_digest, str)
            or not review_path.is_file()
            or sha256_bytes(review_path.read_bytes()) != review_digest
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
        extracted = Path(tmp_name).read_bytes()
        try:
            text = extracted.decode("utf-8")
        except UnicodeDecodeError as exc:
            fail(f"PDF text extraction is not UTF-8: {exc}")
        if not review_path.exists() or review_path.read_bytes() != extracted:
            atomic_bytes(review_path, extracted)
        status = "available" if text.strip() else "empty"
        return sha256_bytes(extracted), len(text.splitlines()), status
    finally:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def prepare(source: Path, original: Path, state_dir: Path) -> dict:
    if not source.is_file():
        fail(f"source file missing: {source}")
    data = source.read_bytes()
    source_digest = sha256_bytes(data)
    receipt_path = state_dir / "receipts" / f"{source_digest}.json"
    cached = reusable_receipt(receipt_path, source_digest)
    if cached is not None:
        cached["original_path"] = str(original.resolve())
        return cached
    source_snapshot = persist_digest_bytes(
        state_dir / "sources", source_digest, ".snapshot", data
    )
    receipt: dict[str, object] = {
        "schema": 1,
        "prepared_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds"),
        "original_path": str(original.resolve()),
        "source_sha256": source_digest,
        "source_snapshot": str(source_snapshot),
        "bytes": len(data),
    }

    if data.startswith(b"%PDF-"):
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
    else:
        try:
            text = data.decode("utf-8")
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
                    "review_lines": len(text.splitlines()),
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
    original = Path(args.original).expanduser().resolve() if args.original else source
    receipt = prepare(source, original, Path(args.state_dir).expanduser().resolve())
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
