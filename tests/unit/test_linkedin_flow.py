from datetime import UTC, datetime

from helm_orchestration.linkedin_flow import run_linkedin_triage_workflow
from helm_storage.db import Base
from helm_storage.models import DraftReplyORM, LinkedInMessageORM, OpportunityORM
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def test_linkedin_triage_scaffold_persists_opportunities_and_drafts_idempotently() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session(engine) as session:
        session.add(
            LinkedInMessageORM(
                provider_message_id="li-msg-100",
                thread_id="li-thread-100",
                sender_name="Recruiter",
                body_text="Open to discuss a role?",
                received_at=datetime.now(tz=UTC),
            )
        )
        session.commit()

    first = run_linkedin_triage_workflow(session_factory=session_local)
    second = run_linkedin_triage_workflow(session_factory=session_local)

    assert first.scanned_messages == 1
    assert first.created_opportunities == 1
    assert first.created_drafts == 1
    assert second.created_opportunities == 0
    assert second.created_drafts == 0

    with Session(engine) as session:
        opportunities = list(session.execute(select(OpportunityORM)).scalars().all())
        drafts = list(session.execute(select(DraftReplyORM)).scalars().all())

    assert len(opportunities) == 1
    assert len(drafts) == 1
    assert drafts[0].channel_type == "linkedin"
