import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".claude/scripts/semantic-check.py"
spec = importlib.util.spec_from_file_location("semantic_check", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def item(kind="claim"):
    states = {
        "claim": {"source": "The job is queued.", "claim": "The job is running."},
        "check": {"hypothesis": "Published", "procedure": "Read local HEAD", "pass": "SHA matches",
                  "under_negative": "SHA also matches before push", "control": "Local repo exists"},
        "propagation": {"change": "Job started", "candidate": "Job is queued", "role": "Live status"},
    }
    return {"id": "example", "kind": kind, "state": states[kind], "data_class": "synthetic"}


def reply(kind="claim", values=(0.03, 0.04), model=mod.EVALUATED_MODEL):
    return {"answers": {k: {"type": "noul", "noul": v}
                        for k, v in zip(mod.QUESTIONS[kind], values)},
            "jev_model": model, "usage": {"input_tokens": 123, "output_tokens": 20}}


@pytest.mark.parametrize("kind,values,expected", [
    ("claim", (0.02, 0.02), "revise"),
    ("claim", (0.95, 0.97), "supported_candidate"),
    ("claim", (0.95, 0.6), "ordinary_review"),
    ("check", (0.02, 0.98), "limitation"),
    ("check", (0.96, 0.94), "discriminating_candidate"),
    ("propagation", (0.97, 0.02), "review_change"),
    ("propagation", (0.97, 0.99), "historical_candidate"),
    ("propagation", (0.02, 0.02), "current_or_unrelated_candidate"),
    ("propagation", (0.6, 0.02), "ordinary_review"),
])
def test_routes(kind, values, expected):
    receipt = mod.evaluate(item(kind), lambda *_: reply(kind, values))
    assert receipt["action"] == expected
    assert receipt["usage"] == {"input_tokens": 123, "output_tokens": 20}


def test_outage_does_not_print_exception_payload():
    def fail(*_):
        raise RuntimeError("secret-and-private-source")
    receipt = mod.evaluate(item(), fail)
    assert receipt["action"] == "ordinary_review"
    assert "secret-and-private-source" not in json.dumps(receipt)
    assert receipt["status"] == "unavailable"


@pytest.mark.parametrize("value", [True, "0.99", -0.1, 1.1, float("nan"), float("inf")])
def test_malformed_never_passes(value):
    receipt = mod.evaluate(item(), lambda *_: reply(values=(value, 0.99)))
    assert receipt["action"] == "ordinary_review"
    json.dumps(receipt, allow_nan=False)


def test_missing_answer_never_passes():
    data = reply()
    data["answers"].pop("preserved")
    assert mod.evaluate(item(), lambda *_: data)["action"] == "ordinary_review"


def test_model_drift_keeps_raw_readings_but_reviews():
    receipt = mod.evaluate(item(), lambda *_: reply(values=(0.99, 0.99), model="different-model"))
    assert receipt["status"] == "model_drift"
    assert receipt["action"] == "ordinary_review"
    assert receipt["answers"]["supported"]["noul"] == 0.99


def test_complete_passage_transmitted_without_truncation():
    data = item()
    data["state"]["source"] = "A long context. " * 150 + "Only while connected."
    seen = []
    def ask(state, _):
        seen.append(state)
        return reply()
    receipt = mod.evaluate(data, ask)
    assert seen[0]["source"] == data["state"]["source"]
    changed = item()
    assert receipt["input_sha256"] != mod.digest(changed)


def test_oversize_rejected_before_call():
    data = item()
    data["state"]["source"] = "x" * mod.MAX_BYTES
    with pytest.raises(ValueError):
        mod.evaluate(data, lambda *_: pytest.fail("must not call"))


def test_missing_negative_case_rejected_before_call():
    data = item("check")
    del data["state"]["under_negative"]
    with pytest.raises(ValueError):
        mod.evaluate(data, lambda *_: pytest.fail("must not call"))


def test_offline_cli_leaves_input_unchanged(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps(item()))
    before = source.read_bytes()
    result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--offline"],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    receipt = json.loads(result.stdout)
    assert receipt["action"] == "ordinary_review"
    assert source.read_bytes() == before
    assert "The job" not in result.stdout

@pytest.mark.parametrize('kind,values,expected', [
    ('claim', (0.9, 0.9), 'supported_candidate'),
    ('claim', (0.899, 0.99), 'ordinary_review'),
    ('claim', (0.2, 0.99), 'revise'),
    ('claim', (0.201, 0.99), 'ordinary_review'),
    ('propagation', (0.1, 0.1), 'current_or_unrelated_candidate'),
    ('propagation', (0.19, 0.01), 'ordinary_review'),
    ('propagation', (0.9, 0.1), 'review_change'),
])
def test_boundaries(kind, values, expected):
    assert mod.route(kind, reply(kind, values)['answers']) == expected


def test_missing_model_routes_to_review():
    assert mod.evaluate(item(), lambda *_: reply(model=None))['status'] == 'model_drift'


@pytest.mark.parametrize('classification', ['private', 'unclassified'])
def test_private_text_never_reaches_backend(classification):
    data = item(); data['data_class'] = classification
    result = mod.evaluate(data, lambda *_: pytest.fail('must not send'))
    assert result['error'] == 'data_not_authorised'


def test_whitespace_and_duplicate_keys_rejected(tmp_path):
    data = item(); data['state']['source'] = '  '
    with pytest.raises(ValueError): mod.validate(data)
    p = tmp_path/'in.json'; p.write_text('{"id":"one","id":"two"}')
    with pytest.raises(ValueError): mod.read_item(p)


def test_nested_and_oversize_cli_returns_receipt(tmp_path):
    p = tmp_path/'in.json'
    for raw in ['[' * 11000 + ']' * 11000, 'x' * (mod.MAX_BYTES + 1)]:
        p.write_text(raw)
        result = subprocess.run([sys.executable, str(SCRIPT), '--input', str(p), '--offline'], capture_output=True, text=True, timeout=10)
        assert result.returncode == 2
        assert json.loads(result.stdout)['status'] == 'invalid_input'
        assert result.stderr == ''


def test_nan_usage_becomes_invalid_reply():
    data = reply(); data['usage']['input_tokens'] = float('nan')
    receipt = mod.evaluate(item(), lambda *_: data)
    assert receipt['status'] == 'invalid_reply'
    json.dumps(receipt, allow_nan=False)


def fake_backend(tmp_path, monkeypatch):
    package = tmp_path/'jevkit';package.mkdir()
    for name in mod.BACKEND_FILES:
        (package/name).write_text('')
    hashes = {name: mod.hashlib.sha256((package/name).read_bytes()).hexdigest() for name in mod.BACKEND_FILES}
    monkeypatch.setattr(mod, 'BACKEND_SHA256', mod.digest(hashes))
    return package


def test_backend_drift_checked_before_import_or_key(tmp_path, monkeypatch):
    package = fake_backend(tmp_path, monkeypatch)
    (package/'client.py').write_text('raise RuntimeError("must never execute")')
    monkeypatch.setattr(mod, 'load_client', lambda *_: pytest.fail('must not import'))
    monkeypatch.setattr(mod.subprocess, 'run', lambda *_args, **_kwargs: pytest.fail('must not read key'))
    result = mod.evaluate(item(), lambda *_: mod.backend(tmp_path, 1))
    assert result['error'] == 'backend_drift'


def test_endpoint_guard_before_key(tmp_path, monkeypatch):
    fake_backend(tmp_path, monkeypatch)
    monkeypatch.setenv('TYPESAFE_BASE_URL', 'https://example.invalid')
    monkeypatch.setattr(mod, 'load_client', lambda *_: pytest.fail('must not import'))
    monkeypatch.setattr(mod.subprocess, 'run', lambda *_args, **_kwargs: pytest.fail('must not read key'))
    result = mod.evaluate(item(), lambda *_: mod.backend(tmp_path, 1))
    assert result['error'] == 'alternate_endpoint_not_supported'


def test_missing_credential(tmp_path, monkeypatch):
    fake_backend(tmp_path, monkeypatch)
    monkeypatch.delenv('TYPESAFE_BASE_URL', raising=False)
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.setattr(mod, 'load_client', lambda *_: None)
    monkeypatch.setattr(mod.subprocess, 'run', lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, b'', b'private diagnostic'))
    result = mod.evaluate(item(), lambda *_: mod.backend(tmp_path, 1))
    assert result['error'] == 'credential_unavailable'
    assert 'private diagnostic' not in json.dumps(result)


