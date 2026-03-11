from email_agent.send_recovery import run_pending_send_retries
from helm_observability.logging import get_logger
from helm_runtime.email_agent import build_email_agent_runtime

logger = get_logger("helm_worker.jobs.email_send_recovery")


def run() -> None:
    runtime = build_email_agent_runtime()
    results = run_pending_send_retries(runtime=runtime, limit=20)
    logger.info(
        "email_send_recovery_job_tick",
        processed_count=len(results),
        retried_count=sum(1 for item in results if item.action == "retried"),
        skipped_count=sum(1 for item in results if item.action == "skipped"),
        statuses=[item.action for item in results],
    )
