"""
Provider-compatible replay endpoints. During replay, the agent's LLM clients are pointed here via
their base-URL settings (OPENAI_BASE_URL, ANTHROPIC_BASE_URL); every request is answered from the
recording, so no provider is called and no client library is patched.

  /replay/{session}/v1/chat/completions   OpenAI Chat Completions (+ streaming)
  /replay/{session}/v1/responses          OpenAI Responses (+ streaming)
  /replay/{session}/v1/messages           Anthropic Messages (+ streaming)
  /replay/{session}/v1/embeddings         OpenAI Embeddings
"""
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Set, Union

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agent_replay.adapters.otel import OTelSpanAdapter
from agent_replay.compiler import Fault, IRCompiler, PlanCompiler, ReplaySession
from agent_replay.ir import ExecutionGraph, NodeKind
from agent_replay.runtime import ReplayScheduler, canonical_request
from agent_replay.runtime.divergence import diff_tools
from agent_replay.compiler import Instruction
from . import wire_formats as wf

SESSION_TTL_SECONDS = float(os.environ.get("AGENT_REPLAY_SESSION_TTL", "3600"))
# Tells OpenAI/Anthropic SDKs not to retry, so a replayed error surfaces exactly once, as recorded.
NO_RETRY = {"x-should-retry": "false"}


@dataclass
class ReplaySessionState:
    session_id: str
    record_id: str
    graph: ExecutionGraph
    session: ReplaySession
    scheduler: ReplayScheduler
    created_at: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)
    fired_faults: Set[int] = field(default_factory=set)
    divergences: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_steps(self) -> int:
        return self.scheduler.total

    def take_fault(self, step: int) -> Optional[Fault]:
        for fault in self.session.faults:
            if fault.step == step and (fault.persistent or step not in self.fired_faults):
                self.fired_faults.add(step)
                return fault
        return None


_sessions: Dict[str, ReplaySessionState] = {}
_sessions_lock = threading.Lock()


def create_session(graph: ExecutionGraph, record_id: str, match: str = "RELAXED", faults=(), store=None) -> ReplaySessionState:
    match = (match or "RELAXED").upper()
    if match not in ("RELAXED", "STRICT"):
        raise ValueError(f"Unknown match mode '{match}'; use RELAXED or STRICT.")
    if store is not None:
        prune_sessions(store)
    session = ReplaySession(mode="CACHE", match=match, faults=tuple(_parse_fault(f) for f in faults or ()))
    plan = PlanCompiler().compile(graph, session)
    # Model and embedding calls are served from the recording; tools execute live and are diffed afterwards.
    served = [i for i in plan.instructions if i.node_kind in (NodeKind.MODEL, NodeKind.EMBEDDING, None)]
    state = ReplaySessionState(
        session_id=f"rs_{uuid.uuid4().hex}",
        record_id=record_id,
        graph=graph,
        session=session,
        scheduler=ReplayScheduler(served, strict=match == "STRICT"),
    )
    with _sessions_lock:
        _sessions[state.session_id] = state
    return state


def prune_sessions(store, max_age: float = SESSION_TTL_SECONDS) -> int:
    """Drop sessions that were opened but never finished (e.g. the agent crashed), and their spans."""
    cutoff = time.time() - max_age
    with _sessions_lock:
        stale = [sid for sid, s in _sessions.items() if s.created_at < cutoff]
        for sid in stale:
            _sessions.pop(sid)
    for sid in stale:
        store.delete_spans(sid)
    return len(stale)


