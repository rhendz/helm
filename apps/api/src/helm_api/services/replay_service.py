from helm_storage.db import SessionLocal
from helm_storage.repositories.agent_runs import AgentRunStatus, SQLAlchemyAgentRunRepository
from helm_storage.repositories.replay_queue import SQLAlchemyReplayQueueRepository
from sqlalchemy.exc import SQLAlchemyError


def enqueue_failed_agent_run(*, agent_run_id: int) -> dict[str, object]:
    try:
        with SessionLocal() as session:
            run_repository = SQLAlchemyAgentRunRepository(session)
            replay_repository = SQLAlchemyReplayQueueRepository(session)

            run = run_repository.get_by_id(agent_run_id)
            if run is None:
                return {
                    "status": "rejected",
                    "replay_id": None,
                    "created": False,
                    "reason": "agent_run_not_found",
                }
            if run.status != AgentRunStatus.FAILED.value:
                return {
                    "status": "rejected",
                    "replay_id": None,
                    "created": False,
                    "reason": "agent_run_not_failed",
                }

            replay_item, created = replay_repository.enqueue_from_failed_run(
                agent_run_id=run.id,
                source_type=run.source_type,
                source_id=run.source_id,
            )
            return {
                "status": "accepted",
                "replay_id": replay_item.id,
                "created": created,
                "reason": None,
            }
    except SQLAlchemyError:
        return {
            "status": "unavailable",
            "replay_id": None,
            "created": False,
            "reason": "storage_unavailable",
        }
