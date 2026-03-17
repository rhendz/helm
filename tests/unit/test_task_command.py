"""Unit tests for the /task command handler (task.py).

Follows the same stub pattern as test_workflow_telegram_commands.py:
  - _Message captures replies
  - _Update wraps message + effective_user
  - _Context wraps args + application stub
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from helm_orchestration import ApprovalAction, TaskSemantics
from helm_orchestration.schemas import ApprovalDecision
from helm_telegram_bot.commands import task


class _Message:
    def __init__(self, *, chat_id: int = 100) -> None:
        self.replies: list[str] = []
        self.chat_id = chat_id

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _Update:
    def __init__(self, *, user_id: int = 1) -> None:
        self.message = _Message()
        self.effective_user = type("User", (), {"id": user_id})()


class _Application:
    """Captures coroutines passed to create_task() for manual execution in tests."""

    def __init__(self) -> None:
        self.created_tasks: list = []

    def create_task(self, coro, *, update=None) -> MagicMock:  # noqa: ANN001
        self.created_tasks.append(coro)
        mock = MagicMock()
        return mock


class _Context:
    def __init__(self, args: list[str]) -> None:
        self.args = args
        self.application = _Application()


# ---------------------------------------------------------------------------
# Test: no args → usage message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_no_args_returns_usage_message(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(task, "reject_if_unauthorized", _allow)
    update = _Update()

    await task.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /task <description>"]
    assert update.message.chat_id == 100  # sanity: no extra replies


# ---------------------------------------------------------------------------
# Test: ack sent immediately before background task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_ack_sent_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def start_task_run(
            self, *, request_text: str, submitted_by: str, chat_id: str
        ) -> dict[str, object]:
            return {"id": 42, "status": "pending"}

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(task, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(task, "_service", _Service())
    update = _Update()
    ctx = _Context(args=["book", "flights"])

    await task.handle(update, ctx)

    # First reply must be the ack
    assert len(update.message.replies) == 1
    assert "Task received" in update.message.replies[0]
    assert "analyzing" in update.message.replies[0]
    assert "42" in update.message.replies[0]


# ---------------------------------------------------------------------------
# Test: background task created after ack
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_background_task_created(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def start_task_run(
            self, *, request_text: str, submitted_by: str, chat_id: str
        ) -> dict[str, object]:
            assert request_text == "book flights this week"
            assert submitted_by == "telegram:1"
            return {"id": 7, "status": "pending"}

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(task, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(task, "_service", _Service())
    update = _Update()
    ctx = _Context(args=["book", "flights", "this", "week"])

    await task.handle(update, ctx)

    # A coroutine was queued
    assert len(ctx.application.created_tasks) == 1
    assert asyncio.iscoroutine(ctx.application.created_tasks[0])
    # Clean up the coroutine to avoid runtime warning
    ctx.application.created_tasks[0].close()


# ---------------------------------------------------------------------------
# Test: successful inference → formatted outcome with auto-approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_successful_inference_auto_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_semantics = TaskSemantics(
        urgency="high",
        priority="high",
        sizing_minutes=30,
        confidence=0.95,
    )
    fixed_decision = ApprovalDecision(
        action=ApprovalAction.APPROVE,
        actor="system:conditional_policy",
        target_artifact_id=0,
    )

    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            return fixed_semantics

    class _FakePolicy:
        def evaluate(self, semantics: TaskSemantics) -> ApprovalDecision:
            return fixed_decision

    monkeypatch.setattr(task, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(task, "_policy", _FakePolicy())

    update = _Update()
    await task._run_task_async(update, "book flights", run_id=99)

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "Task Analysis" in reply
    assert "run 99" in reply
    assert "high" in reply  # urgency
    assert "30min" in reply  # sizing
    assert "95%" in reply  # confidence
    assert "Auto-approved" in reply
    assert "✅" in reply


# ---------------------------------------------------------------------------
# Test: successful inference → needs review (low confidence)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_successful_inference_needs_review(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed_semantics = TaskSemantics(
        urgency="low",
        priority="medium",
        sizing_minutes=180,
        confidence=0.60,
    )
    fixed_decision = ApprovalDecision(
        action=ApprovalAction.REQUEST_REVISION,
        actor="system:conditional_policy",
        target_artifact_id=0,
        revision_feedback="Confidence or sizing outside auto-approve thresholds",
    )

    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            return fixed_semantics

    class _FakePolicy:
        def evaluate(self, semantics: TaskSemantics) -> ApprovalDecision:
            return fixed_decision

    monkeypatch.setattr(task, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(task, "_policy", _FakePolicy())

    update = _Update()
    await task._run_task_async(update, "refactor entire codebase", run_id=55)

    reply = update.message.replies[0]
    assert "Needs review" in reply
    assert "⚠️" in reply
    assert "Reason: Confidence or sizing outside auto-approve thresholds" in reply
    assert "180min" in reply
    assert "60%" in reply


# ---------------------------------------------------------------------------
# Test: inference failure → error message pushed to operator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_inference_failure_pushes_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeLLMClient:
        def infer_task_semantics(self, text: str) -> TaskSemantics:
            raise RuntimeError("OpenAI connection timeout")

    monkeypatch.setattr(task, "LLMClient", _FakeLLMClient)

    update = _Update()
    await task._run_task_async(update, "some task", run_id=13)

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "❌" in reply
    assert "Task analysis failed" in reply
    assert "13" in reply  # run_id in error message
    assert "/task" in reply  # retry hint


# ---------------------------------------------------------------------------
# Test: start_task_run creates a run with correct workflow_type
# ---------------------------------------------------------------------------


def test_start_task_run_uses_task_quick_add_workflow_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify start_task_run passes workflow_type='task_quick_add' to create_run."""
    from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

    received_payload = []

    class _FakeOrchestrationService:
        def create_run(self, payload) -> dict[str, object]:  # noqa: ANN001
            received_payload.append(payload)
            return {"id": 1, "status": "pending"}

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    import helm_telegram_bot.services.workflow_status_service as svc_mod

    monkeypatch.setattr(svc_mod, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(
        svc_mod,
        "WorkflowStatusService",
        lambda session: _FakeOrchestrationService(),
    )

    svc = TelegramWorkflowStatusService()
    result = svc.start_task_run(
        request_text="book flights", submitted_by="telegram:1", chat_id="100"
    )

    assert result["id"] == 1
    assert len(received_payload) == 1
    payload = received_payload[0]
    # WorkflowRunCreateInput is a Pydantic/dataclass object with attributes
    assert payload.workflow_type == "task_quick_add"
    assert payload.first_step_name == "infer_task_semantics"