def finish_session(session_id: str, store) -> Dict[str, Any]:
    """Close a session and report what was served, injected and diverged."""
    with _sessions_lock:
        state = _sessions.pop(session_id, None)
    if state is None:
        raise KeyError(session_id)

    divergences = list(state.divergences)
    unserved = state.scheduler.unserved()
    if unserved:
        stopped_early = any(d.get("severity") == "error" for d in divergences)
        divergences.append({
            "type": "under_execution",
            "severity": "warning",
            "reason": (f"{len(unserved)} of {state.total_steps} recorded calls were never requested"
                       + (" (the run stopped at the first error)." if stopped_early else ".")),
            "node_ids": [i.node_id for i in unserved],
            "expected": canonical_request(unserved[0].expected_input),
            "got": None,
        })

    tool_check = "skipped: replay run emitted no spans (is autolog() enabled?)"
    replay_spans = store.get_spans(session_id)
    if replay_spans:
        replay_graph = IRCompiler().compile(OTelSpanAdapter().parse_spans(replay_spans))
        divergences.extend(diff_tools(state.graph, replay_graph))
        tool_check = "compared"
    store.delete_spans(session_id)

    return {
        "session_id": session_id,
        "record_id": state.record_id,
        "match": state.session.match,
        "served_steps": state.scheduler.served_count,
        "total_steps": state.total_steps,
        "complete": state.scheduler.served_count == state.total_steps,
        "tool_check": tool_check,
        "events": state.events,
        "divergences": divergences,
    }


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/replay/{session_id}/v1/models", summary="Replay: list models")
    def list_models(session_id: str):
        state = _get(session_id)
        models = sorted({
            str(i.expected_input.get("model"))
            for i in state.scheduler.instructions
            if isinstance(i.expected_input, Mapping) and i.expected_input.get("model")
        }) or ["agent-replay"]
        return {"object": "list", "data": [{"id": m, "object": "model", "owned_by": "agent-replay"} for m in models]}

    @router.post("/replay/{session_id}/v1/chat/completions", summary="Replay: OpenAI chat completions")
    async def chat_completions(session_id: str, request: Request):
        body = await request.json()
        served = _serve(_get(session_id), wf.CHAT, wf.chat_request(body), (NodeKind.MODEL,))
        if not isinstance(served, Instruction):
            return served
        completion = wf.to_chat_completion(served.output_to_return, body.get("model"), served.node_id)
        if body.get("stream"):
            include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
            return _sse(wf.chat_stream(completion, include_usage))
        return completion

    @router.post("/replay/{session_id}/v1/responses", summary="Replay: OpenAI responses")
    async def responses(session_id: str, request: Request):
        body = await request.json()
        served = _serve(_get(session_id), wf.RESPONSES, wf.responses_request(body), (NodeKind.MODEL,))
        if not isinstance(served, Instruction):
            return served
        completion = wf.to_chat_completion(served.output_to_return, body.get("model"), served.node_id)
        response = wf.to_response(completion, body.get("model"), served.node_id)
        return _sse(wf.responses_stream(response)) if body.get("stream") else response

    @router.post("/replay/{session_id}/v1/messages", summary="Replay: Anthropic messages")
    async def messages(session_id: str, request: Request):
        body = await request.json()
        served = _serve(_get(session_id), wf.MESSAGES, wf.anthropic_request(body), (NodeKind.MODEL,))
        if not isinstance(served, Instruction):
            return served
        completion = wf.to_chat_completion(served.output_to_return, body.get("model"), served.node_id)
        message = wf.to_anthropic_message(completion, body.get("model"))
        return _sse(wf.anthropic_stream(message)) if body.get("stream") else message

    @router.post("/replay/{session_id}/v1/embeddings", summary="Replay: OpenAI embeddings")
    async def embeddings(session_id: str, request: Request):
        body = await request.json()
        served = _serve(_get(session_id), wf.EMBEDDINGS, wf.embeddings_request(body), (NodeKind.EMBEDDING,))
        if not isinstance(served, Instruction):
            return served
        return wf.to_embeddings(served.output_to_return, body.get("model"), body.get("encoding_format"))

    return router


def _serve(state: ReplaySessionState, api: str, request_input: Mapping[str, Any], kinds) -> Union[Instruction, JSONResponse]:
    """Resolve one request against the recording; returns the instruction to render, or an error response."""
    with state.lock:
        step = state.scheduler.served_count + 1
        fault = state.take_fault(step)
        if fault is not None:
            state.events.append({"type": "fault_injected", "step": step, "status": fault.status, "api": api})
            # No x-should-retry header: clients apply their normal retry policy to injected faults.
            return JSONResponse(status_code=fault.status, content=wf.error_body(api, fault.message, "injected_fault"))

        resolution = state.scheduler.resolve(request_input, kinds)
        divergence = {
            "step": step,
            "api": api,
            "reason": resolution.reason,
            "expected": resolution.expected,
            "got": canonical_request(request_input),
        }
        if resolution.instruction is None:
            divergence.update(type="over_execution" if resolution.expected is None else "request_mismatch", severity="error")
            state.divergences.append(divergence)
            content = wf.error_body(api, f"Replay Divergence: {resolution.reason}", "replay_divergence")
            content.update(expected=divergence["expected"], got=divergence["got"])
            return JSONResponse(status_code=400, content=content, headers=NO_RETRY)

        instruction = resolution.instruction
        if resolution.diverged:
            state.divergences.append({**divergence, "type": "request_mismatch", "severity": "warning", "node_id": instruction.node_id})
        output = instruction.output_to_return
        if isinstance(output, Mapping) and "recorded_error" in output:
            error = output["recorded_error"]
            state.events.append({"type": "replayed_error", "step": step, "node_id": instruction.node_id,
                                 "status": error["status"], "api": api})
            content = error.get("body") if isinstance(error.get("body"), dict) else wf.error_body(api, error["message"], "replayed_error")
            return JSONResponse(status_code=error["status"], content=content, headers=NO_RETRY)
        state.events.append({"type": "served", "step": step, "node_id": instruction.node_id, "api": api})
        return instruction


def _sse(events) -> StreamingResponse:
    return StreamingResponse(events, media_type="text/event-stream")


def _get(session_id: str) -> ReplaySessionState:
    with _sessions_lock:
        state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown replay session '{session_id}'.")
    return state


def _parse_fault(raw: Any) -> Fault:
    if isinstance(raw, Fault):
        return raw
    if not isinstance(raw, Mapping) or "step" not in raw:
        raise ValueError(f"Invalid fault {raw!r}; expected e.g. {{'step': 2, 'status': 503}}.")
    return Fault(
        step=int(raw["step"]),
        status=int(raw.get("status", 503)),
        message=str(raw.get("message", Fault.message)),
        persistent=bool(raw.get("persistent", False)),
    )
