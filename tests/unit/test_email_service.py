from email_agent import query as email_query
from helm_storage.db import Base
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.contracts import NewActionProposal, NewEmailDraft, NewEmailThread
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def test_email_service_lists_threads_proposals_and_drafts(monkeypatch) -> None:  # noqa: ANN001
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(email_query, "SessionLocal", session_local)

    with Session(engine) as session:
        thread_repo = SQLAlchemyEmailThreadRepository(session)
        proposal_repo = SQLAlchemyActionProposalRepository(session)
        draft_repo = SQLAlchemyEmailDraftRepository(session)

        thread = thread_repo.create(
            NewEmailThread(
                provider_thread_id="thr-api-1",
                business_state="waiting_on_user",
                visible_labels=("Action", "Urgent"),
                current_summary="Recruiter follow-up",
                latest_confidence_band="High",
                resurfacing_source="new_message",
                action_reason="reply_needed",
            )
        )
        proposal = proposal_repo.create(
            NewActionProposal(
                email_thread_id=thread.id,
                proposal_type="reply",
                rationale="Reply with availability",
                confidence_band="High",
            )
        )
        draft_repo.create(
            NewEmailDraft(
                email_thread_id=thread.id,
                action_proposal_id=proposal.id,
                draft_body="Thanks, I would be glad to connect.",
                draft_subject="Re: Interview availability",
            )
        )

    threads = email_query.list_email_threads()
    proposals = email_query.list_email_proposals()
    drafts = email_query.list_email_drafts()

    assert len(threads) == 1
    assert threads[0]["provider_thread_id"] == "thr-api-1"
    assert threads[0]["visible_labels"] == ["Action", "Urgent"]
    assert len(proposals) == 1
    assert proposals[0]["proposal_type"] == "reply"
    assert len(drafts) == 1
    assert drafts[0]["approval_status"] == "pending_user"
