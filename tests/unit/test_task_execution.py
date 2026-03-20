"""Unit tests for inline execution path: /task → orchestration, /approve → inline resume.

Covers:
  1. Inline execution after inference produces needs_action=True with approval notification
  2. Inline execution with needs_action=False produces success notification
  3. execute_task_run raising → user-facing error push (not silent failure)
  4. PastEventError during execute_task_run → user-friendly past-time message
  5. None returned from LLMClient.infer_task_semantics → user-facing error pushed
  6. /approve calls execute_after_approval after successful approve_run
  7. /approve inline execution failure → approval still confirmed (graceful fallback)
  8. _build_specialist_steps() includes ('task_quick_add', 'infer_task_semantics') key
  9. task_quick_add step: artifact_type=SCHEDULE_PROPOSAL and next_step_name="apply_schedule"
  10. Worker recovery step handler (_run_task_inference) produces CalendarAgentOutput
"""
from __future__ import annotations

import pytest
from helm_orchestration import PastEventError, TaskSemantics
from helm_telegram_bot.commands import approve, task


class _Message:
    def __init__(self) -> None:
        self.replies: list[str] = []
        self.chat_id = 100

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _User:
    def __init__(self) -> None:
        self.id = 42


class _Update:
    def __init__(self) -> None:
        self.message = _Message()
        self.effective_user = _User()


class _Context:
    def __init__(self, args: list[str]) -> None:
        self.args = args


