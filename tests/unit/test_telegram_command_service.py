from __future__ import annotations

from datetime import UTC, datetime

from email_agent.operator import ActionView, DraftTransitionResult, DraftView
from helm_telegram_bot.services import command_service


def test_list_open_actions_applies_limit(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: object())

    def fake_list_open_actions(*, limit: int = 5, runtime: object) -> list[ActionView]:
        return [
            ActionView(id=i, priority=2, title=f"action-{i}")
            for i in range(1, limit + 1)
        ]

    monkeypatch.setattr(
        command_service,
        "list_open_actions",
        fake_list_open_actions,
    )

    service = command_service.TelegramCommandService()
    actions = service.list_open_actions(limit=3)

    assert [a.id for a in actions] == [1, 2, 3]


def test_list_action_threads_uses_action_label(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": lambda self, *, label, limit: [
                {
                    "id": 11,
                    "business_state": "waiting_on_user",
                    "current_summary": "Reply to recruiter",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_action_threads(limit=2)

    assert len(threads) == 1
    assert threads[0].id == 11


def test_list_proposals_filters_by_type(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_proposals": lambda self, *, status, proposal_type, limit: [
                {
                    "id": 6,
                    "email_thread_id": 4,
                    "proposal_type": proposal_type,
                    "status": status,
                    "rationale": "Reply with availability",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    proposals = service.list_proposals(limit=2, proposal_type="reply")

    assert len(proposals) == 1
    assert proposals[0].proposal_type == "reply"


def test_list_threads_filters_by_business_state(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": lambda self, *, business_state, label, limit: [
                {
                    "id": 3,
                    "business_state": business_state,
                    "visible_labels": ["Action"],
                    "current_summary": "Reply to recruiter",
                    "action_reason": "reply_needed",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_threads(limit=2, business_state="waiting_on_user")

    assert len(threads) == 1
    assert threads[0].business_state == "waiting_on_user"


def test_list_threads_filters_by_label(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": lambda self, *, business_state, label, limit: [
                {
                    "id": 8,
                    "business_state": "waiting_on_user",
                    "visible_labels": [label],
                    "current_summary": "Urgent recruiter reply",
                    "action_reason": "reply_needed",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_threads(limit=2, label="Urgent")

    assert len(threads) == 1
    assert threads[0].visible_labels == ["Urgent"]


def test_list_pending_drafts_applies_limit(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: object())

    def fake_list_pending_drafts(*, limit: int = 5, runtime: object) -> list[DraftView]:
        return [
            DraftView(id=i, status="pending_user", draft_text=f"draft-{i}")
            for i in range(1, limit + 1)
        ]

    monkeypatch.setattr(
        command_service,
        "list_pending_drafts",
        fake_list_pending_drafts,
    )

    service = command_service.TelegramCommandService()
    drafts = service.list_pending_drafts(limit=4)

    assert [d.id for d in drafts] == [1, 2, 3, 4]


def test_list_pending_drafts_filters_by_approval_status(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_drafts": lambda self, *, limit, approval_status: [
                {
                    "id": 4,
                    "approval_status": approval_status,
                    "preview": "Approved draft",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    drafts = service.list_pending_drafts(limit=2, approval_status="approved")

    assert len(drafts) == 1
    assert drafts[0].status == "approved"


def test_approve_draft_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: object())

    monkeypatch.setattr(
        command_service,
        "approve_draft",
        lambda draft_id, runtime: DraftTransitionResult(
            ok=True,
            message=f"Approved draft {draft_id}. Not sent yet.",
        ),
    )

    service = command_service.TelegramCommandService()
    result = service.approve_draft(1)

    assert result.ok is True
    assert result.message == "Approved draft 1. Not sent yet."


def test_approve_draft_failure_passthrough(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: object())

    def fake_approve_draft(draft_id: int, runtime: object) -> DraftTransitionResult:
        return DraftTransitionResult(
            ok=False,
            message=f"Draft {draft_id} not found.",
        )

    monkeypatch.setattr(
        command_service,
        "approve_draft",
        fake_approve_draft,
    )

    service = command_service.TelegramCommandService()
    result = service.approve_draft(99)

    assert result.ok is False
    assert result.message == "Draft 99 not found."


def test_snooze_draft_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: object())

    monkeypatch.setattr(
        command_service,
        "snooze_draft",
        lambda draft_id, runtime: DraftTransitionResult(
            ok=True,
            message=f"Snoozed draft {draft_id} for later review.",
        ),
    )

    service = command_service.TelegramCommandService()
    result = service.snooze_draft(1)

    assert result.ok is True
    assert result.message == "Snoozed draft 1 for later review."


def test_snooze_draft_failure_passthrough(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: object())

    monkeypatch.setattr(
        command_service,
        "snooze_draft",
        lambda draft_id, runtime: DraftTransitionResult(
            ok=False,
            message=f"Draft {draft_id} is approved; cannot snooze.",
        ),
    )

    service = command_service.TelegramCommandService()
    result = service.snooze_draft(3)

    assert result.ok is False
    assert result.message == "Draft 3 is approved; cannot snooze."


def test_create_thread_task_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: object())
    monkeypatch.setattr(
        command_service,
        "create_thread_reminder",
        lambda **kwargs: type(
            "Result",
            (),
            {"status": "accepted", "task_id": 12, "reason": None},
        )(),
    )

    service = command_service.TelegramCommandService()
    result = service.create_thread_task(
        thread_id=7,
        due_at=datetime(2026, 1, 3, 9, 0, tzinfo=UTC),
        task_type="reminder",
    )

    assert result.ok is True
    assert result.message == "Created reminder task 12 for thread 7."


def test_resolve_thread_happy_path(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "get_thread_by_id": lambda self, thread_id: type(
                "Thread",
                (),
                {
                    "id": thread_id,
                    "visible_labels": "Action",
                    "latest_confidence_band": "High",
                    "current_summary": "Need reply",
                    "last_message_id": None,
                    "last_inbound_message_id": None,
                    "last_outbound_message_id": None,
                },
            )(),
            "update_thread_state": lambda self, *args, **kwargs: object(),
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    result = service.resolve_thread(7)

    assert result.ok is True
    assert result.message == "Marked thread 7 resolved."


def test_get_thread_detail_happy_path(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "get_email_thread_detail": lambda self, *, thread_id: {
                "thread": {
                    "id": thread_id,
                    "business_state": "waiting_on_user",
                    "visible_labels": ["Action"],
                    "current_summary": "Reply to recruiter",
                    "action_reason": "reply_needed",
                }
            }
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    result = service.get_thread_detail(5)

    assert result is not None
    assert result.id == 5
    assert result.visible_labels == ["Action"]


def test_list_review_threads_filters_results(monkeypatch) -> None:  # noqa: ANN001
    def _list_email_threads(self, *, business_state, limit, label=None):  # noqa: ANN001
        items = [
            {
                "id": 1,
                "business_state": "needs_review",
                "visible_labels": ["NeedsReview"],
                "current_summary": "Review recruiter thread",
                "action_reason": "user_requested_review",
            },
            {
                "id": 2,
                "business_state": "waiting_on_user",
                "visible_labels": ["Action"],
                "current_summary": "Reply later",
                "action_reason": "reply_needed",
            },
        ]
        return [item for item in items if item["business_state"] == business_state][:limit]

    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": _list_email_threads,
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    results = service.list_review_threads()

    assert [item.id for item in results] == [1]


def test_list_scheduled_tasks_applies_status_and_limit(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_scheduled_tasks": lambda self, *, status, limit: [
                {
                    "id": 11,
                    "email_thread_id": 7,
                    "task_type": "followup",
                    "due_at": datetime(2026, 1, 3, 9, 0, tzinfo=UTC),
                    "status": status,
                    "reason": "followup_due",
                }
            ][:limit]
        },
    )()
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    results = service.list_scheduled_tasks(limit=1, status="pending")

    assert len(results) == 1
    assert results[0].id == 11
    assert results[0].status == "pending"


def test_complete_task_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_helm_runtime", lambda: object())
    monkeypatch.setattr(
        command_service,
        "complete_scheduled_task",
        lambda **kwargs: type(
            "Result",
            (),
            {"status": "accepted", "thread_id": 7, "task_id": 12, "reason": None},
        )(),
    )

    service = command_service.TelegramCommandService()
    result = service.complete_task(12)

    assert result.ok is True
    assert result.message == "Completed task 12 for thread 7."
