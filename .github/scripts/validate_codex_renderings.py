#!/usr/bin/env python3
"""Validate acknowledged Claude-to-Codex rendering pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath


MANIFEST_PATH = PurePosixPath("codex/render-map.json")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
NAME_RE = re.compile(r"^_?[a-z0-9]+(?:[-_][a-z0-9]+)*$")
ENTRY_FIELDS = {"source", "render", "source_sha256", "render_sha256"}
FRONTMATTER_FIELD_RE = re.compile(r"^([A-Za-z0-9_-]+):[ \t]*(.*)$")
UNSUPPORTED_SCALAR_PREFIXES = ("[", "{", "|", ">", "&", "*", "!")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or acknowledge OpenCairn's Claude-to-Codex renderings."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root (defaults to the root containing this script)",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="validate without writing")
    action.add_argument(
        "--acknowledge",
        nargs="+",
        metavar="NAME",
        help="record current hashes after reviewing the named rendering pairs",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_repo_path(root: Path, raw: object, label: str, errors: list[str]) -> Path | None:
    if not isinstance(raw, str) or not raw:
        errors.append(f"{label}: expected a non-empty relative path")
        return None

    relative = PurePosixPath(raw)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label}: path must stay inside the repository: {raw!r}")
        return None

    path = (root / Path(*relative.parts)).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        errors.append(f"{label}: path resolves outside the repository: {raw!r}")
        return None
    return path


def load_manifest(root: Path) -> tuple[Path, dict, list[str]]:
    path = root / Path(*MANIFEST_PATH.parts)
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return path, {}, [f"missing manifest: {MANIFEST_PATH}"]
    except json.JSONDecodeError as exc:
        return path, {}, [f"invalid JSON in {MANIFEST_PATH}: {exc}"]

    if not isinstance(data, dict):
        return path, {}, [f"{MANIFEST_PATH}: top level must be an object"]
    if data.get("schema_version") != 1:
        errors.append(f"{MANIFEST_PATH}: schema_version must be 1")
    if not isinstance(data.get("renderings"), dict) or not data["renderings"]:
        errors.append(f"{MANIFEST_PATH}: renderings must be a non-empty object")
    return path, data, errors


def expected_paths(name: str) -> tuple[str, str]:
    source = f".claude/commands/{name}.md"
    if name.startswith("_"):
        return source, f"codex/skills/{name}.md"
    return source, f"codex/skills/{name}/SKILL.md"


def read_frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}, ["missing YAML frontmatter"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, ["unterminated YAML frontmatter"]

    fields: dict[str, str] = {}
    errors: list[str] = []
    for line_number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        match = FRONTMATTER_FIELD_RE.fullmatch(line)
        if not match:
            errors.append(
                f"frontmatter line {line_number}: expected an unindented key: scalar field"
            )
            continue

        key, raw_value = match.groups()
        if key in fields:
            errors.append(f"frontmatter line {line_number}: duplicate field {key!r}")
            continue

        value = raw_value.strip()
        if value.startswith(UNSUPPORTED_SCALAR_PREFIXES):
            errors.append(
                f"frontmatter line {line_number}: structured or block YAML is unsupported"
            )
            continue

        if value.startswith('"'):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                errors.append(
                    f"frontmatter line {line_number}: invalid double-quoted scalar"
                )
                continue
            if not isinstance(parsed, str):
                errors.append(f"frontmatter line {line_number}: expected a string scalar")
                continue
            value = parsed
        elif value.startswith("'"):
            if len(value) < 2 or not value.endswith("'"):
                errors.append(
                    f"frontmatter line {line_number}: unterminated single-quoted scalar"
                )
                continue
            interior = value[1:-1]
            if "'" in interior.replace("''", ""):
                errors.append(
                    f"frontmatter line {line_number}: invalid single-quoted scalar"
                )
                continue
            value = interior.replace("''", "'")
        elif re.search(r":\s", value) or value.startswith(("- ", "? ")):
            errors.append(
                f"frontmatter line {line_number}: nested YAML is unsupported"
            )
            continue

        fields[key] = value
    return fields, errors


def actual_renderings(root: Path) -> tuple[dict[str, str], list[str]]:
    found: dict[str, str] = {}
    errors: list[str] = []
    skills = root / "codex" / "skills"
    candidates = [
        (path.parent.name, path) for path in sorted(skills.glob("*/SKILL.md"))
    ]
    candidates.extend((path.stem, path) for path in sorted(skills.glob("_*.md")))
    for name, path in candidates:
        relative = path.relative_to(root).as_posix()
        if name in found:
            errors.append(
                f"Codex renderings share manifest name {name!r}: {found[name]}, {relative}"
            )
            continue
        found[name] = relative
    return found, errors


def validate_structure(root: Path, data: dict) -> tuple[list[str], dict[str, tuple[Path, Path]]]:
    errors: list[str] = []
    resolved: dict[str, tuple[Path, Path]] = {}
    renderings = data.get("renderings")
    if not isinstance(renderings, dict):
        return errors, resolved

    actual, discovery_errors = actual_renderings(root)
    errors.extend(discovery_errors)
    missing = sorted(set(actual) - set(renderings))
    extra = sorted(set(renderings) - set(actual))
    for name in missing:
        errors.append(f"unregistered Codex rendering: {actual[name]}")
    for name in extra:
        errors.append(f"manifest entry has no Codex rendering: {name}")

    sources_seen: set[str] = set()
    renders_seen: set[str] = set()
    for name, entry in renderings.items():
        label = f"renderings.{name}"
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"{label}: name must use lowercase letters, digits, hyphens, or underscores")
            continue
        if not isinstance(entry, dict):
            errors.append(f"{label}: entry must be an object")
            continue

        fields = set(entry)
        if fields != ENTRY_FIELDS:
            missing_fields = sorted(ENTRY_FIELDS - fields)
            extra_fields = sorted(fields - ENTRY_FIELDS)
            if missing_fields:
                errors.append(f"{label}: missing fields: {', '.join(missing_fields)}")
            if extra_fields:
                errors.append(f"{label}: unknown fields: {', '.join(extra_fields)}")

        expected_source, expected_render = expected_paths(name)
        if entry.get("source") != expected_source:
            errors.append(f"{label}.source: expected {expected_source!r}")
        if entry.get("render") != expected_render:
            errors.append(f"{label}.render: expected {expected_render!r}")

        source = resolve_repo_path(root, entry.get("source"), f"{label}.source", errors)
        render = resolve_repo_path(root, entry.get("render"), f"{label}.render", errors)
        if source is None or render is None:
            continue
        if not source.is_file():
            errors.append(f"{label}.source: file does not exist: {expected_source}")
        if not render.is_file():
            errors.append(f"{label}.render: file does not exist: {expected_render}")
        if not source.is_file() or not render.is_file():
            continue

        source_key = source.relative_to(root).as_posix()
        render_key = render.relative_to(root).as_posix()
        if source_key in sources_seen:
            errors.append(f"{label}.source: duplicate path: {source_key}")
        if render_key in renders_seen:
            errors.append(f"{label}.render: duplicate path: {render_key}")
        sources_seen.add(source_key)
        renders_seen.add(render_key)
        resolved[name] = (source, render)

        for field in ("source_sha256", "render_sha256"):
            value = entry.get(field)
            if not isinstance(value, str) or not HASH_RE.fullmatch(value):
                errors.append(f"{label}.{field}: expected a lowercase SHA-256 hash")

        if not name.startswith("_"):
            frontmatter, frontmatter_errors = read_frontmatter(render)
            for error in frontmatter_errors:
                errors.append(f"{render_key}: {error}")
            if not frontmatter_errors:
                if frontmatter.get("name") != name:
                    errors.append(
                        f"{render_key}: frontmatter name {frontmatter.get('name')!r} must match {name!r}"
                    )
                if not frontmatter.get("description"):
                    errors.append(f"{render_key}: frontmatter description must be non-empty")

    return errors, resolved


def stale_renderings(data: dict, resolved: dict[str, tuple[Path, Path]]) -> dict[str, list[str]]:
    stale: dict[str, list[str]] = {}
    for name, (source, render) in resolved.items():
        entry = data["renderings"][name]
        changed: list[str] = []
        if entry.get("source_sha256") != sha256(source):
            changed.append("source")
        if entry.get("render_sha256") != sha256(render):
            changed.append("render")
        if changed:
            stale[name] = changed
    return stale


def write_manifest(path: Path, data: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def report_failure(errors: list[str], stale: dict[str, list[str]]) -> int:
    print("Codex rendering validation failed:", file=sys.stderr)
    for error in errors:
        print(f"  ERROR {error}", file=sys.stderr)
    for name, changed in stale.items():
        print(f"  STALE {name}: {', '.join(changed)} changed", file=sys.stderr)
    if stale:
        names = " ".join(stale)
        print("", file=sys.stderr)
        print("Review every stale source/render pair and update the Codex rendering if needed.", file=sys.stderr)
        print(
            f"Then acknowledge the reviewed pairs explicitly:\n"
            f"  python3 .github/scripts/validate_codex_renderings.py --acknowledge {names}",
            file=sys.stderr,
        )
    return 1


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    manifest_path, data, errors = load_manifest(root)
    structure_errors, resolved = validate_structure(root, data)
    errors.extend(structure_errors)

    if args.acknowledge:
        if errors:
            return report_failure(errors, {})
        unknown = sorted(set(args.acknowledge) - set(resolved))
        if unknown:
            return report_failure([f"unknown rendering name: {name}" for name in unknown], {})
        for name in args.acknowledge:
            source, render = resolved[name]
            data["renderings"][name]["source_sha256"] = sha256(source)
            data["renderings"][name]["render_sha256"] = sha256(render)
        write_manifest(manifest_path, data)
        print(f"Acknowledged reviewed renderings: {', '.join(args.acknowledge)}")

    stale = stale_renderings(data, resolved)
    if errors or stale:
        return report_failure(errors, stale)

    print(f"Codex rendering validation passed: {len(resolved)} acknowledged pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
