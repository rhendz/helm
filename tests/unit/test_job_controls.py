from helm_api.services import status_service
from helm_storage.db import Base
from helm_storage.repositories.job_controls import SQLAlchemyJobControlRepository
from helm_worker import main as worker_main
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_worker_run_once_respects_paused_job(monkeypatch) -> None:  # noqa: ANN001
    executed: list[str] = []
    monkeypatch.setattr(worker_main, "is_job_paused", lambda name: name == "digest")
    monkeypatch.setattr(
        worker_main,
        "record_agent_run",
        lambda *, agent_name, source_type, source_id, execute: (
            executed.append(agent_name) or execute()
        ),
    )

    jobs = {
        "email_triage": lambda: None,
        "digest": lambda: None,
    }
    worker_main.run_once(jobs=jobs)
    assert executed == ["email_triage"]


def test_status_includes_paused_jobs(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(status_service, "SessionLocal", session_local)

    with Session(engine) as session:
        repository = SQLAlchemyJobControlRepository(session)
        repository.set_paused(job_name="digest", paused=True)
        repository.set_paused(job_name="email_triage", paused=False)

    status = status_service.get_runtime_status()
    assert "digest" in status["paused_jobs"]
    assert "email_triage" not in status["paused_jobs"]
