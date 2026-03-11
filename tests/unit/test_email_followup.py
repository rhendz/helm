from datetime import UTC, datetime

from email_agent.followup import add_business_days, enqueue_stale_followups
from email_agent.types import EmailMessage
from helm_runtime.email_agent import build_email_agent_runtime
from helm_storage.db import Base
from helm_storage.repositories.contracts import (
    EmailAgentConfigPatch,
    NewEmailThread,
    NewOutboundEmailMessage,
    NewScheduledThreadTask,
)
from helm_storage.repositories.email_agent_config import SQLAlchemyEmailAgentConfigRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_storage.repositories.scheduled_thread_tasks import SQLAlchemyScheduledThreadTaskRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_add_business_days_skips_weekends() -> None:
    start_at = datetime(2026, 3, 6, 9, 0, tzinfo=UTC)

    result = add_business_days(start_at, business_days=3)

    assert result == datetime(2026, 3, 11, 9, 0, tzinfo=UTC)


def test_enqueue_stale_followups_creates_due_followup_task() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(
                provider_thread_id="thr-followup-scan",
                business_state="waiting_on_other_party",
                current_summary="Waiting on recruiter",
            )
        )
        SQLAlchemyEmailMessageRepository(session).create_outbound(
            NewOutboundEmailMessage(
                provider_message_id="msg-outbound-1",
                provider_thread_id="thr-followup-scan",
                email_thread_id=thread.id,
                source_draft_id=1,
                from_address="me@example.com",
                to_addresses=("recruiter@example.com",),
                subject="Re: Interview",
                body_text="Following up on timing.",
                received_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
                normalized_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
            )
        )
        thread_id = thread.id

    results = enqueue_stale_followups(
        runtime=runtime,
        now=datetime(2026, 3, 11, 9, 1, tzinfo=UTC),
    )

    assert len(results) == 1
    assert results[0].action == "enqueued"
    assert results[0].reason == "followup_due"

    tasks = runtime.list_scheduled_tasks_for_thread(thread_id=thread_id)
    assert len(tasks) == 1
    assert tasks[0]["task_type"] == "followup"
    assert tasks[0]["created_by"] == "system"
    assert tasks[0]["due_at"].replace(tzinfo=UTC) == datetime(2026, 3, 11, 9, 0, tzinfo=UTC)


def test_enqueue_stale_followups_uses_configured_business_day_window() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    with Session(engine) as session:
        SQLAlchemyEmailAgentConfigRepository(session).update(
            EmailAgentConfigPatch(default_follow_up_business_days=5)
        )
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(
                provider_thread_id="thr-followup-config",
                business_state="waiting_on_other_party",
            )
        )
        SQLAlchemyEmailMessageRepository(session).create_outbound(
            NewOutboundEmailMessage(
                provider_message_id="msg-outbound-2",
                provider_thread_id="thr-followup-config",
                email_thread_id=thread.id,
                source_draft_id=2,
                from_address="me@example.com",
                to_addresses=("person@example.com",),
                subject="Checking in",
                body_text="Any update?",
                received_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
                normalized_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
            )
        )

    results = enqueue_stale_followups(
        runtime=runtime,
        now=datetime(2026, 3, 12, 9, 0, tzinfo=UTC),
    )

    assert len(results) == 1
    assert results[0].action == "skipped"
    assert results[0].reason == "not_due_yet"


def test_enqueue_stale_followups_skips_threads_with_pending_followup() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(
                provider_thread_id="thr-followup-pending",
                business_state="waiting_on_other_party",
            )
        )
        SQLAlchemyEmailMessageRepository(session).create_outbound(
            NewOutboundEmailMessage(
                provider_message_id="msg-outbound-3",
                provider_thread_id="thr-followup-pending",
                email_thread_id=thread.id,
                source_draft_id=3,
                from_address="me@example.com",
                to_addresses=("person@example.com",),
                subject="Followup",
                body_text="Just checking in.",
                received_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
                normalized_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
            )
        )
        SQLAlchemyScheduledThreadTaskRepository(session).create(
            NewScheduledThreadTask(
                email_thread_id=thread.id,
                task_type="followup",
                created_by="system",
                due_at=datetime(2026, 3, 11, 9, 0, tzinfo=UTC),
                reason="followup_due",
            )
        )

    results = enqueue_stale_followups(
        runtime=runtime,
        now=datetime(2026, 3, 11, 9, 1, tzinfo=UTC),
    )

    assert len(results) == 1
    assert results[0].action == "skipped"
    assert results[0].reason == "pending_followup_exists"


def test_enqueue_stale_followups_skips_when_new_inbound_arrived() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(
                provider_thread_id="thr-followup-replied",
                business_state="waiting_on_other_party",
            )
        )
        SQLAlchemyEmailMessageRepository(session).create_outbound(
            NewOutboundEmailMessage(
                provider_message_id="msg-outbound-4",
                provider_thread_id="thr-followup-replied",
                email_thread_id=thread.id,
                source_draft_id=4,
                from_address="me@example.com",
                to_addresses=("person@example.com",),
                subject="Checking in",
                body_text="Any update?",
                received_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
                normalized_at=datetime(2026, 3, 6, 9, 0, tzinfo=UTC),
            )
        )
        SQLAlchemyEmailMessageRepository(session).upsert_from_normalized(
            EmailMessage(
                provider_message_id="msg-inbound-4",
                provider_thread_id="thr-followup-replied",
                from_address="person@example.com",
                subject="Re: Checking in",
                body_text="Replying now.",
                received_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
                normalized_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
            ),
            email_thread_id=thread.id,
        )

    results = enqueue_stale_followups(
        runtime=runtime,
        now=datetime(2026, 3, 11, 9, 1, tzinfo=UTC),
    )

    assert len(results) == 1
    assert results[0].action == "skipped"
    assert results[0].reason == "reply_received_after_outbound"
