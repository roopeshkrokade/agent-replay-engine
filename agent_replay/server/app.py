import os
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent_replay.adapters.otel import OTelSpanAdapter
from agent_replay.replay import replay_env, session_url
from agent_replay.compiler import IRCompiler
from agent_replay.ir import NodeKind
from agent_replay.server import otlp, replay_gateway, security
from agent_replay.storage.db import SQLiteGraphStore

BASE_DIR = Path(__file__).resolve().parent
# The React dashboard is built into the package (frontend/ -> `npm run build`), like MLflow's UI.
UI_DIR = Path(os.environ.get("AGENT_REPLAY_UI_DIR", BASE_DIR / "ui"))

app = FastAPI(
    title="Agent Replay API",
    description="Tracking server: receives OTel spans, compiles them into versioned execution graphs, and replays them.",
    version="2.0.0"
)
security.install(app)

store = SQLiteGraphStore(os.environ.get("AGENT_REPLAY_DB", ".agent-replay/traces.db"))
SPAN_RETENTION = timedelta(hours=float(os.environ.get("AGENT_REPLAY_SPAN_RETENTION_HOURS", "24")))
store.prune_spans(SPAN_RETENTION)

app.include_router(otlp.create_router(store))
app.include_router(replay_gateway.create_router())

# ---------------------------------------------------------
# 1. AGENT MANAGEMENT APIs
# ---------------------------------------------------------
@app.get("/api/agents", response_model=List[Dict], summary="List Unique Agents")
def list_unique_agents():
    try:
        return store.get_unique_agents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/{agent_id}", response_model=List[Dict], summary="Get Agent Version History")
def get_agent_history(agent_id: str):
    try:
        history = store.get_agent_history(agent_id)
        if not history:
            raise HTTPException(status_code=404, detail=f"No history found for agent: {agent_id}")
        return history
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Entire Agent")
def delete_entire_agent(agent_id: str):
    try:
        history = store.get_agent_history(agent_id)
        if not history:
            raise HTTPException(status_code=404, detail="Agent not found.")
        for record in history:
            store.delete(record["record_id"])
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# 2. RECORDING APIs (called by agent_replay.end_run)
# ---------------------------------------------------------
class RunEnd(BaseModel):
    agent_id: str
    agent_name: str
    kind: str = "record"
    status: str = "FINISHED"
    entrypoint: Optional[Dict[str, Any]] = None

@app.post("/api/runs/{run_id}/end", summary="Finish a run and compile its spans into a new agent version")
def end_run(run_id: str, body: RunEnd):
    if body.kind == "replay":
        # Replay spans stay until the replay session is finished and diffed.
        return {"run_id": run_id, "kind": "replay"}

    spans = store.get_spans(run_id)
    if not spans:
        raise HTTPException(
            status_code=400,
            detail=f"No spans received for run '{run_id}'. Is an OTel instrumentor installed for your framework?",
        )
    graph = IRCompiler().compile(
        OTelSpanAdapter().parse_spans(spans),
        attributes={"run_id": run_id, "run_status": body.status, "entrypoint": body.entrypoint},
    )
    record_id = store.save(graph, agent_id=body.agent_id, agent_name=body.agent_name)
    store.prune_spans(SPAN_RETENTION)
    models = [n for n in graph.nodes.values() if n.kind == NodeKind.MODEL]
    return {
        "record_id": record_id,
        "spans": len(spans),
        "model_calls": sum(1 for n in models if n.metadata.replayable),
        "tool_calls": sum(1 for n in graph.nodes.values() if n.kind == NodeKind.TOOL),
        "not_replayable": [
            {"node_id": n.id, "reason": n.metadata.replay_note}
            for n in graph.nodes.values() if not n.metadata.replayable
        ],
    }

