import pytest

pytest.importorskip("mcp")

from fastapi.testclient import TestClient
from woo_connector.main import app


def test_health_and_ready_endpoints():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json() == {"status": "ready"}

def test_mcp_route_is_mounted():
    assert any(
        getattr(route, "path", None) == "/mcp"
        or getattr(route, "path", None) == "/"
        for route in app.routes
    ) or any(
        getattr(route, "path", "").startswith("/mcp")
        for route in app.routes
    )