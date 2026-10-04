"""Synthetic read/producer regressions; never invoke hooks or use live state."""
from pathlib import Path
import os
import hashlib
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / ".claude/scripts/session-ledger.sh"

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session


class LedgerDedupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ledger-dedup-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.config = self.root / "config"
        state = self.config / ".session-state"
        state.mkdir(parents=True)
        self.ledger = state / "synthetic-ledger-dedup.tsv"
        # Read mode must work with no jq available, not merely with jq unused.
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name in ("dirname", "head", "cut", "awk", "find", "grep",
                     "basename", "sort", "sed", "date"):
            executable = shutil.which(name)
            self.assertIsNotNone(executable, name)
            (bin_dir / name).symlink_to(executable)
        self.bash = shutil.which("bash")
        self.assertIsNotNone(self.bash)
        self.env = {
            "PATH": str(bin_dir),
            "HOME": str(self.root),
            "CLAUDE_CONFIG_DIR": str(self.config),
            "OPENCAIRN_SESSION_ID": "synthetic-ledger-dedup",
            "CLAUDE_CODE_SESSION_ID": "synthetic-claude",
            "CODEX_THREAD_ID": "synthetic-codex",
            "LC_ALL": "C",
            "TZ": "UTC",
        }
        self.assertIsNone(shutil.which("jq", path=self.env["PATH"]))

    def read_rows(self, rows, *args):
        # Rows are (timestamp, tool, relative fixture path, optional agent).
        lines = []
        for timestamp, tool, name, agent in rows:
            fields = [timestamp, tool, str(self.vault / name)]
            if agent is not None:
                fields.append(agent)
            lines.append("\t".join(fields) + "\n")
        self.ledger.write_text("".join(lines))
        result = subprocess.run(
            [self.bash, str(SCRIPT), "--read", *args],
            env=self.env, cwd=self.vault, text=True, capture_output=True,
            timeout=10, check=True,
        )
        self.assertEqual(result.stderr, "")
        return result.stdout

    def agents(self, values):
        output = self.read_rows([
            ("2026-01-01T12:00:00Z", "Write", "note.md", agent)
            for agent in values
        ])
        data = [line for line in output.splitlines() if not line.startswith("#")]
        self.assertEqual(data[-1], f"TOTAL\t1 file(s)\t{len(values)} write(s)")
        return data[0].split("\t")[-1]

    def test_short_identifier_after_long_identifier(self):
        self.assertEqual(self.agents(["agent-10", "agent-1", "agent-10", "agent-1"]),
                         "agent-10,agent-1")

    def test_positive_control_exact_duplicates_and_reverse_order(self):
        self.assertEqual(self.agents(["agent-1", "agent-10", "agent-1", "agent-10"]),
                         "agent-1,agent-10")
        self.assertEqual(self.agents(["main", "main"]), "main")

    def test_identifiers_are_literal_not_delimited_or_regex_matched(self):
        self.assertEqual(self.agents(["x,y", "x", "y", ".*", ".", "x,y", ".*"]),
                         "x,y,x,y,.*,.")

    def test_legacy_and_empty_agent_remain_unknown(self):
        self.assertEqual(self.agents([None, "", "?", "main", None]), "?,main")

    def test_path_local_membership_and_complete_output_order(self):
        output = self.read_rows([
            ("2026-01-01T12:01:00Z", "Write", "z.md", "agent-10"),
            ("2026-01-01T12:02:00Z", "Edit", "a.md", "agent-1"),
            ("2026-01-01T12:03:00Z", "Edit", "z.md", "agent-1"),
            ("2026-01-01T12:04:00Z", "Write", "a.md", "agent-10"),
            ("2026-01-01T12:05:00Z", "Edit", "z.md", "agent-10"),
        ])
        self.assertEqual(output, (
            "# ledger begins 2026-01-01T12:01:00Z — writes before the hook was\n"
            "# wired are NOT here; park-files.sh is the backstop for them.\n"
            "# path\twrites\tfirst..last (UTC)\tagents\n"
            f"{self.vault / 'z.md'}\t3x Write,Edit\t12:01..12:05\tagent-10,agent-1\n"
            f"{self.vault / 'a.md'}\t2x Edit,Write\t12:02..12:04\tagent-1,agent-10\n"
            "TOTAL\t2 file(s)\t5 write(s)\n"
        ))

    def test_cutoff_does_not_seed_membership(self):
        output = self.read_rows([
            ("2000-01-01T00:00:00Z", "Write", "note.md", "agent-10"),
            ("2999-01-01T12:00:00Z", "Edit", "note.md", "agent-1"),
            ("2999-01-01T12:01:00Z", "Edit", "note.md", "agent-10"),
        ], "-m", "60")
        self.assertIn("\t2x Edit\t12:00..12:01\tagent-1,agent-10\n", output)
        self.assertTrue(output.endswith("TOTAL\t1 file(s)\t2 write(s)\n"))


