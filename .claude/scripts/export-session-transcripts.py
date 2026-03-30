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
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


def find_session_dir():
    """Find the JSONL session directory for the current project."""
    claude_dir = Path.home() / ".claude" / "projects"
    # The directory name is the CWD path with / replaced by -
    # e.g., /home/user -> -home-user
    cwd = os.environ.get("HOME", str(Path.home()))
    encoded = cwd.replace("/", "-")
    session_dir = claude_dir / encoded
    if session_dir.exists():
        return session_dir

    # Fallback: find any project dir
    for d in claude_dir.iterdir():
        if d.is_dir() and list(d.glob("*.jsonl")):
            return d
    return None


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


def main():
    if len(sys.argv) < 2:
        print("Usage: export-session-transcripts.py <vault_path> [--days N]", file=sys.stderr)
        sys.exit(1)

    vault_path = Path(sys.argv[1])
    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    session_dir = find_session_dir()
    if not session_dir:
        print("Error: Could not find session directory", file=sys.stderr)
        sys.exit(1)

    output_dir = vault_path / "06 Archive" / "Claude" / "Session Transcripts"
    output_dir.mkdir(parents=True, exist_ok=True)

    cutoff = datetime.now() - timedelta(days=days)
    cutoff_ts = cutoff.timestamp()

    # Group sessions by date
    sessions_by_date = defaultdict(list)
    jsonl_files = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)

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
            sessions_by_date[date_str].append((start_time, formatted))
            exported += 1

    # Write one file per date
    files_written = 0
    for date_str, sessions in sorted(sessions_by_date.items()):
        output_file = output_dir / f"{date_str}.md"

        # Sort sessions by start time
        sessions.sort(key=lambda x: x[0])

        content = f"# Session Transcripts — {date_str}\n\n"
        content += f"Auto-exported from `~/.claude/projects/` JSONL files.\n\n---\n\n"
        for _, formatted in sessions:
            content += formatted + "\n---\n\n"

        output_file.write_text(content)
        files_written += 1

    # Summary to stdout for the hygiene report
    print(f"Sessions exported: {exported}")
    print(f"Sessions skipped (empty): {skipped}")
    print(f"Transcript files written: {files_written}")
    for date_str in sorted(sessions_by_date.keys()):
        count = len(sessions_by_date[date_str])
        print(f"  {date_str}: {count} sessions")


if __name__ == "__main__":
    main()
