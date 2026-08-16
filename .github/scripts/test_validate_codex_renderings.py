#!/usr/bin/env python3
"""Integration tests for validate_codex_renderings.py."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / ".github" / "scripts" / "validate_codex_renderings.py"
MANIFEST = REPO_ROOT / "codex" / "render-map.json"


class ValidatorIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for entry in manifest["renderings"].values():
            for field in ("source", "render"):
                relative = Path(entry[field])
                destination = self.root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPO_ROOT / relative, destination)
        destination = self.root / "codex" / "render-map.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST, destination)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_validator(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--root", str(self.root), *arguments],
            check=False,
            capture_output=True,
            text=True,
        )

    def assert_fails_with(self, expected: str) -> None:
        result = self.run_validator("--check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(expected, result.stderr)

    def test_valid_repository_passes(self) -> None:
        result = self.run_validator("--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Codex rendering validation passed", result.stdout)

    def test_stale_source_fails(self) -> None:
        source = self.root / ".claude" / "commands" / "morning.md"
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assert_fails_with("STALE morning: source changed")

    def test_unregistered_rendering_fails(self) -> None:
        render = self.root / "codex" / "skills" / "probe-skill" / "SKILL.md"
        render.parent.mkdir(parents=True)
        render.write_text(
            "---\nname: probe-skill\ndescription: Test fixture\n---\n",
            encoding="utf-8",
        )
        self.assert_fails_with(
            "unregistered Codex rendering: codex/skills/probe-skill/SKILL.md"
        )

    def test_malformed_frontmatter_fails(self) -> None:
        render = self.root / "codex" / "skills" / "morning" / "SKILL.md"
        content = render.read_text(encoding="utf-8")
        closing = content.index("---", 4)
        render.write_text(content[:closing] + "metadata: [\n" + content[closing:], encoding="utf-8")
        self.assert_fails_with("structured or block YAML is unsupported")

    def test_duplicate_manifest_identity_fails(self) -> None:
        duplicate = self.root / "codex" / "skills" / "_shared-patterns" / "SKILL.md"
        duplicate.parent.mkdir(parents=True)
        shutil.copy2(self.root / "codex" / "skills" / "audit" / "SKILL.md", duplicate)
        self.assert_fails_with("Codex renderings share manifest name '_shared-patterns'")


if __name__ == "__main__":
    unittest.main()
