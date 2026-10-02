"""
The replay API launches recorded commands, so the server guards it:

* Host allow-list (always on): only requests addressed to localhost or AGENT_REPLAY_ALLOWED_HOSTS
  are served. This stops DNS-rebinding pages in a browser from reaching a local server.
* Bearer token (when AGENT_REPLAY_TOKEN is set): required for /api/* and OTLP ingestion. Clients
  (autolog, CLI, replayed agents, the dashboard) send it automatically from the same variable.
  Replay endpoints are addressed by an unguessable per-session id and need no token.
* serve() refuses to bind a non-loopback interface unless a token is configured.
"""
import hmac
import os
from typing import Iterable, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

TOKEN_ENV = "AGENT_REPLAY_TOKEN"
ALLOWED_HOSTS_ENV = "AGENT_REPLAY_ALLOWED_HOSTS"
LOOPBACK_HOSTS = ["localhost", "127.0.0.1", "::1", "[::1]"]
PROTECTED_PREFIXES = ("/api/", "/v1/traces")


def configured_token() -> Optional[str]:
    return os.environ.get(TOKEN_ENV) or None


def allowed_hosts(extra: Iterable[str] = ()) -> List[str]:
    configured = [h.strip() for h in os.environ.get(ALLOWED_HOSTS_ENV, "").split(",") if h.strip()]
    return [*LOOPBACK_HOSTS, *configured, *extra]


def is_loopback(host: str) -> bool:
    return host in LOOPBACK_HOSTS


class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = configured_token()
        if token and request.url.path.startswith(PROTECTED_PREFIXES):
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not hmac.compare_digest(supplied.encode(), token.encode()):
                return JSONResponse(status_code=401, content={"detail": "Missing or invalid agent-replay token."},
                                    headers={"WWW-Authenticate": "Bearer"})
        return await call_next(request)


def install(app, extra_hosts: Iterable[str] = ()) -> None:
    app.add_middleware(TokenAuthMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts(extra_hosts))
