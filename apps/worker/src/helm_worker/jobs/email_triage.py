from helm_connectors.gmail import pull_new_messages
from helm_observability.logging import get_logger


logger = get_logger("helm_worker.jobs.email_triage")


def run() -> None:
    messages = pull_new_messages()
    logger.info("email_triage_job_tick", count=len(messages))
    # TODO(v1-phase2): dispatch each message through orchestration.email_flow graph.
