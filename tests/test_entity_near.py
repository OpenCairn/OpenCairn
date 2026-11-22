import difflib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import unicodedata

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".claude/scripts/entity-near.py"
spec = importlib.util.spec_from_file_location("entity_near", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def setup(tmp_path):
    root = tmp_path / "notes"; root.mkdir()
    return root


def found(result):
    return [(m["path"], m["line"], m["kind"], m["phrase"]) for m in result["matches"]]


def reference_words(text):
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.casefold())
                     if not unicodedata.combining(c))
    return re.findall(r"[^\W_]+", folded, flags=re.UNICODE)


def reference_matches(candidates, names):
    """Every window of every candidate compared, with no candidate selection."""
    result = []
    for name in names:
        parts = reference_words(name); query = "".join(parts)
        for width in range(max(1, len(parts) - 1), len(parts) + 2):
            for label, text in candidates:
                tokens = reference_words(text)
                for start in range(len(tokens) - width + 1):
                    window = tokens[start:start + width]
                    score = difflib.SequenceMatcher(None, query, "".join(window), autojunk=False).ratio()
                    if score >= mod.MIN_SIMILARITY:
                        result.append((name, label, " ".join(window), score))
    return result


def test_each_home_location_is_compared_and_body_text_is_not(tmp_path):
    root = setup(tmp_path)
    (root / "Ceder Link").mkdir()
    (root / "Ceder Link" / "Cedar Lnik.md").write_text(
        "Intro mentions Cedar Link in passing.\n"
        "## Cedar-Link overview\n"
        "| Ceder Link | owner |\n"
        "|---|---|\n"
        "- **Cedar Lnik** — a list entry\n"
        "- [ ] **Cedar Linc** as a task lead-in\n"
        "Closing mention of Cedar Link.\n")
    result = mod.scan(root, ["Cedar Link"])
    assert result["complete"] and result["files"] == 1
    assert set(found(result)) == {
        ("Ceder Link", 0, "folder name", "ceder link"),
        ("Ceder Link/Cedar Lnik.md", 0, "file name", "cedar lnik"),
        ("Ceder Link/Cedar Lnik.md", 2, "heading", "cedar link"),
        ("Ceder Link/Cedar Lnik.md", 3, "table cell", "ceder link"),
        ("Ceder Link/Cedar Lnik.md", 5, "list lead-in", "cedar lnik"),
        ("Ceder Link/Cedar Lnik.md", 6, "list lead-in", "cedar linc"),
    }


@pytest.mark.parametrize("line,kind,phrase", [
    ("> ## Ceder Link", "heading", "ceder link"),
    ("> [!note] title\n> | 1 | Ceder Link |", "table cell", "ceder link"),
    (">> - **Ceder Link**", "list lead-in", "ceder link"),
    ("\u00a0> \u2003> ## Ceder Link", "heading", "ceder link"),
    ("| 1 | Ceder Link | supplier |", "table cell", "ceder link"),
    ("| | Ceder Link |", "table cell", "ceder link"),
    ("| [[orgs/acme-17\\|Ceder Link]] | supplier |", "table cell", "ceder link"),
    ("- __Ceder Link__ — supplier", "list lead-in", "ceder link"),
    ("- ***Ceder Link***", "list lead-in", "ceder link"),
    ("  - [/] **Ceder Link** in progress", "list lead-in", "ceder link"),
    ("3. [[acme-17|Ceder Link]] — supplier", "list link", "ceder link"),
    ("* [[People/Ceder Link]]", "list link", "ceder link"),
])
def test_home_forms_inside_quotes_cells_and_list_entries(tmp_path, line, kind, phrase):
    root = setup(tmp_path)
    (root / "index.md").write_text("opening paragraph\n" + line + "\n")
    result = mod.scan(root, ["Cedar Link"])
    got = [(m["kind"], m["phrase"]) for m in result["matches"]]
    assert (kind, phrase) in got and {k for k, _ in got} == {kind}  # a wider window may also match
    assert {m["line"] for m in result["matches"]} == {1 + len(line.split("\n"))}


