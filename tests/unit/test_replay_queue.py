from helm_api.services import replay_service
from helm_observability import agent_runs as agent_run_observability
from helm_storage.db import Base
from helm_storage.models import AgentRunORM, ReplayQueueORM
from helm_storage.repositories.agent_runs import AgentRunStatus, SQLAlchemyAgentRunRepository
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

    replay_job.run()

    with Session(engine) as session:
        replay_row = session.execute(
            select(ReplayQueueORM).where(ReplayQueueORM.id == replay_item_id)
        ).scalar_one()
        run_rows = list(session.execute(select(AgentRunORM)).scalars().all())

    assert replay_row.status == AgentRunStatus.FAILED.value
    assert replay_row.attempts == 1
    assert replay_row.last_error is not None
    assert len(run_rows) == 1
    assert run_rows[0].status == AgentRunStatus.FAILED.value
