from datetime import datetime, timedelta

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


def reprocess_failed_runs(
    *,
    source_type: str | None,
    source_id: str | None,
    since_hours: int | None,
    limit: int,
    dry_run: bool,
) -> dict[str, object]:
    if not source_type and not source_id and since_hours is None:
        return {
            "status": "rejected",
            "dry_run": dry_run,
            "matched_count": 0,
            "enqueued_count": 0,
            "skipped_count": 0,
            "reason": "scope_required",
        }

    started_at_gte = datetime.utcnow() - timedelta(hours=since_hours) if since_hours else None
    try:
        with SessionLocal() as session:
            run_repository = SQLAlchemyAgentRunRepository(session)
            replay_repository = SQLAlchemyReplayQueueRepository(session)
            failed_runs = run_repository.list_failed_for_reprocess(
                source_type=source_type,
                source_id=source_id,
                started_at_gte=started_at_gte,
                limit=limit,
            )
            if dry_run:
                return {
                    "status": "accepted",
                    "dry_run": True,
                    "matched_count": len(failed_runs),
                    "enqueued_count": 0,
                    "skipped_count": 0,
                    "reason": None,
                }

            enqueued_count = 0
            skipped_count = 0
            for run in failed_runs:
                _item, created = replay_repository.enqueue_from_failed_run(
                    agent_run_id=run.id,
                    source_type=run.source_type,
                    source_id=run.source_id,
                )
                if created:
                    enqueued_count += 1
                else:
                    skipped_count += 1

            return {
                "status": "accepted",
                "dry_run": False,
                "matched_count": len(failed_runs),
                "enqueued_count": enqueued_count,
                "skipped_count": skipped_count,
                "reason": None,
            }
    except SQLAlchemyError:
        return {
            "status": "unavailable",
            "dry_run": dry_run,
            "matched_count": 0,
            "enqueued_count": 0,
            "skipped_count": 0,
            "reason": "storage_unavailable",
        }