def test_front_matter_is_compared_and_a_leading_rule_is_not_front_matter(tmp_path):
    root = setup(tmp_path)
    (root / "a.md").write_text("---\ntitle: Ceder Link\naliases:\n  - Cedar Lnik\ntags: [x]\n---\nbody Cedar Link\n")
    (root / "b.md").write_text("---\nCedar Link in body text after a rule\n# Other\n")
    (root / "c.md").write_bytes(b"\xef\xbb\xbf# Ceder Link\n")
    assert found(mod.scan(root, ["Cedar Link"])) == [
        ("a.md", 2, "front matter", "ceder link"), ("a.md", 4, "front matter", "cedar lnik"),
        ("c.md", 1, "heading", "ceder link")]


def test_exact_mentions_in_body_text_alone_return_nothing(tmp_path):
    root = setup(tmp_path)
    (root / "journal.md").write_text("Met Cedar Link today.\nCedar Link again.\n**Cedar Link:** a field label\n")
    result = mod.scan(root, ["Cedar Link"])
    assert result["complete"] and result["matches"] == [] and result["candidates"] == 1


def test_no_window_spans_two_candidates(tmp_path):
    root = setup(tmp_path)
    (root / "a.md").write_text("# Cedar\n# Link\n| Cedar |\n| Link |\n")
    (root / "cedar").mkdir(); (root / "cedar" / "link.md").write_text("plain\n")
    assert mod.scan(root, ["Cedar Link"])["matches"] == []
    (root / "b.md").write_text("# Cedar Link\n")
    assert found(mod.scan(root, ["Cedar Link"])) == [("b.md", 1, "heading", "cedar link")]


def test_normalisation_and_separator_folds(tmp_path):
    root = setup(tmp_path)
    (root / "home.md").write_text("# Café-Bridge\n## cafe_bridge notes\n### CafeBridge\n#### HTTPServer\n")
    result = mod.scan(root, ["Cafe Bridge", "http server"])
    assert {(m["name"], m["line"]) for m in result["matches"]} == {
        ("Cafe Bridge", 1), ("Cafe Bridge", 2), ("Cafe Bridge", 3), ("http server", 4)}


def test_hidden_and_archive_reached_git_and_symlinks_excluded(tmp_path):
    root = setup(tmp_path)
    for folder in [".hidden", "06 Archive"]:
        (root / folder).mkdir(); (root / folder / "home.md").write_text("# Cedar Link\n")
    (root / ".git").mkdir(); (root / ".git" / "ignore.md").write_text("# Cedar Link\n")
    outside = tmp_path / "outside"; outside.mkdir(); (outside / "far.md").write_text("# Cedar Link\n")
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
        (root / "link.md").symlink_to(outside / "far.md")
    except OSError:
        pass  # symlinks unavailable on this platform
    result = mod.scan(root, ["Cedar Link"])
    assert {m["path"] for m in result["matches"]} == {".hidden/home.md", "06 Archive/home.md"}
    assert result["files"] == 2


def test_unreadable_text_is_incomplete_but_its_name_is_still_compared(tmp_path):
    root = setup(tmp_path)
    (root / "Ceder Link.md").write_bytes(b"# heading\n\0")
    (root / "bad.md").write_bytes(b"\xff\xfe")
    result = mod.scan(root, ["Cedar Link"])
    assert not result["complete"]
    assert {e["path"] for e in result["errors"]} == {"Ceder Link.md", "bad.md"}
    assert found(result) == [("Ceder Link.md", 0, "file name", "ceder link")]


