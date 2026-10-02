"""
Run tracking, modelled on MLflow: spans are tagged with the active run id and shipped to the
tracking server over OTLP; ending a run asks the server to compile those spans into a graph.
"""
import json
import os
import sys
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

TRACKING_URI_ENV = "AGENT_REPLAY_TRACKING_URI"
TOKEN_ENV = "AGENT_REPLAY_TOKEN"
SESSION_ID_ENV = "AGENT_REPLAY_SESSION_ID"
DEFAULT_TRACKING_URI = "http://localhost:5000"

_tracking_uri: Optional[str] = None
_lock = threading.Lock()
_active_run: Optional["Run"] = None
_implicit_run: Optional["Run"] = None
_session_run: Optional["Run"] = None  # spans of an in-process replay() block


def set_tracking_uri(uri: str) -> None:
    """Set the tracking server. Call before autolog(), which binds its exporter to this URI."""
    global _tracking_uri
    _tracking_uri = uri.rstrip("/")


def get_tracking_uri() -> str:
    return (_tracking_uri or os.environ.get(TRACKING_URI_ENV) or DEFAULT_TRACKING_URI).rstrip("/")


@dataclass
class Run:
    run_id: str
    agent_id: str
    agent_name: str
    kind: str = "record"  # "record" creates a new agent version; "replay" is diffed against its recording
    span_count: int = 0
    result: Dict[str, Any] = field(default_factory=dict)

    def __enter__(self) -> "Run":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        end_run(status="FAILED" if exc_type else "FINISHED")


def start_run(agent_id: Optional[str] = None, agent_name: Optional[str] = None) -> Run:
    """
    Start a run; every span created until end_run() belongs to it.

        with agent_replay.start_run(agent_id="weather_bot", agent_name="Weather Bot"):
            crew.kickoff()

    Inside a replay (AGENT_REPLAY_SESSION_ID is set) the run joins the replay session
    instead of recording a new version.
    """
    global _active_run
    run = _new_run(agent_id, agent_name)
    with _lock:
        _active_run = run
    return run


def end_run(status: str = "FINISHED") -> Dict[str, Any]:
    global _active_run
    with _lock:
        run, _active_run = _active_run, None
    if run is None:
        return {}
    return _finish(run, status)


def active_run() -> Optional[Run]:
    return _active_run


def current_run() -> Run:
    """The run new spans belong to: the active run, or an implicit one for scripts that never call start_run()."""
    global _implicit_run, _session_run
    with _lock:
        if _active_run is not None:
            return _active_run
        session_id = os.environ.get(SESSION_ID_ENV)
        if session_id:
            if _session_run is None or _session_run.run_id != session_id:
                _session_run = _new_run(None, None)
            return _session_run
        if _implicit_run is None:
            _implicit_run = _new_run(None, None)
        return _implicit_run


def end_implicit_run() -> None:
    """Called at interpreter exit: finalise spans recorded outside any start_run() block."""
    global _implicit_run
    with _lock:
        run, _implicit_run = _implicit_run, None
    if run is not None and run.span_count:
        _finish(run, "FINISHED")


def entrypoint() -> Optional[Dict[str, Any]]:
    """How to re-launch this process, so the server can replay it later."""
    argv = list(sys.argv)
    if not argv or argv[0] in ("", "-c", "-"):
        return None  # interactive / inline code cannot be re-run
    if argv[0] != "-m":
        argv[0] = str(Path(argv[0]).resolve())
    return {"executable": sys.executable, "argv": argv, "cwd": os.getcwd()}


def auth_headers() -> Dict[str, str]:
    """Bearer token for a tracking server started with AGENT_REPLAY_TOKEN."""
    token = os.environ.get(TOKEN_ENV)
    return {"Authorization": f"Bearer {token}"} if token else {}


def post_json(path: str, payload: Dict[str, Any], timeout: float = 30, method: str = "POST") -> Dict[str, Any]:
    req = urllib.request.Request(
        f"{get_tracking_uri()}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **auth_headers()},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Tracking server error {exc.code} on {path}: {detail}") from exc


def _new_run(agent_id: Optional[str], agent_name: Optional[str]) -> Run:
    default_id = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else "agent"
    agent_id = agent_id or default_id
    session_id = os.environ.get(SESSION_ID_ENV)
    if session_id:
        return Run(run_id=session_id, agent_id=agent_id, agent_name=agent_name or agent_id, kind="replay")
    return Run(run_id=uuid.uuid4().hex, agent_id=agent_id, agent_name=agent_name or agent_id)


def _finish(run: Run, status: str) -> Dict[str, Any]:
    from .autolog import flush

    flush()  # every span must reach the server before it compiles the run
    run.result = post_json(f"/api/runs/{run.run_id}/end", {
        "agent_id": run.agent_id,
        "agent_name": run.agent_name,
        "kind": run.kind,
        "status": status,
        "entrypoint": entrypoint(),
    })
    if run.kind == "record" and run.result.get("record_id"):
        print(f"💾 [agent-replay] Recorded run as {run.result['record_id']} ({get_tracking_uri()})")
    return run.result
