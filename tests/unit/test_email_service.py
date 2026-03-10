from datetime import UTC, datetime

from email_agent import query as email_query
from email_agent.adapters import build_helm_runtime
from email_agent.reminders import (
    complete_thread_task,
    create_thread_reminder,
    list_scheduled_tasks,
    list_thread_scheduled_tasks,
)
from email_agent.reprocess import reprocess_email_thread
from email_agent.types import EmailMessage
from helm_api.services.email_service import override_thread
from helm_storage.db import Base
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.contracts import NewActionProposal, NewEmailDraft, NewEmailThread
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_email_service_lists_threads_proposals_and_drafts(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)

        thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-api-1",
                business_state="waiting_on_user",
                visible_labels=("Action", "Urgent"),
                current_summary="Recruiter follow-up",
                latest_confidence_band="High",
                resurfacing_source="new_message",
                action_reason="reply_needed",
            )
        )
        proposal = proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Reply with availability",
                confidence_band="High",
            )
        )
        draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                draft_body="Thanks, I would be glad to connect.",
                draft_subject="Re: Interview availability",
            )
        )

    threads = email_query.list_email_threads(runtime=runtime)
    proposals = email_query.list_email_proposals(runtime=runtime)
    drafts = email_query.list_email_drafts(runtime=runtime)

    assert len(threads) == 1
    assert threads[0]["provider_thread_id"] == "thr-api-1"
    assert threads[0]["visible_labels"] == ["Action", "Urgent"]
    assert len(proposals) == 1
    assert proposals[0]["proposal_type"] == "reply"
    assert len(drafts) == 1
    assert drafts[0]["approval_status"] == "pending_user"


def test_email_thread_detail_and_reprocess() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)
        message_repo = SQLAlchemyEmailMessageRepository(session)

        thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-api-detail",
                business_state="waiting_on_user",
                visible_labels=("Action",),
                current_summary="Need to reply",
            )
        )
        thread_id = thread.id
        proposal = proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread_id,
                proposal_type="reply",
                rationale="Reply to recruiter",
                confidence_band="High",
            )
        )
        draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread_id,
                action_proposal_id=proposal.id,
                draft_body="Thanks for reaching out.",
                draft_subject="Re: Opportunity",
            )
        )
        message_repo.upsert_from_normalized(
            EmailMessage(
                provider_message_id="msg-api-detail",
                provider_thread_id="thr-api-detail",
                from_address="recruiter@example.com",
                subject="Opportunity",
                body_text="Can we schedule time?",
                received_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
                normalized_at=datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC),
                source="gmail",
            ),
            email_thread_id=thread_id,
        )

    detail = email_query.get_email_thread_detail(thread_id=thread_id, runtime=runtime)
    assert detail is not None
    assert detail["thread"]["provider_thread_id"] == "thr-api-detail"
    assert len(detail["proposals"]) == 1
    assert len(detail["drafts"]) == 1
    assert len(detail["messages"]) == 1

    dry_run = reprocess_email_thread(thread_id=thread_id, dry_run=True, runtime=runtime)
    assert dry_run.status == "accepted"
    assert dry_run.reprocessed is False

    executed = reprocess_email_thread(thread_id=thread_id, dry_run=False, runtime=runtime)
    assert executed.status == "accepted"
    assert executed.reprocessed is True

    scheduled = create_thread_reminder(
        thread_id=thread_id,
        due_at=datetime(2026, 1, 3, 9, 0, 0, tzinfo=UTC),
        created_by="user",
        task_type="reminder",
        runtime=runtime,
    )
    assert scheduled.status == "accepted"
    assert scheduled.task_id is not None

    tasks = list_thread_scheduled_tasks(thread_id=thread_id, runtime=runtime)
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "reminder"
    completed = complete_thread_task(
        thread_id=thread_id,
        task_id=tasks[0]["id"],
        runtime=runtime,
    )
    assert completed.status == "accepted"
    assert completed.completed is True


def test_email_service_lists_global_scheduled_tasks() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        first = thread_repo.create(NewEmailThread(provider_thread_id="thr-task-1"))
        second = thread_repo.create(NewEmailThread(provider_thread_id="thr-task-2"))
        first_id = first.id
        second_id = second.id

    create_thread_reminder(
        thread_id=second_id,
        due_at=datetime(2026, 1, 3, 9, 0, 0, tzinfo=UTC),
        created_by="user",
        task_type="followup",
        runtime=runtime,
    )
    scheduled = create_thread_reminder(
        thread_id=first_id,
        due_at=datetime(2026, 1, 2, 9, 0, 0, tzinfo=UTC),
        created_by="user",
        task_type="reminder",
        runtime=runtime,
    )
    assert scheduled.task_id is not None
    complete_thread_task(
        thread_id=first_id,
        task_id=scheduled.task_id,
        runtime=runtime,
    )

    all_tasks = list_scheduled_tasks(runtime=runtime, limit=10)
    pending_tasks = list_scheduled_tasks(runtime=runtime, status="pending", limit=10)
    completed_tasks = list_scheduled_tasks(runtime=runtime, status="completed", limit=10)

    assert [task["task_type"] for task in all_tasks] == ["reminder", "followup"]
    assert [task["status"] for task in all_tasks] == ["completed", "pending"]
    assert len(pending_tasks) == 1
    assert pending_tasks[0]["task_type"] == "followup"
    assert len(completed_tasks) == 1
    assert completed_tasks[0]["task_type"] == "reminder"


def test_email_thread_override_updates_state(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_helm_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(
                provider_thread_id="thr-api-override",
                business_state="waiting_on_user",
                visible_labels=("Action",),
                current_summary="Need reply",
            )
        )
        thread_id = thread.id

    monkeypatch.setattr("helm_api.services.email_service._runtime", lambda: runtime)

    result = override_thread(
        thread_id=thread_id,
        business_state="resolved",
        visible_labels=[],
        current_summary="Resolved manually",
        latest_confidence_band="High",
        action_reason="user_marked_done",
    )

    assert result["status"] == "accepted"
    assert result["thread"]["business_state"] == "resolved"
    assert result["thread"]["visible_labels"] == []
    assert result["thread"]["resurfacing_source"] == "user_override"
