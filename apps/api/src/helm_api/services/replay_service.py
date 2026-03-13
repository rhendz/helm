from datetime import datetime, timedelta

from helm_api.services.workflow_status_service import WorkflowStatusService
from helm_orchestration import WorkflowOrchestrationService
from helm_storage.db import SessionLocal
from helm_storage.repositories.agent_runs import AgentRunStatus, SQLAlchemyAgentRunRepository
from helm_storage.repositories.replay_queue import SQLAlchemyReplayQueueRepository
from helm_storage.repositories.workflow_sync_records import SQLAlchemyWorkflowSyncRecordRepository
from helm_storage.repositories.contracts import WorkflowSyncRecoveryClassification, WorkflowSyncStatus
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


def request_workflow_run_replay(*, run_id: int, actor: str, reason: str) -> dict[str, object]:
    try:
        with SessionLocal() as session:
            status_service = WorkflowStatusService(session)
            detail = status_service.get_run_detail(run_id)
            if detail is None:
                raise ValueError(f"Workflow run {run_id} does not exist.")

            safe_next_actions = detail.get("safe_next_actions", [])
            if not isinstance(safe_next_actions, list) or "request_replay" not in {
                item.get("action") for item in safe_next_actions if isinstance(item, dict)
            }:
                raise ValueError(f"Workflow run {run_id} does not allow explicit replay.")

            sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
            source_sync_record_ids = _select_replayable_sync_record_ids(sync_repo.list_for_run(run_id))
            if not source_sync_record_ids:
                raise ValueError(f"Workflow run {run_id} has no replayable sync records.")

            WorkflowOrchestrationService(session).request_sync_replay(
                run_id,
                actor=actor,
                sync_record_ids=tuple(source_sync_record_ids),
                reason=reason,
            )

            refreshed = status_service.get_run_detail(run_id)
            if refreshed is None:
                raise ValueError(f"Workflow run {run_id} could not be refreshed after replay request.")

            replay_requested_at = None
            replay_requested_by = None
            replay_sync_record_ids: list[int] = []
            replay_queue_source_ids: list[str] = []
            for record in sync_repo.list_for_run(run_id):
                if record.replay_requested_at is None:
                    continue
                if record.replayed_from_sync_record_id not in source_sync_record_ids:
                    continue
                replay_requested_at = replay_requested_at or record.replay_requested_at
                replay_requested_by = replay_requested_by or record.replay_requested_by
                if (
                    record.replayed_from_sync_record_id is not None
                    and record.replay_requested_by == actor
                    and record.id not in replay_sync_record_ids
                ):
                    replay_sync_record_ids.append(record.id)
                    replay_queue_source_ids.append(f"{run_id}:{record.replayed_from_sync_record_id}")

            return {
                "status": "accepted",
                "run_id": run_id,
                "source_sync_record_ids": source_sync_record_ids,
                "replay_sync_record_ids": replay_sync_record_ids,
                "replay_queue_source_ids": replay_queue_source_ids,
                "run": refreshed,
                "reason": None if replay_requested_at is not None and replay_requested_by == actor else None,
            }
    except SQLAlchemyError as exc:
        raise ValueError("Replay is unavailable because workflow storage is unavailable.") from exc


def _select_replayable_sync_record_ids(sync_records: list[object]) -> list[int]:
    replayable: list[int] = []
    for record in sync_records:
        if record.replayed_from_sync_record_id is not None:
            continue
        if record.replay_requested_at is not None or record.supersedes_sync_record_id is not None:
            continue
        if (
            record.status == WorkflowSyncStatus.SUCCEEDED.value
            and record.recovery_classification in {None, ""}
        ):
            replayable.append(record.id)
            continue
        if record.recovery_classification == WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value and (
            record.status == WorkflowSyncStatus.FAILED_TERMINAL.value
        ):
            replayable.append(record.id)
            continue
        if record.recovery_classification == WorkflowSyncRecoveryClassification.TERMINATED_AFTER_PARTIAL_SUCCESS.value and (
            record.status == WorkflowSyncStatus.CANCELLED.value
        ):
            replayable.append(record.id)
    return replayable


def execute_workflow_sync_replay(*, source_id: str) -> dict[str, object]:
    run_id, sync_record_id = _parse_workflow_sync_replay_source_id(source_id)
    try:
        with SessionLocal() as session:
            sync_record = SQLAlchemyWorkflowSyncRecordRepository(session).get_by_id(sync_record_id)
            if sync_record is None or sync_record.run_id != run_id:
                raise ValueError(
                    f"Workflow sync replay source {source_id} does not resolve to run {run_id}."
                )
            WorkflowOrchestrationService(session).execute_pending_sync_step(run_id)
            return {
                "status": "accepted",
                "run_id": run_id,
                "sync_record_id": sync_record_id,
                "source_id": source_id,
            }
    except SQLAlchemyError as exc:
        raise ValueError("Replay execution is unavailable because workflow storage is unavailable.") from exc


def _parse_workflow_sync_replay_source_id(source_id: str) -> tuple[int, int]:
    parts = source_id.split(":", maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Workflow sync replay source id '{source_id}' is invalid.")
    run_id, sync_record_id = parts
    try:
        return int(run_id), int(sync_record_id)
    except ValueError as exc:
        raise ValueError(f"Workflow sync replay source id '{source_id}' is invalid.") from exc
