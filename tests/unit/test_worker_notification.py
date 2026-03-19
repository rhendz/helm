"""Tests for the proactive notification loop in workflow_runs.run()."""
from __future__ import annotations

import types
from contextlib import contextmanager

import pytest
from helm_storage.repositories import WorkflowArtifactType
from helm_worker.jobs import workflow_runs


def _make_fake_state(
    *,
    needs_action: bool = False,
    run_id: int = 1,
    workflow_type: str = "task_quick_add",
    latest_artifacts: dict | None = None,
) -> types.SimpleNamespace:
    run = types.SimpleNamespace(
        needs_action=needs_action,
        id=run_id,
        workflow_type=workflow_type,
    )
    return types.SimpleNamespace(run=run, latest_artifacts=latest_artifacts or {})


def _make_session_patcher():
    """Return a context-manager factory that yields a dummy session."""
    @contextmanager
    def _session_local():
        yield object()
    return _session_local


def test_notification_fires_for_needs_action_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """notify_approval_needed is called when state.run.needs_action=True."""
    state = _make_fake_state(needs_action=True, run_id=42, workflow_type="task_quick_add")

    class _FakeService:
        def resume_runnable_runs(self):
            return [state]

    monkeypatch.setattr(workflow_runs, "_resolve_bootstrap_user_id", lambda _: 1)
    monkeypatch.setattr(workflow_runs, "SessionLocal", _make_session_patcher())
    monkeypatch.setattr(
        workflow_runs,
        "_build_specialist_steps",
        lambda: {("task_quick_add", "infer_task_semantics"): object()},
    )
    monkeypatch.setattr(
        workflow_runs,
        "_build_resume_service",
        lambda *_args, **_kwargs: _FakeService(),
    )

    calls: list[tuple[int, str]] = []

    import helm_telegram_bot.services.digest_delivery as _dd
    monkeypatch.setattr(
        _dd.TelegramDigestDeliveryService,
        "notify_approval_needed",
        lambda self, run_id, proposal_summary: calls.append((run_id, proposal_summary)),
    )

    result = workflow_runs.run(handlers={("task_quick_add", "infer_task_semantics"): object()})

    assert result == 1
    assert calls == [(42, "")]


def test_no_notification_for_needs_action_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """notify_approval_needed is NOT called when state.run.needs_action=False."""
    state = _make_fake_state(needs_action=False, run_id=99, workflow_type="task_quick_add")

    class _FakeService:
        def resume_runnable_runs(self):
            return [state]

    monkeypatch.setattr(workflow_runs, "_resolve_bootstrap_user_id", lambda _: 1)
    monkeypatch.setattr(workflow_runs, "SessionLocal", _make_session_patcher())
    monkeypatch.setattr(
        workflow_runs,
        "_build_specialist_steps",
        lambda: {("task_quick_add", "infer_task_semantics"): object()},
    )
    monkeypatch.setattr(
        workflow_runs,
        "_build_resume_service",
        lambda *_args, **_kwargs: _FakeService(),
    )

    calls: list[tuple[int, str]] = []

    import helm_telegram_bot.services.digest_delivery as _dd
    monkeypatch.setattr(
        _dd.TelegramDigestDeliveryService,
        "notify_approval_needed",
        lambda self, run_id, proposal_summary: calls.append((run_id, proposal_summary)),
    )

    result = workflow_runs.run(handlers={("task_quick_add", "infer_task_semantics"): object()})

    assert result == 1
    assert calls == []


def test_notification_failure_does_not_crash_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """A RuntimeError in one notification does not stop the loop or change the return value."""
    state1 = _make_fake_state(needs_action=True, run_id=1, workflow_type="task_quick_add")
    state2 = _make_fake_state(needs_action=True, run_id=2, workflow_type="task_quick_add")

    class _FakeService:
        def resume_runnable_runs(self):
            return [state1, state2]

    monkeypatch.setattr(workflow_runs, "_resolve_bootstrap_user_id", lambda _: 1)
    monkeypatch.setattr(workflow_runs, "SessionLocal", _make_session_patcher())
    monkeypatch.setattr(
        workflow_runs,
        "_build_specialist_steps",
        lambda: {("task_quick_add", "infer_task_semantics"): object()},
    )
    monkeypatch.setattr(
        workflow_runs,
        "_build_resume_service",
        lambda *_args, **_kwargs: _FakeService(),
    )

    call_count = {"n": 0}

    def _flaky_notify(self, run_id, proposal_summary):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated notification failure")

    import helm_telegram_bot.services.digest_delivery as _dd
    monkeypatch.setattr(_dd.TelegramDigestDeliveryService, "notify_approval_needed", _flaky_notify)

    result = workflow_runs.run(handlers={("task_quick_add", "infer_task_semantics"): object()})

    assert result == 2
    assert call_count["n"] == 2


def test_proposal_summary_extracted_from_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    """proposal_summary is extracted from the SCHEDULE_PROPOSAL artifact when present."""
    artifact = types.SimpleNamespace(payload={"proposal_summary": "Schedule: test task"})
    latest_artifacts = {WorkflowArtifactType.SCHEDULE_PROPOSAL.value: artifact}
    state = _make_fake_state(
        needs_action=True,
        run_id=7,
        workflow_type="weekly_scheduling",
        latest_artifacts=latest_artifacts,
    )

    class _FakeService:
        def resume_runnable_runs(self):
            return [state]

    monkeypatch.setattr(workflow_runs, "_resolve_bootstrap_user_id", lambda _: 1)
    monkeypatch.setattr(workflow_runs, "SessionLocal", _make_session_patcher())
    monkeypatch.setattr(
        workflow_runs,
        "_build_specialist_steps",
        lambda: {("weekly_scheduling", "dispatch_calendar_agent"): object()},
    )
    monkeypatch.setattr(
        workflow_runs,
        "_build_resume_service",
        lambda *_args, **_kwargs: _FakeService(),
    )

    calls: list[tuple[int, str]] = []

    import helm_telegram_bot.services.digest_delivery as _dd
    monkeypatch.setattr(
        _dd.TelegramDigestDeliveryService,
        "notify_approval_needed",
        lambda self, run_id, proposal_summary: calls.append((run_id, proposal_summary)),
    )

    result = workflow_runs.run(
        handlers={("weekly_scheduling", "dispatch_calendar_agent"): object()}
    )

    assert result == 1
    assert calls == [(7, "Schedule: test task")]
