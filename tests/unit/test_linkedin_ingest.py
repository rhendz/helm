from datetime import UTC, datetime

from helm_connectors.linkedin import normalize_event, pull_new_events, pull_new_events_report
from helm_storage.db import Base
from helm_storage.models import LinkedInMessageORM, LinkedInThreadORM
from helm_storage.repositories.linkedin_messages import SQLAlchemyLinkedInMessageRepository
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_normalize_linkedin_event_contract() -> None:
    normalized = normalize_event(
        {
            "id": "li-msg-1",
            "thread_id": "li-thread-1",
            "sender_name": "Jane Recruiter",
            "body_text": "Can we chat this week?",
            "received_at": "2026-03-09T09:00:00Z",
        },
        normalized_at=datetime(2026, 3, 9, 9, 1, 0, tzinfo=UTC),
    )

    assert normalized.provider_message_id == "li-msg-1"
    assert normalized.provider_thread_id == "li-thread-1"
    assert normalized.sender_name == "Jane Recruiter"
    assert normalized.body_text == "Can we chat this week?"
    assert normalized.source == "linkedin"


def test_pull_new_events_manual_payload_normalizes() -> None:
    events = pull_new_events(manual_payload=[{"id": "li-msg-2", "body_text": "hello"}])
    assert len(events) == 1
    assert events[0].provider_message_id == "li-msg-2"
    assert events[0].provider_thread_id == "li-msg-2"


def test_pull_new_events_manual_payload_records_failures_and_keeps_valid() -> None:
    report = pull_new_events_report(
        manual_payload=[
            {"id": "li-msg-ok", "body_text": "valid"},
            {"thread_id": "missing-id"},
        ]
    )

    assert len(report.events) == 1
    assert report.events[0].provider_message_id == "li-msg-ok"
    assert report.failure_counts == {"missing_id": 1}


def test_linkedin_repository_upsert_is_idempotent() -> None:
    with _session() as session:
        repository = SQLAlchemyLinkedInMessageRepository(session)
        normalized = normalize_event(
            {
                "id": "li-msg-3",
                "thread_id": "li-thread-3",
                "sender_name": "Ankush",
                "body_text": "checking in",
            }
        )

        first = repository.upsert_from_normalized(normalized)
        second = repository.upsert_from_normalized(normalized)

        assert first.id == second.id
        messages = list(session.execute(select(LinkedInMessageORM)).scalars().all())
        threads = list(session.execute(select(LinkedInThreadORM)).scalars().all())
        assert len(messages) == 1
        assert len(threads) == 1
