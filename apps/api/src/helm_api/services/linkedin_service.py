from collections.abc import Mapping

from helm_connectors.linkedin import pull_new_events_report
from helm_observability.agent_runs import record_agent_run
from helm_storage.db import SessionLocal
from helm_storage.repositories.linkedin_messages import SQLAlchemyLinkedInMessageRepository
from sqlalchemy.exc import SQLAlchemyError


def ingest_manual_linkedin_events(*, source_type: str, events: list[Mapping[str, object]]) -> dict:
    report = pull_new_events_report(manual_payload=[dict(item) for item in events])
    normalized_events = report.events
    persisted = False
    message_count = 0
    thread_ids: set[str] = set()

    def _execute() -> None:
        nonlocal persisted, message_count
        with SessionLocal() as session:
            repository = SQLAlchemyLinkedInMessageRepository(session)
            for message in normalized_events:
                repository.upsert_from_normalized(message)
                message_count += 1
                thread_ids.add(message.provider_thread_id)
            persisted = True

    try:
        record_agent_run(
            agent_name="linkedin_manual_ingest",
            source_type=source_type,
            source_id=f"count:{len(normalized_events)}",
            execute=_execute,
        )
    except SQLAlchemyError:
        persisted = False

    return {
        "status": "accepted",
        "source_type": source_type,
        "event_count": len(normalized_events),
        "persisted": persisted,
        "message_count": message_count,
        "thread_count": len(thread_ids),
        "failed_event_count": sum(report.failure_counts.values()),
        "normalization_failures": report.failure_counts,
    }
