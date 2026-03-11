from fastapi.testclient import TestClient
from helm_api.main import app


def test_routes_exist() -> None:
    client = TestClient(app)
    assert client.get("/v1/status").status_code == 200
    assert client.get("/v1/status/agent-runs/failures").status_code == 200
    assert client.get("/v1/status/draft-transitions/failures").status_code == 200
    assert client.get("/v1/job-controls").status_code == 200
    assert client.get("/v1/job-controls?status=paused").status_code == 200
    assert client.get("/v1/job-controls?status=active").status_code == 200
    assert client.get("/v1/job-controls/digest").json() == {
        "job_name": "digest",
        "paused": False,
    }
    assert client.post("/v1/job-controls/digest/run").status_code == 200
    assert client.post("/v1/job-controls/replay/run", json={"limit": 10}).status_code == 200
    assert client.get("/v1/job-controls/not-a-real-job").status_code == 404
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
    assert client.get("/v1/email/threads/1/classification-artifacts").status_code == 200
    assert client.get("/v1/email/messages/1/classification-artifacts").status_code == 200
    assert client.get("/v1/email/proposals").status_code == 200
    assert client.get("/v1/email/proposals?status=proposed&proposal_type=reply").status_code == 200
    assert client.get("/v1/email/drafts").status_code == 200
    assert client.get("/v1/email/drafts?approval_status=pending_user").status_code == 200
    assert client.get("/v1/email/drafts/999999").status_code == 404
    assert client.get("/v1/email/drafts/999999/transition-audits").status_code == 200
    assert client.get("/v1/email/drafts/999999/reasoning-artifacts").status_code == 200
    assert client.get("/v1/email/drafts/999999/send-attempts").status_code == 200
    assert client.post("/v1/email/drafts/999999/send").status_code == 200
    seed_plan_response = client.post(
        "/v1/email/seed/plan",
        json={
            "source_type": "email_manual",
            "messages": [
                {
                    "id": "seed-1",
                    "threadId": "seed-thread-1",
                    "from": "recruiter@example.com",
                    "subject": "Interview request",
                }
            ],
        },
    )
    assert seed_plan_response.status_code == 200
    assert seed_plan_response.json()["bucket_counts"]["deep_seed"] == 1
    seed_enqueue_response = client.post(
        "/v1/email/seed/enqueue",
        json={
            "source_type": "email_manual",
            "messages": [
                {
                    "id": "seed-2",
                    "threadId": "seed-thread-2",
                    "from": "recruiter@example.com",
                    "subject": "Interview request",
                }
            ],
        },
    )
    assert seed_enqueue_response.status_code == 200
    assert seed_enqueue_response.json()["status"] in {"accepted", "unavailable"}
    assert client.get("/v1/email/seed/queue").status_code == 200
    assert client.get("/v1/email/seed/queue?status=pending").status_code == 200
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
    replay_response = client.post("/v1/replay/enqueue", json={"agent_run_id": 999999})
    assert replay_response.status_code == 200
    assert replay_response.json()["status"] in {"rejected", "unavailable"}
    replay_items_response = client.get("/v1/replay/items")
    assert replay_items_response.status_code == 200
    replay_items_filtered_response = client.get("/v1/replay/items?status=dead_lettered")
    assert replay_items_filtered_response.status_code == 200
    replay_requeue_response = client.post("/v1/replay/999999/requeue")
    assert replay_requeue_response.status_code == 200
    assert replay_requeue_response.json()["status"] in {"rejected", "unavailable"}
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
    paused_run_response = client.post("/v1/job-controls/digest/run")
    assert paused_run_response.status_code == 200
    assert paused_run_response.json()["status"] in {"accepted", "rejected"}
    if paused_run_response.json()["status"] == "rejected":
        assert paused_run_response.json()["reason"] == "job_paused"
    paused_items_response = client.get("/v1/job-controls?status=paused")
    assert paused_items_response.status_code == 200
    assert all(
        item["paused"] is True for item in paused_items_response.json()["items"]
    )
    detail_response = client.get("/v1/job-controls/digest")
    assert detail_response.status_code == 200
    assert detail_response.json()["job_name"] == "digest"
    resume_response = client.post("/v1/job-controls/digest/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["paused"] is False
    active_items_response = client.get("/v1/job-controls?status=active")
    assert active_items_response.status_code == 200
    assert all(
        item["paused"] is False for item in active_items_response.json()["items"]
    )
    assert any(
        item["job_name"] == "digest" and item["paused"] is False
        for item in active_items_response.json()["items"]
    )
    active_run_response = client.post("/v1/job-controls/digest/run")
    assert active_run_response.status_code == 200
    assert active_run_response.json()["status"] == "accepted"
    replay_run_response = client.post("/v1/job-controls/replay/run", json={"limit": 5})
    assert replay_run_response.status_code == 200
    assert replay_run_response.json()["status"] == "accepted"
    assert replay_run_response.json()["job_name"] == "replay"
    assert replay_run_response.json()["limit"] == 5
    trace_response = client.get("/v1/artifacts/action/1/trace")
    assert trace_response.status_code == 200
    assert trace_response.json()["status"] in {"ok", "not_found", "unavailable"}
