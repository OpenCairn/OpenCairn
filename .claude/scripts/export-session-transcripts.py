#!/usr/bin/env python3
"""Export Claude Code and Codex CLI session JSONL files to readable markdown transcripts.

Extracts user messages and assistant text/tool-input content from JSONL session
files. Skips tool results (file contents, grep output, web scrapes) which are
bulk noise. Produces one markdown file per day in the vault archive.

Sources: ~/.claude/projects/**/*.jsonl (Claude Code) and, when present,
~/.codex/sessions/**/*.jsonl (Codex CLI rollouts). Codex sessions are slugged
`codex-<id13>` and their assistant turns labelled **Codex**; in cwd-scoped mode
they are filtered to rollouts whose recorded cwd matches, mirroring the
per-project scoping of the Claude source. Codex `spawn_agent` payloads are
encrypted at rest in the rollout — only the task name is exportable.

Usage:
    export-session-transcripts.py <vault_path> [--days N] [--all-projects]

Options:
    --days N       Export sessions modified in the last N days (default: 7)
    --all-projects Export every Claude Code project and Codex rollout
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


def find_session_dir(allow_fallback=False):
    """Resolve the JSONL session directory for the current working directory.

    Returns (session_dir, encoded). session_dir is None when the cwd-encoded
    directory doesn't exist and fallback is disabled — the caller must then fail
    closed rather than export an arbitrary project's transcripts.
    """
    claude_dir = Path.home() / ".claude" / "projects"
    # The directory name is the CWD path with / replaced by -
    # e.g., /home/user -> -home-user
    cwd = os.getcwd()
    encoded = cwd.replace("/", "-")
    session_dir = claude_dir / encoded
    if session_dir.exists():
        return session_dir, encoded

    # Fallback is OFF by default: returning an arbitrary project's transcripts here
    # silently exports the WRONG project, which /goodnight then hashes as provenance.
    # Only an explicit --fallback-any-project opts into that risk.
    if allow_fallback and claude_dir.is_dir():
        for d in sorted(claude_dir.iterdir()):
            if d.is_dir() and list(d.glob("*.jsonl")):
                return d, encoded
    return None, encoded


def all_session_dirs():
    """Every project dir containing JSONL — for the cross-project backstop sweep."""
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.is_dir():
        return []
    return [d for d in sorted(claude_dir.iterdir()) if d.is_dir() and list(d.glob("*.jsonl"))]


def extract_text_from_content(content):
    """Extract readable text from a message content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(block["text"])
                elif block.get("type") == "image":
                    texts.append("[image]")
        return "\n".join(texts)
    return ""


def extract_tool_inputs(content):
    """Extract tool use inputs that contain substantive written content."""
    if not isinstance(content, list):
        return []
    inputs = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        name = block.get("name", "")
        inp = block.get("input", {})

        # Write/Edit tool inputs contain content Claude wrote
        if name == "Write":
            path = inp.get("file_path", "unknown")
            content_text = inp.get("content", "")
            if len(content_text) > 2000:
                # Truncate very long file writes to keep transcripts manageable
                content_text = content_text[:2000] + f"\n[... {len(content_text)} chars total]"
            inputs.append(f"[Write → {path}]\n{content_text}")
        elif name == "Edit":
            path = inp.get("file_path", "unknown")
            old = inp.get("old_string", "")
            new = inp.get("new_string", "")
            if len(old) > 500:
                old = old[:500] + "..."
            if len(new) > 500:
                new = new[:500] + "..."
            inputs.append(f"[Edit → {path}]\n- {old}\n+ {new}")
        elif name == "Agent":
            prompt = inp.get("prompt", "")
            desc = inp.get("description", "")
            if len(prompt) > 300:
                prompt = prompt[:300] + "..."
            inputs.append(f"[Agent: {desc}]\n{prompt}")

    return inputs


