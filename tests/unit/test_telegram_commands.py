import pytest
from helm_telegram_bot.commands import (
    action_threads,
    actions,
    approve,
    common,
    digest,
    done_task,
    drafts,
    followup,
    needsreview_threads,
    proposals,
    remind,
    resolve,
    review,
    reviews,
    snooze,
    tasks,
    thread,
    threads,
    threads_label,
    urgent_threads,
)
from helm_telegram_bot.services.command_service import (
    DraftTransitionResult,
    ProposalView,
    ScheduledTaskView,
    ThreadDetailView,
    ThreadOverrideTransitionResult,
    ThreadQueueView,
    ThreadTaskTransitionResult,
)


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


def test_parse_two_arg_task_inputs() -> None:
    assert common.parse_two_arg_task_inputs(["42", "2026-01-03T09:00:00Z"]) == (
        42,
        "2026-01-03T09:00:00Z",
    )
    assert common.parse_two_arg_task_inputs(["42"]) is None
    assert common.parse_two_arg_task_inputs(["x", "2026-01-03T09:00:00Z"]) is None


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

    assert update.message.replies == ["Usage: /approve <id>"]


@pytest.mark.asyncio
async def test_approve_parses_id_and_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_id: int | None = None

        def approve_draft(self, draft_id: int) -> DraftTransitionResult:
            self.seen_id = draft_id
            return DraftTransitionResult(ok=True, message="Approved draft 7. Not sent yet.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(approve, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(approve, "_service", service)
    update = _Update()

    await approve.handle(update, _Context(args=["7"]))

    assert service.seen_id == 7
    assert update.message.replies == ["Approved draft 7. Not sent yet."]


@pytest.mark.asyncio
async def test_approve_unauthorized_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def approve_draft(self, draft_id: int) -> DraftTransitionResult:
            raise AssertionError(f"service should not be called: {draft_id}")

    async def _deny(_update: _Update, _context: _Context) -> bool:
        return True

    monkeypatch.setattr(approve, "reject_if_unauthorized", _deny)
    monkeypatch.setattr(approve, "_service", _Service())
    update = _Update()

    await approve.handle(update, _Context(args=["9"]))

    assert update.message.replies == []


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
async def test_action_threads_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_action_threads(self) -> list[ThreadQueueView]:
            return [
                ThreadQueueView(
                    id=14,
                    business_state="waiting_on_user",
                    current_summary="Reply to recruiter",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(action_threads, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(action_threads, "_service", _Service())
    update = _Update()

    await action_threads.handle(update, _Context(args=[]))

    assert update.message.replies == ["Action threads:\n14: Reply to recruiter"]


@pytest.mark.asyncio
async def test_needsreview_threads_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_needs_review_threads(self) -> list[ThreadQueueView]:
            return [
                ThreadQueueView(
                    id=22,
                    business_state="needs_review",
                    current_summary="Review recruiter note",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(needsreview_threads, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(needsreview_threads, "_service", _Service())
    update = _Update()

    await needsreview_threads.handle(update, _Context(args=[]))

    assert update.message.replies == ["NeedsReview threads:\n22: Review recruiter note"]


@pytest.mark.asyncio
async def test_urgent_threads_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_urgent_threads(self) -> list[ThreadQueueView]:
            return [
                ThreadQueueView(
                    id=18,
                    business_state="waiting_on_user",
                    current_summary="Urgent response needed",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(urgent_threads, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(urgent_threads, "_service", _Service())
    update = _Update()

    await urgent_threads.handle(update, _Context(args=[]))

    assert update.message.replies == ["Urgent threads:\n18: Urgent response needed"]


@pytest.mark.asyncio
async def test_drafts_command_replies_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_pending_drafts(self, approval_status=None) -> list[_Draft]:
            return []

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(drafts, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(drafts, "_service", _Service())
    update = _Update()

    await drafts.handle(update, _Context(args=[]))

    assert update.message.replies == ["No pending drafts."]


@pytest.mark.asyncio
async def test_drafts_command_rejects_invalid_status(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(drafts, "reject_if_unauthorized", _allow)
    update = _Update()

    await drafts.handle(update, _Context(args=["bad"]))

    assert update.message.replies == ["Usage: /drafts [pending_user|snoozed|approved]"]


@pytest.mark.asyncio
async def test_drafts_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_pending_drafts(self, approval_status=None) -> list[_Draft]:
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
async def test_proposals_command_rejects_invalid_type(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(proposals, "reject_if_unauthorized", _allow)
    update = _Update()

    await proposals.handle(update, _Context(args=["bad"]))

    assert update.message.replies == ["Usage: /proposals [reply|review]"]


@pytest.mark.asyncio
async def test_proposals_command_formats_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_proposals(self, proposal_type=None) -> list[ProposalView]:
            assert proposal_type == "reply"
            return [
                ProposalView(
                    id=8,
                    email_thread_id=3,
                    proposal_type="reply",
                    status="proposed",
                    rationale="Reply with availability",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(proposals, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(proposals, "_service", _Service())
    update = _Update()

    await proposals.handle(update, _Context(args=["reply"]))

    assert update.message.replies == ["Proposals (reply):\n8: thread 3 Reply with availability"]


@pytest.mark.asyncio
async def test_tasks_command_rejects_invalid_status(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(tasks, "reject_if_unauthorized", _allow)
    update = _Update()

    await tasks.handle(update, _Context(args=["bad"]))

    assert update.message.replies == ["Usage: /tasks [pending|completed]"]


@pytest.mark.asyncio
async def test_tasks_command_formats_completed_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_scheduled_tasks(self, status="pending") -> list[ScheduledTaskView]:
            assert status == "completed"
            return [
                ScheduledTaskView(
                    id=10,
                    email_thread_id=4,
                    task_type="reminder",
                    due_at=common.parse_iso_datetime_arg("2026-01-03T09:00:00Z"),
                    status="completed",
                    reason="reminder_due",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(tasks, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(tasks, "_service", _Service())
    update = _Update()

    await tasks.handle(update, _Context(args=["completed"]))

    assert update.message.replies == [
        "Completed email tasks:\n10: thread 4 reminder due 2026-01-03T09:00:00Z"
    ]


@pytest.mark.asyncio
async def test_drafts_command_formats_filtered_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_pending_drafts(self, approval_status=None) -> list[_Draft]:
            assert approval_status == "approved"
            return [
                _Draft(draft_id=7, status="approved", draft_text="Ready to inspect"),
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(drafts, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(drafts, "_service", _Service())
    update = _Update()

    await drafts.handle(update, _Context(args=["approved"]))

    assert update.message.replies == ["Drafts (approved):\n7: approved Ready to inspect"]


@pytest.mark.asyncio
async def test_threads_command_rejects_invalid_state(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(threads, "reject_if_unauthorized", _allow)
    update = _Update()

    await threads.handle(update, _Context(args=["bad"]))

    assert update.message.replies == [
        (
            "Usage: /threads "
            "[uninitialized|waiting_on_user|waiting_on_other_party|needs_review|resolved]"
        )
    ]


@pytest.mark.asyncio
async def test_threads_command_formats_filtered_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_threads(self, business_state=None) -> list[ThreadDetailView]:
            assert business_state == "needs_review"
            return [
                ThreadDetailView(
                    id=9,
                    business_state="needs_review",
                    visible_labels=["NeedsReview"],
                    current_summary="Check recruiter note",
                    action_reason="user_requested_review",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(threads, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(threads, "_service", _Service())
    update = _Update()

    await threads.handle(update, _Context(args=["needs_review"]))

    assert update.message.replies == ["Threads (needs_review):\n9: Check recruiter note"]


@pytest.mark.asyncio
async def test_threads_label_command_rejects_missing_label(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(threads_label, "reject_if_unauthorized", _allow)
    update = _Update()

    await threads_label.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /threads_label <Action|Urgent|NeedsReview>"]


@pytest.mark.asyncio
async def test_threads_label_command_formats_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_threads(self, business_state=None, label=None) -> list[ThreadDetailView]:
            assert label == "Action"
            return [
                ThreadDetailView(
                    id=12,
                    business_state="waiting_on_user",
                    visible_labels=["Action"],
                    current_summary="Reply to recruiter",
                    action_reason="reply_needed",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(threads_label, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(threads_label, "_service", _Service())
    update = _Update()

    await threads_label.handle(update, _Context(args=["Action"]))

    assert update.message.replies == ["Threads (Action):\n12: Reply to recruiter"]


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
async def test_remind_usage_message_when_missing_args(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(remind, "reject_if_unauthorized", _allow)
    update = _Update()

    await remind.handle(update, _Context(args=["7"]))

    assert update.message.replies == ["Usage: /remind <thread_id> <ISO8601>"]


@pytest.mark.asyncio
async def test_followup_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.calls: list[tuple[int, str]] = []

        def create_thread_task(
            self,
            *,
            thread_id: int,
            due_at,
            task_type: str,
        ) -> ThreadTaskTransitionResult:
            self.calls.append((thread_id, task_type))
            return ThreadTaskTransitionResult(
                ok=True,
                message="Created followup task 9 for thread 3.",
            )

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(followup, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(followup, "_service", service)
    update = _Update()

    await followup.handle(update, _Context(args=["3", "2026-01-03T09:00:00Z"]))

    assert service.calls == [(3, "followup")]
    assert update.message.replies == ["Created followup task 9 for thread 3."]


@pytest.mark.asyncio
async def test_resolve_usage_message_when_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(resolve, "reject_if_unauthorized", _allow)
    update = _Update()

    await resolve.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /resolve <thread_id>"]


@pytest.mark.asyncio
async def test_review_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_id: int | None = None

        def mark_thread_needs_review(self, thread_id: int) -> ThreadOverrideTransitionResult:
            self.seen_id = thread_id
            return ThreadOverrideTransitionResult(
                ok=True,
                message="Marked thread 5 for review.",
            )

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(review, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(review, "_service", service)
    update = _Update()

    await review.handle(update, _Context(args=["5"]))

    assert service.seen_id == 5
    assert update.message.replies == ["Marked thread 5 for review."]


@pytest.mark.asyncio
async def test_thread_command_formats_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def get_thread_detail(self, thread_id: int) -> ThreadDetailView | None:
            return ThreadDetailView(
                id=thread_id,
                business_state="waiting_on_user",
                visible_labels=["Action", "Urgent"],
                current_summary="Reply to recruiter",
                action_reason="reply_needed",
            )

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(thread, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(thread, "_service", _Service())
    update = _Update()

    await thread.handle(update, _Context(args=["8"]))

    assert update.message.replies == [
        (
            "Thread 8\n"
            "State: waiting_on_user\n"
            "Labels: Action, Urgent\n"
            "Reason: reply_needed\n"
            "Summary: Reply to recruiter"
        )
    ]


@pytest.mark.asyncio
async def test_reviews_command_formats_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_review_threads(self) -> list[ThreadDetailView]:
            return [
                ThreadDetailView(
                    id=4,
                    business_state="needs_review",
                    visible_labels=["NeedsReview"],
                    current_summary="Check recruiter note",
                    action_reason="user_requested_review",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(reviews, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(reviews, "_service", _Service())
    update = _Update()

    await reviews.handle(update, _Context(args=[]))

    assert update.message.replies == ["Review threads:\n4: Check recruiter note"]


@pytest.mark.asyncio
async def test_tasks_command_formats_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_scheduled_tasks(self, status="pending") -> list[ScheduledTaskView]:
            assert status == "pending"
            return [
                ScheduledTaskView(
                    id=10,
                    email_thread_id=4,
                    task_type="reminder",
                    due_at=common.parse_iso_datetime_arg("2026-01-03T09:00:00Z"),
                    status="pending",
                    reason="reminder_due",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(tasks, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(tasks, "_service", _Service())
    update = _Update()

    await tasks.handle(update, _Context(args=[]))

    assert update.message.replies == [
        "Pending email tasks:\n10: thread 4 reminder due 2026-01-03T09:00:00Z"
    ]


@pytest.mark.asyncio
async def test_done_task_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_id: int | None = None

        def complete_task(self, task_id: int) -> ThreadTaskTransitionResult:
            self.seen_id = task_id
            return ThreadTaskTransitionResult(
                ok=True,
                message="Completed task 10 for thread 4.",
            )

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(done_task, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(done_task, "_service", service)
    update = _Update()

    await done_task.handle(update, _Context(args=["10"]))

    assert service.seen_id == 10
    assert update.message.replies == ["Completed task 10 for thread 4."]
