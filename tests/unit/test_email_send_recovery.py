from datetime import UTC, datetime

from email_agent import query as email_query
from email_agent.send_recovery import run_pending_send_retries
from email_agent.types import EmailMessage
from helm_providers.gmail import GmailSendResult
from helm_runtime.email_agent import build_email_agent_runtime
from helm_storage.db import Base
from helm_storage.repositories.contracts import NewEmailDraft, NewEmailThread
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_run_pending_send_retries_retries_retryable_failures(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-send-retry")
        )
        draft = SQLAlchemyEmailDraftRepository(session).create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Retry me",
                draft_subject="Re: Retry",
                approval_status="approved",
                status="send_failed",
            )
        )
        SQLAlchemyEmailMessageRepository(session).upsert_from_normalized(
            EmailMessage(
                provider_message_id="msg-send-retry",
                provider_thread_id="thr-send-retry",
                from_address="person@example.com",
                subject="Retry",
                body_text="Please send",
                received_at=datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
                normalized_at=datetime(2026, 3, 10, 16, 0, tzinfo=UTC),
            ),
            email_thread_id=thread.id,
        )
        attempt = runtime.create_send_attempt(
            draft_id=draft.id,
            email_thread_id=thread.id,
            attempt_number=1,
            started_at=datetime(2026, 3, 10, 16, 1, tzinfo=UTC),
        )
        runtime.complete_send_attempt(
            attempt_id=attempt.id,
            status="failed",
            completed_at=datetime(2026, 3, 10, 16, 2, tzinfo=UTC),
            failure_class="timeout",
            failure_message="Timed out",
        )
        draft_id = draft.id

    monkeypatch.setattr(
        "email_agent.send.send_reply",
        lambda **_: GmailSendResult(
            provider_message_id="gmail-out-retry-1",
            provider_thread_id="thr-send-retry",
            from_address="me@example.com",
            to_address="person@example.com",
            subject="Re: Retry",
            body_text="Retry me",
            sent_at=datetime(2026, 3, 10, 16, 3, tzinfo=UTC),
        ),
    )

    results = run_pending_send_retries(runtime=runtime)

    assert len(results) == 1
    assert results[0].action == "retried"
    assert results[0].sent is True

    detail = email_query.get_email_draft_detail(draft_id=draft_id, runtime=runtime)
    assert detail is not None
    assert detail["status"] == "generated"
    assert detail["final_sent_message_id"] is not None
    assert len(detail["send_attempts"]) == 2
    assert detail["send_attempts"][0]["status"] == "succeeded"
    assert detail["send_attempts"][0]["attempt_number"] == 2


def test_run_pending_send_retries_skips_non_retryable_failures() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-send-unknown")
        )
        draft = SQLAlchemyEmailDraftRepository(session).create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Do not auto retry",
                approval_status="approved",
                status="send_failed",
            )
        )
        attempt = runtime.create_send_attempt(
            draft_id=draft.id,
            email_thread_id=thread.id,
            attempt_number=1,
            started_at=datetime(2026, 3, 10, 17, 0, tzinfo=UTC),
        )
        runtime.complete_send_attempt(
            attempt_id=attempt.id,
            status="failed",
            completed_at=datetime(2026, 3, 10, 17, 1, tzinfo=UTC),
            failure_class="unknown_delivery_state",
            failure_message="Provider timed out after accept",
        )
        draft_id = draft.id

    results = run_pending_send_retries(runtime=runtime)

    assert len(results) == 1
    assert results[0].action == "skipped"
    assert results[0].reason == "non_retryable_failure"
    detail = email_query.get_email_draft_detail(draft_id=draft_id, runtime=runtime)
    assert detail is not None
    assert len(detail["send_attempts"]) == 1


def test_run_pending_send_retries_stops_after_automatic_attempt_limit(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    runtime = build_email_agent_runtime(session_local)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-send-exhausted")
        )
        draft = SQLAlchemyEmailDraftRepository(session).create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Exhaust me",
                approval_status="approved",
                status="send_failed",
            )
        )
        for attempt_number in range(1, 4):
            attempt = runtime.create_send_attempt(
                draft_id=draft.id,
                email_thread_id=thread.id,
                attempt_number=attempt_number,
                started_at=datetime(2026, 3, 10, 18, attempt_number, tzinfo=UTC),
            )
            runtime.complete_send_attempt(
                attempt_id=attempt.id,
                status="failed",
                completed_at=datetime(2026, 3, 10, 18, attempt_number, 30, tzinfo=UTC),
                failure_class="provider_5xx",
                failure_message="Upstream unavailable",
            )

    observed = {"calls": 0}

    def fail_if_called(**_kwargs) -> GmailSendResult:  # noqa: ANN001
        observed["calls"] += 1
        raise AssertionError(
            "send_reply should not be called after automatic retries are exhausted"
        )

    monkeypatch.setattr("email_agent.send.send_reply", fail_if_called)

    results = run_pending_send_retries(runtime=runtime)

    assert len(results) == 1
    assert results[0].action == "skipped"
    assert results[0].reason == "automatic_attempts_exhausted"
    assert observed["calls"] == 0
