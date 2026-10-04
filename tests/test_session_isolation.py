#!/usr/bin/env python3
"""The fixture-isolation helper must keep test writes out of the live ledger."""

from __future__ import annotations

import os
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

try:
    from session_isolation import HARNESS_SESSION_VARS, isolate_session, isolated_os_environ
except ImportError:  # `python -m unittest tests.<module>` from the repo root
    from tests.session_isolation import (
        HARNESS_SESSION_VARS,
        isolate_session,
        isolated_os_environ,
    )


LOCKED_EDIT = Path(__file__).parents[1] / ".claude/scripts/locked-edit.sh"


class SessionIsolationTests(unittest.TestCase):
    def test_every_harness_session_variable_is_replaced(self) -> None:
        environment = {name: "inherited" for name in HARNESS_SESSION_VARS}
        environment["CLAUDE_CONFIG_DIR"] = "/real/config"
        isolate_session(environment, "/tmp/fixture-state", "fixture-id")
        self.assertEqual(environment["OPENCAIRN_SESSION_ID"], "fixture-id")
        self.assertEqual(environment["CLAUDE_CONFIG_DIR"], "/tmp/fixture-state")
        self.assertEqual(environment["CODEX_HOME"], "/tmp/fixture-state/codex")
        for name in HARNESS_SESSION_VARS:
            if name != "OPENCAIRN_SESSION_ID":
                self.assertNotIn(name, environment)

    def test_os_environ_isolation_restores_the_inherited_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = {"CLAUDE_CODE_SESSION_ID": "live-session"}
            original = os.environ.get("CLAUDE_CODE_SESSION_ID")
            os.environ.update(marker)
            try:
                with isolated_os_environ(tmp, "fixture-id"):
                    self.assertNotIn("CLAUDE_CODE_SESSION_ID", os.environ)
                    self.assertEqual(os.environ["OPENCAIRN_SESSION_ID"], "fixture-id")
                self.assertEqual(os.environ["CLAUDE_CODE_SESSION_ID"], "live-session")
            finally:
                if original is None:
                    os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
                else:
                    os.environ["CLAUDE_CODE_SESSION_ID"] = original

    def test_locked_edit_ledgers_under_the_fixture_session_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "note.md"
            target.write_text("before\n", encoding="utf-8")
            inherited = root / "inherited-config"
            fixture = root / "fixture-config"
            environment = isolate_session(
                dict(
                    os.environ,
                    CLAUDE_CONFIG_DIR=str(inherited),
                    CLAUDE_CODE_SESSION_ID="live-session",
                ),
                fixture,
                "fixture-id",
            )
            subprocess.run(
                [str(LOCKED_EDIT), str(target), "--replace"],
                input="before\n========OPENCAIRN-LOCKED-EDIT-SEP========\nafter\n",
                text=True,
                check=True,
                capture_output=True,
                env=environment,
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "after\n")
            self.assertFalse(inherited.exists(), "wrote into the inherited state root")
            rows = (fixture / ".session-state/fixture-id.tsv").read_text(encoding="utf-8")
            self.assertIn(str(target), rows)

    def test_unisolated_writer_control_and_isolated_writer_use_distinct_roots(self):
        # The outer inherited environment is a sandbox, never the real home.
        with tempfile.TemporaryDirectory(prefix='inherited-sentinel-') as outer, \
             tempfile.TemporaryDirectory(prefix='writer-fixture-') as inner:
            fixture = Path(inner)
            inherited = Path(outer) / 'config'
            target = fixture / 'note.md'
            target.write_text('before\n')
            environment = dict(os.environ, HOME=str(Path(outer) / 'home'),
                CLAUDE_CONFIG_DIR=str(inherited), CODEX_HOME=str(Path(outer) / 'codex'),
                OPENCAIRN_SESSION_ID='inherited-session',
                CLAUDE_CODE_SESSION_ID='inherited-claude', CODEX_THREAD_ID='inherited-codex',
                VAULT_PATH=str(fixture))
            subprocess.run([str(LOCKED_EDIT), str(target), '--append'], input='control\n',
                env=environment, text=True, capture_output=True, check=True)
            ledger = inherited / '.session-state/inherited-session.tsv'
            self.assertIn('\tlocked-edit\t' + str(target), ledger.read_text())
            inherited_files = {p: p.read_bytes() for p in inherited.rglob('*') if p.is_file()}
            isolated = isolate_session(environment.copy(), fixture / 'config', 'fixture-session')
            subprocess.run([str(LOCKED_EDIT), str(target), '--append'], input='isolated\n',
                env=isolated, text=True, capture_output=True, check=True)
            self.assertEqual(target.read_text(), 'before\ncontrol\nisolated\n')
            rows = (fixture / 'config/.session-state/fixture-session.tsv').read_text()
            self.assertIn('\tlocked-edit\t' + str(target), rows)
            self.assertEqual({p: p.read_bytes() for p in inherited.rglob('*') if p.is_file()}, inherited_files)
            self.assertTrue(Path(isolated['CODEX_HOME']).is_relative_to(fixture))

    def test_mocked_obsidian_move_receipt_is_isolated_from_inherited_state(self):
        try:
            from test_locked_edit_move import MOCK_OBSIDIAN
        except ImportError:
            from tests.test_locked_edit_move import MOCK_OBSIDIAN
        with tempfile.TemporaryDirectory(prefix='move-inherited-') as outer, \
             tempfile.TemporaryDirectory(prefix='move-fixture-') as inner:
            fixture = Path(inner)
            vault = fixture / 'vault'
            (vault / 'Old').mkdir(parents=True)
            (vault / 'New').mkdir()
            obsidian = fixture / 'obsidian'
            obsidian.write_text(textwrap.dedent(MOCK_OBSIDIAN))
            obsidian.chmod(0o755)
            inherited = Path(outer) / 'config'
            env = dict(os.environ, HOME=str(Path(outer) / 'home'),
                CLAUDE_CONFIG_DIR=str(inherited), CODEX_HOME=str(Path(outer) / 'codex'),
                OPENCAIRN_SESSION_ID='inherited-session',
                CLAUDE_CODE_SESSION_ID='inherited-claude', CODEX_THREAD_ID='inherited-codex',
                VAULT_PATH=str(vault), OBSIDIAN_CLI=str(obsidian),
                LOCKED_EDIT_MOVE_TIMEOUT_SECONDS='1', LOCKED_EDIT_OBSIDIAN_CALL_TIMEOUT_SECONDS='1')
            saved_inherited = None
            for name, environment, state, sid in [
                ('control', env, inherited, 'inherited-session'),
                ('isolated', isolate_session(env.copy(), fixture / 'config', 'fixture-session'),
                 fixture / 'config', 'fixture-session')]:
                source = vault / f'Old/{name}.md'
                destination = vault / f'New/{name}.md'
                reference = vault / f'{name}-reference.md'
                source.write_text('Source bytes\n')
                reference.write_text(f'[[Old/{name}]]\n')
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                subprocess.run([str(LOCKED_EDIT), str(source), '--move', str(destination), digest],
                    env=environment, text=True, capture_output=True, check=True)
                receipts = list((state / f'.session-state/{sid}.project-move-receipts').glob('*.json'))
                self.assertEqual(len(receipts), 1)
                payload = json.loads(receipts[0].read_text())
                self.assertIs(payload['complete'], True)
                self.assertEqual(payload['source'], str(source))
                self.assertEqual(payload['destination'], str(destination))
                self.assertEqual(payload['content_sha256'], digest)
                self.assertEqual(destination.read_text(), 'Source bytes\n')
                self.assertFalse(source.exists())
                self.assertEqual(reference.read_text(), f'[[New/{name}]]\n')
                ledger = (state / f'.session-state/{sid}.tsv').read_text()
                self.assertIn(str(destination), ledger)
                self.assertIn(str(reference), ledger)
                current = {p: p.read_bytes() for p in inherited.rglob('*') if p.is_file()}
                if saved_inherited is None:
                    saved_inherited = current  # Positive control wrote only to the sandbox sentinel.
                else:
                    self.assertEqual(current, saved_inherited)
                    self.assertTrue(receipts[0].is_relative_to(fixture))


if __name__ == "__main__":
    unittest.main()
