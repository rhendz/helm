from email_agent.adapters import build_helm_runtime
from email_agent.triage import run_email_triage_workflow
from email_agent.types import EmailMessage
from helm_connectors.gmail import pull_new_messages_report
from helm_observability.logging import get_logger

logger = get_logger("helm_worker.jobs.email_triage")


def run() -> None:
    runtime = build_helm_runtime()
    report = pull_new_messages_report()
    logger.info(
        "email_triage_job_tick",
        count=len(report.messages),
        normalization_failures=report.failure_counts,
    )
    messages = report.messages
    for message in messages:
        result = run_email_triage_workflow(
            EmailMessage(
                provider_message_id=message.provider_message_id,
                provider_thread_id=message.provider_thread_id,
                from_address=message.from_address,
                subject=message.subject,
                body_text=message.body_text,
                received_at=message.received_at,
                normalized_at=message.normalized_at,
                source=message.source,
            ),
            runtime=runtime,
        )
        logger.info(
            "email_triage_scaffold_result",
            message_id=result.message_id,
            classification=result.classification,
            priority_score=result.priority_score,
            workflow_status=result.workflow_status,
        )
