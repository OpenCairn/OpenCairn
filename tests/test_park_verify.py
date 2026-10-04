import subprocess
import hashlib
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/park-verify.sh"


def make_vault(base: Path) -> Path:
    vault = base / "vault"
    (vault / "01 Now").mkdir(parents=True)
    (vault / "01 Now/This Week.md").write_text("# This Week\n", encoding="utf-8")
    (vault / "01 Now/Tickler.md").write_text("# Tickler\n", encoding="utf-8")
    return vault


def write_log(vault: Path, created=(), updated=(), deleted=None) -> Path:
    def rows(items):
        return ["- " + item for item in items] or ["None"]

    lines = ["## Session 1 - Fixture", "### Summary", "Done.",
             "### Files Created", *rows(created), "### Files Updated", *rows(updated)]
    if deleted is not None:
        lines += ["### Files Deleted", *rows(deleted)]
    lines += ["### Pickup Context", "**For next session:** None", "**Project:** None", ""]
    log = vault / "log.md"
    log.write_text("\n".join(lines), encoding="utf-8")
    return log


def verify(vault: Path, log: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(SCRIPT), str(vault), str(log), "1", *args],
                          check=False, capture_output=True, text=True)


class ParkVerifyTests(unittest.TestCase):
    def test_reverse_coverage_skips_deleted_rows_and_off_host_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = make_vault(Path(tmp))
            (vault / "docs").mkdir()
            (vault / "docs/a.md").write_text("body\n", encoding="utf-8")
            log = write_log(
                vault,
                updated=["docs/a.md - edited",
                         "nas:/share/file - mirrored copy",
                         "`Other PC C:\\Users\\x\\file` - consumer copy",
                         "Other PC C:\\Users\\x\\other - consumer copy"],
                deleted=["docs/gone.md - superseded", "`docs/old - draft.md` - merged"],
            )
            result = verify(vault, log, "--touched", "docs/a.md")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("REVIEW backfill", result.stdout)
            self.assertIn("PASS backfill: --touched covers every path", result.stdout)
            self.assertIn("3 off-host path form(s) not compared", result.stdout)
            self.assertIn("RESULT: PASS", result.stdout)

    def test_reverse_coverage_still_reports_lintable_unpassed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = make_vault(Path(tmp))
            (vault / "docs").mkdir()
            for name in ("a.md", "b.md"):
                (vault / "docs" / name).write_text("body\n", encoding="utf-8")
            # An existing local file is comparable even when its name looks remote.
            (vault / "nas:").mkdir()
            (vault / "nas:/local.md").write_text("body\n", encoding="utf-8")
            log = write_log(
                vault,
                updated=["docs/a.md - edited", "docs/b.md - edited",
                         "nas:/local.md - edited", "/tmp/absent-fixture.md - edited"],
                deleted=["docs/gone.md - superseded"],
            )
            result = verify(vault, log, "--touched", "docs/a.md")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            review = [l for l in result.stdout.splitlines() if l.startswith("REVIEW backfill:")]
            self.assertEqual(len(review), 1, result.stdout)
            self.assertTrue(
                review[0].endswith(": docs/b.md; nas:/local.md; /tmp/absent-fixture.md; "), review[0])
            self.assertNotIn("gone.md", review[0])

    def closure_lines(self, week: str, ident: str) -> list:
        with tempfile.TemporaryDirectory() as tmp:
            vault = make_vault(Path(tmp))
            (vault / "01 Now/This Week.md").write_text(week, encoding="utf-8")
            result = verify(vault, write_log(vault), "--ident", ident)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return [l for l in result.stdout.splitlines() if " closure: " in l]

    def test_ident_hidden_link_target_and_mid_word_matches_are_not_review(self) -> None:
        for ident, week in (
            ("Budget plan", "- [ ] Check [[03 Projects/Budget plan|the numbers]] with the bank\n"),
            ("Projects", "- [ ] Tidy [[03 Projects/Roadmap]]\n"),
            ("budget-plan", "- [ ] Read [the notes](https://example.org/budget-plan-2)\n"),
            ("log", "- [ ] Update the catalogue\n"),
            ("204", "- [ ] Chase order 91204\n"),
        ):
            with self.subTest(ident=ident):
                lines = self.closure_lines(week, ident)
                self.assertEqual(len(lines), 1, lines)
                self.assertTrue(lines[0].startswith("PASS closure: "), lines[0])
                self.assertIn("not counted", lines[0])
                self.assertIn("1:- [ ] ", lines[0])

    def test_ident_review_labels_text_and_link_matches(self) -> None:
        week = ("- [ ] Check [[03 Projects/Budget plan|the numbers]] with the bank\n"
                "- [ ] Draft [[03 Projects/Budget plan]] summary\n"
                "- [ ] Send budget plans to the client\n"
                "- [x] Budget plan agreed\n"
                "- [ ] Rename [[Old|Budget plan]] note\n")
        lines = self.closure_lines(week, "Budget plan")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("REVIEW closure: ident 'Budget plan' has unchecked matches: "), lines[0])
        counted, _, uncounted = lines[0].partition("not counted")
        self.assertIn("[link] 2:- [ ] Draft", counted)
        self.assertIn("[text] 3:- [ ] Send", counted)
        self.assertIn("[text] 5:- [ ] Rename", counted)
        self.assertNotIn("1:- [ ]", counted)
        self.assertIn("[link-target] 1:- [ ] Check", uncounted)
        self.assertNotIn("4:", lines[0])

    def test_ident_after_a_different_character_class_is_text(self) -> None:
        # A digit ident after letters (or the reverse) is a whole token of its
        # own, not the tail of a longer word or number.
        for ident, week in (("20417", "- [ ] Pay INV20417\n"),
                            ("kg", "- [ ] Order 25kg of flour\n")):
            with self.subTest(ident=ident):
                lines = self.closure_lines(week, ident)
                self.assertEqual(len(lines), 1, lines)
                self.assertTrue(lines[0].startswith("REVIEW closure: "), lines[0])
                self.assertIn("[text] 1:- [ ] ", lines[0])
                self.assertNotIn("not counted", lines[0])

    def test_truncated_touched_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = make_vault(Path(tmp))
            (vault / "docs").mkdir()
            (vault / "docs/Plan - draft.md").write_text("body\n", encoding="utf-8")
            log = write_log(vault, updated=["docs/Plan - draft.md - edited"])
            result = verify(vault, log, "--touched", "docs/Plan")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("FAIL touched: ", result.stdout)
            self.assertIn("FAIL backfill: touched but absent", result.stdout)
            self.assertIn("not passed to --touched", result.stdout)

    def test_truncated_deleted_touched_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = make_vault(Path(tmp))
            full = "notes/Foo - Bar.md"
            for row in (full + " - removed", full):
                with self.subTest(row=row):
                    log = write_log(vault, deleted=[row])
                    result = verify(vault, log, "--touched", "notes/Foo")
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("FAIL touched: ", result.stdout)
                    self.assertIn("FAIL backfill: touched but absent", result.stdout)
                    # Positive control: the complete deleted path remains valid.
                    complete = verify(vault, log, "--touched", full)
                    self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
                    self.assertIn("RESULT: PASS", complete.stdout)

    def test_touched_path_needs_a_complete_files_row_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = make_vault(Path(tmp))
            (vault / "docs").mkdir()
            for name in ("a.md", "a.md.bak", "Plan - draft.md", "Plan - draft.md - copy.md"):
                (vault / "docs" / name).write_text("body\n", encoding="utf-8")
            for touched, row in (("docs/a.md", "docs/a.md.bak - saved"),
                                 ("docs/a.md", "archive/docs/a.md - other tree"),
                                 ("docs/Plan - draft.md", "docs/Plan - draft.md - copy.md")):
                with self.subTest(touched=touched, row=row):
                    result = verify(vault, write_log(vault, updated=[row]), "--touched", touched)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn("FAIL backfill: touched but absent", result.stdout)
                    self.assertNotIn("FAIL touched", result.stdout)

    def test_separator_bearing_filenames_match_in_every_row_form(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = make_vault(Path(tmp))
            (vault / "docs").mkdir()
            name = "docs/Plan - draft - final.md"
            (vault / name).write_text("body\n", encoding="utf-8")
            (vault / "docs/Plan").write_text("shorter sibling\n", encoding="utf-8")
            for row in (name, name + " - edited - twice", "`" + name + "` - edited",
                        "[[" + name + "]] - edited", "[[docs/Plan - draft - final|label]]",
                        "[[Plan - draft - final]]", str(vault / name) + " - edited"):
                for touched in (name, "./" + name, str(vault / name), "docs/../" + name):
                    with self.subTest(row=row, touched=touched):
                        result = verify(vault, write_log(vault, updated=[row]), "--touched", touched)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        self.assertIn("RESULT: PASS", result.stdout)

    def test_missing_touched_target_needs_deleted_row_or_nonlocal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = make_vault(Path(tmp))
            gone = "docs/Old - v1.md"
            for row in (gone + " - removed", "`" + gone + "` - removed", gone):
                with self.subTest(row=row):
                    result = verify(vault, write_log(vault, deleted=[row]), "--touched", gone)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("RESULT: PASS", result.stdout)
            # Listed as updated, not deleted: nothing explains the missing target.
            result = verify(vault, write_log(vault, updated=["`" + gone + "`"]), "--touched", gone)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("FAIL touched: ", result.stdout)
            self.assertIn(gone, result.stdout)
            log = write_log(vault, updated=["nas:/share/file - mirrored copy"])
            result = verify(vault, log, "--touched", "nas:/share/file", "--nonlocal", "nas:/share/file")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("FAIL touched", result.stdout)

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



def touch(vault: Path, *names: str) -> None:
    for name in names:
        target = vault / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("body\n", encoding="utf-8")


def lines_of(result: subprocess.CompletedProcess, prefix: str) -> list:
    return [l for l in result.stdout.splitlines() if l.startswith(prefix)]


class CoverageIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.vault = make_vault(self.base)

    def run_rows(self, *touched: str, env=None, **sections) -> subprocess.CompletedProcess:
        log = write_log(self.vault, **sections)
        args = [a for t in touched for a in ("--touched", t)]
        return subprocess.run([str(SCRIPT), str(self.vault), str(log), "1", *args],
                              check=False, capture_output=True, text=True, env=env)

    def assert_pass(self, result) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT: PASS", result.stdout)

    # --- bare wikilink rows are an identity, not a basename ------------------
    def test_bare_wikilink_row_is_not_covered_by_a_same_named_file_outside_the_vault(self) -> None:
        touch(self.vault, "01 Now/Inbox.md")
        touch(self.base, "elsewhere/Inbox.md")
        result = self.run_rows(str(self.base / "elsewhere/Inbox.md"), updated=["[[Inbox]]"])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL backfill: touched but absent", result.stdout)
        review = lines_of(result, "REVIEW backfill: Files lists name path(s) not passed")
        self.assertEqual(len(review), 1, result.stdout)
        self.assertIn("01 Now/Inbox.md", review[0])
        # The one vault note of that name is what the row means.
        self.assert_pass(self.run_rows("01 Now/Inbox.md", updated=["[[Inbox]]"]))

    def test_bare_wikilink_row_shared_by_several_vault_files_is_ambiguous(self) -> None:
        touch(self.vault, "01 Now/Inbox.md", "06 Archive/Inbox.md")
        result = self.run_rows("01 Now/Inbox.md", updated=["[[Inbox]] - triaged"])
        self.assertEqual(result.returncode, 1, result.stdout)
        review = [l for l in lines_of(result, "REVIEW backfill: ") if "ambiguous" in l]
        self.assertEqual(len(review), 1, result.stdout)
        self.assertIn("[[Inbox]] - triaged", review[0])
        self.assertIn("full vault-relative path", review[0])
        self.assertIn("FAIL backfill: touched but absent", result.stdout)
        # A folder-qualified link still resolves by path.
        self.assert_pass(self.run_rows("01 Now/Inbox.md", updated=["[[01 Now/Inbox]] - triaged"]))

    def test_bare_wikilink_deleted_row_covers_one_absent_vault_path_only(self) -> None:
        # Defect: the deleted-row exemption used a vault-root key, so a note
        # deleted from a subfolder passed backfill and then failed `touched`.
        self.assert_pass(self.run_rows("03 Projects/Old Note.md", deleted=["[[Old Note]]"]))
        self.assert_pass(self.run_rows("03 Projects/Old Note.md", deleted=["[[Old Note]] - merged"]))
        outside = self.run_rows(str(self.base / "elsewhere/Old Note.md"), deleted=["[[Old Note]]"])
        self.assertEqual(outside.returncode, 1, outside.stdout)
        self.assertIn("FAIL backfill: touched but absent", outside.stdout)
        both = self.run_rows("03 Projects/Old Note.md", "04 Areas/Old Note.md", deleted=["[[Old Note]]"])
        self.assertEqual(both.returncode, 1, both.stdout)
        self.assertTrue(any("ambiguous" in l for l in lines_of(both, "REVIEW backfill: ")), both.stdout)

    def test_wikilink_string_passed_as_touched_follows_its_row(self) -> None:
        for spelling in ("[[Old Note]]", str(self.vault / "[[Old Note]]")):
            with self.subTest(spelling=spelling):
                self.assert_pass(self.run_rows(spelling, deleted=["[[Old Note]]"]))
        self.assert_pass(self.run_rows("[[03 Projects/Old Note]]", deleted=["[[03 Projects/Old Note]] - gone"]))
        # A live note named by wikilink is checked as the file it resolves to.
        touch(self.vault, "03 Projects/Live Note.md")
        self.assert_pass(self.run_rows("[[Live Note]]", updated=["[[Live Note]]"]))
        (self.vault / "03 Projects/Live Note.md").write_text("joined- [ ] item\n", encoding="utf-8")
        linted = self.run_rows("[[Live Note]]", updated=["[[Live Note]]"])
        self.assertIn("FAIL lint: ", linted.stdout)
        # Naming several vault files, it names none of them.
        touch(self.vault, "04 Areas/Live Note.md")
        shared = self.run_rows("[[Live Note]]", updated=["03 Projects/Live Note.md"])
        self.assertEqual(shared.returncode, 1, shared.stdout)
        self.assertIn("FAIL touched: wikilink passed to --touched names several vault files", shared.stdout)
        self.assertNotIn("PASS backfill: all", shared.stdout)
        # Not listed at all: still a failure.
        unlisted = self.run_rows("[[Other Note]]", deleted=["[[Old Note]]"])
        self.assertEqual(unlisted.returncode, 1, unlisted.stdout)
        self.assertIn("FAIL backfill: touched but absent", unlisted.stdout)

    # --- keys are case-sensitive --------------------------------------------
    def test_distinct_files_differing_only_in_case_do_not_cover_each_other(self) -> None:
        touch(self.vault, "notes/README.md", "notes/readme.md")
        if (self.vault / "notes/README.md").samefile(self.vault / "notes/readme.md"):
            self.skipTest("case-insensitive filesystem")
        result = self.run_rows("notes/readme.md", updated=["notes/README.md - edited"])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL backfill: touched but absent", result.stdout)
        self.assertIn("not passed to --touched", result.stdout)
        both = self.run_rows("notes/README.md", updated=["`notes/README.md`", "`notes/readme.md`"])
        review = lines_of(both, "REVIEW backfill: ")
        self.assertEqual(len(review), 1, both.stdout)
        self.assertTrue(review[0].endswith(": notes/readme.md; "), review[0])

    def test_row_spelled_in_a_different_case_still_matches_its_only_file(self) -> None:
        touch(self.vault, "notes/README.md")
        for row in ("notes/readme.md - edited", "`Notes/Readme.md`", "[[notes/readme]]", "[[readme]]"):
            with self.subTest(row=row):
                self.assert_pass(self.run_rows("notes/README.md", updated=[row]))

    # --- a directory is not the row's path -----------------------------------
    def test_directory_prefix_of_a_separator_bearing_filename_is_not_the_row_path(self) -> None:
        (self.vault / "docs/Plan").mkdir(parents=True)
        row = "docs/Plan - draft.md - rewrote intro"
        # File gone, directory present: the real path must still match its row.
        self.assert_pass(self.run_rows("docs/Plan - draft.md", deleted=[row]))
        # ... and the directory matching through the truncated prefix is flagged.
        result = self.run_rows("docs/Plan", updated=[row])
        self.assertNotIn("RESULT: PASS", result.stdout)
        review = [l for l in lines_of(result, "REVIEW backfill: ") if "backticks" in l]
        self.assertEqual(len(review), 1, result.stdout)
        self.assertIn(row, review[0])
        # File present: the directory does not match at all.
        touch(self.vault, "docs/Plan - draft.md")
        result = self.run_rows("docs/Plan", updated=[row])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL backfill: touched but absent", result.stdout)
        self.assertIn("not passed to --touched", result.stdout)
        self.assert_pass(self.run_rows("docs/Plan - draft.md", updated=[row]))

    def test_directory_row_with_a_description_still_matches_the_directory(self) -> None:
        (self.vault / "docs/Plan").mkdir(parents=True)
        for row in ("docs/Plan - new folder", "docs/Plan/ - exports, including summary.txt",
                    "docs/Plan (holds drafts) - see index.md"):
            with self.subTest(row=row):
                self.assert_pass(self.run_rows("docs/Plan", created=[row]))

    # --- Files Deleted rows that still exist ---------------------------------
    def test_deleted_row_whose_file_still_exists_stays_in_reverse_coverage(self) -> None:
        touch(self.vault, "docs/a.md", "docs/kept.md")
        result = self.run_rows("docs/a.md", updated=["docs/a.md"],
                               deleted=["docs/kept.md - removed", "docs/gone.md - removed"])
        review = lines_of(result, "REVIEW backfill: ")
        self.assertEqual(len(review), 1, result.stdout)
        self.assertTrue(review[0].endswith(": docs/kept.md; "), review[0])
        clean = self.run_rows("docs/a.md", updated=["docs/a.md"], deleted=["docs/gone.md - removed"])
        self.assert_pass(clean)
        self.assertIn("1 absent Files Deleted row(s) not compared", clean.stdout)

    # --- legacy row shapes ----------------------------------------------------
    def test_legacy_unquoted_row_shapes_resolve_to_their_path(self) -> None:
        path = "03 Projects/Alpha.md"
        touch(self.vault, path)
        for row in (path + " \u2014 updated status", path + ": updated status",
                    path + " (updated status)", "**" + path + "** - updated status",
                    "**" + path + "**", "[Alpha](" + path + ") - updated status",
                    "[Alpha](03%20Projects/Alpha.md)"):
            with self.subTest(row=row):
                self.assert_pass(self.run_rows(path, updated=[row]))
                short = self.run_rows("03 Projects/Alpha", updated=[row])
                self.assertEqual(short.returncode, 1, short.stdout)
        # Absent file: a split is taken only where the left side has an extension.
        for row in ("docs/Gone.md \u2014 superseded", "docs/Gone.md: superseded", "docs/Gone.md (superseded)"):
            with self.subTest(row=row):
                self.assert_pass(self.run_rows("docs/Gone.md", deleted=[row]))
                self.assertEqual(self.run_rows("docs/Gone", deleted=[row]).returncode, 1)

    def test_star_and_plus_bullets_are_rows(self) -> None:
        touch(self.vault, "docs/a.md", "docs/b.md")
        log = write_log(self.vault, updated=["docs/a.md - edited"])
        log.write_text(log.read_text().replace("- docs/a.md - edited", "* docs/a.md - edited\n+ docs/b.md"),
                       encoding="utf-8")
        result = verify(self.vault, log, "--touched", "docs/a.md", "--touched", "docs/b.md")
        self.assert_pass(result)
        result = verify(self.vault, log, "--touched", "docs/a.md")
        self.assertTrue(lines_of(result, "REVIEW backfill: ")[0].endswith(": docs/b.md; "), result.stdout)

    def test_existing_filenames_containing_the_new_separators_are_not_split(self) -> None:
        names = ("docs/Report (v2).md", "docs/Plan \u2014 draft.md", "docs/Note: one.md")
        touch(self.vault, *names)
        for name in names:
            for row in (name, name + " - edited", name + " \u2014 edited", "`" + name + "` - edited"):
                with self.subTest(row=row):
                    self.assert_pass(self.run_rows(name, updated=[row]))
        # Backticked rows stay exact: no separator handling inside or after them.
        touch(self.vault, "docs/a.md")
        result = self.run_rows("docs/a.md", updated=["`docs/a.md \u2014 edited`"])
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_row_text_passed_verbatim_as_touched_is_checked_as_the_row_file(self) -> None:
        # A caller that splits rows differently hands over "path <sep> description".
        touch(self.vault, "docs/a.md")
        row = "docs/a.md \u2014 collapsed one section"
        self.assert_pass(self.run_rows(row, updated=[row]))
        (self.vault / "docs/a.md").write_text("joined- [ ] item\n", encoding="utf-8")
        self.assertIn("FAIL lint: ", self.run_rows(row, updated=[row]).stdout)
        # So is the row cut at a later separator, as a last-" - " splitter does.
        cut = "docs/a.md (old copy)"
        self.assertIn("FAIL lint: ", self.run_rows(cut, deleted=[cut + " - merged; original binned"]).stdout)
        (self.vault / "docs/a.md").write_text("body\n", encoding="utf-8")
        self.assert_pass(self.run_rows(cut, deleted=[cut + " - merged; original binned"]))
        # A cut that is itself file-shaped may be a different, absent file.
        result = self.run_rows("docs/a.md - v2.md", updated=["docs/a.md - v2.md - compared"])
        self.assertEqual(result.returncode, 1, result.stdout)
        # Text that is not the row's own stays an absent, unlisted path.
        result = self.run_rows("docs/a.md \u2014 other words", updated=[row])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL touched: ", result.stdout)

    # --- off-host path passed as --touched ------------------------------------
    def test_off_host_touched_path_is_not_an_absent_target(self) -> None:
        for row, touched in (("nas:/share/file - mirrored copy", "nas:/share/file"),
                             ("`Other PC C:\\Users\\x\\file` - consumer copy", "Other PC C:\\Users\\x\\file"),
                             ("`https://example.org/doc` - published", "https://example.org/doc")):
            with self.subTest(touched=touched):
                result = self.run_rows(touched, updated=[row])
                self.assertNotIn("FAIL touched", result.stdout)
                self.assert_pass(result)
        # An absent local path is still a failure.
        result = self.run_rows("docs/typo.md", updated=["docs/typo.md"])
        self.assertIn("FAIL touched: ", result.stdout)

    # --- canonicalisation without GNU realpath --------------------------------
    def test_path_spellings_match_without_gnu_realpath(self) -> None:
        touch(self.vault, "docs/a.md", "docs/sub/x.md")
        (self.vault / "docs/link.md").symlink_to(self.vault / "docs/a.md")
        shim = self.base / "bin"
        shim.mkdir()
        (shim / "realpath").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (shim / "realpath").chmod(0o755)
        env = dict(os.environ, PATH=str(shim) + os.pathsep + os.environ.get("PATH", os.defpath))
        for row, touched in (("`docs/sub/../a.md`", "docs/a.md"), ("docs/a.md", "docs/sub/../a.md"),
                             ("docs/link.md - edited", "docs/a.md"), ("docs/a.md", "docs/link.md")):
            with self.subTest(row=row, touched=touched):
                self.assert_pass(self.run_rows(touched, env=env, updated=[row]))

    # --- CRLF session logs -----------------------------------------------------
    def test_crlf_session_log_rows_match(self) -> None:
        touch(self.vault, "docs/a.md")
        log = write_log(self.vault, updated=["docs/a.md", "`docs/b.md` - gone later", "[[docs/a]]"],
                        deleted=["docs/b.md - removed"])
        log.write_bytes(log.read_bytes().replace(b"\n", b"\r\n"))
        result = verify(self.vault, log, "--touched", "docs/a.md")
        review = lines_of(result, "REVIEW backfill: ")
        self.assertEqual(len(review), 1, result.stdout)
        self.assertTrue(review[0].endswith(": docs/b.md; "), review[0])
        self.assertNotIn("FAIL backfill", result.stdout)


class CoverageRoundTwoTests(unittest.TestCase):
    setUp = CoverageIdentityTests.setUp
    run_rows = CoverageIdentityTests.run_rows
    assert_pass = CoverageIdentityTests.assert_pass

    def test_deleted_row_for_an_extensionless_file_still_on_disk_is_compared(self) -> None:
        touch(self.vault, "scripts/deploy")
        result = self.run_rows(deleted=["scripts/deploy - replaced by deploy.sh"])
        review = lines_of(result, "REVIEW backfill: ")
        self.assertEqual(len(review), 1, result.stdout)
        self.assertTrue(review[0].endswith(": scripts/deploy; "), review[0])
        self.assertNotIn("absent Files Deleted", result.stdout)

    def test_absent_touched_message_names_nonlocal(self) -> None:
        result = self.run_rows("/mnt/other-host/fetch.sh", "docs/f*.md",
                               updated=["/mnt/other-host/fetch.sh - remote script", "docs/f*.md - many notes"])
        fails = lines_of(result, "FAIL touched: ")
        self.assertEqual(len(fails), 1, result.stdout)
        self.assertIn("path(s) do not exist and are not recorded under Files Deleted (truncated or mistyped?", fails[0])
        self.assertIn("a path on another host or a glob needs --nonlocal", fails[0])
        self.assertTrue(fails[0].endswith(": /mnt/other-host/fetch.sh; docs/f*.md; "), fails[0])

    def test_markdown_link_row_with_a_title_or_angle_destination(self) -> None:
        touch(self.vault, "hosts", "docs/My Note.md", "docs/Report (v2).md")
        for row, path in (('[Hosts](hosts "System hosts")', "hosts"),
                          ("[Hosts](hosts 'System hosts') - edited", "hosts"),
                          ("[Hosts](hosts (System hosts))", "hosts"),
                          ('[Note](<docs/My Note.md> "Mine") - edited', "docs/My Note.md"),
                          ("[Note](<docs/My Note.md>)", "docs/My Note.md"),
                          ('[Note](docs/My%20Note.md "Mine")', "docs/My Note.md"),
                          ("[Report](docs/Report (v2).md) - edited", "docs/Report (v2).md")):
            with self.subTest(row=row):
                self.assert_pass(self.run_rows(path, updated=[row]))
        # An absent destination is still reported by its path, not path-plus-title.
        result = self.run_rows(updated=['[Gone](docs/gone.md "Old")'])
        self.assertTrue(lines_of(result, "REVIEW backfill: ")[0].endswith(": docs/gone.md; "), result.stdout)

    def test_bare_wikilink_resolves_beneath_a_directory_symlink(self) -> None:
        touch(self.base, "shared/theme/Main.qml")
        (self.vault / "theme").symlink_to(self.base / "shared/theme")
        (self.base / "shared/theme/loop").symlink_to(self.base / "shared/theme")   # a cycle
        (self.vault / "again").symlink_to(self.base / "shared/theme")             # same directory twice
        self.assert_pass(self.run_rows("theme/Main.qml", updated=["[[Main.qml]]"]))
        self.assert_pass(self.run_rows("[[Main.qml]]", updated=["[[Main.qml]]"]))
        result = self.run_rows(updated=["[[Main.qml]]"])
        self.assertEqual(len(lines_of(result, "REVIEW backfill: Files lists name")), 1, result.stdout)
        self.assertNotIn("ambiguous", result.stdout)

    def test_one_ambiguous_row_does_not_cover_two_touched_paths(self) -> None:
        row = "missing - draft.md"
        result = self.run_rows("missing", "missing - draft.md", deleted=[row])
        self.assertEqual(result.returncode, 1, result.stdout)
        review = [l for l in lines_of(result, "REVIEW backfill: ") if "backticks" in l]
        self.assertEqual(len(review), 1, result.stdout)
        self.assertIn("- " + row, review[0])
        self.assertIn("FAIL backfill: touched but absent", result.stdout)
        self.assertNotIn("PASS backfill: all", result.stdout)
        # Two rows for one file, one carrying a parenthetical: each touched
        # value has a row of its own, so nothing is ambiguous.
        self.assert_pass(self.run_rows("docs/gone.md", "docs/gone.md (old copy)",
                                       deleted=["docs/gone.md (old copy) - merged", "docs/gone.md - removed"]))
        # Each on its own is unchanged, and backticks settle which one is meant.
        self.assert_pass(self.run_rows("missing - draft.md", deleted=[row]))
        quoted = self.run_rows("missing", "missing - draft.md", deleted=["`" + row + "`"])
        self.assertIn("FAIL backfill: touched but absent from Session 1 Files lists", quoted.stdout)
        self.assertNotIn("backticks;", quoted.stdout)
        self.assertTrue(lines_of(quoted, "FAIL backfill: ")[0].endswith(": missing; "), quoted.stdout)

    def test_bare_wikilink_deleted_row_ignores_surviving_notes_of_that_name(self) -> None:
        touch(self.vault, "sub/Note.md")
        (self.vault / "sub/Note.md").write_text("joined- [ ] item\n", encoding="utf-8")
        for touched in ("[[Note]]", "03 Projects/Note.md"):
            with self.subTest(survivors=1, touched=touched):
                result = self.run_rows(touched, deleted=["[[Note]]"])
                self.assertNotIn("FAIL lint", result.stdout)
                self.assert_pass(result)
        touch(self.vault, "other/Note.md")
        for touched in ("[[Note]]", "03 Projects/Note.md"):
            with self.subTest(survivors=2, touched=touched):
                self.assert_pass(self.run_rows(touched, deleted=["[[Note]]"]))
        # The survivor itself is not what the row deleted.
        result = self.run_rows("other/Note.md", deleted=["[[Note]]"])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL backfill: touched but absent", result.stdout)

    def test_home_tail_row_does_not_relink_an_already_covered_path(self) -> None:
        home = self.base / "home"
        touch(home, "repos/proj/tests/t.py")
        env = dict(os.environ, HOME=str(home))
        for rows in (["repos/proj/tests/t.py - added a case", "proj/tests/t.py - other checkout"],
                     ["proj/tests/t.py - other checkout", "repos/proj/tests/t.py - added a case"],
                     ["~/repos/proj/tests/t.py - added a case", "proj/tests/t.py - other checkout"]):
            with self.subTest(rows=rows):
                result = self.run_rows("~/repos/proj/tests/t.py", env=env, updated=rows)
                review = lines_of(result, "REVIEW backfill: ")
                self.assertEqual(len(review), 1, result.stdout)
                self.assertTrue(review[0].endswith(": proj/tests/t.py; "), review[0])
        self.assert_pass(self.run_rows("~/repos/proj/tests/t.py", env=env, updated=["proj/tests/t.py - edited"]))


if __name__ == "__main__":
    unittest.main()
