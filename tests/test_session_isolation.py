#!/usr/bin/env python3
"""The fixture-isolation helper must keep test writes out of the live ledger."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
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


if __name__ == "__main__":
    unittest.main()
