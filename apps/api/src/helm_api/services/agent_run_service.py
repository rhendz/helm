from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from helm_observability.logging import get_logger
from helm_storage.db import SessionLocal
from helm_storage.repositories.agent_runs import AgentRunCreate, SQLAlchemyAgentRunRepository

logger = get_logger("helm_api.services.agent_runs")
_MAX_ERROR_MESSAGE = 512


def _as_iso(ts: datetime | None) -> str | None:
    return ts.isoformat() if ts else None


def _sanitize_error(error: Exception) -> str:
    # Keep payloads small and avoid leaking sensitive content in raw exceptions.
    return f"{type(error).__name__}: {str(error)[:_MAX_ERROR_MESSAGE]}"


def serialize_agent_run(run: Any) -> dict[str, Any]:
    return {
        "id": run.id,
        "agent_name": run.agent_name,
        "source_type": run.source_type,
        "source_id": run.source_id,
        "status": run.status,
        "started_at": _as_iso(run.started_at),
        "completed_at": _as_iso(run.completed_at),
        "error_message": run.error_message,
    }


def create_agent_run(*, agent_name: str, source_type: str | None, source_id: str | None) -> int | None:
    try:
        with SessionLocal() as session:
            repo = SQLAlchemyAgentRunRepository(session)
            run = repo.create(
                AgentRunCreate(agent_name=agent_name, source_type=source_type, source_id=source_id)
            )
            return run.id
    except SQLAlchemyError as exc:
        logger.warning("agent_run_create_failed", agent_name=agent_name, error_type=type(exc).__name__)
        return None


def mark_agent_run_success(run_id: int | None) -> None:
    if run_id is None:
        return
    try:
        with SessionLocal() as session:
            repo = SQLAlchemyAgentRunRepository(session)
            repo.mark_succeeded(run_id)
    except SQLAlchemyError as exc:
        logger.warning("agent_run_success_mark_failed", run_id=run_id, error_type=type(exc).__name__)


def mark_agent_run_failure(run_id: int | None, *, error: Exception) -> None:
    if run_id is None:
        return
    try:
        with SessionLocal() as session:
            repo = SQLAlchemyAgentRunRepository(session)
            repo.mark_failed(run_id, error_message=_sanitize_error(error))
    except SQLAlchemyError as exc:
        logger.warning("agent_run_failure_mark_failed", run_id=run_id, error_type=type(exc).__name__)


def list_recent_agent_runs(*, limit: int = 20, status: str | None = None) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            repo = SQLAlchemyAgentRunRepository(session)
            items = [serialize_agent_run(run) for run in repo.list_recent(limit=limit, status=status)]
            return {"items": items, "storage": "ok"}
    except SQLAlchemyError as exc:
        logger.warning("agent_runs_query_failed", error_type=type(exc).__name__)
        return {"items": [], "storage": "unavailable"}


def get_agent_run(run_id: int) -> dict[str, Any] | None:
    try:
        with SessionLocal() as session:
            repo = SQLAlchemyAgentRunRepository(session)
            run = repo.get_by_id(run_id)
            return None if run is None else serialize_agent_run(run)
    except SQLAlchemyError as exc:
        logger.warning("agent_run_get_failed", run_id=run_id, error_type=type(exc).__name__)
        return None
