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
    limit: int = 20,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_email_proposals(limit=limit)
    except SQLAlchemyError:
        return []


def list_email_drafts(
    *,
    limit: int = 20,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_email_drafts(limit=limit)
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
