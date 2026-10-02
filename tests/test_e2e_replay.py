"""
End-to-end, offline: record an agent through OTel/OTLP into the tracking server, then replay it
through the OpenAI-compatible replay endpoint with zero calls to the (fake) provider.
"""
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI, Request

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "openai_tools.py"
FINAL_ANSWER = "It is 75F and sunny in Tokyo."


class ServerThread:
    def __init__(self, app):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        self.thread.start()
        deadline = time.time() + 15
        while not self.server.started:
            if time.time() > deadline:
                raise RuntimeError("server did not start")
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=10)


def fake_provider():
    """An OpenAI-compatible upstream: asks for the weather tool, then answers."""
    app = FastAPI()
    app.state.calls = 0

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        body = await request.json()
        app.state.calls += 1
        if any(m.get("role") == "tool" for m in body["messages"]):
            message, finish = {"role": "assistant", "content": FINAL_ANSWER}, "stop"
        else:
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "get_weather", "arguments": '{"location": "Tokyo"}'},
            }]}
            finish = "tool_calls"
        return {
            "id": f"chatcmpl-{app.state.calls}", "object": "chat.completion", "created": 1,
            "model": body["model"], "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }

    return app


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("AGENT_REPLAY_DB", str(tmp_path_factory.mktemp("db") / "traces.db"))
    mp.setenv("HF_TOKEN", "test-key")  # never read the developer's real token from .env
    mp.setenv("EXAMPLE_MODEL", "fake-model")
    mp.setenv("PYTHONIOENCODING", "utf-8")
    for var in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "AGENT_REPLAY_SESSION_ID"):
        mp.delenv(var, raising=False)

    sys.modules.pop("agent_replay.server.app", None)
    import agent_replay.server.app as tracking_app

    provider = fake_provider()
    with ServerThread(provider) as upstream, ServerThread(tracking_app.app) as tracking:
        yield {"upstream": upstream, "provider": provider, "tracking": tracking, "store": tracking_app.store}
    mp.undo()


def _record(env) -> str:
    proc = subprocess.run(
        [sys.executable, str(EXAMPLE)],
        env={**os.environ,
             "AGENT_REPLAY_TRACKING_URI": env["tracking"].url,
             "OPENAI_BASE_URL": f"{env['upstream'].url}/v1"},
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert FINAL_ANSWER in proc.stdout
    history = httpx.get(f"{env['tracking'].url}/api/agents/openai_weather_tools").json()
    return history[-1]["record_id"]


@pytest.fixture(scope="module")
def record_id(env):
    return _record(env)


def test_recording_captures_full_graph(env, record_id):
    assert env["provider"].state.calls == 2
    graph = env["store"].load(record_id)
    models = [n for n in graph.nodes.values() if n.kind.name == "MODEL" and n.metadata.replayable]
    tools = [n for n in graph.nodes.values() if n.kind.name == "TOOL"]
    assert len(models) == 2 and len(tools) == 1
    assert models[0].output["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert models[1].output["choices"][0]["message"]["content"] == FINAL_ANSWER
    assert tools[0].input == {"location": "Tokyo"}
    assert graph.metadata.attributes["entrypoint"]["argv"][0].endswith("openai_tools.py")
    assert any(s["name"].startswith("openinference.instrumentation")
               for s in graph.metadata.attributes["instrumentation_scopes"])


def test_replay_serves_recording_without_provider_calls(env, record_id):
    calls_before = env["provider"].state.calls
    result = httpx.post(f"{env['tracking'].url}/api/runs/{record_id}/replay", json={}, timeout=180).json()
    assert result["status"] == "success", result["logs"]
    assert FINAL_ANSWER in result["logs"]
    assert result["report"]["served_steps"] == result["report"]["total_steps"] == 2
    assert result["report"]["tool_check"] == "compared"
    assert result["divergences"] == []
    assert env["provider"].state.calls == calls_before


def test_transient_fault_is_retried_by_the_client(env, record_id):
    result = httpx.post(f"{env['tracking'].url}/api/runs/{record_id}/replay",
                        json={"faults": [{"step": 2, "status": 503}]}, timeout=180).json()
    assert result["status"] == "success", result["logs"]
    assert {"type": "fault_injected", "step": 2, "status": 503, "api": "chat"} in result["report"]["events"]


def test_persistent_fault_fails_the_run(env, record_id):
    result = httpx.post(f"{env['tracking'].url}/api/runs/{record_id}/replay",
                        json={"faults": [{"step": 1, "status": 500, "persistent": True}]}, timeout=180).json()
    assert result["status"] == "error"
    assert "CRITICAL SYSTEM HALT" in result["logs"]


def test_strict_mode_reports_expected_and_got(env, record_id):
    tracking = env["tracking"].url
    session = httpx.post(f"{tracking}/api/replay-sessions", json={"record_id": record_id, "match": "STRICT"}).json()
    response = httpx.post(f"{session['base_url']}/chat/completions", json={
        "model": "fake-model", "messages": [{"role": "user", "content": "Something else entirely"}],
    })
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["type"] == "replay_divergence"
    assert body["got"][0]["content"] == "Something else entirely"
    assert "Tokyo" in body["expected"][0]["content"]
    report = httpx.post(f"{tracking}/api/replay-sessions/{session['session_id']}/finish").json()
    assert report["divergences"][0]["severity"] == "error"


def test_streaming_replay_with_openai_sdk(env, record_id):
    from openai import OpenAI

    tracking = env["tracking"].url
    session = httpx.post(f"{tracking}/api/replay-sessions", json={"record_id": record_id}).json()
    client = OpenAI(base_url=session["base_url"], api_key="agent-replay")

    tool_names = [
        tc.function.name
        for chunk in client.chat.completions.create(model="fake-model", messages=[{"role": "user", "content": "x"}], stream=True)
        for choice in chunk.choices
        for tc in (choice.delta.tool_calls or [])
    ]
    assert tool_names == ["get_weather"]

    text = "".join(
        choice.delta.content or ""
        for chunk in client.chat.completions.create(model="fake-model", messages=[{"role": "user", "content": "x"}], stream=True)
        for choice in chunk.choices
    )
    assert text == FINAL_ANSWER
    httpx.post(f"{tracking}/api/replay-sessions/{session['session_id']}/finish")
