import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
CHECK = REPO / ".claude/scripts/check-archive-layout.sh"
MIGRATE = REPO / ".claude/scripts/archive-namespace-migration.py"


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
            [str(CHECK), "--status", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        return dict(line.split("=", 1) for line in result.stdout.splitlines())

    def inspect(self):
        result = subprocess.run(
            [str(MIGRATE), "inspect", str(self.vault)],
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

    def test_new_only_with_legacy_locator_is_not_complete(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        note = self.vault / "03 Projects/Example.md"
        note.write_text("[[06 Archive/Claude/Session Logs/2026-01-01]]\n")
        state = self.inspect()
        self.assertEqual(state["layout"], "new-with-legacy-locators")
        self.assertEqual(state["actionable_legacy_files"], ["03 Projects/Example.md"])

    def test_locator_scan_is_limited_to_obsidian_text_artefacts(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        binary = self.vault / "04 Areas/Photos/example.jpg"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"prefix 06 Archive/Claude suffix")
        canvas = self.vault / "03 Projects/Map.canvas"
        canvas.write_text('{"text":"06 Archive/Claude"}\n')

        state = self.inspect()
        self.assertEqual(state["actionable_legacy_files"], ["03 Projects/Map.canvas"])
        self.assertEqual(self.check_state()["ACTIONABLE_LEGACY_FILES"], "1")

    def test_locator_search_error_fails_closed(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        fake_bin = self.vault / "fake-bin"
        fake_bin.mkdir()
        fake_rg = fake_bin / "rg"
        fake_rg.write_text("#!/bin/sh\nexit 2\n")
        fake_rg.chmod(0o755)
        env = dict(os.environ, PATH=f"{fake_bin}:/usr/bin:/bin")

        status = subprocess.run(
            [str(CHECK), "--status", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
            env=env,
        )
        self.assertIn("ARCHIVE_LAYOUT=indeterminate", status.stdout)
        enforce = subprocess.run(
            [str(CHECK), "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(enforce.returncode, 24)
        self.assertIn("legacy-locator search failed", enforce.stderr)

    def test_rewrite_is_idempotent_and_preserves_immutable_files(self):
        (self.vault / "06 Archive/OpenCairn").mkdir(parents=True)
        note = self.vault / "03 Projects/Example.md"
        note.write_text("[[06 Archive/Claude/Session Logs/2026-01-01]]\n")
        snapshot = self.vault / "07 System/.Provenance/x.snapshot.md"
        snapshot.parent.mkdir(parents=True)
        snapshot.write_text("[[06 Archive/Claude/Session Logs/2026-01-01]]\n")

        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-with-legacy-locators")

        first = subprocess.run(
            [str(MIGRATE), "rewrite", str(self.vault)],
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
            [str(MIGRATE), "rewrite", str(self.vault)],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(second.stdout)["count"], 0)

    def test_old_only_enforcement_fails_with_migration_route(self):
        (self.vault / "06 Archive/Claude").mkdir(parents=True)
        result = subprocess.run(
            [str(CHECK), "--enforce", str(self.vault)],
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

        subprocess.run([str(MIGRATE), "begin", str(self.vault)], check=True, capture_output=True)
        self.assertIn("| 2 | Project-doc schema | never | 2026-08-01 |", record.read_text())
        self.assertIn("| archive-namespace-opencairn-v1 | in-progress |", record.read_text())

        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        subprocess.run([str(MIGRATE), "rewrite", str(self.vault)], check=True, capture_output=True)
        subprocess.run([str(MIGRATE), "finish", str(self.vault)], check=True, capture_output=True)
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
            [str(MIGRATE), "begin", str(self.vault)],
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
        subprocess.run([str(MIGRATE), "rewrite", str(self.vault)], check=True, capture_output=True)
        subprocess.run([str(MIGRATE), "finish", str(self.vault)], check=True, capture_output=True)
        self.assertEqual((new / ".Session Transcripts/2026-01-01.md").read_text(), original)

    def test_transcript_without_legacy_locator_is_still_byte_verified(self):
        old = self.vault / "06 Archive/Claude"
        transcript = old / ".Session Transcripts/raw.txt"
        transcript.parent.mkdir(parents=True)
        transcript.write_text("immutable transcript without a path locator\n")

        begin = subprocess.run(
            [str(MIGRATE), "begin", str(self.vault)],
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
            [str(MIGRATE), "verify", str(self.vault)],
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
        subprocess.run([str(MIGRATE), "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)

        subprocess.run([str(MIGRATE), "rewrite", str(self.vault)], check=True, capture_output=True)
        self.assertTrue((new / "Session Logs/.2026-01-01.md.lock").is_file())
        subprocess.run([str(MIGRATE), "finish", str(self.vault)], check=True, capture_output=True)

    def test_empty_source_inventory_still_rejects_new_destination_member(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        subprocess.run([str(MIGRATE), "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)
        (new / "unexpected.md").write_text("unexpected\n")

        result = subprocess.run(
            [str(MIGRATE), "verify", str(self.vault)],
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
        subprocess.run([str(MIGRATE), "begin", str(self.vault)], check=True, capture_output=True)
        old.rename(self.vault / "06 Archive/OpenCairn")

        verify_before = subprocess.run(
            [str(MIGRATE), "verify", str(self.vault)], capture_output=True, text=True
        )
        self.assertNotEqual(verify_before.returncode, 0)
        subprocess.run([str(MIGRATE), "rewrite", str(self.vault)], check=True, capture_output=True)
        subprocess.run([str(MIGRATE), "finish", str(self.vault)], check=True, capture_output=True)
        self.assertIn("06 Archive/OpenCairn", note.read_text())

    def test_unfinished_journal_blocks_locator_clean_layouts_until_finish(self):
        old = self.vault / "06 Archive/Claude"
        old.mkdir(parents=True)
        subprocess.run([str(MIGRATE), "begin", str(self.vault)], check=True, capture_output=True)
        new = self.vault / "06 Archive/OpenCairn"
        old.rename(new)

        state = self.check_state()
        self.assertEqual(state["ARCHIVE_LAYOUT"], "pending-verification")
        self.assertEqual(state["MIGRATION_JOURNAL_PHASE"], "in-progress")
        enforce = subprocess.run(
            [str(CHECK), "--enforce", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(enforce.returncode, 20)
        self.assertIn("awaiting journal-backed verification", enforce.stderr)

        subprocess.run([str(MIGRATE), "finish", str(self.vault)], check=True, capture_output=True)
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "new-only")
        subprocess.run([str(CHECK), "--enforce", str(self.vault)], check=True, capture_output=True)

        journal_path = self.vault / "07 System/.OpenCairn Migration/archive-namespace-opencairn-v1.json"
        journal = json.loads(journal_path.read_text())
        journal["phase"] = "in-progress"
        journal_path.write_text(json.dumps(journal) + "\n")
        new.rmdir()
        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "pending-verification")

    def test_symlink_alias_is_never_treated_as_split_members(self):
        new = self.vault / "06 Archive/OpenCairn"
        new.mkdir(parents=True)
        (new / "only-copy.md").write_text("content\n")
        old = self.vault / "06 Archive/Claude"
        old.symlink_to("OpenCairn", target_is_directory=True)

        self.assertEqual(self.check_state()["ARCHIVE_LAYOUT"], "legacy-symlink-alias")
        self.assertEqual(self.inspect()["layout"], "legacy-symlink-alias")
        result = subprocess.run(
            [str(MIGRATE), "split-plan", str(self.vault)],
            text=True,
            capture_output=True,
            check=False,
        )
        report = json.loads(result.stdout)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["kind"], "legacy-symlink-alias")
        self.assertFalse(report["member_reconciliation_permitted"])
        self.assertNotIn("identical", report)

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
            [str(MIGRATE), "split-plan", str(self.vault)],
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
            text.index("### Step 3d: Recover the Migration Bundle, Then Gate"),
            text.index("### Step 4: Compare Working Tree Against Template"),
        )
        self.assertIn('check-archive-layout.sh" --status', text)
        self.assertIn("Do not offer independent accept/skip choices", text)
        self.assertIn("git checkout $REF -- <the-four-literal-paths>", text)
        self.assertIn("rg -q 'archive-namespace-opencairn-v1'", text)
        self.assertIn("old task-only `migrate.md`", text)


if __name__ == "__main__":
    unittest.main()
