import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

try:
    from session_isolation import isolated_os_environ
except ImportError:  # python -m unittest tests.<module>
    from tests.session_isolation import isolated_os_environ


SCRIPT = Path(__file__).parents[1] / ".claude/scripts/panel-run-record.sh"
SESSION = "fixture0abcdef12"
SID8 = SESSION[:8]
RUNS_REL = "06 Archive/OpenCairn/Panel Runs"
LEDGER_REL = "07 System/Panel Seat Ledger.md"


class PanelRunRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.vault = self.root / "vault"
        self.run = self.root / "run"
        self.home = self.root / "home"
        for d in (self.vault, self.run, self.home):
            d.mkdir()
        self.enterContext(isolated_os_environ(self.root / "state", SESSION))
        # The script reads ~/.gemini and ~/.claude: bind HOME to the fixture.
        os.environ["HOME"] = str(self.home)
        os.environ.pop("VAULT_PATH", None)

    # -- fixture helpers -------------------------------------------------
    def seat(self, name: str, rnd: int = 1, out="findings", secs="100",
             exit_code=None, err=None, model=None) -> None:
        suf = "" if rnd == 1 else f"-r{rnd}"
        if out is not None:
            (self.run / f"{name}{suf}.out").write_text(out, encoding="utf-8")
        if secs is not None:
            (self.run / f"{name}{suf}.time").write_text(f"{secs}\n", encoding="utf-8")
        if exit_code is not None:
            (self.run / f"{name}{suf}.exit").write_text(f"{exit_code}\n", encoding="utf-8")
        if err is not None:
            (self.run / f"{name}{suf}.err").write_text(err, encoding="utf-8")
        if model is not None:
            (self.run / f"{name}{suf}.model").write_text(f"{model}\n", encoding="utf-8")

    def full_round(self, rnd: int = 1, secs="100", tag="A") -> None:
        self.seat("claude", rnd, secs=secs, model=f"claude-{tag}")
        self.seat("gemini", rnd, secs=secs, model=f"gemini-{tag}")
        self.seat("codex", rnd, secs=secs, err=f"model: codex-{tag}\n")
        self.seat("grok", rnd, secs=secs, err=f"grok grok-{tag} 55.2s $0.123\n")
        name = "synthesis.md" if rnd == 1 else f"synthesis-r{rnd}.md"
        (self.run / name).write_text(f"# synthesis round {rnd}\n", encoding="utf-8")

    def record(self, rnd: int = 1, *extra: str, archive=True, vault=True,
               skill="audit") -> subprocess.CompletedProcess:
        cmd = [str(SCRIPT), str(self.run), "--skill", skill, "--round", str(rnd),
               "--target", "fixture target", *extra]
        if vault:
            cmd += ["--vault", str(self.vault)]
        if archive:
            cmd.append("--archive")
        return subprocess.run(cmd, check=False, capture_output=True, text=True,
                              env=os.environ.copy())

    def archives(self) -> list:
        runs = self.vault / RUNS_REL
        return sorted(p for p in runs.iterdir() if p.is_dir()) if runs.is_dir() else []

    def ledger_lines(self) -> list:
        ledger = self.vault / LEDGER_REL
        if not ledger.is_file():
            return []
        return [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]

    @staticmethod
    def field(line: str, name: str) -> str:
        for part in line.split(" | "):
            if part.startswith(name + ":") or part.startswith(name + " "):
                return part.split(" ", 1)[1].split(": ", 1)[-1] if ":" in part[:len(name) + 1] else part[len(name) + 1:]
        raise AssertionError(f"field {name!r} not in line: {line}")

    def transcript(self, agent: str, events) -> Path:
        path = self.home / ".claude/projects/fixture" / SESSION / "subagents" / f"agent-{agent}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for ts in events:
                fh.write(json.dumps({"timestamp": ts, "message": {"role": "assistant", "model": "claude-fixture"}}) + "\n")
        return path

    # -- 1. multi-round archiving ------------------------------------------
    def test_round_two_without_marker_joins_round_one_archive(self) -> None:
        self.full_round(1)
        r1 = self.record(1)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertEqual(len(self.archives()), 1)
        (self.run / ".archive-path").unlink()  # the link to round 1 is lost
        self.full_round(2, secs="200", tag="B")
        r2 = self.record(2)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        dirs = self.archives()
        self.assertEqual([d.name for d in dirs], [d.name for d in dirs if d.name.endswith("-r1")],
                         "round 2 must not create a second archive directory")
        self.assertEqual(len(dirs), 1)
        self.assertTrue((dirs[0] / "claude-r2.out").is_file())
        self.assertTrue((dirs[0] / "claude.out").is_file())
        lines = self.ledger_lines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].endswith(f"evidence: {RUNS_REL}/{dirs[0].name}"), lines[1])

    def test_round_two_recorded_twice_makes_no_duplicate_directory(self) -> None:
        self.full_round(1)
        self.record(1)
        self.full_round(2, secs="200", tag="B")
        (self.run / ".archive-path").unlink()
        a = self.record(2)
        b = self.record(2)
        self.assertEqual((a.returncode, b.returncode), (0, 0), a.stderr + b.stderr)
        self.assertEqual(len(self.archives()), 1, [d.name for d in self.archives()])

    def test_round_line_takes_models_and_wall_from_round_files(self) -> None:
        self.full_round(1, secs="100", tag="A")
        self.record(1)
        self.full_round(2, secs="200", tag="B")
        r2 = self.record(2)
        line = r2.stdout.strip()
        self.assertIn("| round 2 |", line)
        self.assertIn("models: Claude=claude-B Gemini=gemini-B Codex=codex-B Grok=grok-B", line)
        self.assertIn("wall s: Claude 200 Gemini 200 Codex 200 Grok 200", line)

    def test_round_model_files_fall_back_to_round_one(self) -> None:
        self.full_round(1, tag="A")
        self.record(1)
        self.seat("claude", 2, secs="50")
        self.seat("gemini", 2, secs="50")
        self.seat("codex", 2, secs="50", err="")
        (self.run / "synthesis-r2.md").write_text("r2\n", encoding="utf-8")
        line = self.record(2).stdout
        self.assertIn("models: Claude=claude-A Gemini=gemini-A Codex=codex-A", line)
        self.assertIn("wall s: Claude 50 Gemini 50 Codex 50", line)

    def test_claude_transcript_wall_covers_only_the_recorded_round(self) -> None:
        self.transcript("A1", ["2026-10-01T00:00:00Z", "2026-10-01T00:05:00Z"])
        self.seat("claude", 1, secs=None)
        (self.run / "synthesis.md").write_text("r1\n", encoding="utf-8")
        r1 = self.record(1, "--claude-agent", "A1")
        self.assertIn("wall s: Claude 300", r1.stdout, r1.stdout + r1.stderr)
        self.transcript("A1", ["2026-10-01T01:00:00Z", "2026-10-01T01:02:00Z"])
        self.seat("claude", 2, secs=None)
        (self.run / "synthesis-r2.md").write_text("r2\n", encoding="utf-8")
        r2 = self.record(2, "--claude-agent", "A1")
        self.assertIn("wall s: Claude 120", r2.stdout, r2.stdout + r2.stderr)
        self.assertIn("models: Claude=claude-fixture", r2.stdout)


if __name__ == "__main__":
    unittest.main()
