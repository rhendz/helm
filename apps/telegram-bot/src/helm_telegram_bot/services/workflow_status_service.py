from __future__ import annotations

import logging
from typing import Any

from helm_api.services.replay_service import request_workflow_run_replay
from helm_api.services.workflow_status_service import (
    WorkflowStatusService,
    build_workflow_run_create_input,
)
from helm_storage.db import SessionLocal
from helm_storage.repositories.workflow_events import SQLAlchemyWorkflowEventRepository
from helm_storage.repositories.workflow_sync_records import (
    SQLAlchemyWorkflowSyncRecordRepository,
)

logger = logging.getLogger(__name__)


class TelegramWorkflowStatusService:
    def start_run(self, *, request_text: str, submitted_by: str, chat_id: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).create_run(
                build_workflow_run_create_input(
                    workflow_type="weekly_scheduling",
                    first_step_name="dispatch_task_agent",
                    request_text=request_text,
                    submitted_by=submitted_by,
                    channel="telegram",
                    metadata={"chat_id": chat_id},
                )
            )

    def start_task_run(self, *, request_text: str, submitted_by: str, chat_id: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).create_run(
                build_workflow_run_create_input(
                    workflow_type="task_quick_add",
                    first_step_name="infer_task_semantics",
                    request_text=request_text,
                    submitted_by=submitted_by,
                    channel="telegram",
                    metadata={"chat_id": chat_id},
                )
            )

    def list_recent_runs(self, *, limit: int = 5) -> list[dict[str, object]]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).list_runs(limit=limit)

    def list_runs_needing_action(self, *, limit: int = 5) -> list[dict[str, object]]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).list_runs(needs_action=True, limit=limit)

    def get_run_detail(self, run_id: int) -> dict[str, object] | None:
        with SessionLocal() as session:
            return WorkflowStatusService(session).get_run_detail(run_id)

    def retry_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).retry_run(run_id, reason=reason)

    def terminate_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).terminate_run(run_id, reason=reason)

    def request_replay(self, run_id: int, *, actor: str, reason: str) -> dict[str, object]:
        return request_workflow_run_replay(run_id=run_id, actor=actor, reason=reason)["run"]

    def approve_run(self, run_id: int, *, actor: str, target_artifact_id: int) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).approve_run(
                run_id,
                actor=actor,
                target_artifact_id=target_artifact_id,
            )

    def reject_run(self, run_id: int, *, actor: str, target_artifact_id: int) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).reject_run(
                run_id,
                actor=actor,
                target_artifact_id=target_artifact_id,
            )

    def request_revision(
        self,
        run_id: int,
        *,
        actor: str,
        target_artifact_id: int,
        feedback: str,
    ) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).request_revision(
                run_id,
                actor=actor,
                target_artifact_id=target_artifact_id,
                feedback=feedback,
            )

    def list_sync_events(self, run_id: int) -> list[dict[str, object]]:
        """Query sync records and associated drift events for a workflow run.

        Returns a list of dicts, each containing sync record details and associated
        drift event metadata (if present). Records are sorted by created_at descending
        (most recent first).

        Args:
            run_id: ID of the workflow run to query

        Returns:
            List of dicts with keys:
                - sync_record_id: int
                - planned_item_key: str
                - status: str (WorkflowSyncStatus)
                - external_object_id: str | None
                - created_at: datetime
                - last_error_summary: str | None (raw or JSON for drift metadata)
                - drift_event: dict | None (associated drift event if present)

        Edge cases handled:
            - Empty results: Returns empty list
            - Missing drift events: drift_event field is None
            - Malformed drift metadata: Returned as-is in last_error_summary
        """
        with SessionLocal() as session:
            sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
            event_repo = SQLAlchemyWorkflowEventRepository(session)

            # Fetch sync records and drift events
            sync_records = sync_repo.list_for_run(run_id)
            drift_events = event_repo.list_for_run_by_type(
                run_id, event_type="drift_detected_external_change"
            )

            # Build a map of drift events by sync record ID for fast lookup
            drift_by_sync_id: dict[int, dict[str, Any]] = {}
            for event in drift_events:
                # Drift event details should contain the sync_record_id
                if isinstance(event.details, dict) and "sync_record_id" in event.details:
                    sync_id = event.details["sync_record_id"]
                    drift_by_sync_id[sync_id] = {
                        "event_id": event.id,
                        "summary": event.summary,
                        "details": event.details,
                        "created_at": event.created_at,
                    }

            # Build sync event list with drift association
            sync_events: list[dict[str, object]] = []
            for record in sync_records:
                sync_event: dict[str, object] = {
                    "sync_record_id": record.id,
                    "planned_item_key": record.planned_item_key,
                    "status": record.status,
                    "external_object_id": record.external_object_id,
                    "created_at": record.created_at,
                    "last_error_summary": record.last_error_summary,
                    "drift_event": drift_by_sync_id.get(record.id),
                }
                sync_events.append(sync_event)

            # Sort by created_at descending (most recent first)
            sync_events.sort(key=lambda x: x["created_at"], reverse=True)

            logger.debug(
                "sync_query_executed",
                extra={
                    "run_id": run_id,
                    "sync_record_count": len(sync_records),
                    "drift_event_count": len(drift_events),
                },
            )

            return sync_events

    def get_sync_details(self, run_id: int) -> dict[str, object]:
        """Get aggregated sync details for a workflow run including event timeline and counts.

        Queries sync records and computes total/task/calendar write counts, reusing logic
        from WorkflowStatusService._completion_summary() to avoid duplication.

        Args:
            run_id: ID of the workflow run to query

        Returns:
            Dict with keys:
                - sync_records: list[dict] (from list_sync_events)
                - drift_events: list[dict] (filtered drift events with metadata)
                - total_sync_writes: int (count of succeeded sync records)
                - task_sync_writes: int (count of task system syncs)
                - calendar_sync_writes: int (count of calendar system syncs)

        Edge cases handled:
            - No sync records: Returns empty lists and 0 counts
            - Missing target_system field: Treated as unknown target system, not counted
            - Empty drift metadata: Included but with empty details
        """
        with SessionLocal() as session:
            sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
            event_repo = SQLAlchemyWorkflowEventRepository(session)

            sync_records = sync_repo.list_for_run(run_id)
            drift_events = event_repo.list_for_run_by_type(
                run_id, event_type="drift_detected_external_change"
            )

            # Get formatted sync events
            sync_events = self.list_sync_events(run_id)

            # Aggregate counts by status and target system
            # Only count succeeded records (matching WorkflowStatusService pattern)
            total_sync_writes = sum(
                1
                for record in sync_records
                if record.status == "succeeded"  # WorkflowSyncStatus.SUCCEEDED.value
            )
            task_sync_writes = sum(
                1
                for record in sync_records
                if record.status == "succeeded" and record.target_system == "task_system"
            )
            calendar_sync_writes = sum(
                1
                for record in sync_records
                if record.status == "succeeded" and record.target_system == "calendar_system"
            )

            # Format drift events with metadata
            formatted_drift_events: list[dict[str, object]] = []
            for event in drift_events:
                formatted_drift_events.append(
                    {
                        "event_id": event.id,
                        "summary": event.summary,
                        "details": event.details or {},
                        "created_at": event.created_at,
                    }
                )

            result: dict[str, object] = {
                "sync_records": sync_events,
                "drift_events": formatted_drift_events,
                "total_sync_writes": total_sync_writes,
                "task_sync_writes": task_sync_writes,
                "calendar_sync_writes": calendar_sync_writes,
            }

            return result
