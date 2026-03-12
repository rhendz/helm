import pytest
from helm_telegram_bot.commands import actions, approve, common, digest, drafts, snooze, workflows


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


class _Action:
    def __init__(self, item_id: int, priority: int, title: str) -> None:
        self.id = item_id
        self.priority = priority
        self.title = title


class _Draft:
    def __init__(self, draft_id: int, status: str, draft_text: str) -> None:
        self.id = draft_id
        self.status = status
        self.draft_text = draft_text


def test_parse_single_id_arg() -> None:
    assert common.parse_single_id_arg(["42"]) == 42
    assert common.parse_single_id_arg([]) is None
    assert common.parse_single_id_arg(["abc"]) is None
    assert common.parse_single_id_arg(["0"]) is None
    assert common.parse_single_id_arg(["1", "2"]) is None


@pytest.mark.asyncio
async def test_reject_if_unauthorized_replies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(common, "is_allowed_user", lambda _update: False)
    update = _Update()

    rejected = await common.reject_if_unauthorized(update, _Context(args=[]))

    assert rejected is True
    assert update.message.replies == ["Unauthorized user."]


@pytest.mark.asyncio
async def test_approve_usage_message_when_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    update = _Update()

    await approve.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /approve <run_id>"]


@pytest.mark.asyncio
async def test_approve_parses_id_and_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_id: int | None = None

        def approve_run(self, run_id: int, *, actor: str) -> dict[str, object]:
            self.seen_id = run_id
            assert actor == "telegram:1"
            return {
                "id": run_id,
                "status": "pending",
                "current_step": "apply_schedule",
                "paused_state": None,
                "last_event_summary": "Approval granted and workflow resumed.",
                "needs_action": False,
                "available_actions": [],
            }

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_service", service)
    update = _Update()

    await approve.handle(update, _Context(args=["7"]))

    assert service.seen_id == 7
    assert update.message.replies == [
        "Run 7 [pending] step=apply_schedule paused=active\n"
        "Last: Approval granted and workflow resumed.\n"
        "Needs action: no | Next: none"
    ]


@pytest.mark.asyncio
async def test_approve_unauthorized_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def approve_run(self, run_id: int, *, actor: str) -> dict[str, object]:
            raise AssertionError(f"service should not be called: {run_id} {actor}")

    async def _deny(_update: _Update, _context: _Context) -> bool:
        return True

    monkeypatch.setattr(approve, "reject_if_unauthorized", _deny)
    monkeypatch.setattr(approve, "_service", _Service())
    update = _Update()

    await approve.handle(update, _Context(args=["9"]))

    assert update.message.replies == []


