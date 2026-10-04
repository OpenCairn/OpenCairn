import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/export-session-transcripts.py"
SCRIPTS = SCRIPT.parent

_spec = importlib.util.spec_from_file_location("transcript_exporter", SCRIPT)
exporter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exporter)

try:
    from session_isolation import isolate_session
except ImportError:  # `python -m unittest tests.<module>` from the repo root
    from tests.session_isolation import isolate_session


class ExportSessionTranscriptsTests(unittest.TestCase):
    def make_codex_rollout(self, home: Path, cwd: Path) -> Path:
        rollout = (
            home
            / ".codex/sessions/2026/08/16"
            / "rollout-2026-08-16T10-00-00-019c1234-5678-7abc-9def-0123456789ab.jsonl"
        )
        rollout.parent.mkdir(parents=True)
        records = [
            {
                "timestamp": "2026-08-16T00:00:00Z",
                "type": "session_meta",
                "payload": {"id": "019c1234-5678-7abc-9def-0123456789ab", "cwd": str(cwd)},
            },
            {
                "timestamp": "2026-08-16T00:00:01Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "Codex-only prompt"},
            },
            {
                "timestamp": "2026-08-16T00:00:02Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Codex-only response"}],
                },
            },
        ]
        rollout.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        return rollout

    def run_exporter(self, home: Path, vault: Path, cwd: Path, *args: str):
        vault_scripts = vault / ".claude/scripts"
        vault_scripts.mkdir(parents=True, exist_ok=True)
        for name in (
            "locked-edit.sh",
            "lib-lock.sh",
            "lib-session.sh",
            "archive-namespace-migration.py",
        ):
            shutil.copy2(SCRIPTS / name, vault_scripts / name)
        env = isolate_session(
            os.environ.copy(), home / ".claude", "export-transcripts-test"
        )
        env["HOME"] = str(home)
        return subprocess.run(
            ["python3", str(SCRIPT), str(vault), "--days", "7", *args],
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_help_and_invalid_arguments_do_not_create_archive(self) -> None:
        # Parse before archive-root --write: --help used to become a vault path.
        for arguments, expected_status in (
            (["--help"], 0),
            (["vault", "--help"], 0),
            (["vault", "--days", "not-a-number"], 2),
            (["vault", "--days"], 2),
            (["vault", "--typo"], 2),
        ):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "vault").mkdir()
                env = isolate_session(os.environ.copy(), root / "state", "export-help-test")
                env["HOME"] = str(root / "home")
                result = subprocess.run(
                    ["python3", str(SCRIPT), *arguments], cwd=root, env=env,
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, expected_status, result.stdout + result.stderr)
                self.assertEqual(list(root.rglob("*")), [root / "vault"], "argument parsing wrote files")

    def assert_codex_export(self, vault: Path, rollout: Path) -> None:
        date_str = datetime.fromtimestamp(rollout.stat().st_mtime).strftime("%Y-%m-%d")
        output = vault / "06 Archive/OpenCairn/.Session Transcripts" / f"{date_str}.md"
        self.assertTrue(output.is_file())
        text = output.read_text(encoding="utf-8")
        self.assertIn("Codex-only prompt", text)
        self.assertIn("Codex-only response", text)
        self.assertFalse((vault / "06 Archive/Claude").exists())

    def export_day_path(self, vault: Path, rollout: Path) -> Path:
        date_str = datetime.fromtimestamp(rollout.stat().st_mtime).strftime("%Y-%m-%d")
        return vault / "06 Archive/OpenCairn/.Session Transcripts" / f"{date_str}.md"

    def test_recovered_codex_prompt_reuses_existing_rollout_section(self) -> None:
        # Older app exports started at the first assistant minute. Recovering
        # the earlier user prompt changes the displayed time, not the rollout.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, vault, cwd = root / "home", root / "vault", root / "project"
            cwd.mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)
            records = [json.loads(line) for line in rollout.read_text().splitlines()]
            records.pop(1)
            records[-1]["timestamp"] = "2026-08-16T00:01:02Z"
            prompt = {"timestamp": "2026-08-16T00:00:59Z", "type": "response_item",
                "payload": {"type": "message", "role": "user",
                    "content": [{"type": "input_text", "text": "Recovered exact prompt"}],
                    "internal_chat_message_metadata_passthrough": {"content_item_kinds": ["user.text"]}}}
            records.insert(1, prompt)
            rollout.write_text("".join(json.dumps(record) + "\n" for record in records))
            output = self.export_day_path(vault, rollout)
            output.parent.mkdir(parents=True)
            slug = "codex-019c1234-5678"
            old_body = exporter.format_session([("codex", "Codex-only response", "2026-08-16T00:01:02Z")], slug, "00:01").split("\n", 1)[1]
            output.write_text(exporter.render_day_file(output.stem, {(slug, "00:01"): old_body}))
            result = self.run_exporter(home, vault, cwd, "--all-projects")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = output.read_text()
            self.assertEqual(text.count("Codex-only response"), 1)
            self.assertEqual(text.count("Recovered exact prompt"), 1)
            self.assertEqual(len(exporter.parse_exported_text(text)), 1)
            self.assertIn(f"### {slug} (00:00)", text)
            self.assertNotIn("Sessions carried forward", result.stdout)

    def test_carried_write_tool_trailing_rule_survives_without_source(self) -> None:
        # Write inputs keep their trailing newline, unlike plain message text.
        # This is an ordinary producer of the same suffix as old separator junk.
        record = {"timestamp": "2026-08-16T00:00:00Z", "type": "assistant",
            "message": {"content": [{"type": "tool_use", "name": "Write",
                "input": {"file_path": "Example.md", "content": "# Example\n\n---\n"}}]}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "old.jsonl"
            jsonl.write_text(json.dumps(record) + "\n")
            messages = exporter.parse_session(jsonl)
            body = exporter.format_session(messages, "carried-rule", "00:00").split("\n", 1)[1]
            jsonl.unlink()  # the day file is now the only retained source
            home, vault, cwd = root / "home", root / "vault", root / "project"
            cwd.mkdir()
            output = self.export_day_path(vault, self.make_codex_rollout(home, cwd))
            output.parent.mkdir(parents=True)
            output.write_text(exporter.render_day_file(output.stem, {("carried-rule", "00:00"): body}))
            for _ in range(2):
                result = self.run_exporter(home, vault, cwd, "--all-projects")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                carried = exporter.parse_exported_text(output.read_text())[("carried-rule", "00:00")]
                self.assertTrue(carried.endswith("---"), carried)

    def test_reexport_is_byte_stable(self) -> None:
        # The day file's final separator must not be read back as body text:
        # the old parser grew the last session by one `---` per re-export.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, vault, cwd = root / "home", root / "vault", root / "project"
            cwd.mkdir(parents=True)
            output = self.export_day_path(vault, self.make_codex_rollout(home, cwd))

            snapshots = []
            for _ in range(3):
                result = self.run_exporter(home, vault, cwd, "--all-projects")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                snapshots.append(output.read_bytes())

            self.assertEqual(snapshots[0], snapshots[1])
            self.assertEqual(snapshots[1], snapshots[2])

    def test_accumulated_separator_residue_collapses_on_reexport(self) -> None:
        # Files written by the old parser carry extra trailing separators;
        # one re-export must remove them.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, vault, cwd = root / "home", root / "vault", root / "project"
            cwd.mkdir(parents=True)
            output = self.export_day_path(vault, self.make_codex_rollout(home, cwd))

            self.assertEqual(self.run_exporter(home, vault, cwd, "--all-projects").returncode, 0)
            clean = output.read_bytes()
            output.write_bytes(clean + b"\n---\n\n" * 5)

            result = self.run_exporter(home, vault, cwd, "--all-projects")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(output.read_bytes(), clean)

    def test_carried_forward_sessions_survive_reexport(self) -> None:
        # Sessions with no JSONL behind them exist only in the day file, so the
        # parser's output is what gets written back. A message ending in `---`
        # must not fuse the next session into it, and a separator run inside a
        # body must survive.
        a_body = (
            "\n**User (09:00):**\nfirst\n\n**Claude (09:01):**\n"
            "rule below\n\n---\n\n\n---\n\nafter the rules\n\n---\n"
        )
        b_body = "\n**User (09:30):**\nsecond session\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, vault, cwd = root / "home", root / "vault", root / "project"
            cwd.mkdir(parents=True)
            output = self.export_day_path(vault, self.make_codex_rollout(home, cwd))
            output.parent.mkdir(parents=True)
            output.write_text(
                f"# Session Transcripts — {output.stem}\n\n"
                "Auto-exported from `~/.claude/projects/` and `~/.codex/sessions/` JSONL files.\n\n---\n\n"
                f"### carried-a (00:01)\n{a_body}\n---\n\n"
                f"### carried-b (00:02)\n{b_body}\n---\n\n",
                encoding="utf-8",
            )

            snapshots = []
            for _ in range(2):
                result = self.run_exporter(home, vault, cwd, "--all-projects")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                snapshots.append(output.read_text(encoding="utf-8"))

            text = snapshots[-1]
            self.assertEqual(snapshots[0], snapshots[1])
            self.assertEqual(text.count("### carried-a (00:01)"), 1)
            self.assertEqual(text.count("### carried-b (00:02)"), 1)
            self.assertEqual(text.count("second session"), 1)
            self.assertIn(a_body.rstrip(), text)
            self.assertIn("Codex-only response", text)
            a_section = text.split("### carried-a (00:01)", 1)[1].split("### carried-b", 1)[0]
            self.assertNotIn("second session", a_section)

    def test_explicit_codex_user_text_is_exported_without_injected_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, vault, cwd = root / "home", root / "vault", root / "project"
            cwd.mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)
            records = [json.loads(line) for line in rollout.read_text().splitlines()]
            records.pop(1)  # Current app rollouts have no event_msg/user_message.
            prompt = "Please preserve this exact prompt."
            for content, kinds in (
                (["injected instructions", "environment"], ["agents_md.instructions", "environments.environment_context"]),
                (["injected skill"], ["skills.selected_skill_instructions"]),
                ([prompt], ["user.text"]),
            ):
                records.insert(-1, {
                    "timestamp": "2026-08-16T00:00:01Z", "type": "response_item",
                    "payload": {"type": "message", "role": "user",
                        "content": [{"type": "input_text", "text": text} for text in content],
                        "internal_chat_message_metadata_passthrough": {"content_item_kinds": kinds}},
                })
            rollout.write_text("".join(json.dumps(r) + "\n" for r in records))
            result = self.run_exporter(home, vault, cwd)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = self.export_day_path(vault, rollout).read_text()
            self.assertIn(prompt, text)
            self.assertNotIn("injected instructions", text)
            self.assertNotIn("environment", text)
            self.assertNotIn("injected skill", text)
            self.assertIn("Codex-only response", text)

    def test_legacy_codex_user_message_does_not_duplicate_wrapped_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, vault, cwd = root / "home", root / "vault", root / "project"
            cwd.mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)
            with rollout.open("a") as f:
                f.write(json.dumps({"type": "response_item", "payload": {
                    "type": "message", "role": "user", "content": [
                        {"type": "input_text", "text": "Codex-only prompt"}]}}) + "\n")
            result = self.run_exporter(home, vault, cwd)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.export_day_path(vault, rollout).read_text().count("Codex-only prompt"), 1)

    def test_separator_residue_and_header_line_endings_converge(self) -> None:
        merged = {("kept", "09:00"): "**User:**\nkept text"}
        clean = exporter.render_day_file("2026-08-16", merged)
        for residue in ("\n---\n\n", "\n---\n\n\n", "\n---\n\n" * 5):
            with self.subTest(residue=repr(residue)):
                parsed = exporter.parse_exported_text(clean + residue)
                # A parser cannot identify source-free horizontal rules as junk.
                # Only a freshly regenerated matching body licenses repair.
                retained = parsed[("kept", "09:00")]
                repaired = exporter.source_backed_body(retained, merged[("kept", "09:00")])
                self.assertEqual(exporter.render_day_file("2026-08-16", {("kept", "09:00"): repaired}), clean)
        mixed = clean.replace("### kept (09:00)\n", "### kept (09:00)\r\n")
        self.assertEqual(exporter.render_day_file("2026-08-16", exporter.parse_exported_text(mixed)), clean)

    def test_all_projects_works_without_claude_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            vault = root / "vault"
            cwd = root / "project"
            cwd.mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)

            result = self.run_exporter(home, vault, cwd, "--all-projects")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("0 Claude project(s), 1 Codex rollout(s)", result.stdout)
            self.assert_codex_export(vault, rollout)

    def test_cwd_scoped_export_works_without_claude_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            vault = root / "vault"
            cwd = root / "project"
            cwd.mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)

            result = self.run_exporter(home, vault, cwd)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Session source: Codex rollouts", result.stdout)
            self.assert_codex_export(vault, rollout)

    def test_old_only_vault_exports_to_legacy_root_without_migrating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            vault = root / "vault"
            cwd = root / "project"
            cwd.mkdir(parents=True)
            (vault / "06 Archive/Claude").mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)

            result = self.run_exporter(home, vault, cwd)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            date_str = datetime.fromtimestamp(rollout.stat().st_mtime).strftime("%Y-%m-%d")
            self.assertTrue(
                (vault / "06 Archive/Claude/.Session Transcripts" / f"{date_str}.md").is_file()
            )
            self.assertFalse((vault / "06 Archive/OpenCairn").exists())

    def test_split_vault_refuses_export_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            vault = root / "vault"
            cwd = root / "project"
            cwd.mkdir(parents=True)
            (vault / "06 Archive/Claude").mkdir(parents=True)
            (vault / "06 Archive/OpenCairn").mkdir()
            self.make_codex_rollout(home, cwd)

            result = self.run_exporter(home, vault, cwd)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refused unsafe or contradictory archive state", result.stderr)
            self.assertFalse((vault / "07 System/Migration Record.md").exists())


if __name__ == "__main__":
    unittest.main()
