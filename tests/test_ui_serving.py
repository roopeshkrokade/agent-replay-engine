"""The tracking server serves the React dashboard and the API from one port, like MLflow."""
import re
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("AGENT_REPLAY_DB", str(tmp_path_factory.mktemp("db") / "traces.db"))
    mp.setenv("AGENT_REPLAY_ALLOWED_HOSTS", "testserver")  # TestClient's Host header
    sys.modules.pop("agent_replay.server.app", None)
    import agent_replay.server.app as tracking_app

    if not tracking_app.ui_available():
        mp.undo()
        pytest.skip("UI not built; run `npm run build` in frontend/")
    yield TestClient(tracking_app.app)
    mp.undo()
    sys.modules.pop("agent_replay.server.app", None)


def test_dashboard_and_assets_are_served(client):
    index = client.get("/")
    assert index.status_code == 200 and '<div id="root">' in index.text
    assets = re.findall(r'(?:src|href)="\.?/?(assets/[^"]+)"', index.text)
    assert assets, index.text
    for asset in assets:
        assert client.get(f"/{asset}").status_code == 200


def test_api_routes_take_precedence_over_the_ui(client):
    assert client.get("/api/stats").json() == {"total_execution_records": 0}
    assert client.get("/api/agents").json() == []
    assert client.get("/docs").status_code == 200
    assert client.post("/v1/traces", content=b"").status_code == 200  # empty OTLP export is valid