# ---------------------------------------------------------
# 3. TRACE / RUN EXECUTION APIs
# ---------------------------------------------------------
@app.get("/api/runs/{record_id}/graph", summary="Get Execution Graph Payload")
def get_version_graph(record_id: str):
    try:
        return store.load(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/runs/{record_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Specific Version")
def delete_run(record_id: str):
    try:
        try:
            store.load(record_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Execution record not found.")
        store.delete(record_id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class Entrypoint(BaseModel):
    argv: List[str] = Field(..., min_length=1, description="Command line, e.g. ['python', 'examples/crewai_weather.py']")
    cwd: Optional[str] = None
    executable: Optional[str] = None

def resolve_entrypoint(argv: List[str], cwd: Optional[str] = None, executable: Optional[str] = None) -> Dict[str, Any]:
    """Turn a command line into the stored {executable, argv, cwd} form; `python` means this interpreter."""
    cwd = str(Path(cwd or os.getcwd()).resolve())
    argv = list(argv)
    if executable is None:
        head = argv.pop(0)
        if Path(head).name.lower() in ("python", "python3", "python.exe", "py"):
            executable = sys.executable
        else:
            executable = shutil.which(head) or head
    if argv and not argv[0].startswith("-") and (Path(cwd) / argv[0]).is_file():
        argv[0] = str((Path(cwd) / argv[0]).resolve())
    return {"executable": executable, "argv": argv, "cwd": cwd}

def _with_attributes(graph, **attributes):
    merged = {**(graph.metadata.attributes or {}), **attributes}
    return replace(graph, metadata=replace(graph.metadata, attributes=merged))

@app.put("/api/runs/{record_id}/entrypoint", summary="Set the command used to re-run a record during replay")
def set_entrypoint(record_id: str, body: Entrypoint):
    """Needed for records made interactively or before the OTel migration, which have no saved command."""
    try:
        graph = store.load(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    entrypoint = resolve_entrypoint(body.argv, body.cwd, body.executable)
    store.update_graph(record_id, _with_attributes(graph, entrypoint=entrypoint))
    return {"record_id": record_id, "entrypoint": entrypoint}

@app.post("/api/runs/{record_id}/recompile", summary="Rebuild a record's graph from its raw spans")
def recompile_run(record_id: str):
    """Picks up adapter/compiler improvements without re-running the agent."""
    try:
        graph = store.load(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    attributes = dict(graph.metadata.attributes or {})
    spans = store.get_spans(attributes.get("run_id") or "")
    if not spans:
        raise HTTPException(status_code=409, detail="No raw spans are stored for this record.")
    keep = {k: attributes[k] for k in ("run_id", "run_status", "entrypoint") if k in attributes}
    rebuilt = IRCompiler().compile(OTelSpanAdapter().parse_spans(spans), graph_id=graph.id, attributes=keep)
    store.update_graph(record_id, rebuilt)
    return {"record_id": record_id, "nodes": len(rebuilt.nodes)}

# ---------------------------------------------------------
# 4. REPLAY APIs
# ---------------------------------------------------------
class ReplayOptions(BaseModel):
    match: str = "RELAXED"
    faults: List[Dict[str, Any]] = Field(default_factory=list)
    input: Any = None  # accepted for frontend compatibility
    timeout: float = 600

class SessionCreate(BaseModel):
    record_id: str
    match: str = "RELAXED"
    faults: List[Dict[str, Any]] = Field(default_factory=list)

def _tracking_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/")

def _open_session(record_id: str, match: str, faults: List[Dict[str, Any]]):
    try:
        graph = store.load(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        return graph, replay_gateway.create_session(graph, record_id, match, faults, store=store)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/replay-sessions", summary="Open a replay session (used by agent_replay.replay)")
def create_replay_session(body: SessionCreate, request: Request):
    _, state = _open_session(body.record_id, body.match, body.faults)
    root = session_url(_tracking_uri(request), state.session_id)
    return {
        "session_id": state.session_id,
        "base_url": f"{root}/v1",      # OpenAI-style clients
        "anthropic_base_url": root,    # the Anthropic SDK appends /v1 itself
        "total_steps": state.total_steps,
    }

@app.post("/api/replay-sessions/{session_id}/finish", summary="Close a replay session and get its report")
def finish_replay_session(session_id: str):
    try:
        return replay_gateway.finish_session(session_id, store)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown replay session '{session_id}'.")

@app.post("/api/runs/{record_id}/replay", summary="Re-run the recorded agent against its recording")
def replay_agent_run(record_id: str, request: Request, body: Optional[ReplayOptions] = None):
    body = body or ReplayOptions()
    graph, state = _open_session(record_id, body.match, body.faults)
    entrypoint = (graph.metadata.attributes or {}).get("entrypoint")
    if not entrypoint:
        replay_gateway.finish_session(state.session_id, store)
        raise HTTPException(
            status_code=400,
            detail="This record has no saved command (recorded interactively or before the OTel migration). "
                   f"Set one with: agent-replay set-entrypoint {record_id} -- python path/to/agent.py",
        )

    tracking_uri = _tracking_uri(request)
    env = {
        **os.environ,
        **replay_env(tracking_uri, state.session_id),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }

    command = [entrypoint["executable"], *entrypoint["argv"]]
    try:
        proc = subprocess.run(
            command, cwd=entrypoint.get("cwd"), env=env, capture_output=True, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", timeout=body.timeout,
        )
        returncode, logs = proc.returncode, proc.stdout + (f"\n{proc.stderr}" if proc.stderr.strip() else "")
    except subprocess.TimeoutExpired as e:
        returncode, logs = -1, f"{e.stdout or ''}\n❌ Replay timed out after {body.timeout}s."
    except OSError as e:
        returncode, logs = -1, f"❌ Could not launch {command}: {e}"

    report = replay_gateway.finish_session(state.session_id, store)
    errors = [d for d in report["divergences"] if d.get("severity") == "error"]
    ok = returncode == 0 and not errors

    summary = [
        "",
        f"[agent-replay] Served {report['served_steps']}/{report['total_steps']} recorded calls "
        f"({report['match']} match); no provider calls were made.",
    ]
    summary += [f"[agent-replay] Fault injected on step {e['step']} (HTTP {e['status']})"
                for e in report["events"] if e["type"] == "fault_injected"]
    summary += [f"[agent-replay] Replayed recorded error on step {e['step']} (HTTP {e['status']})"
                for e in report["events"] if e["type"] == "replayed_error"]
    summary += [f"[agent-replay] {d['severity'].upper()} {d['type']}: {d['reason']}" for d in report["divergences"]]
    if returncode != 0:
        summary.append(f"❌ CRITICAL SYSTEM HALT: agent exited with code {returncode}")

    # HTTP 200 either way, so the Replay panel can render the logs up to the failure point.
    return {
        "status": "success" if ok else "error",
        "message": (f"Successfully replayed {record_id} with ZERO network calls! ({report['match'].title()} Mode)"
                    if ok else f"Replay of {record_id} failed or diverged."),
        "logs": logs + "\n".join(summary),
        "divergences": report["divergences"],
        "report": report,
    }

# ---------------------------------------------------------
# 5. SYSTEM APIs
# ---------------------------------------------------------
@app.get("/api/stats", summary="Get System Stats")
def get_system_stats():
    try:
        return {"total_execution_records": store.get_count()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/system/clear", status_code=status.HTTP_204_NO_CONTENT, summary="Nuke Database")
def clear_all_data():
    try:
        store.clear_all()
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# 6. UI DASHBOARD (mounted last so every API route above takes precedence)
# ---------------------------------------------------------
def ui_available() -> bool:
    return (UI_DIR / "index.html").is_file()

if ui_available():
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def ui_not_built():
        return (
            "<h3>Agent Replay UI is not built</h3>"
            "<p>Run <code>cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</code>, then restart the server. "
            "The API is available at <a href='/docs'>/docs</a>.</p>"
        )


def serve(host: Optional[str] = None, port: Optional[int] = None):
    import uvicorn
    # Loopback by default: the replay API launches recorded commands.
    host = host or os.environ.get("AGENT_REPLAY_HOST", "127.0.0.1")
    port = port or int(os.environ.get("AGENT_REPLAY_PORT", "5000"))
    if not security.is_loopback(host) and not security.configured_token():
        raise SystemExit(
            f"Refusing to listen on {host}: the replay API runs recorded commands. "
            f"Set {security.TOKEN_ENV} (and {security.ALLOWED_HOSTS_ENV}) to expose it beyond localhost."
        )
    print(f"🚀 Agent Replay UI + API at http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}", flush=True)
    if not ui_available():
        print("⚠️  UI not built; run `cd frontend && npm ci && npm run build` to enable the dashboard.", flush=True)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    serve()
