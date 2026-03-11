from email_agent.followup import enqueue_stale_followups
from helm_observability.logging import get_logger
from helm_runtime.email_agent import build_email_agent_runtime

logger = get_logger("helm_worker.jobs.email_followup_scan")


def run() -> None:
    results = enqueue_stale_followups(runtime=build_email_agent_runtime(), limit=100)
    logger.info(
        "email_followup_scan_job_tick",
        processed_count=len(results),
        enqueued_count=sum(1 for item in results if item.action == "enqueued"),
        skipped_count=sum(1 for item in results if item.action == "skipped"),
        statuses=[item.action for item in results],
    )
