from fastapi.testclient import TestClient

from helm_api.main import app


def test_routes_exist() -> None:
    client = TestClient(app)
    assert client.get("/v1/status").status_code == 200
    assert client.get("/v1/actions").status_code == 200
    assert client.get("/v1/drafts").status_code == 200
