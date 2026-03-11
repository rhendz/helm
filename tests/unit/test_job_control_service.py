from helm_api.services import job_control_service


def test_run_job_rejects_unknown_and_paused_jobs(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(job_control_service, "JOBS", {"digest": lambda: None})
    monkeypatch.setattr(
        job_control_service,
        "MANUALLY_RUNNABLE_JOB_NAMES",
        frozenset({"digest"}),
    )

    unknown = job_control_service.run_job(job_name="missing")
    assert unknown["status"] == "rejected"
    assert unknown["reason"] == "unknown_job"

    monkeypatch.setattr(job_control_service, "is_job_paused", lambda job_name: job_name == "digest")
    paused = job_control_service.run_job(job_name="digest")
    assert paused["status"] == "rejected"
    assert paused["reason"] == "job_paused"


def test_run_job_executes_manually_runnable_job(monkeypatch) -> None:  # noqa: ANN001
    executed: list[str] = []
    monkeypatch.setattr(
        job_control_service,
        "JOBS",
        {"digest": lambda: executed.append("digest"), "replay": lambda: None},
    )
    monkeypatch.setattr(
        job_control_service,
        "MANUALLY_RUNNABLE_JOB_NAMES",
        frozenset({"digest"}),
    )
    monkeypatch.setattr(job_control_service, "is_job_paused", lambda _job_name: False)

    result = job_control_service.run_job(job_name="digest")

    assert result == {"status": "accepted", "job_name": "digest", "reason": None}
    assert executed == ["digest"]


def test_run_replay_job_respects_pause_and_reports_processed_count(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(job_control_service, "is_job_paused", lambda job_name: job_name == "replay")
    paused = job_control_service.run_replay_job(limit=5)
    assert paused["status"] == "rejected"
    assert paused["reason"] == "job_paused"
    assert paused["processed_count"] == 0

    monkeypatch.setattr(job_control_service, "is_job_paused", lambda _job_name: False)
    monkeypatch.setattr(job_control_service.replay_job, "run", lambda *, limit: limit - 1)
    accepted = job_control_service.run_replay_job(limit=5)

    assert accepted == {
        "status": "accepted",
        "job_name": "replay",
        "limit": 5,
        "processed_count": 4,
        "reason": None,
    }
