import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from inbox_graph import REPO, Runner, inside, require_trial_copy, scan, validate_plan

CONFIG = {'configurable': {'thread_id': 'test'}}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    vault = tmp_path / 'vault'
    (vault / '02 Inbox').mkdir(parents=True)
    (vault / '04 Areas/Example').mkdir(parents=True)
    (vault / '02 Inbox/note.md').write_text('original\n')
    (vault / '04 Areas/Example/hub.md').write_text('# Example\n\n[[02 Inbox/note]]\n')
    run = tmp_path / 'run'
    run.mkdir()
    module = ast.parse((REPO / 'tests/test_locked_edit_move.py').read_text())
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MOCK_OBSIDIAN' for t in node.targets):
            mock = tmp_path / 'mock-obsidian'
            mock.write_text(ast.literal_eval(node.value))
            mock.chmod(0o755)
    monkeypatch.setenv('OBSIDIAN_CLI', str(mock))
    monkeypatch.setenv('VAULT_PATH', str(vault))
    monkeypatch.delenv('CLAUDE_SESSION_ID', raising=False)
    return vault, run


def plan(destination='04 Areas/Example/note.md'):
    return {'decisions': [{'source': '02 Inbox/note.md', 'outcome': 'MOVE',
                          'destination': destination, 'reason': 'Belongs to Example'}], 'patches': []}


def start(vault, run, value=None):
    calls = []
    def router(*args):
        calls.append(True)
        return value or plan()
    with SqliteSaver.from_conn_string(str(run / 'checkpoints.sqlite')) as saver:
        graph = Runner(run, router=router).build(saver)
        state = graph.invoke({'vault': str(vault), 'context': ''}, CONFIG)
    return state, calls


def resume(run, state, approved=True, router=None):
    def never(*args):
        raise AssertionError('Resume must not reroute')
    with SqliteSaver.from_conn_string(str(run / 'checkpoints.sqlite')) as saver:
        graph = Runner(run, router=router or never).build(saver)
        return graph.invoke(Command(resume={'plan_hash': state['plan_hash'], 'approved': approved}), CONFIG)


def test_approval_then_reopen_heals_links_and_verifies(workspace):
    vault, run = workspace
    state, calls = start(vault, run)
    assert len(calls) == 1
    assert (vault / '02 Inbox/note.md').exists()
    assert not (vault / '04 Areas/Example/note.md').exists()
    result = resume(run, state)
    assert result['verification']['moved'] == 1
    assert result['verification']['remaining'] == []
    assert (vault / '04 Areas/Example/note.md').read_text() == 'original\n'
    assert '[[04 Areas/Example/note]]' in (vault / '04 Areas/Example/hub.md').read_text()


def test_reject_makes_no_changes(workspace):
    vault, run = workspace
    state, _ = start(vault, run)
    resume(run, state, False)
    assert (vault / '02 Inbox/note.md').read_text() == 'original\n'
    assert not (run / 'effects.sqlite').exists()


@pytest.mark.parametrize('mutation', ['source', 'collision'])
def test_changed_preconditions_after_approval_pause_stop(workspace, mutation):
    vault, run = workspace
    state, _ = start(vault, run)
    if mutation == 'source':
        (vault / '02 Inbox/note.md').write_text('new user content\n')
    else:
        (vault / '04 Areas/Example/note.md').write_text('unrelated\n')
    with pytest.raises(ValueError, match='precondition changed'):
        resume(run, state)
    assert (vault / '02 Inbox/note.md').exists()


def test_coverage_duplicates_and_path_escape(workspace):
    vault, _ = workspace
    items = scan(vault)
    p = plan()
    p['decisions'] *= 2
    with pytest.raises(ValueError, match='exactly once'):
        validate_plan(vault, items, p)
    with pytest.raises(ValueError, match='Unsafe relative path'):
        validate_plan(vault, items, plan('../escape.md'))
    with pytest.raises(ValueError, match='exactly once'):
        validate_plan(vault, items, {'decisions': [], 'patches': []})


def test_symlink_destination_refused(workspace, tmp_path):
    vault, _ = workspace
    (vault / '04 Areas/Outside').symlink_to(tmp_path)
    with pytest.raises(ValueError, match='escapes vault|Symlink'):
        inside(vault, '04 Areas/Outside/escape.md')


def test_unviewed_image_cannot_be_moved(workspace):
    vault, _ = workspace
    (vault / '02 Inbox/note.md').unlink()
    (vault / '02 Inbox/image.png').write_bytes(b'not an image')
    p = plan('04 Areas/Example/image.png')
    p['decisions'][0]['source'] = '02 Inbox/image.png'
    with pytest.raises(ValueError, match='Uninspected'):
        validate_plan(vault, scan(vault), p)