def test_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENCAIRN_JEV_ROOT', raising=False)
    monkeypatch.setattr(mod.Path, 'home', lambda: tmp_path)
    assert mod.configured_root() is None
    (tmp_path/'.claude').mkdir()
    p = tmp_path/'.claude/semantic-check.json';p.write_text('{"backend_root":"/reviewed/path"}')
    assert mod.configured_root() == '/reviewed/path'
    p.write_text('{broken')
    with pytest.raises(mod.Unavailable): mod.configured_root()


def test_receipt_verifier_detects_changed_bytes_and_target(tmp_path, monkeypatch):
    fake_backend(tmp_path, monkeypatch)
    data=item();p=tmp_path/'input.json';p.write_text(json.dumps(data))
    parsed, raw_hash=mod.read_item(p)
    response=reply(); response['backend_sha256']=mod.BACKEND_SHA256
    receipt=mod.evaluate(parsed,lambda *_:response,raw_hash)
    target=tmp_path/'note.md';target.write_text(data['state']['claim'])
    assert mod.verify(receipt,parsed,raw_hash,tmp_path,target)['status']=='bindings_match'
    target.write_text('Different claim')
    with pytest.raises(ValueError): mod.verify(receipt,parsed,raw_hash,tmp_path,target)
    p.write_text(json.dumps(data,indent=2));_, changed_hash=mod.read_item(p)
    with pytest.raises(ValueError): mod.verify(receipt,parsed,changed_hash,tmp_path)
    receipt['questions_sha256']='0'*64
    with pytest.raises(ValueError): mod.verify(receipt,parsed,raw_hash,tmp_path)


@pytest.mark.parametrize('code', ['timeout','http_401','auth_failed','credits_exhausted','rate_limited','invalid_response'])
def test_failure_codes_are_static(code):
    class Error(Exception): pass
    def fail(*_):
        error=Error('secret'); error.code=code; raise error
    result=mod.evaluate(item(),fail)
    assert result['error']==code
    assert 'secret' not in json.dumps(result)
