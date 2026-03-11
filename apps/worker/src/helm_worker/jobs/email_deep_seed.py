from email_agent.adapters import build_helm_runtime
from email_agent.seed import run_pending_deep_seed_queue
from helm_observability.logging import get_logger

logger = get_logger("helm_worker.jobs.email_deep_seed")


def run() -> None:
    runtime = build_helm_runtime()
    results = run_pending_deep_seed_queue(runtime=runtime, limit=10)
    logger.info(
        "email_deep_seed_job_tick",
        processed_count=len(results),
        statuses=[item["status"] for item in results],
    )
