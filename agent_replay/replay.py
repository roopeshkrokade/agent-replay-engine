"""
replay(): run code against a recording. LLM clients are pointed at the tracking server's
OpenAI-compatible replay endpoint through their standard base-URL environment variables,
so no client library is patched.
"""
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional

from . import tracking

# Base-URL variables read by the provider SDKs (and the frameworks built on them).
# OpenAI-style clients expect the URL to include /v1; the Anthropic SDK appends /v1 itself.
OPENAI_BASE_URL_ENV = ("OPENAI_BASE_URL", "OPENAI_API_BASE")
ANTHROPIC_BASE_URL_ENV = "ANTHROPIC_BASE_URL"
# A replay never reaches the provider, but SDKs refuse to start without some key.
API_KEY_ENV = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
DUMMY_API_KEY = "agent-replay"


@dataclass
class ReplayHandle:
    session_id: str
    record_id: str
    base_url: str
    report: Dict[str, Any] = field(default_factory=dict)


def session_url(tracking_uri: str, session_id: str) -> str:
    return f"{tracking_uri.rstrip('/')}/replay/{session_id}"


def replay_env(tracking_uri: str, session_id: str, current: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """Environment that routes a process's LLM traffic to a replay session."""
    root = session_url(tracking_uri, session_id)
    env = {name: f"{root}/v1" for name in OPENAI_BASE_URL_ENV}
    env[ANTHROPIC_BASE_URL_ENV] = root
    env[tracking.SESSION_ID_ENV] = session_id
    env[tracking.TRACKING_URI_ENV] = tracking_uri
    current = os.environ if current is None else current
    for key in API_KEY_ENV:
        if not current.get(key):
            env[key] = DUMMY_API_KEY
    return env


@contextmanager
def replay(
    record_id: str,
    match: str = "RELAXED",
    faults: Iterable[Mapping[str, Any]] = (),
) -> Iterator[ReplayHandle]:
    """
    Replay a recorded run in-process:

        with agent_replay.replay("weather_bot_v1.0.0") as session:
            build_and_run_agent()      # create LLM clients inside the block
        print(session.report)

    match: "RELAXED" serves the matching (else next) recorded call; "STRICT" requires identical requests.
    faults: e.g. [{"step": 2, "status": 503}] to inject a failure on the second model call.
    """
    created = tracking.post_json("/api/replay-sessions", {
        "record_id": record_id, "match": match, "faults": list(faults),
    })
    handle = ReplayHandle(created["session_id"], record_id, created["base_url"])

    overrides = replay_env(tracking.get_tracking_uri(), handle.session_id)
    saved = {k: os.environ.get(k) for k in overrides}
    os.environ.update(overrides)
    try:
        yield handle
    finally:
        tracking.end_run()
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        handle.report = tracking.post_json(f"/api/replay-sessions/{handle.session_id}/finish", {})


def divergences(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return list(report.get("divergences", []))
