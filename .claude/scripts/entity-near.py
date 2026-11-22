#!/usr/bin/env python3
"""Near-spelling candidates among the places an entity home can live.

Each name is compared with Markdown file and folder names, front matter,
headings, table cells, bold list lead-ins and list entries that open with a
wikilink. Body text is never compared: a mention is not a home, and an exact
search already finds mentions.
"""
from __future__ import annotations
import argparse
import bisect
import difflib
import itertools
import json
import operator
import os
from pathlib import Path
import re
import sys
import unicodedata

MIN_SIMILARITY = 0.8
DEFAULT_MAX_BYTES = 32_000_000
SCORE_MEMO_LIMIT = 250_000  # per name and per score; a full memo is emptied and refilled
SCOPE = ("Markdown file and folder names, front matter, headings, table cells, bold list lead-ins "
         "and list entries opening with a wikilink; body text not compared; .git excluded; "
         "symlinks not followed")
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
WORD = re.compile(r"[^\W_]+")
FRONT_MATTER_LINES = 200  # a leading '---' with no closing line this soon is a rule, not front matter
QUOTE = re.compile(r"(?:\s*>)+[ \t]?")  # \s, to agree with the lstrip() pre-check
HEADING = re.compile(r" {0,3}#{1,6}[ \t]+(.*)")
CELL_BREAK = re.compile(r"(?<!\\)\|")
ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])[ \t]+(?:\[.\][ \t]+)?(?:(\*{2,3}|_{2,3})(.+?)\1|\[\[([^\]]+)\]\])")
HOME_STARTS = frozenset("#|>-*+0123456789")

COMBINING = {}  # code point -> None for every combining character, filled on first use


def words(text):
    text = CAMEL.sub(" ", text)
    if text.isascii():  # casefold is lower() and NFKD is the identity for ASCII
        return WORD.findall(text.lower())
    if not COMBINING:
        COMBINING.update((point, None) for point in range(sys.maxunicode + 1)
                         if unicodedata.combining(chr(point)))
    return WORD.findall(unicodedata.normalize("NFKD", text.casefold()).translate(COMBINING))


def home_lines(text):
    """Yield (line number, kind, text) for each line that can name a home.

    Lines inside code fences are kept: a fence that never closes would otherwise
    hide every later heading, and an extra candidate costs only a comparison.
    """
    lines = text.splitlines()
    body = 0
    if lines and lines[0].strip() == "---":
        for index in range(1, min(len(lines), FRONT_MATTER_LINES + 1)):
            if lines[index].strip() in ("---", "..."):
                for inner in range(1, index):
                    yield inner + 1, "front matter", lines[inner]
                body = index + 1
                break
    for number, line in enumerate(lines[body:], body + 1):
        first = line.lstrip()[:1]
        if first not in HOME_STARTS:
            continue
        if first == ">":  # block quotes and callouts can hold any of the forms below
            line = line[QUOTE.match(line).end():]
            first = line.lstrip()[:1]
        match = HEADING.match(line)
        if match:
            yield number, "heading", match.group(1)
        elif first == "|":
            for cell in CELL_BREAK.split(line.strip().strip("|")):
                yield number, "table cell", cell
        else:
            match = ITEM.match(line)
            if match:
                yield number, "list link" if match.group(3) else "list lead-in", match.group(2) or match.group(3)


class Scores(dict):
    """Per-token score, computed on first lookup and kept up to a size limit."""

    def __init__(self, compute):
        super().__init__()
        self.compute = compute

    def __missing__(self, token):
        if len(self) >= SCORE_MEMO_LIMIT:
            self.clear()
        value = self[token] = self.compute(token)
        return value


