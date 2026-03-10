from datetime import UTC, datetime

import pytest
from helm_connectors import gmail
from helm_connectors.gmail import normalize_message, pull_new_messages, pull_new_messages_report
from helm_orchestration.email_flow import build_email_triage_graph, run_email_triage_workflow
from helm_storage.db import Base
from helm_storage.models import (
    ActionItemORM,
    ActionProposalORM,
    AgentRunORM,
    DigestItemORM,
    DraftReplyORM,
    EmailDraftORM,
    EmailMessageORM,
    EmailThreadORM,
)
from helm_storage.repositories.agent_runs import AgentRunStatus
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


def test_pull_new_messages_manual_payload_records_failures_and_keeps_valid() -> None:
    report = pull_new_messages_report(
        manual_payload=[
            {"id": "msg-ok", "subject": "Hello"},
            {"threadId": "missing-id"},
        ]
    )

    assert len(report.messages) == 1
    assert report.messages[0].provider_message_id == "msg-ok"
    assert report.failure_counts == {"missing_id": 1}


def test_pull_new_messages_returns_empty_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("GMAIL_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GMAIL_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("GMAIL_USER_EMAIL", raising=False)
    assert pull_new_messages() == []


def test_pull_new_messages_polling_normalizes_provider_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in {
        "GMAIL_CLIENT_ID": "id",
        "GMAIL_CLIENT_SECRET": "secret",
        "GMAIL_REFRESH_TOKEN": "refresh",
        "GMAIL_USER_EMAIL": "me@example.com",
    }.items():
        monkeypatch.setenv(name, value)

    class FakeGetRequest:
        def __init__(self, message_id: str) -> None:
            self.message_id = message_id

        def execute(self) -> dict[str, object]:
            return {
                "id": self.message_id,
                "threadId": "thr-9",
                "internalDate": "1734567890000",
                "snippet": "snippet fallback",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Subject", "value": "Role update"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": "SGVsbG8gZnJvbSBHbWFpbA"},
                        }
                    ],
                },
            }

    class FakeMessagesResource:
        def list(self, **_: object):
            return self

        def get(self, *, id: str, **_: object) -> FakeGetRequest:
            return FakeGetRequest(id)

        def execute(self) -> dict[str, object]:
            return {"messages": [{"id": "msg-9"}]}

    class FakeUsersResource:
        def messages(self) -> FakeMessagesResource:
            return FakeMessagesResource()

    class FakeService:
        def users(self) -> FakeUsersResource:
            return FakeUsersResource()

    monkeypatch.setattr(gmail, "_build_gmail_service", lambda: FakeService())
    messages = pull_new_messages()

    assert len(messages) == 1
    assert messages[0].provider_message_id == "msg-9"
    assert messages[0].provider_thread_id == "thr-9"
    assert messages[0].from_address == "sender@example.com"
    assert messages[0].subject == "Role update"
    assert messages[0].body_text == "Hello from Gmail"


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
    assert first_result.email_thread_id is not None
    assert first_result.action_proposal_id is not None
    assert first_result.email_draft_id is not None
    assert first_result.action_item_id is not None
    assert first_result.draft_reply_id is not None
    assert first_result.digest_item_id is not None

    assert second_result.email_thread_id == first_result.email_thread_id
    assert second_result.action_proposal_id == first_result.action_proposal_id
    assert second_result.email_draft_id == first_result.email_draft_id
    assert second_result.action_item_id == first_result.action_item_id
    assert second_result.draft_reply_id == first_result.draft_reply_id
    assert second_result.digest_item_id == first_result.digest_item_id

    with Session(engine) as session:
        email_messages = list(session.execute(select(EmailMessageORM)).scalars().all())
        email_threads = list(session.execute(select(EmailThreadORM)).scalars().all())
        action_proposals = list(session.execute(select(ActionProposalORM)).scalars().all())
        email_drafts = list(session.execute(select(EmailDraftORM)).scalars().all())
        action_items = list(session.execute(select(ActionItemORM)).scalars().all())
        draft_replies = list(session.execute(select(DraftReplyORM)).scalars().all())
        digest_items = list(session.execute(select(DigestItemORM)).scalars().all())
        agent_runs = list(session.execute(select(AgentRunORM)).scalars().all())

    assert len(email_messages) == 1
    assert email_messages[0].processed_at is not None
    assert email_messages[0].email_thread_id == first_result.email_thread_id
    assert len(email_threads) == 1
    assert email_threads[0].provider_thread_id == "thr-4"
    assert email_threads[0].business_state == "waiting_on_user"
    assert email_threads[0].visible_labels == "Action"
    assert len(action_proposals) == 1
    assert len(email_drafts) == 1
    assert len(action_items) == 1
    assert len(draft_replies) == 1
    assert len(digest_items) == 1
    assert len(agent_runs) == 2
    assert all(run.status == AgentRunStatus.SUCCEEDED.value for run in agent_runs)


def test_email_triage_consolidates_near_duplicate_messages_on_same_thread() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    first_message = normalize_message(
        {
            "id": "msg-10-a",
            "threadId": "thr-10",
            "from": "recruiter@example.com",
            "subject": "Staff Backend role",
            "snippet": "Would you be open to an interview?",
        }
    )
    second_message = normalize_message(
        {
            "id": "msg-10-b",
            "threadId": "thr-10",
            "from": "recruiter@example.com",
            "subject": "Staff Backend role",
            "snippet": "Checking in on this thread.",
        }
    )

    graph = build_email_triage_graph()
    first_result = run_email_triage_workflow(
        first_message,
        graph=graph,
        session_factory=session_local,
    )
    second_result = run_email_triage_workflow(
        second_message,
        graph=graph,
        session_factory=session_local,
    )

    assert first_result.action_item_id is not None
    assert first_result.email_thread_id is not None
    assert second_result.action_item_id == first_result.action_item_id
    assert second_result.email_thread_id == first_result.email_thread_id
    assert first_result.draft_reply_id is not None
    assert second_result.draft_reply_id == first_result.draft_reply_id
    assert first_result.action_proposal_id is not None
    assert second_result.action_proposal_id == first_result.action_proposal_id
    assert first_result.email_draft_id is not None
    assert second_result.email_draft_id == first_result.email_draft_id

    with Session(engine) as session:
        email_threads = list(session.execute(select(EmailThreadORM)).scalars().all())
        action_proposals = list(session.execute(select(ActionProposalORM)).scalars().all())
        email_drafts = list(session.execute(select(EmailDraftORM)).scalars().all())
        action_items = list(session.execute(select(ActionItemORM)).scalars().all())
        draft_replies = list(session.execute(select(DraftReplyORM)).scalars().all())
        email_messages = list(session.execute(select(EmailMessageORM)).scalars().all())

    assert len(email_threads) == 1
    assert len(action_proposals) == 1
    assert len(email_drafts) == 1
    assert len(action_items) == 1
    assert len(draft_replies) == 1
    assert len(email_messages) == 2
