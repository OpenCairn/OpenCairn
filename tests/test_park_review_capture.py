"""End-to-end regression fixtures for completion and captured review evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(__file__).parents[1] / "codex/skills/park/scripts/park-review.py"


class TargetedCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="park-review-targeted-")
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.vault = self.base / "vault"
        self.vault.mkdir()
        self.config = self.base / "config"
        self.env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(self.base),
                    "VAULT_PATH": str(self.vault), "CLAUDE_CONFIG_DIR": str(self.config),
                    "OPENCAIRN_SESSION_ID": "targeted-fixture"}
        begun = self.run_review("begin-run")
        self.assertEqual(begun.returncode, 0, begun.stderr)
        self.root = Path(json.loads(begun.stdout)["root"])
        self.target = self.vault / "reference.txt"
        self.target.write_text("A retained reference passage.\n", encoding="utf-8")
        self.log = self.vault / "log.md"
        self.log.write_text(
            "## Session 1 - Fixture\n\n### Summary\nRetained a source.\n\n"
            "### Files Created\nNone\n\n"
            f"### Files Updated\n- `{self.target}` - reference\n- `{self.log}` - record\n\n"
            "### Pickup Context\n**For next session:** None.\n**Project:** None\n",
            encoding="utf-8")
        for path in (self.target, self.log):
            result = self.run_review("classify", "--vault", str(self.vault), "--path", str(path),
                                     "--semantic", "--targeted", "--inspection-target", "session delta")
            self.assertEqual(result.returncode, 0, result.stderr)
        for kind, text in (("propagation", "Checked empty enumeration."),):
            result = self.run_review("capture", "--kind", kind, "--label", "fixture", stdin=text)
            self.assertEqual(result.returncode, 0, result.stderr)
        verifier = self.run_review("run-verifier", "--", sys.executable, "-c", "print('RESULT: PASS')")
        self.assertEqual(verifier.returncode, 0, verifier.stderr)
        self.build()

    def run_review(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(HELPER), *args], env=self.env, input=stdin,
                              text=True, capture_output=True, timeout=60)

    def build(self) -> None:
        result = self.run_review("build", "--vault", str(self.vault), "--session-log", str(self.log),
                                 "--number", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.brief = self.root / "review-brief.md"
        self.report = f"COMPLETE {hashlib.sha256(self.brief.read_bytes()).hexdigest()}\nTerminal state: clean\n"

    def record(self, report: str | None = None) -> subprocess.CompletedProcess:
        return self.run_review("record-audit", "--reviewer", "fixture", "--from-brief",
                               stdin=self.report if report is None else report)

    def receipts(self) -> list[dict]:
        return [json.loads(p.read_text()) for p in
                (self.config / ".session-state/.park-audit-receipts").glob("*.json")]

    def test_all_targeted_clean_review_writes_completion_without_full_read_reuse(self):
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipts = self.receipts()
        self.assertEqual(len(receipts), 1, result.stdout)
        self.assertEqual(receipts[0]["status"], "clean")
        self.assertEqual(receipts[0]["files"], [])
        self.assertEqual(receipts[0]["reviewed_files"], [])
        self.assertEqual({p["path"] for p in receipts[0]["completion_files"]},
                         {str(self.target), str(self.log)})

    def test_all_targeted_rejects_wrong_or_missing_completion_digest(self):
        for report in ("Terminal state: clean\n", "COMPLETE " + "0" * 64 + "\nTerminal state: clean\n"):
            with self.subTest(report=report):
                result = self.record(report)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("completion attestation", result.stderr)
        self.assertEqual(self.receipts(), [])

    def test_targeted_source_change_rejects_old_completion(self):
        self.target.write_text("Changed after review.\n", encoding="utf-8")
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed after review", result.stderr)
        self.assertEqual(self.receipts(), [])

    def test_targeted_snapshot_and_brief_tampering_are_rejected(self):
        manifest = json.loads((self.root / "review-brief-manifest.json").read_text())
        snapshot = Path(manifest["targeted_review"][0]["source_snapshot"])
        snapshot.write_text("tampered snapshot", encoding="utf-8")
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("snapshot missing or corrupt", result.stderr)
        self.assertEqual(self.receipts(), [])
        self.brief.write_text("replacement brief", encoding="utf-8")
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("brief changed", result.stderr)

    def test_targeted_report_cannot_fake_a_full_read_attestation(self):
        report = "ATTEST " + hashlib.sha256(self.target.read_bytes()).hexdigest() + f" {self.target}\n" + self.report
        result = self.record(report)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected attestation", result.stderr)

    def test_added_capture_requires_rebuild(self):
        captured = self.run_review("capture", "--kind", "evidence", "--label", "late",
                                   "--source", "fixture", "--provenance", "primary", stdin="Late evidence.")
        self.assertEqual(captured.returncode, 0, captured.stderr)
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inputs changed", result.stderr)

    def test_stale_generation_remains_rejected(self):
        path = self.root / "review-brief-manifest.json"
        manifest = json.loads(path.read_text())
        manifest["run_generation"] = "0" * 32
        path.write_text(json.dumps(manifest))
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different park generation", result.stderr)