def codex_session_files():
    """Codex CLI rollout files, or [] when Codex isn't installed/used."""
    codex_dir = Path.home() / ".codex" / "sessions"
    if not codex_dir.is_dir():
        return []
    return sorted(codex_dir.rglob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime)


def codex_meta(jsonl_path):
    """(session_id, cwd) from a rollout's session_meta line, or (None, None)."""
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "session_meta":
                    p = data.get("payload", {})
                    return p.get("session_id") or p.get("id"), p.get("cwd")
                break  # session_meta is the first line; don't scan the file
    except (OSError, IOError):
        pass
    return None, None


def _codex_block_text(content):
    """Join text out of a Codex message content list (input_text/output_text/text)."""
    if isinstance(content, str):
        return content
    texts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                texts.append(block["text"])
    return "\n".join(texts)


def parse_codex_session(jsonl_path):
    """Parse a Codex rollout into (role, text, ts) tuples.

    user turns come from event_msg/user_message (the clean prompt — the
    response_item user/developer messages carry injected wrappers and
    environment context). Assistant text comes from response_item messages;
    tool calls (exec / apply_patch / collaboration.*) are rendered truncated,
    matching the Claude source's Write/Edit/Agent treatment. Tool outputs,
    reasoning, and token/world-state bookkeeping are skipped as bulk noise.
    """
    messages = []
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = data.get("timestamp", "")
                dtype = data.get("type")
                payload = data.get("payload", {}) or {}
                ptype = payload.get("type")

                if dtype == "event_msg" and ptype == "user_message":
                    text = payload.get("message")
                    if isinstance(text, str) and text.strip():
                        messages.append(("user", text.strip(), ts))
                elif dtype == "response_item" and ptype == "message":
                    if payload.get("role") != "assistant":
                        continue
                    text = _codex_block_text(payload.get("content"))
                    if text.strip():
                        messages.append(("codex", text.strip(), ts))
                elif dtype == "response_item" and ptype in ("function_call", "custom_tool_call"):
                    name = payload.get("name", "?")
                    args = payload.get("arguments") or payload.get("input") or ""
                    if not isinstance(args, str):
                        args = json.dumps(args)
                    if name == "spawn_agent":
                        # message payload is encrypted at rest — render the task name only
                        m = re.search(r'"task_name"\s*:\s*"([^"]*)"', args)
                        rendered = f"[spawn_agent: {m.group(1) if m else '?'}]"
                    else:
                        if len(args) > 2000:
                            args = args[:2000] + f"\n[... {len(args)} chars total]"
                        rendered = f"[{name}]\n{args}"
                    messages.append(("codex", rendered, ts))
    except (OSError, IOError) as e:
        print(f"Warning: Could not read {jsonl_path}: {e}", file=sys.stderr)
    return messages


def parse_session(jsonl_path):
    """Parse a JSONL session file into a list of (role, text) tuples."""
    messages = []
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")
                if msg_type not in ("user", "assistant"):
                    continue

                message = data.get("message", {})
                content = message.get("content", "")
                timestamp = data.get("timestamp", "")

                if msg_type == "user":
                    text = extract_text_from_content(content)
                    if text.strip():
                        messages.append(("user", text.strip(), timestamp))
                elif msg_type == "assistant":
                    text = extract_text_from_content(content)
                    tool_inputs = extract_tool_inputs(content)
                    combined = []
                    if text.strip():
                        combined.append(text.strip())
                    for ti in tool_inputs:
                        combined.append(ti)
                    if combined:
                        messages.append(("assistant", "\n\n".join(combined), timestamp))
    except (OSError, IOError) as e:
        print(f"Warning: Could not read {jsonl_path}: {e}", file=sys.stderr)
    return messages


def get_session_slug(jsonl_path):
    """Try to extract session slug from the first few lines."""
    try:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    slug = data.get("slug")
                    if slug:
                        return slug
                except json.JSONDecodeError:
                    continue
    except (OSError, IOError):
        pass
    return jsonl_path.stem[:8]


