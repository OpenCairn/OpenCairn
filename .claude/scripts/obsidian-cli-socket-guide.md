# Obsidian command-socket client

`obsidian-cli-socket.py` sends commands to the already running app through its Unix socket. It avoids Electron startup for command calls; it does not start the app, grant socket permissions, or exempt vault writes from the canonical lock wrapper. The established request framing was used with Obsidian 1.13.7; fixtures verify transport and failure handling, not every app command or platform.

Use the reviewed executable as `OBSIDIAN_CLI` for locked moves, or install it as the `obsidian` command sender after checking the existing destination and preserving its launcher. The script uses `$XDG_RUNTIME_DIR/.obsidian-cli.sock`, with the existing home-directory fallback when that variable is unset. An isolated app test needs its own runtime directory as well as its own profile: profiles alone share the socket.

No arguments or an `obsidian://` URI delegates to the executable path in `OBSIDIAN_DESKTOP`, or `obsidian-desktop` on PATH. Keep that launcher separate; its existing desktop flags belong there. CLI commands never take the desktop route. An unavailable launcher is an error, not permission to guess another install path.

```bash
"<installed-client>" version
"<installed-client>" vault info=path
```

Pass requires a nonblank version and the expected vault path at exit 0. A missing connection or an explicit command error is a failed check. Compare old/new clients on these read-only calls before replacing a working sender; preserve exact commands, statuses and output. Run structural or mutating commands only through the canonical lock wrapper and its postchecks.

Raw response bytes and command arguments are preserved. The client maps `--help` to the app's `help` command. Empty/whitespace responses exit 75 (`EX_TEMPFAIL`); command, connection and launcher failures exit 1. Existing callers must keep every nonzero response unverified. Read-only probes may retry the documented transient-empty status within their existing attempt/time limits, never a nonblank success-looking reply at nonzero status. The move wrapper also recognises the older sender's exact exit-1 empty-response diagnostic. Explicit errors on stdout or stderr fail immediately.

`OBSIDIAN_CLI_SOCKET_TIMEOUT_SECONDS` bounds the complete client call; its default and maximum are 30 seconds. The move preflight keeps its own shorter call timeout and three-attempt limit. A timeout or exhausted blank reply stops before the move.