def test_deletion_never_executes_and_new_arrivals_are_reported(workspace):
    vault, run = workspace
    p = plan()
    p['decisions'][0].update(outcome='DELETE', destination=None)
    state, _ = start(vault, run, p)
    (vault / '02 Inbox/new.md').write_text('new capture')
    result = resume(run, state)
    assert result['verification']['moved'] == 0
    assert result['verification']['arrivals_during_run'] == ['02 Inbox/new.md']
    assert (vault / '02 Inbox/note.md').exists()


def test_crash_after_move_before_graph_checkpoint_does_not_repeat(workspace):
    vault, run = workspace
    state, _ = start(vault, run)
    # Land the filesystem effect and its durable receipt, but omit the node checkpoint.
    state['approved'] = True
    Runner(run).execute(state)
    assert not (vault / '02 Inbox/note.md').exists()
    result = resume(run, state)
    assert result['verification']['moved'] == 1


def test_crash_after_write_before_receipt_reconciles_intent(workspace, monkeypatch):
    vault, run = workspace
    state, _ = start(vault, run)
    original = subprocess.run
    def crash(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[0][0].endswith('locked-edit.sh') and result.returncode == 0:
            raise RuntimeError('simulated process loss after filesystem effect')
        return result
    with monkeypatch.context() as m:
        m.setattr(subprocess, 'run', crash)
        with pytest.raises(RuntimeError, match='simulated process loss'):
            resume(run, state)
    with SqliteSaver.from_conn_string(str(run / 'checkpoints.sqlite')) as saver:
        graph = Runner(run).build(saver)
        result = graph.invoke(None, CONFIG)
    assert result['verification']['moved'] == 1


def test_locked_mover_reports_success_without_moving_is_failure(workspace, monkeypatch):
    vault, run = workspace
    monkeypatch.setenv('MOCK_MOVE_BEHAVIOUR', 'none')
    state, _ = start(vault, run)
    with pytest.raises(RuntimeError, match='Locked write refused'):
        resume(run, state)
    assert (vault / '02 Inbox/note.md').exists()


def test_patch_is_exact_and_replay_does_not_duplicate_capture(workspace):
    vault, run = workspace
    p = plan()
    target = '01 Now/Working memory.md'
    (vault / '01 Now').mkdir()
    (vault / target).write_text('# Working memory\n\n## Fresh captures\n')
    before = (vault / target).read_text()
    p['patches'] = [{'target': target, 'before': before,
                     'after': before + '- [ ] Example action\n', 'reason': 'Explicit action'}]
    state, _ = start(vault, run, p)
    state['approved'] = True
    Runner(run).execute(state)
    resume(run, state)
    assert (vault / target).read_text().count('Example action') == 1


def test_stale_move_blocks_earlier_patch_too(workspace):
    vault, run = workspace
    p = plan()
    target = '04 Areas/Example/hub.md'
    before = (vault / target).read_text()
    p['patches'] = [{'target': target, 'before': before,
                     'after': before + '\nAdditional index entry\n', 'reason': 'Index'}]
    state, _ = start(vault, run, p)
    (vault / '02 Inbox/note.md').write_text('user changed this')
    with pytest.raises(ValueError, match='precondition changed'):
        resume(run, state)
    assert (vault / target).read_text() == before


def test_symlink_capture_can_be_deferred(workspace, tmp_path):
    vault, run = workspace
    (vault / '02 Inbox/note.md').unlink()
    (vault / '02 Inbox/note.md').symlink_to(tmp_path / 'outside')
    p = plan()
    p['decisions'][0].update(outcome='DEFER', destination=None)
    state, _ = start(vault, run, p)
    result = resume(run, state)
    assert result['verification']['moved'] == 0


def test_deferred_file_corruption_cannot_pass_verification(workspace):
    vault, run = workspace
    p = plan()
    p['decisions'][0].update(outcome='DEFER', destination=None)
    state, _ = start(vault, run, p)
    (vault / '02 Inbox/note.md').write_text('changed')
    with pytest.raises(ValueError, match='Deferred source changed'):
        resume(run, state)


def test_unmarked_vault_is_refused(workspace):
    vault, _ = workspace
    with pytest.raises(ValueError, match='disposable copies'):
        require_trial_copy(vault)
    (vault / '.inbox-graph-trial').write_text('disposable-copy\n')
    require_trial_copy(vault)
