#!/usr/bin/env python3
"""Near-spelling candidates from a content-bound local Markdown token cache."""
from __future__ import annotations
import argparse
import bisect
import difflib
import hashlib
import itertools
import json
import operator
import os
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata

TABLES = {"entity_tokens", "entity_roots", "opencairn_entity_cache"}
MIN_SIMILARITY = 0.8
DEFAULT_MAX_BYTES = 32_000_000
SCORE_MEMO_LIMIT = 250_000  # per name and per score; a full memo is emptied and refilled
CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
WORD = re.compile(r"[^\W_]+")
PAYLOAD = re.compile(r"[\w \n]*")


COMBINING = {}  # code point -> None for every combining character, filled on first use


def words(text):
    text = CAMEL.sub(" ", text)
    if text.isascii():  # casefold is lower() and NFKD is the identity for ASCII
        return WORD.findall(text.lower())
    if not COMBINING:
        COMBINING.update((point, None) for point in range(sys.maxunicode + 1)
                         if unicodedata.combining(chr(point)))
    return WORD.findall(unicodedata.normalize("NFKD", text.casefold()).translate(COMBINING))


def tokenise(text):
    """Folded words, space-joined, one payload line per source line."""
    return "\n".join(" ".join(words(line)) for line in text.splitlines())


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

    Only windows passing both reach SequenceMatcher; its test is unchanged.
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
        self.compared = 0

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
                self.compared += 1
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


