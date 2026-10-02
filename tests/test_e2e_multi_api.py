"""
End-to-end, offline, across every API the gateway serves: OpenAI chat (streamed), Responses,
Embeddings, Anthropic Messages with a tool round trip, a recorded provider error, and concurrent
calls. The replay must print exactly what the recording printed, with zero provider calls.
"""
import base64
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from tests.test_e2e_replay import ServerThread

AGENT = Path(__file__).parent / "agents" / "multi_api_agent.py"
VECTORS = {"tokyo": [0.1, 0.2, 0.3], "osaka": [0.4, 0.5, 0.6]}


def fake_provider():
    app = FastAPI()
    app.state.calls = 0

    def completion(text):
        return {"id": "chatcmpl-x", "object": "chat.completion", "created": 1, "model": "fake-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6}}

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        body = await request.json()
        app.state.calls += 1
        if body["model"] == "rate-limited":
            return JSONResponse(status_code=429, content={"error": {"message": "Slow down", "type": "rate_limit_error"}})
        prompt = body["messages"][-1]["content"]
        if not body.get("stream"):
            return completion(f"answer to {prompt}")

        def events():
            for word in ["old ", "pond ", "frog"]:
                chunk = {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "fake-model",
                         "choices": [{"index": 0, "delta": {"content": word}, "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
            done = {"id": "c", "object": "chat.completion.chunk", "created": 1, "model": "fake-model",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            yield f"data: {json.dumps(done)}\n\ndata: [DONE]\n\n"
        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/v1/responses")
    async def responses(request: Request):
        app.state.calls += 1
        return {"id": "resp_1", "object": "response", "created_at": 1, "status": "completed", "model": "fake-model",
                "output": [{"type": "message", "id": "msg_1", "status": "completed", "role": "assistant",
                            "content": [{"type": "output_text", "text": "Sunny all week.", "annotations": []}]}],
                "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
                "usage": {"input_tokens": 3, "output_tokens": 3, "total_tokens": 6,
                          "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}

    @app.post("/v1/embeddings")
    async def embeddings(request: Request):
        body = await request.json()
        app.state.calls += 1
        data = []
        for i, text in enumerate(body["input"]):
            vector = VECTORS[text]
            encoded = base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode()
            data.append({"object": "embedding", "index": i,
                         "embedding": encoded if body.get("encoding_format") == "base64" else vector})
        return {"object": "list", "model": "fake-embed", "data": data, "usage": {"prompt_tokens": 2, "total_tokens": 2}}

    @app.post("/v1/messages")
    async def messages(request: Request):
        body = await request.json()
        app.state.calls += 1
        last = body["messages"][-1]["content"]
        if isinstance(last, list) and any(b.get("type") == "tool_result" for b in last):
            content, stop = [{"type": "text", "text": "It is 75F in Tokyo."}], "end_turn"
        else:
            content, stop = [{"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "Tokyo"}}], "tool_use"
        return {"id": "msg_1", "type": "message", "role": "assistant", "model": "fake-claude", "content": content,
                "stop_reason": stop, "stop_sequence": None, "usage": {"input_tokens": 5, "output_tokens": 5}}

    return app


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("AGENT_REPLAY_DB", str(tmp_path_factory.mktemp("db") / "traces.db"))
    mp.setenv("PYTHONIOENCODING", "utf-8")
    for var in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "ANTHROPIC_BASE_URL", "AGENT_REPLAY_SESSION_ID"):
        mp.delenv(var, raising=False)
    sys.modules.pop("agent_replay.server.app", None)
    import agent_replay.server.app as tracking_app

    provider = fake_provider()
    with ServerThread(provider) as upstream, ServerThread(tracking_app.app) as tracking:
        yield {"upstream": upstream, "provider": provider, "tracking": tracking, "store": tracking_app.store}
    mp.undo()
    sys.modules.pop("agent_replay.server.app", None)


def _results(output: str):
    return [line for line in output.splitlines() if line.startswith("RESULT ")]


@pytest.fixture(scope="module")
def recording(env):
    proc = subprocess.run(
        [sys.executable, str(AGENT)],
        env={**os.environ,
             "AGENT_REPLAY_TRACKING_URI": env["tracking"].url,
             "OPENAI_BASE_URL": f"{env['upstream'].url}/v1",
             "ANTHROPIC_BASE_URL": env["upstream"].url,
             "OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": "sk-ant-test"},
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    record_id = httpx.get(f"{env['tracking'].url}/api/agents/multi_api_agent").json()[-1]["record_id"]
    return {"record_id": record_id, "results": _results(proc.stdout)}


def test_recording_output(env, recording):
    assert recording["results"] == [
        "RESULT chat_stream: old pond frog",
        "RESULT responses: Sunny all week.",
        "RESULT embeddings: [0.4, 0.5, 0.6]",
        "RESULT anthropic_tool: get_weather({'city': 'Tokyo'})",
        "RESULT anthropic_final: It is 75F in Tokyo.",
        "RESULT error: RateLimitError 429",
        "RESULT parallel: [('parallel A', 'answer to parallel A'), ('parallel B', 'answer to parallel B'), "
        "('parallel C', 'answer to parallel C')]",
    ]
    graph = env["store"].load(recording["record_id"])
    notes = {n.metadata.span.get("name"): n.metadata.replay_note for n in graph.nodes.values() if not n.metadata.replayable}
    assert notes == {}, notes


@pytest.mark.parametrize("match", ["RELAXED", "STRICT"])
def test_replay_reproduces_every_api_without_provider_calls(env, recording, match):
    calls_before = env["provider"].state.calls
    result = httpx.post(f"{env['tracking'].url}/api/runs/{recording['record_id']}/replay",
                        json={"match": match}, timeout=180).json()
    assert result["status"] == "success", result["logs"]
    assert _results(result["logs"]) == recording["results"]
    report = result["report"]
    assert report["served_steps"] == report["total_steps"] == 9
    assert [e["status"] for e in report["events"] if e["type"] == "replayed_error"] == [429]
    assert result["divergences"] == [], result["divergences"]
    assert env["provider"].state.calls == calls_before
