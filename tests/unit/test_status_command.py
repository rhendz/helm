import pytest
from helm_telegram_bot.commands import status
from helm_telegram_bot.services.digest_delivery import TelegramDigestDeliveryService


class _Message:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _Update:
    def __init__(self, *, user_id: int = 1) -> None:
        self.message = _Message()
        self.effective_user = type("User", (), {"id": user_id})()


class _Context:
    def __init__(self, args: list[str] | None = None) -> None:
        self.args = args or []


class _Settings:
    operator_timezone = "America/Los_Angeles"


class _Service:
    def __init__(
        self,
        *,
        pending: list[dict] | None = None,
        recent: list[dict] | None = None,
    ) -> None:
        self._pending = pending or []
        self._recent = recent or []

    def list_runs_needing_action(self, *, limit: int = 5) -> list[dict]:
        return self._pending[:limit]

    def list_recent_runs(self, *, limit: int = 5) -> list[dict]:
        return self._recent[:limit]


async def _allow(_update: object, _context: object) -> bool:
    return False


@pytest.mark.asyncio
async def test_status_no_pending_approvals_no_recent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(status, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(status, "_service", _Service())
    monkeypatch.setattr(status, "get_settings", lambda: _Settings())

    update = _Update()
    await status.handle(update, _Context())

    assert len(update.message.replies) == 1
    reply = update.message.replies[0]
    assert "✅ No pending approvals." in reply
    assert "No recent activity." in reply


@pytest.mark.asyncio
async def test_status_shows_pending_approval_with_approve_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = [
        {
            "id": 7,
            "needs_action": True,
            "workflow_type": "weekly_scheduling",
            "approval_checkpoint": {
                "target_artifact_id": 42,
                "proposal_summary": "Schedule: dentist",
            },
            "completion_summary": None,
            "last_event_summary": "awaiting approval",
        }
    ]
    monkeypatch.setattr(status, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(status, "_service", _Service(pending=pending))
    monkeypatch.setattr(status, "get_settings", lambda: _Settings())

    update = _Update()
    await status.handle(update, _Context())

    reply = update.message.replies[0]
    assert "/approve 7 42" in reply
    assert "Schedule: dentist" in reply


@pytest.mark.asyncio
async def test_status_shows_recent_completions(monkeypatch: pytest.MonkeyPatch) -> None:
    recent = [
        {
            "id": 3,
            "needs_action": False,
            "workflow_type": "weekly_scheduling",
            "approval_checkpoint": None,
            "completion_summary": {"headline": "Scheduled 3 blocks"},
            "last_event_summary": "completed",
        }
    ]
    monkeypatch.setattr(status, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(status, "_service", _Service(recent=recent))
    monkeypatch.setattr(status, "get_settings", lambda: _Settings())

    update = _Update()
    await status.handle(update, _Context())

    reply = update.message.replies[0]
    assert "Scheduled 3 blocks" in reply


@pytest.mark.asyncio
async def test_status_shows_operator_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(status, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(status, "_service", _Service())
    monkeypatch.setattr(status, "get_settings", lambda: _Settings())

    update = _Update()
    await status.handle(update, _Context())

    reply = update.message.replies[0]
    assert "America/Los_Angeles" in reply


@pytest.mark.asyncio
async def test_status_no_debug_internals(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = [
        {
            "id": 7,
            "needs_action": True,
            "workflow_type": "weekly_scheduling",
            "approval_checkpoint": {
                "target_artifact_id": 42,
                "proposal_summary": "Schedule: dentist",
            },
            "completion_summary": None,
            "last_event_summary": "awaiting approval",
            "current_step": "awaiting_approval",
            "paused_state": "approval_pending",
        }
    ]
    recent = [
        {
            "id": 3,
            "needs_action": False,
            "workflow_type": "weekly_scheduling",
            "approval_checkpoint": None,
            "completion_summary": {"headline": "Scheduled 3 blocks"},
            "last_event_summary": "completed",
            "current_step": "done",
            "paused_state": None,
        }
    ]
    monkeypatch.setattr(status, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(status, "_service", _Service(pending=pending, recent=recent))
    monkeypatch.setattr(status, "get_settings", lambda: _Settings())

    update = _Update()
    await status.handle(update, _Context())

    reply = update.message.replies[0]
    assert "current_step" not in reply
    assert "paused_state" not in reply
    # "sync" may appear in words like "Timezone" — check for standalone debug patterns
    assert "total_sync_writes" not in reply
    assert "downstream_sync_status" not in reply


def test_notify_approval_needed_calls_deliver(monkeypatch: pytest.MonkeyPatch) -> None:
    delivered: list[str] = []

    monkeypatch.setattr(
        TelegramDigestDeliveryService,
        "deliver",
        lambda self, text: delivered.append(text),
    )

    svc = TelegramDigestDeliveryService()
    svc.notify_approval_needed(run_id=7, proposal_summary="Schedule: dentist")

    assert len(delivered) == 1
    text = delivered[0]
    assert "run 7" in text
    assert "/approve 7" in text