def format_session(messages, slug, session_start):
    """Format a parsed session into markdown."""
    if not messages:
        return ""

    lines = [f"### {slug} ({session_start})\n"]
    for role, text, ts in messages:
        time_str = ""
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f" ({dt.strftime('%H:%M')})"
            except (ValueError, AttributeError):
                pass

        label = {"user": "User", "codex": "Codex"}.get(role, "Claude")
        lines.append(f"**{label}{time_str}:**\n{text}\n")

    return "\n".join(lines)


SESSION_HDR = re.compile(r'^### (\S+) \((\d{2}:\d{2}|unknown)\)\s*\n')
SEPARATOR = "\n---\n\n"


def parse_exported_text(text):
    """Split exported transcript text into {(slug, start): body}.

    Inverse of format_session() + the day-file writer.

    Anchored on the `\\n---\\n\\n` separator the writer emits between sessions,
    NOT on header lines alone. Transcript bodies routinely quote header-shaped
    text (a session that ran `head` on a transcript embeds `### <slug> (HH:MM)`
    at column 0), and matching those splits one real session into two, inventing
    a phantom that is then carried forward forever. A chunk that does not open
    with a header is continuation text and is reattached to the session before
    it, so a body containing its own `---` survives the round trip intact.

    Keyed on (slug, start) rather than slug alone. Claude Code reuses a slug
    across a parent/child session split, so two genuinely distinct sessions can
    share one — keying on slug silently collapses them and drops a session.
    """
    out = {}
    last = None
    for chunk in text.split(SEPARATOR):
        m = SESSION_HDR.match(chunk)
        if m:
            key = (m.group(1), m.group(2))
            body = chunk[m.end():].rstrip()
            if key not in out or len(body) > len(out[key]):
                out[key] = body
                last = key
        elif last is not None:
            # Continuation: the body itself contained a separator.
            out[last] = f"{out[last]}{SEPARATOR}{chunk.rstrip()}"
    return out


def read_exported_snapshot(md_path):
    """Read one exact day-file snapshot as (parsed sessions, CAS token).

    Parsing and hashing the same byte read matters: hashing a second read could
    approve an overwrite based on stale parsed content if another exporter wrote
    between the two reads. Errors other than a missing target fail closed.
    """
    try:
        raw = md_path.read_bytes()
    except FileNotFoundError:
        return {}, "MISSING"
    text = raw.decode("utf-8", errors="replace")
    return parse_exported_text(text), hashlib.sha256(raw).hexdigest()


