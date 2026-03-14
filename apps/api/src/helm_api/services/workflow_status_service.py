from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from helm_connectors import (
    GoogleCalendarAdapter,
    GoogleCalendarAuth,
    StubCalendarSystemAdapter,
    StubTaskSystemAdapter,
)
from helm_orchestration import (
    ApprovalAction,
    ApprovalDecision,
    CalendarSystemAdapter,
    TaskSystemAdapter,
    WeeklySchedulingRequest,
    WeeklyTaskRequest,
    WorkflowOrchestrationService,
)
from helm_storage.models import WorkflowArtifactORM, WorkflowRunORM
from helm_storage.repositories import (
    RawRequestArtifactPayload,
    SQLAlchemyWorkflowArtifactRepository,
    SQLAlchemyWorkflowRunRepository,
    SQLAlchemyWorkflowSyncRecordRepository,
    WorkflowArtifactType,
    WorkflowRunState,
    WorkflowRunStatus,
    WorkflowStepStatus,
    WorkflowSyncRecoveryClassification,
    WorkflowSyncStatus,
    WorkflowTargetSystem,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload


@dataclass(frozen=True)
class WorkflowRunCreateInput:
    workflow_type: str
    first_step_name: str
    request_text: str
    submitted_by: str
    channel: str
    metadata: dict[str, Any]


class WorkflowStatusService:
    def __init__(
        self,
        session: Session,
        *,
        task_system_adapter: TaskSystemAdapter | None = None,
        calendar_system_adapter: CalendarSystemAdapter | None = None,
    ) -> None:
        self._session = session
        self._run_repo = SQLAlchemyWorkflowRunRepository(session)
        self._artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        self._sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
        
        # Instantiate real adapters if credentials are available, otherwise use stubs
        if task_system_adapter is None:
            task_system_adapter = StubTaskSystemAdapter()
        if calendar_system_adapter is None:
            # Try to use real GoogleCalendarAdapter if credentials are available
            try:
                auth = GoogleCalendarAuth()
                calendar_system_adapter = GoogleCalendarAdapter(auth)
            except ValueError:
                # Credentials not available; fall back to stub
                calendar_system_adapter = StubCalendarSystemAdapter()
        
        self._orchestration = WorkflowOrchestrationService(
            session,
            task_system_adapter=task_system_adapter,
            calendar_system_adapter=calendar_system_adapter,
        )

    def create_run(self, payload: WorkflowRunCreateInput) -> dict[str, object]:
        normalized_payload = build_workflow_run_create_input(
            workflow_type=payload.workflow_type,
            first_step_name=payload.first_step_name,
            request_text=payload.request_text,
            submitted_by=payload.submitted_by,
            channel=payload.channel,
            metadata=payload.metadata,
        )
        state = self._orchestration.create_run(
            workflow_type=normalized_payload.workflow_type,
            first_step_name=normalized_payload.first_step_name,
            request_payload=RawRequestArtifactPayload(
                request_text=normalized_payload.request_text,
                submitted_by=normalized_payload.submitted_by,
                channel=normalized_payload.channel,
                metadata=normalized_payload.metadata,
            ),
        )
        return self._build_summary(state)

    def list_runs(
        self, *, needs_action: bool | None = None, limit: int = 20
    ) -> list[dict[str, object]]:
        if needs_action is True:
            states = self._run_repo.list_needing_action(limit=limit)
            return [self._build_summary(state) for state in states]

        runs = list(self._session.execute(self._run_query().limit(limit)).scalars().all())
        return [self._build_summary(self._build_state(run.id)) for run in runs]

    def get_run_detail(self, run_id: int) -> dict[str, object] | None:
        run = self._session.execute(self._run_query(run_id=run_id)).scalars().first()
        if run is None:
            return None
        state = self._build_state(run.id)
        detail = self._build_summary(state)
        detail["lineage"] = self._build_lineage(run)
        return detail

    def list_proposal_versions(self, run_id: int) -> list[dict[str, object]]:
        run = self._session.execute(self._run_query(run_id=run_id)).scalars().first()
        if run is None:
            raise ValueError(f"Workflow run {run_id} does not exist.")
        return self._build_proposal_versions(run)

    def retry_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        return self._build_summary(self._orchestration.retry_current_step(run_id, reason=reason))

    def terminate_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        return self._build_summary(self._orchestration.terminate_run(run_id, reason=reason))

    def approve_run(self, run_id: int, *, actor: str, target_artifact_id: int) -> dict[str, object]:
        return self._submit_approval(
            run_id,
            ApprovalDecision(
                action=ApprovalAction.APPROVE,
                actor=actor,
                target_artifact_id=target_artifact_id,
            ),
        )

    def reject_run(self, run_id: int, *, actor: str, target_artifact_id: int) -> dict[str, object]:
        return self._submit_approval(
            run_id,
            ApprovalDecision(
                action=ApprovalAction.REJECT,
                actor=actor,
                target_artifact_id=target_artifact_id,
            ),
        )

    def request_revision(
        self,
        run_id: int,
        *,
        actor: str,
        target_artifact_id: int,
        feedback: str,
    ) -> dict[str, object]:
        return self._submit_approval(
            run_id,
            ApprovalDecision(
                action=ApprovalAction.REQUEST_REVISION,
                actor=actor,
                target_artifact_id=target_artifact_id,
                revision_feedback=feedback,
            ),
        )

    def _build_state(self, run_id: int) -> WorkflowRunState:
        state = self._run_repo.get_with_current_state(run_id)
        if state is None:
            raise ValueError(f"Workflow run {run_id} does not exist.")
        return state

    def _run_query(self, *, run_id: int | None = None):
        stmt = (
            select(WorkflowRunORM)
            .options(
                selectinload(WorkflowRunORM.steps),
                selectinload(WorkflowRunORM.artifacts),
                selectinload(WorkflowRunORM.events),
                selectinload(WorkflowRunORM.approval_checkpoints),
            )
            .order_by(WorkflowRunORM.started_at.desc(), WorkflowRunORM.id.desc())
        )
        if run_id is not None:
            stmt = stmt.where(WorkflowRunORM.id == run_id)
        return stmt

    def _build_summary(self, state: WorkflowRunState) -> dict[str, object]:
        failed_step = self._latest_failed_step(state)
        sync_projection = self._sync_projection(state.run.id)
        latest_validation_artifact = state.latest_artifacts.get(
            WorkflowArtifactType.VALIDATION_RESULT.value
        )
        approval_projection = self._approval_projection(state)
        proposal_versions = self._build_proposal_versions(state.run)
        final_summary_artifact = self._artifact_repo.get_latest_for_run(
            state.run.id,
            artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value,
        )
        final_summary = self._final_summary(final_summary_artifact)
        latest_validation_outcome = None
        if latest_validation_artifact is not None:
            latest_validation_outcome = str(latest_validation_artifact.payload.get("outcome"))
        elif state.run.validation_outcome_summary:
            latest_validation_outcome = state.run.validation_outcome_summary

        paused_state, pause_reason = self._paused_state(state, failed_step)
        failure_kind = self._failure_kind(state, failed_step, sync_projection)
        failure_summary = self._failure_summary(state, failed_step, sync_projection)
        return {
            "id": state.run.id,
            "workflow_type": state.run.workflow_type,
            "status": state.run.status,
            "current_step": state.run.current_step_name,
            "current_step_attempt": state.run.current_step_attempt,
            "attempt_count": state.run.attempt_count,
            "needs_action": state.run.needs_action,
            "paused_state": paused_state,
            "pause_reason": pause_reason,
            "last_event_summary": state.run.last_event_summary
            or (state.last_event.summary if state.last_event else None),
            "failure_summary": failure_summary,
            "failure_kind": failure_kind,
            "recovery_class": sync_projection["recovery_class"],
            "latest_validation_outcome": latest_validation_outcome,
            "retry_state": (
                sync_projection["retry_state"]
                if sync_projection["has_sync_records"]
                else (failed_step.retry_state if failed_step is not None else state.run.retry_state)
            ),
            "retryable": (
                bool(sync_projection["retryable"])
                if sync_projection["has_sync_records"]
                else bool(failed_step.retryable if failed_step is not None else False)
            ),
            "available_actions": self._available_actions(state, failed_step),
            "safe_next_actions": sync_projection["safe_next_actions"],
            "approval_checkpoint": approval_projection["checkpoint"],
            "latest_decision": approval_projection["latest_decision"],
            "latest_proposal_version": proposal_versions[0] if proposal_versions else None,
            "proposal_versions": proposal_versions,
            "weekly_request": self._weekly_request_projection(state),
            "completion_summary": self._completion_summary(
                state,
                failed_step=failed_step,
                sync_projection=sync_projection,
                proposal_versions=proposal_versions,
                final_summary=final_summary,
            ),
            "effect_summary": sync_projection["effect_summary"],
            "sync": sync_projection["sync"],
            "started_at": state.run.started_at,
            "updated_at": state.run.updated_at,
            "completed_at": state.run.completed_at,
        }

    def _build_lineage(self, run: WorkflowRunORM) -> dict[str, object]:
        artifacts = sorted(run.artifacts, key=lambda artifact: (artifact.created_at, artifact.id))
        raw_request = next(
            (
                artifact
                for artifact in artifacts
                if artifact.artifact_type == WorkflowArtifactType.RAW_REQUEST.value
            ),
            None,
        )
        intermediate = [
            self._artifact_payload(artifact)
            for artifact in artifacts
            if artifact.artifact_type
            in {
                WorkflowArtifactType.NORMALIZED_TASK.value,
                WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
                WorkflowArtifactType.APPROVAL_REQUEST.value,
                WorkflowArtifactType.APPROVAL_DECISION.value,
                WorkflowArtifactType.REVISION_REQUEST.value,
            }
        ]
        validations = [
            self._artifact_payload(artifact)
            for artifact in artifacts
            if artifact.artifact_type == WorkflowArtifactType.VALIDATION_RESULT.value
        ]
        final_summary_artifact = self._artifact_repo.get_latest_for_run(
            run.id,
            artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value,
        )
        return {
            "raw_request": self._artifact_payload(raw_request) if raw_request is not None else None,
            "intermediate_artifacts": intermediate,
            "validation_artifacts": validations,
            "final_summary": self._final_summary(final_summary_artifact),
            "step_transitions": [
                {
                    "id": step.id,
                    "step_name": step.step_name,
                    "attempt_number": step.attempt_number,
                    "status": step.status,
                    "retry_state": step.retry_state,
                    "retryable": step.retryable,
                    "validation_outcome_summary": step.validation_outcome_summary,
                    "execution_error_summary": step.execution_error_summary,
                    "failure_class": step.failure_class,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at,
                }
                for step in sorted(run.steps, key=lambda row: (row.attempt_number, row.id))
            ],
            "events": [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "run_status": event.run_status,
                    "step_status": event.step_status,
                    "step_id": event.step_id,
                    "summary": event.summary,
                    "details": event.details,
                    "created_at": event.created_at,
                }
                for event in sorted(run.events, key=lambda row: row.id)
            ],
        }

    def _available_actions(self, state: WorkflowRunState, failed_step) -> list[dict[str, str]]:  # noqa: ANN001
        if not state.run.needs_action:
            return []

        if (
            state.run.blocked_reason == "approval_required"
            and state.active_approval_checkpoint is not None
        ):
            return [
                {"action": action, "label": _approval_action_label(action)}
                for action in state.active_approval_checkpoint.allowed_actions
            ]

        actions = [{"action": "terminate", "label": "Terminate run"}]
        if failed_step is not None and (
            state.run.status == WorkflowRunStatus.BLOCKED.value or failed_step.retryable
        ):
            actions.insert(0, {"action": "retry", "label": "Retry current step"})
        return actions

    def _paused_state(self, state: WorkflowRunState, failed_step) -> tuple[str | None, str | None]:  # noqa: ANN001
        if (
            state.run.status == WorkflowRunStatus.BLOCKED.value
            and state.run.blocked_reason == "approval_required"
        ):
            return "awaiting_approval", "Awaiting operator approval before downstream changes."
        if state.run.status == WorkflowRunStatus.BLOCKED.value:
            return (
                "blocked_validation",
                state.run.validation_outcome_summary or state.run.last_event_summary,
            )
        if state.run.status == WorkflowRunStatus.FAILED.value:
            return (
                "awaiting_retry",
                state.run.execution_error_summary or state.run.last_event_summary,
            )
        return None, None

    def _failure_kind(
        self, state: WorkflowRunState, failed_step, sync_projection: dict[str, object]
    ) -> str | None:  # noqa: ANN001
        sync_recovery_class = sync_projection["recovery_class"]
        if isinstance(sync_recovery_class, str):
            return sync_recovery_class
        if (
            state.run.status == WorkflowRunStatus.BLOCKED.value
            and state.run.blocked_reason == "approval_required"
        ):
            return "approval_required"
        if state.run.status == WorkflowRunStatus.BLOCKED.value:
            return "blocked_validation"
        if state.run.status == WorkflowRunStatus.FAILED.value:
            return "execution_failed"
        if (
            failed_step is not None
            and failed_step.status == WorkflowStepStatus.VALIDATION_FAILED.value
        ):
            return "blocked_validation"
        return None

    def _failure_summary(
        self, state: WorkflowRunState, failed_step, sync_projection: dict[str, object]
    ) -> str | None:  # noqa: ANN001
        sync_failure_summary = sync_projection["failure_summary"]
        if isinstance(sync_failure_summary, str):
            return sync_failure_summary
        if (
            state.run.status == WorkflowRunStatus.BLOCKED.value
            and state.run.blocked_reason == "approval_required"
        ):
            return "Awaiting operator approval before downstream changes."
        if state.run.status == WorkflowRunStatus.BLOCKED.value:
            return state.run.validation_outcome_summary or (
                failed_step.validation_outcome_summary if failed_step is not None else None
            )
        if state.run.status == WorkflowRunStatus.FAILED.value:
            return state.run.execution_error_summary or (
                failed_step.execution_error_summary if failed_step is not None else None
            )
        return None

    def _latest_failed_step(self, state: WorkflowRunState):  # noqa: ANN001
        failures = [
            step
            for step in state.run.steps
            if step.status
            in {WorkflowStepStatus.FAILED.value, WorkflowStepStatus.VALIDATION_FAILED.value}
        ]
        if not failures:
            return None
        return max(failures, key=lambda step: (step.attempt_number, step.id))

    def _approval_projection(self, state: WorkflowRunState) -> dict[str, object]:
        schedule_proposal = state.latest_artifacts.get(WorkflowArtifactType.SCHEDULE_PROPOSAL.value)
        latest_decision = state.latest_artifacts.get(WorkflowArtifactType.APPROVAL_DECISION.value)
        checkpoint = state.active_approval_checkpoint
        checkpoint_payload = None
        if checkpoint is not None:
            checkpoint_proposal = self._artifact_repo.get_by_id(checkpoint.target_artifact_id)
            proposal_detail = self._proposal_projection(
                checkpoint_proposal.payload
                if checkpoint_proposal is not None
                else (schedule_proposal.payload if schedule_proposal is not None else {})
            )
            checkpoint_payload = {
                "checkpoint_id": checkpoint.id,
                "target_artifact_id": checkpoint.target_artifact_id,
                "target_version_number": checkpoint_proposal.version_number
                if checkpoint_proposal is not None
                else 0,
                **proposal_detail,
                "pause_reason": "Awaiting operator approval before downstream changes.",
                "allowed_actions": list(checkpoint.allowed_actions),
            }
        decision_payload = None
        if latest_decision is not None:
            decision_payload = {
                "decision": latest_decision.payload.get("decision"),
                "actor": latest_decision.payload.get("actor"),
                "target_artifact_id": latest_decision.payload.get("target_artifact_id"),
                "target_version_number": latest_decision.payload.get("target_version_number"),
                "decision_at": latest_decision.payload.get("decision_at"),
                "revision_feedback": latest_decision.payload.get("revision_feedback"),
            }
        return {"checkpoint": checkpoint_payload, "latest_decision": decision_payload}

    def _sync_projection(self, run_id: int) -> dict[str, object]:
        sync_records = self._sync_repo.list_for_run(run_id)
        if not sync_records:
            return {
                "has_sync_records": False,
                "effect_summary": None,
                "failure_summary": None,
                "recovery_class": None,
                "retry_state": None,
                "retryable": False,
                "safe_next_actions": [],
                "sync": {
                    "counts_by_state": {},
                    "counts_by_target": {},
                    "last_failed_or_unresolved": None,
                    "replay_lineage": None,
                },
            }

        counts_by_state: dict[str, int] = {}
        counts_by_target = {
            WorkflowTargetSystem.TASK_SYSTEM.value: 0,
            WorkflowTargetSystem.CALENDAR_SYSTEM.value: 0,
        }
        for record in sync_records:
            counts_by_state[record.status] = counts_by_state.get(record.status, 0) + 1
            counts_by_target[record.target_system] = (
                counts_by_target.get(record.target_system, 0) + 1
            )

        unresolved_statuses = {
            WorkflowSyncStatus.PENDING.value,
            WorkflowSyncStatus.IN_PROGRESS.value,
            WorkflowSyncStatus.FAILED_RETRYABLE.value,
            WorkflowSyncStatus.FAILED_TERMINAL.value,
            WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
            WorkflowSyncStatus.CANCELLED.value,
        }
        last_failed_or_unresolved = [
            record for record in sync_records if record.status in unresolved_statuses
        ]
        last_failed_record = max(
            last_failed_or_unresolved,
            key=lambda record: (
                record.last_attempted_at or record.completed_at or record.updated_at,
                record.id,
            ),
            default=None,
        )
        recovery_record = max(
            [record for record in sync_records if record.recovery_classification],
            key=lambda record: (record.recovery_updated_at or record.updated_at, record.id),
            default=None,
        )
        replay_records = [
            record
            for record in sync_records
            if record.replayed_from_sync_record_id is not None
            or record.replay_requested_at is not None
        ]
        replay_lineage = None
        if replay_records:
            latest_replay = max(
                replay_records,
                key=lambda record: (record.replay_requested_at or record.updated_at, record.id),
            )
            replay_lineage = {
                "active": True,
                "latest_generation": max(record.lineage_generation for record in replay_records),
                "latest_replay_requested_at": latest_replay.replay_requested_at,
                "latest_replay_requested_by": latest_replay.replay_requested_by,
                "source_sync_record_ids": sorted(
                    {
                        record.replayed_from_sync_record_id
                        for record in replay_records
                        if record.replayed_from_sync_record_id is not None
                    }
                ),
                "replay_sync_record_ids": [record.id for record in replay_records],
            }

        total_writes = len(sync_records)
        pending_execution = counts_by_state.get(WorkflowSyncStatus.PENDING.value, 0) == total_writes
        effect_summary = {
            "pending_execution": pending_execution,
            "total_writes": total_writes,
            "task_writes": counts_by_target.get(WorkflowTargetSystem.TASK_SYSTEM.value, 0),
            "calendar_writes": counts_by_target.get(WorkflowTargetSystem.CALENDAR_SYSTEM.value, 0),
        }

        recovery_class = (
            recovery_record.recovery_classification if recovery_record is not None else None
        )
        retryable = recovery_class in {
            WorkflowSyncRecoveryClassification.RECOVERABLE_FAILURE.value,
            WorkflowSyncRecoveryClassification.RETRY_REQUESTED.value,
            WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value,
        }
        retry_state = "retryable" if retryable else None
        successful_replay_sources = [
            record
            for record in sync_records
            if record.status == WorkflowSyncStatus.SUCCEEDED.value
            and record.replayed_from_sync_record_id is None
            and record.replay_requested_at is None
            and record.supersedes_sync_record_id is None
            and not record.recovery_classification
        ]
        safe_next_actions = self._safe_next_actions(
            recovery_class=recovery_class,
            last_record=last_failed_record,
            has_successful_replay_sources=bool(successful_replay_sources),
        )

        return {
            "has_sync_records": True,
            "effect_summary": effect_summary,
            "failure_summary": self._sync_failure_summary(last_failed_record, recovery_class),
            "recovery_class": recovery_class,
            "retry_state": retry_state,
            "retryable": retryable,
            "safe_next_actions": safe_next_actions,
            "sync": {
                "counts_by_state": counts_by_state,
                "counts_by_target": counts_by_target,
                "last_failed_or_unresolved": self._sync_record_summary(last_failed_record),
                "replay_lineage": replay_lineage,
            },
        }

    def _sync_failure_summary(self, sync_record, recovery_class: str | None) -> str | None:  # noqa: ANN001
        if sync_record is None:
            return None
        if (
            recovery_class
            == WorkflowSyncRecoveryClassification.TERMINATED_AFTER_PARTIAL_SUCCESS.value
        ):
            return "Remaining approved writes were cancelled after partial sync success."
        if recovery_class == WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value:
            return "Replay requested for downstream sync lineage."
        if sync_record.status == WorkflowSyncStatus.DRIFT_DETECTED.value:
            return "External event was manually edited after Helm wrote it; operator action required to recover."
        if sync_record.last_error_summary:
            return sync_record.last_error_summary
        if sync_record.status == WorkflowSyncStatus.PENDING.value:
            return "Approved writes are queued and ready for execution."
        return None

    def _sync_record_summary(self, sync_record) -> dict[str, object] | None:  # noqa: ANN001
        if sync_record is None:
            return None
        return {
            "sync_record_id": sync_record.id,
            "target_system": sync_record.target_system,
            "sync_kind": sync_record.sync_kind,
            "planned_item_key": sync_record.planned_item_key,
            "status": sync_record.status,
            "recovery_class": sync_record.recovery_classification,
            "retryable": sync_record.status
            in {
                WorkflowSyncStatus.PENDING.value,
                WorkflowSyncStatus.FAILED_RETRYABLE.value,
                WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
            },
            "external_object_id": sync_record.external_object_id,
            "last_error_summary": sync_record.last_error_summary,
            "lineage_generation": sync_record.lineage_generation,
            "replayed_from_sync_record_id": sync_record.replayed_from_sync_record_id,
            "supersedes_sync_record_id": sync_record.supersedes_sync_record_id,
            "last_attempted_at": sync_record.last_attempted_at,
            "completed_at": sync_record.completed_at,
        }

    def _safe_next_actions(
        self,
        *,
        recovery_class: str | None,
        last_record,
        has_successful_replay_sources: bool,
    ) -> list[dict[str, str]]:  # noqa: ANN001
        if recovery_class is None and has_successful_replay_sources:
            return [
                {"action": "request_replay", "label": "Request explicit replay after adapter fix"}
            ]
        if last_record is None:
            return []
        # Handle drift-detected records: operator must initiate recovery
        if last_record.status == WorkflowSyncStatus.DRIFT_DETECTED.value:
            return [
                {"action": "request_replay", "label": "Request explicit replay to recover from manual edit"}
            ]
        if (
            recovery_class
            == WorkflowSyncRecoveryClassification.TERMINATED_AFTER_PARTIAL_SUCCESS.value
        ):
            return [{"action": "request_replay", "label": "Request replay for cancelled writes"}]
        if recovery_class == WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value:
            return [
                {"action": "request_replay", "label": "Request explicit replay after adapter fix"}
            ]
        if recovery_class in {
            WorkflowSyncRecoveryClassification.RECOVERABLE_FAILURE.value,
            WorkflowSyncRecoveryClassification.RETRY_REQUESTED.value,
        }:
            return [
                {"action": "retry", "label": "Retry unresolved writes"},
                {"action": "terminate", "label": "Terminate remaining writes"},
            ]
        if recovery_class == WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value:
            return [{"action": "await_replay", "label": "Await replay processing"}]
        if last_record.status == WorkflowSyncStatus.PENDING.value:
            return [{"action": "await_execution", "label": "Await approved write execution"}]
        return []

    def _submit_approval(self, run_id: int, decision: ApprovalDecision) -> dict[str, object]:
        return self._build_summary(
            self._orchestration.submit_approval_decision(run_id, decision=decision)
        )

    def _build_proposal_versions(self, run: WorkflowRunORM) -> list[dict[str, object]]:
        proposals = [
            artifact
            for artifact in run.artifacts
            if artifact.artifact_type == WorkflowArtifactType.SCHEDULE_PROPOSAL.value
        ]
        if not proposals:
            return []
        proposals = sorted(
            proposals, key=lambda artifact: (artifact.version_number, artifact.id), reverse=True
        )
        active_checkpoint = next(
            (
                checkpoint
                for checkpoint in sorted(
                    run.approval_checkpoints, key=lambda row: row.id, reverse=True
                )
                if checkpoint.status == "pending"
            ),
            None,
        )
        decision_by_artifact_id: dict[int, dict[str, Any]] = {}
        revision_feedback_by_artifact_id: dict[int, str] = {}
        for artifact in sorted(run.artifacts, key=lambda row: row.id):
            if artifact.artifact_type == WorkflowArtifactType.APPROVAL_DECISION.value:
                target_artifact_id = artifact.payload.get("target_artifact_id")
                if isinstance(target_artifact_id, int):
                    decision_by_artifact_id[target_artifact_id] = {
                        "decision": artifact.payload.get("decision"),
                        "actor": artifact.payload.get("actor"),
                        "target_artifact_id": target_artifact_id,
                        "target_version_number": artifact.payload.get("target_version_number"),
                        "decision_at": artifact.payload.get("decision_at"),
                        "revision_feedback": artifact.payload.get("revision_feedback"),
                    }
            if artifact.artifact_type == WorkflowArtifactType.REVISION_REQUEST.value:
                target_artifact_id = artifact.payload.get("target_artifact_id")
                feedback = artifact.payload.get("feedback")
                if isinstance(target_artifact_id, int) and isinstance(feedback, str) and feedback:
                    revision_feedback_by_artifact_id[target_artifact_id] = feedback

        latest_proposal_id = proposals[0].id
        superseded_ids = {
            artifact.supersedes_artifact_id
            for artifact in proposals
            if artifact.supersedes_artifact_id is not None
        }
        return [
            {
                "artifact_id": artifact.id,
                "version_number": artifact.version_number,
                **self._proposal_projection(artifact.payload),
                "created_at": artifact.created_at,
                "producer_step_name": artifact.producer_step_name,
                "is_latest": artifact.id == latest_proposal_id,
                "is_actionable": active_checkpoint is not None
                and active_checkpoint.target_artifact_id == artifact.id,
                "superseded": artifact.id in superseded_ids,
                "approved": decision_by_artifact_id.get(artifact.id, {}).get("decision")
                == "approve",
                "rejected": decision_by_artifact_id.get(artifact.id, {}).get("decision")
                == "reject",
                "latest_decision": decision_by_artifact_id.get(artifact.id),
                "revision_feedback_summary": revision_feedback_by_artifact_id.get(artifact.id),
                "supersedes_artifact_id": artifact.supersedes_artifact_id,
            }
            for artifact in proposals
        ]

    def _weekly_request_projection(self, state: WorkflowRunState) -> dict[str, object] | None:
        raw_request = state.latest_artifacts.get(WorkflowArtifactType.RAW_REQUEST.value)
        if raw_request is None:
            return None
        weekly_request = raw_request.payload.get("metadata", {}).get("weekly_request")
        if not isinstance(weekly_request, dict):
            return None
        return {
            "raw_request_text": weekly_request.get("raw_request_text"),
            "planning_goal": weekly_request.get("planning_goal"),
            "tasks": [
                {
                    "title": task.get("title"),
                    "details": task.get("details"),
                    "priority": task.get("priority"),
                    "deadline": task.get("deadline"),
                    "estimated_minutes": task.get("estimated_minutes"),
                    "source_line": task.get("source_line"),
                    "warnings": list(task.get("warnings", [])),
                }
                for task in weekly_request.get("tasks", [])
                if isinstance(task, dict)
            ],
            "protected_time": list(weekly_request.get("protected_time", [])),
            "no_meeting_windows": list(weekly_request.get("no_meeting_windows", [])),
            "assumptions": list(weekly_request.get("assumptions", [])),
            "warnings": list(weekly_request.get("warnings", [])),
        }

    def _proposal_projection(self, payload: dict[str, Any]) -> dict[str, object]:
        return {
            "proposal_summary": payload.get("proposal_summary"),
            "time_blocks": [
                {
                    "title": block.get("title"),
                    "task_title": block.get("task_title"),
                    "start": block.get("start"),
                    "end": block.get("end"),
                }
                for block in payload.get("time_blocks", [])
                if isinstance(block, dict)
            ],
            "proposed_changes": list(payload.get("proposed_changes", [])),
            "honored_constraints": list(payload.get("honored_constraints", [])),
            "assumptions": list(payload.get("assumptions", [])),
            "carry_forward_tasks": list(payload.get("carry_forward_tasks", [])),
            "rationale": list(payload.get("rationale", [])),
        }

    def _artifact_payload(self, artifact: WorkflowArtifactORM) -> dict[str, object]:
        return {
            "artifact_id": artifact.id,
            "artifact_type": artifact.artifact_type,
            "schema_version": artifact.schema_version,
            "version_number": artifact.version_number,
            "step_id": artifact.step_id,
            "producer_step_name": artifact.producer_step_name,
            "lineage_parent_id": artifact.lineage_parent_id,
            "supersedes_artifact_id": artifact.supersedes_artifact_id,
            "payload": artifact.payload,
            "created_at": artifact.created_at,
        }

    def _final_summary(self, artifact: WorkflowArtifactORM | None) -> dict[str, object]:
        if artifact is None:
            return {
                "artifact_id": None,
                "request_artifact_id": None,
                "intermediate_artifact_ids": [],
                "validation_artifact_ids": [],
                "final_summary_text": None,
                "approval_decision": None,
                "approval_decision_artifact_id": None,
                "downstream_sync_status": None,
                "downstream_sync_artifact_ids": [],
                "downstream_sync_reference_ids": [],
            }

        payload = artifact.payload
        return {
            "artifact_id": artifact.id,
            "request_artifact_id": payload.get("request_artifact_id"),
            "intermediate_artifact_ids": list(payload.get("intermediate_artifact_ids", [])),
            "validation_artifact_ids": list(payload.get("validation_artifact_ids", [])),
            "final_summary_text": payload.get("final_summary_text"),
            "approval_decision": payload.get("approval_decision"),
            "approval_decision_artifact_id": payload.get("approval_decision_artifact_id"),
            "downstream_sync_status": payload.get("downstream_sync_status"),
            "downstream_sync_artifact_ids": list(payload.get("downstream_sync_artifact_ids", [])),
            "downstream_sync_reference_ids": list(payload.get("downstream_sync_reference_ids", [])),
        }

    def _completion_summary(
        self,
        state: WorkflowRunState,
        *,
        failed_step,
        sync_projection: dict[str, object],
        proposal_versions: list[dict[str, object]],
        final_summary: dict[str, object],
    ) -> dict[str, object] | None:  # noqa: ANN001
        if state.run.workflow_type != "weekly_scheduling":
            return None
        if not proposal_versions:
            return None

        latest_proposal = proposal_versions[0]
        counts_by_target = sync_projection["sync"].get("counts_by_target", {})
        counts_by_state = sync_projection["sync"].get("counts_by_state", {})
        total_sync_writes = sum(counts_by_state.values())
        scheduled_highlights = [
            value
            for value in dict.fromkeys(
                block.get("task_title") or block.get("title")
                for block in latest_proposal.get("time_blocks", [])
                if isinstance(block, dict)
            )
            if isinstance(value, str)
        ]
        carry_forward_tasks = [
            str(item)
            for item in latest_proposal.get("carry_forward_tasks", [])
            if isinstance(item, str)
        ]
        attention_items: list[str] = []
        live_downstream_sync_status = self._live_downstream_sync_status(
            final_summary=final_summary,
            sync_projection=sync_projection,
        )
        failure_summary = self._failure_summary(state, failed_step, sync_projection)
        if failure_summary and state.run.status in {
            WorkflowRunStatus.FAILED.value,
            WorkflowRunStatus.TERMINATED.value,
        }:
            attention_items.append(failure_summary)
        elif live_downstream_sync_status not in {None, "succeeded"} and isinstance(
            sync_projection.get("failure_summary"), str
        ):
            attention_items.append(sync_projection["failure_summary"])
        attention_items.extend(carry_forward_tasks[:3])
        if sync_projection["safe_next_actions"]:
            labels = ", ".join(
                item["label"]
                for item in sync_projection["safe_next_actions"]
                if isinstance(item, dict) and isinstance(item.get("label"), str)
            )
            only_success_replay_option = (
                sync_projection.get("recovery_class") is None
                and state.run.status == WorkflowRunStatus.COMPLETED.value
                and all(
                    isinstance(item, dict) and item.get("action") == "request_replay"
                    for item in sync_projection["safe_next_actions"]
                )
            )
            if labels and not only_success_replay_option:
                attention_items.append(f"Next: {labels}.")

        return {
            "headline": self._completion_headline(
                state,
                final_summary=final_summary,
                sync_projection=sync_projection,
                scheduled_block_count=len(latest_proposal.get("time_blocks", [])),
                total_sync_writes=total_sync_writes,
            ),
            "approval_decision": final_summary.get("approval_decision"),
            "downstream_sync_status": live_downstream_sync_status,
            "scheduled_block_count": len(latest_proposal.get("time_blocks", [])),
            "scheduled_highlights": scheduled_highlights[:3],
            "total_sync_writes": total_sync_writes,
            "task_sync_writes": counts_by_target.get(WorkflowTargetSystem.TASK_SYSTEM.value, 0),
            "calendar_sync_writes": counts_by_target.get(
                WorkflowTargetSystem.CALENDAR_SYSTEM.value, 0
            ),
            "carry_forward_tasks": carry_forward_tasks,
            "attention_items": attention_items,
        }

    def _completion_headline(
        self,
        state: WorkflowRunState,
        *,
        final_summary: dict[str, object],
        sync_projection: dict[str, object],
        scheduled_block_count: int,
        total_sync_writes: int,
    ) -> str:
        if sync_projection.get("recovery_class") is not None:
            return f"Approved schedule needs downstream follow-up after {total_sync_writes} planned write(s)."

        downstream_sync_status = self._live_downstream_sync_status(
            final_summary=final_summary,
            sync_projection=sync_projection,
        )
        if (
            state.run.status == WorkflowRunStatus.COMPLETED.value
            and downstream_sync_status == "succeeded"
        ):
            return f"Scheduled {scheduled_block_count} block(s) and synced {total_sync_writes} approved write(s)."
        if state.run.status == WorkflowRunStatus.COMPLETED.value:
            return (
                f"Completed scheduling with downstream sync status "
                f"{downstream_sync_status or 'unknown'}."
            )
        if state.run.status in {WorkflowRunStatus.FAILED.value, WorkflowRunStatus.TERMINATED.value}:
            return f"Approved schedule needs downstream follow-up after {total_sync_writes} planned write(s)."
        if total_sync_writes:
            return f"Approved schedule is queued to sync {total_sync_writes} planned write(s)."
        return f"Prepared a proposal with {scheduled_block_count} scheduled block(s)."

    def _live_downstream_sync_status(
        self,
        *,
        final_summary: dict[str, object],
        sync_projection: dict[str, object],
    ) -> str | None:
        recovery_class = sync_projection.get("recovery_class")
        if isinstance(recovery_class, str) and recovery_class:
            return recovery_class
        downstream_sync_status = final_summary.get("downstream_sync_status")
        return downstream_sync_status if isinstance(downstream_sync_status, str) else None


