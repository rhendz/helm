from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime
from email_agent.triage import EmailTriageWorkflowResult, run_email_triage_workflow
from email_agent.types import EmailMessage


@dataclass(frozen=True, slots=True)
class ThreadReprocessResult:
    status: str
    thread_id: int
    dry_run: bool
    found: bool
    reprocessed: bool
    reason: str | None = None
    workflow_status: str | None = None


def reprocess_email_thread(
    *,
    thread_id: int,
    dry_run: bool,
    runtime: EmailAgentRuntime,
) -> ThreadReprocessResult:
    try:
        detail = runtime.get_email_thread_detail(thread_id=thread_id)
        if detail is None:
            return ThreadReprocessResult(
                status="not_found",
                thread_id=thread_id,
                dry_run=dry_run,
                found=False,
                reprocessed=False,
                reason="thread_not_found",
            )

        latest_message = runtime.get_latest_inbound_email_message(thread_id=thread_id)
        if latest_message is None:
            return ThreadReprocessResult(
                status="rejected",
                thread_id=thread_id,
                dry_run=dry_run,
                found=True,
                reprocessed=False,
                reason="no_inbound_message",
            )

        if dry_run:
            return ThreadReprocessResult(
                status="accepted",
                thread_id=thread_id,
                dry_run=True,
                found=True,
                reprocessed=False,
            )

        result = run_email_triage_workflow(
            EmailMessage(**latest_message),
            runtime=runtime,
            trigger_family="manual_thread_reprocess",
        )
    except SQLAlchemyError:
        return ThreadReprocessResult(
            status="unavailable",
            thread_id=thread_id,
            dry_run=dry_run,
            found=False,
            reprocessed=False,
            reason="storage_unavailable",
        )

    return _completed_reprocess_result(thread_id=thread_id, workflow=result)


def _completed_reprocess_result(
    *,
    thread_id: int,
    workflow: EmailTriageWorkflowResult,
) -> ThreadReprocessResult:
    return ThreadReprocessResult(
        status="accepted",
        thread_id=thread_id,
        dry_run=False,
        found=True,
        reprocessed=True,
        workflow_status=workflow.workflow_status,
    )
