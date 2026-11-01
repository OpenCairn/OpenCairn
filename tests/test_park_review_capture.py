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
        self.assertEqual(receipts[0]["schema"], 3)
        self.assertEqual(receipts[0]["kind"], "completion")
        self.assertTrue(receipts[0]["completion"])
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

    def test_terminal_state_must_be_the_exact_final_line_lookup_reads(self):
        complete = self.report.splitlines()[0]
        for tail in ("**Terminal state:** clean.", "- `Terminal state: clean`",
                     "## Terminal state — clean", "Terminal state: clean\nTrailing note."):
            with self.subTest(tail=tail):
                result = self.record(f"{complete}\n{tail}\n")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("terminal state is not clean", result.stderr)
        self.assertEqual(self.receipts(), [])
        result = self.record(f"{complete}\nTerminal state: clean\n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        # The completion retention/lookup predicate accepts what record-audit accepted.
        self.assertTrue(all(r["report"].rstrip().endswith("Terminal state: clean")
                            for r in self.receipts()))

    def test_targeted_source_change_rejects_old_completion(self):
        self.target.write_text("Changed after review.\n", encoding="utf-8")
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed after review", result.stderr)
        self.assertEqual(self.receipts(), [])

    def targeted_second_session(self) -> bytes:
        self.log.write_bytes(self.log.read_bytes() +
            b"\n\n## Session 2 - Earlier owned work\n\n### Summary\nOWNED wording.\n")
        classified = self.run_review("classify", "--vault", str(self.vault), "--path", str(self.log),
            "--semantic", "--targeted", "--inspection-target", "Session 2 Summary: OWNED wording")
        self.assertEqual(classified.returncode, 0, classified.stderr)
        self.build()
        return self.log.read_bytes()

    def test_targeted_work_in_another_existing_session_cannot_be_overwritten(self):
        original = self.targeted_second_session()
        self.log.write_bytes(original.replace(b"OWNED wording", b"OVERWRITTEN wording"))
        rejected = self.record()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("changed after review", rejected.stderr)
        self.assertEqual(self.receipts(), [])

    def test_targeted_existing_sessions_allow_a_fresh_session_append(self):
        original = self.targeted_second_session()
        writer = Path(__file__).parents[1] / ".claude/scripts/write-session.sh"
        appended = subprocess.run(["bash", str(writer), str(self.log), "--auto-number", "Concurrent work", "09:00am"],
            input="### Summary\nIndependent fixture work.\n", text=True, capture_output=True,
            env={**self.env, "OPENCAIRN_SESSION_ID": "concurrent-fixture"})
        self.assertEqual(appended.returncode, 0, appended.stderr)
        self.assertIn("Session number assigned: 3", appended.stdout)
        self.assertTrue(self.log.read_bytes().startswith(original))
        accepted = self.record()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(self.receipts()[0]["kind"], "completion")
        self.assertEqual(self.receipts()[0]["files"], [])

    def test_targeted_last_session_allows_only_a_new_session_append(self):
        original = self.log.read_bytes()
        writer = Path(__file__).parents[1] / ".claude/scripts/write-session.sh"
        appended = subprocess.run(["bash", str(writer), str(self.log), "--auto-number", "Concurrent work", "09:00am"],
            input="### Summary\nIndependent fixture work.\n", text=True, capture_output=True,
            env={**self.env, "OPENCAIRN_SESSION_ID": "concurrent-fixture"})
        self.assertEqual(appended.returncode, 0, appended.stderr)
        self.assertIn("Session number assigned: 2", appended.stdout)
        self.assertTrue(self.log.read_bytes().startswith(original))
        accepted = self.record()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_targeted_existing_session_tail_change_requires_rebuild(self):
        original = self.targeted_second_session()
        self.log.write_bytes(original + b"\nAn unproved addendum inside the owned Session 2.\n")
        rejected = self.record()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("changed after review", rejected.stderr)
        self.assertEqual(self.receipts(), [])

    def test_targeted_append_cannot_duplicate_an_existing_session_heading(self):
        original = self.targeted_second_session()
        self.log.write_bytes(original + b"\n\n## Session 2 - Duplicate locator\n\n### Summary\nAmbiguous.\n")
        rejected = self.record()
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("changed after review", rejected.stderr)
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

    def test_standalone_source_attestation_is_not_same_generation_completion(self):
        digest = hashlib.sha256(self.target.read_bytes()).hexdigest()
        imported = self.run_review("record-audit", "--reviewer", "fixture", "--file", str(self.target),
                                   stdin=f"ATTEST {digest} {self.target}\nTerminal state: clean\n")
        self.assertEqual(imported.returncode, 0, imported.stderr)
        source_receipt = self.receipts()[0]
        self.assertEqual(source_receipt["kind"], "source-attestation")
        self.assertFalse(source_receipt["completion"])
        self.assertNotIn("session_log", source_receipt)
        completed = self.record()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        completion = next(item for item in self.receipts() if item["kind"] == "completion")
        self.assertEqual(source_receipt["run_generation"], completion["run_generation"])
        self.assertTrue(completion["completion"])
        self.assertEqual(completion["session_log"], str(self.log))
        self.assertEqual(completion["session_number"], 1)
        self.assertEqual(hashlib.sha256(Path(completion["manifest_snapshot"]).read_bytes()).hexdigest(),
                         completion["manifest_sha256"])
        self.assertEqual(hashlib.sha256(Path(completion["brief_snapshot"]).read_bytes()).hexdigest(),
                         completion["brief_sha256"])

    def test_full_read_report_replay_cannot_accept_new_packet_with_unchanged_sources(self):
        for path in (self.target, self.log):
            classified = self.run_review("classify", "--vault", str(self.vault), "--path", str(path), "--semantic")
            self.assertEqual(classified.returncode, 0, classified.stderr)
        self.build()
        first = json.loads((self.root / "review-brief-manifest.json").read_text())
        attest = "".join(f"ATTEST {item['sha256']} {item['path']}\n" for item in first["full_read"])
        old_report = attest + self.report
        captured = self.run_review("capture", "--kind", "evidence", "--label", "new packet fact",
                                   "--source", "fixture", "--provenance", "primary", stdin="A new review input.")
        self.assertEqual(captured.returncode, 0, captured.stderr)
        self.build()
        second = json.loads((self.root / "review-brief-manifest.json").read_text())
        self.assertEqual({x["path"]: x["sha256"] for x in first["full_read"]},
                         {x["path"]: x["sha256"] for x in second["full_read"]})
        self.assertNotEqual(first["brief_sha256"], second["brief_sha256"])
        stale = self.record(old_report)
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("stale completion attestation", stale.stderr)
        unbound = self.record(attest + "Terminal state: clean\n")
        self.assertNotEqual(unbound.returncode, 0)
        self.assertIn("completion attestation", unbound.stderr)
        accepted = self.record(attest + self.report)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_full_read_report_replay_across_new_generation_is_rejected(self):
        for path in (self.target, self.log):
            self.assertEqual(self.run_review("classify", "--vault", str(self.vault),
                "--path", str(path), "--semantic").returncode, 0)
        self.build()
        first = json.loads((self.root / "review-brief-manifest.json").read_text())
        attest = "".join(f"ATTEST {item['sha256']} {item['path']}\n" for item in first["full_read"])
        old_report = attest + self.report
        self.root = Path(json.loads(self.run_review("begin-run").stdout)["root"])
        for path in (self.target, self.log):
            self.assertEqual(self.run_review("classify", "--vault", str(self.vault),
                "--path", str(path), "--semantic").returncode, 0)
        self.assertEqual(self.run_review("capture", "--kind", "propagation", "--label", "nil",
            stdin="Checked empty enumeration.").returncode, 0)
        self.assertEqual(self.run_review("run-verifier", "--", sys.executable, "-c",
            "print('RESULT: PASS')").returncode, 0)
        self.build()
        second = json.loads((self.root / "review-brief-manifest.json").read_text())
        self.assertNotEqual(first["run_generation"], second["run_generation"])
        self.assertEqual({x["path"]: x["sha256"] for x in first["full_read"]},
                         {x["path"]: x["sha256"] for x in second["full_read"]})
        replay = self.record(old_report)
        self.assertNotEqual(replay.returncode, 0)
        self.assertIn("stale completion attestation", replay.stderr)
        self.assertEqual(self.record(attest + self.report).returncode, 0)

    def test_removed_new_manifest_binding_cannot_downgrade_to_legacy(self):
        path = self.root / "review-brief-manifest.json"
        manifest = json.loads(path.read_text())
        manifest.pop("completion_binding")
        manifest["schema"] = 2
        path.write_text(json.dumps(manifest))
        (self.root / "completion-binding.json").unlink()
        result = self.record()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("completion binding", result.stderr)

    def test_partial_standalone_import_does_not_shrink_a_multifile_report(self):
        report = (f"ATTEST {hashlib.sha256(self.target.read_bytes()).hexdigest()} {self.target}\n"
                  f"ATTEST {hashlib.sha256(self.log.read_bytes()).hexdigest()} {self.log}\nTerminal state: clean\n")
        result = self.run_review("record-audit", "--reviewer", "fixture", "--file", str(self.target), stdin=report)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected attestation", result.stderr)
        self.assertEqual(self.receipts(), [])

    def test_cited_companion_requires_attribution_or_captured_source(self):
        companion = self.vault / "companion - evidence.md"
        companion.write_text("A supporting pre-state passage.\n")
        classified = self.run_review("classify", "--vault", str(self.vault), "--path", str(self.target),
            "--semantic", "--targeted", "--inspection-target", f"Source passage in `{companion}`")
        self.assertEqual(classified.returncode, 0, classified.stderr)
        args = ["build", "--vault", str(self.vault), "--session-log", str(self.log), "--number", "1", "--check-dependencies"]
        missing = self.run_review(*args)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn(str(companion), missing.stderr)
        self.assertIn("Dependency coverage", missing.stderr)
        captured = self.run_review("capture", "--kind", "prestate", "--source", str(companion),
                                   "--label", "companion", stdin=companion.read_text())
        self.assertEqual(captured.returncode, 0, captured.stderr)
        covered = self.run_review(*args)
        self.assertEqual(covered.returncode, 0, covered.stderr)
        manifest = json.loads((self.root / "review-brief-manifest.json").read_text())
        self.assertIn(str(companion), manifest["dependency_coverage"]["covered"])
        self.assertEqual(manifest["dependency_coverage"]["missing"], [])

    def test_remote_row_needs_exact_mutation_command_in_strict_dependency_mode(self):
        remote = "fixture-host:/opt/tool"
        self.log.write_text(self.log.read_text().replace("### Pickup Context", f"- `{remote}` (remote) - simulated fixture\n\n### Pickup Context"))
        self.assertEqual(self.run_review("classify", "--vault", str(self.vault), "--path", str(self.log),
            "--semantic", "--targeted", "--inspection-target", "Session 1").returncode, 0)
        args = ["build", "--vault", str(self.vault), "--session-log", str(self.log), "--number", "1", "--check-dependencies"]
        missing = self.run_review(*args)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("missing_remote_mutation", missing.stderr)
        captured = self.run_review("capture", "--kind", "evidence", "--source", "simulated fixture",
            "--provenance", "unverified", "--label", "remote transfer fixture", "--mutation-for", remote,
            "--command", "scp local-fixture fixture-host:/opt/tool", "--cwd", str(self.base), "--exit-status", "0",
            stdin="A simulated command receipt for the isolated fixture; no remote action is executed.")
        self.assertEqual(captured.returncode, 0, captured.stderr)
        self.assertEqual(self.run_review(*args).returncode, 0)

    def test_web_run_open_detection_ignores_key_order(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("park_review_web", HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        opens = [
            'await tools.web__run({"open":[{"ref_id":"u"}]})',
            'await tools.web__run({"response_length":"long","open":[{"ref_id":"u"}]})',
            "await tools.web__run({response_length: 'long', fetch: [{url: 'u'}]})",
        ]
        not_opens = [
            'await tools.web__run({"search_query":[{"q":"open: now"}]})',
            "await tools.web__run({search_query: [{q: 'x', meta: {open: 1}}]})",
        ]
        for source in opens:
            with self.subTest(source=source):
                self.assertTrue(module.web_run_opens(source))
        for source in not_opens:
            with self.subTest(source=source):
                self.assertFalse(module.web_run_opens(source))

    def test_native_tool_families_content_blocks_and_async_wait_keep_passage_support(self):
        url = "https://example.invalid/source"
        passage = "The retained source says the limit is 12 units."
        records = [
            {"type": "response_item", "payload": {"type": "custom_tool_call", "call_id": "exec-1",
                "name": "functions.exec", "input": f'await tools.web__run({{"response_length":"long","open":[{{"ref_id":"{url}"}}]}})'}},
            {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "exec-1",
                "output": [{"type": "text", "text": "Script running with cell ID cell-1"}]}},
            {"type": "response_item", "payload": {"type": "function_call", "call_id": "wait-1",
                "name": "functions.wait", "arguments": json.dumps({"cell_id": "cell-1"})}},
            {"type": "response_item", "payload": {"type": "custom_tool_call_output", "call_id": "wait-1",
                "output": json.dumps({"content": [{"type": "text", "text": passage},
                    {"type": "text", "text": "A later supporting paragraph."}]})}},
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "read-1",
                "name": "Read", "input": {"file_path": "/fixture/source.md"}}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "read-1",
                "content": [{"type": "text", "text": "Read result retained too."}]}]}},
        ]
        transcript = self.base / "rollout.jsonl"
        encoded_lines = [json.dumps(json.dumps(x)) if i == 3 else json.dumps(x) for i, x in enumerate(records)]
        transcript.write_bytes(("\r\n".join(encoded_lines) + "\r\n").encode("utf-8"))
        claims = self.base / "claims.json"
        claims.write_text(json.dumps([{"source": url, "call_id": "exec-1", "passage": passage}]))
        result = self.run_review("capture-tools", "--transcript", str(transcript), "--claims-file", str(claims))
        self.assertEqual(result.returncode, 0, result.stderr)
        index = json.loads((self.root / "tool-source-index.json").read_text())
        self.assertEqual(len(index["records"]), 3)
        waited = next(item for item in index["records"] if item["call_id"] == "wait-1")
        self.assertEqual(waited["parent_call_id"], "exec-1")
        self.assertEqual(waited["requested_sources"], [url])
        self.assertEqual(waited["support"], [passage])
        self.assertEqual(Path(waited["raw_path"]).read_bytes(), (encoded_lines[3] + "\r\n").encode("utf-8"))
        self.assertIn("A later supporting paragraph.", Path(waited["text_path"]).read_text())
        self.assertTrue(any(item["call_id"] == "read-1" for item in index["records"]))
        self.assertEqual(self.run_review("capture-tools", "--transcript", str(transcript)).returncode, 0)
        self.assertEqual(len(json.loads((self.root / "tool-source-index.json").read_text())["records"]), 3)

    def test_tool_source_claim_rejects_metadata_only_and_wrong_passage(self):
        url = "https://example.invalid/metadata"
        transcript = self.base / "metadata.jsonl"
        transcript.write_text("\n".join(json.dumps(x) for x in [
            {"type": "response_item", "payload": {"type": "function_call", "call_id": "meta-1",
                "name": "web.run", "arguments": json.dumps({"open": [{"ref_id": url}]})}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "meta-1",
                "output": {"url": url, "title": "A title without source text"}}},
        ]))
        claims = self.base / "claims.json"
        claims.write_text(json.dumps([{"source": url, "passage": "A title without source text"}]))
        result = self.run_review("capture-tools", "--transcript", str(transcript), "--claims-file", str(claims))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no captured passage supports", result.stderr)
        records = json.loads((self.root / "tool-source-index.json").read_text())["records"]
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["metadata_only"])

    def test_aliases_share_physical_classification_and_conflicts_fail(self):
        alias = self.vault / "source-alias.txt"
        alias.symlink_to(self.target)
        conflict = self.run_review("classify", "--vault", str(self.vault), "--path", str(alias), "--reference")
        self.assertNotEqual(conflict.returncode, 0)
        self.assertIn("alias conflicts", conflict.stderr)
        same = self.run_review("classify", "--vault", str(self.vault), "--path", str(alias),
                               "--semantic", "--targeted", "--inspection-target", "source passage")
        self.assertEqual(same.returncode, 0, same.stderr)
        self.log.write_text(self.log.read_text().replace("### Pickup Context", f"- `{alias}` - alias\n\n### Pickup Context"))
        self.assertEqual(self.run_review("classify", "--vault", str(self.vault), "--path", str(self.log),
            "--semantic", "--targeted", "--inspection-target", "Session 1").returncode, 0)
        self.build()
        manifest = json.loads((self.root / "review-brief-manifest.json").read_text())
        self.assertEqual(sum(item["path"] == str(self.target) for item in manifest["targeted_review"]), 1)
        self.assertIn(f"`{alias}` -> `{self.target}`", self.brief.read_text())
        same_bytes = self.vault / "different-source.txt"
        same_bytes.write_bytes(self.target.read_bytes())
        alias.unlink()
        alias.symlink_to(same_bytes)
        changed = self.record()
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn("attributed alias changed", changed.stderr)

    def test_unclassified_updated_text_requires_explicit_mode(self):
        unknown = self.vault / "unclassified.md"
        unknown.write_text("Unclassified fixture.\n")
        self.log.write_text(self.log.read_text().replace("### Pickup Context", f"- `{unknown}` - changed\n\n### Pickup Context"))
        self.assertEqual(self.run_review("classify", "--vault", str(self.vault), "--path", str(self.log),
            "--semantic", "--targeted", "--inspection-target", "Session 1").returncode, 0)
        result = self.run_review("build", "--vault", str(self.vault), "--session-log", str(self.log), "--number", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unclassified file", result.stderr)

    def test_generation_has_one_classification_writer(self):
        env = {**self.env, "OPENCAIRN_AGENT_ID": "different-writer"}
        result = subprocess.run([sys.executable, str(HELPER), "classify", "--vault", str(self.vault),
            "--path", str(self.target), "--semantic"], env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another writer", result.stderr)

    def test_historical_continuation_full_read_requires_confirmation(self):
        old = self.vault / "06 Archive/old.md"
        old.parent.mkdir()
        old.write_text("Historical text.\n")
        self.log.write_text(self.log.read_text().replace("### Pickup Context", f"- `{old}` - continuation\n\n### Pickup Context"))
        self.assertEqual(self.run_review("classify", "--vault", str(self.vault), "--path", str(self.log),
            "--semantic", "--targeted", "--inspection-target", "Session 1").returncode, 0)
        self.assertEqual(self.run_review("classify", "--vault", str(self.vault), "--path", str(old),
            "--semantic", "--reason", "continuation link").returncode, 0)
        result = self.run_review("build", "--vault", str(self.vault), "--session-log", str(self.log), "--number", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit coverage confirmation", result.stderr)
        self.assertEqual(self.run_review("classify", "--vault", str(self.vault), "--path", str(old),
            "--semantic", "--reason", "continuation link", "--confirm-full-read").returncode, 0)
        self.build()

    def test_final_enumeration_cannot_use_an_earlier_incomplete_search_set(self):
        generation = json.loads((self.root / "run.json").read_text())["generation"]
        (self.root / "captures/enum.json").write_text(json.dumps({
            "kind": "enumeration", "run_generation": generation, "captured_at": "9",
            "label": "final", "text": "final alpha and beta", "structured": {
                "needles": [{"needle": "alpha", "match_mode": "fixed"},
                            {"needle": "beta", "match_mode": "word"}]}}))
        result = self.run_review("build", "--vault", str(self.vault), "--session-log", str(self.log),
                                 "--number", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Propagation coverage", result.stderr)

    def test_structured_searches_match_values_modes_and_raw_byte_receipts(self):
        stdout = self.base / "stdout.bin"
        stderr = self.base / "stderr.bin"
        payload = b"notes/a - b.md\0" + b"1:" + b"A" * (2 * 1024 * 1024) + b"\r\nnotes/last.md\0" + b"2:tail\r"
        stdout.write_bytes(payload)
        stderr.write_bytes(b"")
        # The hit lines exist in the vault, so the receipt is fresh at build.
        (self.vault / "notes").mkdir()
        (self.vault / "notes/a - b.md").write_bytes(b"A" * (2 * 1024 * 1024) + b"\r\n")
        (self.vault / "notes/last.md").write_bytes(b"head\ntail\r")
        enum = {"needles": [{"needle": "alpha", "match_mode": "word"}]}
        captured = self.run_review("capture", "--kind", "enumeration", "--label", "final",
                                   stdin=json.dumps(enum))
        self.assertEqual(captured.returncode, 0, captured.stderr)
        row = {"needle": "alpha", "match_mode": "word", "exit_code": 0,
               "command": "rg -n -F -w -- alpha .", "cwd": str(self.vault),
               "stdout_file": str(stdout), "stderr_file": str(stderr)}
        captured = self.run_review("capture", "--kind", "propagation", "--label", "search",
                                   stdin=json.dumps({"report": "Checked full hit set.", "searches": [row]}))
        self.assertEqual(captured.returncode, 0, captured.stderr)
        receipt = json.loads(Path(captured.stdout.strip().split("Receipt: ", 1)[1]).read_text())
        search = receipt["structured"]["searches"][0]
        self.assertEqual(search["exit_status"], 0)
        self.assertEqual(Path(search["stdout"]["path"]).read_bytes(), payload)
        self.assertEqual(search["stdout"]["lf_records"], 2)
        self.assertEqual({item["path"]: item["records"] for item in search["stdout"]["per_file_counts"]},
                         {"notes/a - b.md": 1, "notes/last.md": 1})
        self.assertNotIn("A" * 1000, receipt["text"])
        self.build()
        manifest = json.loads((self.root / "review-brief-manifest.json").read_text())
        self.assertEqual(manifest["propagation_coverage"]["missing"], [])
        Path(search["stdout"]["path"]).write_bytes(b"truncated")
        result = self.run_review("build", "--vault", str(self.vault), "--session-log", str(self.log), "--number", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing or corrupt", result.stderr)

    def capture_task_search(self, stdout_bytes: bytes) -> None:
        stdout, stderr = self.base / "task.stdout", self.base / "task.stderr"
        stdout.write_bytes(stdout_bytes)
        stderr.write_bytes(b"")
        self.assertEqual(self.run_review("capture", "--kind", "enumeration", "--label", "final",
            stdin=json.dumps({"needles": [{"needle": "task X", "match_mode": "fixed"}]})).returncode, 0)
        row = {"needle": "task X", "match_mode": "fixed", "exit_status": 0,
               "command": "rg --hidden --no-ignore -n -F -- 'task X' .", "cwd": str(self.vault),
               "stdout_file": str(stdout), "stderr_file": str(stderr)}
        captured = self.run_review("capture", "--kind", "propagation", "--label", "final search",
                                   stdin=json.dumps({"searches": [row]}))
        self.assertEqual(captured.returncode, 0, captured.stderr)

    def test_stale_propagation_hit_line_blocks_build(self):
        doc = self.vault / "doc.md"
        doc.write_text("# Doc\n\n- [ ] task X\n", encoding="utf-8")
        self.capture_task_search(b"./doc.md:3:- [ ] task X\n")
        self.build()
        # An unrelated edit that only shifts the hit line keeps the receipt fresh.
        doc.write_text("# Doc\n\nIntro.\n\n- [ ] task X\n", encoding="utf-8")
        self.build()
        doc.write_text("# Doc\n\nIntro.\n\n- [x] task X → [[log]]\n", encoding="utf-8")
        result = self.run_review("build", "--vault", str(self.vault), "--session-log", str(self.log),
                                 "--number", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale propagation receipt: 'task X' ./doc.md:3", result.stderr)
        self.assertIn("rerun this needle", result.stderr)

    def test_stale_propagation_hit_in_missing_file_blocks_build(self):
        self.capture_task_search(b"./gone.md\x003:- [ ] task X\n")
        result = self.run_review("build", "--vault", str(self.vault), "--session-log", str(self.log),
                                 "--number", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale propagation receipt: 'task X' ./gone.md:3", result.stderr)

    def test_raw_capture_preserves_non_utf8_and_carriage_returns(self):
        source = self.base / "output.bin"
        source.write_bytes(b"a\0" + b"1:\xff\r\nlast\0" + b"2:tail\r")
        result = self.run_review("capture", "--kind", "evidence", "--label", "raw",
                                 "--source", "fixture", "--provenance", "primary", "--raw-file", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(Path(result.stdout.strip().split("Receipt: ", 1)[1]).read_text())
        self.assertEqual(Path(receipt["raw"]["path"]).read_bytes(), source.read_bytes())
        self.assertEqual(receipt["raw"]["lf_records"], 2)

    def test_structured_search_rejects_declared_word_mode_without_word_flag(self):
        out = self.base / "out"
        out.write_bytes(b"")
        row = {"needle": "alpha", "match_mode": "word", "exit_status": 1,
               "command": "rg -n -F -- alpha .", "cwd": str(self.vault),
               "stdout_file": str(out), "stderr_file": str(out)}
        result = self.run_review("capture", "--kind", "propagation", "--label", "bad mode",
                                 stdin=json.dumps({"searches": [row]}))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("match_mode", result.stderr)
        row["command"] = "rg -n -F -w -- beta alpha"
        result = self.run_review("capture", "--kind", "propagation", "--label", "wrong needle",
                                 stdin=json.dumps({"searches": [row]}))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("declared pattern", result.stderr)

    def test_structured_failed_search_is_retained_but_blocks_build(self):
        out = self.base / "out"
        out.write_bytes(b"")
        self.assertEqual(self.run_review("capture", "--kind", "enumeration", "--label", "final",
            stdin=json.dumps({"needles": [{"needle": "alpha", "match_mode": "fixed"}]})).returncode, 0)
        row = {"needle": "alpha", "match_mode": "fixed", "exit_status": 2,
               "command": "rg -n -F -- alpha .", "cwd": str(self.vault),
               "stdout_file": str(out), "stderr_file": str(out)}
        self.assertEqual(self.run_review("capture", "--kind", "propagation", "--label", "failed",
            stdin=json.dumps({"searches": [row]})).returncode, 0)
        result = self.run_review("build", "--vault", str(self.vault), "--session-log", str(self.log), "--number", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"failed": [["alpha", "fixed"]]', result.stderr)

    @unittest.skipUnless(sys.platform == "linux", "uses Linux address-space limits")
    def test_large_reference_classification_and_build_are_bounded_memory(self):
        source = self.vault / "large.gguf"
        with source.open("wb") as handle:
            handle.write(b"GGUF\x00\xff")
            handle.truncate(256 * 1024 * 1024)
        text = self.log.read_text().replace("### Pickup Context", f"- `{source}` - binary reference\n\n### Pickup Context")
        self.log.write_text(text)
        classified = self.run_review("classify", "--vault", str(self.vault), "--path", str(self.log),
                                    "--semantic", "--targeted", "--inspection-target", "Session 1")
        self.assertEqual(classified.returncode, 0, classified.stderr)
        runner = ("import resource,runpy,sys; resource.setrlimit(resource.RLIMIT_AS,"
                  "(128*1024*1024,128*1024*1024)); sys.argv=sys.argv[1:]; "
                  "runpy.run_path(sys.argv[0],run_name='__main__')")
        for args in (["classify", "--vault", str(self.vault), "--path", str(source), "--reference"],
                     ["build", "--vault", str(self.vault), "--session-log", str(self.log), "--number", "1"],
                     ["capture", "--kind", "evidence", "--label", "large raw output", "--source", "fixture",
                      "--provenance", "primary", "--raw-file", str(source)]):
            result = subprocess.run([sys.executable, "-c", runner, str(HELPER), *args],
                                    env=self.env, text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
