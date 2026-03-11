from datetime import UTC, datetime

from helm_api.services import replay_service
from helm_observability import agent_runs as agent_run_observability
from helm_storage.db import Base
from helm_storage.models import AgentRunORM, EmailMessageORM, ReplayQueueORM
from helm_storage.repositories.agent_runs import AgentRunStatus, SQLAlchemyAgentRunRepository
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.replay_queue import SQLAlchemyReplayQueueRepository
from helm_worker.jobs import replay as replay_job
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_enqueue_failed_agent_run_validation_and_dedupe(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    with Session(engine) as session:
        runs = SQLAlchemyAgentRunRepository(session)
        non_failed = runs.start_run(agent_name="a", source_type="worker", source_id="x")
        runs.mark_succeeded(non_failed.id)
        failed = runs.start_run(agent_name="b", source_type="worker", source_id="y")
        runs.mark_failed(failed.id, "boom")
        non_failed_id = non_failed.id
        failed_id = failed.id

    rejected = replay_service.enqueue_failed_agent_run(agent_run_id=non_failed_id)
    assert rejected["status"] == "rejected"
    assert rejected["reason"] == "agent_run_not_failed"

    first = replay_service.enqueue_failed_agent_run(agent_run_id=failed_id)
    second = replay_service.enqueue_failed_agent_run(agent_run_id=failed_id)
    assert first["status"] == "accepted"
    assert first["created"] is True
    assert second["status"] == "accepted"
    assert second["created"] is False
    assert first["replay_id"] == second["replay_id"]


def test_replay_worker_marks_failed_and_records_agent_run(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_job, "SessionLocal", session_local)
    monkeypatch.setattr(agent_run_observability, "SessionLocal", session_local)

    with Session(engine) as session:
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        replay_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=123,
            source_type="worker",
            source_id="scheduler",
        )
        replay_item_id = replay_item.id

    processed_count = replay_job.run()

    with Session(engine) as session:
        replay_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == replay_item_id)
        ).scalar_one()
        run_rows = list(session.execute(select(AgentRunORM)).scalars().all())

    assert replay_row.status == "pending"
    assert replay_row.attempts == 1
    assert replay_row.last_error is not None
    assert len(run_rows) == 1
    assert run_rows[0].status == AgentRunStatus.FAILED.value
    assert processed_count == 1


def test_replay_worker_dead_letters_after_repeated_failures(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_job, "SessionLocal", session_local)
    monkeypatch.setattr(agent_run_observability, "SessionLocal", session_local)

    with Session(engine) as session:
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        replay_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=123,
            source_type="worker",
            source_id="scheduler",
        )
        replay_item_id = replay_item.id

    replay_job.run()
    replay_job.run()
    replay_job.run()

    with Session(engine) as session:
        replay_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == replay_item_id)
        ).scalar_one()

    assert replay_row.status == "dead_lettered"
    assert replay_row.attempts == 3
    assert replay_row.last_error is not None


def test_reclaim_stale_processing_resets_items_to_pending() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        replay_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=444,
            source_type="worker",
            source_id="scheduler",
        )
        replay_repo.mark_processing(replay_item.id)
        row = replay_repo.get_by_id(replay_item.id)
        assert row is not None
        row.updated_at = datetime(2026, 3, 10, 0, 0, tzinfo=UTC)
        session.add(row)
        session.commit()

        reclaimed = replay_repo.reclaim_stale_processing(
            stale_before=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            limit=10,
        )

    assert [item.id for item in reclaimed] == [replay_item.id]

    with Session(engine) as session:
        replay_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == replay_item.id)
        ).scalar_one()

    assert replay_row.status == "pending"
    assert replay_row.attempts == 1


