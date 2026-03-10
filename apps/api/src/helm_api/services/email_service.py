from helm_storage.db import SessionLocal
from helm_storage.repositories.action_proposals import SQLAlchemyActionProposalRepository
from helm_storage.repositories.email_drafts import SQLAlchemyEmailDraftRepository
from helm_storage.repositories.email_threads import SQLAlchemyEmailThreadRepository
from sqlalchemy.exc import SQLAlchemyError


def list_email_threads(*, limit: int = 20) -> list[dict]:
    try:
        with SessionLocal() as session:
            records = SQLAlchemyEmailThreadRepository(session).list_recent(limit=limit)
            return [
                {
                    "id": thread.id,
                    "provider_thread_id": thread.provider_thread_id,
                    "business_state": thread.business_state,
                    "visible_labels": _split_labels(thread.visible_labels),
                    "current_summary": thread.current_summary,
                    "latest_confidence_band": thread.latest_confidence_band,
                    "resurfacing_source": thread.resurfacing_source,
                    "action_reason": thread.action_reason,
                }
                for thread in records
            ]
    except SQLAlchemyError:
        return []


def list_email_proposals(*, limit: int = 20) -> list[dict]:
    try:
        with SessionLocal() as session:
            records = SQLAlchemyActionProposalRepository(session).list_recent(limit=limit)
            return [
                {
                    "id": proposal.id,
                    "email_thread_id": proposal.email_thread_id,
                    "proposal_type": proposal.proposal_type,
                    "status": proposal.status,
                    "confidence_band": proposal.confidence_band,
                    "rationale": proposal.rationale,
                }
                for proposal in records
            ]
    except SQLAlchemyError:
        return []


def list_email_drafts(*, limit: int = 20) -> list[dict]:
    try:
        with SessionLocal() as session:
            records = SQLAlchemyEmailDraftRepository(session).list_recent(limit=limit)
            return [
                {
                    "id": draft.id,
                    "email_thread_id": draft.email_thread_id,
                    "action_proposal_id": draft.action_proposal_id,
                    "status": draft.status,
                    "approval_status": draft.approval_status,
                    "preview": draft.draft_body[:120],
                    "draft_subject": draft.draft_subject,
                }
                for draft in records
            ]
    except SQLAlchemyError:
        return []


def _split_labels(value: str) -> list[str]:
    if not value:
        return []
    return [label for label in value.split(",") if label]
