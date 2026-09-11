#!/usr/bin/env python3
"""Bind fixture subprocesses to their own session state.

Scripts under test resolve the harness session id from the environment
(`lib-session.sh`'s `OPENCAIRN_SESSION_ID` → `CLAUDE_CODE_SESSION_ID` →
`CODEX_THREAD_ID` order, mirrored by `park-review.py`) and self-ledger every
write under `$CLAUDE_CONFIG_DIR/.session-state/<id>.tsv`. Run inside a live
session, a fixture that inherits that id writes its `/tmp` paths into the real
park ledger, where the next `/park` reads them back as attributed files.

Import defensively — this module is reached by three different invocations:

    try:
        from session_isolation import isolate_session
    except ImportError:  # `python -m unittest tests.<module>` from the repo root
        from tests.session_isolation import isolate_session
"""

from __future__ import annotations

import os
from pathlib import Path


HARNESS_SESSION_VARS = (
    "OPENCAIRN_SESSION_ID",
    "CLAUDE_CODE_SESSION_ID",
    "CODEX_THREAD_ID",
)


def isolate_session(
    environment: dict, state_root: Path | str, session_id: str
) -> dict:
    """Point `environment` at a fixture-owned session id and state root.

    Mutates and returns `environment`, so it works on both a copy and
    `os.environ` itself (for subprocesses launched without an explicit `env=`).
    Every harness session variable is cleared first: setting the
    highest-priority one would be enough for today's resolution order, but a
    leftover lower-priority id is a live inheritance path for any script that
    reads them directly.
    """
    for name in HARNESS_SESSION_VARS:
        environment.pop(name, None)
    environment["CLAUDE_CONFIG_DIR"] = str(state_root)
    environment["OPENCAIRN_SESSION_ID"] = session_id
    return environment


def isolated_os_environ(state_root: Path | str, session_id: str):
    """Context manager isolating `os.environ` for inherited-env subprocesses."""
    from unittest import mock

    patch = mock.patch.dict(os.environ, {}, clear=False)

    class _Ctx:
        def __enter__(self):
            patch.start()
            isolate_session(os.environ, state_root, session_id)
            return os.environ

        def __exit__(self, *exc):
            patch.stop()
            return False

    return _Ctx()
