from fastapi.testclient import TestClient
from helm_api.main import app


def test_routes_exist() -> None:
    client = TestClient(app)
    assert client.get("/v1/status").status_code == 200
    assert client.get("/v1/status/agent-runs/failures").status_code == 200
    assert client.get("/v1/actions").status_code == 200
    assert client.get("/v1/drafts").status_code == 200
    response = client.post(
        "/v1/study/ingest",
        json={"source_type": "manual", "raw_text": "Gap: weak in graph DP\nTODO: solve 3 problems"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    linkedin_response = client.post(
        "/v1/linkedin/ingest",
        json={
            "source_type": "linkedin_manual",
            "events": [
                {
                    "id": "li-msg-1",
                    "thread_id": "li-thread-1",
                    "sender_name": "Recruiter",
                    "body_text": "Can we chat?",
                }
            ],
        },
    )
    assert linkedin_response.status_code == 200
    assert linkedin_response.json()["status"] == "accepted"