def _approval_action_label(action: str) -> str:
    labels = {
        "approve": "Approve and continue",
        "reject": "Reject and close run",
        "request_revision": "Request revision and regenerate proposal",
    }
    return labels.get(action, action.replace("_", " ").title())


def build_workflow_run_create_input(
    *,
    workflow_type: str,
    first_step_name: str,
    request_text: str,
    submitted_by: str,
    channel: str,
    metadata: dict[str, Any] | None = None,
) -> WorkflowRunCreateInput:
    normalized_metadata = dict(metadata or {})
    normalized_workflow_type = workflow_type
    normalized_first_step = first_step_name
    if workflow_type == "weekly_scheduling":
        normalized_first_step = "dispatch_task_agent"
        weekly_request = parse_weekly_scheduling_request(request_text)
        normalized_metadata["weekly_request"] = weekly_request.model_dump(mode="json")
    return WorkflowRunCreateInput(
        workflow_type=normalized_workflow_type,
        first_step_name=normalized_first_step,
        request_text=request_text,
        submitted_by=submitted_by,
        channel=channel,
        metadata=normalized_metadata,
    )


def parse_weekly_scheduling_request(request_text: str) -> WeeklySchedulingRequest:
    text = " ".join(request_text.strip().split())
    sections = _extract_labeled_sections(text)
    warnings: list[str] = []
    assumptions: list[str] = []

    task_lines = _split_items(sections.get("tasks"))
    tasks = tuple(_parse_weekly_task(item) for item in task_lines if item)
    if not tasks:
        fallback_title = _infer_planning_goal(text) or "Weekly planning request"
        tasks = (
            WeeklyTaskRequest(
                title=fallback_title,
                details=text,
                source_line=text,
                warnings=(
                    "Parsed no explicit task list; treating the full brief as one planning item.",
                ),
            ),
        )
        warnings.append(
            "No explicit tasks parsed; Helm will plan around one synthesized planning item."
        )

    protected_time = tuple(_split_items(sections.get("protected time")))
    no_meeting_windows = tuple(_split_items(sections.get("no meeting windows")))

    constraints = _split_items(sections.get("constraints"))
    for item in constraints:
        lowered = item.lower()
        if any(token in lowered for token in ("protect", "deep work", "focus", "morning")):
            protected_time += (item,)
            continue
        if any(token in lowered for token in ("no meeting", "keep", "open", "avoid")):
            no_meeting_windows += (item,)
            continue
        assumptions.append(item)

    if not protected_time:
        assumptions.append(
            "No protected-time windows were supplied; schedule uses default daytime focus blocks."
        )
    if not no_meeting_windows:
        assumptions.append(
            "No no-meeting windows were supplied; only explicit protected blocks constrain placement."
        )

    return WeeklySchedulingRequest(
        raw_request_text=text,
        planning_goal=_infer_planning_goal(text),
        tasks=tasks,
        protected_time=tuple(dict.fromkeys(protected_time)),
        no_meeting_windows=tuple(dict.fromkeys(no_meeting_windows)),
        assumptions=tuple(dict.fromkeys(assumptions)),
        warnings=tuple(warnings),
    )


