from datetime import UTC, datetime

import pytest
from helm_connectors.gmail import normalize_message, pull_new_messages
from helm_orchestration.email_flow import build_email_triage_graph, run_email_triage_workflow
from helm_storage.db import Base
from helm_storage.models import (
    ActionItemORM,
    AgentRunORM,
    DigestItemORM,
    DraftReplyORM,
    EmailMessageORM,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def test_normalize_message_contract() -> None:
    normalized = normalize_message(
        {
            "id": "msg-1",
            "threadId": "thr-1",
            "from": "recruiter@example.com",
            "subject": "Backend role",
            "snippet": "Want to chat about a role?",
            "internalDate": "1734567890000",
        },
        normalized_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    assert normalized.provider_message_id == "msg-1"
    assert normalized.provider_thread_id == "thr-1"
    assert normalized.from_address == "recruiter@example.com"
    assert normalized.subject == "Backend role"
    assert normalized.body_text == "Want to chat about a role?"
    assert normalized.source == "gmail"


def test_normalize_message_requires_message_id() -> None:
    with pytest.raises(ValueError, match="must include non-empty `id`"):
        normalize_message({"threadId": "t-1"})


def test_pull_new_messages_manual_payload_normalizes() -> None:
    messages = pull_new_messages(
        manual_payload=[
            {
                "id": "msg-2",
                "from": "sender@example.com",
                "subject": "Hello",
                "body_text": "Body",
            }
        ]
    )

    assert len(messages) == 1
    assert messages[0].provider_message_id == "msg-2"
    assert messages[0].subject == "Hello"


def test_email_triage_graph_scaffold_result_shape() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    message = normalize_message(
        {
            "id": "msg-3",
            "threadId": "thr-3",
            "from": "sender@example.com",
            "subject": "Status update",
            "snippet": "Quick update on this.",
        }
    )

    graph = build_email_triage_graph()
    result = run_email_triage_workflow(message, graph=graph, session_factory=session_local)

    assert result.message_id == "msg-3"
    assert result.classification == "unclassified"
    assert result.priority_score == 3
    assert result.action_item_required is False
    assert result.draft_reply_required is False
    assert result.digest_item_required is False
    assert result.workflow_status == "completed"


def test_email_triage_persists_artifacts_and_is_idempotent_for_repeated_runs() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    message = normalize_message(
        {
            "id": "msg-4",
            "threadId": "thr-4",
            "from": "recruiter@example.com",
            "subject": "Staff Backend role",
            "snippet": "Would you be open to an interview?",
        }
    )

    graph = build_email_triage_graph()
    first_result = run_email_triage_workflow(
        message,
        graph=graph,
        session_factory=session_local,
    )
    second_result = run_email_triage_workflow(
        message,
        graph=graph,
        session_factory=session_local,
    )

    assert first_result.action_item_required is True
    assert first_result.draft_reply_required is True
    assert first_result.digest_item_required is True
    assert first_result.action_item_id is not None
    assert first_result.draft_reply_id is not None
    assert first_result.digest_item_id is not None

    assert second_result.action_item_id == first_result.action_item_id
    assert second_result.draft_reply_id == first_result.draft_reply_id
    assert second_result.digest_item_id == first_result.digest_item_id

    with Session(engine) as session:
        email_messages = list(session.execute(select(EmailMessageORM)).scalars().all())
        action_items = list(session.execute(select(ActionItemORM)).scalars().all())
        draft_replies = list(session.execute(select(DraftReplyORM)).scalars().all())
        digest_items = list(session.execute(select(DigestItemORM)).scalars().all())
        agent_runs = list(session.execute(select(AgentRunORM)).scalars().all())

    assert len(email_messages) == 1
    assert email_messages[0].processed_at is not None
    assert len(action_items) == 1
    assert len(draft_replies) == 1
    assert len(digest_items) == 1
    assert len(agent_runs) == 2
    assert all(run.status == "succeeded" for run in agent_runs)
