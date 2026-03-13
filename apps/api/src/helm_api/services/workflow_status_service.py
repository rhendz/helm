from __future__ import annotations

from dataclasses import dataclass

from helm_orchestration import WorkflowOrchestrationService
from helm_storage.models import WorkflowArtifactORM, WorkflowRunORM
from helm_storage.repositories import (
    RawRequestArtifactPayload,
    SQLAlchemyWorkflowArtifactRepository,
    SQLAlchemyWorkflowRunRepository,
    WorkflowArtifactType,
    WorkflowRunState,
    WorkflowRunStatus,
    WorkflowStepStatus,
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
    metadata: dict[str, str]


class WorkflowStatusService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._run_repo = SQLAlchemyWorkflowRunRepository(session)
        self._artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        self._orchestration = WorkflowOrchestrationService(session)

    def create_run(self, payload: WorkflowRunCreateInput) -> dict[str, object]:
        state = self._orchestration.create_run(
            workflow_type=payload.workflow_type,
            first_step_name=payload.first_step_name,
            request_payload=RawRequestArtifactPayload(
                request_text=payload.request_text,
                submitted_by=payload.submitted_by,
                channel=payload.channel,
                metadata=payload.metadata,
            ),
        )
        return self._build_summary(state)

    def list_runs(self, *, needs_action: bool | None = None, limit: int = 20) -> list[dict[str, object]]:
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

    def retry_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        return self._build_summary(self._orchestration.retry_current_step(run_id, reason=reason))

    def terminate_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        return self._build_summary(self._orchestration.terminate_run(run_id, reason=reason))

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
            )
            .order_by(WorkflowRunORM.started_at.desc(), WorkflowRunORM.id.desc())
        )
        if run_id is not None:
            stmt = stmt.where(WorkflowRunORM.id == run_id)
        return stmt

    def _build_summary(self, state: WorkflowRunState) -> dict[str, object]:
        failed_step = self._latest_failed_step(state)
        latest_validation_artifact = state.latest_artifacts.get(WorkflowArtifactType.VALIDATION_RESULT.value)
        latest_validation_outcome = None
        if latest_validation_artifact is not None:
            latest_validation_outcome = str(latest_validation_artifact.payload.get("outcome"))
        elif state.run.validation_outcome_summary:
            latest_validation_outcome = state.run.validation_outcome_summary

        paused_state, pause_reason = self._paused_state(state, failed_step)
        failure_kind = self._failure_kind(state, failed_step)
        failure_summary = self._failure_summary(state, failed_step)
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
            "last_event_summary": state.run.last_event_summary or (state.last_event.summary if state.last_event else None),
            "failure_summary": failure_summary,
            "failure_kind": failure_kind,
            "latest_validation_outcome": latest_validation_outcome,
            "retry_state": failed_step.retry_state if failed_step is not None else state.run.retry_state,
            "retryable": bool(failed_step.retryable) if failed_step is not None else False,
            "available_actions": self._available_actions(state, failed_step),
            "started_at": state.run.started_at,
            "updated_at": state.run.updated_at,
            "completed_at": state.run.completed_at,
        }

    def _build_lineage(self, run: WorkflowRunORM) -> dict[str, object]:
        artifacts = sorted(run.artifacts, key=lambda artifact: (artifact.created_at, artifact.id))
        raw_request = next(
            (artifact for artifact in artifacts if artifact.artifact_type == WorkflowArtifactType.RAW_REQUEST.value),
            None,
        )
        intermediate = [
            self._artifact_payload(artifact)
            for artifact in artifacts
            if artifact.artifact_type == WorkflowArtifactType.NORMALIZED_TASK.value
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

        actions = [{"action": "terminate", "label": "Terminate run"}]
        if failed_step is not None and (
            state.run.status == WorkflowRunStatus.BLOCKED.value or failed_step.retryable
        ):
            actions.insert(0, {"action": "retry", "label": "Retry current step"})
        return actions

    def _paused_state(self, state: WorkflowRunState, failed_step) -> tuple[str | None, str | None]:  # noqa: ANN001
        if state.run.status == WorkflowRunStatus.BLOCKED.value:
            return "blocked_validation", state.run.validation_outcome_summary or state.run.last_event_summary
        if state.run.status == WorkflowRunStatus.FAILED.value:
            return "awaiting_retry", state.run.execution_error_summary or state.run.last_event_summary
        return None, None

    def _failure_kind(self, state: WorkflowRunState, failed_step) -> str | None:  # noqa: ANN001
        if state.run.status == WorkflowRunStatus.BLOCKED.value:
            return "blocked_validation"
        if state.run.status == WorkflowRunStatus.FAILED.value:
            return "execution_failed"
        if failed_step is not None and failed_step.status == WorkflowStepStatus.VALIDATION_FAILED.value:
            return "blocked_validation"
        return None

    def _failure_summary(self, state: WorkflowRunState, failed_step) -> str | None:  # noqa: ANN001
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
            if step.status in {WorkflowStepStatus.FAILED.value, WorkflowStepStatus.VALIDATION_FAILED.value}
        ]
        if not failures:
            return None
        return max(failures, key=lambda step: (step.attempt_number, step.id))

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