# ---------------------------------------------------------------------------
# 1. Inline execution → needs_action=True → approval notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_task_async_needs_action_sends_approval_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_semantics = TaskSemantics(
        urgency="high",
        priority="high",
        sizing_minutes=30,
        confidence=0.95,
    )

    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            return fixed_semantics

    class _FakeService:
        def execute_task_run(
            self, run_id: int, *, semantics: TaskSemantics, request_text: str
        ) -> dict[str, object]:
            return {
                "id": run_id,
                "status": "blocked",
                "needs_action": True,
                "approval_checkpoint": {
                    "target_artifact_id": 101,
                    "proposal_summary": "Schedule: book dentist tomorrow",
                },
            }

    monkeypatch.setattr(task, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(task, "_service", _FakeService())

    update = _Update()
    await task._run_task_async(update, "book dentist tomorrow", run_id=5)

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    # Must include run ID, artifact ID, and /approve hint
    assert "⏳" in reply
    assert "run 5" in reply
    assert "101" in reply
    assert "/approve 5 101" in reply


# ---------------------------------------------------------------------------
# 2. Inline execution → needs_action=False → success notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_task_async_completed_sends_success_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            return TaskSemantics(urgency="low", priority="low", sizing_minutes=60, confidence=0.9)

    class _FakeService:
        def execute_task_run(
            self, run_id: int, *, semantics: TaskSemantics, request_text: str
        ) -> dict[str, object]:
            return {
                "id": run_id,
                "status": "completed",
                "needs_action": False,
                "approval_checkpoint": None,
            }

    monkeypatch.setattr(task, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(task, "_service", _FakeService())

    update = _Update()
    await task._run_task_async(update, "quick note", run_id=7)

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "✅" in reply
    assert "7" in reply


# ---------------------------------------------------------------------------
# 3. execute_task_run raising generic exception → user-facing error push
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_task_async_execution_error_pushes_error_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            return TaskSemantics(urgency="low", priority="low", sizing_minutes=60, confidence=0.9)

    class _FakeService:
        def execute_task_run(
            self, run_id: int, *, semantics: TaskSemantics, request_text: str
        ) -> dict[str, object]:
            raise RuntimeError("DB connection lost")

    monkeypatch.setattr(task, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(task, "_service", _FakeService())

    update = _Update()
    await task._run_task_async(update, "some task", run_id=13)

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "❌" in reply
    assert "13" in reply
    assert "/task" in reply


# ---------------------------------------------------------------------------
# 4. PastEventError → user-friendly "time is in the past" message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_task_async_past_event_error_friendly_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            return TaskSemantics(urgency="low", priority="low", sizing_minutes=60, confidence=0.9)

    class _FakeService:
        def execute_task_run(
            self, run_id: int, *, semantics: TaskSemantics, request_text: str
        ) -> dict[str, object]:
            raise PastEventError("2024-01-01 is before now")

    monkeypatch.setattr(task, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(task, "_service", _FakeService())

    update = _Update()
    await task._run_task_async(update, "book meeting last week", run_id=20)

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "past" in reply.lower()
    # Should NOT show the generic error ❌
    assert "❌" not in reply


# ---------------------------------------------------------------------------
# 5. /approve calls execute_after_approval after successful approve_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_triggers_inline_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    execute_after_approval_called: list[int] = []

    class _FakeWorkflowService:
        def approve_run(
            self, run_id: int, *, actor: str, target_artifact_id: int
        ) -> dict[str, object]:
            return {
                "id": run_id,
                "status": "pending",
                "needs_action": False,
                "approval_checkpoint": None,
            }

        def execute_after_approval(self, run_id: int) -> dict[str, object]:
            execute_after_approval_called.append(run_id)
            return {"id": run_id, "status": "completed", "needs_action": False}

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_workflow_service", _FakeWorkflowService())

    update = _Update()
    ctx = _Context(args=["5", "101"])

    await approve.handle(update, ctx)

    # execute_after_approval was called with the run_id
    assert execute_after_approval_called == [5]
    # Single reply: "Approved — syncing to calendar…"
    assert len(update.message.replies) == 1
    assert "syncing" in update.message.replies[0].lower() or "Approved" in update.message.replies[0]


# ---------------------------------------------------------------------------
# 6. _build_specialist_steps() includes task_quick_add handler
# ---------------------------------------------------------------------------


def test_build_specialist_steps_includes_task_quick_add() -> None:
    from helm_worker.jobs.workflow_runs import _build_specialist_steps

    steps = _build_specialist_steps()
    assert ("task_quick_add", "infer_task_semantics") in steps
    step = steps[("task_quick_add", "infer_task_semantics")]
    assert step.workflow_type == "task_quick_add"
    assert step.step_name == "infer_task_semantics"
    assert step.next_step_name == "apply_schedule"


# ---------------------------------------------------------------------------
# 7. Worker recovery handler produces CalendarAgentOutput from request_text
# ---------------------------------------------------------------------------


def test_run_task_inference_produces_calendar_agent_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from helm_orchestration import CalendarAgentOutput, TaskSemantics
    from helm_worker.jobs import workflow_runs

    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            return TaskSemantics(
                urgency="high", priority="high", sizing_minutes=45, confidence=0.9,
                suggested_date="2099-01-06",
            )

    monkeypatch.setattr(workflow_runs, "LLMClient", _FakeLLMClient)

    result = workflow_runs._run_task_inference("dentist appointment")

    assert isinstance(result, CalendarAgentOutput)
    assert len(result.time_blocks) == 1
    assert "dentist" in result.time_blocks[0].title.lower()
    assert result.time_blocks[0].start is not None
    assert result.time_blocks[0].end is not None
    assert "dentist" in result.proposal_summary.lower()


def test_run_task_inference_no_explicit_time_uses_future_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When LLM returns no suggested_date, fallback slot must be in the future.

    Regression guard: old code used parse_local_slot + week_start fallback which
    placed tasks on Monday 9am — already in the past mid-week.
    """
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch
    from zoneinfo import ZoneInfo

    from helm_orchestration import CalendarAgentOutput, TaskSemantics
    from helm_worker.jobs import workflow_runs

    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            # No suggested_date — LLM couldn't infer one
            return TaskSemantics(urgency="low", priority="low", sizing_minutes=30, confidence=0.9)

    # Simulate Thursday at noon
    thursday_noon = datetime(2099, 1, 9, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    monkeypatch.setattr(workflow_runs, "LLMClient", _FakeLLMClient)

    real_datetime = datetime

    class _MockDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return thursday_noon

    with patch("helm_worker.jobs.workflow_runs.datetime", _MockDatetime):
        # Must not raise PastEventError
        result = workflow_runs._run_task_inference("book dentist appointment this week")

    assert isinstance(result, CalendarAgentOutput)
    start_dt = datetime.fromisoformat(result.time_blocks[0].start)
    assert start_dt > thursday_noon.astimezone(timezone.utc).replace(tzinfo=timezone.utc), (
        "fallback slot must be strictly in the future"
    )


# ---------------------------------------------------------------------------
# 8. LLMClient.infer_task_semantics returns None → user-facing error pushed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_inference_returns_none_pushes_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the LLM returns None semantics, a user-facing error is pushed (not silently dropped)."""

    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics | None:
            return None  # simulate LLM returning no result

    monkeypatch.setattr(task, "LLMClient", _FakeLLMClient)

    update = _Update()
    await task._run_task_async(update, "ambiguous task text", run_id=88)

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "❌" in reply
    assert "88" in reply
    assert "/task" in reply


# ---------------------------------------------------------------------------
# 9. /approve inline execution failure → approval still confirmed (graceful fallback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_inline_execution_failure_still_confirms_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If execute_after_approval raises, the operator still gets an approval confirmation
    with a graceful fallback message (calendar sync completing shortly)."""

    class _FakeWorkflowService:
        def approve_run(
            self, run_id: int, *, actor: str, target_artifact_id: int
        ) -> dict[str, object]:
            return {
                "id": run_id,
                "status": "pending",
                "needs_action": False,
                "approval_checkpoint": None,
            }

        def execute_after_approval(self, run_id: int) -> dict[str, object]:
            raise RuntimeError("worker pool unavailable")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_workflow_service", _FakeWorkflowService())

    update = _Update()
    ctx = _Context(args=["9", "55"])

    await approve.handle(update, ctx)

    # Single reply: fallback message since inline execution failed
    assert len(update.message.replies) == 1
    assert "shortly" in update.message.replies[0]


# ---------------------------------------------------------------------------
# 10. task_quick_add step: artifact_type=SCHEDULE_PROPOSAL, next_step_name=apply_schedule
# ---------------------------------------------------------------------------


def test_task_quick_add_step_handler_produces_schedule_proposal() -> None:
    """The task_quick_add recovery step must declare SCHEDULE_PROPOSAL output
    and advance to apply_schedule — these are the contract for the approval checkpoint."""
    from helm_orchestration import WorkflowArtifactKind
    from helm_worker.jobs.workflow_runs import _build_specialist_steps

    steps = _build_specialist_steps()
    step = steps[("task_quick_add", "infer_task_semantics")]
    assert step.artifact_type == WorkflowArtifactKind.SCHEDULE_PROPOSAL
    assert step.next_step_name == "apply_schedule"
