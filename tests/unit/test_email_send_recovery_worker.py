from datetime import UTC, datetime

from helm_runtime.email_agent import build_email_agent_runtime
from helm_storage.db import Base
from helm_storage.repositories.contracts import NewEmailDraft, NewEmailThread
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from helm_worker.jobs import email_send_recovery
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_email_send_recovery_worker_processes_retry_candidates(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-worker-retry")
        )
        draft = SQLAlchemyEmailDraftRepository(session).create(
            NewEmailDraft(
                email_thread_id=thread.id,
                draft_body="Recover this send",
                approval_status="approved",
                status="send_failed",
            )
        )
        runtime = build_email_agent_runtime(session_local)
        attempt = runtime.create_send_attempt(
            draft_id=draft.id,
            email_thread_id=thread.id,
            attempt_number=1,
            started_at=datetime(2026, 3, 10, 19, 0, tzinfo=UTC),
        )
        runtime.complete_send_attempt(
            attempt_id=attempt.id,
            status="failed",
            completed_at=datetime(2026, 3, 10, 19, 1, tzinfo=UTC),
            failure_class="timeout",
            failure_message="Timed out",
        )

    runtime = email_send_recovery.build_email_agent_runtime(session_local)
    monkeypatch.setattr(email_send_recovery, "build_email_agent_runtime", lambda: runtime)
    observed: dict[str, int] = {}

    def fake_run_pending_send_retries(*, runtime, limit=20):  # noqa: ANN001
        observed["limit"] = limit
        drafts = runtime.list_email_drafts(
            status="send_failed",
            approval_status="approved",
            limit=20,
        )
        observed["drafts"] = len(drafts)
        return []

    monkeypatch.setattr(
        email_send_recovery,
        "run_pending_send_retries",
        fake_run_pending_send_retries,
    )

    email_send_recovery.run()

    assert observed == {"limit": 20, "drafts": 1}