class SelfLedgerIdentityTests(unittest.TestCase):
    def test_move_collateral_records_actual_codex_writer_identity(self):
        try:
            from test_locked_edit_move import MOCK_OBSIDIAN
        except ImportError:
            from tests.test_locked_edit_move import MOCK_OBSIDIAN
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / 'vault'
            (vault / 'Old').mkdir(parents=True)
            (vault / 'New').mkdir()
            cli = root / 'obsidian'
            cli.write_text(MOCK_OBSIDIAN)
            cli.chmod(0o755)
            source = vault / 'Old/Example.md'
            source.write_text('source\n')
            reference = vault / 'Reference.md'
            reference.write_text('[[Old/Example]]\n')
            env = isolate_session(os.environ.copy(), root / 'config', 'parent-fixture')
            env.update(VAULT_PATH=str(vault), OBSIDIAN_CLI=str(cli),
                       CODEX_THREAD_ID='child-fixture', OPENCAIRN_AGENT_ID='',
                       LOCKED_EDIT_MOVE_TIMEOUT_SECONDS='1')
            subprocess.run([str(SCRIPT.parent / 'locked-edit.sh'), str(source), '--move',
                str(vault / 'New/Example.md'), hashlib.sha256(source.read_bytes()).hexdigest()],
                env=env, text=True, capture_output=True, check=True)
            rows = (root / 'config/.session-state/parent-fixture.tsv').read_text().splitlines()
            self.assertTrue(rows)
            self.assertTrue(all(r.split('\t')[3] == 'codex:child-fixture' for r in rows), rows)
            self.assertEqual(reference.read_text(), '[[New/Example]]\n')

    def test_actual_producers_use_explicit_or_codex_identity_without_guessing(self):
        scripts = SCRIPT.parent
        for identity, thread, expected in [
            ('worker-fixture', 'thread-fixture', 'worker-fixture'),
            ('', 'thread-fixture', 'codex:thread-fixture'),
            ('', '', '?'),
            ('worker\tpart\nlabel\rtail', '', 'worker part label tail')]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                vault = root / 'vault'
                vault.mkdir()
                env = isolate_session(os.environ.copy(), root / 'config', 'parent-fixture')
                env['VAULT_PATH'] = str(vault)
                env['OPENCAIRN_AGENT_ID'] = identity
                if thread:
                    env['CODEX_THREAD_ID'] = thread
                target = vault / 'note.md'
                subprocess.run([str(scripts / 'locked-edit.sh'), str(target), '--append'],
                    env=env, input='Fixture bytes\n', text=True, capture_output=True, check=True)
                source = root / 'source.bin'
                source.write_bytes(b'fixture')
                landed = vault / 'landed.bin'
                subprocess.run([str(scripts / 'locked-ingress.sh'), str(vault), str(source), str(landed)],
                    env=env, text=True, capture_output=True, check=True)
                rows = (root / 'config/.session-state/parent-fixture.tsv').read_text().splitlines()
                self.assertEqual(len(rows), 2)
                for row in rows:
                    self.assertEqual(len(row.split('\t')), 4)
                    self.assertEqual(row.split('\t')[3], expected)
                self.assertEqual(target.read_text(), 'Fixture bytes\n')
                self.assertEqual(landed.read_bytes(), b'fixture')


if __name__ == "__main__":
    unittest.main()
