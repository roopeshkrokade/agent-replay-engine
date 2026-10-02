import sys
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from agent_replay.compiler import Instruction, InstructionKind
from agent_replay.ir import NodeKind
from agent_replay.runtime import ReplayScheduler
from tests import SAMPLE_TRACE


def _instruction(node_id, prompt):
    return Instruction(InstructionKind.RETURN_RECORDED, node_id,
                       {"messages": [{"role": "user", "content": prompt}]}, f"answer {prompt}", NodeKind.MODEL)


def test_scheduler_serves_out_of_order_requests_by_content():
    scheduler = ReplayScheduler([_instruction("n1", "A"), _instruction("n2", "B"), _instruction("n3", "C")])
    served = [scheduler.resolve({"messages": [{"role": "user", "content": p}]}, [NodeKind.MODEL]) for p in "CAB"]
    assert [r.instruction.node_id for r in served] == ["n3", "n1", "n2"]
    assert not any(r.diverged for r in served)


def test_scheduler_relaxed_falls_back_and_strict_refuses():
    request = {"messages": [{"role": "user", "content": "changed prompt"}]}
    relaxed = ReplayScheduler([_instruction("n1", "A")]).resolve(request, [NodeKind.MODEL])
    assert relaxed.instruction.node_id == "n1" and relaxed.diverged
    strict = ReplayScheduler([_instruction("n1", "A")], strict=True).resolve(request, [NodeKind.MODEL])
    assert strict.instruction is None and strict.expected[0]["content"] == "A"


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_REPLAY_DB", str(tmp_path / "traces.db"))
    monkeypatch.setenv("AGENT_REPLAY_ALLOWED_HOSTS", "testserver")
    sys.modules.pop("agent_replay.server.app", None)
    import agent_replay.server.app as tracking_app
    yield tracking_app
    sys.modules.pop("agent_replay.server.app", None)


def _record_sample(app_module, run_id="run-1") -> str:
    """Store the sample trace as if it had arrived over OTLP for `run_id`."""
    import json
    with open(SAMPLE_TRACE, encoding="utf-8") as f:
        app_module.store.add_spans(run_id, json.load(f))
    client = TestClient(app_module.app)
    response = client.post(f"/api/runs/{run_id}/end", json={"agent_id": "sample", "agent_name": "Sample"})
    assert response.status_code == 200, response.text
    return response.json()["record_id"]


def test_token_protects_api_and_otlp(server, monkeypatch):
    monkeypatch.setenv("AGENT_REPLAY_TOKEN", "s3cret")
    client = TestClient(server.app)
    assert client.get("/api/agents").status_code == 401
    assert client.post("/v1/traces", content=b"").status_code == 401
    assert client.get("/api/agents", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/agents", headers={"Authorization": "Bearer s3cret"}).status_code == 200
    # Replay endpoints are addressed by an unguessable session id instead.
    assert client.get("/replay/rs_unknown/v1/models").status_code == 404


def test_untrusted_host_header_is_rejected(server):
    """Blocks DNS-rebinding pages from driving a localhost server through the browser."""
    client = TestClient(server.app, base_url="http://evil.example")
    assert client.get("/api/agents").status_code == 400


def test_serve_refuses_public_bind_without_token(server, monkeypatch):
    monkeypatch.delenv("AGENT_REPLAY_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="Refusing to listen"):
        server.serve(host="0.0.0.0", port=5999)


def test_set_entrypoint_makes_old_records_replayable(server, tmp_path):
    record_id = _record_sample(server)
    client = TestClient(server.app)
    assert "set-entrypoint" in client.post(f"/api/runs/{record_id}/replay", json={}).json()["detail"]

    script = tmp_path / "agent.py"
    script.write_text("print('replayed agent ran')\n", encoding="utf-8")
    response = client.put(f"/api/runs/{record_id}/entrypoint", json={"argv": ["python", "agent.py"], "cwd": str(tmp_path)})
    assert response.status_code == 200
    entrypoint = response.json()["entrypoint"]
    assert entrypoint["executable"] == sys.executable and entrypoint["argv"] == [str(script.resolve())]

    result = client.post(f"/api/runs/{record_id}/replay", json={}).json()
    assert "replayed agent ran" in result["logs"]


def test_recompile_and_span_lifecycle(server):
    record_id = _record_sample(server, run_id="run-keep")
    store = server.store
    store.add_spans("orphan", [{"context": {"trace_id": "t", "span_id": "s"}}])

    client = TestClient(server.app)
    assert client.post(f"/api/runs/{record_id}/recompile").json()["nodes"] == 2

    assert store.prune_spans(timedelta(0)) == 1  # the orphan goes, the record's spans stay
    assert store.get_spans("orphan") == [] and store.get_spans("run-keep")

    assert client.delete(f"/api/runs/{record_id}").status_code == 204
    assert store.get_spans("run-keep") == []  # deleting a record deletes its raw spans
