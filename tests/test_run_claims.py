import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / ".claude/scripts/run-claims.py"
NOW = "2026-11-03T02:00:00+10:00"
NO_FCNTL = (
    "import runpy, sys; sys.modules['fcntl'] = None; sys.argv = sys.argv[1:]; "
    "runpy.run_path(sys.argv[0], run_name='__main__')"
)


class RunClaimsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry = self.root / "state/runs/registry.jsonl"
        self.queue = self.root / "vault/03 Projects/Work Queue.md"
        self.queue.parent.mkdir(parents=True)
        self.queue.write_text("queue\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_claims(self, *args: str, no_fcntl: bool = False) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["OPENCAIRN_RUN_REGISTRY"] = str(self.registry)
        command = ["python3", str(SCRIPT), *args]
        if no_fcntl:  # simulate native Windows, which has no fcntl module
            command = ["python3", "-c", NO_FCNTL, str(SCRIPT), *args]
        return subprocess.run(command, env=env, capture_output=True, text=True, check=False)

    def write_rows(self, *rows: dict) -> None:
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        self.registry.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def check(self, *extra: str) -> subprocess.CompletedProcess:
        return self.run_claims("check", "--now", NOW, *extra, str(self.queue))

    def test_missing_registry_means_free(self) -> None:
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("free:", result.stdout)
        self.assertIn("(not configured): nothing is claimed", result.stdout)

    def test_live_claim_on_file_or_parent_directory_blocks(self) -> None:
        for claim in (self.queue, self.queue.parent):
            with self.subTest(claim=claim):
                self.write_rows({"run_id": "opencairn-20261103", "owner": "s1",
                    "claims": [str(claim)], "ends_at": "2026-11-03T10:00:00+10:00"})
                result = self.check()
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                self.assertIn("claimed by opencairn-20261103 (owner s1", result.stdout)

    def test_expired_released_self_and_unrelated_claims_are_free(self) -> None:
        cases = {
            "expired": [{"run_id": "r", "claims": [str(self.queue)], "ends_at": "2026-11-03T01:00:00+10:00"}],
            "released": [{"run_id": "r", "claims": [str(self.queue)], "ends_at": "2026-11-03T10:00:00+10:00"},
                         {"run_id": "r", "claims": [], "released": True}],
            "unrelated": [{"run_id": "r", "claims": [str(self.root / "vault/other.md")],
                           "ends_at": "2026-11-03T10:00:00+10:00"}],
            "sibling-prefix": [{"run_id": "r", "claims": [str(self.queue) + ".bak"],
                                "ends_at": "2026-11-03T10:00:00+10:00"}],
        }
        for name, rows in cases.items():
            with self.subTest(case=name):
                self.write_rows(*rows)
                result = self.check()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.write_rows({"run_id": "me", "claims": [str(self.queue)], "ends_at": "2026-11-03T10:00:00+10:00"})
        self.assertEqual(self.check("--self", "me").returncode, 0)

    def test_directory_target_is_claimed_by_a_claim_beneath_it(self) -> None:
        self.write_rows({"run_id": "r", "claims": [str(self.queue)], "ends_at": "2026-11-03T10:00:00+10:00"})
        for target in (self.queue.parent, self.root / "vault"):
            with self.subTest(target=target):
                result = self.run_claims("check", "--now", NOW, str(target))
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                self.assertIn("claimed by r", result.stdout)
        # A sibling directory that only shares a name prefix stays free.
        sibling = self.root / "vault/03 Proj"
        sibling.mkdir()
        self.assertEqual(self.run_claims("check", "--now", NOW, str(sibling)).returncode, 0)

    def test_claim_without_end_time_stays_live(self) -> None:
        self.write_rows({"run_id": "r", "claims": [str(self.queue)]})
        result = self.check()
        self.assertEqual(result.returncode, 3)
        self.assertIn("no end time", result.stdout)

    def test_malformed_registry_fails_closed(self) -> None:
        live = "2026-11-03T10:00:00+10:00"
        cases = {
            "claims-not-a-list": {"run_id": "r", "claims": "not-a-list"},
            # A string "false" is truthy: read loosely it would release the claim.
            "released-not-bool": {"run_id": "r", "claims": [str(self.queue)], "ends_at": live,
                                  "released": "false"},
            "relative-claim": {"run_id": "r", "claims": ["vault/03 Projects"], "ends_at": live},
            # An empty claim would normalise to the current directory.
            "empty-claim": {"run_id": "r", "claims": [""], "ends_at": live},
        }
        for name, row in cases.items():
            with self.subTest(case=name):
                self.write_rows(row)
                result = self.check()
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("registry unreadable", result.stderr)

    def test_register_then_release_round_trip(self) -> None:
        reg = self.run_claims("register", "--run-id", "r1", "--owner", "s1",
            "--ends-at", "2099-01-01T00:00:00+10:00", "--claim", str(self.queue))
        self.assertEqual(reg.returncode, 0, reg.stderr)
        self.assertEqual(self.run_claims("check", str(self.queue)).returncode, 3)
        self.assertEqual(self.run_claims("release", "--run-id", "r1").returncode, 0)
        self.assertEqual(self.run_claims("check", str(self.queue)).returncode, 0)
        bad = self.run_claims("register", "--run-id", "r2", "--owner", "s",
            "--ends-at", "tomorrow", "--claim", str(self.queue))
        self.assertEqual(bad.returncode, 2)

    def test_check_works_without_fcntl_and_writes_fail_closed(self) -> None:
        self.write_rows({"run_id": "r", "claims": [str(self.queue)], "ends_at": "2026-11-03T10:00:00+10:00"})
        before = self.registry.read_text(encoding="utf-8")
        result = self.run_claims("check", "--now", NOW, str(self.queue), no_fcntl=True)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        for args in (("register", "--run-id", "r2", "--owner", "s", "--ends-at",
                      "2099-01-01T00:00:00+10:00", "--claim", str(self.queue)),
                     ("release", "--run-id", "r")):
            with self.subTest(command=args[0]):
                result = self.run_claims(*args, no_fcntl=True)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("file locking", result.stderr)
        self.assertEqual(self.registry.read_text(encoding="utf-8"), before)

    def test_weekly_hygiene_step_15_gates_writes_on_claims(self) -> None:
        for rel in (".claude/commands/weekly-hygiene.md", "codex/skills/weekly-hygiene/SKILL.md"):
            with self.subTest(render=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                step = text.split("15. **Skill-Monitor Log Processing**", 1)[1].split("16. **Write Hygiene Report**", 1)[0]
                self.assertIn('.claude/scripts/run-claims.py" check', step)
                self.assertIn("skipped: claimed by <run>", step)


if __name__ == "__main__":
    unittest.main()
