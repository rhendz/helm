from helm_connectors.gmail import pull_changed_messages_report
from helm_observability.logging import get_logger
from helm_runtime.email_agent import build_email_agent_runtime
from helm_worker.jobs.email_message_ingest import process_inbound_messages

logger = get_logger("helm_worker.jobs.email_triage")


def run() -> None:
    runtime = build_email_agent_runtime()
    config = runtime.get_email_agent_config()
    report = pull_changed_messages_report(last_history_cursor=config.last_history_cursor)
    logger.info(
        "email_triage_job_tick",
        count=len(report.messages),
        normalization_failures=report.failure_counts,
        mode=report.mode,
        last_history_cursor=config.last_history_cursor,
        next_history_cursor=report.next_history_cursor,
    )

    ingest_report = process_inbound_messages(runtime=runtime, messages=report.messages)
    if (
        report.next_history_cursor is not None
        and report.next_history_cursor != config.last_history_cursor
    ):
        runtime.update_email_agent_config(last_history_cursor=report.next_history_cursor)

    logger.info(
        "email_triage_job_completed",
        processed_count=ingest_report.processed_count,
        skipped_count=ingest_report.skipped_count,
        next_history_cursor=report.next_history_cursor,
    )
