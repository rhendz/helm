import pytest

from helm_telegram_bot.commands import approve, workflows


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
    def __init__(self, args: list[str]) -> None:
        self.args = args


@pytest.mark.asyncio
async def test_workflow_start_usage_message_when_request_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    update = _Update()

    await workflows.start(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /workflow_start <request text>"]


@pytest.mark.asyncio
async def test_workflow_start_formats_created_run(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def start_run(self, *, request_text: str, submitted_by: str, chat_id: str) -> dict[str, object]:
            assert request_text == "Plan my week"
            assert submitted_by == "telegram:1"
            assert chat_id == "1"
            return {
                "id": 7,
                "status": "pending",
                "current_step": "normalize_request",
                "paused_state": None,
                "last_event_summary": "Workflow run created",
                "needs_action": False,
                "available_actions": [],
            }

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", _Service())
    update = _Update()

    await workflows.start(update, _Context(args=["Plan", "my", "week"]))

    assert update.message.replies == [
        "Run 7 [pending] step=normalize_request paused=active\n"
        "Last: Workflow run created\n"
        "Needs action: no | Next: none"
    ]


@pytest.mark.asyncio
async def test_workflow_replay_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen: tuple[int, str, str] | None = None

        def request_replay(self, run_id: int, *, actor: str, reason: str) -> dict[str, object]:
            self.seen = (run_id, actor, reason)
            return {
                "id": run_id,
                "status": "failed",
                "current_step": "apply_schedule",
                "paused_state": "awaiting_retry",
                "last_event_summary": "Explicit sync replay requested.",
                "needs_action": True,
                "available_actions": [],
                "safe_next_actions": [{"action": "await_replay", "label": "Await replay processing"}],
            }

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", service)
    update = _Update()

    await workflows.replay(update, _Context(args=["12", "Replay", "after", "adapter", "fix"]))

    assert service.seen == (12, "telegram:1", "Replay after adapter fix")
    assert update.message.replies == [
        "Run 12 [failed] step=apply_schedule paused=awaiting_retry\n"
        "Last: Explicit sync replay requested.\n"
        "Needs action: yes | Next: await_replay"
    ]


@pytest.mark.asyncio
async def test_workflow_approve_parses_ids_and_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen: tuple[int, int] | None = None

        def approve_run(self, run_id: int, *, actor: str, target_artifact_id: int) -> dict[str, object]:
            self.seen = (run_id, target_artifact_id)
            assert actor == "telegram:1"
            return {
                "id": run_id,
                "status": "pending",
                "current_step": "apply_schedule",
                "paused_state": None,
                "last_event_summary": "Approval granted and workflow resumed.",
                "needs_action": False,
                "available_actions": [],
                "latest_proposal_version": {"version_number": 1, "artifact_id": target_artifact_id},
            }

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_workflow_service", service)
    monkeypatch.setattr(approve, "_draft_service", object())
    update = _Update()

    await approve.handle(update, _Context(args=["7", "41"]))

    assert service.seen == (7, 41)
    assert update.message.replies == [
        "Run 7 [pending] step=apply_schedule paused=active\n"
        "Last: Approval granted and workflow resumed.\n"
        "Needs action: no | Next: none\n"
        "Latest proposal: v1 artifact=41"
    ]
