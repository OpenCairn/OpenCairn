"""Settings roots are configurable; shipped hook commands belong to the installer."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HookInstallation(unittest.TestCase):
    def test_separate_config_root_wires_and_removes_actual_installed_helpers(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / 'different config root';cfg.mkdir()
            env = dict(os.environ, CLAUDE_CONFIG_DIR=str(cfg), HOME=d)
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
            env=dict(os.environ,CLAUDE_CONFIG_DIR=str(cfg),HOME=d)
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
            env=dict(os.environ,CLAUDE_CONFIG_DIR=str(cfg),HOME=d)
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


if __name__ == '__main__':unittest.main()
