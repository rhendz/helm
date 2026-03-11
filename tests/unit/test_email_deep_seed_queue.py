from helm_storage.db import Base
from helm_storage.models import EmailDeepSeedQueueORM
from helm_storage.repositories.contracts import NewEmailDeepSeedQueueItem, NewEmailThread
from helm_storage.repositories.email_deep_seed_queue import SQLAlchemyEmailDeepSeedQueueRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_worker.jobs import email_deep_seed
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def test_email_deep_seed_worker_processes_pending_items(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-seed-worker")
        )
        queue = SQLAlchemyEmailDeepSeedQueueRepository(session)
        item, _created = queue.enqueue(
            NewEmailDeepSeedQueueItem(
                source_type="email_manual",
                provider_thread_id="thr-seed-worker",
                seed_reason="sender_signal",
                message_count=1,
                latest_received_at=thread.created_at,
                sample_subject="Interview request",
                from_addresses=("recruiter@example.com",),
                thread_payload=[
                    {
                        "provider_message_id": "msg-1",
                        "provider_thread_id": "thr-seed-worker",
                        "from_address": "recruiter@example.com",
                        "subject": "Interview request",
                        "body_text": "Body",
                        "received_at": "2026-01-02T08:00:00+00:00",
                        "normalized_at": "2026-01-02T08:01:00+00:00",
                        "source": "gmail",
                    }
                ],
            )
        )
        item_id = item.id

    runtime = email_deep_seed.build_helm_runtime(session_local)
    monkeypatch.setattr(email_deep_seed, "build_helm_runtime", lambda: runtime)

    email_deep_seed.run()

    with Session(engine) as session:
        refreshed = session.execute(
            select(EmailDeepSeedQueueORM).where(EmailDeepSeedQueueORM.id == item_id)
        ).scalar_one()

    assert refreshed.status == "completed"
    assert refreshed.attempts == 1
