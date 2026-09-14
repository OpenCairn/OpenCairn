"""Structural contracts for the split shared-rule library and its consumers."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCOPES = {
    "_shared-rules-planning.md": {2, 3, 4, 9, 18},
    "_shared-rules-reviewer.md": {10, 16, 20, 23},
    "_shared-rules-content.md": {14, 15, 24, 26},
}
OWNERS = {number: name for name, numbers in SCOPES.items() for number in numbers}
CORE = "_shared-rules.md"
DIRECT_REFERENCE = re.compile(
    r"(_shared-rules(?:-(?:planning|reviewer|content))?\.md)"
    r"`?\*{0,2}\s*(?:§|Section\s+)(\d+)"
)


def sections(text):
    headings = list(re.finditer(r"^## (\d+)\. .+$", text, re.M))
    numbers = [int(match[1]) for match in headings]
    if len(numbers) != len(set(numbers)):
        raise ValueError("Duplicate shared-rule section number")
    return {
        int(match[1]): text[
            match.start():headings[index + 1].start()
            if index + 1 < len(headings) else len(text)
        ].strip()
        for index, match in enumerate(headings)
    }


class SharedRuleRoutesTests(unittest.TestCase):
    def test_section_ownership_and_legacy_forwarding(self):
        for relative in (".claude/commands", "codex/skills"):
            with self.subTest(tree=relative):
                directory = ROOT / relative
                library = {
                    name: sections((directory / name).read_text(encoding="utf-8"))
                    for name in (CORE, *SCOPES)
                }
                self.assertEqual(set(library[CORE]), set(range(1, 27)))
                for name, expected in SCOPES.items():
                    self.assertEqual(set(library[name]), expected)
                for number in range(1, 27):
                    owner = OWNERS.get(number, CORE)
                    actual = library[owner][number]
                    self.assertFalse(actual.splitlines()[2].startswith("Moved to "))
                    if owner != CORE:
                        forwarding = library[CORE][number]
                        self.assertIn(f"]({owner})", forwarding)
                        self.assertTrue(forwarding.splitlines()[2].startswith("Moved to "))

    def test_explicit_consumer_references_resolve(self):
        checked = 0
        for relative in (".claude/commands", "codex/skills"):
            directory = ROOT / relative
            library = {
                name: sections((directory / name).read_text(encoding="utf-8"))
                for name in (CORE, *SCOPES)
            }
            for path in directory.rglob("*.md"):
                text = path.read_text(encoding="utf-8")
                for match in DIRECT_REFERENCE.finditer(text):
                    checked += 1
                    self.assertIn(int(match[2]), library[match[1]], f"{path}: {match[0]}")
                for target in re.findall(r"\]\(([^)\s]*_shared-rules[^)\s]*\.md)\)", text):
                    self.assertTrue((path.parent / target).is_file(), f"{path}: {target}")
        self.assertGreater(checked, 0, "Reference scan did not inspect any consumers")

    def test_split_does_not_duplicate_transcript_or_panel_body_in_core(self):
        for relative in (".claude/commands", "codex/skills"):
            directory = ROOT / relative
            core = sections((directory / CORE).read_text(encoding="utf-8"))
            for number, owner in OWNERS.items():
                body = sections((directory / owner).read_text(encoding="utf-8"))[number]
                self.assertLess(len(core[number]), len(body))


if __name__ == "__main__":
    unittest.main()
