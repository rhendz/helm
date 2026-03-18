import types
from contextlib import contextmanager

from helm_worker.jobs import workflow_runs
from helm_worker.jobs.registry import JOBS


def _make_fake_state(needs_action: bool = False) -> types.SimpleNamespace:
    run = types.SimpleNamespace(needs_action=needs_action)
    return types.SimpleNamespace(run=run, latest_artifacts={})


def test_job_registry_contains_core_jobs() -> None:
    assert {
        "email_triage",
        "email_reconciliation_sweep",
        "digest",
        "scheduled_thread_tasks",
        "email_followup_scan",
        "email_send_recovery",
        "workflow_runs",
    }.issubset(JOBS.keys())


def test_workflow_runs_job_uses_default_specialist_registry(monkeypatch) -> None:  # noqa: ANN001
    def _unexpected_session_local():  # type: ignore[no-untyped-def]
        raise AssertionError("SessionLocal should not be called when no workflow runs are resumed.")

    monkeypatch.setattr(workflow_runs, "SessionLocal", _unexpected_session_local)
    monkeypatch.setattr(
        workflow_runs,
        "_build_specialist_steps",
        lambda: {("weekly_scheduling", "dispatch_task_agent"): object()},
    )
    monkeypatch.setattr(
        workflow_runs,
        "_build_resume_service",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    try:
        workflow_runs.run()
    except AssertionError:
        pass
    else:
        raise AssertionError("Expected the default specialist registry to attempt a session.")


def test_workflow_runs_job_resumes_runnable_runs(monkeypatch) -> None:  # noqa: ANN001
    @contextmanager
    def _session_local():  # type: ignore[no-untyped-def]
        yield object()

    class _FakeResumeService:
        def resume_runnable_runs(self) -> list[types.SimpleNamespace]:
            return [_make_fake_state(), _make_fake_state()]

    captured_handlers: dict[tuple[str, str], object] = {}

    def _build_resume_service(_session, *, handlers):  # type: ignore[no-untyped-def]
        captured_handlers.update(handlers)
        return _FakeResumeService()

    monkeypatch.setattr(workflow_runs, "SessionLocal", _session_local)
    monkeypatch.setattr(workflow_runs, "_build_resume_service", _build_resume_service)

    result = workflow_runs.run(handlers={("weekly_scheduling", "dispatch_task_agent"): object()})

    assert result == 2
    assert ("weekly_scheduling", "dispatch_task_agent") in captured_handlers
