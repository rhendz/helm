"""Integration test for /task → DB state path.

Exercises the full inline execution flow used by the Telegram /task command:
    start_task_run → execute_task_run → [blocked, needs_action=True]
    → approve_run → execute_after_approval → [completed, needs_action=False]

Uses:
- In-memory SQLite (no external Postgres)
- Mocked LLM (no real OpenAI calls)
- StubCalendarSystemAdapter (no real Google Calendar calls)
- Time-freeze on helm_orchestration.scheduling.datetime to avoid past_event_guard flakiness

Corresponds to R113 / D007: integration test for the task_quick_add execution path.

## Observability Impact

Signals introduced / observable via this test:
- structlog entries from `upsert_calendar_block` (issued by StubCalendarSystemAdapter during
  `execute_after_approval`) include `planned_item_key` — filter for key="upsert_calendar_block"
  to confirm the calendar write was reached.
- `WorkflowRunStatus` transitions (PENDING → BLOCKED → PENDING → COMPLETED) are observable
  via `GET /v1/workflow-runs/{run_id}` or `WorkflowStatusService.get_run_detail(run_id)`.
- `needs_action` flips True → False across the approval boundary — query `WorkflowRun` directly
  for post-hoc inspection: `SELECT status, needs_action FROM workflow_runs WHERE id = <run_id>`.
- `_build_calendar_adapter()` logs `calendar_adapter_fallback_to_stub` at WARNING when
  Google credentials are absent (which they are in this test); this is expected and harmless.
- Failure visibility: if `past_event_guard` fires, the test fails at `execute_task_run` with
  `PastEventError` — this means the time-freeze patch was not applied correctly.
- Inspection surface: `session.get(WorkflowRunORM, run_id)` gives the raw ORM state at any
  point; no external service required.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime as _real_datetime
from typing import TYPE_CHECKING
from unittest.mock import patch as _mock_patch

from helm_api.dependencies import get_db
from helm_api.main import app
from helm_api.services.workflow_status_service import WorkflowStatusService
from helm_orchestration import TaskSemantics
from helm_storage.db import Base, SessionLocal
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if TYPE_CHECKING:
    from collections.abc import Generator

# ---------------------------------------------------------------------------
# Time-freeze constant: 2099-01-05 is a Monday — all Mon-Fri 9am+ slots are
# far in the future so past_event_guard never fires.
# ---------------------------------------------------------------------------
_FUTURE_MONDAY_MIDNIGHT_UTC = _real_datetime(2099, 1, 5, 0, 1, 0, tzinfo=UTC)


class _SessionContext:
    """Lightweight context manager that wraps a test Session.

    Mimics the behaviour of SQLAlchemy's sessionmaker().__call__().__enter__()
    without actually opening a new session — the test shares a single transaction
    so all reads/writes are immediately visible to every service call.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def __enter__(self) -> Session:
        return self._session

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session() -> tuple[Session, object]:
    """Create an in-memory SQLite engine + session with all tables created."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    session = TestingSessionLocal()
    return session, engine


def _override_session_local(session: Session):
    """Return a callable that produces a _SessionContext wrapping *session*."""
    return lambda: _SessionContext(session)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_task_execution_creates_blocked_run_and_completes_after_approval(
    monkeypatch,  # noqa: ANN001
) -> None:
    """Full /task → DB state integration test.

    Proves that the inline task_quick_add execution path produces the correct
    WorkflowRun state transitions:

        start_task_run           → status=pending,  needs_action=False
        execute_task_run         → status=blocked,  needs_action=True
        approve_run              → status=pending,  needs_action=False
        execute_after_approval   → status=completed, needs_action=False
    """
    session, _engine = _make_session()

    # -----------------------------------------------------------------------
    # Override FastAPI's get_db so any API layer that uses DI gets the same
    # in-memory session.
    # -----------------------------------------------------------------------
    def _override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = _override_get_db

    try:
        # -------------------------------------------------------------------
        # Patch SessionLocal everywhere it's used by the services under test.
        # TelegramWorkflowStatusService imports SessionLocal from helm_storage.db
        # at module level, then uses it in start_task_run, execute_task_run,
        # execute_after_approval, and approve_run.
        # -------------------------------------------------------------------
        session_factory = _override_session_local(session)
        import helm_telegram_bot.services.workflow_status_service as _tg_svc
        monkeypatch.setattr(_tg_svc, "SessionLocal", session_factory)

        # helm_worker.jobs.workflow_runs.SessionLocal is used by the run() loop
        # (not directly exercised here, but patched for safety).
        import helm_worker.jobs.workflow_runs as _wf_job
        monkeypatch.setattr(_wf_job, "SessionLocal", session_factory)

        # -------------------------------------------------------------------
        # Freeze scheduling time: patch helm_orchestration.scheduling.datetime
        # so compute_reference_week and past_event_guard see 2099-01-05 00:01 UTC.
        # The mock's side_effect delegates constructor calls to the real datetime
        # so ScheduleBlock.start/end remain valid ISO strings.
        # -------------------------------------------------------------------
        with _mock_patch("helm_orchestration.scheduling.datetime") as mock_dt:
            mock_dt.now.return_value = _FUTURE_MONDAY_MIDNIGHT_UTC
            mock_dt.side_effect = lambda *args, **kw: _real_datetime(*args, **kw)

            # ---------------------------------------------------------------
            # Known task semantics — no LLM call needed.
            # ---------------------------------------------------------------
            semantics = TaskSemantics(
                urgency="low",
                priority="low",
                sizing_minutes=60,
                confidence=0.9,
            )

            svc = TelegramWorkflowStatusService()

            # ---------------------------------------------------------------
            # Step 1: create a task_quick_add run.
            # ---------------------------------------------------------------
            created = svc.start_task_run(
                request_text="dentist Monday 9am",
                submitted_by="test-user",
                chat_id="test-chat",
            )
            run_id: int = created["id"]
            assert created["status"] == "pending", f"Expected pending, got {created['status']}"
            assert created["needs_action"] is False

            # ---------------------------------------------------------------
            # Step 2: inline execution — builds CalendarAgentOutput from
            # semantics, calls complete_current_step, blocks at approval.
            # We mock Google credentials so _build_calendar_adapter falls
            # back to StubCalendarSystemAdapter (no real API calls).
            # ---------------------------------------------------------------
            with (
                _mock_patch("google.oauth2.credentials.Credentials"),
                _mock_patch("googleapiclient.discovery.build"),
            ):
                execute_result = svc.execute_task_run(
                    run_id,
                    semantics=semantics,
                    request_text="dentist Monday 9am",
                )

            assert execute_result["status"] == "blocked", (
                f"Expected blocked after execute_task_run, got {execute_result['status']!r}"
            )
            assert execute_result["needs_action"] is True, (
                "Expected needs_action=True after execute_task_run"
            )

            # Retrieve approval checkpoint details from DB state
            run_detail = WorkflowStatusService(session).get_run_detail(run_id)
            assert run_detail is not None
            checkpoint = run_detail["approval_checkpoint"]
            assert checkpoint is not None, "Expected approval_checkpoint to be populated"
            target_artifact_id: int = checkpoint["target_artifact_id"]
            assert target_artifact_id > 0

            # ---------------------------------------------------------------
            # Step 3: approve the run.
            # ---------------------------------------------------------------
            approved = WorkflowStatusService(session).approve_run(
                run_id,
                actor="test-user",
                target_artifact_id=target_artifact_id,
            )
            assert approved["status"] == "pending", (
                f"Expected pending after approve_run, got {approved['status']!r}"
            )
            assert approved["current_step"] == "apply_schedule", (
                f"Expected apply_schedule, got {approved['current_step']!r}"
            )

            # ---------------------------------------------------------------
            # Step 4: execute_after_approval drives the apply_schedule step.
            # StubCalendarSystemAdapter is used (Google credentials absent).
            # ---------------------------------------------------------------
            with (
                _mock_patch("google.oauth2.credentials.Credentials"),
                _mock_patch("googleapiclient.discovery.build"),
            ):
                final_result = svc.execute_after_approval(run_id)

            assert final_result["status"] == "completed", (
                f"Expected completed after execute_after_approval, got {final_result['status']!r}"
            )
            assert final_result["needs_action"] is False, (
                "Expected needs_action=False after execute_after_approval"
            )

    finally:
        app.dependency_overrides.clear()
        session.close()
