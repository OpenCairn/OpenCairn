import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("TRANSCRIPT_CLEAN", ROOT / ".claude/scripts/transcript-clean.py"))

BODY = "\n\n".join(
    f"[{i // 60:02d}:{i % 60:02d}] **Speaker {1 + i % 2}:** "
    + " ".join(f"word{i}x{j} thinking" for j in range(40))
    for i in range(0, 600, 10)
) + "\n"

# Stub `claude -p`: reads the prompt on stdin, returns the chunk (optionally damaged) as JSON.
STUB = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
for flag in ("--tools", "--strict-mcp-config", "--setting-sources", "--no-session-persistence"):
    assert flag in args, flag
assert args[args.index("--tools") + 1] == "", "tools not disabled"
assert args[args.index("--setting-sources") + 1] == "", "setting sources not empty"
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(os.getcwd() + "\n")
prompt = sys.stdin.buffer.read().decode("utf-8")
with open(os.environ["STUB_LOG"] + ".prompt", "a", encoding="utf-8") as log:
    log.write(prompt)
chunk = prompt.split("\nChunk:\n", 1)[1]
mode = os.environ.get("STUB_MODE", "echo")
if mode == "preamble":
    chunk = "Here is the cleaned transcript chunk:\n\n" + chunk
elif mode == "drop_long":
    chunk = "\n\n".join(p for p in chunk.split("\n\n") if not p.startswith(LONG_MARK))
