from helm_storage.db import SessionLocal
from helm_storage.repositories.agent_runs import SQLAlchemyAgentRunRepository
from sqlalchemy.exc import SQLAlchemyError


def get_runtime_status() -> dict[str, str | int]:
    failed_runs = 0
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyAgentRunRepository(session)
            failed_runs = len(repository.list_recent_failed(limit=10))
    except SQLAlchemyError:
        failed_runs = 0

    return {"service": "api", "state": "bootstrapped", "recent_failed_runs": failed_runs}


def list_recent_failed_agent_runs(limit: int = 20) -> list[dict]:
    try:
        with SessionLocal() as session:
            repository = SQLAlchemyAgentRunRepository(session)
            records = repository.list_recent_failed(limit=limit)
            return [
                {
                    "id": run.id,
                    "agent_name": run.agent_name,
                    "source_type": run.source_type,
                    "source_id": run.source_id,
                    "status": run.status,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                    "error_message": run.error_message,
                }
                for run in records
            ]
    except SQLAlchemyError:
        return []
