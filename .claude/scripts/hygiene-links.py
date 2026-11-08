#!/usr/bin/env python3
"""Read-only, approximate basename link scan for weekly hygiene's fallback.

One walk/read pass; no persistent index. JSON is emitted only after the entire
scan and grep-BRE exclusion filter succeed. This is not Obsidian resolution.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


LINK = re.compile(rb"\[\[[^\]\n]*\]\]")


def targets(content):
    # Match rg's line-oriented extraction and sed's normalisation order.
    for match in LINK.finditer(content):
        target = match[0][2:-2].split(b"|", 1)[0].split(b"#", 1)[0]
        target = target.rsplit(b"/", 1)[-1].rstrip(b" \t\r\v\f")
        if target:
            yield os.fsdecode(target)


def exclude(rows, root):
    path = root / ".claude/hygiene-excludes"
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        # A dangling excludes symlink is a read failure, not an absent filter.
        if path.is_symlink():
            raise
        return rows, False
    patterns = [line for line in content.split(b"\n")
                if line and not line.startswith(b"#")]
    if not patterns:
        return rows, False
    # Keep grep's basic regular expressions, including BRE-only operators.
    # One child process for the complete result, never one per note.
    with tempfile.NamedTemporaryFile(prefix="hygiene-excludes-") as temporary:
        temporary.write(b"\n".join(patterns) + b"\n")
        temporary.flush()
        result = subprocess.run(
            ["grep", "-v", "-f", temporary.name],
            input=b"".join(os.fsencode(row) + b"\n" for row in rows),
            capture_output=True)
    if result.returncode not in (0, 1):
        raise OSError("excludes filter failed: " + os.fsdecode(result.stderr).strip())
    return set(map(os.fsdecode, result.stdout.split(b"\n")[:-1])), True


def scan(root):
    if not root.is_dir():
        raise OSError(f"vault directory unavailable: {root}")
    notes, incoming, live_targets, candidates = set(), set(), set(), []
    count = 0

    def fail(error):
        raise error

    for directory, children, files in os.walk(root, onerror=fail):
        children[:] = sorted(name for name in children if name != ".stversions")
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = Path(directory) / name
            relative = path.relative_to(root)
            if "\n" in str(relative):
                raise OSError(f"newline in note path cannot be filtered: {relative!s}")
            content = path.read_bytes()  # Read failures invalidate the whole scan.
            if b"\0" in content:
                raise OSError(f"binary Markdown cannot be scanned completely: {relative}")
            count += 1
            notes.add(name[:-3])
            linked = set(targets(content))
            incoming.update(linked)
            if "06 Archive" not in relative.parts[:-1]:
                live_targets.update(linked)
            # Original find -type f excludes symlink orphan candidates.
            if not path.is_symlink() and relative.parts[0] in ("03 Projects", "04 Areas"):
                candidates.append((relative.as_posix(), name[:-3]))
    unresolved = live_targets - notes
    orphans = {path for path, name in candidates if name not in incoming}
    allowed, active = exclude(unresolved | orphans, root)
    order = os.fsencode
    return dict(status="ok", mode="basename-approximation", notes_scanned=count,
                excludes_active=active,
                unresolved_targets=sorted(unresolved & allowed, key=order),
                orphan_paths=sorted(orphans & allowed, key=order),
                deadends="unavailable (CLI unavailable)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path)
    args = parser.parse_args()
    try:
        result = scan(args.vault.absolute())
    except (OSError, ValueError) as error:
        print(f"hygiene-links: {error}", file=sys.stderr)
        print(json.dumps(dict(status="unavailable", error=str(error),
                              unresolved_targets=None, orphan_paths=None)))
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