@pytest.mark.asyncio
async def test_reject_usage_message_when_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    update = _Update()

    await approve.reject(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /reject <run_id>"]


@pytest.mark.asyncio
async def test_request_revision_calls_service_with_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen: tuple[int, str, str] | None = None

        def request_revision(self, run_id: int, *, actor: str, feedback: str) -> dict[str, object]:
            self.seen = (run_id, actor, feedback)
            return {
                "id": run_id,
                "status": "pending",
                "current_step": "dispatch_calendar_agent",
                "paused_state": None,
                "last_event_summary": "Revision requested and workflow resumed at proposal generation.",
                "needs_action": False,
                "available_actions": [],
                "latest_decision": {
                    "decision": "request_revision",
                    "actor": actor,
                    "decision_at": "2026-03-13T10:00:00Z",
                    "revision_feedback": feedback,
                },
            }

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_service", service)
    update = _Update()

    await approve.request_revision(update, _Context(args=["11", "Keep", "Friday", "free"]))

    assert service.seen == (11, "telegram:1", "Keep Friday free")
    assert update.message.replies == [
        "Run 11 [pending] step=dispatch_calendar_agent paused=active\n"
        "Last: Revision requested and workflow resumed at proposal generation.\n"
        "Needs action: no | Next: none\n"
        "Latest decision: request_revision by telegram:1"
    ]


@pytest.mark.asyncio
async def test_snooze_usage_message_when_id_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(snooze, "reject_if_unauthorized", _allow)
    update = _Update()

    await snooze.handle(update, _Context(args=["oops"]))

    assert update.message.replies == ["Usage: /snooze <id>"]


@pytest.mark.asyncio
async def test_digest_command_replies_with_generated_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(digest, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(digest, "build_daily_digest", lambda: "Daily Brief\n1. Ship feature.")
    update = _Update()

    await digest.handle(update, _Context(args=[]))

    assert update.message.replies == ["Daily Brief\n1. Ship feature."]


@pytest.mark.asyncio
async def test_actions_command_replies_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_open_actions(self) -> list[_Action]:
            return []

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(actions, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(actions, "_service", _Service())
    update = _Update()

    await actions.handle(update, _Context(args=[]))

    assert update.message.replies == ["No open actions."]


@pytest.mark.asyncio
async def test_actions_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_open_actions(self) -> list[_Action]:
            return [
                _Action(item_id=3, priority=1, title="Reply to recruiter"),
                _Action(item_id=2, priority=2, title="Review draft"),
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(actions, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(actions, "_service", _Service())
    update = _Update()

    await actions.handle(update, _Context(args=[]))

    assert update.message.replies == [
        "Open actions:\n3: P1 Reply to recruiter\n2: P2 Review draft"
    ]


@pytest.mark.asyncio
async def test_drafts_command_replies_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_pending_drafts(self) -> list[_Draft]:
            return []

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(drafts, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(drafts, "_service", _Service())
    update = _Update()

    await drafts.handle(update, _Context(args=[]))

    assert update.message.replies == ["No pending drafts."]


@pytest.mark.asyncio
async def test_drafts_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_pending_drafts(self) -> list[_Draft]:
            return [
                _Draft(draft_id=1, status="pending", draft_text="First line\nSecond line"),
                _Draft(draft_id=2, status="snoozed", draft_text="Need follow-up"),
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(drafts, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(drafts, "_service", _Service())
    update = _Update()

    await drafts.handle(update, _Context(args=[]))

    assert update.message.replies == [
        (
            "Pending drafts:\n"
            "1: pending First line Second line\n"
            "2: snoozed Need follow-up\n"
            "Use /approve <id> or /snooze <id>."
        )
    ]


@pytest.mark.asyncio
async def test_actions_unauthorized_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_open_actions(self) -> list[_Action]:
            raise AssertionError("service should not be called")

    async def _deny(_update: _Update, _context: _Context) -> bool:
        return True

    monkeypatch.setattr(actions, "reject_if_unauthorized", _deny)
    monkeypatch.setattr(actions, "_service", _Service())
    update = _Update()

    await actions.handle(update, _Context(args=[]))

    assert update.message.replies == []


@pytest.mark.asyncio
async def test_drafts_unauthorized_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_pending_drafts(self) -> list[_Draft]:
            raise AssertionError("service should not be called")

    async def _deny(_update: _Update, _context: _Context) -> bool:
        return True

    monkeypatch.setattr(drafts, "reject_if_unauthorized", _deny)
    monkeypatch.setattr(drafts, "_service", _Service())
    update = _Update()

    await drafts.handle(update, _Context(args=[]))

    assert update.message.replies == []


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
async def test_workflow_lists_needs_action_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_runs_needing_action(self) -> list[dict[str, object]]:
            return [
                {
                    "id": 9,
                    "status": "blocked",
                    "current_step": "await_schedule_approval",
                    "paused_state": "awaiting_approval",
                    "last_event_summary": "Awaiting approval for schedule proposal.",
                    "needs_action": True,
                    "available_actions": [
                        {"action": "approve"},
                        {"action": "reject"},
                        {"action": "request_revision"},
                    ],
                    "approval_checkpoint": {
                        "checkpoint_id": 3,
                        "target_artifact_id": 17,
                        "proposal_summary": "Hold deep work blocks and review windows this week.",
                        "pause_reason": "Awaiting operator approval before downstream changes.",
                        "allowed_actions": ["approve", "reject", "request_revision"],
                    },
                }
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", _Service())
    update = _Update()

    await workflows.needs_action(update, _Context(args=[]))

    assert update.message.replies == [
        "Run 9 [blocked] step=await_schedule_approval paused=awaiting_approval\n"
        "Last: Awaiting approval for schedule proposal.\n"
        "Needs action: yes | Next: approve, reject, request_revision\n"
        "Proposal: Hold deep work blocks and review windows this week.\n"
        "Actions: approve continues, reject closes, request_revision regenerates."
    ]


@pytest.mark.asyncio
async def test_workflow_retry_usage_message_when_reason_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    update = _Update()

    await workflows.retry(update, _Context(args=["5"]))

    assert update.message.replies == ["Usage: /workflow_retry <run_id> <reason>"]


@pytest.mark.asyncio
async def test_workflow_terminate_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen: tuple[int, str] | None = None

        def terminate_run(self, run_id: int, *, reason: str) -> dict[str, object]:
            self.seen = (run_id, reason)
            return {
                "id": run_id,
                "status": "terminated",
                "current_step": "normalize_request",
                "paused_state": None,
                "last_event_summary": reason,
                "needs_action": False,
                "available_actions": [],
            }

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", service)
    update = _Update()

    await workflows.terminate(update, _Context(args=["12", "Operator", "terminated", "run"]))

    assert service.seen == (12, "Operator terminated run")
    assert update.message.replies == [
        "Run 12 [terminated] step=normalize_request paused=active\n"
        "Last: Operator terminated run\n"
        "Needs action: no | Next: none"
    ]
