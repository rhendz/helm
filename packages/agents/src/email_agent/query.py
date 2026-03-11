from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime


def list_email_threads(
    *,
    business_state: str | None = None,
    label: str | None = None,
    limit: int = 20,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_email_threads(
            business_state=business_state,
            label=label,
            limit=limit,
        )
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


def list_classification_artifacts_for_thread(
    *,
    thread_id: int,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_classification_artifacts_for_thread(thread_id=thread_id)
    except SQLAlchemyError:
        return []


def list_classification_artifacts_for_message(
    *,
    message_id: int,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_classification_artifacts_for_message(message_id=message_id)
    except SQLAlchemyError:
        return []


def list_draft_reasoning_artifacts_for_draft(
    *,
    draft_id: int,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_draft_reasoning_artifacts_for_draft(draft_id=draft_id)
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


def get_email_draft_detail(
    *,
    draft_id: int,
    runtime: EmailAgentRuntime,
) -> dict | None:
    try:
        draft = runtime.get_email_draft_by_id(draft_id)
        if draft is None:
            return None
        return {
            **draft,
            "transition_audits": runtime.list_draft_transition_audits_for_draft(draft_id=draft_id),
            "reasoning_artifacts": runtime.list_draft_reasoning_artifacts_for_draft(
                draft_id=draft_id
            ),
        }
    except SQLAlchemyError:
        return None


def list_draft_transition_audits_for_draft(
    *,
    draft_id: int,
    runtime: EmailAgentRuntime,
) -> list[dict]:
    try:
        return runtime.list_draft_transition_audits_for_draft(draft_id=draft_id)
    except SQLAlchemyError:
        return []
