#!/usr/bin/env python3
"""Export Claude Code session JSONL files to readable markdown transcripts.

Extracts user messages and assistant text/tool-input content from JSONL session
files. Skips tool results (file contents, grep output, web scrapes) which are
bulk noise. Produces one markdown file per day in the vault archive.

Usage:
    export-session-transcripts.py <vault_path> [--days N]

Options:
    --days N    Export sessions modified in the last N days (default: 7)
"""

import json
import os
import re
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
    if allow_fallback:
        for d in sorted(claude_dir.iterdir()):
            if d.is_dir() and list(d.glob("*.jsonl")):
                return d, encoded
    return None, encoded


def all_session_dirs():
    """Every project dir containing JSONL — for the cross-project backstop sweep."""
    claude_dir = Path.home() / ".claude" / "projects"
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

        if role == "user":
            lines.append(f"**User{time_str}:**\n{text}\n")
        else:
            lines.append(f"**Claude{time_str}:**\n{text}\n")

    return "\n".join(lines)


SESSION_HDR = re.compile(r'^### (\S+) \((\d{2}:\d{2}|unknown)\)\s*\n')
SEPARATOR = "\n---\n\n"


def parse_exported(md_path):
    """Split an already-exported transcript file into {(slug, start): body}.

    Inverse of format_session() + the day-file writer. Returns {} if the file is
    missing or unreadable — an unreadable file must not block a fresh write.

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
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
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


def main():
    if len(sys.argv) < 2:
        print("Usage: export-session-transcripts.py <vault_path> [--days N] [--all-projects] [--fallback-any-project]", file=sys.stderr)
        sys.exit(1)

    vault_path = Path(sys.argv[1])
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    all_projects = "--all-projects" in sys.argv
    allow_fallback = "--fallback-any-project" in sys.argv

    if all_projects:
        scan_dirs = all_session_dirs()
        if not scan_dirs:
            print("Error: no project directories with JSONL under ~/.claude/projects/", file=sys.stderr)
            sys.exit(1)
        print(f"Session directories: {len(scan_dirs)} project(s) (--all-projects sweep)")
    else:
        session_dir, encoded = find_session_dir(allow_fallback=allow_fallback)
        if not session_dir:
            print(f"Error: no session directory for this cwd. Expected ~/.claude/projects/{encoded}", file=sys.stderr)
            print("  cwd may have drifted, or this project has no sessions. Re-run from the session's", file=sys.stderr)
            print("  launch directory, or pass --all-projects (backstop) / --fallback-any-project (may be wrong).", file=sys.stderr)
            sys.exit(1)
        print(f"Session directory: {session_dir}")  # attestation — confirm this is the expected project
        scan_dirs = [session_dir]

    # Dot-prefixed so Obsidian's metadata indexer ignores this tree: verbatim
    # transcripts are the bulk of vault markdown and a full-vault cold index of
    # them overflows Electron/V8's ~4GB heap cap (renderer OOM crash-loop). They
    # stay on disk (still synced, provenance-hashable), just unindexed. Whether
    # they are also version-controlled is a per-vault .gitignore decision — do not
    # assume git is available as a recovery path; the merge below is the guarantee.
    output_dir = vault_path / "06 Archive" / "Claude" / ".Session Transcripts"
    output_dir.mkdir(parents=True, exist_ok=True)

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

        merged = parse_exported(output_file)
        on_disk_keys = set(merged)

        incoming_keys = set()
        for start_time, slug, body in sessions:
            key = (slug, start_time)
            incoming_keys.add(key)
            if key not in merged or len(body) > len(merged[key]):
                merged[key] = body

        # Sessions this run could not see, preserved only because we merged.
        carried_total += len(on_disk_keys - incoming_keys)

        content = f"# Session Transcripts — {date_str}\n\n"
        content += f"Auto-exported from `~/.claude/projects/` JSONL files.\n\n---\n\n"
        for (slug, start_time), body in sorted(merged.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            content += f"### {slug} ({start_time})\n{body}\n---\n\n"

        output_file.write_text(content)
        files_written += 1

    # Summary to stdout for the hygiene report
    print(f"Sessions exported: {exported}")
    print(f"Sessions skipped (empty): {skipped}")
    print(f"Transcript files written: {files_written}")
    if carried_total:
        print(f"Sessions carried forward from existing files: {carried_total}")
    for date_str in sorted(sessions_by_date.keys()):
        count = len(sessions_by_date[date_str])
        print(f"  {date_str}: {count} sessions")


if __name__ == "__main__":
    main()
