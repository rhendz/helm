"""Unit tests for inline execution path: /task → orchestration, /approve → inline resume.

Covers:
  1. Inline execution after inference produces needs_action=True with approval notification
  2. Inline execution with needs_action=False produces success notification
  3. execute_task_run raising → user-facing error push (not silent failure)
  4. PastEventError during execute_task_run → user-friendly past-time message
  5. /approve calls execute_after_approval after successful approve_run
  6. _build_specialist_steps() includes ('task_quick_add', 'infer_task_semantics') key
  7. Worker recovery step handler (_run_task_inference) produces CalendarAgentOutput
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
    monkeypatch.setattr(approve, "_format_run", lambda result: f"run {result['id']}")

    update = _Update()
    ctx = _Context(args=["5", "101"])

    await approve.handle(update, ctx)

    # execute_after_approval was called with the run_id
    assert execute_after_approval_called == [5]
    # At least two replies: formatted run + "Approved and syncing" message
    replies_text = " ".join(update.message.replies)
    assert "syncing" in replies_text or "Approved" in replies_text


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
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from helm_orchestration import CalendarAgentOutput, TaskSemantics
    from helm_worker.jobs import workflow_runs

    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            return TaskSemantics(urgency="high", priority="high", sizing_minutes=45, confidence=0.9)

    # Return next Monday at midnight so past_event_guard doesn't trigger
    future_monday = datetime(2099, 1, 6, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))

    monkeypatch.setattr(workflow_runs, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(workflow_runs, "compute_reference_week", lambda tz: future_monday)

    result = workflow_runs._run_task_inference("dentist appointment")

    assert isinstance(result, CalendarAgentOutput)
    assert len(result.time_blocks) == 1
    assert "dentist" in result.time_blocks[0].title.lower()
    assert result.time_blocks[0].start is not None
    assert result.time_blocks[0].end is not None
    # Proposal summary should reference the request text
    assert "dentist" in result.proposal_summary.lower()
