from helm_api.services import job_control_service


def test_run_replay_job_respects_pause_and_reports_processed_count(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(job_control_service, "is_job_paused", lambda job_name: job_name == "replay")
    paused = job_control_service.run_replay_job(limit=5)
    assert paused["status"] == "rejected"
    assert paused["reason"] == "job_paused"
    assert paused["processed_count"] == 0

    monkeypatch.setattr(job_control_service, "is_job_paused", lambda _job_name: False)
    monkeypatch.setattr(job_control_service, "run_replay_queue", lambda *, limit: limit - 1)
    accepted = job_control_service.run_replay_job(limit=5)

    assert accepted == {
        "status": "accepted",
        "job_name": "replay",
        "limit": 5,
        "processed_count": 4,
        "reason": None,
    }
