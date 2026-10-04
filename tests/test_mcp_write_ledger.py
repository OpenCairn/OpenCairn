import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    from session_isolation import isolate_session
except ImportError:
    from tests.session_isolation import isolate_session

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.claude/scripts/mcp-write-ledger.sh'


class McpWriteLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.vault = self.base / 'vault'
        self.vault.mkdir()
        self.config = self.base / 'state'
        self.env = isolate_session(os.environ.copy(), self.config, 'mcp-fixture')
        self.env['VAULT_PATH'] = str(self.vault)
        self.path = self.vault / 'Notes/Example note.md'
        self.path.parent.mkdir()
        self.path.write_text('Already landed note contents')
        self.payload = {'hook_event_name': 'PostToolUse', 'session_id': 'mcp-fixture',
            'tool_name': 'mcp__obsidian__obsidian_write_note', 'agent_id': 'agent-fixture',
            'tool_input': {'target': {'type': 'active'}},
            'tool_response': {'structuredContent': {'path': 'Notes/Example note.md',
                                                  'currentSizeInBytes': 28}}}
        self.ledger = self.config / '.session-state/mcp-fixture.tsv'

    def run_hook(self, *args):
        r = subprocess.run([str(SCRIPT), *args], input=json.dumps(self.payload),
            env=self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, '')
        return self.ledger.read_text() if self.ledger.exists() else ''

    def test_each_named_mutator_records_resolved_output_and_agent(self):
        for tool in ['write_note', 'append_to_note', 'patch_note', 'replace_in_note']:
            with self.subTest(tool=tool):
                self.payload['tool_name'] = 'mcp__obsidian__obsidian_' + tool
                row = self.run_hook().splitlines()[-1].split('\t')
                self.assertEqual(row[1:], [self.payload['tool_name'], str(self.path), 'agent-fixture'])

    def test_periodic_target_uses_resolved_response_not_input(self):
        self.payload['tool_input']['target'] = {'type': 'periodic', 'period': 'daily'}
        self.assertIn(str(self.path), self.run_hook())

    def test_json_text_response(self):
        self.payload['tool_response'] = {'content': [{'type': 'text', 'text':
            json.dumps({'path': 'Notes/Example note.md'})}]}
        self.assertIn(str(self.path), self.run_hook())

    def test_direct_response(self):
        self.payload['tool_response'] = {'path': 'Notes/Example note.md'}
        self.assertIn(str(self.path), self.run_hook())

    def test_failed_mcp_call_is_not_attributed(self):
        self.payload['tool_response']['isError'] = True
        self.assertEqual(self.run_hook(), '')

    def test_structured_error_is_not_attributed(self):
        self.payload['tool_response']['structuredContent']['error'] = {'reason': 'refused'}
        self.assertEqual(self.run_hook(), '')

    def test_input_path_alone_is_not_landed_evidence(self):
        self.payload['tool_input']['target'] = {'type': 'path', 'path': 'Notes/Example note.md'}
        self.payload['tool_response'] = {}
        self.assertEqual(self.run_hook(), '')

    def test_unknown_read_or_other_server_is_ignored(self):
        for tool in ['mcp__obsidian__obsidian_get_note', 'mcp__other__obsidian_write_note']:
            self.payload['tool_name'] = tool
            self.assertEqual(self.run_hook(), '')

    def test_post_failure_event_is_ignored(self):
        self.payload['hook_event_name'] = 'PostToolUseFailure'
        self.assertEqual(self.run_hook(), '')

    def test_escaping_absolute_missing_or_symlink_target_is_ignored(self):
        outside = self.base / 'outside.md'
        outside.write_text('outside')
        (self.vault / 'outside-link.md').symlink_to(outside)
        for path in ['../outside.md', str(outside), 'missing.md', 'outside-link.md']:
            with self.subTest(path=path):
                self.payload['tool_response']['structuredContent']['path'] = path
                self.assertEqual(self.run_hook(), '')

    def test_skill_command_write_also_marks_skill_edit(self):
        command = self.vault / '.claude/commands/example.md'
        command.parent.mkdir(parents=True)
        command.write_text('landed command')
        self.payload['tool_response']['structuredContent']['path'] = '.claude/commands/example.md'
        self.assertIn(str(command), self.run_hook())
        self.assertTrue((self.config / '.session-state/mcp-fixture.skilledit').exists())

    def test_note_contents_remain_unchanged(self):
        before = self.path.read_bytes()
        self.run_hook()
        self.assertEqual(self.path.read_bytes(), before)

    def test_marker_only_does_not_opt_into_ledger(self):
        command = self.vault / '.claude/commands/example.md'
        command.parent.mkdir(parents=True)
        command.write_text('landed command')
        self.payload['tool_response']['structuredContent']['path'] = '.claude/commands/example.md'
        self.assertEqual(self.run_hook('--marker'), '')
        self.assertTrue((self.config / '.session-state/mcp-fixture.skilledit').exists())

    def test_ledger_only_does_not_opt_into_skill_marker(self):
        command = self.vault / '.claude/commands/example.md'
        command.parent.mkdir(parents=True)
        command.write_text('landed command')
        self.payload['tool_response']['structuredContent']['path'] = '.claude/commands/example.md'
        self.assertIn(str(command), self.run_hook('--ledger'))
        self.assertFalse((self.config / '.session-state/mcp-fixture.skilledit').exists())

    def test_hook_sets_add_idempotently_and_remove_independently(self):
        wire = ROOT / '.claude/scripts/wire-park-hooks.sh'
        skill_wire = ROOT / '.claude/scripts/wire-skill-edit-hook.sh'
        for script in [wire, skill_wire, wire, skill_wire]:
            r = subprocess.run(['bash', str(script)], env=self.env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        settings = self.config / 'settings.json'
        def mcp_hooks():
            return [h['command'] for b in json.loads(settings.read_text())['hooks']['PostToolUse']
                    for h in b['hooks'] if 'mcp-write-ledger.sh' in h['command']]
        self.assertEqual(len(mcp_hooks()), 2)
        r = subprocess.run(['bash', str(wire), '--remove'], env=self.env, capture_output=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(mcp_hooks(), ['"' + str(self.config / 'scripts/mcp-write-ledger.sh') + '" --marker'])
        r = subprocess.run(['bash', str(skill_wire), '--remove'], env=self.env, capture_output=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(mcp_hooks(), [])


if __name__ == '__main__':
    unittest.main()