elif mode == "truncate":
    chunk = chunk[: len(chunk) // 2]
elif mode == "merge":
    paras = chunk.split("\n\n")
    paras[1] = paras[1] + " " + paras.pop(2).split(":** ", 1)[1]
    chunk = "\n\n".join(paras)
elif mode == "fail":
    print(json.dumps({"is_error": True, "result": "boom"})); sys.exit(1)
sys.stdout.buffer.write(json.dumps(
    {"result": chunk, "usage": {}, "modelUsage": {"stub": {}}}, ensure_ascii=False).encode("utf-8"))
'''.replace("LONG_MARK", repr("\u957f"))

# A no-timestamp CJK body (the --no-timestamps layout): no whitespace inside a paragraph,
# so each paragraph is one "word" and the prefix check has nothing to compare. The one
# long paragraph starts with LONG and carries about a third of the characters.
SHORT = "\u6211\u4eec\u4eca\u5929\u8ba8\u8bba\u8fd9\u4e2a\u95ee\u9898\u3002" * 4
LONG = "\u957f" + "\u8fd9\u662f\u4e00\u4e2a\u5f88\u957f\u7684\u6bb5\u843d\u3002" * 40
CJK_BODY = "\n\n".join([SHORT] * 4 + [LONG] + [SHORT] * 5) + "\n"

# Environment that makes Python's locale encoding ASCII, so any open() or pipe
# without an explicit encoding fails on CJK text.
ASCII_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}


class TranscriptCleanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        bindir = self.dir / "bin"
        bindir.mkdir()
        stub = bindir / "claude"
        stub.write_text(STUB)
        stub.chmod(0o755)
        # PATH holds only the stub and system dirs, so a real `claude` elsewhere is unreachable.
        self.log = self.dir / "stub-calls.log"
        self.env = {**os.environ, "PATH": f"{bindir}:/usr/bin:/bin", "STUB_LOG": str(self.log)}
        self.body = self.dir / "body.md"
        self.body.write_text(BODY)
        self.out = self.dir / "clean.md"

    def run_clean(self, mode, *extra):
        env = {**self.env, "STUB_MODE": mode}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--in", str(self.body), "--out", str(self.out),
             "--chunk-words", "500", *extra],
            capture_output=True, text=True, env=env)

    def test_faithful_cleanup_writes_output(self):
        r = self.run_clean("echo")
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)
        self.assertTrue(report["ok"])
        self.assertGreater(len(report["chunks"]), 1)
        self.assertEqual(self.out.read_text().strip(), BODY.strip())
        calls = self.log.read_text().splitlines()
        self.assertEqual(len(calls), len(report["chunks"]))
        self.assertTrue(all(c != str(ROOT) and not c.startswith(str(ROOT) + os.sep) for c in calls))

    def test_truncated_chunk_fails_and_writes_nothing(self):
        r = self.run_clean("truncate")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(json.loads(r.stdout)["ok"])
        self.assertFalse(self.out.exists())

    def test_merged_paragraph_fails_structure_check(self):
        r = self.run_clean("merge")
        self.assertEqual(r.returncode, 2)
        chunk = json.loads(r.stdout)["chunks"][0]
        self.assertTrue(chunk["retention_ok"])
        self.assertFalse(chunk["structure_ok"])
        self.assertFalse(self.out.exists())

    def test_model_failure_exits_1_and_writes_nothing(self):
        r = self.run_clean("fail")
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.out.exists())

    def test_refuses_to_overwrite_as_usage_error_not_check_failure(self):
        self.out.write_text("existing")
        r = self.run_clean("echo")
        self.assertEqual(r.returncode, 1, r.stderr)  # 2 is reserved for a failed fidelity check
        self.assertEqual(self.out.read_text(), "existing")
        self.assertFalse(self.log.exists())

    def test_missing_claude_exits_3_and_writes_nothing(self):
        empty = self.dir / "empty-bin"
        empty.mkdir()
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--in", str(self.body), "--out", str(self.out)],
            capture_output=True, text=True, env={**self.env, "PATH": str(empty)})
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertIn("claude", r.stderr)
        self.assertFalse(self.out.exists())

    def test_check_only_compares_files_without_model(self):
        cleaned = self.dir / "cleaned.md"
        cleaned.write_text(BODY.replace("word0x0", "Word0x0"))
        r = subprocess.run([sys.executable, str(SCRIPT), "--in", str(cleaned), "--check-only", str(self.body)],
                           capture_output=True, text=True, env={**self.env, "PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_injected_preamble_fails_head_check(self):
        r = self.run_clean("preamble")
        self.assertEqual(r.returncode, 2, r.stderr)
        chunk = json.loads(r.stdout)["chunks"][0]
        self.assertFalse(chunk["head_ok"])
        self.assertFalse(self.out.exists())

    def test_cjk_chunk_with_paragraph_dropped_fails(self):
        self.body.write_text(CJK_BODY, encoding="utf-8")
        r = self.run_clean("drop_long")
        self.assertEqual(r.returncode, 2, r.stderr)
        chunk = json.loads(r.stdout)["chunks"][0]
        self.assertTrue(chunk["retention_ok"])  # the word count alone cannot see the loss
        self.assertFalse(chunk["chars_ok"])
        self.assertFalse(self.out.exists())

    def test_cjk_faithful_cleanup_passes_under_ascii_locale(self):
        self.body.write_text(CJK_BODY, encoding="utf-8")
        context = self.dir / "page.txt"
        context.write_text("\u8282\u76ee\u8bf4\u660e", encoding="utf-8")
        env = {**self.env, **ASCII_LOCALE, "STUB_MODE": "echo"}
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--in", str(self.body), "--out", str(self.out),
             "--context", str(context)], capture_output=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        self.assertEqual(self.out.read_text(encoding="utf-8").strip(), CJK_BODY.strip())

    def test_check_only_refuses_a_failing_input(self):
        raw = self.dir / "raw.md"
        raw.write_text(CJK_BODY, encoding="utf-8")
        cleaned = self.dir / "cleaned.md"
        cleaned.write_text("\n\n".join([SHORT] * 4 + [SHORT] * 5) + "\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPT), "--in", str(cleaned), "--check-only", str(raw)],
                           capture_output=True, text=True, env={**self.env, "PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertFalse(json.loads(r.stdout)["ok"])
        self.assertFalse(self.log.exists())

    def test_context_cap_is_reported_when_it_truncates(self):
        context = self.dir / "page.txt"
        context.write_text("divergence list\n" + "x" * 7000)
        r = self.run_clean("echo", "--context", str(context))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("context truncated", r.stderr)
        short = self.dir / "short.txt"
        short.write_text("divergence list\n")
        self.out.unlink()
        r = self.run_clean("echo", "--context", str(short))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("context truncated", r.stderr)


if __name__ == "__main__":
    unittest.main()