def test_replay_worker_reclaims_stale_processing_before_retry(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_job, "SessionLocal", session_local)
    monkeypatch.setattr(agent_run_observability, "SessionLocal", session_local)
    monkeypatch.setattr(
        replay_job,
        "_utcnow",
        lambda: datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
    )

    with Session(engine) as session:
        message_repo = SQLAlchemyEmailMessageRepository(session)
        message_repo.upsert_from_normalized(
            type(
                "Message",
                (),
                {
                    "provider_message_id": "msg-replay-stale",
                    "provider_thread_id": "thr-replay-stale",
                    "from_address": "sender@example.com",
                    "subject": "Replay stale",
                    "body_text": "Retry me",
                    "received_at": datetime(2026, 3, 10, 10, 0, tzinfo=UTC),
                    "normalized_at": datetime(2026, 3, 10, 10, 1, tzinfo=UTC),
                    "source": "gmail",
                },
            )(),
            direction="inbound",
        )
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        replay_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=555,
            source_type="email_message",
            source_id="msg-replay-stale",
        )
        replay_repo.mark_processing(replay_item.id)
        row = replay_repo.get_by_id(replay_item.id)
        assert row is not None
        row.updated_at = datetime(2026, 3, 10, 10, 30, tzinfo=UTC)
        session.add(row)
        session.commit()
        replay_item_id = replay_item.id

    monkeypatch.setattr(replay_job, "build_email_agent_runtime", lambda: object())
    seen: dict[str, str] = {}

    def fake_process_inbound_email_message(message, *, runtime):  # noqa: ANN001
        seen["provider_message_id"] = message.provider_message_id

    monkeypatch.setattr(
        replay_job,
        "process_inbound_email_message",
        fake_process_inbound_email_message,
    )

    processed_count = replay_job.run()

    with Session(engine) as session:
        replay_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == replay_item_id)
        ).scalar_one()

    assert seen == {"provider_message_id": "msg-replay-stale"}
    assert replay_row.status == "completed"
    assert replay_row.attempts == 2
    assert processed_count == 1


def test_replay_worker_replays_failed_email_triage_run(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_job, "SessionLocal", session_local)
    monkeypatch.setattr(agent_run_observability, "SessionLocal", session_local)

    with Session(engine) as session:
        message_repo = SQLAlchemyEmailMessageRepository(session)
        message_repo.upsert_from_normalized(
            type(
                "Message",
                (),
                {
                    "provider_message_id": "msg-replay-1",
                    "provider_thread_id": "thr-replay-1",
                    "from_address": "sender@example.com",
                    "subject": "Replay me",
                    "body_text": "Need another pass",
                    "received_at": datetime(2026, 3, 10, 18, 0, tzinfo=UTC),
                    "normalized_at": datetime(2026, 3, 10, 18, 1, tzinfo=UTC),
                    "source": "gmail",
                },
            )(),
            direction="inbound",
        )
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        replay_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=321,
            source_type="email_message",
            source_id="msg-replay-1",
        )
        replay_item_id = replay_item.id

    monkeypatch.setattr(
        replay_job,
        "build_email_agent_runtime",
        lambda: object(),
    )
    seen: dict[str, str] = {}

    def fake_process_inbound_email_message(message, *, runtime):  # noqa: ANN001
        seen["provider_message_id"] = message.provider_message_id

    monkeypatch.setattr(
        replay_job,
        "process_inbound_email_message",
        fake_process_inbound_email_message,
    )

    processed_count = replay_job.run()

    with Session(engine) as session:
        replay_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == replay_item_id)
        ).scalar_one()
        run_rows = list(session.execute(select(AgentRunORM)).scalars().all())
        message_row = session.execute(
            select(EmailMessageORM).where(EmailMessageORM.provider_message_id == "msg-replay-1")
        ).scalar_one()

    assert seen == {"provider_message_id": "msg-replay-1"}
    assert replay_row.status == "completed"
    assert replay_row.attempts == 1
    assert run_rows[0].status == AgentRunStatus.SUCCEEDED.value
    assert message_row.provider_thread_id == "thr-replay-1"
    assert processed_count == 1


def test_replay_worker_respects_explicit_limit(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_job, "SessionLocal", session_local)
    monkeypatch.setattr(agent_run_observability, "SessionLocal", session_local)

    with Session(engine) as session:
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        first, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=701,
            source_type="worker",
            source_id="scheduler-1",
        )
        second, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=702,
            source_type="worker",
            source_id="scheduler-2",
        )
        first_id = first.id
        second_id = second.id

    processed_count = replay_job.run(limit=1)

    with Session(engine) as session:
        first_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == first_id)
        ).scalar_one()
        second_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == second_id)
        ).scalar_one()

    assert processed_count == 1
    assert first_row.attempts == 1
    assert second_row.attempts == 0


