import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class CloseoutCoverageFindingTests(unittest.TestCase):
    def test_coverage_finding_needs_a_cited_rerun_search(self) -> None:
        for rel in (".claude/commands/_closeout.md", "codex/skills/_closeout.md"):
            with self.subTest(render=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn("**A coverage finding is closed by a re-run search, not by rewording.**", text)
                self.assertIn("would have caught the miss the finding names", text)
                self.assertIn("cite its argv and output", text)


class ReviewerDigestContractTests(unittest.TestCase):
    def test_shell_denied_reviewer_is_not_asked_to_verify_digests(self) -> None:
        text = (ROOT / ".claude/commands/_closeout.md").read_text(encoding="utf-8")
        review = text.split("\n## Independent review\n", 1)[1].split("\n## Completion evidence\n", 1)[0]
        self.assertIn("adding the digest only for a shell-capable seat to verify", review)
        self.assertIn("a shell-capable reviewer verifies it, while a shell-denied reviewer only reads the declared targets", review)
        self.assertIn("states once that it read the supplied paths, neither verifies nor attests digests", review)
        self.assertNotIn("raw digest output for a shell-denied seat", review)
        # The parent's own byte check is the protection and stays.
        self.assertIn("calculate its SHA-256 and pass its absolute path", review)
        self.assertIn("the parent checks that the brief and reviewed files still match the reviewed bytes", review)
        # That check needs a recorded baseline, so the parent hashes for every seat; only verification is scoped.
        self.assertIn("Include raw hash commands/output (the parent's baseline for the after-review byte check) "
                      "and declare whether the seat has shell; only a shell-capable seat verifies them.", review)
        self.assertIn("The parent supplies raw hash output for immutable sources/review copies;", review)
        self.assertNotIn("include raw hash commands/output only for a shell-capable seat", review)
        self.assertIn("`Brief SHA-256: <digest>`", text)


if __name__ == "__main__":
    unittest.main()
