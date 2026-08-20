import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CLAUDE = ROOT / ".claude/commands/park.md"
CODEX = ROOT / "codex/skills/park/SKILL.md"
PARK_REVIEW = ROOT / "codex/skills/park/scripts/park-review.py"
PARK_VERIFY = ROOT / ".claude/scripts/park-verify.sh"


class ParkQuickContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.claude = CLAUDE.read_text(encoding="utf-8")
        cls.codex = CODEX.read_text(encoding="utf-8")

    def test_exact_activation_and_default_full_are_mirrored(self) -> None:
        for text in (self.claude, self.codex):
            self.assertIn(
                "Quick mode activates only when the complete argument string is exactly `--quick`",
                text,
            )
            self.assertIn("including `--quick foo`, run the full protocol", text)
            self.assertIn("Never infer quick mode from a quiet-looking session", text)

        self.assertIn('argument-hint: "[--quick]"', self.claude)
        self.assertIn("**Args:** `/park --quick`", self.claude)
        self.assertIn("**Args:** `$park --quick`", self.codex)

    def test_fail_closed_gate_and_merge_escalation_are_mirrored(self) -> None:
        for text in (self.claude, self.codex):
            self.assertIn("#### Explicit `--quick` gate", text)
            self.assertIn("actual tool calls and shell commands", text)
            self.assertIn("Nil must be a checked result, never a default", text)
            self.assertIn(
                "↪ --quick escalated to full park: merge-continuation", text
            )
            self.assertIn("This second inventory—not `park-verify.sh`—detects late files", text)
            self.assertIn("late deleted paths", text)

    def test_quick_verification_and_completion_are_lane_specific(self) -> None:
        self.assertIn(
            'run `"{VAULT}/.claude/scripts/park-verify.sh" "{VAULT}" "$SESSION_LOG" N`',
            self.claude,
        )
        self.assertIn(
            'run the verifier through `python3 "$PARK_REVIEW" run-verifier -- '
            '"{VAULT}/.claude/scripts/park-verify.sh" "{VAULT}" "$SESSION_LOG" N`',
            self.codex,
        )
        self.assertIn(
            "Branch past propagation capture, `build`, reviewer despatch, and `record-audit`",
            self.codex,
        )
        for text in (self.claude, self.codex):
            self.assertIn("✓ Audit: skipped (--quick)", text)
            self.assertIn("Quick parked.", text)
            self.assertIn("### 12. Full-path completion message", text)

    def test_codex_quick_verifier_wrapper_executes_complete_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            (vault / "01 Now").mkdir(parents=True)
            (vault / "01 Now/This Week.md").write_text("# This Week\n", encoding="utf-8")
            (vault / "01 Now/Tickler.md").write_text("# Tickler\n", encoding="utf-8")
            log = vault / "06 Archive/OpenCairn/Session Logs/2026-08-19.md"
            log.parent.mkdir(parents=True)
            log.write_text(
                "\n".join(
                    [
                        "## Session 1 - Read-only discussion",
                        "### Summary",
                        "Discussion completed without durable changes.",
                        "### Key Insights / Decisions",
                        "None",
                        "### Next Steps / Open Loops",
                        "None — work completed",
                        "### Files Created",
                        "None",
                        "### Files Updated",
                        "None",
                        "### Files Deleted",
                        "None",
                        "### Pickup Context",
                        "**For next session:** None — work completed",
                        "**Project:** None",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["CLAUDE_CONFIG_DIR"] = str(root / "config")
            env["OPENCAIRN_SESSION_ID"] = "park-quick-wrapper-test"

            result = subprocess.run(
                [
                    "python3",
                    str(PARK_REVIEW),
                    "run-verifier",
                    "--",
                    str(PARK_VERIFY),
                    str(vault),
                    str(log),
                    "1",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RESULT: PASS", result.stdout)
            self.assertIn("Verifier receipt:", result.stderr)

    def test_acceptance_scenarios_have_explicit_branch_observables(self) -> None:
        markers = {
            "read-only success": "✓ Quick eligibility: PASS",
            "durable file edit": "Any attributed creation, update, or deletion fails the gate",
            "external action": "external mutations (messages sent, bookings, purchases, pushes, remote edits)",
            "conversation-only draft": "assistant-authored drafts that exist only in the conversation",
            "open loop": "resumable next steps or open loops",
            "merge continuation": "merge-continuation",
            "ambiguous attribution": "target or ownership is uncertain",
            "late creation or update": "late created or updated artefact",
            "late deletion": "late deleted paths",
            "single session-log mutation": "never rerun Step 3",
            "quick agent count": "do not enter the remaining full-path steps",
        }
        for lane, text in (("claude", self.claude), ("codex", self.codex)):
            for scenario, marker in markers.items():
                with self.subTest(lane=lane, scenario=scenario):
                    self.assertIn(marker, text)

    def test_proportional_artefact_policy_is_mirrored(self) -> None:
        for lane, text in (("claude", self.claude), ("codex", self.codex)):
            with self.subTest(lane=lane):
                self.assertIn("Large semantic artefact", text)
                self.assertIn("Local reference artefact", text)
                self.assertIn("index, not evidence every page", text)
                self.assertNotIn("Read each edited file IN FULL", text)

        self.assertIn("park-artifact.py", self.claude)
        self.assertIn(".session-state/.park-artifacts", self.claude)
        self.assertIn("--reference", self.codex)
        self.assertIn("--targeted --inspection-target", self.codex)
        self.assertIn("cross-session/cross-lane `.park-artifacts` cache", self.codex)


if __name__ == "__main__":
    unittest.main()
