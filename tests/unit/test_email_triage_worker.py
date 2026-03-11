from datetime import UTC, datetime

from helm_connectors.gmail import NormalizedGmailMessage, PullMessagesReport
from helm_storage.db import Base
from helm_storage.models import EmailMessageORM
from helm_worker.jobs import email_triage
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def test_email_triage_worker_processes_changed_messages_and_updates_history_cursor(
    monkeypatch,
) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    runtime = email_triage.build_email_agent_runtime(session_local)
    runtime.update_email_agent_config(last_history_cursor="cursor-1")

    monkeypatch.setattr(email_triage, "build_email_agent_runtime", lambda: runtime)
    monkeypatch.setattr(
        email_triage,
        "pull_changed_messages_report",
        lambda *, last_history_cursor: PullMessagesReport(
            messages=[
                NormalizedGmailMessage(
                    provider_message_id="msg-history-1",
                    provider_thread_id="thr-history-1",
                    from_address="sender@example.com",
                    subject="History update",
                    body_text="Please take a look.",
                    received_at=datetime(2026, 3, 10, 18, 0, tzinfo=UTC),
                    normalized_at=datetime(2026, 3, 10, 18, 1, tzinfo=UTC),
                )
            ],
            failure_counts={},
            next_history_cursor="cursor-2",
            mode="history",
        ),
    )

    email_triage.run()

    config = runtime.get_email_agent_config()
    assert config.last_history_cursor == "cursor-2"

    with Session(engine) as session:
        messages = list(session.execute(select(EmailMessageORM)).scalars().all())

    assert len(messages) == 1
    assert messages[0].provider_message_id == "msg-history-1"
    assert messages[0].processed_at is not None


def test_email_triage_worker_recovery_poll_resynchronizes_history_cursor(
    monkeypatch,
) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    runtime = email_triage.build_email_agent_runtime(session_local)
    runtime.update_email_agent_config(last_history_cursor="cursor-stale")

    monkeypatch.setattr(email_triage, "build_email_agent_runtime", lambda: runtime)
    monkeypatch.setattr(
        email_triage,
        "pull_changed_messages_report",
        lambda *, last_history_cursor: PullMessagesReport(
            messages=[],
            failure_counts={},
            next_history_cursor="cursor-recovered",
            mode="recovery_poll",
            recovery_reason="history_cursor_invalid",
        ),
    )

    email_triage.run()

    config = runtime.get_email_agent_config()
    assert config.last_history_cursor == "cursor-recovered"