def test_size_limit_default_and_override(tmp_path):
    root = setup(tmp_path)
    (root / "big.md").write_text("ordinary archive line\n" * 150_000 + "# Cedar Link\n")
    assert (root / "big.md").stat().st_size > 3_000_000
    result = mod.scan(root, ["Cedar Link"])
    assert result["complete"] and found(result) == [("big.md", 150_001, "heading", "cedar link")]
    limited = mod.scan(root, ["Cedar Link"], max_bytes=1_000_000)
    assert not limited["complete"] and limited["errors"][0]["error"] == "oversized" and limited["matches"] == []
    (root / "big.md").rename(root / "Ceder Link.md")
    renamed = mod.scan(root, ["Cedar Link"], max_bytes=1_000_000)
    assert not renamed["complete"] and found(renamed) == [("Ceder Link.md", 0, "file name", "ceder link")]


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="needs POSIX permissions")
def test_unreadable_directory_is_not_clean(tmp_path):
    root = setup(tmp_path); locked = root / "locked"; locked.mkdir(); (locked / "home.md").write_text("# Cedar Link\n")
    locked.chmod(0)
    try:
        result = mod.scan(root, ["Cedar Link"])
    finally:
        locked.chmod(0o755)
    assert not result["complete"] and result["errors"][0]["error"] == "enumeration_failed"


def test_near_spelling_threshold_and_unrelated_control(tmp_path):
    root = setup(tmp_path)
    (root / "home.md").write_text("# Marowfield\n# Marrowfields\n# Sunnybrook\n# abcde\n# abcdx\n# abcxy\n")
    result = mod.scan(root, ["Marrowfield", "abcde"])
    assert [(m["name"], m["phrase"]) for m in result["matches"]] == [
        ("Marrowfield", "marowfield"), ("Marrowfield", "marrowfields"), ("abcde", "abcde"), ("abcde", "abcdx")]
    assert all(m["similarity"] >= mod.MIN_SIMILARITY for m in result["matches"])


def test_long_headings_match_inside_and_heading_marks_are_not_words(tmp_path):
    root = setup(tmp_path)
    (root / "home.md").write_text("## 2026 review — Ceder Link, second draft ##\n   ### Cedar Link\n    #### Cedar Link (indented code, not a heading)\n")
    assert found(mod.scan(root, ["Cedar Link"])) == [("home.md", 1, "heading", "ceder link"), ("home.md", 2, "heading", "cedar link")]


@pytest.mark.parametrize("alphabets,separators,longest_name", [
    (["ab", "abc", "abcde", "abcdefgh"], ["\n"], 4),
    (["aé", "abß", "aBcñ", "ab́c"], ["\n", "\r", "\r\n", " ", "\x1c", "\x0b"], 4),
    (["ab", "abc"], ["\n"], 16),
])
def test_matches_equal_the_exhaustive_per_candidate_reference(tmp_path, alphabets, separators, longest_name):
    rng = random.Random(20261122)
    def word(alphabet):
        return "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 7)))
    for case in range(120):
        alphabet = rng.choice(alphabets)
        root = tmp_path / f"case{case}"; root.mkdir()
        lines, candidates = [], [("file", "note")]
        for number in range(1, rng.randint(2, 30)):
            text = " ".join(word(alphabet) for _ in range(rng.randint(0, 9)))
            kind = rng.choice(["heading", "row", "lead", "body", "body"])
            if kind == "heading":
                lines.append("## " + text)
            elif kind == "row":
                lines.append("| " + text + " | other cell |")
            elif kind == "lead":
                lines.append("- **" + (text or "x") + "** trailing words")
                text = text or "x"
            else:
                lines.append("plain " + text)
            if kind != "body":
                candidates.append((number, text))
            if kind == "row":
                candidates.append((number, "other cell"))
        body = "".join(line + rng.choice(separators) for line in lines)
        (root / "note.md").write_bytes(body.encode("utf-8"))
        names = []
        while len(names) < rng.randint(1, 3):
            name = " ".join(word(alphabet) for _ in range(rng.randint(1, longest_name)))
            if 1 <= len(reference_words(name)) <= 16:  # a lone combining mark folds to no word
                names.append(name)
        expected = reference_matches(candidates, names)
        result = mod.scan(root, names)
        got = [(m["name"], "file" if m["kind"] == "file name" else m["line"], m["phrase"], m["similarity"])
               for m in result["matches"]]
        assert sorted(got, key=repr) == sorted(expected, key=repr), (case, names)


