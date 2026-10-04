"""Settings roots are configurable; shipped hook commands belong to the installer."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest
import shutil

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session


def fixture_env(home, config):
    environment = isolate_session(dict(os.environ), config, 'hook-install-fixture')
    environment['HOME'] = home
    return environment


ROOT = Path(__file__).resolve().parents[1]


class HookInstallation(unittest.TestCase):
    def test_both_sets_are_idempotent_when_config_and_installation_share_root(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / 'config'
            scripts = cfg / 'scripts'
            shutil.copytree(ROOT / '.claude/scripts', scripts)
            env = fixture_env(d, cfg)
            wires = [scripts / 'wire-park-hooks.sh', scripts / 'wire-skill-edit-hook.sh']
            for wire in wires:
                subprocess.run([str(wire)], env=env, capture_output=True, check=True)
            settings = cfg / 'settings.json'
            before = settings.read_bytes()
            backups = sorted(cfg.glob('settings.json.bak-*'))
            for wire in wires:
                result = subprocess.run([str(wire)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('No changes', result.stdout)
                self.assertEqual(settings.read_bytes(), before)
            self.assertEqual(sorted(cfg.glob('settings.json.bak-*')), backups)

    def test_separate_config_root_wires_and_removes_actual_installed_helpers(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / 'different config root';cfg.mkdir()
            env = fixture_env(d, cfg)
            scripts = ROOT / '.claude/scripts'
            for wire in ['wire-skill-edit-hook.sh', 'wire-park-hooks.sh']:
                r = subprocess.run([str(scripts/wire)], env=env, capture_output=True, text=True)
                self.assertEqual(0, r.returncode, r.stderr)
            data=json.loads((cfg/'settings.json').read_text())
            commands=[h['command'] for rows in data['hooks'].values() for row in rows for h in row['hooks']]
            self.assertTrue(commands)
            self.assertTrue(all(str(scripts) in command for command in commands), commands)
            self.assertFalse(any(str(cfg/'scripts') in command for command in commands))
            for wire in ['wire-skill-edit-hook.sh', 'wire-park-hooks.sh']:
                r=subprocess.run([str(scripts/wire),'--remove'],env=env,capture_output=True,text=True)
                self.assertEqual(0,r.returncode,r.stderr)
            remaining=json.loads((cfg/'settings.json').read_text())['hooks']
            self.assertFalse(any(remaining.values()), remaining)

    def test_current_config_legacy_commands_migrate_without_duplicates_or_foreign_removal(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=Path(d)/'cfg';cfg.mkdir()
            old=str(cfg/'scripts/skill-edit-marker.sh')
            foreign='"/other/tool.sh"'
            (cfg/'settings.json').write_text(json.dumps({'hooks':{'PostToolUse':[{'matcher':'Write|Edit','hooks':[{'type':'command','command':old,'timeout':5},{'type':'command','command':foreign,'timeout':5}]}]}}))
            env=fixture_env(d, cfg)
            wire=ROOT/'.claude/scripts/wire-skill-edit-hook.sh'
            for _ in range(2):
                r=subprocess.run([str(wire)],env=env,capture_output=True,text=True);self.assertEqual(0,r.returncode,r.stderr)
            commands=[h['command'] for rows in json.loads((cfg/'settings.json').read_text())['hooks'].values() for row in rows for h in row['hooks']]
            self.assertIn(foreign,commands)
            self.assertNotIn(old,commands)
            self.assertEqual(1,sum('skill-edit-marker.sh' in c for c in commands))


    def test_invalid_settings_preserved_and_unknown_old_root_not_claimed_absent(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=Path(d)/'cfg';cfg.mkdir()
            env=fixture_env(d, cfg)
            settings=cfg/'settings.json';settings.write_text('{invalid')
            wire=ROOT/'.claude/scripts/wire-skill-edit-hook.sh'
            r=subprocess.run([str(wire),'--remove'],env=env,capture_output=True,text=True)
            self.assertNotEqual(0,r.returncode)
            self.assertEqual('{invalid',settings.read_text())
            unknown='"/old-root/scripts/skill-edit-marker.sh"'
            settings.write_text(json.dumps({'hooks':{'PostToolUse':[{'matcher':'Write|Edit','hooks':[{'type':'command','command':unknown}]}]}}))
            original=settings.read_bytes()
            r=subprocess.run([str(wire),'--remove'],env=env,capture_output=True,text=True)
            self.assertEqual(0,r.returncode,r.stderr)
            self.assertEqual(original,settings.read_bytes())
            self.assertIn('this installation or current config root',r.stdout)
            self.assertNotIn('already in their target state',r.stdout)


    def test_park_startup_helpers_use_installer_root_and_preserve_foreign_settings(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / 'separate config'; cfg.mkdir()
            settings = cfg / 'settings.json'
            foreign = {'type': 'command', 'command': 'foreign-startup-command', 'timeout': 9}
            initial = {'permissions': {'allow': ['Read']}, 'env': {'KEEP': 'value'},
                       'hooks': {'SessionStart': [{'matcher': 'startup', 'hooks': [foreign]}]}}
            settings.write_text(json.dumps(initial))
            env = fixture_env(d, cfg)
            wire = ROOT / '.claude/scripts/wire-park-hooks.sh'
            for _ in range(2):
                result = subprocess.run([str(wire)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            added = json.loads(settings.read_text())
            self.assertEqual(added['permissions'], initial['permissions'])
            self.assertEqual(added['env'], initial['env'])
            for event, name in [('SessionStart', 'harness-semantics-check.py'),
                                ('UserPromptSubmit', 'park-preflight.py')]:
                commands = [h['command'] for row in added['hooks'][event] for h in row['hooks']]
                expected = 'python3 "' + str(ROOT / '.claude/scripts' / name) + '"'
                self.assertEqual(commands.count(expected), 1, commands)
                self.assertFalse(any(str(cfg / 'scripts') in c for c in commands))
            result = subprocess.run([str(wire), '--remove'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            remaining = json.loads(settings.read_text())
            commands = [h['command'] for rows in remaining['hooks'].values() for row in rows for h in row['hooks']]
            self.assertEqual(commands, ['foreign-startup-command'])
            self.assertEqual(remaining['permissions'], initial['permissions'])
            self.assertEqual(remaining['env'], initial['env'])
            self.assertFalse((cfg / 'harness-semantics.json').exists())


if __name__ == '__main__':unittest.main()