def render_day_file(date_str, merged):
    """Render one canonical day file from a merged session mapping."""
    content = f"# Session Transcripts — {date_str}\n\n"
    content += "Auto-exported from `~/.claude/projects/` and `~/.codex/sessions/` JSONL files.\n\n---\n\n"
    for (slug, start_time), body in sorted(merged.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        content += f"### {slug} ({start_time})\n{body}\n---\n\n"
    return content


def write_day_locked(output_file, date_str, sessions, locked_edit, attempts=5):
    """Merge and atomically replace one day file under its canonical lock.

    locked-edit's whole-file mode compares the snapshot hash while holding the
    lock. Exit 2 means a concurrent exporter won after our read, so re-read,
    re-merge, and retry instead of clobbering its sessions.
    """
    incoming_keys = {(slug, start_time) for start_time, slug, _body in sessions}

    for attempt in range(attempts):
        merged, expected = read_exported_snapshot(output_file)
        on_disk_keys = set(merged)

        for start_time, slug, body in sessions:
            key = (slug, start_time)
            if key not in merged or len(body) > len(merged[key]):
                merged[key] = body

        content = render_day_file(date_str, merged).encode("utf-8")
        result = subprocess.run(
            ["bash", str(locked_edit), str(output_file), "--replace-whole", expected],
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return len(on_disk_keys - incoming_keys)
        if result.returncode == 2 and attempt + 1 < attempts:
            continue

        detail = result.stderr.decode("utf-8", errors="replace").strip()
        if not detail:
            detail = f"locked-edit.sh exited {result.returncode}"
        raise RuntimeError(f"could not install {output_file}: {detail}")

    raise RuntimeError(f"could not install {output_file}: concurrent updates did not settle")


def main():
    if len(sys.argv) < 2:
        print("Usage: export-session-transcripts.py <vault_path> [--days N] [--all-projects] [--fallback-any-project]", file=sys.stderr)
        sys.exit(1)

    vault_path = Path(sys.argv[1])
    locked_edit = Path(__file__).with_name("locked-edit.sh")
    migration_helper = Path(__file__).with_name("archive-namespace-migration.py")
    if not locked_edit.is_file():
        print(f"Error: locking wrapper not found beside exporter: {locked_edit}", file=sys.stderr)
        sys.exit(1)
    if not migration_helper.is_file():
        print(f"Error: archive helper not found beside exporter: {migration_helper}", file=sys.stderr)
        sys.exit(1)
    archive = subprocess.run(
        [sys.executable, str(migration_helper), "archive-root", "--write", str(vault_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    archive_root = archive.stdout.strip()
    if archive.returncode != 0 or archive_root not in {
        "06 Archive/Claude",
        "06 Archive/OpenCairn",
    }:
        detail = archive.stderr.strip() or "archive helper returned an invalid root"
        print(f"Error: {detail}", file=sys.stderr)
        sys.exit(1)
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    all_projects = "--all-projects" in sys.argv
    allow_fallback = "--fallback-any-project" in sys.argv
    codex_files = codex_session_files()

    if all_projects:
        scan_dirs = all_session_dirs()
        if not scan_dirs and not codex_files:
            print("Error: no session JSONL under ~/.claude/projects/ or ~/.codex/sessions/", file=sys.stderr)
            sys.exit(1)
        print(
            f"Session sources: {len(scan_dirs)} Claude project(s), "
            f"{len(codex_files)} Codex rollout(s) (--all-projects sweep)"
        )
    else:
        session_dir, encoded = find_session_dir(allow_fallback=allow_fallback)
        if not session_dir:
            has_scoped_codex = any(codex_meta(path)[1] == os.getcwd() for path in codex_files)
            if not has_scoped_codex:
                print(f"Error: no session source for this cwd. Expected ~/.claude/projects/{encoded}", file=sys.stderr)
                print("  cwd may have drifted, or this project has no sessions. Re-run from the session's", file=sys.stderr)
                print("  launch directory, or pass --all-projects (backstop) / --fallback-any-project (may be wrong).", file=sys.stderr)
                sys.exit(1)
            print(f"Session source: Codex rollouts for {os.getcwd()}")
            scan_dirs = []
        else:
            print(f"Session directory: {session_dir}")  # attestation — confirm this is the expected project
            scan_dirs = [session_dir]

    # Dot-prefixed so Obsidian's metadata indexer ignores this tree: verbatim
    # transcripts are the bulk of vault markdown and a full-vault cold index of
    # them overflows Electron/V8's ~4GB heap cap (renderer OOM crash-loop). They
    # stay on disk (still synced, provenance-hashable), just unindexed. Whether
    # they are also version-controlled is a per-vault .gitignore decision — do not
    # assume git is available as a recovery path; the merge below is the guarantee.
    output_dir = vault_path / archive_root / ".Session Transcripts"

    cutoff = datetime.now() - timedelta(days=days)
    cutoff_ts = cutoff.timestamp()

    # Group sessions by date
    sessions_by_date = defaultdict(list)
    jsonl_files = sorted(
        (p for d in scan_dirs for p in d.glob("*.jsonl")),
        key=lambda p: p.stat().st_mtime,
    )

    exported = 0
    skipped = 0

    for jsonl_path in jsonl_files:
        if jsonl_path.stat().st_mtime < cutoff_ts:
            continue

        mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime)
        date_str = mtime.strftime("%Y-%m-%d")

        messages = parse_session(jsonl_path)
        if not messages:
            skipped += 1
            continue

        slug = get_session_slug(jsonl_path)

        # Get session start time
        first_ts = messages[0][2] if messages else ""
        try:
            dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            start_time = dt.strftime("%H:%M")
        except (ValueError, AttributeError):
            start_time = "unknown"

        formatted = format_session(messages, slug, start_time)
        if formatted:
            # Body only — the header is re-emitted by the writer, so that merging
            # with an existing file compares like with like.
            body = formatted.split("\n", 1)[1] if "\n" in formatted else ""
            sessions_by_date[date_str].append((start_time, slug, body))
            exported += 1

    # Codex CLI rollouts — same mtime window; cwd-scoped unless --all-projects,
    # mirroring the Claude source's per-project scoping.
    codex_exported = 0
    for jsonl_path in codex_files:
        if jsonl_path.stat().st_mtime < cutoff_ts:
            continue
        sid, sess_cwd = codex_meta(jsonl_path)
        if not all_projects and sess_cwd != os.getcwd():
            continue
        mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime)
        date_str = mtime.strftime("%Y-%m-%d")

        messages = parse_codex_session(jsonl_path)
        if not messages:
            skipped += 1
            continue

        # Slug from the FILENAME's uuid, not session_meta: a spawned sub-agent's
        # rollout records the PARENT's session_id in its meta, so meta-based
        # slugs collapse parent and sub-agent into one key and can silently
        # merge their transcripts. The filename uuid is unique per rollout.
        # 13 chars spans uuidv7's time prefix + next group: ids minted seconds
        # apart (a parent and its spawned sub-agent) share the first 8 chars.
        slug = f"codex-{jsonl_path.stem[-36:][:13]}"
        first_ts = messages[0][2]
        try:
            dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            start_time = dt.strftime("%H:%M")
        except (ValueError, AttributeError):
            start_time = "unknown"

        formatted = format_session(messages, slug, start_time)
        if formatted:
            body = formatted.split("\n", 1)[1] if "\n" in formatted else ""
            sessions_by_date[date_str].append((start_time, slug, body))
            codex_exported += 1
    exported += codex_exported

    # Write one file per date — MERGE, never replace.
    #
    # The JSONL source is auto-deleted after 30 days, so a day file is often the
    # only surviving copy of a session. A wholesale rewrite therefore destroys
    # data whenever this run sees fewer sessions than a previous run did — which
    # happens for any number of upstream reasons (a session's mtime drifting to a
    # later date, the --days window sliding past it, a partial project scan).
    # Rather than diagnose every such cause, the writer is append-only: sessions
    # already on disk are carried forward, and an incoming copy replaces one on
    # disk only when it is longer (a session that grew since the last export).
    files_written = 0
    carried_total = 0
    for date_str, sessions in sorted(sessions_by_date.items()):
        output_file = output_dir / f"{date_str}.md"
        try:
            # Count carry-forwards from the snapshot that actually won the
            # compare-and-swap, not from a stale failed attempt.
            carried_total += write_day_locked(output_file, date_str, sessions, locked_edit)
        except (OSError, RuntimeError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        files_written += 1

    # Summary to stdout for the hygiene report
    print(f"Sessions exported: {exported} ({codex_exported} Codex)")
    print(f"Sessions skipped (empty): {skipped}")
    print(f"Transcript files written: {files_written}")
    if carried_total:
        print(f"Sessions carried forward from existing files: {carried_total}")
    for date_str in sorted(sessions_by_date.keys()):
        count = len(sessions_by_date[date_str])
        print(f"  {date_str}: {count} sessions")


if __name__ == "__main__":
    main()
