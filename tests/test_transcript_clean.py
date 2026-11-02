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
chunk = sys.stdin.read().split("\nChunk:\n", 1)[1]
mode = os.environ.get("STUB_MODE", "echo")
if mode == "truncate":
    chunk = chunk[: len(chunk) // 2]
elif mode == "merge":
    paras = chunk.split("\n\n")
    paras[1] = paras[1] + " " + paras.pop(2).split(":** ", 1)[1]
    chunk = "\n\n".join(paras)
elif mode == "fail":
    print(json.dumps({"is_error": True, "result": "boom"})); sys.exit(1)
print(json.dumps({"result": chunk, "usage": {}, "modelUsage": {"stub": {}}}))
'''


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


if __name__ == "__main__":
    unittest.main()
