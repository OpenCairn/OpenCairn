import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".claude/scripts/entity-near.py"
spec = importlib.util.spec_from_file_location("entity_near", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def setup(tmp_path):
    root = tmp_path / "notes"; root.mkdir()
    cache = tmp_path / "cache.sqlite"
    return root, cache


def test_normalisation_and_cache_reuse(tmp_path, monkeypatch):
    root, cache = setup(tmp_path)
    (root / "old.md").write_text("# Café-Bridge\nCafe bridge remains the entity home.\n")
    first = mod.scan(root, cache, ["Cafe Bridge"])
    original = mod.words
    def guard(text):
        assert not text.startswith("#") and "remains" not in text, "cached body was tokenised again"
        return original(text)
    monkeypatch.setattr(mod, "words", guard)
    second = mod.scan(root, cache, ["Café_Bridge"])
    assert first["complete"] and second["complete"]
    assert first["tokenised"] > 0 and first["reused_tokens"] == 0
    assert second["tokenised"] == 0 and second["reused_tokens"] == first["processed_tokens"]
    assert {m["line"] for m in first["matches"]} == {1, 2}
    assert [(m["path"],m["phrase"]) for m in first["matches"]] == [(m["path"],m["phrase"]) for m in second["matches"]]


def test_same_mtime_changed_content_invalidates_cache(tmp_path):
    root, cache = setup(tmp_path); p = root / "home.md"
    p.write_text("Cedar Link"); before = p.stat()
    first = mod.scan(root, cache, ["Cedar Link"])
    p.write_text("Birch Unit"); os.utime(p, ns=(before.st_atime_ns,before.st_mtime_ns))
    second = mod.scan(root, cache, ["Cedar Link"])
    assert first["matches"] and not second["matches"]
    assert second["tokenised"] > 0
    assert first["files"]["home.md"] != second["files"]["home.md"]


def test_hidden_and_archive_reached_removed_file_not_reused(tmp_path):
    root, cache = setup(tmp_path)
    for folder in [".hidden", "06 Archive"]:
        (root/folder).mkdir(); (root/folder/"home.md").write_text("Cedar Link")
    (root/".git").mkdir(); (root/".git/ignore.md").write_text("Cedar Link")
    result=mod.scan(root, cache, ["Cedar Link"])
    assert set(result["files"]) == {".hidden/home.md", "06 Archive/home.md"}
    (root/".hidden/home.md").unlink()
    result=mod.scan(root, cache, ["Cedar Link"])
    assert set(result["files"]) == {"06 Archive/home.md"}


def test_errors_do_not_read_as_clean_negative(tmp_path):
    root, cache = setup(tmp_path)
    (root/"large.md").write_text("x" * 50)
    (root/"control.md").write_text("Cedar")
    result=mod.scan(root, cache, ["Cedar"], max_bytes=20)
    assert not result["complete"] and result["errors"]
    assert result["matches"][0]["path"] == "control.md"


def test_cache_cannot_write_inside_root(tmp_path):
    root, _ = setup(tmp_path)
    with pytest.raises(ValueError): mod.scan(root, root/"cache.sqlite", ["Cedar"])
    assert not (root/"cache.sqlite").exists()


def test_near_spelling_not_only_exact_and_unrelated_control(tmp_path):
    root, cache = setup(tmp_path)
    (root/"home.md").write_text("Ceder Link\nAn unrelated sentence.")
    result=mod.scan(root, cache, ["Cedar Link"])
    assert result["matches"] and all("ceder link" in m["phrase"] for m in result["matches"])


def test_invalid_bytes_are_incomplete(tmp_path):
    root, cache = setup(tmp_path); (root/"bad.md").write_bytes(b"\xff")
    assert not mod.scan(root, cache, ["Cedar"])["complete"]

@pytest.mark.parametrize("source,query", [("CedarLink", "Cedar Link"), ("Cedar Link", "CedarLink")])
def test_separator_fold_camelcase(tmp_path, source, query):
    root, cache = setup(tmp_path); (root/"home.md").write_text(source)
    assert mod.scan(root, cache, [query])["matches"]


def test_threshold_boundary_and_negative(tmp_path):
    root, cache = setup(tmp_path)
    (root/"home.md").write_text("Ceder\nCider\n")
    result = mod.scan(root, cache, ["Cedar"])
    assert [(m["phrase"],m["similarity"]) for m in result["matches"]] == [("ceder",0.8)]


def test_different_query_reuses_tokens(tmp_path, monkeypatch):
    root, cache = setup(tmp_path); (root/"home.md").write_text("# Ceder Link\n# Masen Unit\n")
    mod.scan(root, cache, ["Cedar Link"])
    original = mod.words
    def guard(text):
        assert not text.startswith("#")
        return original(text)
    monkeypatch.setattr(mod,"words",guard)
    result = mod.scan(root,cache,["Mason Unit"])
    assert result["tokenised"] == 0 and result["reused_tokens"] > 0
    assert result["matches"] and result["matches"][0]["phrase"] == "masen unit"


def test_symlink_is_outside_declared_scope(tmp_path):
    root, cache = setup(tmp_path)
    outside=tmp_path/"outside.md";outside.write_text("Cedar Link")
    try:
        (root/"link.md").symlink_to(outside)
    except OSError:
        pytest.skip("requires symlink support")
    result=mod.scan(root,cache,["Cedar Link"])
    assert result["complete"] and result["files"] == {} and result["matches"] == []


def test_deleted_content_is_pruned(tmp_path):
    import sqlite3
    root, cache=setup(tmp_path);p=root/"home.md";p.write_text("Cedar Link")
    mod.scan(root,cache,["Cedar Link"]);p.unlink()
    mod.scan(root,cache,["Cedar Link"])
    with sqlite3.connect(cache) as conn:
        assert conn.execute("SELECT COUNT(*) FROM entity_tokens").fetchone()[0] == 0


def test_busy_cache_falls_back_without_losing_fresh_hits(tmp_path):
    import sqlite3
    root, cache=setup(tmp_path);p=root/"home.md";p.write_text("Old Name")
    mod.scan(root,cache,["Cedar Link"])
    p.write_text("Ceder Link")
    with sqlite3.connect(cache) as holder:
        holder.execute("BEGIN IMMEDIATE")
        result=mod.scan(root,cache,["Cedar Link"])
        holder.rollback()
    assert result["complete"] and result["cache_warnings"]
    assert result["matches"][0]["phrase"] == "ceder link"


def test_unreadable_directory_is_not_clean(tmp_path):
    if not hasattr(os, "geteuid") or os.geteuid() == 0:
        pytest.skip("requires non-root directory permissions")
    root,cache=setup(tmp_path);hidden=root/"unreadable";hidden.mkdir()
    (hidden/"home.md").write_text("Cedar Link");hidden.chmod(0)
    try:result=mod.scan(root,cache,["Cedar Link"])
    finally:hidden.chmod(0o700)
    assert not result["complete"]
    assert result["errors"][0]["error"] == "enumeration_failed"


def test_cli_incomplete_has_nonzero_exit_and_control(tmp_path):
    import json,subprocess,sys
    root,cache=setup(tmp_path)
    (root/"large.md").write_text("x"*50);(root/"control.md").write_text("Cedar")
    result=subprocess.run([sys.executable,str(SCRIPT),"--root",str(root),"--cache",str(cache),
                           "--name","Cedar","--max-bytes","20"],capture_output=True,text=True,timeout=10)
    report=json.loads(result.stdout)
    assert result.returncode == 2 and not report["complete"]
    assert report["errors"][0]["error"] == "oversized" and report["errors"][0]["bytes"] == 50
    assert report["matches"][0]["path"] == "control.md"


def test_nul_markdown_is_incomplete(tmp_path):
    root,cache=setup(tmp_path);(root/"binary.md").write_bytes(b"Cedar\0Link")
    assert not mod.scan(root,cache,["Cedar Link"])["complete"]

@pytest.mark.parametrize("source,query", [("Macdonald","McDonald"),("McDonald","Macdonald"),("Yubykey","YubiKey")])
def test_internal_capital_near_spelling(tmp_path, source, query):
    root,cache=setup(tmp_path);(root/"home.md").write_text(source)
    assert mod.scan(root,cache,[query])["matches"]


def test_incomplete_scan_still_prunes_deleted_cached_content(tmp_path):
    import sqlite3
    root,cache=setup(tmp_path);old=root/"old.md";old.write_text("Cedar Link")
    mod.scan(root,cache,["Cedar Link"]);old.unlink()
    (root/"bad.md").write_bytes(b"\0")
    result=mod.scan(root,cache,["Cedar Link"])
    assert not result["complete"]
    with sqlite3.connect(cache) as conn:
        assert conn.execute("SELECT COUNT(*) FROM entity_tokens").fetchone()[0] == 0


def test_exclusive_cache_lock_fails_closed_with_specific_code(tmp_path):
    import json,sqlite3,subprocess,sys
    root,cache=setup(tmp_path);(root/"home.md").write_text("Cedar Link")
    mod.scan(root,cache,["Cedar Link"])
    with sqlite3.connect(cache) as holder:
        holder.execute("BEGIN EXCLUSIVE")
        result=subprocess.run([sys.executable,str(SCRIPT),"--root",str(root),"--cache",str(cache),
                               "--name","Cedar Link"],capture_output=True,text=True,timeout=10)
        holder.rollback()
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"complete":False,"error":"cache_busy"}


def test_character_filter_never_drops_a_threshold_match():
    import difflib,itertools
    values=["".join(chars) for n in range(1,5) for chars in itertools.product("abc",repeat=n)]
    for query in values:
        for candidate in values:
            score=difflib.SequenceMatcher(None,query,candidate,autojunk=False).ratio()
            possible=sum(c in set(query) for c in candidate)
            if score >= mod.MIN_SIMILARITY:
                assert 2*possible/(len(query)+len(candidate)) >= mod.MIN_SIMILARITY
