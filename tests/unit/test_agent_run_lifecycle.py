from helm_observability import agent_runs as agent_run_observability
from helm_storage.db import Base
from helm_storage.models import AgentRunORM
from helm_storage.repositories.agent_runs import AgentRunStatus, SQLAlchemyAgentRunRepository
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_agent_run_repository_terminal_transition_guarantee() -> None:
    with _session() as session:
        repository = SQLAlchemyAgentRunRepository(session)
        run = repository.start_run(agent_name="test", source_type="unit", source_id="1")
        assert run.status == AgentRunStatus.RUNNING.value

        repository.mark_failed(run.id, "boom")
        failed = repository.get_by_id(run.id)
        assert failed is not None
        assert failed.status == AgentRunStatus.FAILED.value
        assert failed.completed_at is not None

        # Terminal run must not transition again.
        repository.mark_succeeded(run.id)
        still_failed = repository.get_by_id(run.id)
        assert still_failed is not None
        assert still_failed.status == AgentRunStatus.FAILED.value


def test_record_agent_run_persists_terminal_states(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(agent_run_observability, "SessionLocal", session_local)

    agent_run_observability.record_agent_run(
        agent_name="test_success",
        source_type="unit",
        source_id="ok",
        execute=lambda: None,
    )

    def _failing_execute() -> None:
        raise RuntimeError("expected failure")

    try:
        agent_run_observability.record_agent_run(
            agent_name="test_failure",
            source_type="unit",
            source_id="fail",
            execute=_failing_execute,
        )
    except RuntimeError:
        pass

    with Session(engine) as session:
        rows = list(session.execute(select(AgentRunORM)).scalars().all())

    assert len(rows) == 2
    statuses = sorted(row.status for row in rows)
    assert statuses == [AgentRunStatus.FAILED.value, AgentRunStatus.SUCCEEDED.value]
    assert all(row.completed_at is not None for row in rows)
