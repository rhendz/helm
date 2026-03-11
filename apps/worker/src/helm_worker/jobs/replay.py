from email_agent.triage import process_inbound_email_message
from email_agent.types import EmailMessage
from helm_observability.agent_runs import record_agent_run
from helm_observability.logging import get_logger
from helm_runtime.email_agent import build_email_agent_runtime
from helm_storage.db import SessionLocal
from helm_storage.repositories.email_messages import SQLAlchemyEmailMessageRepository
from helm_storage.repositories.replay_queue import SQLAlchemyReplayQueueRepository
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger("helm_worker.jobs.replay")
MAX_REPLAY_ATTEMPTS = 3


def run() -> None:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyReplayQueueRepository(session)
            pending = repository.list_pending(limit=10)
            pending_ids = [item.id for item in pending]
    except SQLAlchemyError:
        logger.warning("replay_queue_query_failed")
        return

    for item_id in pending_ids:
        _process_replay_item(item_id=item_id)


def _process_replay_item(*, item_id: int) -> None:
    source = None
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyReplayQueueRepository(session)
            item = repository.mark_processing(item_id)
            if item is None:
                return
            if item.status != "processing":
                return
            source = (item.source_type, item.source_id)
    except SQLAlchemyError:
        logger.warning("replay_queue_mark_processing_failed", item_id=item_id)
        return

    if source is None:
        return
    source_type, source_id = source

    try:
        record_agent_run(
            agent_name="replay_worker",
            source_type=source_type,
            source_id=source_id,
            execute=lambda: _execute_replay(source_type=source_type, source_id=source_id),
        )
    except Exception as exc:  # noqa: BLE001
        with SessionLocal() as session:
            repository = SQLAlchemyReplayQueueRepository(session)
            repository.mark_failed(
                item_id,
                error_message=str(exc),
                max_attempts=MAX_REPLAY_ATTEMPTS,
            )
        return

    with SessionLocal() as session:
        repository = SQLAlchemyReplayQueueRepository(session)
        repository.mark_completed(item_id)


def _execute_replay(*, source_type: str, source_id: str | None) -> None:
    logger.info("replay_item_received", source_type=source_type, source_id=source_id)
    if source_type == "email_message":
        _replay_email_message(source_id=source_id)
        return
    raise NotImplementedError(f"Unsupported replay source_type: {source_type}")


def _replay_email_message(*, source_id: str | None) -> None:
    provider_message_id = str(source_id or "").strip()
    if not provider_message_id:
        raise ValueError("Replay email_message source_id is required.")

    with SessionLocal() as session:
        record = SQLAlchemyEmailMessageRepository(session).get_by_provider_message_id(
            provider_message_id
        )

    if record is None:
        raise ValueError(f"Email message {provider_message_id} not found.")
    if record.direction != "inbound":
        raise ValueError(f"Email message {provider_message_id} is not inbound.")

    process_inbound_email_message(
        EmailMessage(
            provider_message_id=record.provider_message_id,
            provider_thread_id=record.provider_thread_id,
            from_address=record.from_address or "",
            subject=record.subject or "",
            body_text=record.body_text or "",
            received_at=record.received_at,
            normalized_at=record.normalized_at,
            source=record.source,
        ),
        runtime=build_email_agent_runtime(),
    )
