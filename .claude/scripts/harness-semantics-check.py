#!/usr/bin/env python3
"""Advisory version drift detector; observing a version never verifies semantics."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

VERSION = r'\d+\.\d+\.\d+'


def baseline(path):
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            raise ValueError('manifest must be an object')
        version = manifest.get('verified_against')
        if not isinstance(version, str) or not re.fullmatch(VERSION, version):
            raise ValueError('missing or unknown verified_against')
        for key in ('evidence', 'claims'):
            values = manifest.get(key)
            if not isinstance(values, list) or not values or any(
                    not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f'{key} must name the recorded evidence and scope')
        return version, None
    except (OSError, ValueError) as exc:
        return None, str(exc)


def warn_once(cache, old, current):
    """mkdir is the atomic claim, including simultaneous SessionStart handlers."""
    vault = os.environ.get('VAULT_PATH')
    if vault and cache.resolve().is_relative_to(Path(vault).resolve()):
        raise ValueError('warning cache must be outside the vault')
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(json.dumps([old, current]).encode()).hexdigest()
    try:
        (cache / key).mkdir()
        return True
    except FileExistsError:
        return False


def main():
    config = Path(os.environ.get('CLAUDE_CONFIG_DIR') or str(Path.home() / '.claude'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=config / 'harness-semantics.json')
    parser.add_argument('--cache-dir', type=Path, default=Path(os.environ.get(
        'XDG_CACHE_HOME', str(Path.home() / '.cache'))) / 'opencairn/harness-semantics')
    parser.add_argument('--claude', default='claude', help='CLI executable; argv is always --version')
    parser.add_argument('--timeout', type=float, default=3.0)
    args = parser.parse_args()
    old, error = baseline(args.manifest)
    try:
        if not 0 < args.timeout <= 30:
            raise ValueError('timeout must be greater than zero and at most 30 seconds')
        result = subprocess.run([args.claude, '--version'], capture_output=True,
                                timeout=args.timeout, check=False)
        if result.returncode:
            raise ValueError(f'CLI exit {result.returncode}; stderr={result.stderr!r}')
        match = re.fullmatch(rb'(\d+\.\d+\.\d+) \(Claude Code\)\s*', result.stdout)
        if not match:
            raise ValueError(f'unrecognised version output: {result.stdout!r}')
        current = match[1].decode('ascii')
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f'Harness semantics: cannot observe Claude Code version ({exc}); verification unknown. Continue normally.')
        return 0
    if old is None:
        print(f'Harness semantics: unverified baseline ({error}); observed CLI {current}. Version output does not test semantics. Continue normally.')
        return 0
    if old == current:
        return 0
    try:
        emit = warn_once(args.cache_dir, old, current)
    except (OSError, ValueError) as exc:
        print(f'Harness semantics: cache unavailable ({exc}).')
        emit = True
    if emit:
        print(f'Harness semantics: Claude Code {old} -> {current}. Recorded claims in {args.manifest} need scoped re-verification; version output alone does not verify them. Continue normally.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
