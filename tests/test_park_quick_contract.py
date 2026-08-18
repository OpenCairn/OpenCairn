import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CLAUDE = ROOT / ".claude/commands/park.md"
CODEX = ROOT / "codex/skills/park/SKILL.md"


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
            "run `park-verify.sh` with no `--ident` or `--touched` arguments",
            self.claude,
        )
        self.assertIn(
            'run the verifier through `python3 "$PARK_REVIEW" run-verifier --`',
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


if __name__ == "__main__":
    unittest.main()
