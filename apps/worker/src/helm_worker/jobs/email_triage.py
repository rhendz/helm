from email_agent.triage import run_email_triage_workflow
from helm_connectors.gmail import pull_new_messages_report
from helm_observability.logging import get_logger

logger = get_logger("helm_worker.jobs.email_triage")


def run() -> None:
    report = pull_new_messages_report()
    logger.info(
        "email_triage_job_tick",
        count=len(report.messages),
        normalization_failures=report.failure_counts,
    )
    messages = report.messages
    for message in messages:
        result = run_email_triage_workflow(message)
        logger.info(
            "email_triage_scaffold_result",
            message_id=result.message_id,
            classification=result.classification,
            priority_score=result.priority_score,
            workflow_status=result.workflow_status,
        )
