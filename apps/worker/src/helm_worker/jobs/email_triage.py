from helm_connectors.gmail import pull_new_messages
from helm_observability.logging import get_logger
from helm_orchestration.email_flow import EmailTriageState, run_email_triage_workflow

logger = get_logger("helm_worker.jobs.email_triage")


def run() -> None:
    messages = pull_new_messages()
    logger.info("email_triage_job_tick", count=len(messages))
    for message in messages:
        state = EmailTriageState(
            provider_message_id=str(message.get("provider_message_id") or ""),
            provider_thread_id=str(message.get("provider_thread_id") or ""),
        )
        result = run_email_triage_workflow(state)
        logger.info(
            "email_triage_message_processed",
            provider_message_id=result.provider_message_id,
            step=result.step.value,
            handoff_count=len(result.handoffs),
        )
    # TODO(rhe-15): persist workflow checkpoints and failures for retry/reprocessing.
