#!/usr/bin/env python3
"""Diagnose authoring prerequisites separately from binary vault ingress; never write."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys


def file_receipt(path):
    p = Path(path).expanduser().absolute()
    result = {'path': str(p), 'type': 'missing'}
    try:
        st = p.lstat()
        result['mode'] = f'{stat.S_IMODE(st.st_mode):04o}'
        result['type'] = ('symlink' if stat.S_ISLNK(st.st_mode) else
                          'regular' if stat.S_ISREG(st.st_mode) else
                          'directory' if stat.S_ISDIR(st.st_mode) else 'other')
        if result['type'] == 'regular':
            result['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
            result['size'] = st.st_size
            result['readable'] = os.access(p, os.R_OK)
            result['executable'] = os.access(p, os.X_OK)
    except OSError as exc:
        result['error'] = str(exc)
    return result


def run(argv, cwd, timeout, env=None):
    receipt = {'argv': list(map(str, argv)), 'cwd': str(cwd), 'exit_code': None,
               'stdout': '', 'stderr': '', 'timeout': False}
    try:
        p = subprocess.run(receipt['argv'], cwd=cwd, env=env, text=True,
                           errors='replace', capture_output=True, timeout=timeout)
        receipt.update(exit_code=p.returncode, stdout=p.stdout, stderr=p.stderr)
    except subprocess.TimeoutExpired as exc:
        def text(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else (value or '')
        receipt.update(timeout=True, stdout=text(exc.stdout), stderr=text(exc.stderr))
    except OSError as exc:
        receipt['stderr'] = str(exc)
    return receipt


IMPORT = """import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require=createRequire(pathToFileURL(process.argv[1]+'/__preflight__.cjs'));
const entry=require.resolve('@oai/artifact-tool');
const module=await import(pathToFileURL(entry).href);
console.log(JSON.stringify({entry,imported:true}));
"""


def registry_receipt(path):
    if path is None:
        return {'status': 'unknown', 'reason': 'current tool registry not supplied', 'loader': 'unknown'}
    receipt = file_receipt(path)
    try:
        if receipt['type'] != 'regular':
            raise ValueError('registry must be a regular JSON file')
        value = json.loads(Path(path).read_text())
        if not isinstance(value, dict) or not isinstance(value.get('tools'), list):
            raise ValueError('expected {"tools": [{"name": "..."}]}')
        names = [tool['name'] for tool in value['tools']
                 if isinstance(tool, dict) and isinstance(tool.get('name'), str)]
        if len(names) != len(value['tools']):
            raise ValueError('each tool needs a string name')
        matches = [n for n in names if n == 'load_workspace_dependencies'
                   or n.endswith('__load_workspace_dependencies')]
        receipt.update(status='inspected', tool_count=len(names), loader='exposed' if matches else 'not_exposed',
                       loader_matches=matches,
                       boundary='names in the supplied current registry; filesystem presence is not tool exposure')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        receipt.update(status='unknown', loader='unknown', reason=str(exc))
    return receipt


def ingress_receipt(vault, cwd, timeout):
    if vault is None:
        return {'status': 'not_requested'}
    root = Path(vault).expanduser().absolute()
    scripts = root / '.claude/scripts'
    names = ['resolve-vault.sh', 'locked-ingress.sh', 'lib-lock.sh', 'lib-session.sh']
    files = {name: file_receipt(scripts / name) for name in names}
    commands = {name: shutil.which(name) for name in
                ['bash', 'python3', 'mktemp', 'dirname', 'rm', 'mkdir', 'flock', 'sleep', 'date', 'uname', 'sed']}
    required = ['bash', 'python3', 'mktemp', 'dirname', 'rm', 'mkdir', 'sleep', 'date', 'uname', 'sed']
    problems = [name + ': not a readable regular file' for name, r in files.items()
                if r['type'] != 'regular' or not r.get('readable')]
    problems += [name + ': missing executable' for name in required if not commands[name]]
    problems += [name + ': not executable' for name in ['resolve-vault.sh', 'locked-ingress.sh']
                 if files[name]['type'] == 'regular' and not files[name].get('executable')]
    checks = []
    if not problems:
        for name in names:
            checks.append(run([commands['bash'], '-n', str(scripts / name)], cwd, timeout))
        env = dict(os.environ, VAULT_PATH=str(root))
        checks.append(run([commands['bash'], str(scripts / 'resolve-vault.sh')], cwd, timeout, env))
        expected = 'VAULT_PATH=' + str(root) + '\n'
        if any(r['exit_code'] != 0 for r in checks) or checks[-1]['stdout'] != expected:
            problems.append('syntax or canonical resolver value check failed')
    return {'status': 'unsupported' if problems else 'prerequisites_present',
            'files': files, 'commands': commands, 'checks': checks, 'missing': problems,
            'writer_invoked': False, 'boundary': 'syntax/resolver/prerequisites only; no destination, lock acquisition or write tested'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cwd', required=True, type=Path)
    p.add_argument('--skill', required=True, type=Path, help='installed SKILL.md')
    p.add_argument('--profile', choices=['js-artifact', 'marker-only'], default='js-artifact',
                   help='explicit diagnostic scope; read the selected skill first')
    p.add_argument('--node', type=Path, help='explicit supplied JS runtime executable')
    p.add_argument('--node-modules', type=Path, help='explicit supplied JS runtime node_modules')
    p.add_argument('--require-loader', action='store_true',
                   help='gate on loader exposure only when the selected requirement forbids fallback')
    p.add_argument('--requirement-provenance', help='caller-supplied skill section/requirement supporting the selected scope')
    p.add_argument('--tool-registry', type=Path, help='current exposed tool names in {tools:[{name:...}]}')
    p.add_argument('--vault', type=Path, help='optional vault for canonical ingress prerequisite checks')
    p.add_argument('--timeout', type=float, default=15)
    a = p.parse_args(argv)
    if not math.isfinite(a.timeout) or a.timeout <= 0:
        p.error('--timeout must be finite and positive')
    if a.profile == 'js-artifact' and (a.node is None or a.node_modules is None):
        p.error('--node and --node-modules are required for --profile js-artifact')
    if a.require_loader and not (a.requirement_provenance and a.requirement_provenance.strip()):
        p.error('--require-loader requires non-empty --requirement-provenance')
    cwd = a.cwd.expanduser().absolute()
    skill = a.skill.expanduser().absolute()
    files = {'skill': file_receipt(skill),
             'operation_marker': file_receipt(skill.parent / 'container_tools/mark_artifact_operation_started.mjs')}
    checked = ['skill_readable_regular', 'operation_marker_readable_regular']
    missing = []
    unknown = []
    if not cwd.is_dir():
        missing.append('cwd: not an existing directory')
    for name in ['skill', 'operation_marker']:
        if files[name]['type'] != 'regular' or not files[name].get('readable'):
            missing.append(name + ': not a readable regular file')
    if a.profile == 'js-artifact':
        module_root = a.node_modules.expanduser().absolute()
        node = a.node.expanduser().absolute()
        files.update(node=file_receipt(node), node_modules=file_receipt(module_root),
                     package_manifest=file_receipt(module_root / '@oai/artifact-tool/package.json'))
        checked += ['node_executable', 'node_modules_directory', 'artifact_module_import']
        if not node.is_file() or not os.access(node, os.X_OK):
            missing.append('node: not an executable file')
        if not module_root.is_dir():
            missing.append('node_modules: not an existing directory')
    registry = registry_receipt(a.tool_registry)
    probe = None
    if a.profile == 'js-artifact' and cwd.is_dir() and node.is_file() and os.access(node, os.X_OK) and module_root.is_dir():
        probe = run([str(node), '--input-type=module', '-e', IMPORT, str(module_root)], cwd, a.timeout)
        try:
            value = json.loads(probe['stdout'])
            good = probe['exit_code'] == 0 and isinstance(value.get('entry'), str) and value.get('imported') is True
        except (ValueError, AttributeError):
            good = False
        if probe['timeout']:
            unknown.append('artifact_import: observation timed out')
        elif not good:
            missing.append('artifact_import: import did not return a successful module receipt')
    elif a.profile == 'js-artifact':
        missing.append('artifact_import: prerequisites missing; not run')
    else:
        unknown.append('marker-only scope: other authoring prerequisites were not checked')
    if a.require_loader:
        checked.append('load_workspace_dependencies_exposure')
        if registry['loader'] == 'not_exposed':
            missing.append('load_workspace_dependencies: not exposed in supplied registry')
        elif registry['loader'] == 'unknown':
            unknown.append('load_workspace_dependencies: exposure unknown')
    status = 'unsupported' if missing else ('unknown' if unknown else 'prerequisites_present')
    ingress = ingress_receipt(a.vault, cwd, a.timeout) if cwd.is_dir() else {'status': 'unknown', 'reason': 'invalid cwd'}
    result = {'schema': 'opencairn-artifact-preflight-v2', 'cwd': str(cwd),
              'invocation': [sys.executable, str(Path(__file__).absolute()), *(argv if argv is not None else sys.argv[1:])],
              'authoring': {'status': status, 'profile': a.profile, 'checked_requirements': checked,
                            'require_loader': a.require_loader,
                            'requirement_provenance': {'caller_supplied': a.requirement_provenance,
                                                       'skill_path': str(skill),
                                                       'skill_sha256': files['skill'].get('sha256'),
                                                       'selection': 'explicit profile; requirements not inferred from skill text'},
                            'files': files, 'registry': registry, 'import': probe,
                            'missing': missing, 'unknown': unknown, 'marker_invoked': False,
                            'boundary': 'selected diagnostics only; whole-skill dependencies, marker invocation, authoring and artifact QA are not certified'},
              'binary_ingress': ingress}
    exit_code = 1 if status == 'unsupported' or ingress['status'] == 'unsupported' else 2 if status == 'unknown' or ingress['status'] == 'unknown' else 0
    result['exit_code'] = exit_code
    print(json.dumps(result, indent=2))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
