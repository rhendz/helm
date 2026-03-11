from datetime import UTC, datetime

from helm_connectors.gmail import NormalizedGmailMessage, PullMessagesReport
from helm_storage.db import Base
from helm_storage.models import AgentRunORM, EmailMessageORM
from helm_worker.jobs import email_reconciliation_sweep
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def test_email_reconciliation_sweep_skips_already_processed_messages(
    monkeypatch,
) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    runtime = email_reconciliation_sweep.build_email_agent_runtime(session_local)
    thread = runtime.get_or_create_thread(provider_thread_id="thr-reconcile-1")
    runtime.upsert_inbound_message(
        message=NormalizedGmailMessage(
            provider_message_id="msg-reconcile-1",
            provider_thread_id="thr-reconcile-1",
            from_address="sender@example.com",
            subject="Already seen",
            body_text="No new work",
            received_at=datetime(2026, 3, 10, 18, 0, tzinfo=UTC),
            normalized_at=datetime(2026, 3, 10, 18, 1, tzinfo=UTC),
        ),
        email_thread_id=thread.id,
    )
    runtime.mark_message_processed(
        "msg-reconcile-1",
        processed_at=datetime(2026, 3, 10, 18, 2, tzinfo=UTC),
    )

    monkeypatch.setattr(
        email_reconciliation_sweep,
        "build_email_agent_runtime",
        lambda: runtime,
    )
    monkeypatch.setattr(
        email_reconciliation_sweep,
        "pull_new_messages_report",
        lambda: PullMessagesReport(
            messages=[
                NormalizedGmailMessage(
                    provider_message_id="msg-reconcile-1",
                    provider_thread_id="thr-reconcile-1",
                    from_address="sender@example.com",
                    subject="Already seen",
                    body_text="No new work",
                    received_at=datetime(2026, 3, 10, 18, 0, tzinfo=UTC),
                    normalized_at=datetime(2026, 3, 10, 18, 1, tzinfo=UTC),
                )
            ],
            failure_counts={},
            next_history_cursor="cursor-9",
            mode="poll",
        ),
    )

    email_reconciliation_sweep.run()

    config = runtime.get_email_agent_config()

    with Session(engine) as session:
        messages = list(session.execute(select(EmailMessageORM)).scalars().all())
        runs = list(session.execute(select(AgentRunORM)).scalars().all())

    assert config.last_history_cursor == "cursor-9"
    assert len(messages) == 1
    assert messages[0].provider_message_id == "msg-reconcile-1"
    assert messages[0].processed_at is not None
    assert runs == []