class Query:
    """One name, with integer bounds that can only over-admit a window.

    SequenceMatcher's ratio is 2*M/T, with M the matched characters and T the
    combined length of the name (Lq) and the window's joined tokens (Lc). A
    window passes ratio >= 0.8 only if 5*M >= 2*T. Two consequences, both exact:

    Adjacent pairs. Matched blocks are separated by unmatched characters, so at
    least 3*M - T - 1 positions of the window start a character pair that also
    occurs in the name; hence 5*hits + 5 >= T. Hits inside tokens add up, and
    w tokens have w - 1 joins, so sum(5*hits(t) - len(t)) >= Lq - 5*w. That sum
    is taken for every window with prefix differences in C.

    Shared characters. M never exceeds the character multiset shared with the
    name, which is at most the sum of each token's own share, so
    sum(5*share(t) - 2*len(t)) >= 2*Lq.

    Only windows passing both reach SequenceMatcher. A window longer than
    1.5*Lq fails the length test below, which is how a separator token longer
    than that keeps windows from spanning two candidates.
    """

    def __init__(self, name):
        self.name = name
        self.parts = words(name)
        self.text = "".join(self.parts)
        self.length = len(self.text)
        counts = self.counts = {c: self.text.count(c) for c in set(self.text)}
        pairs = self.pairs = {self.text[i:i + 2] for i in range(self.length - 1)}
        self.widths = range(max(1, len(self.parts) - 1), len(self.parts) + 2)
        self.pair_scores = Scores(
            lambda token: 5 * sum(token[i:i + 2] in pairs for i in range(len(token) - 1)) - len(token))
        self.share_scores = Scores(
            lambda token: 5 * sum(min(token.count(c), counts[c]) for c in set(token) if c in counts) - 2 * len(token))

    def matches(self, tokens):
        """Yield (start, width, similarity) in width-then-start order."""
        share_scores, counts, pairs = self.share_scores, self.counts, self.pairs
        pair = list(itertools.accumulate(map(self.pair_scores.__getitem__, tokens), initial=0))
        count, own, need = len(tokens), self.length, 2 * self.length
        for width in self.widths:
            if width > count:
                break
            floor = own - 5 * width
            sums = map(operator.sub, itertools.islice(pair, width, None), pair)
            for start in itertools.compress(range(count - width + 1), map(floor.__le__, sums)):
                window = tokens[start:start + width]
                share, total = 0, own
                for token in window:
                    share += share_scores[token]
                    total += len(token)
                if share < need or 5 * min(own, total - own) < 2 * total:
                    continue
                # The same two bounds, now exact for the joined window (joins included).
                compact = "".join(window)
                if 5 * sum(min(compact.count(c), n) for c, n in counts.items()) < 2 * total:
                    continue
                if 5 * sum(compact[i:i + 2] in pairs for i in range(len(compact) - 1)) + 5 < total:
                    continue
                matcher = difflib.SequenceMatcher(None, self.text, compact, autojunk=False)
                if matcher.quick_ratio() >= MIN_SIMILARITY:
                    similarity = matcher.ratio()
                    if similarity >= MIN_SIMILARITY:
                        yield start, width, similarity


def scan(root, names, max_bytes=DEFAULT_MAX_BYTES):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("root must be a directory")
    if not names or any(not words(name) or len(words(name)) > 16 or len(name) > 256 for name in names):
        raise ValueError("names must contain 1–16 words and at most 256 characters")
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    queries = [Query(name) for name in names]
    separator = "\0" * (2 * max(query.length for query in queries) + 1)
    report = {"root": str(root), "scope": SCOPE, "complete": True, "files": 0, "candidates": 0,
              "errors": [], "matches": []}

    def compare(path, candidates):
        """Compare (line, kind, text) candidates; no window spans two of them."""
        tokens, starts, kept = [], [], []
        for line, kind, text in candidates:
            found = words(text)
            if found:
                starts.append(len(tokens))
                kept.append((line, kind))
                tokens.extend(found)
                tokens.append(separator)
        report["candidates"] += len(kept)
        if not tokens:
            return
        for query in queries:
            for start, width, similarity in query.matches(tokens):
                line, kind = kept[bisect.bisect_right(starts, start) - 1]
                report["matches"].append({"name": query.name, "path": path, "line": line, "kind": kind,
                                          "phrase": " ".join(tokens[start:start + width]),
                                          "similarity": similarity})

    def walk_error(error):
        report["errors"].append({"path": str(error.filename), "error": "enumeration_failed"})

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d != ".git" and not (Path(directory) / d).is_symlink())
        folder = Path(directory)
        if folder != root:
            compare(str(folder.relative_to(root)), [(0, "folder name", folder.name)])
        for filename in sorted(files):
            path = folder / filename
            if path.suffix.lower() != ".md" or path.is_symlink():
                continue
            relative = str(path.relative_to(root))
            report["files"] += 1
            candidates = [(0, "file name", path.stem)]
            try:
                with path.open("rb") as handle:
                    raw = handle.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    report["errors"].append({"path": relative, "error": "oversized",
                                             "bytes": path.stat().st_size, "limit": max_bytes})
                elif b"\0" in raw:
                    raise UnicodeError("NUL in Markdown")
                else:
                    candidates.extend(home_lines(raw.decode("utf-8-sig")))
            except (OSError, UnicodeError) as error:
                report["errors"].append({"path": relative, "error": type(error).__name__})
            compare(relative, candidates)  # the file's name is compared even when its text is not
    report["complete"] = not report["errors"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--name", action="append", required=True)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    try:
        report = scan(args.root, args.name, args.max_bytes)
    except (ValueError, OSError) as error:
        known = {
            "root must be a directory": "invalid_root",
            "names must contain 1–16 words and at most 256 characters": "invalid_name",
            "max_bytes must be positive": "invalid_size_limit",
        }
        code = "io_error" if isinstance(error, OSError) else known.get(str(error), "invalid_input")
        print(json.dumps({"complete": False, "error": code}))
        return 2
    # A name with undecodable bytes is escaped rather than failing the whole report.
    sys.stdout.buffer.write(json.dumps(report, ensure_ascii=False).encode("utf-8", "backslashreplace") + b"\n")
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