def scan(root, cache, names, max_bytes=DEFAULT_MAX_BYTES):
    root, cache = Path(root).resolve(), Path(cache).resolve()
    if not root.is_dir() or cache == root or root in cache.parents:
        raise ValueError("root must be a directory and cache must be outside it")
    if not names or any(not words(name) or len(words(name)) > 16 or len(name) > 256 for name in names):
        raise ValueError("names must contain 1–16 words and at most 256 characters")
    queries = [Query(name) for name in names]
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    cache.parent.mkdir(parents=True, exist_ok=True)
    old_umask = os.umask(0o077)
    try:
        connection = sqlite3.connect(cache, timeout=0.1)
    finally:
        os.umask(old_umask)
    algorithm = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = {"root": str(root), "algorithm_sha256": algorithm,
              "scope": "regular Markdown files; .git excluded; symlinks not followed",
              "complete": True, "files": {}, "errors": [], "matches": [], "cache_warnings": [],
              "tokenised": 0, "reused_tokens": 0, "processed_tokens": 0, "compared_windows": 0}
    writable = True

    def write(sql, params=()):
        nonlocal writable
        if not writable:
            return False
        try:
            connection.execute(sql, params)
            connection.commit()  # never hold a write transaction across matching
            return True
        except sqlite3.OperationalError as error:
            connection.rollback()
            if "locked" not in str(error).lower():
                raise
            writable = False
            report["cache_warnings"].append("cache_busy; fresh computation continues; pruning deferred")
            return False

    try:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and tables != TABLES:
            raise ValueError("not a recognised entity cache; choose a new cache path")
        if not tables:
            connection.execute("BEGIN IMMEDIATE")
            tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not tables:
                connection.execute("CREATE TABLE entity_tokens (algorithm TEXT, content TEXT, payload TEXT, PRIMARY KEY(algorithm,content))")
                connection.execute("CREATE TABLE entity_roots (root TEXT, path TEXT, algorithm TEXT, content TEXT, PRIMARY KEY(root,path))")
                connection.execute("CREATE TABLE opencairn_entity_cache (version INTEGER)")
                connection.execute("INSERT INTO opencairn_entity_cache VALUES (1)")
            elif tables != TABLES:
                raise ValueError("not a recognised entity cache")
            connection.commit()
        if connection.execute("SELECT version FROM opencairn_entity_cache").fetchall() != [(1,)]:
            raise ValueError("unsupported entity cache schema")

        write("CREATE INDEX IF NOT EXISTS entity_root_content ON entity_roots (algorithm,content)")

        def walk_error(error):
            report["errors"].append({"path": str(error.filename), "error": "enumeration_failed"})

        for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
            dirs[:] = sorted(d for d in dirs if d != ".git" and not (Path(directory)/d).is_symlink())
            for filename in sorted(files):
                path = Path(directory)/filename
                if path.suffix.lower() != ".md" or path.is_symlink():
                    continue
                relative = str(path.relative_to(root))
                try:
                    with path.open("rb") as handle:
                        raw = handle.read(max_bytes + 1)
                    if len(raw) > max_bytes:
                        report["errors"].append({"path": relative, "error": "oversized",
                                                 "bytes": path.stat().st_size, "limit": max_bytes})
                        continue
                    if b"\0" in raw:
                        raise UnicodeError("NUL in Markdown")
                    text = raw.decode("utf-8")
                except (OSError, UnicodeError) as error:
                    report["errors"].append({"path": relative, "error": type(error).__name__})
                    continue
                sha = hashlib.sha256(raw).hexdigest()
                report["files"][relative] = sha
                row = connection.execute("SELECT payload FROM entity_tokens WHERE algorithm=? AND content=?", (algorithm, sha)).fetchone()
                if row is None:
                    payload = tokenise(text)
                    tokens = payload.split()
                    write("INSERT OR IGNORE INTO entity_tokens VALUES (?,?,?)", (algorithm, sha, payload))
                    report["tokenised"] += len(tokens)
                else:
                    payload = row[0]
                    if not isinstance(payload, str) or "_" in payload or not PAYLOAD.fullmatch(payload):
                        raise ValueError("invalid cached tokens")
                    tokens = payload.split()
                    report["reused_tokens"] += len(tokens)
                report["processed_tokens"] += len(tokens)
                line_ends = None
                for query in queries:
                    # Adjacent token counts preserve near-spellings across internal capitals.
                    # Windows may overlap; match counts are not entity counts.
                    for start, width, similarity in query.matches(tokens):
                        if line_ends is None:  # tokens up to and including each payload line
                            line_ends = list(itertools.accumulate(len(line.split()) for line in payload.split("\n")))
                        report["matches"].append({"name": query.name, "path": relative, "source_sha256": sha,
                                                  "line": bisect.bisect_right(line_ends, start) + 1,
                                                  "phrase": " ".join(tokens[start:start + width]),
                                                  "similarity": similarity})
                print(json.dumps({"file": relative, "processed_tokens": report["processed_tokens"],
                                  "tokenised": report["tokenised"], "reused_tokens": report["reused_tokens"]}), file=sys.stderr)
        report["compared_windows"] = sum(query.compared for query in queries)
        report["complete"] = not report["errors"]
        # Cache rows are derived: unreadable/unseen paths can be safely recomputed later.
        if writable:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM entity_roots WHERE root=?", (str(root),))
                connection.executemany("INSERT INTO entity_roots VALUES (?,?,?,?)",
                                       [(str(root), path, algorithm, sha) for path, sha in report["files"].items()])
                connection.execute("DELETE FROM entity_tokens WHERE NOT EXISTS (SELECT 1 FROM entity_roots r WHERE r.algorithm=entity_tokens.algorithm AND r.content=entity_tokens.content)")
                connection.commit()
            except sqlite3.OperationalError as error:
                connection.rollback()
                if "locked" not in str(error).lower():
                    raise
                report["cache_warnings"].append("cache_busy; pruning deferred")
        return report
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--name", action="append", required=True)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args()
    try:
        report = scan(args.root, args.cache, args.name, args.max_bytes)
    except (ValueError, OSError, sqlite3.Error) as error:
        known = {
            "root must be a directory and cache must be outside it": "invalid_root_or_cache",
            "names must contain 1–16 words and at most 256 characters": "invalid_name",
            "max_bytes must be positive": "invalid_size_limit",
            "not a recognised entity cache; choose a new cache path": "foreign_cache",
            "not a recognised entity cache": "foreign_cache",
            "unsupported entity cache schema": "unsupported_cache_schema",
            "invalid cached tokens": "invalid_cache_payload",
        }
        if isinstance(error, sqlite3.Error):
            code = "cache_busy" if "locked" in str(error).lower() else "cache_error"
        elif isinstance(error, OSError):
            code = "io_error"
        else:
            code = known.get(str(error), "invalid_input_or_cache")
        print(json.dumps({"complete": False, "error": code}))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
