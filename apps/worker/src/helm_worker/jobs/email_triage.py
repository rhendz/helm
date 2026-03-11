from email_agent.triage import process_inbound_email_message
from email_agent.types import EmailMessage
from helm_connectors.gmail import pull_new_messages_report
from helm_observability.logging import get_logger
from helm_runtime.email_agent import build_email_agent_runtime

logger = get_logger("helm_worker.jobs.email_triage")


def run() -> None:
    runtime = build_email_agent_runtime()
    report = pull_new_messages_report()
    logger.info(
        "email_triage_job_tick",
        count=len(report.messages),
        normalization_failures=report.failure_counts,
    )
    messages = report.messages
    for message in messages:
        result = process_inbound_email_message(
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
            trigger_family=result.trigger_family,
            classification=result.classification,
            priority_score=result.priority_score,
            workflow_status=result.workflow_status,
        )
