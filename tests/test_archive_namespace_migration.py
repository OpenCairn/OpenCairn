import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / ".claude/scripts/check-archive-layout.sh"
MIGRATE = REPO / ".claude/scripts/archive-namespace-migration.py"


def find_bash():
    candidates = []
    if sys.platform == "darwin":
        candidates.extend((Path("/opt/homebrew/bin/bash"), Path("/usr/local/bin/bash")))
    if os.name == "nt":
        for root in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ):
            if root:
                candidates.extend(
                    (Path(root) / "Git/bin/bash.exe", Path(root) / "Programs/Git/bin/bash.exe")
                )
    found = shutil.which("bash")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("archive migration tests require Bash")


BASH = find_bash()
CHECK_COMMAND = [BASH, str(CHECK)]
MIGRATE_COMMAND = [sys.executable, str(MIGRATE)]


class ArchiveNamespaceMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp.name)
        (self.vault / "03 Projects").mkdir()
        scripts = self.vault / ".claude/scripts"
        scripts.mkdir(parents=True)
        for name in ("locked-edit.sh", "lib-lock.sh", "lib-session.sh"):
            shutil.copy2(REPO / ".claude/scripts" / name, scripts / name)

    def tearDown(self):
        self.temp.cleanup()

    def check_state(self):
        result = subprocess.run(
            [*CHECK_COMMAND, "--status", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def inspect(self):
        result = subprocess.run(
            [*MIGRATE_COMMAND, "inspect", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_four_directory_states(self):
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "empty-clean")
        old = self.vault / "06 Archive/Claude"
        new = self.vault / "06 Archive/OpenCairn"
        old.mkdir(parents=True)
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "old-only")
        new.mkdir()
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "split")
        old.rmdir()
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-only")

    def test_gate_status_contract_is_exactly_three_lines(self):
        result = subprocess.run(
            [*CHECK_COMMAND, "--status", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "ARCHIVE_LAYOUT=empty-clean",
                "ACTIONABLE_LEGACY_FILES=0",
                "MIGRATION_JOURNAL_PHASE=absent",
            ],
        )

    def test_gate_accepts_crlf_helper_status(self):
        install = self.vault / "crlf-helper"
        install.mkdir()
        shutil.copy2(CHECK, install / "check-archive-layout.sh")
        helper = install / "archive-namespace-migration.py"
        helper.write_bytes(
            b"#!/usr/bin/env bash\n"
            b"printf 'ARCHIVE_LAYOUT=empty-clean\\r\\n"
            b"ACTIONABLE_LEGACY_FILES=0\\r\\n"
            b"MIGRATION_JOURNAL_PHASE=absent\\r\\n'\n"
        )
        helper.chmod(0o755)

        result = subprocess.run(
            [BASH, str(install / "check-archive-layout.sh"), "--status", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "ARCHIVE_LAYOUT=empty-clean",
                "ACTIONABLE_LEGACY_FILES=0",
                "MIGRATION_JOURNAL_PHASE=absent",
            ],
        )

    def test_mixed_gate_and_helper_report_archive_core_mismatch(self):
        install = self.vault / "mixed"
        install.mkdir()
        shutil.copy2(CHECK, install / "check-archive-layout.sh")
        helper = install / "archive-namespace-migration.py"
        helper.write_text("#!/bin/sh\necho old-helper\nexit 2\n")
        helper.chmod(0o755)
        status = subprocess.run(
            [BASH, str(install / "check-archive-layout.sh"), "--status", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(
            status.stdout.splitlines(),
            [
                "ARCHIVE_LAYOUT=archive-core-mismatch",
                "ACTIONABLE_LEGACY_FILES=unknown",
                "MIGRATION_JOURNAL_PHASE=unknown",
            ],
        )
        enforce = subprocess.run(
            [BASH, str(install / "check-archive-layout.sh"), "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(enforce.returncode, 26)
        self.assertIn("helper-first update bridge", enforce.stderr)

    def test_new_only_with_legacy_locator_is_not_complete(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        note = self.vault / "03 Projects/Example.md"
        note.write_text("[[06 Archive/Claude/Session Logs/2026-01-01]]\n")
        state = self.inspect()
        self.assertEqual(state["layout"], "new-with-legacy-locators")
        self.assertEqual(state["actionable_legacy_files"], ["03 Projects/Example.md"])

    def test_legacy_locator_exemption_preserves_historical_diagnostics(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        note = self.vault / "03 Projects/Archive migration incident.md"
        note.write_text(
            "<!-- opencairn: legacy-locator-exempt -->\n"
            "Historical example: 06 Archive/Claude/Session Logs/2026-01-01\n"
        )

        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-only")
        self.assertEqual(self.inspect()["actionable_legacy_files"], [])
        result = subprocess.run(
            [*MIGRATE_COMMAND, "rewrite", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout)["count"], 0)
        self.assertIn("06 Archive/Claude", note.read_text())

    def test_locator_scan_covers_text_artefacts_and_ignores_binary_data(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        binary = self.vault / "04 Areas/Photos/example.jpg"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"\x00prefix 06 Archive/Claude/Session Logs suffix")
        canvas = self.vault / "03 Projects/Map.canvas"
        canvas.write_text('{"text":"06 Archive/Claude/Session Logs"}\n')
        script = self.vault / "04 Areas/Scripts/archive.sh"
        script.parent.mkdir(parents=True)
        script.write_text('archive="06 Archive/Claude/Session Logs"\n')
        unrelated = self.vault / "04 Areas/Scripts/older-layout.sh"
        unrelated.write_text('archive="06 Archive/Claude Sessions"\n')
        extensionless = self.vault / "04 Areas/Scripts/archive-config"
        extensionless.write_text('archive="06 Archive/Claude/Session Logs"\n')
        hidden_extensionless = self.vault / "04 Areas/Scripts/.archive-root"
        hidden_extensionless.write_text('06 Archive/Claude\n')
        exact_root = self.vault / "04 Areas/Scripts/root.conf"
        exact_root.write_text('archive="06 Archive/Claude"\n')
        parenthesised_root = self.vault / "04 Areas/Scripts/parenthesised.conf"
        parenthesised_root.write_text('(see 06 Archive/Claude)\n')
        eof_root = self.vault / "04 Areas/Scripts/eof.conf"
        eof_root.write_text('archive_root=06 Archive/Claude')
        binary_extensionless = self.vault / "04 Areas/Scripts/archive-binary"
        binary_extensionless.write_bytes(b"06 Archive/Claude\x00binary")
        windows = self.vault / "04 Areas/Scripts/archive.ini"
        windows.write_text('archive="06 Archive\\Claude\\Session Logs"\n')
        backup = self.vault / "04 Areas/Scripts/archive.md.bak.123"
        backup.write_text('archive="06 Archive/Claude/Session Logs"\n')

        state = self.inspect()
        self.assertEqual(
            state["actionable_legacy_files"],
            [
                "03 Projects/Map.canvas",
                "04 Areas/Scripts/.archive-root",
                "04 Areas/Scripts/archive-config",
                "04 Areas/Scripts/archive.ini",
                "04 Areas/Scripts/archive.md.bak.123",
                "04 Areas/Scripts/archive.sh",
                "04 Areas/Scripts/eof.conf",
                "04 Areas/Scripts/parenthesised.conf",
                "04 Areas/Scripts/root.conf",
            ],
        )
        self.assertEqual(self.check_state()["ACTIONABLE_LEGACY_FILES"], "9")

        subprocess.run(
            [*MIGRATE_COMMAND, "rewrite", str(self.vault)],
            check=True,
            capture_output=True,
        )
        self.assertIn("06 Archive/OpenCairn/Session Logs", script.read_text())
        self.assertIn("06 Archive/OpenCairn/Session Logs", extensionless.read_text())
        self.assertEqual(hidden_extensionless.read_text(), "06 Archive/OpenCairn\n")
        self.assertIn('archive="06 Archive/OpenCairn"', exact_root.read_text())
        self.assertEqual(parenthesised_root.read_text(), "(see 06 Archive/OpenCairn)\n")
        self.assertEqual(eof_root.read_text(), "archive_root=06 Archive/OpenCairn")
        self.assertIn("06 Archive\\OpenCairn\\Session Logs", windows.read_text())
        self.assertIn("06 Archive/OpenCairn/Session Logs", backup.read_text())
        self.assertIn("06 Archive/Claude Sessions", unrelated.read_text())
        self.assertEqual(binary_extensionless.read_bytes(), b"06 Archive/Claude\x00binary")

    def test_non_utf8_extensionless_locator_is_consistently_reported(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        target = self.vault / "03 Projects/legacy-config"
        target.write_bytes(b"\xff\narchive=06 Archive/Claude")

        self.assertEqual(
            self.inspect()["actionable_legacy_files"],
            ["03 Projects/legacy-config"],
        )
        self.assertEqual(self.check_state()["ACTIONABLE_LEGACY_FILES"], "1")
        result = subprocess.run(
            [*MIGRATE_COMMAND, "rewrite", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("non-UTF-8 text", result.stderr)

    def test_empty_layout_with_legacy_locator_can_be_rewritten(self):
        note = self.vault / "03 Projects/Example.md"
        note.write_text("[[06 Archive/Claude/Session Logs/2026-01-01]]\n")

        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "empty-with-legacy-locators")
        subprocess.run([*MIGRATE_COMMAND, "rewrite", str(self.vault)], check=True, capture_output=True)
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "empty-clean")

    def test_locator_search_does_not_depend_on_ripgrep(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        fake_bin = self.vault / "fake-bin"
        fake_bin.mkdir()
        fake_rg = fake_bin / "rg"
        fake_rg.write_text("#!/bin/sh\nexit 2\n")
        fake_rg.chmod(0o755)
        restricted_path = os.pathsep.join(
            (
                str(fake_bin),
                str(Path(sys.executable).parent),
                str(Path(BASH).parent),
                "/usr/bin",
                "/bin",
            )
        )
        env = dict(os.environ, PATH=restricted_path)

        status = subprocess.run(
            [*CHECK_COMMAND, "--status", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
            env=env,
        )
        self.assertIn("ARCHIVE_LAYOUT=new-only", status.stdout)
        enforce = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(enforce.returncode, 0)

    def test_migrator_works_without_ripgrep(self):
        empty_path = self.vault / "empty-path"
        empty_path.mkdir()
        result = subprocess.run(
            [sys.executable, str(MIGRATE), "inspect", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
            env=dict(os.environ, PATH=str(empty_path)),
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["layout"], "empty-clean")
        self.assertNotIn("Traceback", result.stderr)

    def test_rewrite_is_idempotent_and_preserves_immutable_files(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        note = self.vault / "03 Projects/Example.md"
        note.write_text("[[06 Archive/Claude/Session Logs/2026-01-01]]\n")
        snapshot = self.vault / "07 System/.Provenance/x.snapshot.md"
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text("[[06 Archive/Claude/Session Logs/2026-01-01]]\n")

        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-with-legacy-locators")

        first = subprocess.run(
            [*MIGRATE_COMMAND, "rewrite", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(first.stdout)["count"], 1)
        self.assertIn("06 Archive/OpenCairn", note.read_text())
        self.assertIn("06 Archive/Claude", snapshot.read_text())
        self.assertEqual(self.inspect()["layout"], "new-only")
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-only")

        second = subprocess.run(
            [*MIGRATE_COMMAND, "rewrite", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(second.stdout)["count"], 0)

    def test_old_only_enforcement_fails_with_migration_route(self):
        (self.vault / "06 Archive/Claude").mkdir(parents=True)
        result = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 20)
        self.assertIn("/migrate", result.stderr)
        self.assertIn("$migrate", result.stderr)

    def test_begin_and_finish_preserve_legacy_component_table(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        (old / "Session Logs").mkdir()
        (old / "Session Logs/2026-01-01.md").write_text("session\n")
        record = self.vault / "07 System/Migration Record.md"
        record.parent.mkdir(parents=True)
        record.write_text(
            "# OpenCairn Migration Record\n\n"
            "| # | Component | now/later/never | YYYY-MM-DD |\n"
            "|---|---|---|---|\n"
            "| 2 | Project-doc schema | never | 2026-08-01 |\n"
        )

        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        self.assertIn("| 2 | Project-doc schema | never | 2026-08-01 |", record.read_text())
        self.assertIn("| archive-namespace-opencairn-v1 | in-progress |", record.read_text())

        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        subprocess.run([*MIGRATE_COMMAND, "rewrite", str(self.vault)], check=True, capture_output=True)
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        text = record.read_text()
        self.assertIn("| 2 | Project-doc schema | never | 2026-08-01 |", text)
        self.assertEqual(text.count("| archive-namespace-opencairn-v1 | complete |"), 1)

    def test_old_transcript_is_hashed_at_renamed_path_and_not_rewritten(self):
        old = self.vault / "06 Archive/Claude"
        transcript = old / ".Session Transcripts/2026-01-01.md"
        transcript.parent.mkdir(parents=True)
        original = "Historical locator: 06 Archive/Claude/Session Logs/2026-01-01\n"
        transcript.write_text(original)
        self.assertEqual(self.check_state()["ACTIONABLE_LEGACY_FILES"], "0")

        begin = subprocess.run(
            [*MIGRATE_COMMAND, "begin", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        journal = json.loads(begin.stdout)
        self.assertIn(
            "06 Archive/Claude/.Session Transcripts/2026-01-01.md",
            journal["immutable_sha256"],
        )
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        self.assertNotIn(
            "07 System/.OpenCairn Migration/archive-namespace-opencairn-v1.json",
            self.inspect()["actionable_legacy_files"],
        )
        subprocess.run([*MIGRATE_COMMAND, "rewrite", str(self.vault)], check=True, capture_output=True)
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        self.assertEqual((new / ".Session Transcripts/2026-01-01.md").read_text(), original)

    def test_transcript_without_legacy_locator_is_still_byte_verified(self):
        old = self.vault / "06 Archive/Claude"
        transcript = old / ".Session Transcripts/raw.txt"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("immutable transcript without a path locator\n")

        begin = subprocess.run(
            [*MIGRATE_COMMAND, "begin", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        journal = json.loads(begin.stdout)
        self.assertIn(
            "06 Archive/Claude/.Session Transcripts/raw.txt",
            journal["immutable_sha256"],
        )
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        (new / ".Session Transcripts/raw.txt").write_text("mutated\n")

        result = subprocess.run(
            [*MIGRATE_COMMAND, "verify", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "immutable file changed: 06 Archive/Claude/.Session Transcripts/raw.txt",
            result.stdout,
        )

    def test_archive_lock_files_do_not_change_member_inventory(self):
        old = self.vault / "06 Archive/Claude"
        note = old / "Session Logs/2026-01-01.md"
        note.parent.mkdir(parents=True)
        note.write_text("Locator: 06 Archive/Claude/Session Logs/2026-01-01\n")
        (note.parent / ".2026-01-01.md.lock").write_text("")
        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)

        subprocess.run([*MIGRATE_COMMAND, "rewrite", str(self.vault)], check=True, capture_output=True)
        self.assertTrue((new / "Session Logs/.2026-01-01.md.lock").is_file())
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)

    def test_empty_source_inventory_still_rejects_new_destination_member(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        (new / "unexpected.md").write_text("unexpected\n")

        result = subprocess.run(
            [*MIGRATE_COMMAND, "verify", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("destination member inventory differs", result.stdout)

    def test_interrupted_after_move_resumes_locator_rewrite(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        (old / "Session Logs").mkdir()
        (old / "Session Logs/2026-01-01.md").write_text("session\n")
        note = self.vault / "03 Projects/Example.md"
        note.write_text("[[06 Archive/Claude/Session Logs/2026-01-01]]\n")
        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        old.rename(self.vault / "06 Archive/OpenCairn")

        verify_before = subprocess.run(
            [*MIGRATE_COMMAND, "verify", str(self.vault)], capture_output=True, text=True
        )
        self.assertNotEqual(verify_before.returncode, 0)
        subprocess.run([*MIGRATE_COMMAND, "rewrite", str(self.vault)], check=True, capture_output=True)
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        self.assertIn("06 Archive/OpenCairn", note.read_text())

    def test_unfinished_journal_blocks_locator_clean_layouts_until_finish(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)

        state = self.check_state()
        self.assertEqual(state["ARCHIVE_LAYOUT"], "pending-verification")
        self.assertEqual(state["MIGRATION_JOURNAL_PHASE"], "in-progress")
        enforce = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(enforce.returncode, 20)
        self.assertIn("awaiting journal-backed verification", enforce.stderr)

        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-only")
        subprocess.run([*CHECK_COMMAND, "--enforce", str(self.vault)], check=True, capture_output=True)

        journal_path = self.vault / "07 System/.OpenCairn Migration/archive-namespace-opencairn-v1.json"
        journal = json.loads(journal_path.read_text())
        journal["phase"] = "in-progress"
        journal.pop("completed_at")
        journal_path.write_text(json.dumps(journal) + "\n")
        new.rmdir()
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "pending-verification")

    def test_completed_migration_allows_later_archive_growth(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        (old / "existing.md").write_text("existing\n")
        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        (new / "later.md").write_text("later\n")

        subprocess.run([*MIGRATE_COMMAND, "verify", str(self.vault)], check=True, capture_output=True)
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)

    def test_completed_journal_repairs_missing_or_duplicated_ledger_row(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        old.rename(self.vault / "06 Archive/OpenCairn")
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        record = self.vault / "07 System/Migration Record.md"
        lines = [
            line
            for line in record.read_text().splitlines()
            if not line.startswith("| archive-namespace-opencairn-v1 |")
        ]
        record.write_text("\n".join(lines) + "\n")
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        row = next(
            line
            for line in record.read_text().splitlines()
            if line.startswith("| archive-namespace-opencairn-v1 |")
        )
        with record.open("a") as handle:
            handle.write(row + "\n")
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        self.assertEqual(
            record.read_text().count("| archive-namespace-opencairn-v1 | complete |"),
            1,
        )
    def test_completed_journal_is_terminal_after_archive_growth(self):
        old = self.vault / "06 Archive/Claude"
        transcript = old / ".Session Transcripts/raw.txt"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("immutable\n")
        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        (new / ".Session Transcripts/raw.txt").write_text("changed\n")

        result = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ARCHIVE_LAYOUT=new-only", result.stdout)
        rewrite = subprocess.run(
            [*MIGRATE_COMMAND, "rewrite", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(rewrite.stdout), {"changed": [], "count": 0})

    def test_completed_journal_requires_open_cairn_root(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        subprocess.run([*MIGRATE_COMMAND, "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        subprocess.run([*MIGRATE_COMMAND, "finish", str(self.vault)], check=True, capture_output=True)
        new.rmdir()

        verify = subprocess.run(
            [*MIGRATE_COMMAND, "verify", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("unsafe live layout: empty-clean", verify.stdout)
        enforce = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(enforce.returncode, 25)
        self.assertIn("ARCHIVE_LAYOUT=complete-journal-topology-mismatch", enforce.stdout)
        self.assertIn("conflicts with archive topology", enforce.stderr)

    def test_complete_ledger_is_terminal_and_mismatch_is_explicit(self):
        new = self.vault / "06 Archive/OpenCairn"
        new.mkdir(parents=True)
        subprocess.run(
            [*MIGRATE_COMMAND, "record", str(self.vault), "complete"],
            check=True,
            capture_output=True,
        )
        note = self.vault / "03 Projects/Historical.md"
        note.write_text("06 Archive/Claude/Session Logs/example\n")
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-only")
        new.rmdir()
        result = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 25)
        self.assertIn("ARCHIVE_LAYOUT=complete-ledger-topology-mismatch", result.stdout)

    def test_archive_root_initialises_empty_vault_before_recording(self):
        result = subprocess.run(
            [*MIGRATE_COMMAND, "archive-root", "--write", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "06 Archive/OpenCairn")
        self.assertTrue((self.vault / "06 Archive/OpenCairn/.Session Transcripts").is_dir())
        record = (self.vault / "07 System/Migration Record.md").read_text()
        self.assertEqual(record.count("| archive-namespace-opencairn-v1 | complete |"), 1)

    def test_archive_root_preserves_old_only_consumer(self):
        (self.vault / "06 Archive/Claude").mkdir(parents=True)
        result = subprocess.run(
            [*MIGRATE_COMMAND, "archive-root", "--write", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "06 Archive/Claude")
        self.assertFalse((self.vault / "07 System/Migration Record.md").exists())

    def test_archive_root_refuses_split_without_writing(self):
        (self.vault / "06 Archive/Claude").mkdir(parents=True)
        (self.vault / "06 Archive/OpenCairn").mkdir()
        result = subprocess.run(
            [*MIGRATE_COMMAND, "archive-root", "--write", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.vault / "07 System/Migration Record.md").exists())

    def test_archive_root_refuses_empty_topology_with_legacy_locators_without_writing(self):
        (self.vault / "03 Projects/Legacy.md").write_text(
            "06 Archive/Claude/Session Logs/example\n"
        )
        result = subprocess.run(
            [*MIGRATE_COMMAND, "archive-root", "--write", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertFalse((self.vault / "06 Archive/OpenCairn").exists())
        self.assertFalse((self.vault / "07 System/Migration Record.md").exists())

    def test_concurrent_first_archive_roots_leave_one_ledger_row(self):
        command = [*MIGRATE_COMMAND, "archive-root", "--write", str(self.vault)]
        processes = [
            subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for _ in range(4)
        ]
        results = [process.communicate() + (process.returncode,) for process in processes]
        self.assertTrue(all(returncode == 0 for _, _, returncode in results), results)
        text = (self.vault / "07 System/Migration Record.md").read_text()
        self.assertEqual(text.count("| archive-namespace-opencairn-v1 | complete |"), 1)

    def test_structurally_invalid_journals_fail_closed(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        journal_path = self.vault / "07 System/.OpenCairn Migration/archive-namespace-opencairn-v1.json"
        journal_path.parent.mkdir(parents=True)
        cases = {
            "phase only": {"phase": "complete"},
            "wrong schema": {
                "schema": 2,
                "migration": "archive-namespace-opencairn-v1",
                "phase": "complete",
                "source_members": [],
                "immutable_sha256": {},
            },
            "wrong migration": {
                "schema": 1,
                "migration": "different-migration",
                "phase": "complete",
                "source_members": [],
                "immutable_sha256": {},
            },
            "bad member inventory": {
                "schema": 1,
                "migration": "archive-namespace-opencairn-v1",
                "phase": "complete",
                "source_members": "not-a-list",
                "immutable_sha256": {},
            },
            "bad immutable hashes": {
                "schema": 1,
                "migration": "archive-namespace-opencairn-v1",
                "phase": "complete",
                "source_members": [],
                "immutable_sha256": {"example.md": "not-a-hash"},
            },
            "absolute member path": {
                "schema": 1,
                "migration": "archive-namespace-opencairn-v1",
                "phase": "complete",
                "source_members": ["/etc/passwd"],
                "immutable_sha256": {},
            },
            "escaping immutable path": {
                "schema": 1,
                "migration": "archive-namespace-opencairn-v1",
                "phase": "complete",
                "source_members": [],
                "immutable_sha256": {"../outside": "a" * 64},
            },
            "immutable path outside protected namespace": {
                "schema": 1,
                "migration": "archive-namespace-opencairn-v1",
                "phase": "complete",
                "source_members": [],
                "immutable_sha256": {"03 Projects/Example.md": "a" * 64},
            },
        }
        for label, journal in cases.items():
            with self.subTest(label=label):
                journal_path.write_text(json.dumps(journal) + "\n")
                state = self.check_state()
                self.assertEqual(state["ARCHIVE_LAYOUT"], "indeterminate")
                self.assertEqual(state["MIGRATION_JOURNAL_PHASE"], "invalid")
                inspection = self.inspect()
                self.assertEqual(inspection["journal_phase"], "invalid")
                self.assertTrue(inspection["journal_error"])
                enforce = subprocess.run(
                    [*CHECK_COMMAND, "--enforce", str(self.vault)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(enforce.returncode, 24)
                verify = subprocess.run(
                    [*MIGRATE_COMMAND, "verify", str(self.vault)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertNotEqual(verify.returncode, 0)

    def test_finish_requires_a_valid_journal(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        result = subprocess.run(
            [*MIGRATE_COMMAND, "finish", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a valid migration journal", result.stderr)

    def test_phase_flipped_journal_without_completion_timestamp_fails_closed(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        begin = subprocess.run(
            [*MIGRATE_COMMAND, "begin", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(begin.returncode, 0, begin.stderr)
        old.rename(self.vault / "06 Archive/OpenCairn")
        journal_path = (
            self.vault
            / "07 System/.OpenCairn Migration/archive-namespace-opencairn-v1.json"
        )
        journal = json.loads(journal_path.read_text())
        journal["phase"] = "complete"
        journal_path.write_text(json.dumps(journal) + "\n")

        state = self.check_state()
        self.assertEqual(state["ARCHIVE_LAYOUT"], "indeterminate")
        self.assertEqual(state["MIGRATION_JOURNAL_PHASE"], "invalid")
        enforce = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(enforce.returncode, 24)
        verify = subprocess.run(
            [*MIGRATE_COMMAND, "verify", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(verify.returncode, 0)
        self.assertIn("completed_at", verify.stderr)

    def test_symlink_alias_is_never_treated_as_split_members(self):
        new = self.vault / "06 Archive/OpenCairn"
        new.mkdir(parents=True)
        (new / "only-copy.md").write_text("content\n")
        old = self.vault / "06 Archive/Claude"
        old.symlink_to("OpenCairn", target_is_directory=True)

        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "legacy-symlink-alias")
        self.assertEqual(self.inspect()["layout"], "legacy-symlink-alias")
        result = subprocess.run(
            [*MIGRATE_COMMAND, "split-plan", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["kind"], "legacy-symlink-alias")
        self.assertFalse(report["member_reconciliation_permitted"])
        self.assertNotIn("identical", report)

    def test_symlinked_new_root_fails_closed(self):
        outside = self.vault / "outside"
        outside.mkdir()
        new = self.vault / "06 Archive/OpenCairn"
        new.parent.mkdir()
        new.symlink_to(outside, target_is_directory=True)

        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-symlink-unsafe")
        enforce = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(enforce.returncode, 23)
        self.assertIn("active archive root must remain inside the vault", enforce.stderr)
        plan = subprocess.run(
            [*MIGRATE_COMMAND, "split-plan", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(plan.returncode, 2)
        self.assertEqual(json.loads(plan.stdout)["kind"], "new-symlink-unsafe")

    def test_regular_file_at_archive_root_fails_closed(self):
        path = self.vault / "06 Archive/OpenCairn"
        path.parent.mkdir()
        path.write_text("not a directory\n")
        state = self.check_state()
        self.assertEqual(state["ARCHIVE_LAYOUT"], "new-path-unsafe")
        result = subprocess.run(
            [*CHECK_COMMAND, "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 23)
        self.assertIn("is not a directory", result.stderr)

    def test_split_plan_binds_collisions_to_hashes(self):
        old = self.vault / "06 Archive/Claude"
        new = self.vault / "06 Archive/OpenCairn"
        old.mkdir(parents=True)
        new.mkdir()
        (old / "same.md").write_text("same\n")
        (new / "same.md").write_text("same\n")
        (old / "different.md").write_text("old\n")
        (new / "different.md").write_text("new\n")

        result = subprocess.run(
            [*MIGRATE_COMMAND, "split-plan", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(report["identical"][0]["sha256"]), 64)
        self.assertEqual(len(report["conflicts"][0]["old_sha256"]), 64)
        self.assertEqual(len(report["conflicts"][0]["new_sha256"]), 64)

    def test_every_archive_backed_workflow_has_deterministic_gate(self):
        claude_files = []
        for path in (REPO / ".claude/commands").glob("*.md"):
            text = path.read_text()
            if "06 Archive/OpenCairn" in text and path.name not in {
                "_shared-rules.md",
                "migrate.md",
                "update.md",
            }:
                claude_files.append(path)
                self.assertIn("check-archive-layout.sh", text, path)
                self.assertIn("--enforce", text, path)
        self.assertGreaterEqual(len(claude_files), 10)

        codex_files = []
        for path in (REPO / "codex/skills").glob("*/SKILL.md"):
            text = path.read_text()
            if "06 Archive/OpenCairn" in text and path.parent.name not in {"migrate", "update"}:
                codex_files.append(path)
                self.assertIn("check-archive-layout.sh", text, path)
                self.assertIn("--enforce", text, path)
        self.assertGreaterEqual(len(codex_files), 10)

    def test_update_gate_precedes_apply(self):
        text = (REPO / ".claude/commands/update.md").read_text()
        self.assertLess(
            text.index("### Step 1c: Old-Format Vault Check"),
            text.index("### Step 3d: Recover the Migration Bundle, Then Gate"),
        )
        self.assertLess(
            text.index("### Step 3d: Recover the Migration Bundle, Then Gate"),
            text.index("### Step 4: Compare Working Tree Against Template"),
        )
        self.assertIn('check-archive-layout.sh" --status', text)
        self.assertIn("Do not offer independent accept/skip choices", text)
        self.assertIn("git checkout $REF -- <the-nine-literal-paths>", text)
        self.assertIn("archive-bundle-v3", text)
        self.assertIn("pre-revamp installations", text)
        self.assertIn("two-stage", text)
        self.assertIn("**Universal user route:** run `/update`", text)
        self.assertIn("Both commands are idempotent", text)
        self.assertIn("task-system `/migrate` already installed with v0.8.0", text)
        self.assertIn("PRE_REVAMP_HANDOFF", text)
        self.assertIn("only after proving the requested update target", text)
        self.assertIn("Under `--dry-run`, report the required task/archive migration", text)
        self.assertIn("Step 3d repairs an incomplete local bundle", text)
        self.assertIn("Continuing through /migrate now", text)
        self.assertIn("/update will resume after verification", text)
        self.assertIn("Review them on **2026-11-16**", text)
        self.assertIn("never an automatic user-facing expiry", text)
        self.assertIn("minimum supported update source beyond v0.8.0", text)
        self.assertIn("validation is unconditional", text)
        self.assertIn("`--tag` selects an older release", text)
        self.assertIn("Under `--dry-run`, report the required copies but do not write them", text)
        self.assertIn('prepend `cd "$VAULT_PATH" || exit 1`', text)
        self.assertIn("${CODEX_HOME:-$HOME/.codex}", text)
        self.assertIn('cd "$VAULT_PATH"', text)
        self.assertIn("Freeze the verified target", text)
        self.assertIn("literal immutable commit ID", text)
        self.assertIn("review is mandatory even under `--force`", text)
        self.assertIn("Reject symlinks and unexpected types", text)
        self.assertIn("Do not restore files automatically from a historical `HEAD`", text)
        self.assertIn("complete-journal-topology-mismatch", text)
        self.assertIn("archive-core-mismatch", text)
        self.assertIn("Step 1b: Guard the staged surface", text)
        self.assertIn("possible interrupted update", text)
        self.assertIn("probe the installed helper directly", text)
        self.assertIn("one all-or-nothing archive-core unit", text)
        self.assertIn("never chmod a glob", text)
        self.assertIn("recalculate that identity", text)
        self.assertIn("Reject a symlink", text)
        self.assertNotIn("git checkout $REF -- .claude/commands/ .claude/scripts/ codex/", text)
        self.assertNotIn("chmod +x .claude/scripts/*.sh", text)

        bundle = [
            ".claude/commands/update.md",
            ".claude/commands/migrate.md",
            ".claude/scripts/check-archive-layout.sh",
            ".claude/scripts/archive-namespace-migration.py",
            ".claude/scripts/locked-edit.sh",
            ".claude/scripts/lib-lock.sh",
            ".claude/scripts/lib-session.sh",
            "codex/skills/update/SKILL.md",
            "codex/skills/migrate/SKILL.md",
        ]
        for relative in bundle:
            self.assertIn("archive-bundle-v3", (REPO / relative).read_text(), relative)

        migrate_text = (REPO / ".claude/commands/migrate.md").read_text()
        self.assertIn("task-system revamp first, archive namespace second", migrate_text)
        self.assertIn("return directly to §1 in this same invocation", migrate_text)
        self.assertIn("journal is absent and the layout is `new-with-legacy-locators`", migrate_text)
        self.assertIn("otherwise confirm `new-only`, record `complete`", migrate_text)

        codex_update = (REPO / "codex/skills/update/SKILL.md").read_text()
        codex_migrate = (REPO / "codex/skills/migrate/SKILL.md").read_text()
        self.assertIn("Require it to contain `archive-bundle-v3`", codex_update)
        self.assertIn("only pre-gate writes", codex_update)
        self.assertIn("immutable commit ID", codex_update)
        self.assertIn("even under `--force`", codex_update)
        self.assertIn("unrelated staged content", codex_update)
        self.assertIn("all-or-nothing archive-core unit", codex_update)
        self.assertIn("canonical migrate command to contain `archive-bundle-v3`", codex_migrate)


if __name__ == "__main__":
    unittest.main()