def test_reprocess_failed_runs_requires_bounded_scope(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    rejected = replay_service.reprocess_failed_runs(
        source_type=None,
        source_id=None,
        since_hours=None,
        limit=20,
        dry_run=True,
    )
    assert rejected["status"] == "rejected"
    assert rejected["reason"] == "scope_required"


def test_reprocess_failed_runs_dry_run_and_execute(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    with Session(engine) as session:
        runs = SQLAlchemyAgentRunRepository(session)
        first = runs.start_run(agent_name="a", source_type="worker", source_id="scheduler")
        runs.mark_failed(first.id, "x")
        second = runs.start_run(agent_name="b", source_type="worker", source_id="scheduler")
        runs.mark_failed(second.id, "y")

    dry_run = replay_service.reprocess_failed_runs(
        source_type="worker",
        source_id="scheduler",
        since_hours=24,
        limit=20,
        dry_run=True,
    )
    assert dry_run["status"] == "accepted"
    assert dry_run["dry_run"] is True
    assert dry_run["matched_count"] == 2

    execute = replay_service.reprocess_failed_runs(
        source_type="worker",
        source_id="scheduler",
        since_hours=24,
        limit=20,
        dry_run=False,
    )
    assert execute["status"] == "accepted"
    assert execute["dry_run"] is False
    assert execute["matched_count"] == 2
    assert execute["enqueued_count"] == 2
    assert execute["skipped_count"] == 0


def test_list_replay_items_filters_recent_status(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    with Session(engine) as session:
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        pending_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=1,
            source_type="worker",
            source_id="scheduler-1",
        )
        dead_lettered_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=2,
            source_type="worker",
            source_id="scheduler-2",
        )
        replay_repo.mark_processing(dead_lettered_item.id)
        replay_repo.mark_failed(dead_lettered_item.id, error_message="boom", max_attempts=1)
        pending_item_id = pending_item.id
        dead_lettered_item_id = dead_lettered_item.id

    dead_lettered = replay_service.list_replay_items(status="dead_lettered", limit=10)

    assert [row["id"] for row in dead_lettered] == [dead_lettered_item_id]
    assert dead_lettered[0]["status"] == "dead_lettered"

    recent = replay_service.list_replay_items(status=None, limit=10)

    assert [row["id"] for row in recent] == [dead_lettered_item_id, pending_item_id]
    assert recent[0]["attempts"] == 1


def test_requeue_replay_item_resets_dead_lettered_row(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    with Session(engine) as session:
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        replay_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=7,
            source_type="worker",
            source_id="scheduler",
        )
        replay_repo.mark_processing(replay_item.id)
        replay_repo.mark_failed(replay_item.id, error_message="boom", max_attempts=1)
        replay_item_id = replay_item.id

    result = replay_service.requeue_replay_item(replay_id=replay_item_id)

    assert result == {"status": "accepted", "replay_id": replay_item_id, "reason": None}

    with Session(engine) as session:
        replay_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == replay_item_id)
        ).scalar_one()

    assert replay_row.status == "pending"
    assert replay_row.attempts == 0
    assert replay_row.last_error is None


def test_requeue_replay_item_rejects_pending_and_missing(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(replay_service, "SessionLocal", session_local)

    with Session(engine) as session:
        replay_repo = SQLAlchemyReplayQueueRepository(session)
        replay_item, _created = replay_repo.enqueue_from_failed_run(
            agent_run_id=8,
            source_type="worker",
            source_id="scheduler",
        )
        replay_item_id = replay_item.id

    pending = replay_service.requeue_replay_item(replay_id=replay_item_id)
    missing = replay_service.requeue_replay_item(replay_id=999999)

    assert pending == {
        "status": "rejected",
        "replay_id": replay_item_id,
        "reason": "replay_not_requeueable",
    }
    assert missing == {
        "status": "rejected",
        "replay_id": 999999,
        "reason": "replay_not_found",
    }
