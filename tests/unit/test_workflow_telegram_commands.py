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


@pytest.mark.asyncio
async def test_workflow_completion_summary_surfaces_sync_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Telegram formats completion summary with sync counts for weekly scheduling."""
    class _Service:
        def list_recent_runs(self, *, limit: int = 5) -> list[dict[str, object]]:
            return [
                {
                    "id": 1,
                    "status": "completed",
                    "current_step": None,
                    "paused_state": None,
                    "last_event_summary": "Schedule applied and synced.",
                    "needs_action": False,
                    "available_actions": [],
                    "completion_summary": {
                        "headline": "Scheduled 3 block(s) and synced 6 approved write(s).",
                        "approval_decision": "approve",
                        "downstream_sync_status": "succeeded",
                        "total_sync_writes": 6,
                        "task_sync_writes": 3,
                        "calendar_sync_writes": 3,
                        "scheduled_highlights": ["Task 1", "Task 2", "Task 3"],
                        "carry_forward_tasks": ["Task 4"],
                    },
                }
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", _Service())
    update = _Update()

    await workflows.recent(update, _Context(args=[]))

    reply = update.message.replies[0]
    # Verify key completion summary fields are present
    assert "Outcome: Scheduled 3 block(s) and synced 6 approved write(s)." in reply
    assert "Sync: 6 writes (3 task, 3 calendar) status=succeeded" in reply
    assert "Scheduled: Task 1, Task 2, Task 3" in reply
    assert "Carry forward: Task 4" in reply


@pytest.mark.asyncio
async def test_workflow_completion_summary_absent_when_not_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Telegram does not show completion summary for active runs."""
    class _Service:
        def list_recent_runs(self, *, limit: int = 5) -> list[dict[str, object]]:
            return [
                {
                    "id": 2,
                    "status": "active",
                    "current_step": "dispatch_task_agent",
                    "paused_state": None,
                    "last_event_summary": "Run started.",
                    "needs_action": False,
                    "available_actions": [],
                }
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", _Service())
    update = _Update()

    await workflows.recent(update, _Context(args=[]))

    reply = update.message.replies[0]
    # Verify completion summary is not shown for active run
    assert "Outcome:" not in reply
    assert "Sync:" not in reply


@pytest.mark.asyncio
async def test_workflow_approval_checkpoint_shows_artifact_and_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Telegram shows approval checkpoint with artifact ID and proposal summary."""
    class _Service:
        def list_recent_runs(self, *, limit: int = 5) -> list[dict[str, object]]:
            return [
                {
                    "id": 3,
                    "status": "active",
                    "current_step": "await_schedule_approval",
                    "paused_state": "awaiting_approval",
                    "last_event_summary": "Schedule proposal generated, awaiting approval.",
                    "needs_action": True,
                    "available_actions": [
                        {"action": "approve"},
                        {"action": "reject"},
                        {"action": "request_revision"},
                    ],
                    "approval_checkpoint": {
                        "target_artifact_id": 5,
                        "target_version_number": 1,
                        "proposal_summary": "Schedule with 3 time blocks and constraints honored.",
                    },
                }
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", _Service())
    update = _Update()

    await workflows.recent(update, _Context(args=[]))

    reply = update.message.replies[0]
    # Verify approval checkpoint information is present
    assert "Latest proposal: v1 artifact=5" in reply
    assert "Proposal: Schedule with 3 time blocks and constraints honored." in reply
    assert "Actions: approve/reject/request_revision must name this artifact id." in reply
    assert "Needs action: yes" in reply


@pytest.mark.asyncio
async def test_workflow_safe_next_actions_on_completed_run_with_replay_option(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Telegram shows safe_next_actions (e.g., replay) on completed runs."""
    class _Service:
        def list_recent_runs(self, *, limit: int = 5) -> list[dict[str, object]]:
            return [
                {
                    "id": 4,
                    "status": "completed",
                    "current_step": None,
                    "paused_state": None,
                    "last_event_summary": "Workflow completed successfully.",
                    "needs_action": False,
                    "available_actions": [],
                    "safe_next_actions": [
                        {"action": "request_replay", "label": "Request replay"}
                    ],
                    "completion_summary": {
                        "headline": "Scheduled 2 block(s) and synced 4 approved write(s).",
                        "approval_decision": "approve",
                        "downstream_sync_status": "succeeded",
                        "total_sync_writes": 4,
                        "task_sync_writes": 2,
                        "calendar_sync_writes": 2,
                        "scheduled_highlights": ["Review meeting", "Planning session"],
                        "carry_forward_tasks": [],
                    },
                }
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", _Service())
    update = _Update()

    await workflows.recent(update, _Context(args=[]))

    reply = update.message.replies[0]
    # Verify safe_next_actions are shown as "Next:" options
    assert "Needs action: no" in reply
    assert "Next: request_replay" in reply
    assert "Outcome: Scheduled 2 block(s) and synced 4 approved write(s)." in reply


@pytest.mark.asyncio
async def test_workflow_lists_needs_action_shows_approval_checkpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify /workflow_needs_action lists runs with approval checkpoints."""
    class _Service:
        def list_runs_needing_action(self, *, limit: int = 5) -> list[dict[str, object]]:
            return [
                {
                    "id": 6,
                    "status": "active",
                    "current_step": "await_schedule_approval",
                    "paused_state": "awaiting_approval",
                    "last_event_summary": "Awaiting approval decision.",
                    "needs_action": True,
                    "available_actions": [{"action": "approve"}, {"action": "reject"}],
                    "approval_checkpoint": {
                        "target_artifact_id": 8,
                        "target_version_number": 1,
                        "proposal_summary": "Weekly schedule prepared.",
                    },
                }
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(workflows, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(workflows, "_service", _Service())
    update = _Update()

    await workflows.needs_action(update, _Context(args=[]))

    reply = update.message.replies[0]
    assert "Run 6 [active]" in reply
    assert "Needs action: yes" in reply
    assert "Latest proposal: v1 artifact=8" in reply
    assert "Proposal: Weekly schedule prepared." in reply


@pytest.mark.asyncio
async def test_workflow_reject_parses_ids_and_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify /reject command parses run and artifact IDs and surfaces the result."""
    class _Service:
        def __init__(self) -> None:
            self.seen: tuple[int, int] | None = None

        def reject_run(self, run_id: int, *, actor: str, target_artifact_id: int) -> dict[str, object]:
            self.seen = (run_id, target_artifact_id)
            assert actor == "telegram:1"
            return {
                "id": run_id,
                "status": "active",
                "current_step": "dispatch_calendar_agent",
                "paused_state": None,
                "last_event_summary": "Proposal rejected, restarting generation.",
                "needs_action": False,
                "available_actions": [],
            }

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_workflow_service", service)
    update = _Update()

    await approve.reject(update, _Context(args=["9", "12"]))

    assert service.seen == (9, 12)
    assert "Run 9 [active]" in update.message.replies[0]
    assert "Last: Proposal rejected, restarting generation." in update.message.replies[0]


@pytest.mark.asyncio
async def test_workflow_request_revision_parses_ids_feedback_and_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify /request_revision command parses run ID, artifact ID, and feedback."""
    class _Service:
        def __init__(self) -> None:
            self.seen: tuple[int, int, str] | None = None

        def request_revision(
            self, run_id: int, *, actor: str, target_artifact_id: int, feedback: str
        ) -> dict[str, object]:
            self.seen = (run_id, target_artifact_id, feedback)
            assert actor == "telegram:1"
            return {
                "id": run_id,
                "status": "active",
                "current_step": "dispatch_calendar_agent",
                "paused_state": None,
                "last_event_summary": "Revision requested, regenerating proposal.",
                "needs_action": False,
                "available_actions": [],
            }

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_workflow_service", service)
    update = _Update()

    await approve.request_revision(
        update, _Context(args=["10", "13", "Please", "increase", "constraints", "priority"])
    )

    assert service.seen == (10, 13, "Please increase constraints priority")
    assert "Run 10 [active]" in update.message.replies[0]
    assert "Last: Revision requested, regenerating proposal." in update.message.replies[0]
