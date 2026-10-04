"""Isolated AF_UNIX controls for the running-app command sender.

Set OBSIDIAN_LEGACY_CLIENT to an existing direct client to run its compatibility
control too. The optional control never launches the desktop or uses its socket.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session

ROOT = Path(__file__).parents[1]
CLIENT = ROOT / ".claude/scripts/obsidian-cli-socket.py"
LOCKED_EDIT = ROOT / ".claude/scripts/locked-edit.sh"
HELP = b"move file=<name> path=<path> to=<path>\n"
LEGACY_EMPTY = "Obsidian returned an empty response; command success is unverified."


class SocketEndpoint:
    """A fixture socket; captures actual newline-framed requests and raw replies."""
    def __init__(self, runtime, replies):
        self.runtime = Path(runtime)
        self.runtime.mkdir(exist_ok=True)
        self.replies = replies
        self.requests = []
        self.responses = []
        self.errors = []
        self.stop = threading.Event()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.runtime / ".obsidian-cli.sock"))
        self.socket.listen()
        self.socket.settimeout(0.1)
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def serve(self):
        while not self.stop.is_set():
            try:
                connection, _ = self.socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                with connection:
                    connection.settimeout(2)
                    raw = b""
                    while not raw.endswith(b"\n"):
                        chunk = connection.recv(65536)
                        if not chunk:
                            break
                        raw += chunk
                    request = json.loads(raw)
                    self.requests.append(raw)
                    index = len(self.requests) - 1
                    reply = self.replies(request, index) if callable(self.replies) else self.replies[min(index, len(self.replies) - 1)]
                    if isinstance(reply, tuple):
                        delay, reply = reply
                        self.stop.wait(delay)
                    self.responses.append(reply)
                    try:
                        connection.sendall(reply)
                    except BrokenPipeError:
                        pass  # The bounded client/probe deliberately timed out.
            except Exception as error:
                self.errors.append(repr(error))

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join(timeout=3)
        self.socket.close()
        if self.thread.is_alive() or self.errors:
            raise AssertionError((self.thread.is_alive(), self.errors))


def probe_command(client):
    """Execute the actual helper, rather than a second copy of its algorithm."""
    source = LOCKED_EDIT.read_text()
    helper = source.split("    _obsidian_read_nonempty() {", 1)[1].split("\n    }", 1)[0]
    shell = "PYTHON_BIN=" + sys.executable + "\nOBSIDIAN_CALL_TIMEOUT_SECONDS=1\n_obsidian_read_nonempty() {" + helper + "\n}\n_obsidian_read_nonempty \"$1\" help move\n"
    return ["bash", "-c", shell, "socket-probe", str(client)]


@unittest.skipUnless(hasattr(socket, "AF_UNIX"), "requires AF_UNIX")
class SocketClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.path.realpath("/tmp"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir()
        self.env = isolate_session(os.environ.copy(), self.root / "state", "socket-client-test")
        self.env.update(XDG_RUNTIME_DIR=str(self.runtime), OBSIDIAN_CLI_SOCKET_TIMEOUT_SECONDS="1")
        self.env.pop("OBSIDIAN_DESKTOP", None)

    def run_client(self, *args, client=CLIENT):
        return subprocess.run([sys.executable, str(client), *args], cwd=self.root,
                              env=self.env, capture_output=True, timeout=5)

    def run_probe(self, client=CLIENT):
        return subprocess.run(probe_command(client), cwd=self.root, env=self.env,
                              capture_output=True, timeout=9)

    def assert_request(self, server, argv, count=1):
        self.assertEqual(len(server.requests), count)
        for raw in server.requests:
            self.assertTrue(raw.endswith(b"\n"))
            self.assertEqual(json.loads(raw), {"argv": argv, "cwd": str(self.root), "tty": False})

    def test_raw_response_and_help_alias(self):
        reply = "réponse\n".encode() + b"\xff\x00"
        with SocketEndpoint(self.runtime, [reply]) as server:
            result = self.run_client("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, reply)
        self.assert_request(server, ["help"])

    def test_command_arguments_are_preserved(self):
        with SocketEndpoint(self.runtime, [b"/fixture/vault\n"]) as server:
            result = self.run_client("vault", "info=path", "vault=Fixture name")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_request(server, ["vault", "info=path", "vault=Fixture name"])

    def test_empty_and_whitespace_have_explicit_transient_status(self):
        for reply in (b"", b" \t\n"):
            with self.subTest(reply=reply):
                with SocketEndpoint(self.runtime, [reply]) as server:
                    result = self.run_client("help", "move")
                self.assertEqual(result.returncode, 75, result.stderr)
                self.assertEqual(result.stdout, reply)
                self.assertIn(LEGACY_EMPTY.encode(), result.stderr)
                self.assert_request(server, ["help", "move"])
                (self.runtime / ".obsidian-cli.sock").unlink()

    def test_reported_error_is_not_success(self):
        for reply in (b"Error: missing file\n", b"ok\n  Error: failed\n", b"Command line interface is not enabled\n"):
            with self.subTest(reply=reply):
                with SocketEndpoint(self.runtime, [reply]) as server:
                    result = self.run_client("help", "move")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, reply)
                self.assert_request(server, ["help", "move"])
                (self.runtime / ".obsidian-cli.sock").unlink()

    def test_missing_socket_is_connection_failure(self):
        result = self.run_client("help", "move")
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"connection failed", result.stderr)
        self.assertNotIn(LEGACY_EMPTY.encode(), result.stderr)

    def test_socket_timeout_is_bounded_connection_failure(self):
        with SocketEndpoint(self.runtime, [(2, HELP)]) as server:
            start = time.monotonic()
            result = self.run_client("help", "move")
            elapsed = time.monotonic() - start
        self.assertEqual(result.returncode, 1)
        self.assertLess(elapsed, 1.8)
        self.assertIn(b"connection failed", result.stderr)
        self.assert_request(server, ["help", "move"])

    def test_canonical_probe_retries_blank_then_supported(self):
        with SocketEndpoint(self.runtime, [b"", HELP]) as server:
            result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, HELP.rstrip(b"\n"))
        self.assert_request(server, ["help", "move"], 2)

    @unittest.skipUnless(os.environ.get("OBSIDIAN_LEGACY_CLIENT"), "optional actual legacy client control")
    def test_legacy_actual_client_probe_retries_blank_then_supported(self):
        client = Path(os.environ["OBSIDIAN_LEGACY_CLIENT"])
        with SocketEndpoint(self.runtime, [b"", HELP]) as server:
            result = self.run_probe(client)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, HELP.rstrip(b"\n"))
        self.assert_request(server, ["help", "move"], 2)

    def test_probe_error_stops_after_first_request(self):
        with SocketEndpoint(self.runtime, [b"Error: path=<path> to=<path>\n", HELP]) as server:
            result = self.run_probe()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assert_request(server, ["help", "move"])

    def test_probe_empty_exhaustion_is_bounded(self):
        with SocketEndpoint(self.runtime, [b" \t\n"]) as server:
            start = time.monotonic()
            result = self.run_probe()
            elapsed = time.monotonic() - start
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertGreaterEqual(elapsed, 2)
        self.assertLess(elapsed, 5)
        self.assert_request(server, ["help", "move"], 3)

    def test_probe_timeout_then_supported_retries(self):
        self.env["OBSIDIAN_CLI_SOCKET_TIMEOUT_SECONDS"] = "30"
        with SocketEndpoint(self.runtime, [(1.3, HELP), HELP]) as server:
            result = self.run_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_request(server, ["help", "move"], 2)

    def test_probe_does_not_retry_unrelated_nonzero_or_error(self):
        # A stub is necessary for statuses the real wire protocol does not carry.
        stub = self.root / "command"
        count = self.root / "calls"
        for stdout, stderr, status in ((b"", b"permission denied", 1),
                                      (b"", b"connection failed", 1),
                                      (HELP, b"", 1),
                                      (HELP, b"", 75),
                                      (b"", LEGACY_EMPTY.encode() + b"\npermission denied", 1),
                                      (HELP, b"Error: refused", 0),
                                      (b"Error: path=<path> to=<path>", b"", 0)):
            with self.subTest(stdout=stdout, stderr=stderr, status=status):
                count.write_text("")
                stub.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\nimport sys\n"
                                + "with Path(" + repr(str(count)) + ").open('a') as f: f.write('call\\n')\n"
                                + "sys.stdout.buffer.write(" + repr(stdout) + ")\n"
                                + "sys.stderr.buffer.write(" + repr(stderr) + ")\n"
                                + "sys.exit(" + str(status) + ")\n")
                stub.chmod(0o755)
                result = self.run_probe(stub)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(count.read_text(), "call\n")

    def test_launcher_delegates_noargs_and_uri_without_extra_flags(self):
        launcher = self.root / "desktop"
        launcher.write_text("#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
        launcher.chmod(0o755)
        self.env["OBSIDIAN_DESKTOP"] = str(launcher)
        for args in ((), ("obsidian://open?vault=Fixture", "second argument")):
            with self.subTest(args=args):
                result = self.run_client(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), list(args))
        with SocketEndpoint(self.runtime, [HELP]) as server:
            result = self.run_client("help", "move")
        self.assertEqual(result.stdout, HELP)
        self.assert_request(server, ["help", "move"])

    def test_missing_configured_launcher_fails_honestly(self):
        self.env["OBSIDIAN_DESKTOP"] = str(self.root / "absent-desktop")
        result = self.run_client()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"desktop launcher", result.stderr)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
