from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from helm_api.services.replay_service import request_workflow_run_replay
from helm_api.services.workflow_status_service import (
    WorkflowStatusService,
    build_workflow_run_create_input,
)
from helm_orchestration import (
    CalendarAgentOutput,
    ScheduleBlock,
    StubTaskSystemAdapter,
    TaskSemantics,
    WorkflowOrchestrationService,
    past_event_guard,
    to_utc,
)
from helm_providers import GoogleCalendarProvider
from helm_storage.db import SessionLocal
from helm_storage.models import WorkflowArtifactORM
from helm_storage.repositories import WorkflowArtifactType
from helm_storage.repositories.users import get_user_by_telegram_id
from helm_storage.repositories.workflow_events import SQLAlchemyWorkflowEventRepository
from helm_storage.repositories.workflow_sync_records import (
    SQLAlchemyWorkflowSyncRecordRepository,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _parse_telegram_user_id(submitted_by: str) -> int | None:
    """Extract numeric Telegram user ID from a 'telegram:{id}' submitted_by string."""
    if not submitted_by.startswith("telegram:"):
        return None
    try:
        return int(submitted_by.split(":", 1)[1])
    except ValueError:
        return None


def _resolve_user_id(submitted_by: str, db: Session) -> int:
    """Resolve an internal Helm user ID from the run's submitted_by field.

    Primary path: parse 'telegram:{id}' from submitted_by and look up the user.
    Fallback path: use the TELEGRAM_ALLOWED_USER_ID env var (V1 single-user workaround).
    Raises RuntimeError if no user is found via either path.
    """
    telegram_id = _parse_telegram_user_id(submitted_by)
    if telegram_id is not None:
        user = get_user_by_telegram_id(telegram_id, db)
        if user is not None:
            return user.id

    # Fallback: V1 bootstrap user from env
    fallback_str = os.getenv("TELEGRAM_ALLOWED_USER_ID", "").strip()
    if fallback_str:
        try:
            fallback_telegram_id = int(fallback_str)
        except ValueError:
            pass
        else:
            user = get_user_by_telegram_id(fallback_telegram_id, db)
            if user is not None:
                return user.id

    raise RuntimeError(f"No user found for submitted_by={submitted_by}")


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

    def execute_task_run(
        self,
        run_id: int,
        *,
        semantics: TaskSemantics,
        request_text: str,
    ) -> dict[str, object]:
        """Build a CalendarAgentOutput from TaskSemantics and advance the run to the approval checkpoint."""
        from helm_worker.jobs.workflow_runs import (
            _build_validator_registry,
            _format_proposal_summary,
            _resolve_task_slot,
        )

        tz = ZoneInfo(os.environ["OPERATOR_TIMEZONE"])
        calendar_id = "primary"

        with SessionLocal() as session:
            raw_req = (
                session.query(WorkflowArtifactORM)
                .filter(
                    WorkflowArtifactORM.run_id == run_id,
                    WorkflowArtifactORM.artifact_type == WorkflowArtifactType.RAW_REQUEST.value,
                )
                .first()
            )
            submitted_by = (
                raw_req.payload.get("submitted_by", "") if raw_req is not None else ""
            )
            user_id = _resolve_user_id(submitted_by, session)
            provider = GoogleCalendarProvider(user_id, session)

            local_start = _resolve_task_slot(
                semantics, tz, calendar_id=calendar_id, provider=provider
            )
            start_utc = to_utc(local_start, tz)
            end_utc = start_utc + timedelta(minutes=semantics.sizing_minutes or 60)
            # Raises PastEventError if the resolved time is in the past — caller handles it
            past_event_guard(start_utc, tz)

            title = semantics.suggested_title or request_text
            block = ScheduleBlock(
                title=title,
                task_title=title,
                start=start_utc.isoformat(),
                end=end_utc.isoformat(),
            )
            output = CalendarAgentOutput(
                proposal_summary=_format_proposal_summary(title, start_utc, tz),
                calendar_id=calendar_id,
                time_blocks=(block,),
                proposed_changes=(f"Schedule {title}",),
            )

            wf_service = WorkflowOrchestrationService(
                session,
                validator_registry=_build_validator_registry(),
                task_system_adapter=StubTaskSystemAdapter(),
                calendar_system_adapter=provider,
            )
            wf_service.complete_current_step(
                run_id,
                artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
                artifact_payload=output,
                next_step_name="apply_schedule",
            )
            session.flush()
            return WorkflowStatusService(session).get_run_detail(run_id)

    def execute_after_approval(self, run_id: int) -> dict[str, object]:
        """Trigger immediate execution of apply_schedule after an approval decision."""
        from helm_worker.jobs.workflow_runs import (
            _build_resume_service,
            _build_specialist_steps,
        )

        with SessionLocal() as session:
            raw_req = (
                session.query(WorkflowArtifactORM)
                .filter(
                    WorkflowArtifactORM.run_id == run_id,
                    WorkflowArtifactORM.artifact_type == WorkflowArtifactType.RAW_REQUEST.value,
                )
                .first()
            )
            submitted_by = (
                raw_req.payload.get("submitted_by", "") if raw_req is not None else ""
            )
            user_id = _resolve_user_id(submitted_by, session)
            handlers = _build_specialist_steps()
            resume_service = _build_resume_service(session, handlers=handlers, user_id=user_id)
            resume_service.resume_run(run_id)
            return WorkflowStatusService(session).get_run_detail(run_id)

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
