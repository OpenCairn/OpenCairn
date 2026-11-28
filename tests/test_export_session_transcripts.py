import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
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


    def test_session_header_time_is_converted_to_utc(self) -> None:
        # Header times are labelled UTC; an offset timestamp must be converted,
        # not formatted in its own zone.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home, vault, cwd = root / "home", root / "vault", root / "project"
            cwd.mkdir(parents=True)
            rollout = self.make_codex_rollout(home, cwd)
            records = [json.loads(line) for line in rollout.read_text().splitlines()]
            records[1]["timestamp"] = "2026-08-16T10:05:01+10:00"
            rollout.write_text("".join(json.dumps(r) + "\n" for r in records))
            claude = home / ".claude/projects/p/abcdef12-session.jsonl"
            claude.parent.mkdir(parents=True)
            claude.write_text(json.dumps({"type": "user", "timestamp": "2026-08-16T10:07:00+10:00",
                "slug": "offset-claude", "message": {"role": "user", "content": "offset prompt"}}) + "\n")
            result = self.run_exporter(home, vault, cwd, "--all-projects")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = "".join(f.read_text() for f in (vault / "06 Archive/OpenCairn/.Session Transcripts").glob("*.md"))
            self.assertIn("### codex-019c1234-5678 (00:05)", text)
            self.assertIn("### offset-claude (00:07)", text)

    def test_queued_human_prompt_is_a_user_turn_with_utc_time(self) -> None:
        # A message typed mid-turn is a queued_command attachment, not a user
        # record. Only human-origin prompts are user turns.
        def queued(text, mode="prompt", kind="human"):
            return {"type": "attachment", "timestamp": "2026-11-01T13:33:27.194Z",
                "attachment": {"type": "queued_command", "prompt": text,
                    "commandMode": mode, "origin": {"kind": kind}}}
        records = [
            {"type": "user", "timestamp": "2026-11-01T13:28:00Z",
                "message": {"role": "user", "content": "start the audit"}},
            queued("you can go to 8 am"),
            queued([{"type": "text", "text": "list-form prompt"}]),
            queued("<task-notification>done</task-notification>", "task-notification", "task-notification"),
            queued("peer session note", kind="peer"),
            {"type": "assistant", "timestamp": "2026-11-01T13:34:00Z",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "noted"}]}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
            messages = exporter.parse_session(path)
        self.assertEqual(
            [(role, text) for role, text, _ts in messages],
            [("user", "start the audit"), ("user_queued", "you can go to 8 am"),
             ("user_queued", "list-form prompt"), ("assistant", "noted")],
        )
        rendered = exporter.format_session(messages, "slug", "13:28")
        self.assertIn("**User, queued mid-turn (13:33 UTC):**\nyou can go to 8 am\n", rendered)
        self.assertIn("**User (13:28 UTC):**\nstart the audit\n", rendered)
        self.assertNotIn("peer session note", rendered)
        self.assertNotIn("task-notification", rendered)
        # A header re-parses unchanged, so day-file merge keys are stable.
        self.assertIn(("slug", "13:28"), exporter.parse_exported_text(rendered + exporter.SEPARATOR))

    # --verify-session: the receipt must name the heading the exporter wrote,
    # in the dated file it chose, read back from disk.
    CLAUDE_ID = "5bb930aa-4885-440c-b1cc-5027a09b0780"
    CODEX_ID = "019c1234-5678-7abc-9def-0123456789ab"

    def make_claude_session(self, home: Path, cwd: Path, slug=None, records=None, sid=None) -> Path:
        path = home / ".claude/projects" / str(cwd).replace("/", "-") / f"{sid or self.CLAUDE_ID}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        if records is None:
            first = {"type": "user", "timestamp": "2026-08-16T03:04:00Z",
                "message": {"role": "user", "content": "verify prompt"}}
            if slug:
                first["slug"] = slug
            records = [first, {"type": "assistant", "timestamp": "2026-08-16T03:05:00Z",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "verify reply"}]}}]
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        return path

    def verify_roots(self, tmp):
        root = Path(tmp).resolve()
        home, vault, cwd = root / "home", root / "vault", root / "project"
        cwd.mkdir(parents=True)
        return home, vault, cwd

    def assert_receipt(self, result, harness, sid, day_file: Path, heading: str) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        receipts = [l for l in result.stdout.splitlines() if l.startswith("Export verified:")]
        self.assertEqual(receipts, [f"Export verified: {harness}:{sid} | {day_file} | {heading}"])
        self.assertIn(heading, day_file.read_text(encoding="utf-8").splitlines())

    def assert_no_receipt(self, result) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Export verified", result.stdout)
        self.assertTrue(result.stderr.strip())

    def test_verify_session_claude_with_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd, slug="brisk-otter")
            result = self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}")
            self.assert_receipt(result, "claude", self.CLAUDE_ID, self.export_day_path(vault, src), "### brisk-otter (03:04)")

    def test_verify_session_claude_slugless_uses_stem_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd)
            result = self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}")
            self.assert_receipt(result, "claude", self.CLAUDE_ID, self.export_day_path(vault, src), "### 5bb930aa (03:04)")

    def test_verify_session_codex_uses_id13_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_codex_rollout(home, cwd)
            result = self.run_exporter(home, vault, cwd, "--verify-session", f"codex:{self.CODEX_ID}")
            self.assert_receipt(result, "codex", self.CODEX_ID, self.export_day_path(vault, src), "### codex-019c1234-5678 (00:00)")
            self.assertNotIn(f"### codex-{self.CODEX_ID}", self.export_day_path(vault, src).read_text())

    def test_verify_session_cross_day_names_mtime_dated_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd, slug="late-night")
            earlier = (datetime.now() - timedelta(days=2)).replace(hour=12).timestamp()
            os.utime(src, (earlier, earlier))
            day_file = self.export_day_path(vault, src)
            self.assertNotEqual(day_file.stem, datetime.now().strftime("%Y-%m-%d"))
            result = self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}")
            self.assert_receipt(result, "claude", self.CLAUDE_ID, day_file, "### late-night (03:04)")

    def test_verify_session_unknown_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            self.make_claude_session(home, cwd, slug="brisk-otter")
            self.make_codex_rollout(home, cwd)
            for value in ("claude:00000000-0000-0000-0000-000000000000",
                          f"codex:{self.CLAUDE_ID}", f"claude:{self.CODEX_ID}"):
                with self.subTest(value=value):
                    self.assert_no_receipt(self.run_exporter(home, vault, cwd, "--verify-session", value))

    def test_verify_session_empty_or_excluded_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            self.make_claude_session(home, cwd, records=[{"type": "summary", "summary": "x"}])
            self.assert_no_receipt(self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}"))
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd, slug="stale")
            old = (datetime.now() - timedelta(days=30)).timestamp()
            os.utime(src, (old, old))
            self.assert_no_receipt(self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}"))
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            self.make_claude_session(home, cwd, slug="here")
            self.make_codex_rollout(home, cwd.parent / "elsewhere")  # outside cwd scope
            self.assert_no_receipt(self.run_exporter(home, vault, cwd, "--verify-session", f"codex:{self.CODEX_ID}"))

    OTHER_ID = "7d3e0c1a-0000-4000-8000-00000000beef"

    @staticmethod
    def shared_key_records(text):
        return [{"type": "user", "timestamp": "2026-08-16T03:04:00Z", "slug": "shared-slug",
                 "message": {"role": "user", "content": text}}]

    def test_verify_session_rejects_shared_key_sources_as_ambiguous(self) -> None:
        # Two Claude sources sharing slug and UTC start minute share one day-file
        # key and the merge keeps one body; neither can be verified from it.
        for short_text, long_text in (("short source", "other source, much longer body"),
                                      ("short", "shorter, but wholly different source")):
            with self.subTest(short=short_text), tempfile.TemporaryDirectory() as tmp:
                home, vault, cwd = self.verify_roots(tmp)
                src = self.make_claude_session(home, cwd, records=self.shared_key_records(short_text))
                self.make_claude_session(home, cwd, records=self.shared_key_records(long_text), sid=self.OTHER_ID)
                for sid in (self.CLAUDE_ID, self.OTHER_ID):
                    result = self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{sid}")
                    self.assert_no_receipt(result)
                    self.assertIn("ambiguous", result.stderr)
                self.assertIn("### shared-slug (03:04)", self.export_day_path(vault, src).read_text().splitlines())

    def test_verify_session_rejects_prefix_ending_mid_message(self) -> None:
        # The day file already holds another source's section under the key;
        # our body is a character prefix of it, not a message prefix.
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd, records=self.shared_key_records("short"))
            foreign = self.make_claude_session(
                home, cwd.parent / "scratch", records=self.shared_key_records("shorter, but wholly different source"))
            body = exporter.format_session(exporter.parse_session(foreign), "shared-slug", "03:04").split("\n", 1)[1]
            foreign.unlink()
            day_file = self.export_day_path(vault, src)
            day_file.parent.mkdir(parents=True)
            day_file.write_text(exporter.render_day_file(day_file.stem, {("shared-slug", "03:04"): body}))
            self.assert_no_receipt(self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}"))

    def test_verify_session_longer_retained_copy_is_identity_inconclusive(self) -> None:
        # A day file already holding a longer copy under this heading may be this
        # session's older export or a pruned different source: no provenance
        # proves which, so the merge keeps it on disk but no receipt is issued.
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd, slug="brisk-otter")
            body = exporter.format_session(exporter.parse_session(src), "brisk-otter", "03:04").split("\n", 1)[1]
            day_file = self.export_day_path(vault, src)
            day_file.parent.mkdir(parents=True)
            longer = body.rstrip() + "\n\n**User (03:09 UTC):**\nlater turn since dropped from the source\n"
            day_file.write_text(exporter.render_day_file(day_file.stem, {("brisk-otter", "03:04"): longer}))
            result = self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}")
            self.assert_no_receipt(result)
            self.assertIn("identity inconclusive", result.stderr)
            self.assertIn("later turn since dropped", day_file.read_text())

    def test_verify_session_pruned_other_source_longer_transcript_fails(self) -> None:
        # A different UUID exported a longer transcript under the same heading
        # whose whole-message prefix equals ours, then its JSONL was pruned.
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd, records=self.shared_key_records("short"))
            other = self.make_claude_session(home, cwd, records=self.shared_key_records("short") + [
                {"type": "assistant", "timestamp": "2026-08-16T03:06:00Z",
                    "message": {"role": "assistant", "content": [{"type": "text", "text": "other session's later reply"}]}}],
                sid=self.OTHER_ID)
            self.run_exporter(home, vault, cwd)
            other.unlink()  # the other UUID's source is pruned; only its day-file section remains
            day_file = self.export_day_path(vault, src)
            self.assertIn("other session's later reply", day_file.read_text())
            result = self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}")
            self.assert_no_receipt(result)
            self.assertIn("identity inconclusive", result.stderr)
            self.assertIn("other session's later reply", day_file.read_text())

    def test_verify_session_quoted_day_file_in_message_passes(self) -> None:
        # A quoted separator + header inside a message must not be read as a
        # session boundary by the verify path.
        quote = "copied transcript:\n\n---\n\n### other-slug (10:00)\nquoted session body"
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd, records=[{"type": "user", "slug": "quoting",
                "timestamp": "2026-08-16T03:04:00Z", "message": {"role": "user", "content": quote}}])
            result = self.run_exporter(home, vault, cwd, "--verify-session", f"claude:{self.CLAUDE_ID}")
            self.assert_receipt(result, "claude", self.CLAUDE_ID, self.export_day_path(vault, src), "### quoting (03:04)")

    def test_verify_inconclusive_when_day_file_changed_after_write(self) -> None:
        import contextlib, io
        with tempfile.TemporaryDirectory() as tmp:
            day = Path(tmp) / "2026-08-16.md"
            day.write_bytes(b"written by this run")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(exporter.finish_verify("claude:x", "### s (00:00)", day, b"written by this run"), 0)
            self.assertIn("Export verified: claude:x |", out.getvalue())
            day.write_bytes(b"rewritten by a concurrent exporter")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(exporter.finish_verify("claude:x", "### s (00:00)", day, b"written by this run"), 3)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("inconclusive", err.getvalue())

    def test_verify_session_malformed_value_is_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            for value in ("claude", "gemini:abc", "claude:", ":abc"):
                with self.subTest(value=value):
                    result = self.run_exporter(home, vault, cwd, "--verify-session", value)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("usage:", result.stderr)
            self.assertFalse((vault / "06 Archive").exists())

    def test_summary_output_unchanged_without_verify_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, vault, cwd = self.verify_roots(tmp)
            src = self.make_claude_session(home, cwd, slug="brisk-otter")
            plain = self.run_exporter(home, vault, cwd)
            self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
            self.assertEqual(plain.stdout.splitlines()[1:], [
                "Sessions exported: 1 (0 Codex)",
                "Export counts JSONL source files, not parked session-log entries.",
                "Sessions skipped (empty): 0",
                "Transcript files written: 1",
                f"  {self.export_day_path(vault, src).stem}: 1 sessions",
            ])
            verified = self.run_exporter(home, vault.parent / "vault2", cwd,
                                         "--verify-session", f"claude:{self.CLAUDE_ID}")
            lines = verified.stdout.splitlines()
            self.assertEqual(lines[:-1], plain.stdout.splitlines())
            self.assertTrue(lines[-1].startswith("Export verified: "))

if __name__ == "__main__":
    unittest.main()
