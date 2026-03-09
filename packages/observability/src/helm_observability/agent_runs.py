from collections.abc import Callable

from helm_storage.db import SessionLocal
from helm_storage.repositories.agent_runs import SQLAlchemyAgentRunRepository
from sqlalchemy.exc import SQLAlchemyError


def record_agent_run(
    *,
    agent_name: str,
    source_type: str,
    source_id: str | None,
    execute: Callable[[], None],
) -> None:
    run_id: int | None = None

    try:
        with SessionLocal() as session:
            repository = SQLAlchemyAgentRunRepository(session)
            run = repository.start_run(
                agent_name=agent_name,
                source_type=source_type,
                source_id=source_id,
            )
            run_id = run.id
    except SQLAlchemyError:
        run_id = None

    try:
        execute()
    except Exception as exc:  # noqa: BLE001
        _mark_failure(run_id=run_id, error_message=str(exc))
        raise

    _mark_success(run_id=run_id)


def _mark_success(*, run_id: int | None) -> None:
    if run_id is None:
        return
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyAgentRunRepository(session)
            repository.mark_succeeded(run_id)
    except SQLAlchemyError:
        return


def _mark_failure(*, run_id: int | None, error_message: str) -> None:
    if run_id is None:
        return
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyAgentRunRepository(session)
            repository.mark_failed(run_id, error_message)
    except SQLAlchemyError:
        return
