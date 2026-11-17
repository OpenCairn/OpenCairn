#!/usr/bin/env python3
"""Near-spelling candidates from a content-bound local Markdown token cache."""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata

TABLES = {"entity_tokens", "entity_roots", "opencairn_entity_cache"}
MIN_SIMILARITY = 0.8


def words(text):
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                     if not unicodedata.combining(c))
    return re.findall(r"[^\W_]+", folded, flags=re.UNICODE)


def scan(root, cache, names, max_bytes=2_000_000):
    root, cache = Path(root).resolve(), Path(cache).resolve()
    if not root.is_dir() or cache == root or root in cache.parents:
        raise ValueError("root must be a directory and cache must be outside it")
    queries = [(name, words(name)) for name in names]
    if not queries or any(not parts or len(parts) > 16 or len(name) > 256 for name, parts in queries):
        raise ValueError("names must contain 1–16 words and at most 256 characters")
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
              "tokenised": 0, "reused_tokens": 0, "processed_tokens": 0}
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
                    tokens = [(word, number) for number, line in enumerate(text.splitlines(), 1) for word in words(line)]
                    write("INSERT OR IGNORE INTO entity_tokens VALUES (?,?,?)", (algorithm, sha, json.dumps(tokens)))
                    report["tokenised"] += len(tokens)
                else:
                    tokens = json.loads(row[0])
                    if not isinstance(tokens, list) or any(not isinstance(t, list) or len(t) != 2 or not isinstance(t[0], str) or type(t[1]) is not int or t[1] < 1 for t in tokens):
                        raise ValueError("invalid cached tokens")
                    report["reused_tokens"] += len(tokens)
                report["processed_tokens"] += len(tokens)
                for original, parts in queries:
                    query = "".join(parts)
                    query_characters = set(query)
                    # Adjacent token counts preserve near-spellings across internal capitals.
                    # Windows may overlap; match counts are not entity counts.
                    for width in range(max(1, len(parts)-1), len(parts)+2):
                        for start in range(len(tokens) - width + 1):
                            window = tokens[start:start+width]
                            phrase = " ".join(token[0] for token in window)
                            compact = "".join(token[0] for token in window)
                            if 2 * min(len(query), len(compact)) / (len(query) + len(compact)) < MIN_SIMILARITY:
                                continue
                            # Every matched character must occur in the query. This is an
                            # upper bound (repetition can overcount), never a rejecting heuristic.
                            possible = sum(char in query_characters for char in compact)
                            if 2 * possible / (len(query) + len(compact)) < MIN_SIMILARITY:
                                continue
                            matcher = difflib.SequenceMatcher(None, query, compact, autojunk=False)
                            if matcher.quick_ratio() >= MIN_SIMILARITY:
                                score = matcher.ratio()
                                if score >= MIN_SIMILARITY:
                                    report["matches"].append({"name": original, "path": relative,
                                                              "source_sha256": sha, "line": window[0][1],
                                                              "phrase": phrase, "similarity": score})
                print(json.dumps({"file": relative, "processed_tokens": report["processed_tokens"],
                                  "tokenised": report["tokenised"], "reused_tokens": report["reused_tokens"]}), file=sys.stderr)
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
    parser.add_argument("--max-bytes", type=int, default=2_000_000)
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
