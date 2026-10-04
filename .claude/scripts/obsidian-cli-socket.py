#!/usr/bin/env python3
"""Send CLI commands to a running Obsidian app without starting Electron.

The established Unix command socket uses newline-delimited JSON with argv,
TTY=false and cwd. This sender supports AF_UNIX systems; it does not grant
socket permissions or start the app for CLI commands. The socket lives under
XDG_RUNTIME_DIR (home-directory fallback matches the existing client).

No arguments or an obsidian:// URI delegates to OBSIDIAN_DESKTOP, an executable
launcher path, or obsidian-desktop on PATH. The launcher owns desktop flags.
OBSIDIAN_CLI_SOCKET_TIMEOUT_SECONDS bounds a complete call (default/max 30s).
Raw response bytes are preserved. Empty/whitespace replies exit EX_TEMPFAIL (75)
so read-only probes can retry them; command/connection errors exit 1. Mutating
commands must still use the vault's locking wrapper and postchecks.
"""
import json
import math
import os
from pathlib import Path
import shutil
import socket
import sys
import time

EMPTY_RESPONSE = "Obsidian returned an empty response; command success is unverified."


def main(args):
    if not args or args[0].startswith("obsidian://"):
        desktop = os.environ.get("OBSIDIAN_DESKTOP") or shutil.which("obsidian-desktop")
        if not desktop:
            print("Obsidian desktop launcher is unavailable; configure OBSIDIAN_DESKTOP or obsidian-desktop on PATH.", file=sys.stderr)
            return 1
        try:
            os.execv(desktop, [desktop, *args])
        except OSError as error:
            print(f"Obsidian desktop launcher failed: {error}", file=sys.stderr)
            return 1

    if not hasattr(socket, "AF_UNIX"):
        print("Obsidian command-socket sender requires AF_UNIX; this platform is unsupported.", file=sys.stderr)
        return 1
    if args == ["--help"]:
        args = ["help"]
    try:
        timeout = float(os.environ.get("OBSIDIAN_CLI_SOCKET_TIMEOUT_SECONDS", "30"))
        if not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError
    except ValueError:
        print("OBSIDIAN_CLI_SOCKET_TIMEOUT_SECONDS must be greater than 0 and at most 30.", file=sys.stderr)
        return 1
    path = str(Path(os.environ.get("XDG_RUNTIME_DIR") or str(Path.home())) / ".obsidian-cli.sock")
    try:
        deadline = time.monotonic() + timeout
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(path)
            request = {"argv": args, "tty": False, "cwd": os.getcwd()}
            connection.settimeout(max(0.001, deadline - time.monotonic()))
            connection.sendall((json.dumps(request) + "\n").encode())
            chunks = []
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("command response timed out")
                connection.settimeout(remaining)
                chunk = connection.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
    except OSError as error:
        print(f"Obsidian CLI connection failed ({path}): {error}. Open Obsidian on the desktop and retry.", file=sys.stderr)
        return 1
    output = b"".join(chunks)
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    if not output.strip():
        print(EMPTY_RESPONSE, file=sys.stderr)
        return 75
    if any(line.lstrip().startswith((b"Error:", b"Command line interface is not enabled")) for line in output.splitlines()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
