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
