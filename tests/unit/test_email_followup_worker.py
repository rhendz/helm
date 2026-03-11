from helm_storage.db import Base
from helm_storage.repositories.contracts import NewEmailThread
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_worker.jobs import email_followup_scan
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_email_followup_scan_worker_invokes_followup_scan(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session(engine) as session:
        SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(
                provider_thread_id="thr-followup-worker",
                business_state="waiting_on_other_party",
            )
        )

    runtime = email_followup_scan.build_email_agent_runtime(session_local)
    monkeypatch.setattr(email_followup_scan, "build_email_agent_runtime", lambda: runtime)
    observed: dict[str, int] = {}

    def fake_enqueue_stale_followups(*, runtime, now=None, limit=100):  # noqa: ANN001
        observed["limit"] = limit
        observed["threads"] = len(
            runtime.list_email_threads(business_state="waiting_on_other_party", limit=100)
        )
        return []

    monkeypatch.setattr(
        email_followup_scan,
        "enqueue_stale_followups",
        fake_enqueue_stale_followups,
    )

    email_followup_scan.run()

    assert observed == {"limit": 100, "threads": 1}
