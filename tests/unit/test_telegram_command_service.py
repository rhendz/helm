from __future__ import annotations

from datetime import UTC, datetime

from email_agent.operator import ActionView, DraftTransitionResult, DraftView
from helm_telegram_bot.services import command_service


def test_list_open_actions_applies_limit(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())

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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_action_threads(limit=2)

    assert len(threads) == 1
    assert threads[0].id == 11


def test_list_replay_queue_applies_status_filter(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_replay_queue": lambda self, *, status, limit: [
                {
                    "id": 41,
                    "agent_run_id": 12,
                    "agent_name": "email_triage",
                    "agent_run_error_message": "history cursor invalid",
                    "source_type": "email_message",
                    "source_id": "msg-41",
                    "status": status or "dead_lettered",
                    "attempts": 3,
                    "last_error": "history cursor invalid",
                }
            ][:limit]
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    items = service.list_replay_queue(limit=2, status="dead_lettered")

    assert len(items) == 1
    assert items[0].id == 41
    assert items[0].status == "dead_lettered"
    assert items[0].agent_name == "email_triage"


def test_list_uninitialized_threads_uses_state_filter(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": lambda self, *, business_state, limit: [
                {
                    "id": 13,
                    "business_state": business_state,
                    "current_summary": "New thread without classification",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_uninitialized_threads(limit=2)

    assert len(threads) == 1
    assert threads[0].id == 13
    assert threads[0].business_state == "uninitialized"


def test_list_waiting_on_user_threads_uses_state_filter(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": lambda self, *, business_state, limit: [
                {
                    "id": 17,
                    "business_state": business_state,
                    "current_summary": "Reply to founder",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_waiting_on_user_threads(limit=2)

    assert len(threads) == 1
    assert threads[0].id == 17
    assert threads[0].business_state == "waiting_on_user"


def test_list_waiting_on_other_party_threads_uses_state_filter(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": lambda self, *, business_state, limit: [
                {
                    "id": 18,
                    "business_state": business_state,
                    "current_summary": "Waiting for recruiter response",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_waiting_on_other_party_threads(limit=2)

    assert len(threads) == 1
    assert threads[0].id == 18
    assert threads[0].business_state == "waiting_on_other_party"


def test_list_resolved_threads_uses_state_filter(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": lambda self, *, business_state, limit: [
                {
                    "id": 19,
                    "business_state": business_state,
                    "current_summary": "Closed recruiter thread",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_resolved_threads(limit=2)

    assert len(threads) == 1
    assert threads[0].id == 19
    assert threads[0].business_state == "resolved"


def test_list_needs_review_threads_uses_label(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_email_threads": lambda self, *, label, limit: [
                {
                    "id": 21,
                    "business_state": "needs_review",
                    "current_summary": "Manual review needed",
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_needs_review_threads(limit=2)

    assert len(threads) == 1
    assert threads[0].id == 21


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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    threads = service.list_threads(limit=2, label="Urgent")

    assert len(threads) == 1
    assert threads[0].visible_labels == ["Urgent"]


def test_list_pending_drafts_applies_limit(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())

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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    drafts = service.list_pending_drafts(limit=2, approval_status="approved")

    assert len(drafts) == 1
    assert drafts[0].status == "approved"


def test_get_draft_detail_happy_path(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "get_email_draft_by_id": lambda self, draft_id: {
                "id": draft_id,
                "email_thread_id": 7,
                "action_proposal_id": 11,
                "status": "generated",
                "approval_status": "approved",
                "draft_body": "Thanks for reaching out.",
                "draft_subject": "Re: Opportunity",
            },
            "list_draft_transition_audits_for_draft": lambda self, *, draft_id: [
                {
                    "action": "approve",
                    "from_status": "pending_user",
                    "to_status": "approved",
                    "success": True,
                }
            ],
            "list_send_attempts_for_draft": lambda self, *, draft_id: [
                {
                    "attempt_number": 1,
                    "status": "failed",
                    "failure_class": "timeout",
                }
            ],
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    draft = service.get_draft_detail(5)

    assert draft is not None
    assert draft.id == 5
    assert draft.email_thread_id == 7
    assert draft.transition_audits[0]["action"] == "approve"
    assert draft.send_attempts[0]["failure_class"] == "timeout"


def test_approve_draft_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())

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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())

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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())

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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())

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


def test_send_draft_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())
    monkeypatch.setattr(
        command_service,
        "send_approved_draft",
        lambda *, draft_id, runtime: type(
            "Result",
            (),
            {
                "status": "accepted",
                "reason": None,
                "warning": None,
                "attempt_id": 3,
            },
        )(),
    )

    service = command_service.TelegramCommandService()
    result = service.send_draft(12)

    assert result.ok is True
    assert result.message == "Sent draft 12."


def test_send_draft_requires_approval(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())
    monkeypatch.setattr(
        command_service,
        "send_approved_draft",
        lambda *, draft_id, runtime: type(
            "Result",
            (),
            {
                "status": "rejected",
                "reason": "approval_required",
                "warning": None,
                "attempt_id": None,
            },
        )(),
    )

    service = command_service.TelegramCommandService()
    result = service.send_draft(9)

    assert result.ok is False
    assert result.message == "Draft 9 is not approved; approve it before sending."


def test_requeue_replay_item_happy_path(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_replay_queue": lambda self, *, status=None, limit=20: [
                {
                    "id": 22,
                    "agent_run_id": 91,
                    "agent_name": "email_triage",
                    "agent_run_error_message": "cursor invalid",
                    "source_type": "email_message",
                    "source_id": "msg-22",
                    "status": "dead_lettered",
                    "attempts": 3,
                    "last_error": "boom",
                }
            ],
            "requeue_replay_item": lambda self, item_id: type(
                "ReplayQueueRecord",
                (),
                {"id": item_id},
            )(),
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    result = service.requeue_replay_item(22)

    assert result.ok is True
    assert result.message == "Requeued replay item 22."


def test_requeue_replay_item_rejects_non_terminal_status(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "list_replay_queue": lambda self, *, status=None, limit=20: [
                {
                    "id": 23,
                    "agent_run_id": 92,
                    "agent_name": "email_triage",
                    "agent_run_error_message": "cursor invalid",
                    "source_type": "email_message",
                    "source_id": "msg-23",
                    "status": "pending",
                    "attempts": 1,
                    "last_error": None,
                }
            ]
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    result = service.requeue_replay_item(23)

    assert result.ok is False
    assert (
        result.message
        == "Replay item 23 is pending; only failed or dead-lettered items can be requeued."
    )


def test_run_replay_worker_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "is_job_paused", lambda name: False)
    monkeypatch.setattr(command_service.replay_job, "run", lambda *, limit: 3)

    service = command_service.TelegramCommandService()
    result = service.run_replay_worker(limit=5)

    assert result.ok is True
    assert result.message == "Triggered replay worker for up to 5 items; processed 3."


def test_run_replay_worker_rejects_invalid_limit() -> None:
    service = command_service.TelegramCommandService()

    result = service.run_replay_worker(limit=0)

    assert result.ok is False
    assert result.message == "Replay limit must be a positive integer."


def test_run_replay_worker_rejects_paused_job(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "is_job_paused", lambda name: name == "replay")

    service = command_service.TelegramCommandService()
    result = service.run_replay_worker(limit=5)

    assert result.ok is False
    assert (
        result.message
        == "Replay job is paused; resume it before running replay manually."
    )


def test_pause_replay_job_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        command_service,
        "set_job_pause",
        lambda *, job_name, paused: {"job_name": job_name, "paused": paused},
    )

    service = command_service.TelegramCommandService()
    result = service.pause_replay_job()

    assert result.ok is True
    assert result.message == "Replay job paused."


def test_get_replay_job_status_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        command_service,
        "list_job_controls",
        lambda: [{"job_name": "replay", "paused": True}],
    )

    service = command_service.TelegramCommandService()
    result = service.get_replay_job_status()

    assert result.ok is True
    assert result.message == "Replay job status: paused."


def test_resume_replay_job_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(
        command_service,
        "set_job_pause",
        lambda *, job_name, paused: {"job_name": job_name, "paused": paused},
    )

    service = command_service.TelegramCommandService()
    result = service.resume_replay_job()

    assert result.ok is True
    assert result.message == "Replay job resumed."


def test_create_thread_task_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())
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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

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
                    "latest_confidence_band": "high",
                    "action_reason": "reply_needed",
                },
                "proposals": [{"proposal_type": "reply", "status": "proposed"}],
                "drafts": [{"approval_status": "pending_user", "preview": "Draft reply preview"}],
                "messages": [
                    {
                        "from_address": "founder@example.com",
                        "subject": "Checking in",
                        "snippet": "Wanted to follow up.",
                    }
                ],
            },
            "list_scheduled_tasks_for_thread": lambda self, *, thread_id: [
                {"status": "pending"},
                {"status": "completed"},
            ],
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    result = service.get_thread_detail(5)

    assert result is not None
    assert result.id == 5
    assert result.visible_labels == ["Action"]
    assert result.latest_confidence_band == "high"
    assert result.latest_proposal_type == "reply"
    assert result.latest_draft_approval_status == "pending_user"
    assert result.latest_message_from == "founder@example.com"
    assert result.pending_task_count == 1


def test_reprocess_thread_passes_dry_run(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())
    monkeypatch.setattr(
        command_service,
        "reprocess_email_thread",
        lambda *, thread_id, dry_run, runtime: type(
            "Result",
            (),
            {
                "status": "accepted",
                "workflow_status": "completed",
                "reason": None,
            },
        )(),
    )

    service = command_service.TelegramCommandService()
    result = service.reprocess_thread(7, dry_run=True)

    assert result.ok is True
    assert result.message == "Reprocess dry-run for thread 7: completed."


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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

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
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    results = service.list_scheduled_tasks(limit=1, status="pending")

    assert len(results) == 1
    assert results[0].id == 11
    assert results[0].status == "pending"


def test_get_email_config_returns_runtime_config(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "get_email_agent_config": lambda self: type(
                "Config",
                (),
                {
                    "approval_required_before_send": True,
                    "default_follow_up_business_days": 4,
                    "timezone_name": "America/Los_Angeles",
                },
            )(),
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    config = service.get_email_config()

    assert config.approval_required_before_send is True
    assert config.default_follow_up_business_days == 4
    assert config.timezone_name == "America/Los_Angeles"


def test_update_email_timezone_validates_and_persists(monkeypatch) -> None:  # noqa: ANN001
    runtime = type(
        "Runtime",
        (),
        {
            "update_email_agent_config": lambda self, **kwargs: type(
                "Config",
                (),
                {
                    "timezone_name": kwargs["timezone_name"],
                    "default_follow_up_business_days": 3,
                    "approval_required_before_send": True,
                },
            )(),
        },
    )()
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: runtime)

    service = command_service.TelegramCommandService()
    result = service.update_email_timezone("America/New_York")

    assert result.ok is True
    assert result.message == "Email timezone set to America/New_York."


def test_update_email_timezone_rejects_invalid_value() -> None:
    service = command_service.TelegramCommandService()

    result = service.update_email_timezone("Mars/Phobos")

    assert result.ok is False
    assert result.message == "Invalid timezone: Mars/Phobos."


def test_update_followup_days_rejects_negative_values() -> None:
    service = command_service.TelegramCommandService()

    result = service.update_followup_days(-1)

    assert result.ok is False
    assert result.message == "Follow-up days must be a non-negative integer."


def test_complete_task_happy_path(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(command_service, "build_email_agent_runtime", lambda: object())
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