def _extract_labeled_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(
        re.finditer(
            r"(?i)\b(tasks?|constraints?|protected time|no meeting windows?)\s*:\s*",
            text,
        )
    )
    if not matches:
        return sections
    for index, match in enumerate(matches):
        key = match.group(1).lower().rstrip("s")
        if key == "task":
            key = "tasks"
        if key == "constraint":
            key = "constraints"
        if key == "no meeting window":
            key = "no meeting windows"
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[key] = text[start:end].strip(" ;")
    return sections


def _split_items(section: str | None) -> list[str]:
    if not section:
        return []
    raw_items = re.split(r"(?:\s*[;\n]\s*|\s*,\s*(?=[A-Z0-9-]))", section)
    return [item.strip(" -") for item in raw_items if item and item.strip(" -")]


def _parse_weekly_task(item: str) -> WeeklyTaskRequest:
    warnings: list[str] = []
    lowered = item.lower()

    priority = None
    for label in ("high", "medium", "low"):
        if re.search(rf"\b{label}\b", lowered):
            priority = label
            break
    if priority is None:
        warnings.append("Priority not provided.")

    deadline_match = re.search(r"\b(?:due|deadline|by)\s+([^,;()]+)", item, flags=re.IGNORECASE)
    deadline = deadline_match.group(1).strip() if deadline_match else None
    if deadline is not None:
        deadline = re.sub(
            r"\b\d+\s*(?:m|min|minutes|h|hr|hours)\b", "", deadline, flags=re.IGNORECASE
        ).strip()
    if deadline is None:
        warnings.append("Deadline not provided.")

    estimate_match = re.search(r"\b(\d+)\s*(m|min|minutes|h|hr|hours)\b", item, flags=re.IGNORECASE)
    estimated_minutes = None
    if estimate_match:
        amount = int(estimate_match.group(1))
        unit = estimate_match.group(2).lower()
        estimated_minutes = amount * 60 if unit.startswith("h") else amount
    else:
        warnings.append("Estimate not provided; default scheduling block will be used.")

    cleaned = re.sub(r"\([^)]*\)", "", item)
    cleaned = re.sub(r"\b(high|medium|low)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:due|deadline|by)\s+[^,;()]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d+\s*(?:m|min|minutes|h|hr|hours)\b", "", cleaned, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", cleaned).strip(" ,;-.")
    if not title:
        title = item.strip()

    return WeeklyTaskRequest(
        title=title,
        details=item,
        priority=priority,
        deadline=deadline,
        estimated_minutes=estimated_minutes,
        source_line=item,
        warnings=tuple(warnings),
    )


def _infer_planning_goal(text: str) -> str | None:
    if not text:
        return None
    match = re.match(r"(?i)(plan my week|plan the week|schedule my week)\b[:\- ]*(.*)", text)
    if match:
        detail = match.group(2).strip(" .")
        return detail or "Plan the week"
    return text.split(".")[0].strip() or None
