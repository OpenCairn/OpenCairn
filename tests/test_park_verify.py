import subprocess
import hashlib
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/park-verify.sh"


class ParkVerifyTests(unittest.TestCase):
    def test_external_reference_quotes_are_hash_bound_and_still_need_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault = base / 'vault'
            (vault / '01 Now').mkdir(parents=True)
            reference = base / 'audit.err'
            reference.write_text('```bash\n========OPENCAIRN-LOCKED-EDIT-SEP========\n```\n')
            digest = hashlib.sha256(reference.read_bytes()).hexdigest()
            log = vault / 'log.md'
            def invoke(extra, listed=True):
                log.write_text('## Session 1 - Fixture\n### Summary\nDone\n'
                               '### Files Created\nNone\n### Files Updated\n'
                               + (f'- {reference} - evidence\n' if listed else 'None\n')
                               + '### Pickup Context\n**Project:** None\n')
                return subprocess.run([str(SCRIPT), str(vault), str(log), '1',
                                       '--touched', str(reference), *extra],
                                      text=True, capture_output=True,
                                      env=dict(os.environ, PYTHONOPTIMIZE="1"))
            self.assertIn('FAIL separator', invoke([]).stdout)
            accepted = invoke(['--reference', str(reference), digest])
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            self.assertIn('RESULT: PASS', accepted.stdout)
            self.assertIn('FAIL reference', invoke(['--reference', str(reference), '0' * 64]).stdout)
            self.assertIn('FAIL backfill', invoke(['--reference', str(reference), digest], listed=False).stdout)
            self.assertIn('FAIL reference', invoke(['--reference', str(log), digest]).stdout)
            reference = vault / 'inside.md'
            reference.write_text('```bash\n========OPENCAIRN-LOCKED-EDIT-SEP========\n```\n')
            self.assertIn('FAIL reference', invoke(['--reference', str(reference), digest]).stdout)

    def test_duplicate_touched_spellings_preserve_distinct_external_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault = base / 'vault'
            (vault / '01 Now').mkdir(parents=True)
            (vault / 'docs').mkdir()
            inside = vault / 'docs/a.md'
            inside.write_text('inside\n')
            outside = base / 'external/docs/a.md'
            outside.parent.mkdir(parents=True)
            outside.write_text('outside\n')
            log = vault / 'log.md'
            for include_external in (True, False):
                with self.subTest(include_external=include_external):
                    log.write_text('## Session 1 - Fixture\n### Summary\nDone\n'
                                   '### Files Created\nNone\n### Files Updated\n'
                                   '- docs/a.md - inside\n'
                                   + (f'- {outside} - outside\n' if include_external else '')
                                   + '### Pickup Context\n**Project:** None\n')
                    result = subprocess.run(
                        [str(SCRIPT), str(vault), str(log), '1',
                         '--touched', 'docs/a.md', '--touched', str(inside),
                         '--touched', './docs/a.md', '--touched', str(outside)],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0 if include_external else 1, result.stdout)
                    if include_external:
                        self.assertIn('PASS backfill: all 2 path(s)', result.stdout)
                        self.assertIn('RESULT: PASS', result.stdout)
                    else:
                        self.assertIn('FAIL backfill:', result.stdout)
                        self.assertIn(str(outside), result.stdout)

    def test_sparse_quick_entry_with_all_none_file_sections_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "01 Now").mkdir(parents=True)
            (vault / "01 Now/This Week.md").write_text("# This Week\n", encoding="utf-8")
            (vault / "01 Now/Tickler.md").write_text("# Tickler\n", encoding="utf-8")
            log = vault / "06 Archive/OpenCairn/Session Logs/2026-08-19.md"
            log.parent.mkdir(parents=True)
            log.write_text(
                "\n".join(
                    [
                        "## Session 1 - Read-only discussion",
                        "### Summary",
                        "Discussion completed without durable changes.",
                        "### Key Insights / Decisions",
                        "None",
                        "### Next Steps / Open Loops",
                        "None — work completed",
                        "### Files Created",
                        "None",
                        "### Files Updated",
                        "None",
                        "### Files Deleted",
                        "None",
                        "### Pickup Context",
                        "**For next session:** None — work completed",
                        "**Project:** None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [str(SCRIPT), str(vault), str(log), "1"],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS closure: no idents supplied", result.stdout)
            self.assertIn("RESULT: PASS", result.stdout)
            self.assertNotIn("REVIEW backfill", result.stdout)

    def test_large_session_block_does_not_false_fail_early_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "01 Now").mkdir(parents=True)
            (vault / "01 Now/This Week.md").write_text("# This Week\n", encoding="utf-8")
            (vault / "01 Now/Tickler.md").write_text("# Tickler\n", encoding="utf-8")
            log = vault / "06 Archive/OpenCairn/Session Logs/2026-08-16.md"
            log.parent.mkdir(parents=True)
            log.write_text(
                "\n".join(
                    [
                        "## Session 1 - Large test",
                        "### Summary",
                        "Done.",
                        "### Files Created",
                        "- None",
                        "### Files Updated",
                        *(["- None"] * 20_000),
                        "### Pickup Context",
                        "**For next session:** None",
                        "**Project:** None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [str(SCRIPT), str(vault), str(log), "1"],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RESULT: PASS", result.stdout)

    def test_root_path_none_and_session_log_reverse_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "01 Now").mkdir(parents=True)
            (vault / "01 Now/This Week.md").write_text("# This Week\n", encoding="utf-8")
            (vault / "01 Now/Tickler.md").write_text("# Tickler\n", encoding="utf-8")
            log = vault / "06 Archive/OpenCairn/Session Logs/2026-08-16.md"
            log.parent.mkdir(parents=True)

            with tempfile.NamedTemporaryFile(
                dir="/tmp", prefix="opencairn-park-verify-", delete=False
            ) as handle:
                root_file = Path(handle.name)
            self.addCleanup(root_file.unlink, missing_ok=True)

            relative_log = log.relative_to(vault)
            log.write_text(
                "\n".join(
                    [
                        "## Session 1 - Test",
                        "### Summary",
                        "Done.",
                        "### Files Created",
                        "- None",
                        "### Files Updated",
                        f"- {root_file} - root-level artefact",
                        f"- {relative_log} - session record",
                        "### Pickup Context",
                        "**For next session:** None",
                        "**Project:** None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(SCRIPT),
                    str(vault),
                    str(log),
                    "1",
                    "--touched",
                    str(root_file),
                    "--touched",
                    str(log),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RESULT: PASS", result.stdout)
            self.assertNotIn("//tmp/", result.stdout)
            self.assertNotIn("--touched None", result.stdout)

    def test_verbatim_transcript_export_skips_separator_and_lint_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "01 Now").mkdir(parents=True)
            (vault / "01 Now/This Week.md").write_text("# This Week\n", encoding="utf-8")
            (vault / "01 Now/Tickler.md").write_text("# Tickler\n", encoding="utf-8")
            transcript = vault / "06 Archive/OpenCairn/.Session Transcripts/2026-08-22.md"
            transcript.parent.mkdir(parents=True)
            transcript.write_text(
                "source shell snippet\n========OPENCAIRN-LOCKED-EDIT-SEP========\n\n\n\n",
                encoding="utf-8",
            )
            log = vault / "06 Archive/OpenCairn/Session Logs/2026-08-22.md"
            log.parent.mkdir(parents=True)
            log.write_text(
                "\n".join(
                    [
                        "## Session 1 - Transcript export",
                        "### Summary",
                        "Exported verbatim source turns.",
                        "### Files Created",
                        "None",
                        "### Files Updated",
                        "- 06 Archive/OpenCairn/.Session Transcripts/2026-08-22.md - rolling export",
                        "### Pickup Context",
                        "**For next session:** None",
                        "**Project:** None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(SCRIPT),
                    str(vault),
                    str(log),
                    "1",
                    "--touched",
                    str(transcript),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RESULT: PASS", result.stdout)
            self.assertIn(
                "PASS separator: no leftover separator tokens (3 scanned, 1 skipped)",
                result.stdout,
            )
            self.assertNotIn("FAIL separator", result.stdout)
            self.assertNotIn("FAIL lint", result.stdout)

    def test_provenance_snapshot_skips_separator_and_lint_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "01 Now").mkdir(parents=True)
            (vault / "01 Now/This Week.md").write_text("# This Week\n", encoding="utf-8")
            (vault / "01 Now/Tickler.md").write_text("# Tickler\n", encoding="utf-8")
            snapshot = vault / "07 System/.Provenance/2026-08-22-transcript.snapshot.md"
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(
                "source shell snippet\nsource- [ ] literal source list\n"
                "========OPENCAIRN-LOCKED-EDIT-SEP========\n\n\n\n",
                encoding="utf-8",
            )
            log = vault / "06 Archive/OpenCairn/Session Logs/2026-08-23.md"
            log.parent.mkdir(parents=True)
            log.write_text(
                "\n".join(
                    [
                        "## Session 1 - Provenance snapshot",
                        "### Summary",
                        "Preserved exact source bytes.",
                        "### Files Created",
                        "- 07 System/.Provenance/2026-08-22-transcript.snapshot.md - frozen preimage",
                        "### Files Updated",
                        "None",
                        "### Pickup Context",
                        "**For next session:** None",
                        "**Project:** None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    str(SCRIPT),
                    str(vault),
                    str(log),
                    "1",
                    "--touched",
                    str(snapshot),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RESULT: PASS", result.stdout)
            self.assertIn(
                "PASS separator: no leftover separator tokens (3 scanned, 1 skipped)",
                result.stdout,
            )
            self.assertNotIn("FAIL separator", result.stdout)
            self.assertNotIn("FAIL lint", result.stdout)


if __name__ == "__main__":
    unittest.main()
