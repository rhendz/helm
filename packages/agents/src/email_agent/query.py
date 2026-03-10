from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime


def list_email_threads(
    *,
    limit: int = 20,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_email_threads(limit=limit)
    except SQLAlchemyError:
        return []


def list_email_proposals(
    *,
    status: str | None = None,
    proposal_type: str | None = None,
    limit: int = 20,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_email_proposals(
            status=status,
            proposal_type=proposal_type,
            limit=limit,
        )
    except SQLAlchemyError:
        return []


def list_email_drafts(
    *,
    status: str | None = None,
    approval_status: str | None = None,
    limit: int = 20,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_email_drafts(
            status=status,
            approval_status=approval_status,
            limit=limit,
        )
    except SQLAlchemyError:
        return []


def get_email_thread_detail(
    *,
    thread_id: int,
    runtime: EmailAgentRuntime,
) -> dict | None:
    try:
        return runtime.get_email_thread_detail(thread_id=thread_id)
    except SQLAlchemyError:
        return None
