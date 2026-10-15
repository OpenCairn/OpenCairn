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
             exit_code=None, err=None, model=None, run: Path = None) -> None:
        run = run or self.run
        suf = "" if rnd == 1 else f"-r{rnd}"
        if out is not None:
            (run / f"{name}{suf}.out").write_text(out, encoding="utf-8")
        if secs is not None:
            (run / f"{name}{suf}.time").write_text(f"{secs}\n", encoding="utf-8")
        if exit_code is not None:
            (run / f"{name}{suf}.exit").write_text(f"{exit_code}\n", encoding="utf-8")
        if err is not None:
            (run / f"{name}{suf}.err").write_text(err, encoding="utf-8")
        if model is not None:
            (run / f"{name}{suf}.model").write_text(f"{model}\n", encoding="utf-8")

    def full_round(self, rnd: int = 1, secs="100", tag="A", run: Path = None) -> None:
        run = run or self.run
        self.seat("claude", rnd, secs=secs, model=f"claude-{tag}", run=run)
        self.seat("gemini", rnd, secs=secs, model=f"gemini-{tag}", run=run)
        self.seat("codex", rnd, secs=secs, err=f"model: codex-{tag}\n", run=run)
        self.seat("grok", rnd, secs=secs, err=f"grok grok-{tag} 55.2s $0.123\n", run=run)
        name = "synthesis.md" if rnd == 1 else f"synthesis-r{rnd}.md"
        (run / name).write_text(f"# synthesis round {rnd}\n", encoding="utf-8")

    def record(self, rnd: int = 1, *extra: str, archive=True, vault=True,
               skill="audit", run: Path = None) -> subprocess.CompletedProcess:
        cmd = [str(SCRIPT), str(run or self.run), "--skill", skill, "--round", str(rnd),
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
        (self.run / "brief.md").write_text("brief A\n", encoding="utf-8")  # a run's identity for lost-marker recovery
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

    def other_review(self, name: str, brief: str) -> Path:
        """A second review of the same session: its own run dir with a round-1 archive."""
        run = self.root / name
        run.mkdir()
        (run / "brief.md").write_text(brief, encoding="utf-8")
        self.full_round(1, run=run)
        r = self.record(1, run=run)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return run

    def test_lost_marker_joins_only_the_archive_whose_round_one_matches(self) -> None:
        (self.run / "brief.md").write_text("brief A\n", encoding="utf-8")
        self.full_round(1)
        self.assertEqual(self.record(1).returncode, 0)
        self.other_review("runB", "brief B\n")
        self.assertEqual(len(self.archives()), 2)
        (self.run / ".archive-path").unlink()
        self.full_round(2, secs="200", tag="B")
        r2 = self.record(2)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        dirs = self.archives()
        self.assertEqual(len(dirs), 2, [d.name for d in dirs])
        a = [d for d in dirs if (d / "brief.md").read_text(encoding="utf-8") == "brief A\n"]
        b = [d for d in dirs if (d / "brief.md").read_text(encoding="utf-8") == "brief B\n"]
        self.assertEqual((len(a), len(b)), (1, 1))
        self.assertTrue((a[0] / "claude-r2.out").is_file(), sorted(p.name for p in a[0].iterdir()))
        self.assertFalse((b[0] / "claude-r2.out").exists(), "round 2 of A must never land in B's archive")
        self.assertTrue(self.ledger_lines()[-1].endswith(f"evidence: {RUNS_REL}/{a[0].name}"))

    def test_lost_marker_without_a_matching_round_one_archives_the_round_whole(self) -> None:
        self.other_review("runB", "brief B\n")
        (self.run / "brief.md").write_text("brief C\n", encoding="utf-8")
        self.full_round(1)
        self.assertEqual(self.record(1, archive=False).returncode, 0)  # round 1 never archived
        self.full_round(2, tag="C")
        r2 = self.record(2)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        dirs = self.archives()
        self.assertEqual(len(dirs), 2, [d.name for d in dirs])
        new = [d for d in dirs if d.name.endswith("-r2")]
        self.assertEqual(len(new), 1, [d.name for d in dirs])
        self.assertTrue((new[0] / "claude-r2.out").is_file())
        self.assertTrue((new[0] / "brief.md").is_file())
        self.assertIn("note: no round-1 archive of this session matches this run directory's brief.md; "
                      f"round 2 archived whole to {RUNS_REL}/{new[0].name}", r2.stderr)

    def test_lost_marker_without_a_brief_never_joins_on_synthesis_alone(self) -> None:
        # Identity is brief.md; an identical short synthesis is not evidence of
        # the same review, so a run that lost its brief archives separately.
        self.other_review("runB", "brief B\n")
        self.full_round(1)
        self.assertEqual(self.record(1, archive=False).returncode, 0)
        (self.run / "brief.md").unlink(missing_ok=True)
        (self.run / "synthesis.md").write_text("CLEAR\n", encoding="utf-8")
        for d in self.archives():
            (d / "synthesis.md").write_text("CLEAR\n", encoding="utf-8")
        self.full_round(2, tag="C")
        (self.run / "synthesis-r2.md").write_text("round 2\n", encoding="utf-8")
        r2 = self.record(2)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        dirs = self.archives()
        self.assertEqual(len(dirs), 2, [d.name for d in dirs])
        self.assertTrue(any(d.name.endswith("-r2") for d in dirs), [d.name for d in dirs])
        self.assertIn("note: run directory has no brief.md; round 2 archived whole to", r2.stderr)
        self.assertNotIn("matches this run directory's brief.md", r2.stderr)

    def test_whole_directory_fallback_archives_the_stand_in_synthesis_under_round_name(self) -> None:
        # No synthesis-r2.md: a fresh synthesis.md stands in, and the whole-directory
        # fallback must still archive it under round 2's name.
        self.other_review("runB", "brief B\n")
        (self.run / "brief.md").write_text("brief C\n", encoding="utf-8")
        self.full_round(1)
        self.assertEqual(self.record(1, archive=False).returncode, 0)
        self.full_round(2, tag="C")
        (self.run / "synthesis-r2.md").unlink()
        (self.run / "synthesis.md").write_text("round 2 verdict\n", encoding="utf-8")
        now = time.time()
        os.utime(self.run / "codex-r2.out", (now - 600, now - 600))
        os.utime(self.run / "synthesis.md", (now, now))
        r2 = self.record(2)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        new = [d for d in self.archives() if d.name.endswith("-r2")]
        self.assertEqual(len(new), 1)
        self.assertEqual((new[0] / "synthesis-r2.md").read_text(encoding="utf-8"), "round 2 verdict\n",
                         sorted(p.name for p in new[0].iterdir()))
        self.assertIn("| synthesis: yes |", r2.stdout)
        self.assertIn("synthesis.md taken as round 2's synthesis", r2.stderr)

    def test_round_two_with_no_seat_output_never_takes_the_stand_in(self) -> None:
        # Zero *-r2.out files: nothing for synthesis.md to be newer than, so it is not round 2's.
        self.full_round(1)
        self.record(1)
        self.full_round(2, tag="B")
        (self.run / "synthesis-r2.md").unlink()
        for p in self.run.glob("*-r2.out"):
            p.unlink()
        now = time.time()
        os.utime(self.run / "synthesis.md", (now, now))
        r = self.record(2)
        self.assertIn("| synthesis: no |", r.stdout)
        self.assertNotIn("taken as round 2's synthesis", r.stderr)
        archive = self.archives()[0]
        self.assertFalse((archive / "synthesis-r2.md").exists(), sorted(p.name for p in archive.iterdir()))

    def test_lost_marker_with_two_matching_archives_fails_explicitly(self) -> None:
        (self.run / "brief.md").write_text("brief A\n", encoding="utf-8")
        self.full_round(1)
        self.assertEqual(self.record(1).returncode, 0)
        self.assertEqual(self.record(1).returncode, 0)  # round 1 recorded twice: two identical archives
        self.assertEqual(len(self.archives()), 2)
        (self.run / ".archive-path").unlink()
        self.full_round(2, tag="B")
        r2 = self.record(2)
        self.assertEqual(r2.returncode, 1, r2.stdout + r2.stderr)
        self.assertIn("error: ambiguous archive recovery", r2.stderr)
        dirs = self.archives()
        self.assertEqual(len(dirs), 2, [d.name for d in dirs])
        for d in dirs:
            self.assertFalse((d / "claude-r2.out").exists(), d.name)

    def test_round_join_copies_per_reviewer_round_briefs(self) -> None:
        # Cross-examination writes brief-rN-<reviewer>.md: a round file with a
        # suffix after the round tag, not a .ext directly after it.
        self.full_round(1)
        self.record(1)
        self.full_round(2, tag="B")
        (self.run / "brief-r2-gemini.md").write_text("cross-examination brief\n", encoding="utf-8")
        r = self.record(2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        archive = self.archives()[0]
        self.assertEqual(len(self.archives()), 1)
        self.assertEqual((archive / "brief-r2-gemini.md").read_text(encoding="utf-8"), "cross-examination brief\n")
        self.assertTrue((archive / "codex-r2.out").is_file())

    def test_round_two_recorded_twice_makes_no_duplicate_directory(self) -> None:
        (self.run / "brief.md").write_text("brief A\n", encoding="utf-8")  # a run's identity for lost-marker recovery
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

    # -- 2. missing seat output -----------------------------------------
    def test_despatched_seat_without_output_is_warned_not_counted(self) -> None:
        self.full_round(1)
        (self.run / "grok.out").unlink()
        self.seat("codex", 1, out="", err="model: codex-A\n")
        r = self.record(1)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("despatched: Claude Gemini Codex Grok | returned: Claude Gemini |", r.stdout)
        self.assertIn("warning: Codex seat despatched, not returned (codex.out empty)", r.stderr)
        self.assertIn("warning: Grok seat despatched, not returned (grok.out missing)", r.stderr)

    def test_round_two_missing_output_names_the_round_file(self) -> None:
        self.full_round(1)
        self.record(1)
        self.full_round(2, tag="B")
        (self.run / "claude-r2.out").unlink()
        r = self.record(2)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("returned: Gemini Codex Grok |", r.stdout)
        self.assertIn("warning: Claude seat despatched, not returned (claude-r2.out missing)", r.stderr)

    def test_claude_agent_flag_counts_the_seat_as_despatched_even_without_files(self) -> None:
        # A Claude seat despatched via --claude-agent that never wrote claude.out
        # (and no .err/.time/.exit/.json either) is still a despatched seat.
        self.seat("gemini", 1, model="gemini-A")
        (self.run / "synthesis.md").write_text("r1\n", encoding="utf-8")
        r = self.record(1, "--claude-agent", "x", archive=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("despatched: Claude Gemini | returned: Gemini |", r.stdout)
        self.assertIn("warning: Claude seat despatched, not returned (claude.out missing)", r.stderr)
        self.assertEqual(len(self.ledger_lines()), 1, "the line is still written")

    def test_claude_model_flag_counts_the_seat_as_despatched_even_without_files(self) -> None:
        self.seat("gemini", 1, model="gemini-A")
        (self.run / "synthesis.md").write_text("r1\n", encoding="utf-8")
        r = self.record(1, "--claude-model", "claude-x", archive=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("despatched: Claude Gemini | returned: Gemini |", r.stdout)
        self.assertIn("models: Claude=claude-x Gemini=gemini-A", r.stdout)
        self.assertIn("warning: Claude seat despatched, not returned (claude.out missing)", r.stderr)

    def test_no_seat_returned_still_records_and_exits_two(self) -> None:
        self.full_round(1)
        for seat in ("claude", "gemini", "codex", "grok"):
            (self.run / f"{seat}.out").unlink()
        r = self.record(1)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("returned: none |", r.stdout)
        self.assertIn("error: no seat returned for round 1", r.stderr)
        self.assertEqual(len(self.ledger_lines()), 1, "the failed run is still indexed")
        self.assertEqual(len(self.archives()), 1)

    def test_nonzero_exit_file_is_reported(self) -> None:
        self.full_round(1)
        self.seat("gemini", 1, exit_code=1)
        r = self.record(1)
        self.assertIn("warning: Gemini seat despatched, not returned (gemini.exit 1)", r.stderr)
        self.assertIn("returned: Claude Codex Grok |", r.stdout)

    # -- 3. synthesis naming -------------------------------------------
    def test_archived_synthesis_keeps_md_extension(self) -> None:
        self.full_round(1)
        (self.run / "brief.md").write_text("brief\n", encoding="utf-8")
        r = self.record(1)
        self.assertEqual(r.returncode, 0, r.stderr)
        archive = self.archives()[0]
        self.assertTrue((archive / "synthesis.md").is_file(), sorted(p.name for p in archive.iterdir()))
        self.assertFalse((archive / "synthesis.txt").exists())
        self.assertTrue((archive / "brief.md").is_file())
        self.assertIn("| synthesis: yes |", r.stdout)

    def test_round_two_archives_its_own_synthesis(self) -> None:
        self.full_round(1)
        self.record(1)
        self.full_round(2, tag="B")
        r = self.record(2)
        archive = self.archives()[0]
        self.assertEqual((archive / "synthesis-r2.md").read_text(encoding="utf-8"), "# synthesis round 2\n")
        self.assertEqual((archive / "synthesis.md").read_text(encoding="utf-8"), "# synthesis round 1\n")
        self.assertIn("| synthesis: yes |", r.stdout)
        self.assertNotIn("warning: no synthesis", r.stderr)

    def test_round_two_without_own_synthesis_archives_synthesis_md_as_round_file(self) -> None:
        self.full_round(1)
        self.record(1)
        self.full_round(2, tag="B")
        (self.run / "synthesis-r2.md").unlink()
        (self.run / "synthesis.md").write_text("# rewritten for round 2\n", encoding="utf-8")
        now = time.time()
        os.utime(self.run / "synthesis.md", (now + 1, now + 1))  # written after the round's seat outputs
        r = self.record(2)
        archive = self.archives()[0]
        self.assertEqual((archive / "synthesis-r2.md").read_text(encoding="utf-8"), "# rewritten for round 2\n")
        self.assertEqual((archive / "synthesis.md").read_text(encoding="utf-8"), "# synthesis round 1\n",
                         "the archived round-1 synthesis is never overwritten")
        self.assertIn("warning: no synthesis-r2.md in", r.stderr)
        self.assertIn("synthesis.md taken as round 2's synthesis", r.stderr)

    def test_round_two_fallback_rejects_a_synthesis_md_older_than_the_round_outputs(self) -> None:
        # Round 1's synthesis.md, untouched since, is not round 2's synthesis.
        self.full_round(1)
        self.record(1)
        self.full_round(2, tag="B")
        (self.run / "synthesis-r2.md").unlink()
        now = time.time()
        os.utime(self.run / "synthesis.md", (now - 600, now - 600))
        os.utime(self.run / "codex-r2.out", (now, now))
        r = self.record(2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| synthesis: no |", r.stdout)
        self.assertIn("warning: no synthesis for round 2 in", r.stderr)
        self.assertNotIn("taken as round 2's synthesis", r.stderr)
        archive = self.archives()[0]
        self.assertFalse((archive / "synthesis-r2.md").exists(), sorted(p.name for p in archive.iterdir()))
        self.assertEqual((archive / "synthesis.md").read_text(encoding="utf-8"), "# synthesis round 1\n")
        self.assertTrue((archive / "codex-r2.out").is_file())

    def test_round_two_fallback_accepts_a_synthesis_md_newer_than_every_round_output(self) -> None:
        self.full_round(1)
        self.record(1)
        self.full_round(2, tag="B")
        (self.run / "synthesis-r2.md").unlink()
        (self.run / "synthesis.md").write_text("# rewritten for round 2\n", encoding="utf-8")
        now = time.time()
        for seat in ("claude", "gemini", "codex", "grok"):
            os.utime(self.run / f"{seat}-r2.out", (now - 60, now - 60))
        os.utime(self.run / "synthesis.md", (now, now))
        r = self.record(2)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| synthesis: yes |", r.stdout)
        self.assertIn("synthesis.md taken as round 2's synthesis", r.stderr)
        archive = self.archives()[0]
        self.assertEqual((archive / "synthesis-r2.md").read_text(encoding="utf-8"), "# rewritten for round 2\n")
        self.assertEqual((archive / "synthesis.md").read_text(encoding="utf-8"), "# synthesis round 1\n")

    def test_round_without_any_synthesis_is_warned_and_recorded_no(self) -> None:
        self.full_round(1)
        self.record(1)
        self.full_round(2, tag="B")
        (self.run / "synthesis-r2.md").unlink()
        (self.run / "synthesis.md").unlink()
        r = self.record(2)
        self.assertIn("| synthesis: no |", r.stdout)
        self.assertIn("warning: no synthesis for round 2 in", r.stderr)

    # -- 4. locking -------------------------------------------------------
    def test_archive_copy_waits_for_the_panel_runs_lock(self) -> None:
        self.full_round(1)
        runs = self.vault / RUNS_REL
        runs.mkdir(parents=True)
        lock = runs.parent / ".Panel Runs.lock"
        holder = subprocess.Popen(["flock", str(lock), "sleep", "2"])
        self.addCleanup(holder.wait)
        time.sleep(0.3)  # let the holder take the lock
        started = time.monotonic()
        r = self.record(1)
        elapsed = time.monotonic() - started
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertGreaterEqual(elapsed, 1.5, "the archive copy ran while another writer held the lock")
        self.assertEqual(len(self.archives()), 1)

    def test_ledger_append_goes_through_locked_edit(self) -> None:
        self.full_round(1)
        self.record(1)
        state = self.root / "state/.session-state" / f"{SESSION}.tsv"
        rows = [row.split("\t") for row in state.read_text(encoding="utf-8").splitlines()]
        ledger = str(self.vault / LEDGER_REL)
        self.assertTrue(any(row[1] == "locked-edit" and row[2] == ledger for row in rows), rows)

    # -- 5. the ledger line is the record; --archive only adds the copy ----
    def test_vault_without_archive_writes_the_ledger_line(self) -> None:
        self.full_round(1)
        r = self.record(1, archive=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = self.ledger_lines()
        self.assertEqual(len(lines), 1, (self.vault / LEDGER_REL).exists())
        self.assertTrue(lines[0].endswith(f"evidence: {self.run}"), lines[0])
        self.assertEqual(lines[0], r.stdout.strip())
        self.assertEqual(self.archives(), [])
        self.assertNotIn("NOT WRITTEN", r.stderr)

    def test_no_vault_prints_the_line_and_says_the_ledger_is_not_written(self) -> None:
        self.full_round(1)
        r = self.record(1, archive=False, vault=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("- "), r.stdout)
        self.assertIn("warning: ledger NOT WRITTEN (no vault: pass --vault or set VAULT_PATH)", r.stderr)
        self.assertFalse((self.vault / LEDGER_REL).exists())

    def test_help_prints_the_header_only(self) -> None:
        r = subprocess.run([str(SCRIPT), "--help"], check=False, capture_output=True, text=True,
                           env=os.environ.copy())
        self.assertEqual(r.returncode, 0)
        self.assertIn("What is written, when", r.stdout)
        self.assertNotIn("set -euo pipefail", r.stdout)
        self.assertTrue(r.stdout.rstrip().endswith("Needs python3."), r.stdout[-200:])


if __name__ == "__main__":
    unittest.main()
