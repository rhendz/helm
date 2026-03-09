from helm_observability.agent_runs import record_agent_run
from helm_observability.logging import get_logger
from helm_storage.db import SessionLocal
from helm_storage.repositories.replay_queue import SQLAlchemyReplayQueueRepository
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger("helm_worker.jobs.replay")


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
            repository.mark_failed(item_id, error_message=str(exc))
        return

    with SessionLocal() as session:
        repository = SQLAlchemyReplayQueueRepository(session)
        repository.mark_completed(item_id)


def _execute_replay(*, source_type: str, source_id: str | None) -> None:
    logger.info("replay_item_received", source_type=source_type, source_id=source_id)
    raise NotImplementedError("replay execution scaffold only; handler not implemented yet")
