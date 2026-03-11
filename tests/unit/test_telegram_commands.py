import pytest
from helm_telegram_bot.commands import (
    action_threads,
    actions,
    approve,
    common,
    digest,
    done_task,
    draft,
    drafts,
    email_config,
    followup,
    job,
    job_controls,
    needsreview_threads,
    pause_job,
    pause_replay,
    proposals,
    remind,
    replay_status,
    replays,
    reprocess_thread,
    requeue_replay,
    resolve,
    resolved_threads,
    resume_job,
    resume_replay,
    review,
    reviews,
    run_job,
    run_replay,
    send,
    set_email_timezone,
    set_followup_days,
    snooze,
    start,
    tasks,
    thread,
    threads,
    threads_label,
    uninitialized_threads,
    urgent_threads,
    waiting_on_other_party_threads,
    waiting_on_user_threads,
)
from helm_telegram_bot.services.command_service import (
    DraftTransitionResult,
    JobControlView,
    ProposalView,
    ReplayQueueView,
    ScheduledTaskView,
    ThreadDetailView,
    ThreadOverrideTransitionResult,
    ThreadQueueView,
    ThreadReprocessResult,
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
async def test_start_command_shows_job_control_shortcuts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(start, "reject_if_unauthorized", _allow)
    update = _Update()

    await start.handle(update, _Context(args=[]))

    assert update.message.replies == [
        "Helm bot is online.\n"
        "Job controls: /jobs, /jobs paused, /jobs active, /job <job_name>"
    ]


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
async def test_uninitialized_threads_command_formats_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Service:
        def list_uninitialized_threads(self) -> list[ThreadQueueView]:
            return [
                ThreadQueueView(
                    id=21,
                    business_state="uninitialized",
                    current_summary="New thread without classification",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(uninitialized_threads, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(uninitialized_threads, "_service", _Service())
    update = _Update()

    await uninitialized_threads.handle(update, _Context(args=[]))

    assert update.message.replies == [
        "Uninitialized threads:\n21: New thread without classification"
    ]


@pytest.mark.asyncio
async def test_waiting_on_user_threads_command_formats_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Service:
        def list_waiting_on_user_threads(self) -> list[ThreadQueueView]:
            return [
                ThreadQueueView(
                    id=23,
                    business_state="waiting_on_user",
                    current_summary="Reply to founder",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(waiting_on_user_threads, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(waiting_on_user_threads, "_service", _Service())
    update = _Update()

    await waiting_on_user_threads.handle(update, _Context(args=[]))

    assert update.message.replies == ["Waiting-on-user threads:\n23: Reply to founder"]


@pytest.mark.asyncio
async def test_waiting_on_other_party_threads_command_formats_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Service:
        def list_waiting_on_other_party_threads(self) -> list[ThreadQueueView]:
            return [
                ThreadQueueView(
                    id=24,
                    business_state="waiting_on_other_party",
                    current_summary="Waiting for recruiter response",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(waiting_on_other_party_threads, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(waiting_on_other_party_threads, "_service", _Service())
    update = _Update()

    await waiting_on_other_party_threads.handle(update, _Context(args=[]))

    assert update.message.replies == [
        "Waiting-on-other-party threads:\n24: Waiting for recruiter response"
    ]


@pytest.mark.asyncio
async def test_resolved_threads_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_resolved_threads(self) -> list[ThreadQueueView]:
            return [
                ThreadQueueView(
                    id=25,
                    business_state="resolved",
                    current_summary="Closed recruiter thread",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(resolved_threads, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(resolved_threads, "_service", _Service())
    update = _Update()

    await resolved_threads.handle(update, _Context(args=[]))

    assert update.message.replies == ["Resolved threads:\n25: Closed recruiter thread"]


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
async def test_replays_command_rejects_invalid_status(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(replays, "reject_if_unauthorized", _allow)
    update = _Update()

    await replays.handle(update, _Context(args=["bad"]))

    assert update.message.replies == [
        "Usage: /replays [pending|processing|completed|failed|dead_lettered]"
    ]


@pytest.mark.asyncio
async def test_replays_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_replay_queue(self, status=None) -> list[ReplayQueueView]:
            assert status == "dead_lettered"
            return [
                ReplayQueueView(
                    id=31,
                    agent_run_id=44,
                    agent_name="email_triage",
                    agent_run_error_message="history id 123 was stale",
                    source_type="email_message",
                    source_id="msg-31",
                    status="dead_lettered",
                    attempts=3,
                    last_error="cursor invalid",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(replays, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(replays, "_service", _Service())
    update = _Update()

    await replays.handle(update, _Context(args=["dead_lettered"]))

    assert update.message.replies == [
        "Replay items (dead_lettered):\n"
        "31: dead_lettered attempts=3 email_message/msg-31 "
        "run=email_triage#44 last_error=cursor invalid "
        "origin_error=history id 123 was stale"
    ]


@pytest.mark.asyncio
async def test_requeue_replay_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_id: int | None = None

        def requeue_replay_item(self, replay_id: int) -> ThreadTaskTransitionResult:
            self.seen_id = replay_id
            return ThreadTaskTransitionResult(ok=True, message="Requeued replay item 31.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(requeue_replay, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(requeue_replay, "_service", service)
    update = _Update()

    await requeue_replay.handle(update, _Context(args=["31"]))

    assert service.seen_id == 31
    assert update.message.replies == ["Requeued replay item 31."]


@pytest.mark.asyncio
async def test_run_replay_command_rejects_invalid_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(run_replay, "reject_if_unauthorized", _allow)
    update = _Update()

    await run_replay.handle(update, _Context(args=["bad"]))

    assert update.message.replies == ["Usage: /run_replay [limit]"]


@pytest.mark.asyncio
async def test_run_job_command_rejects_invalid_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(run_job, "reject_if_unauthorized", _allow)
    update = _Update()

    await run_job.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /run_job <job_name>"]


@pytest.mark.asyncio
async def test_run_job_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_job_name: str | None = None

        def run_job(self, job_name: str) -> ThreadTaskTransitionResult:
            self.seen_job_name = job_name
            return ThreadTaskTransitionResult(ok=True, message=f"Ran {job_name} job.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(run_job, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(run_job, "_service", service)
    update = _Update()

    await run_job.handle(update, _Context(args=["digest"]))

    assert service.seen_job_name == "digest"
    assert update.message.replies == ["Ran digest job."]


@pytest.mark.asyncio
async def test_run_replay_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_limit: int | None = None

        def run_replay_worker(self, *, limit: int) -> ThreadTaskTransitionResult:
            self.seen_limit = limit
            return ThreadTaskTransitionResult(
                ok=True,
                message="Triggered replay worker for up to 5 items; processed 2.",
            )

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(run_replay, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(run_replay, "_service", service)
    update = _Update()

    await run_replay.handle(update, _Context(args=["5"]))

    assert service.seen_limit == 5
    assert update.message.replies == ["Triggered replay worker for up to 5 items; processed 2."]


@pytest.mark.asyncio
async def test_run_replay_command_surfaces_paused_job(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def run_replay_worker(self, *, limit: int) -> ThreadTaskTransitionResult:
            return ThreadTaskTransitionResult(
                ok=False,
                message="Replay job is paused; resume it before running replay manually.",
            )

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(run_replay, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(run_replay, "_service", _Service())
    update = _Update()

    await run_replay.handle(update, _Context(args=[]))

    assert update.message.replies == [
        "Replay job is paused; resume it before running replay manually."
    ]


@pytest.mark.asyncio
async def test_pause_replay_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def pause_replay_job(self) -> ThreadTaskTransitionResult:
            return ThreadTaskTransitionResult(ok=True, message="Replay job paused.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(pause_replay, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(pause_replay, "_service", _Service())
    update = _Update()

    await pause_replay.handle(update, _Context(args=[]))

    assert update.message.replies == ["Replay job paused."]


@pytest.mark.asyncio
async def test_pause_job_command_rejects_invalid_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(pause_job, "reject_if_unauthorized", _allow)
    update = _Update()

    await pause_job.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /pause_job <job_name>"]


@pytest.mark.asyncio
async def test_pause_job_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def pause_job(self, job_name: str) -> ThreadTaskTransitionResult:
            return ThreadTaskTransitionResult(ok=True, message=f"{job_name} job paused.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(pause_job, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(pause_job, "_service", _Service())
    update = _Update()

    await pause_job.handle(update, _Context(args=["email_triage"]))

    assert update.message.replies == ["email_triage job paused."]


@pytest.mark.asyncio
async def test_job_command_rejects_invalid_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job, "reject_if_unauthorized", _allow)
    update = _Update()

    await job.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /job <job_name>"]


@pytest.mark.asyncio
async def test_job_command_formats_single_item(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def get_job_control(self, job_name: str) -> JobControlView | None:
            assert job_name == "replay"
            return JobControlView(
                job_name="replay",
                paused=True,
                run_command="/run_replay [limit]",
                note="bounded manual trigger",
            )

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(job, "_service", _Service())
    update = _Update()

    await job.handle(update, _Context(args=["replay"]))

    assert update.message.replies == [
        "Job replay\nStatus: paused\nRun: /run_replay [limit]\nNote: bounded manual trigger"
    ]


@pytest.mark.asyncio
async def test_job_command_surfaces_unknown_job(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def get_job_control(self, job_name: str) -> JobControlView | None:
            assert job_name == "not_a_job"
            return None

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(job, "_service", _Service())
    update = _Update()

    await job.handle(update, _Context(args=["not_a_job"]))

    assert update.message.replies == ["Unknown job: not_a_job."]


@pytest.mark.asyncio
async def test_job_controls_command_rejects_invalid_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job_controls, "reject_if_unauthorized", _allow)
    update = _Update()

    await job_controls.handle(update, _Context(args=["bad"]))

    assert update.message.replies == ["Usage: /job_controls [paused|active]"]


@pytest.mark.asyncio
async def test_job_controls_command_formats_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_job_controls(self) -> list[JobControlView]:
            return [
                JobControlView(
                    job_name="replay",
                    paused=True,
                    run_command="/run_replay [limit]",
                    note="bounded manual trigger",
                ),
                JobControlView(
                    job_name="email_triage",
                    paused=False,
                    run_command="/run_job email_triage",
                    note=None,
                ),
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job_controls, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(job_controls, "_service", _Service())
    update = _Update()

    await job_controls.handle(update, _Context(args=[]))

    assert update.message.replies == [
        "Job controls:\n"
        "replay: paused (inspect=/job replay; run=/run_replay [limit]; bounded manual trigger)\n"
        "email_triage: active (inspect=/job email_triage; run=/run_job email_triage)"
    ]


@pytest.mark.asyncio
async def test_job_controls_command_filters_paused_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_job_controls(self) -> list[JobControlView]:
            return [
                JobControlView(
                    job_name="replay",
                    paused=True,
                    run_command="/run_replay [limit]",
                    note="bounded manual trigger",
                ),
                JobControlView(
                    job_name="email_triage",
                    paused=False,
                    run_command="/run_job email_triage",
                    note=None,
                ),
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job_controls, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(job_controls, "_service", _Service())
    update = _Update()

    await job_controls.handle(update, _Context(args=["paused"]))

    assert update.message.replies == [
        "Paused jobs:\n"
        "replay: paused (inspect=/job replay; run=/run_replay [limit]; bounded manual trigger)"
    ]


@pytest.mark.asyncio
async def test_job_controls_command_reports_no_paused_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_job_controls(self) -> list[JobControlView]:
            return [
                JobControlView(
                    job_name="email_triage",
                    paused=False,
                    run_command="/run_job email_triage",
                    note=None,
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job_controls, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(job_controls, "_service", _Service())
    update = _Update()

    await job_controls.handle(update, _Context(args=["paused"]))

    assert update.message.replies == ["No paused jobs."]


@pytest.mark.asyncio
async def test_job_controls_command_filters_active_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_job_controls(self) -> list[JobControlView]:
            return [
                JobControlView(
                    job_name="replay",
                    paused=True,
                    run_command="/run_replay [limit]",
                    note="bounded manual trigger",
                ),
                JobControlView(
                    job_name="email_triage",
                    paused=False,
                    run_command="/run_job email_triage",
                    note=None,
                ),
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job_controls, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(job_controls, "_service", _Service())
    update = _Update()

    await job_controls.handle(update, _Context(args=["active"]))

    assert update.message.replies == [
        "Active jobs:\n"
        "email_triage: active (inspect=/job email_triage; run=/run_job email_triage)"
    ]


@pytest.mark.asyncio
async def test_job_controls_command_reports_no_active_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def list_job_controls(self) -> list[JobControlView]:
            return [
                JobControlView(
                    job_name="replay",
                    paused=True,
                    run_command="/run_replay [limit]",
                    note="bounded manual trigger",
                )
            ]

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(job_controls, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(job_controls, "_service", _Service())
    update = _Update()

    await job_controls.handle(update, _Context(args=["active"]))

    assert update.message.replies == ["No active jobs."]


@pytest.mark.asyncio
async def test_replay_status_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def get_replay_job_status(self) -> ThreadTaskTransitionResult:
            return ThreadTaskTransitionResult(ok=True, message="Replay job status: paused.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(replay_status, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(replay_status, "_service", _Service())
    update = _Update()

    await replay_status.handle(update, _Context(args=[]))

    assert update.message.replies == ["Replay job status: paused."]


@pytest.mark.asyncio
async def test_resume_replay_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def resume_replay_job(self) -> ThreadTaskTransitionResult:
            return ThreadTaskTransitionResult(ok=True, message="Replay job resumed.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(resume_replay, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(resume_replay, "_service", _Service())
    update = _Update()

    await resume_replay.handle(update, _Context(args=[]))

    assert update.message.replies == ["Replay job resumed."]


@pytest.mark.asyncio
async def test_resume_job_command_rejects_invalid_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(resume_job, "reject_if_unauthorized", _allow)
    update = _Update()

    await resume_job.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /resume_job <job_name>"]


@pytest.mark.asyncio
async def test_resume_job_command_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def resume_job(self, job_name: str) -> ThreadTaskTransitionResult:
            return ThreadTaskTransitionResult(ok=True, message=f"{job_name} job resumed.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(resume_job, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(resume_job, "_service", _Service())
    update = _Update()

    await resume_job.handle(update, _Context(args=["email_triage"]))

    assert update.message.replies == ["email_triage job resumed."]


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
                    latest_confidence_band=None,
                    latest_message_from=None,
                    latest_message_subject=None,
                    latest_message_snippet=None,
                    latest_proposal_type=None,
                    latest_proposal_status=None,
                    latest_draft_approval_status=None,
                    latest_draft_preview=None,
                    pending_task_count=0,
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
async def test_draft_usage_message_when_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(draft, "reject_if_unauthorized", _allow)
    update = _Update()

    await draft.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /draft <draft_id>"]


@pytest.mark.asyncio
async def test_draft_command_formats_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def get_draft_detail(self, draft_id: int):
            assert draft_id == 8
            return type(
                "DraftDetail",
                (),
                {
                    "id": 8,
                    "email_thread_id": 4,
                    "action_proposal_id": 12,
                    "status": "generated",
                    "approval_status": "approved",
                    "draft_subject": "Re: Opportunity",
                    "draft_body": "Thanks for reaching out.",
                    "transition_audits": [
                        {
                            "action": "approve",
                            "from_status": "pending_user",
                            "to_status": "approved",
                            "success": True,
                        }
                    ],
                    "send_attempts": [
                        {
                            "attempt_number": 1,
                            "status": "failed",
                            "failure_class": "timeout",
                        }
                    ],
                },
            )()

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(draft, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(draft, "_service", _Service())
    update = _Update()

    await draft.handle(update, _Context(args=["8"]))

    assert update.message.replies == [
        "\n".join(
            [
                "Draft 8",
                "Thread: 4",
                "Proposal: 12",
                "Status: generated",
                "Approval: approved",
                "Subject: Re: Opportunity",
                "Body: Thanks for reaching out.",
                "Recent audits:",
                "approve: pending_user -> approved (ok)",
                "Recent send attempts:",
                "1: failed timeout",
            ]
        )
    ]


@pytest.mark.asyncio
async def test_send_usage_message_when_id_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(send, "reject_if_unauthorized", _allow)
    update = _Update()

    await send.handle(update, _Context(args=[]))

    assert update.message.replies == ["Usage: /send <draft_id>"]


@pytest.mark.asyncio
async def test_send_parses_id_and_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen_id: int | None = None

        def send_draft(self, draft_id: int) -> DraftTransitionResult:
            self.seen_id = draft_id
            return DraftTransitionResult(ok=True, message="Sent draft 7.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(send, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(send, "_service", service)
    update = _Update()

    await send.handle(update, _Context(args=["7"]))

    assert service.seen_id == 7
    assert update.message.replies == ["Sent draft 7."]


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
async def test_email_config_formats_current_config(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def get_email_config(self):
            return type(
                "Config",
                (),
                {
                    "timezone_name": "America/Los_Angeles",
                    "default_follow_up_business_days": 5,
                    "approval_required_before_send": True,
                },
            )()

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(email_config, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(email_config, "_service", _Service())
    update = _Update()

    await email_config.handle(update, _Context(args=[]))

    assert update.message.replies == [
        "Email config:\n"
        "timezone: America/Los_Angeles\n"
        "followup_business_days: 5\n"
        "approval_required_before_send: true"
    ]


@pytest.mark.asyncio
async def test_set_email_timezone_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.seen: str | None = None

        def update_email_timezone(self, timezone_name: str) -> ThreadTaskTransitionResult:
            self.seen = timezone_name
            return ThreadTaskTransitionResult(ok=True, message="Email timezone set to UTC.")

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(set_email_timezone, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(set_email_timezone, "_service", service)
    update = _Update()

    await set_email_timezone.handle(update, _Context(args=["UTC"]))

    assert service.seen == "UTC"
    assert update.message.replies == ["Email timezone set to UTC."]


@pytest.mark.asyncio
async def test_set_followup_days_usage_message_on_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    monkeypatch.setattr(set_followup_days, "reject_if_unauthorized", _allow)
    update = _Update()

    await set_followup_days.handle(update, _Context(args=["oops"]))

    assert update.message.replies == ["Usage: /set_followup_days <non-negative integer>"]


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
async def test_reprocess_thread_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Service:
        def __init__(self) -> None:
            self.calls: list[tuple[int, bool]] = []

        def reprocess_thread(
            self, thread_id: int, *, dry_run: bool = True
        ) -> ThreadReprocessResult:
            self.calls.append((thread_id, dry_run))
            return ThreadReprocessResult(
                ok=True,
                message="Reprocess dry-run for thread 8: completed.",
            )

    async def _allow(_update: _Update, _context: _Context) -> bool:
        return False

    service = _Service()
    monkeypatch.setattr(reprocess_thread, "reject_if_unauthorized", _allow)
    monkeypatch.setattr(reprocess_thread, "_service", service)
    update = _Update()

    await reprocess_thread.handle(update, _Context(args=["8"]))

    assert service.calls == [(8, True)]
    assert update.message.replies == ["Reprocess dry-run for thread 8: completed."]


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
                latest_confidence_band="high",
                latest_message_from="founder@example.com",
                latest_message_subject="Checking in",
                latest_message_snippet="Wanted to follow up.",
                latest_proposal_type="reply",
                latest_proposal_status="proposed",
                latest_draft_approval_status="pending_user",
                latest_draft_preview="Draft reply preview",
                pending_task_count=2,
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
            "Confidence: high\n"
            "Reason: reply_needed\n"
            "Summary: Reply to recruiter\n"
            "Latest proposal: reply [proposed]\n"
            "Latest draft: pending_user: Draft reply preview\n"
            "Pending tasks: 2\n"
            "Latest message from: founder@example.com\n"
            "Latest message subject: Checking in\n"
            "Latest message snippet: Wanted to follow up."
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
                    latest_confidence_band=None,
                    latest_message_from=None,
                    latest_message_subject=None,
                    latest_message_snippet=None,
                    latest_proposal_type=None,
                    latest_proposal_status=None,
                    latest_draft_approval_status=None,
                    latest_draft_preview=None,
                    pending_task_count=0,
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