def test_word_folding_matches_the_reference():
    rng = random.Random(7)
    for alphabet in ("abzABZ019 _-.\t\r\x0b\x0c\x1c/", "abZ9 _-ȩ́́ñßﬁİ゙が→—ְאัก"):
        for _ in range(3000):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24)))
            assert mod.words(text) == reference_words(text), repr(text)
    for text in ["Café-Bridge", "ﬁnalStraße", "İstanbul NOTE", "naïveCamelCase"]:
        assert mod.words(text) == reference_words(text)


def test_window_bounds_never_drop_a_threshold_match():
    values = ["".join(chars) for n in range(1, 5) for chars in itertools.product("abc", repeat=n)]
    values += ["".join(chars) for n in range(5, 8) for chars in itertools.product("ab", repeat=n)]
    for query in values:
        pairs = {query[i:i + 2] for i in range(len(query) - 1)}
        for candidate in values:
            if difflib.SequenceMatcher(None, query, candidate, autojunk=False).ratio() < mod.MIN_SIMILARITY:
                continue
            total = len(query) + len(candidate)
            hits = sum(candidate[i:i + 2] in pairs for i in range(len(candidate) - 1))
            shared = sum(min(candidate.count(c), query.count(c)) for c in set(query))
            assert 5 * hits + 5 >= total and 5 * shared >= 2 * total, (query, candidate)


def test_emptying_a_full_score_memo_changes_no_result(tmp_path, monkeypatch):
    root = setup(tmp_path)
    lines = ["alpha beta gamma delta", "Ceder Link and Cedar Lnik", "epsilon zeta eta theta iota", "cedarlink"]
    (root / "home.md").write_text("".join("# " + line + "\n" for line in lines))
    expected = reference_matches([("file", "home")] + list(enumerate(lines, 1)), ["Cedar Link"])
    assert len(expected) >= 3
    monkeypatch.setattr(mod, "SCORE_MEMO_LIMIT", 2)
    result = mod.scan(root, ["Cedar Link"])
    got = [(m["name"], "file" if m["kind"] == "file name" else m["line"], m["phrase"], m["similarity"]) for m in result["matches"]]
    assert sorted(got, key=repr) == sorted(expected, key=repr)


@pytest.mark.parametrize("names,code", [
    ([], None), (["!!!"], "invalid_name"), ([" ".join(["w"] * 17)], "invalid_name"), (["x" * 257], "invalid_name")])
def test_invalid_names_are_rejected(tmp_path, names, code):
    root = setup(tmp_path)
    with pytest.raises(ValueError):
        mod.scan(root, names)
    if code:
        result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--name", names[0]],
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 2 and json.loads(result.stdout) == {"complete": False, "error": code}


def test_cli_reports_json_and_exit_status_with_a_control(tmp_path):
    root = setup(tmp_path)
    (root / "home.md").write_text("# Ceder Link\n")
    run = lambda *extra: subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--name", "Cedar Link", *extra],
                                        capture_output=True, text=True, timeout=20)
    clean = run()
    report = json.loads(clean.stdout)
    assert clean.returncode == 0 and report["complete"] and report["matches"][0]["phrase"] == "ceder link"
    assert "body text not compared" in report["scope"]
    (root / "bad.md").write_bytes(b"\0")
    incomplete = run()
    assert incomplete.returncode == 2 and not json.loads(incomplete.stdout)["complete"]
    missing = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root / "absent"), "--name", "Cedar Link"],
                             capture_output=True, text=True, timeout=20)
    assert missing.returncode == 2 and json.loads(missing.stdout) == {"complete": False, "error": "invalid_root"}


@pytest.mark.skipif(os.name == "nt", reason="needs a byte-named file")
def test_undecodable_file_name_still_yields_a_json_report(tmp_path):
    root = setup(tmp_path)
    try:
        with open(os.path.join(os.fsencode(root), b"Ceder Link \xff.md"), "wb") as handle:
            handle.write(b"# plain\n")
    except OSError:
        pytest.skip("file system rejects undecodable names")
    result = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--name", "Cedar Link"],
                            capture_output=True, timeout=20)
    report = json.loads(result.stdout.decode("utf-8"))
    assert result.returncode == 0 and report["complete"]
    assert [m["phrase"] for m in report["matches"]] == ["ceder link"]

