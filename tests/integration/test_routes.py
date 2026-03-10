from fastapi.testclient import TestClient
from helm_api.main import app


def test_routes_exist() -> None:
    client = TestClient(app)
    assert client.get("/v1/status").status_code == 200
    assert client.get("/v1/status/agent-runs/failures").status_code == 200
    assert client.get("/v1/status/draft-transitions/failures").status_code == 200
    assert client.get("/v1/job-controls").status_code == 200
    assert client.get("/v1/actions").status_code == 200
    email_ingest_response = client.post(
        "/v1/email/ingest",
        json={
            "source_type": "email_manual",
            "messages": [
                {
                    "id": "email-msg-1",
                    "threadId": "email-thread-1",
                    "from": "recruiter@example.com",
                    "subject": "Role update",
                    "body_text": "Would you be open to talking?",
                }
            ],
        },
    )
    assert email_ingest_response.status_code == 200
    assert email_ingest_response.json()["status"] == "accepted"
    assert "processed_count" in email_ingest_response.json()
    assert "normalization_failures" in email_ingest_response.json()
    assert client.get("/v1/email/threads").status_code == 200
    assert client.get("/v1/email/threads?business_state=needs_review").status_code == 200
    assert client.get("/v1/email/threads?label=Action").status_code == 200
    assert client.get("/v1/email/proposals").status_code == 200
    assert client.get("/v1/email/proposals?status=proposed&proposal_type=reply").status_code == 200
    assert client.get("/v1/email/drafts").status_code == 200
    assert client.get("/v1/email/drafts?approval_status=pending_user").status_code == 200
    assert client.get("/v1/email/tasks").status_code == 200
    assert client.get("/v1/email/tasks?status=pending").status_code == 200
    assert client.get("/v1/email/threads/999999").status_code == 404
    reprocess_email_response = client.post(
        "/v1/email/threads/999999/reprocess",
        json={"dry_run": True},
    )
    assert reprocess_email_response.status_code == 200
    assert reprocess_email_response.json()["status"] in {"not_found", "unavailable"}
    override_email_response = client.post(
        "/v1/email/threads/999999/override",
        json={
            "business_state": "resolved",
            "visible_labels": [],
            "current_summary": "Resolved manually",
            "latest_confidence_band": "High",
            "action_reason": "user_marked_done",
        },
    )
    assert override_email_response.status_code == 200
    assert override_email_response.json()["status"] in {"not_found", "unavailable"}
    assert client.get("/v1/email/threads/999999/tasks").status_code == 200
    create_task_response = client.post(
        "/v1/email/threads/999999/tasks",
        json={
            "task_type": "reminder",
            "due_at": "2026-01-03T09:00:00Z",
            "created_by": "user",
        },
    )
    assert create_task_response.status_code == 200
    assert create_task_response.json()["status"] in {"not_found", "unavailable"}
    complete_global_task_response = client.post("/v1/email/tasks/999999/complete")
    assert complete_global_task_response.status_code == 200
    assert complete_global_task_response.json()["status"] in {"not_found", "unavailable"}
    complete_task_response = client.post("/v1/email/threads/999999/tasks/999999/complete")
    assert complete_task_response.status_code == 200
    assert complete_task_response.json()["status"] in {"not_found", "unavailable"}
    drafts_response = client.get("/v1/drafts")
    assert drafts_response.status_code == 200
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
    assert "failed_event_count" in linkedin_response.json()
    assert "normalization_failures" in linkedin_response.json()
    replay_response = client.post("/v1/replay/enqueue", json={"agent_run_id": 999999})
    assert replay_response.status_code == 200
    assert replay_response.json()["status"] in {"rejected", "unavailable"}
    replay_reprocess_rejected = client.post(
        "/v1/replay/reprocess",
        json={"dry_run": True, "limit": 10},
    )
    assert replay_reprocess_rejected.status_code == 200
    assert replay_reprocess_rejected.json()["status"] == "rejected"
    replay_reprocess_scoped = client.post(
        "/v1/replay/reprocess",
        json={"source_type": "worker", "since_hours": 24, "dry_run": True, "limit": 10},
    )
    assert replay_reprocess_scoped.status_code == 200
    assert replay_reprocess_scoped.json()["status"] in {"accepted", "unavailable"}
    requeue_response = client.post(
        "/v1/drafts/requeue-stale",
        json={"stale_after_hours": 72, "limit": 10, "dry_run": True},
    )
    assert requeue_response.status_code == 200
    assert requeue_response.json()["status"] in {"accepted", "unavailable"}
    pause_response = client.post("/v1/job-controls/digest/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["paused"] is True
    resume_response = client.post("/v1/job-controls/digest/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["paused"] is False
    trace_response = client.get("/v1/artifacts/action/1/trace")
    assert trace_response.status_code == 200
    assert trace_response.json()["status"] in {"ok", "not_found", "unavailable"}
