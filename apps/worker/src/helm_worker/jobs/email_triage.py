from helm_connectors.gmail import pull_new_messages
from helm_observability.logging import get_logger
from helm_orchestration.email_flow import run_email_triage_workflow

logger = get_logger("helm_worker.jobs.email_triage")


def run() -> None:
    messages = pull_new_messages()
    logger.info("email_triage_job_tick", count=len(messages))
    for message in messages:
        result = run_email_triage_workflow(message)
        logger.info(
            "email_triage_scaffold_result",
            message_id=result.message_id,
            classification=result.classification,
            priority_score=result.priority_score,
            workflow_status=result.workflow_status,
        )
