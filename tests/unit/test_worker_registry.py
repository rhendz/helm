from contextlib import contextmanager

from helm_worker.jobs import workflow_runs
from helm_worker.jobs.registry import JOBS


def test_job_registry_contains_core_jobs() -> None:
    assert {"email_triage", "digest", "study", "scheduled_thread_tasks", "workflow_runs"}.issubset(
        JOBS.keys()
    )


def test_workflow_runs_job_skips_without_handlers(monkeypatch) -> None:  # noqa: ANN001
    def _unexpected_session_local():  # type: ignore[no-untyped-def]
        raise AssertionError("SessionLocal should not be called when no workflow handlers are configured.")

    monkeypatch.setattr(workflow_runs, "SessionLocal", _unexpected_session_local)

    assert workflow_runs.run() == 0


def test_workflow_runs_job_resumes_runnable_runs(monkeypatch) -> None:  # noqa: ANN001
    @contextmanager
    def _session_local():  # type: ignore[no-untyped-def]
        yield object()

    class _FakeResumeService:
        def resume_runnable_runs(self) -> list[object]:
            return [object(), object()]

    captured_handlers: dict[str, object] = {}

    def _build_resume_service(_session, *, handlers):  # type: ignore[no-untyped-def]
        captured_handlers.update(handlers)
        return _FakeResumeService()

    monkeypatch.setattr(workflow_runs, "SessionLocal", _session_local)
    monkeypatch.setattr(workflow_runs, "_build_resume_service", _build_resume_service)

    result = workflow_runs.run(handlers={"normalize_request": object()})

    assert result == 2
    assert "normalize_request" in captured_handlers
