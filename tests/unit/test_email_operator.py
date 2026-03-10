
from email_agent.adapters import build_helm_runtime
from email_agent.operator import approve_draft, snooze_draft
from helm_storage.db import Base
from helm_storage.models import DraftTransitionAuditORM
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.contracts import NewActionProposal, NewEmailDraft, NewEmailThread
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def test_approve_draft_persists_transition_audit() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-approve-1")
        )
        proposal = SQLAlchemyActionProposalRepository(session).create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Reply with availability",
            )
        )
        draft = SQLAlchemyEmailDraftRepository(session).create(
            NewEmailDraft(
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                draft_body="Thanks, I am interested.",
                draft_subject="Re: Role",
                approval_status="pending_user",
            )
        )

    result = approve_draft(draft.id, runtime=build_helm_runtime(session_local))

    assert result.ok is True
    with Session(engine) as session:
        audits = list(session.execute(select(DraftTransitionAuditORM)).scalars().all())
    assert len(audits) == 1
    assert audits[0].action == "approve"
    assert audits[0].from_status == "pending_user"
    assert audits[0].to_status == "approved"
    assert audits[0].success is True


def test_snooze_draft_failure_persists_audit() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session(engine) as session:
        thread = SQLAlchemyEmailThreadRepository(session).create(
            NewEmailThread(provider_thread_id="thr-snooze-1")
        )
        proposal = SQLAlchemyActionProposalRepository(session).create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Reply with availability",
            )
        )
        draft = SQLAlchemyEmailDraftRepository(session).create(
            NewEmailDraft(
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                draft_body="Thanks, I am interested.",
                draft_subject="Re: Role",
                approval_status="approved",
            )
        )

    result = snooze_draft(draft.id, runtime=build_helm_runtime(session_local))

    assert result.ok is False
    with Session(engine) as session:
        audits = list(session.execute(select(DraftTransitionAuditORM)).scalars().all())
    assert len(audits) == 1
    assert audits[0].action == "snooze"
    assert audits[0].from_status == "approved"
    assert audits[0].to_status == "approved"
    assert audits[0].success is False
    assert audits[0].reason == "invalid_transition"
