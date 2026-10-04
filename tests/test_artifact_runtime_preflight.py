"""Literal diagnostic controls; import/exposure/ingress are independent values."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.claude/scripts/artifact-runtime-preflight.py'
NODE = shutil.which('node')
pytestmark = pytest.mark.skipif(NODE is None, reason='Node required for real module import controls')


def fixture(tmp_path):
    skill = tmp_path / 'skill/SKILL.md'
    skill.parent.mkdir()
    skill.write_text('Use the supplied artifact runtime.\n')
    marker = skill.parent / 'container_tools/mark_artifact_operation_started.mjs'
    marker.parent.mkdir()
    # Invocation would leave a detectable side effect; diagnosis must never invoke.
    marker.write_text("import fs from 'node:fs'; fs.writeFileSync('marker-invoked', 'bad');\n")
    modules = tmp_path / 'node_modules'
    package = modules / '@oai/artifact-tool'
    package.mkdir(parents=True)
    (package / 'package.json').write_text(json.dumps({'name': '@oai/artifact-tool',
                                                     'version': '1.2.3', 'type': 'module', 'exports': './index.mjs'}))
    (package / 'index.mjs').write_text('export const Fixture = 42;\n')
    registry = tmp_path / 'registry.json'
    registry.write_text(json.dumps({'tools': [{'name': 'load_workspace_dependencies'}, {'name': 'positive_control_tool'}]}))
    return skill, modules, registry


def check(tmp_path, skill, modules, registry, extra=(), node=NODE):
    argv = [sys.executable, str(SCRIPT), '--cwd', str(tmp_path), '--skill', str(skill),
            '--node', str(node), '--node-modules', str(modules)]
    if registry is not None:
        argv += ['--tool-registry', str(registry)]
    process = subprocess.run([*argv, *extra], text=True, capture_output=True)
    receipt = json.loads(process.stdout)
    assert receipt['exit_code'] == process.returncode
    assert process.stderr == ''
    assert receipt['cwd'] == str(tmp_path)
    return process.returncode, receipt


def tree_hash(root):
    return {str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode)
            for p in root.rglob('*') if p.is_file()}


def test_real_import_marker_presence_and_read_only(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    before = tree_hash(tmp_path)
    code, r = check(tmp_path, skill, modules, registry)
    assert code == 0
    a = r['authoring']
    assert a['status'] == 'prerequisites_present'
    probe = a['import']
    assert probe['exit_code'] == 0 and probe['stderr'] == ''
    assert json.loads(probe['stdout']) == {'entry': str(modules / '@oai/artifact-tool/index.mjs'), 'imported': True}
    assert probe['argv'][0] == NODE and probe['cwd'] == str(tmp_path)
    assert a['files']['operation_marker']['sha256'] == hashlib.sha256((skill.parent / 'container_tools/mark_artifact_operation_started.mjs').read_bytes()).hexdigest()
    assert not a['marker_invoked'] and not (tmp_path / 'marker-invoked').exists()
    assert before == tree_hash(tmp_path)
    assert r['binary_ingress']['status'] == 'not_requested'


def test_available_import_does_not_prove_loader_exposed(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    registry.write_text('{"tools":[{"name":"positive_control_tool"}]}')
    code, r = check(tmp_path, skill, modules, registry, ['--require-loader', '--requirement-provenance', 'Fixture strict loader requirement'])
    assert code == 1 and r['authoring']['import']['exit_code'] == 0
    assert r['authoring']['registry']['tool_count'] == 1
    assert r['authoring']['registry']['loader'] == 'not_exposed'
    assert r['authoring']['missing'] == ['load_workspace_dependencies: not exposed in supplied registry']


def test_no_registry_unknown_not_absent(tmp_path):
    skill, modules, _ = fixture(tmp_path)
    code, r = check(tmp_path, skill, modules, None)
    assert code == 0 and r['authoring']['status'] == 'prerequisites_present'
    assert r['authoring']['registry']['loader'] == 'unknown'
    assert r['authoring']['import']['exit_code'] == 0


def test_missing_package_is_actual_import_failure(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    positive, control = check(tmp_path, skill, modules, registry)
    shutil.rmtree(modules / '@oai/artifact-tool')
    code, r = check(tmp_path, skill, modules, registry)
    assert positive == 0 and control['authoring']['import']['exit_code'] == 0
    assert code == 1 and r['authoring']['import']['exit_code'] != 0
    assert 'Cannot find module' in r['authoring']['import']['stderr']
    assert r['authoring']['files']['package_manifest']['type'] == 'missing'


def test_missing_and_symlink_marker_not_regular(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    marker = skill.parent / 'container_tools/mark_artifact_operation_started.mjs'
    marker.unlink()
    code, r = check(tmp_path, skill, modules, registry)
    assert code == 1 and r['authoring']['files']['operation_marker']['type'] == 'missing'
    marker.symlink_to(skill)
    code, r = check(tmp_path, skill, modules, registry)
    assert code == 1 and r['authoring']['files']['operation_marker']['type'] == 'symlink'
    assert r['authoring']['import']['exit_code'] == 0


@pytest.mark.parametrize('contents', ['not-json', '{"tools":[{}]}', '{"tools":"bad"}'])
def test_malformed_registry_stays_unknown(tmp_path, contents):
    skill, modules, registry = fixture(tmp_path)
    registry.write_text(contents)
    code, r = check(tmp_path, skill, modules, registry)
    assert code == 0 and r['authoring']['registry']['status'] == 'unknown'
    assert r['authoring']['import']['exit_code'] == 0


def test_nonzero_import_and_zero_without_receipt_are_not_success(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    fake_node = tmp_path / 'node'
    fake_node.write_text('#!/bin/sh\necho failed-import >&2\nexit 7\n')
    fake_node.chmod(0o755)
    code, r = check(tmp_path, skill, modules, registry, node=fake_node)
    assert code == 1 and r['authoring']['import']['exit_code'] == 7
    assert r['authoring']['import']['stderr'] == 'failed-import\n'
    fake_node.write_text('#!/bin/sh\necho not-an-import-receipt\nexit 0\n')
    code, r = check(tmp_path, skill, modules, registry, node=fake_node)
    assert code == 1 and r['authoring']['import']['exit_code'] == 0
    assert r['authoring']['import']['stdout'] == 'not-an-import-receipt\n'


def test_ingress_is_independent_of_loader(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    vault = tmp_path / 'vault'
    scripts = vault / '.claude/scripts'
    scripts.mkdir(parents=True)
    for name in ['resolve-vault.sh', 'locked-ingress.sh', 'lib-lock.sh', 'lib-session.sh']:
        shutil.copy2(ROOT / '.claude/scripts' / name, scripts / name)
    registry.write_text('{"tools":[{"name":"positive_control_tool"}]}')
    before = tree_hash(vault)
    code, r = check(tmp_path, skill, modules, registry, ['--vault', str(vault), '--require-loader', '--requirement-provenance', 'Fixture strict loader requirement'])
    assert code == 1 and r['authoring']['status'] == 'unsupported'
    i = r['binary_ingress']
    assert i['status'] == 'prerequisites_present' and not i['writer_invoked']
    assert len(i['checks']) == 5
    assert all(c['exit_code'] == 0 for c in i['checks'])
    assert i['checks'][-1]['stdout'] == f'VAULT_PATH={vault}\n'
    assert tree_hash(vault) == before
    (scripts / 'lib-lock.sh').unlink()
    code, r = check(tmp_path, skill, modules, registry, ['--vault', str(vault), '--require-loader', '--requirement-provenance', 'Fixture strict loader requirement'])
    assert code == 1 and r['binary_ingress']['status'] == 'unsupported'
    assert r['binary_ingress']['checks'] == []
    assert 'lib-lock.sh: not a readable regular file' in r['binary_ingress']['missing']


def test_resolver_value_must_match_supplied_vault(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    scripts = tmp_path / 'vault/.claude/scripts'
    scripts.mkdir(parents=True)
    for name in ['resolve-vault.sh', 'locked-ingress.sh', 'lib-lock.sh', 'lib-session.sh']:
        shutil.copy2(ROOT / '.claude/scripts' / name, scripts / name)
    (scripts / 'resolve-vault.sh').write_text('#!/bin/sh\necho VAULT_PATH=/different-vault\n')
    code, r = check(tmp_path, skill, modules, registry, ['--vault', str(tmp_path / 'vault')])
    assert code == 1 and r['authoring']['status'] == 'prerequisites_present'
    assert r['binary_ingress']['status'] == 'unsupported'
    assert r['binary_ingress']['checks'][-1]['exit_code'] == 0
    assert r['binary_ingress']['checks'][-1]['stdout'] == 'VAULT_PATH=/different-vault\n'


def test_timeout_is_unknown_failure_not_success(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    fake_node = tmp_path / 'node'
    fake_node.write_text('#!/bin/sh\nexec sleep 2\n')
    fake_node.chmod(0o755)
    code, r = check(tmp_path, skill, modules, registry, ['--timeout', '0.01'], node=fake_node)
    assert code == 2 and r['authoring']['status'] == 'unknown' and r['authoring']['import']['timeout']
    assert r['authoring']['import']['exit_code'] is None


def test_non_executable_ingress_script_not_usable(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    scripts = tmp_path / 'vault/.claude/scripts'
    scripts.mkdir(parents=True)
    for name in ['resolve-vault.sh', 'locked-ingress.sh', 'lib-lock.sh', 'lib-session.sh']:
        shutil.copy2(ROOT / '.claude/scripts' / name, scripts / name)
    (scripts / 'locked-ingress.sh').chmod(0o644)
    code, r = check(tmp_path, skill, modules, registry, ['--vault', str(tmp_path / 'vault')])
    assert code == 1 and r['binary_ingress']['status'] == 'unsupported'
    assert 'locked-ingress.sh: not executable' in r['binary_ingress']['missing']
    assert r['binary_ingress']['files']['locked-ingress.sh']['mode'] == '0644'


def test_import_throw_and_loader_name_not_value_presence(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    registry.write_text('{"tools":[{"name":"not_load_workspace_dependencies_available"}]}')
    code, r = check(tmp_path, skill, modules, registry)
    assert code == 0 and r['authoring']['registry']['loader'] == 'not_exposed'
    assert r['authoring']['import']['exit_code'] == 0
    registry.write_text('{"tools":[{"name":"mcp__runtime__load_workspace_dependencies"}]}')
    (modules / '@oai/artifact-tool/index.mjs').write_text("throw new Error('fixture import rejected');\n")
    code, r = check(tmp_path, skill, modules, registry)
    assert code == 1 and r['authoring']['registry']['loader'] == 'exposed'
    assert r['authoring']['import']['exit_code'] != 0
    assert 'fixture import rejected' in r['authoring']['import']['stderr']


def test_supported_js_fallback_and_strict_loader_gate_same_inputs(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    registry.write_text('{"tools":[{"name":"positive_control_tool"}]}')
    code, fallback = check(tmp_path, skill, modules, registry,
                           ['--requirement-provenance', 'Fixture skill permits local runtime fallback'])
    assert code == 0 and fallback['authoring']['status'] == 'prerequisites_present'
    assert fallback['authoring']['registry']['loader'] == 'not_exposed'
    assert fallback['authoring']['import']['exit_code'] == 0
    assert not fallback['authoring']['require_loader']
    assert 'load_workspace_dependencies_exposure' not in fallback['authoring']['checked_requirements']
    code, strict = check(tmp_path, skill, modules, registry,
                         ['--require-loader', '--requirement-provenance', 'Fixture requirement forbids fallback'])
    assert code == 1 and strict['authoring']['status'] == 'unsupported'
    assert strict['authoring']['import']['stdout'] == fallback['authoring']['import']['stdout']
    assert strict['authoring']['requirement_provenance']['caller_supplied'] == 'Fixture requirement forbids fallback'
    code, strict_unknown = check(tmp_path, skill, modules, None,
                                 ['--require-loader', '--requirement-provenance', 'Fixture requires loader'])
    assert code == 2 and strict_unknown['authoring']['registry']['loader'] == 'unknown'


def test_marker_only_has_no_js_requirement_and_keeps_other_prereqs_unknown(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    shutil.rmtree(modules)
    argv = [sys.executable, str(SCRIPT), '--cwd', str(tmp_path), '--skill', str(skill),
            '--profile', 'marker-only', '--requirement-provenance', 'Fixture requires marker and Python']
    before = tree_hash(tmp_path)
    p = subprocess.run(argv, text=True, capture_output=True)
    r = json.loads(p.stdout)
    a = r['authoring']
    assert p.returncode == r['exit_code'] == 2 and a['status'] == 'unknown'
    assert a['profile'] == 'marker-only' and a['import'] is None
    assert a['checked_requirements'] == ['skill_readable_regular', 'operation_marker_readable_regular']
    assert 'node' not in a['files'] and 'node_modules' not in a['files']
    assert a['missing'] == [] and a['unknown'] == ['marker-only scope: other authoring prerequisites were not checked']
    assert not a['marker_invoked'] and before == tree_hash(tmp_path)
    (skill.parent / 'container_tools/mark_artifact_operation_started.mjs').unlink()
    p = subprocess.run(argv, text=True, capture_output=True)
    r = json.loads(p.stdout)
    assert p.returncode == r['exit_code'] == 1 and r['authoring']['status'] == 'unsupported'
    assert r['authoring']['files']['operation_marker']['type'] == 'missing'


@pytest.mark.parametrize('value', ['nan', 'inf', '-inf', '0', '-1'])
def test_timeout_must_be_finite_positive_before_any_probe(tmp_path, value):
    skill, modules, registry = fixture(tmp_path)
    argv = [sys.executable, str(SCRIPT), '--cwd', str(tmp_path), '--skill', str(skill),
            '--profile', 'marker-only', '--timeout=' + value]
    p = subprocess.run(argv, text=True, capture_output=True)
    assert p.returncode == 2 and p.stdout == ''
    assert '--timeout must be finite and positive' in p.stderr and 'Traceback' not in p.stderr
    assert not (tmp_path / 'marker-invoked').exists()


def test_profile_specific_arguments_and_strict_requirement_provenance(tmp_path):
    skill, modules, registry = fixture(tmp_path)
    argv = [sys.executable, str(SCRIPT), '--cwd', str(tmp_path), '--skill', str(skill)]
    p = subprocess.run(argv, text=True, capture_output=True)
    assert p.returncode == 2 and '--node and --node-modules are required' in p.stderr
    p = subprocess.run([*argv, '--profile', 'marker-only', '--require-loader'], text=True, capture_output=True)
    assert p.returncode == 2 and '--require-loader requires non-empty --requirement-provenance' in p.stderr
