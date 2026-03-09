from fastapi.testclient import TestClient
from helm_api.main import app


def test_routes_exist() -> None:
    client = TestClient(app)
    assert client.get("/v1/status").status_code == 200
    assert client.get("/v1/admin/agent-runs").status_code == 200
    assert client.get("/v1/actions").status_code == 200
    assert client.get("/v1/drafts").status_code == 200


def test_digest_workflow_route_returns_digest(monkeypatch) -> None:
    monkeypatch.setattr(
        "helm_api.routers.workflows.build_daily_digest",
        lambda: "Daily Brief\nTop priorities today:\n1. Test -> Complete action item #1.",
    )
    client = TestClient(app)
    response = client.post("/v1/workflows/digest/run")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "Daily Brief" in payload["digest"]
