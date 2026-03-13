from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from helm_orchestration.schemas import (
    ApprovalAction,
    ApprovalCheckpointStatus,
    ApprovalDecision,
    ApprovalDecisionResult,
    ApprovalRequest,
    ApprovedSyncItem,
    CalendarSyncRequest,
    CalendarSyncResult,
    ExecutionFailurePayload,
    RecoveryClassification,
    RecoveryTransition,
    ReplayRequest,
    SyncLookupRequest,
    SyncLookupResult,
    SyncOutcomeStatus,
    SyncRetryDisposition,
    TaskSyncRequest,
    TaskSyncResult,
    RetryState,
    SCHEMA_VERSION,
    ScheduleProposalArtifact,
    SyncOperation,
    SyncTargetSystem,
    ValidationOutcome,
    ValidationReport,
    WorkflowSummaryArtifact,
)
from helm_orchestration.contracts import (
    CalendarSystemAdapter,
    TaskSystemAdapter,
    WorkflowSpecialistStep,
    WorkflowStepExecutionError,
)
from helm_orchestration.validators import ValidatorRegistry
from helm_storage.repositories import (
    ApprovalDecisionArtifactPayload,
    ApprovalRequestArtifactPayload,
    NewWorkflowApprovalCheckpoint,
    NewWorkflowArtifact,
    NewWorkflowEvent,
    NewWorkflowRun,
    NewWorkflowSpecialistInvocation,
    NewWorkflowStep,
    RevisionRequestArtifactPayload,
    SQLAlchemyWorkflowApprovalCheckpointRepository,
    SQLAlchemyWorkflowArtifactRepository,
    SQLAlchemyWorkflowEventRepository,
    SQLAlchemyReplayQueueRepository,
    SQLAlchemyWorkflowRunRepository,
    SQLAlchemyWorkflowSpecialistInvocationRepository,
    SQLAlchemyWorkflowSyncRecordRepository,
    SQLAlchemyWorkflowStepRepository,
    WorkflowArtifactType,
    WorkflowBlockedReason,
    WorkflowApprovalCheckpointPatch,
    WorkflowRunPatch,
    WorkflowRunState,
    WorkflowRunStatus,
    WorkflowSyncKind,
    WorkflowSyncPayload,
    WorkflowSyncRecoveryClassification,
    WorkflowSyncRecordPatch,
    WorkflowSyncStatus,
    WorkflowSyncStepQuery,
    WorkflowTargetSystem,
    NewWorkflowSyncRecord,
    WorkflowSpecialistInvocationPatch,
    WorkflowStepPatch,
    WorkflowStepStatus,
)
from sqlalchemy.orm import Session


class WorkflowOrchestrationService:
    def __init__(
        self,
        session: Session,
        *,
        validator_registry: ValidatorRegistry | None = None,
        task_system_adapter: TaskSystemAdapter | None = None,
        calendar_system_adapter: CalendarSystemAdapter | None = None,
    ) -> None:
        self._session = session
        self._run_repo = SQLAlchemyWorkflowRunRepository(session)
        self._step_repo = SQLAlchemyWorkflowStepRepository(session)
        self._artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        self._approval_repo = SQLAlchemyWorkflowApprovalCheckpointRepository(session)
        self._event_repo = SQLAlchemyWorkflowEventRepository(session)
        self._replay_queue_repo = SQLAlchemyReplayQueueRepository(session)
        self._invocation_repo = SQLAlchemyWorkflowSpecialistInvocationRepository(session)
        self._sync_repo = SQLAlchemyWorkflowSyncRecordRepository(session)
        self._validator_registry = validator_registry or ValidatorRegistry()
        self._task_system_adapter = task_system_adapter
        self._calendar_system_adapter = calendar_system_adapter

    def create_run(self, *, workflow_type: str, first_step_name: str, request_payload: object) -> WorkflowRunState:
        run = self._run_repo.create(
            NewWorkflowRun(
                workflow_type=workflow_type,
                status=WorkflowRunStatus.PENDING.value,
                current_step_name=first_step_name,
                current_step_attempt=1,
                attempt_count=1,
                last_event_summary="Workflow run created",
            )
        )
        self._step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name=first_step_name,
                status=WorkflowStepStatus.PENDING.value,
                attempt_number=1,
            )
        )
        self._artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run.id,
                artifact_type=WorkflowArtifactType.RAW_REQUEST.value,
                schema_version=SCHEMA_VERSION,
                payload=_payload_dict(request_payload),
            )
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run.id,
                event_type="run_created",
                run_status=WorkflowRunStatus.PENDING.value,
                step_status=WorkflowStepStatus.PENDING.value,
                summary="Workflow run created",
                details={"current_step_name": first_step_name},
            )
        )
        return self.get_run_state(run.id)

    def get_run_state(self, run_id: int) -> WorkflowRunState:
        state = self._run_repo.get_with_current_state(run_id)
        if state is None:
            raise ValueError(f"Workflow run {run_id} does not exist.")
        return state

    def start_current_step(self, run_id: int) -> WorkflowRunState:
        state = self.get_run_state(run_id)
        step = self._ensure_current_step(state)
        if step.status == WorkflowStepStatus.PENDING.value:
            self._step_repo.update(step.id, WorkflowStepPatch(status=WorkflowStepStatus.RUNNING.value))
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name=step.step_name,
                current_step_attempt=step.attempt_number,
                needs_action=False,
                last_event_summary=f"Started step {step.step_name}",
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=step.id,
                event_type="step_started",
                run_status=WorkflowRunStatus.RUNNING.value,
                step_status=WorkflowStepStatus.RUNNING.value,
                summary=f"Started step {step.step_name}",
                details={"step_name": step.step_name, "attempt_number": step.attempt_number},
            )
        )
        return self.get_run_state(run_id)

    def complete_current_step(
        self,
        run_id: int,
        *,
        artifact_type: str,
        artifact_payload: object,
        next_step_name: str | None = None,
    ) -> WorkflowRunState:
        state = self.start_current_step(run_id)
        step = self._require_current_step(state)
        return self._complete_started_step(
            run_id,
            step=step,
            artifact_type=artifact_type,
            artifact_payload=artifact_payload,
            next_step_name=next_step_name,
        )

    def execute_specialist_step(
        self,
        run_id: int,
        specialist_step: WorkflowSpecialistStep,
    ) -> WorkflowRunState:
        state = self.start_current_step(run_id)
        step = self._require_current_step(state)
        prepared_input = specialist_step.input_builder(state)
        invocation = self._invocation_repo.create(
            NewWorkflowSpecialistInvocation(
                run_id=run_id,
                step_id=step.id,
                specialist_name=specialist_step.specialist.value,
                input_artifact_id=prepared_input.input_artifact_id,
            )
        )

        try:
            output_payload = specialist_step.handler(prepared_input.payload)
        except WorkflowStepExecutionError as exc:
            self._invocation_repo.update(
                invocation.id,
                WorkflowSpecialistInvocationPatch(
                    status=WorkflowStepStatus.FAILED.value,
                    completed_at=_now(),
                    error_summary=exc.failure.message,
                ),
            )
            return self._fail_started_step(run_id, step=step, failure=exc.failure)
        except Exception as exc:  # noqa: BLE001
            failure = ExecutionFailurePayload(
                error_type="unhandled_step_exception",
                message=str(exc),
                retry_state=RetryState.RETRYABLE,
                retryable=True,
                details={
                    "step_name": step.step_name,
                    "workflow_type": state.run.workflow_type,
                    "specialist_name": specialist_step.specialist.value,
                },
            )
            self._invocation_repo.update(
                invocation.id,
                WorkflowSpecialistInvocationPatch(
                    status=WorkflowStepStatus.FAILED.value,
                    completed_at=_now(),
                    error_summary=failure.message,
                ),
            )
            return self._fail_started_step(run_id, step=step, failure=failure)

        return self._complete_started_step(
            run_id,
            step=step,
            artifact_type=specialist_step.artifact_type.value,
            artifact_payload=output_payload,
            next_step_name=specialist_step.next_step_name,
            invocation_id=invocation.id,
        )

    def submit_approval_decision(
        self,
        run_id: int,
        *,
        decision: ApprovalDecision,
        checkpoint_id: int | None = None,
    ) -> WorkflowRunState:
        state = self.get_run_state(run_id)
        checkpoint = state.active_approval_checkpoint
        if checkpoint_id is not None:
            checkpoint = self._approval_repo.get_by_id(checkpoint_id)
        if checkpoint is None or checkpoint.run_id != run_id or checkpoint.status != ApprovalCheckpointStatus.PENDING.value:
            raise ValueError(f"Workflow run {run_id} has no pending approval checkpoint.")
        if decision.action.value not in checkpoint.allowed_actions:
            raise ValueError(
                f"Approval action {decision.action.value} is not allowed for checkpoint {checkpoint.id}."
            )
        if decision.target_artifact_id != checkpoint.target_artifact_id:
            raise ValueError(
                f"Approval action targets artifact {decision.target_artifact_id}, "
                f"but checkpoint {checkpoint.id} is waiting on artifact {checkpoint.target_artifact_id}."
            )
        if decision.action is ApprovalAction.REQUEST_REVISION and not decision.revision_feedback:
            raise ValueError("Revision feedback is required when requesting a revision.")

        current_step = self._require_current_step(state)
        decision_time = _now()
        target_artifact = self._require_artifact(checkpoint.target_artifact_id)
        resolved = self._approval_repo.update(
            checkpoint.id,
            WorkflowApprovalCheckpointPatch(
                status=ApprovalCheckpointStatus.RESOLVED.value,
                decision=decision.action.value,
                decision_actor=decision.actor,
                decision_at=decision_time,
                revision_feedback=decision.revision_feedback,
                resolved_at=decision_time,
            ),
        )
        if resolved is None:
            raise ValueError(f"Approval checkpoint {checkpoint.id} no longer exists.")

        approval_request_artifact = self._artifact_repo.get_latest_for_run(
            run_id,
            artifact_type=WorkflowArtifactType.APPROVAL_REQUEST.value,
        )
        if approval_request_artifact is None:
            raise ValueError(f"Workflow run {run_id} has no approval request artifact.")

        self._artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run_id,
                step_id=current_step.id,
                artifact_type=WorkflowArtifactType.APPROVAL_DECISION.value,
                schema_version=SCHEMA_VERSION,
                producer_step_name=current_step.step_name,
                lineage_parent_id=approval_request_artifact.id,
                payload=ApprovalDecisionArtifactPayload(
                    checkpoint_id=resolved.id,
                    target_artifact_id=resolved.target_artifact_id,
                    target_version_number=target_artifact.version_number,
                    decision=decision.action.value,
                    actor=decision.actor,
                    decision_at=decision_time,
                    revision_feedback=decision.revision_feedback,
                ).to_dict(),
            )
        )

        result = ApprovalDecisionResult(
            checkpoint_id=resolved.id,
            action=decision.action,
            actor=decision.actor,
            target_artifact_id=resolved.target_artifact_id,
            decision_at=decision_time.isoformat(),
            resumed_step_name=None,
        )
        if decision.action is ApprovalAction.APPROVE:
            result = result.model_copy(update={"resumed_step_name": checkpoint.resume_step_name})
            return self._resume_from_approval_approval(
                run_id,
                current_step=current_step,
                checkpoint=resolved,
                result=result,
            )
        if decision.action is ApprovalAction.REJECT:
            return self._reject_after_approval(
                run_id,
                current_step=current_step,
                checkpoint=resolved,
                result=result,
            )
        result = result.model_copy(update={"resumed_step_name": checkpoint.step.step_name})
        return self._request_revision_after_approval(
            run_id,
            current_step=current_step,
            checkpoint=resolved,
            result=result,
        )

    def _complete_started_step(
        self,
        run_id: int,
        *,
        step,
        artifact_type: str,
        artifact_payload: object,
        next_step_name: str | None = None,
        invocation_id: int | None = None,
    ) -> WorkflowRunState:
        artifact_lineage = self._artifact_lineage_kwargs(
            run_id=run_id,
            step_name=step.step_name,
            artifact_type=artifact_type,
        )
        candidate_artifact = self._artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run_id,
                step_id=step.id,
                artifact_type=artifact_type,
                schema_version=SCHEMA_VERSION,
                producer_step_name=step.step_name,
                lineage_parent_id=artifact_lineage["lineage_parent_id"],
                supersedes_artifact_id=artifact_lineage["supersedes_artifact_id"],
                payload=_payload_dict(artifact_payload),
            )
        )

        validation_report = self._validate(step_name=step.step_name, artifact_type=artifact_type, payload=artifact_payload)
        validation_artifact_id: int | None = None
        if validation_report is not None:
            validation_artifact = self._artifact_repo.create(
                NewWorkflowArtifact(
                    run_id=run_id,
                    step_id=step.id,
                    artifact_type=WorkflowArtifactType.VALIDATION_RESULT.value,
                    schema_version=SCHEMA_VERSION,
                    producer_step_name=step.step_name,
                    lineage_parent_id=candidate_artifact.id,
                    payload=validation_report.model_dump(mode="json"),
                )
            )
            validation_artifact_id = validation_artifact.id

        if validation_report is not None and validation_report.outcome is ValidationOutcome.FAILED:
            self._mark_invocation(
                invocation_id,
                output_artifact_id=candidate_artifact.id,
                status=WorkflowStepStatus.VALIDATION_FAILED.value,
                error_summary=validation_report.summary,
            )
            self._step_repo.update(
                step.id,
                WorkflowStepPatch(
                    status=WorkflowStepStatus.VALIDATION_FAILED.value,
                    validation_outcome_summary=validation_report.summary,
                    failure_class="schema_validation_failed",
                    retry_state=RetryState.AWAITING_OPERATOR.value,
                    retryable=True,
                    completed_at=_now(),
                ),
            )
            self._run_repo.update(
                run_id,
                WorkflowRunPatch(
                    status=WorkflowRunStatus.BLOCKED.value,
                    current_step_name=step.step_name,
                    current_step_attempt=step.attempt_number,
                    needs_action=True,
                    validation_outcome_summary=validation_report.summary,
                    blocked_reason=WorkflowBlockedReason.VALIDATION_FAILED.value,
                    failure_class="schema_validation_failed",
                    retry_state=RetryState.AWAITING_OPERATOR.value,
                    resume_step_name=None,
                    resume_step_attempt=None,
                    last_event_summary=f"Validation blocked run at step {step.step_name}",
                ),
            )
            self._event_repo.create(
                NewWorkflowEvent(
                    run_id=run_id,
                    step_id=step.id,
                    event_type="validation_failed",
                    run_status=WorkflowRunStatus.BLOCKED.value,
                    step_status=WorkflowStepStatus.VALIDATION_FAILED.value,
                    summary=f"Validation blocked run at step {step.step_name}",
                    details={
                        "artifact_id": candidate_artifact.id,
                        "validation_artifact_id": validation_artifact_id,
                        "specialist_invocation_id": invocation_id,
                        "validation_report": validation_report.model_dump(mode="json"),
                    },
                )
            )
            return self.get_run_state(run_id)

        self._mark_invocation(
            invocation_id,
            output_artifact_id=candidate_artifact.id,
            status=WorkflowStepStatus.SUCCEEDED.value,
        )
        self._step_repo.update(
            step.id,
            WorkflowStepPatch(
                status=WorkflowStepStatus.SUCCEEDED.value,
                validation_outcome_summary=validation_report.outcome.value if validation_report else None,
                completed_at=_now(),
            ),
        )

        if artifact_type == WorkflowArtifactType.SCHEDULE_PROPOSAL.value:
            return self._create_approval_checkpoint(
                run_id,
                step=step,
                proposal_artifact_id=candidate_artifact.id,
                proposal_payload=artifact_payload,
                next_step_name=next_step_name,
                validation_artifact_id=validation_artifact_id,
                invocation_id=invocation_id,
            )

        if next_step_name is None:
            self._run_repo.update(
                run_id,
                WorkflowRunPatch(
                    status=WorkflowRunStatus.COMPLETED.value,
                    current_step_name=step.step_name,
                    current_step_attempt=step.attempt_number,
                    needs_action=False,
                    validation_outcome_summary=validation_report.outcome.value if validation_report else None,
                    blocked_reason=None,
                    last_event_summary=f"Completed step {step.step_name}",
                    completed_at=_now(),
                ),
            )
            self._event_repo.create(
                NewWorkflowEvent(
                    run_id=run_id,
                    step_id=step.id,
                    event_type="run_completed",
                    run_status=WorkflowRunStatus.COMPLETED.value,
                    step_status=WorkflowStepStatus.SUCCEEDED.value,
                    summary=f"Completed step {step.step_name}",
                    details={
                        "artifact_id": candidate_artifact.id,
                        "validation_artifact_id": validation_artifact_id,
                        "specialist_invocation_id": invocation_id,
                    },
                )
            )
            return self.get_run_state(run_id)

        next_step = self._step_repo.create(
            NewWorkflowStep(
                run_id=run_id,
                step_name=next_step_name,
                status=WorkflowStepStatus.PENDING.value,
                attempt_number=1,
            )
        )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.RUNNING.value,
                current_step_name=next_step_name,
                current_step_attempt=next_step.attempt_number,
                needs_action=False,
                validation_outcome_summary=validation_report.outcome.value if validation_report else None,
                execution_error_summary="",
                blocked_reason=None,
                failure_class="",
                retry_state="",
                resume_step_name=None,
                resume_step_attempt=None,
                last_event_summary=f"Advanced to step {next_step_name}",
                completed_at=None,
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=step.id,
                event_type="step_completed",
                run_status=WorkflowRunStatus.RUNNING.value,
                step_status=WorkflowStepStatus.SUCCEEDED.value,
                    summary=f"Advanced to step {next_step_name}",
                    details={
                        "artifact_id": candidate_artifact.id,
                        "validation_artifact_id": validation_artifact_id,
                        "specialist_invocation_id": invocation_id,
                        "next_step_name": next_step_name,
                    },
                )
            )
        return self.get_run_state(run_id)

    def fail_current_step(self, run_id: int, failure: ExecutionFailurePayload) -> WorkflowRunState:
        state = self.start_current_step(run_id)
        step = self._require_current_step(state)
        return self._fail_started_step(run_id, step=step, failure=failure)

    def _fail_started_step(self, run_id: int, *, step, failure: ExecutionFailurePayload) -> WorkflowRunState:
        self._step_repo.update(
            step.id,
            WorkflowStepPatch(
                status=WorkflowStepStatus.FAILED.value,
                execution_error_summary=failure.message,
                failure_class=failure.error_type,
                retry_state=failure.retry_state.value,
                retryable=failure.retryable,
                completed_at=_now(),
            ),
        )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.FAILED.value,
                current_step_name=step.step_name,
                current_step_attempt=step.attempt_number,
                needs_action=True,
                execution_error_summary=failure.message,
                blocked_reason=WorkflowBlockedReason.EXECUTION_FAILED.value,
                failure_class=failure.error_type,
                retry_state=failure.retry_state.value,
                resume_step_name=None,
                resume_step_attempt=None,
                last_event_summary=f"Execution failed at step {step.step_name}",
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=step.id,
                event_type="execution_failed",
                run_status=WorkflowRunStatus.FAILED.value,
                step_status=WorkflowStepStatus.FAILED.value,
                summary=f"Execution failed at step {step.step_name}",
                details=failure.model_dump(mode="json"),
            )
        )
        return self.get_run_state(run_id)

    def retry_current_step(self, run_id: int, *, reason: str) -> WorkflowRunState:
        state = self.get_run_state(run_id)
        failed_step = self._step_repo.get_last_failed_for_run(run_id)
        if failed_step is None:
            raise ValueError(f"Workflow run {run_id} has no failed step to retry.")
        if state.run.status == WorkflowRunStatus.FAILED.value and not failed_step.retryable:
            raise ValueError(f"Workflow run {run_id} failed terminally and cannot be retried.")

        next_attempt = failed_step.attempt_number + 1
        self._step_repo.create(
            NewWorkflowStep(
                run_id=run_id,
                step_name=failed_step.step_name,
                status=WorkflowStepStatus.PENDING.value,
                attempt_number=next_attempt,
            )
        )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.PENDING.value,
                current_step_name=failed_step.step_name,
                current_step_attempt=next_attempt,
                attempt_count=max(state.run.attempt_count + 1, next_attempt),
                needs_action=False,
                validation_outcome_summary="",
                execution_error_summary="",
                blocked_reason=None,
                failure_class="",
                retry_state=RetryState.RETRYABLE.value,
                resume_step_name=None,
                resume_step_attempt=None,
                last_event_summary=reason,
                completed_at=None,
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=failed_step.id,
                event_type="step_retry_requested",
                run_status=WorkflowRunStatus.PENDING.value,
                step_status=WorkflowStepStatus.PENDING.value,
                summary=reason,
                details={
                    "step_name": failed_step.step_name,
                    "previous_attempt": failed_step.attempt_number,
                    "next_attempt": next_attempt,
                },
            )
        )
        for sync_record in self._sync_repo.list_for_step_attempt(
            WorkflowSyncStepQuery(
                run_id=run_id,
                step_name=failed_step.step_name,
                max_attempt_number=failed_step.attempt_number,
                statuses=(
                    WorkflowSyncStatus.FAILED_RETRYABLE.value,
                    WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                ),
            )
        ):
            self._sync_repo.update(
                sync_record.id,
                WorkflowSyncRecordPatch(
                    recovery_classification=WorkflowSyncRecoveryClassification.RETRY_REQUESTED.value,
                    recovery_updated_at=_now(),
                ),
            )
        return self.get_run_state(run_id)

    def request_sync_replay(
        self,
        run_id: int,
        *,
        actor: str,
        sync_record_ids: tuple[int, ...],
        reason: str,
    ) -> WorkflowRunState:
        if not sync_record_ids:
            raise ValueError("Replay requires at least one sync record.")
        state = self.get_run_state(run_id)
        current_step = self._require_current_step(state)
        requested_at = _now()
        replay_records: list[object] = []

        for sync_record_id in sync_record_ids:
            original = self._sync_repo.get_by_id(sync_record_id)
            if original is None or original.run_id != run_id:
                raise ValueError(f"Workflow sync record {sync_record_id} does not exist for run {run_id}.")
            replay_queue_item, _ = self._replay_queue_repo.enqueue_workflow_sync_replay(
                run_id=run_id,
                sync_record_id=sync_record_id,
            )
            replay_record = self._sync_repo.create(
                NewWorkflowSyncRecord(
                    run_id=run_id,
                    step_id=current_step.id,
                    proposal_artifact_id=original.proposal_artifact_id,
                    proposal_version_number=original.proposal_version_number,
                    target_system=original.target_system,
                    sync_kind=original.sync_kind,
                    planned_item_key=original.planned_item_key,
                    execution_order=original.execution_order,
                    idempotency_key=f"{original.idempotency_key}:replay:{original.lineage_generation + 1}",
                    payload_fingerprint=original.payload_fingerprint,
                    payload=original.payload,
                    status=WorkflowSyncStatus.PENDING.value,
                    lineage_generation=original.lineage_generation + 1,
                    recovery_classification=WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value,
                    recovery_updated_at=requested_at,
                    replay_requested_at=requested_at,
                    replay_requested_by=actor,
                    supersedes_sync_record_id=original.id,
                    replayed_from_sync_record_id=original.id,
                )
            )
            self._sync_repo.update(
                original.id,
                WorkflowSyncRecordPatch(
                    recovery_classification=WorkflowSyncRecoveryClassification.REPLAY_REQUESTED.value,
                    recovery_updated_at=requested_at,
                    replay_requested_at=requested_at,
                    replay_requested_by=actor,
                    supersedes_sync_record_id=replay_record.id,
                ),
            )
            replay_records.append(replay_record)
            self._event_repo.create(
                NewWorkflowEvent(
                    run_id=run_id,
                    step_id=current_step.id,
                    event_type="sync_replay_enqueued",
                    run_status=state.run.status,
                    step_status=current_step.status,
                    summary=f"Replay requested for {original.planned_item_key}.",
                    details={
                        "sync_record_id": original.id,
                        "replay_sync_record_id": replay_record.id,
                        "replay_queue_id": replay_queue_item.id,
                        "actor": actor,
                        "reason": reason,
                    },
                )
            )

        replay_request = ReplayRequest(
            run_id=run_id,
            actor=actor,
            requested_at=requested_at.isoformat(),
            reason=reason,
            source_sync_record_ids=sync_record_ids,
            replay_sync_record_ids=tuple(record.id for record in replay_records),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=current_step.id,
                event_type="sync_replay_requested",
                run_status=state.run.status,
                step_status=current_step.status,
                summary="Explicit sync replay requested.",
                details=replay_request.model_dump(mode="json"),
            )
        )
        return self.get_run_state(run_id)

    def terminate_run(self, run_id: int, *, reason: str) -> WorkflowRunState:
        state = self.get_run_state(run_id)
        current_step = state.current_step
        partial_sync_snapshot = self._terminate_pending_sync_records(run_id, reason=reason)
        if current_step is not None and current_step.status in {
            WorkflowStepStatus.PENDING.value,
            WorkflowStepStatus.RUNNING.value,
        }:
            self._step_repo.update(
                current_step.id,
                WorkflowStepPatch(
                    status=WorkflowStepStatus.CANCELLED.value,
                    completed_at=_now(),
                ),
            )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.TERMINATED.value,
                needs_action=False,
                blocked_reason=None,
                retry_state=RetryState.TERMINAL.value,
                resume_step_name=None,
                resume_step_attempt=None,
                last_event_summary=reason,
                completed_at=_now(),
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=current_step.id if current_step is not None else None,
                event_type="run_terminated",
                run_status=WorkflowRunStatus.TERMINATED.value,
                step_status=WorkflowStepStatus.CANCELLED.value if current_step is not None else None,
                summary=reason,
                details={"reason": reason, **partial_sync_snapshot},
            )
        )
        return self.get_run_state(run_id)

    def _create_approval_checkpoint(
        self,
        run_id: int,
        *,
        step,
        proposal_artifact_id: int,
        proposal_payload: object,
        next_step_name: str | None,
        validation_artifact_id: int | None,
        invocation_id: int | None,
    ) -> WorkflowRunState:
        if next_step_name is None:
            raise ValueError("Schedule proposal steps must declare the persisted step after approval.")

        prior_approval_step = self._step_repo.get_last_for_run(run_id, step_name="await_schedule_approval")
        next_approval_attempt = 1 if prior_approval_step is None else prior_approval_step.attempt_number + 1
        approval_step = self._step_repo.create(
            NewWorkflowStep(
                run_id=run_id,
                step_name="await_schedule_approval",
                status=WorkflowStepStatus.PENDING.value,
                attempt_number=next_approval_attempt,
            )
        )
        checkpoint = self._approval_repo.create(
            NewWorkflowApprovalCheckpoint(
                run_id=run_id,
                step_id=approval_step.id,
                target_artifact_id=proposal_artifact_id,
                resume_step_name=next_step_name,
                allowed_actions=(
                    ApprovalAction.APPROVE.value,
                    ApprovalAction.REJECT.value,
                    ApprovalAction.REQUEST_REVISION.value,
                ),
            )
        )
        proposal = _payload_dict(proposal_payload)
        pause_reason = "Awaiting operator approval before downstream changes."
        self._artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run_id,
                step_id=approval_step.id,
                artifact_type=WorkflowArtifactType.APPROVAL_REQUEST.value,
                schema_version=SCHEMA_VERSION,
                producer_step_name=approval_step.step_name,
                lineage_parent_id=proposal_artifact_id,
                payload=ApprovalRequestArtifactPayload(
                    checkpoint_id=checkpoint.id,
                    target_artifact_id=proposal_artifact_id,
                    target_version_number=self._require_artifact(proposal_artifact_id).version_number,
                    allowed_actions=(
                        ApprovalAction.APPROVE.value,
                        ApprovalAction.REJECT.value,
                        ApprovalAction.REQUEST_REVISION.value,
                    ),
                    pause_reason=pause_reason,
                ).to_dict(),
            )
        )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.BLOCKED.value,
                current_step_name=approval_step.step_name,
                current_step_attempt=approval_step.attempt_number,
                needs_action=True,
                validation_outcome_summary=None,
                execution_error_summary=None,
                blocked_reason=WorkflowBlockedReason.APPROVAL_REQUIRED.value,
                failure_class=None,
                retry_state=RetryState.AWAITING_OPERATOR.value,
                resume_step_name=next_step_name,
                resume_step_attempt=1,
                last_event_summary="Awaiting approval for schedule proposal.",
                completed_at=None,
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=approval_step.id,
                event_type="approval_checkpoint_created",
                run_status=WorkflowRunStatus.BLOCKED.value,
                step_status=WorkflowStepStatus.PENDING.value,
                summary="Awaiting approval for schedule proposal.",
                details={
                    "checkpoint_id": checkpoint.id,
                    "proposal_artifact_id": proposal_artifact_id,
                    "validation_artifact_id": validation_artifact_id,
                    "specialist_invocation_id": invocation_id,
                    "proposal_summary": proposal.get("proposal_summary"),
                    "resume_step_name": next_step_name,
                },
            )
        )
        return self.get_run_state(run_id)

    def _resume_from_approval_approval(
        self,
        run_id: int,
        *,
        current_step,
        checkpoint,
        result: ApprovalDecisionResult,
    ) -> WorkflowRunState:
        self._step_repo.update(
            current_step.id,
            WorkflowStepPatch(status=WorkflowStepStatus.SUCCEEDED.value, completed_at=_now()),
        )
        next_step = self._step_repo.create(
            NewWorkflowStep(
                run_id=run_id,
                step_name=checkpoint.resume_step_name,
                status=WorkflowStepStatus.PENDING.value,
                attempt_number=checkpoint.resume_step_attempt,
            )
        )
        sync_records = self.prepare_approved_sync_plan(
            run_id,
            proposal_artifact_id=checkpoint.target_artifact_id,
            step_id=next_step.id,
        )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.PENDING.value,
                current_step_name=next_step.step_name,
                current_step_attempt=next_step.attempt_number,
                needs_action=False,
                validation_outcome_summary=None,
                execution_error_summary=None,
                blocked_reason=None,
                failure_class=None,
                retry_state=RetryState.RETRYABLE.value,
                resume_step_name=None,
                resume_step_attempt=None,
                last_event_summary="Approval granted and workflow resumed.",
                completed_at=None,
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=current_step.id,
                event_type="approval_decision_recorded",
                run_status=WorkflowRunStatus.PENDING.value,
                step_status=WorkflowStepStatus.SUCCEEDED.value,
                summary="Approval granted and workflow resumed.",
                details=result.model_dump(mode="json"),
            )
        )
        return self.get_run_state(run_id)

    def prepare_approved_sync_plan(
        self,
        run_id: int,
        *,
        proposal_artifact_id: int,
        step_id: int,
    ) -> tuple[object, ...]:
        proposal_artifact = self._require_artifact(proposal_artifact_id)
        existing_records = tuple(self._sync_repo.list_for_proposal(proposal_artifact_id))
        if existing_records:
            return existing_records

        sync_items = self._build_approved_sync_items(proposal_artifact_id=proposal_artifact_id)
        persisted_records = tuple(
            self._sync_repo.create(
                NewWorkflowSyncRecord(
                    run_id=run_id,
                    step_id=step_id,
                    proposal_artifact_id=item.proposal_artifact_id,
                    proposal_version_number=item.proposal_version_number,
                    target_system=item.target_system.value,
                    sync_kind=_sync_kind_for_operation(item.operation).value,
                    planned_item_key=item.planned_item_key,
                    execution_order=item.execution_order,
                    idempotency_key=_sync_idempotency_key(item),
                    payload_fingerprint=item.payload_fingerprint,
                    payload=WorkflowSyncPayload(
                        proposal_artifact_id=item.proposal_artifact_id,
                        proposal_version_number=item.proposal_version_number,
                        target_system=item.target_system.value,
                        sync_kind=_sync_kind_for_operation(item.operation).value,
                        planned_item_key=item.planned_item_key,
                        payload=item.payload,
                        payload_fingerprint=item.payload_fingerprint,
                    ).to_dict(),
                )
            )
            for item in sync_items
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=step_id,
                event_type="approved_sync_manifest_created",
                run_status=WorkflowRunStatus.PENDING.value,
                step_status=WorkflowStepStatus.PENDING.value,
                summary="Prepared approved sync manifest from the approved proposal.",
                details={
                    "proposal_artifact_id": proposal_artifact_id,
                    "proposal_version_number": proposal_artifact.version_number,
                    "sync_record_ids": [record.id for record in persisted_records],
                    "task_sync_count": len(
                        [
                            record
                            for record in persisted_records
                            if record.target_system == WorkflowTargetSystem.TASK_SYSTEM.value
                        ]
                    ),
                    "calendar_sync_count": len(
                        [
                            record
                            for record in persisted_records
                            if record.target_system == WorkflowTargetSystem.CALENDAR_SYSTEM.value
                        ]
                    ),
                },
            )
        )
        return persisted_records

    def execute_pending_sync_step(self, run_id: int) -> WorkflowRunState:
        state = self.get_run_state(run_id)
        if state.run.status == WorkflowRunStatus.TERMINATED.value:
            raise ValueError(f"Workflow run {run_id} is terminated and cannot execute sync steps.")
        state = self.start_current_step(run_id)
        step = self._require_current_step(state)
        if step.step_name != "apply_schedule":
            raise ValueError(f"Workflow run {run_id} is not at a sync execution step.")

        while True:
            next_records = self._sync_repo.list_for_step_attempt(
                WorkflowSyncStepQuery(
                    run_id=run_id,
                    step_name=step.step_name,
                    max_attempt_number=step.attempt_number,
                    statuses=(
                        WorkflowSyncStatus.PENDING.value,
                        WorkflowSyncStatus.FAILED_RETRYABLE.value,
                        WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                    ),
                )
            )
            if not next_records:
                return self._complete_sync_execution(run_id, step=step)

            sync_record = next_records[0]
            prior_status = sync_record.status
            claimed = self._sync_repo.mark_attempt_started(sync_record.id, step_id=step.id)
            if claimed is None:
                raise ValueError(f"Workflow sync record {sync_record.id} no longer exists.")

            if prior_status == WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value:
                reconciliation = self._reconcile_sync_record(claimed)
                if reconciliation.found or reconciliation.payload_fingerprint_matches:
                    self._sync_repo.mark_succeeded(
                        claimed.id,
                        external_object_id=reconciliation.external_object_id or claimed.external_object_id,
                    )
                    self._event_repo.create(
                        NewWorkflowEvent(
                            run_id=run_id,
                            step_id=step.id,
                            event_type="sync_record_reconciled",
                            run_status=WorkflowRunStatus.RUNNING.value,
                            step_status=WorkflowStepStatus.RUNNING.value,
                            summary=f"Reconciled sync record {claimed.planned_item_key}.",
                            details={
                                "sync_record_id": claimed.id,
                                "planned_item_key": claimed.planned_item_key,
                                "external_object_id": reconciliation.external_object_id,
                                "provider_state": reconciliation.provider_state,
                            },
                        )
                    )
                    continue

            result = self._dispatch_sync_record(claimed)
            if result.status is SyncOutcomeStatus.SUCCEEDED:
                self._sync_repo.mark_succeeded(
                    claimed.id,
                    external_object_id=result.external_object_id or claimed.external_object_id,
                )
                continue

            if result.status is SyncOutcomeStatus.RECONCILIATION_REQUIRED:
                self._sync_repo.mark_failed(
                    claimed.id,
                    status=WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                    error_summary=result.error_summary,
                    external_object_id=result.external_object_id or claimed.external_object_id,
                    recovery_classification=WorkflowSyncRecoveryClassification.RECOVERABLE_FAILURE.value,
                )
                self._record_recovery_transition(
                    run_id=run_id,
                    step_id=step.id,
                    transition=RecoveryTransition(
                        sync_record_id=claimed.id,
                        planned_item_key=claimed.planned_item_key,
                        classification=RecoveryClassification.RECOVERABLE_FAILURE,
                        prior_status=prior_status,
                        next_status=WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
                        details={"target_system": claimed.target_system},
                    ),
                )
                return self._fail_started_step(
                    run_id,
                    step=step,
                    failure=ExecutionFailurePayload(
                        error_type="sync_write_outcome_uncertain",
                        message=result.error_summary or "Sync write outcome is uncertain and requires reconciliation.",
                        retry_state=RetryState.RETRYABLE,
                        retryable=True,
                        details={
                            "sync_record_id": claimed.id,
                            "planned_item_key": claimed.planned_item_key,
                            "target_system": claimed.target_system,
                        },
                    ),
                )

            failure_status = (
                WorkflowSyncStatus.FAILED_RETRYABLE.value
                if result.status is SyncOutcomeStatus.RETRYABLE_FAILURE
                else WorkflowSyncStatus.FAILED_TERMINAL.value
            )
            retryable = result.status is SyncOutcomeStatus.RETRYABLE_FAILURE
            retry_state = RetryState.RETRYABLE if retryable else RetryState.TERMINAL
            self._sync_repo.mark_failed(
                claimed.id,
                status=failure_status,
                error_summary=result.error_summary,
                external_object_id=result.external_object_id or claimed.external_object_id,
                recovery_classification=(
                    WorkflowSyncRecoveryClassification.RECOVERABLE_FAILURE.value
                    if retryable
                    else WorkflowSyncRecoveryClassification.TERMINAL_FAILURE.value
                ),
            )
            self._record_recovery_transition(
                run_id=run_id,
                step_id=step.id,
                transition=RecoveryTransition(
                    sync_record_id=claimed.id,
                    planned_item_key=claimed.planned_item_key,
                    classification=(
                        RecoveryClassification.RECOVERABLE_FAILURE
                        if retryable
                        else RecoveryClassification.TERMINAL_FAILURE
                    ),
                    prior_status=prior_status,
                    next_status=failure_status,
                    details={"target_system": claimed.target_system},
                ),
            )
            return self._fail_started_step(
                run_id,
                step=step,
                failure=ExecutionFailurePayload(
                    error_type="sync_execution_failed",
                    message=result.error_summary or f"Sync execution failed for {claimed.planned_item_key}.",
                    retry_state=retry_state,
                    retryable=retryable,
                    details={
                        "sync_record_id": claimed.id,
                        "planned_item_key": claimed.planned_item_key,
                        "target_system": claimed.target_system,
                    },
                ),
            )

    def _reject_after_approval(
        self,
        run_id: int,
        *,
        current_step,
        checkpoint,
        result: ApprovalDecisionResult,
    ) -> WorkflowRunState:
        self._step_repo.update(
            current_step.id,
            WorkflowStepPatch(status=WorkflowStepStatus.CANCELLED.value, completed_at=_now()),
        )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.TERMINATED.value,
                current_step_name=current_step.step_name,
                current_step_attempt=current_step.attempt_number,
                needs_action=False,
                validation_outcome_summary=None,
                execution_error_summary=None,
                blocked_reason=None,
                failure_class=None,
                retry_state=RetryState.TERMINAL.value,
                resume_step_name=None,
                resume_step_attempt=None,
                last_event_summary="Approval rejected and workflow closed.",
                completed_at=_now(),
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=current_step.id,
                event_type="approval_decision_recorded",
                run_status=WorkflowRunStatus.TERMINATED.value,
                step_status=WorkflowStepStatus.CANCELLED.value,
                summary="Approval rejected and workflow closed.",
                details=result.model_dump(mode="json"),
            )
        )
        return self.get_run_state(run_id)

    def _request_revision_after_approval(
        self,
        run_id: int,
        *,
        current_step,
        checkpoint,
        result: ApprovalDecisionResult,
    ) -> WorkflowRunState:
        self._step_repo.update(
            current_step.id,
            WorkflowStepPatch(status=WorkflowStepStatus.CANCELLED.value, completed_at=_now()),
        )
        proposal_artifact = self._artifact_repo.get_by_id(checkpoint.target_artifact_id)
        if proposal_artifact is None:
            raise ValueError(f"Schedule proposal artifact {checkpoint.target_artifact_id} does not exist.")
        self._artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run_id,
                step_id=current_step.id,
                artifact_type=WorkflowArtifactType.REVISION_REQUEST.value,
                schema_version=SCHEMA_VERSION,
                producer_step_name=current_step.step_name,
                lineage_parent_id=checkpoint.target_artifact_id,
                payload=RevisionRequestArtifactPayload(
                    checkpoint_id=checkpoint.id,
                    target_artifact_id=checkpoint.target_artifact_id,
                    target_version_number=proposal_artifact.version_number,
                    feedback=checkpoint.revision_feedback or "",
                ).to_dict(),
            )
        )
        prior_attempt = self._step_repo.get_last_for_run(run_id, step_name=proposal_artifact.producer_step_name)
        next_attempt = 1 if prior_attempt is None else prior_attempt.attempt_number + 1
        revision_step = self._step_repo.create(
            NewWorkflowStep(
                run_id=run_id,
                step_name=proposal_artifact.producer_step_name or checkpoint.resume_step_name,
                status=WorkflowStepStatus.PENDING.value,
                attempt_number=next_attempt,
            )
        )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.PENDING.value,
                current_step_name=revision_step.step_name,
                current_step_attempt=revision_step.attempt_number,
                attempt_count=max(self.get_run_state(run_id).run.attempt_count + 1, revision_step.attempt_number),
                needs_action=False,
                validation_outcome_summary=None,
                execution_error_summary=None,
                blocked_reason=None,
                failure_class=None,
                retry_state=RetryState.RETRYABLE.value,
                resume_step_name=None,
                resume_step_attempt=None,
                last_event_summary="Revision requested and workflow resumed at proposal generation.",
                completed_at=None,
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=current_step.id,
                event_type="approval_decision_recorded",
                run_status=WorkflowRunStatus.PENDING.value,
                step_status=WorkflowStepStatus.CANCELLED.value,
                summary="Revision requested and workflow resumed at proposal generation.",
                details=result.model_dump(mode="json"),
            )
        )
        return self.get_run_state(run_id)

    def build_final_summary_artifact(self, run_id: int, *, final_summary_text: str) -> WorkflowSummaryArtifact:
        state = self.get_run_state(run_id)
        latest_artifacts = state.latest_artifacts
        request_artifact = latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
        run_artifacts = self._artifact_repo.list_for_run(run_id)
        validation_ids = tuple(
            artifact.id
            for artifact in run_artifacts
            if artifact.artifact_type == WorkflowArtifactType.VALIDATION_RESULT.value
        )
        intermediate_ids = tuple(
            artifact.id
            for artifact in run_artifacts
            if artifact.artifact_type
            in {
                WorkflowArtifactType.NORMALIZED_TASK.value,
                WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
            }
        )
        approval_decision_artifact = max(
            (
                artifact
                for artifact in run_artifacts
                if artifact.artifact_type == WorkflowArtifactType.APPROVAL_DECISION.value
            ),
            key=lambda artifact: artifact.id,
            default=None,
        )
        sync_records = []
        approval_decision = None
        approval_decision_artifact_id = None
        if approval_decision_artifact is not None:
            approval_decision = approval_decision_artifact.payload.get("decision")
            approval_decision_artifact_id = approval_decision_artifact.id
            target_artifact_id = approval_decision_artifact.payload.get("target_artifact_id")
            if isinstance(target_artifact_id, int):
                sync_records = self._sync_repo.list_for_proposal(target_artifact_id)

        return WorkflowSummaryArtifact(
            request_artifact_id=request_artifact.id,
            intermediate_artifact_ids=intermediate_ids,
            validation_artifact_ids=validation_ids,
            final_summary_text=final_summary_text,
            approval_decision=approval_decision,
            approval_decision_artifact_id=approval_decision_artifact_id,
            downstream_sync_status=self._downstream_sync_status(sync_records),
            downstream_sync_artifact_ids=tuple(record.id for record in self._sorted_sync_records(sync_records)),
            downstream_sync_reference_ids=tuple(
                self._downstream_sync_reference_id(record)
                for record in self._sorted_sync_records(sync_records)
            ),
        )

    def _downstream_sync_status(self, sync_records: list[object]) -> str | None:
        if not sync_records:
            return None
        statuses = {record.status for record in sync_records}
        if statuses == {WorkflowSyncStatus.SUCCEEDED.value}:
            return "succeeded"
        if statuses == {WorkflowSyncStatus.CANCELLED.value}:
            return "cancelled"
        if statuses & {WorkflowSyncStatus.PENDING.value, WorkflowSyncStatus.IN_PROGRESS.value}:
            return "pending"
        if statuses & {
            WorkflowSyncStatus.FAILED_RETRYABLE.value,
            WorkflowSyncStatus.FAILED_TERMINAL.value,
            WorkflowSyncStatus.UNCERTAIN_NEEDS_RECONCILIATION.value,
        }:
            if WorkflowSyncStatus.SUCCEEDED.value in statuses or WorkflowSyncStatus.CANCELLED.value in statuses:
                return "partial"
            return "failed"
        return "mixed"

    def _sorted_sync_records(self, sync_records: list[object]) -> list[object]:
        return sorted(sync_records, key=lambda record: (record.execution_order, record.id))

    def _downstream_sync_reference_id(self, sync_record) -> str:  # noqa: ANN001
        reference = sync_record.external_object_id or sync_record.planned_item_key
        return f"{sync_record.target_system}:{reference}"

    def _build_approved_sync_items(self, *, proposal_artifact_id: int) -> tuple[ApprovedSyncItem, ...]:
        proposal_artifact = self._require_artifact(proposal_artifact_id)
        proposal = ScheduleProposalArtifact.model_validate(proposal_artifact.payload)
        sync_items: list[ApprovedSyncItem] = []
        execution_order = 1

        seen_task_keys: set[str] = set()
        for block in proposal.time_blocks:
            task_title = block.task_title or block.title
            task_key = f"task:{_slugify(task_title)}"
            if task_key in seen_task_keys:
                continue
            seen_task_keys.add(task_key)
            task_payload = {"title": task_title, "proposal_artifact_id": proposal_artifact.id}
            sync_items.append(
                ApprovedSyncItem(
                    proposal_artifact_id=proposal_artifact.id,
                    proposal_version_number=proposal_artifact.version_number,
                    target_system=SyncTargetSystem.TASK_SYSTEM,
                    operation=SyncOperation.TASK_UPSERT,
                    planned_item_key=task_key,
                    execution_order=execution_order,
                    payload_fingerprint=_payload_fingerprint(task_payload),
                    payload=task_payload,
                )
            )
            execution_order += 1

        for index, block in enumerate(proposal.time_blocks, start=1):
            calendar_payload = {
                "title": block.title,
                "start": block.start,
                "end": block.end,
                "task_title": block.task_title,
                "calendar_id": proposal.calendar_id,
            }
            sync_items.append(
                ApprovedSyncItem(
                    proposal_artifact_id=proposal_artifact.id,
                    proposal_version_number=proposal_artifact.version_number,
                    target_system=SyncTargetSystem.CALENDAR_SYSTEM,
                    operation=SyncOperation.CALENDAR_BLOCK_UPSERT,
                    planned_item_key=f"calendar:{_slugify(block.title)}:{index}",
                    execution_order=execution_order,
                    payload_fingerprint=_payload_fingerprint(calendar_payload),
                    payload=calendar_payload,
                )
            )
            execution_order += 1

        return tuple(sync_items)

    def _complete_sync_execution(self, run_id: int, *, step) -> WorkflowRunState:
        sync_records = self._sync_repo.list_for_run(run_id)
        if self.get_run_state(run_id).run.workflow_type == "weekly_scheduling":
            summary_text = self._build_representative_completion_summary_text(sync_records)
            final_summary = self.build_final_summary_artifact(run_id, final_summary_text=summary_text)
            if self._artifact_repo.get_latest_for_run(run_id, artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value) is None:
                self._artifact_repo.create(
                    NewWorkflowArtifact(
                        run_id=run_id,
                        step_id=step.id,
                        artifact_type=WorkflowArtifactType.FINAL_SUMMARY.value,
                        schema_version=SCHEMA_VERSION,
                        producer_step_name=step.step_name,
                        payload=final_summary.model_dump(mode="json"),
                    )
                )
        self._step_repo.update(
            step.id,
            WorkflowStepPatch(
                status=WorkflowStepStatus.SUCCEEDED.value,
                completed_at=_now(),
            ),
        )
        self._run_repo.update(
            run_id,
            WorkflowRunPatch(
                status=WorkflowRunStatus.COMPLETED.value,
                current_step_name=step.step_name,
                current_step_attempt=step.attempt_number,
                needs_action=False,
                execution_error_summary=None,
                blocked_reason=None,
                failure_class=None,
                retry_state=None,
                resume_step_name=None,
                resume_step_attempt=None,
                last_event_summary=f"Completed step {step.step_name}",
                completed_at=_now(),
            ),
        )
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=step.id,
                event_type="run_completed",
                run_status=WorkflowRunStatus.COMPLETED.value,
                step_status=WorkflowStepStatus.SUCCEEDED.value,
                summary=f"Completed step {step.step_name}",
                details={
                    "sync_record_ids": [record.id for record in sync_records],
                    "succeeded_sync_record_ids": [
                        record.id
                        for record in sync_records
                        if record.status == WorkflowSyncStatus.SUCCEEDED.value
                    ],
                },
            )
        )
        return self.get_run_state(run_id)

    def _build_representative_completion_summary_text(self, sync_records: list[object]) -> str:
        sorted_sync_records = self._sorted_sync_records(sync_records)
        if not sorted_sync_records:
            return "Approved schedule finished without persisted downstream sync lineage."

        proposal_artifact = self._require_artifact(sorted_sync_records[0].proposal_artifact_id)
        proposal = ScheduleProposalArtifact.model_validate(proposal_artifact.payload)
        scheduled_highlights = tuple(
            dict.fromkeys(block.task_title or block.title for block in proposal.time_blocks)
        )
        task_writes = len(
            [record for record in sorted_sync_records if record.target_system == WorkflowTargetSystem.TASK_SYSTEM.value]
        )
        calendar_writes = len(
            [
                record
                for record in sorted_sync_records
                if record.target_system == WorkflowTargetSystem.CALENDAR_SYSTEM.value
            ]
        )
        summary = (
            f"Scheduled {len(proposal.time_blocks)} block(s) across {len(scheduled_highlights)} focus area(s) "
            f"and synced {len(sorted_sync_records)} approved write(s) "
            f"({task_writes} task, {calendar_writes} calendar)."
        )
        if proposal.carry_forward_tasks:
            return f"{summary} Carry forward: {', '.join(proposal.carry_forward_tasks[:3])}."
        return summary

    def _record_recovery_transition(self, run_id: int, *, step_id: int, transition: RecoveryTransition) -> None:
        self._event_repo.create(
            NewWorkflowEvent(
                run_id=run_id,
                step_id=step_id,
                event_type="sync_recovery_transition_recorded",
                run_status=WorkflowRunStatus.RUNNING.value,
                step_status=WorkflowStepStatus.RUNNING.value,
                summary=f"Recorded {transition.classification.value} for {transition.planned_item_key}.",
                details=transition.model_dump(mode="json"),
            )
        )

    def _terminate_pending_sync_records(self, run_id: int, *, reason: str) -> dict[str, Any]:
        sync_records = self._sync_repo.list_for_run(run_id)
        if not sync_records:
            return {
                "partial_sync_succeeded_count": 0,
                "partial_sync_cancelled_count": 0,
                "partial_sync_last_attempted_item_key": None,
            }

        succeeded_count = len(
            [record for record in sync_records if record.status == WorkflowSyncStatus.SUCCEEDED.value]
        )
        cancelled_count = 0
        last_attempted = max(
            (record for record in sync_records if record.last_attempted_at is not None),
            key=lambda record: record.last_attempted_at,
            default=None,
        )
        for record in sync_records:
            if record.status == WorkflowSyncStatus.SUCCEEDED.value:
                continue
            self._sync_repo.update(
                record.id,
                WorkflowSyncRecordPatch(
                    status=WorkflowSyncStatus.CANCELLED.value,
                    recovery_classification=(
                        WorkflowSyncRecoveryClassification.TERMINATED_AFTER_PARTIAL_SUCCESS.value
                    ),
                    recovery_updated_at=_now(),
                    terminated_at=_now(),
                    termination_reason=reason,
                    terminated_after_sync_count=succeeded_count,
                    terminated_after_planned_item_key=(
                        last_attempted.planned_item_key if last_attempted is not None else None
                    ),
                ),
            )
            cancelled_count += 1

        return {
            "partial_sync_succeeded_count": succeeded_count,
            "partial_sync_cancelled_count": cancelled_count,
            "partial_sync_last_attempted_item_key": (
                last_attempted.planned_item_key if last_attempted is not None else None
            ),
        }

    def _sync_item_from_record(self, sync_record) -> ApprovedSyncItem:
        return ApprovedSyncItem(
            proposal_artifact_id=sync_record.proposal_artifact_id,
            proposal_version_number=sync_record.proposal_version_number,
            target_system=SyncTargetSystem(sync_record.target_system),
            operation=_sync_operation_for_kind(sync_record.sync_kind),
            planned_item_key=sync_record.planned_item_key,
            execution_order=sync_record.execution_order,
            payload_fingerprint=sync_record.payload_fingerprint,
            payload=sync_record.payload["payload"],
        )

    def _dispatch_sync_record(self, sync_record) -> TaskSyncResult | CalendarSyncResult:
        sync_item = self._sync_item_from_record(sync_record)
        if sync_item.target_system is SyncTargetSystem.TASK_SYSTEM:
            adapter = self._require_task_system_adapter()
            return adapter.upsert_task(TaskSyncRequest(item=sync_item))
        adapter = self._require_calendar_system_adapter()
        return adapter.upsert_calendar_block(CalendarSyncRequest(item=sync_item))

    def _reconcile_sync_record(self, sync_record) -> SyncLookupResult:
        lookup = SyncLookupRequest(
            proposal_artifact_id=sync_record.proposal_artifact_id,
            proposal_version_number=sync_record.proposal_version_number,
            target_system=SyncTargetSystem(sync_record.target_system),
            operation=_sync_operation_for_kind(sync_record.sync_kind),
            planned_item_key=sync_record.planned_item_key,
            payload_fingerprint=sync_record.payload_fingerprint,
            external_object_id=sync_record.external_object_id,
        )
        if lookup.target_system is SyncTargetSystem.TASK_SYSTEM:
            adapter = self._require_task_system_adapter()
            return adapter.reconcile_task(lookup)
        adapter = self._require_calendar_system_adapter()
        return adapter.reconcile_calendar_block(lookup)

    def _require_task_system_adapter(self) -> TaskSystemAdapter:
        if self._task_system_adapter is None:
            raise ValueError("Task system adapter is not configured.")
        return self._task_system_adapter

    def _require_calendar_system_adapter(self) -> CalendarSystemAdapter:
        if self._calendar_system_adapter is None:
            raise ValueError("Calendar system adapter is not configured.")
        return self._calendar_system_adapter

    def _artifact_lineage_kwargs(self, *, run_id: int, step_name: str, artifact_type: str) -> dict[str, int | None]:
        if artifact_type != WorkflowArtifactType.SCHEDULE_PROPOSAL.value:
            return {"lineage_parent_id": None, "supersedes_artifact_id": None}
        proposals = self._artifact_repo.list_for_run_by_type(
            run_id,
            artifact_type=WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
        )
        prior_proposal = proposals[-1] if proposals else None
        revision_requests = self._artifact_repo.list_for_run_by_type(
            run_id,
            artifact_type=WorkflowArtifactType.REVISION_REQUEST.value,
        )
        latest_revision_request = revision_requests[-1] if revision_requests else None
        if (
            prior_proposal is None
            or latest_revision_request is None
            or latest_revision_request.payload.get("target_artifact_id") != prior_proposal.id
            or prior_proposal.producer_step_name != step_name
        ):
            return {"lineage_parent_id": None, "supersedes_artifact_id": None}
        return {
            "lineage_parent_id": latest_revision_request.id,
            "supersedes_artifact_id": prior_proposal.id,
        }

    def _require_artifact(self, artifact_id: int):
        artifact = self._artifact_repo.get_by_id(artifact_id)
        if artifact is None:
            raise ValueError(f"Workflow artifact {artifact_id} does not exist.")
        return artifact

    def _ensure_current_step(self, state: WorkflowRunState):
        if state.current_step is not None:
            return state.current_step
        run = state.run
        if run.current_step_name is None:
            raise ValueError(f"Workflow run {run.id} has no current step.")
        current_step = self._step_repo.create(
            NewWorkflowStep(
                run_id=run.id,
                step_name=run.current_step_name,
                status=WorkflowStepStatus.PENDING.value,
                attempt_number=max(run.current_step_attempt, 1),
            )
        )
        return current_step

    def _require_current_step(self, state: WorkflowRunState):
        if state.current_step is None:
            raise ValueError(f"Workflow run {state.run.id} has no current step.")
        return state.current_step

    def _validate(
        self,
        *,
        step_name: str,
        artifact_type: str,
        payload: object,
    ) -> ValidationReport | None:
        validator = self._validator_registry.get_for_step(step_name)
        if validator is None:
            validator = self._validator_registry.get_for_artifact_type(artifact_type)
        if validator is None:
            return None
        return validator.validate(payload)

    def _mark_invocation(
        self,
        invocation_id: int | None,
        *,
        output_artifact_id: int | None,
        status: str,
        error_summary: str | None = None,
    ) -> None:
        if invocation_id is None:
            return
        self._invocation_repo.update(
            invocation_id,
            WorkflowSpecialistInvocationPatch(
                output_artifact_id=output_artifact_id,
                status=status,
                completed_at=_now(),
                error_summary=error_summary,
            ),
        )


def _payload_dict(payload: object) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json")  # type: ignore[return-value]
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "to_dict"):
        return payload.to_dict()  # type: ignore[return-value]
    raise TypeError(f"Unsupported workflow payload type: {type(payload)!r}")


def _now() -> datetime:
    return datetime.now(UTC)


def _payload_fingerprint(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def _sync_idempotency_key(item: ApprovedSyncItem) -> str:
    return ":".join(
        (
            "workflow-sync",
            str(item.proposal_artifact_id),
            str(item.proposal_version_number),
            item.target_system.value,
            item.operation.value,
            item.planned_item_key,
        )
    )


def _sync_kind_for_operation(operation: SyncOperation) -> WorkflowSyncKind:
    if operation is SyncOperation.TASK_UPSERT:
        return WorkflowSyncKind.TASK_UPSERT
    return WorkflowSyncKind.CALENDAR_BLOCK_UPSERT


def _sync_operation_for_kind(sync_kind: str) -> SyncOperation:
    if sync_kind == WorkflowSyncKind.TASK_UPSERT.value:
        return SyncOperation.TASK_UPSERT
    return SyncOperation.CALENDAR_BLOCK_UPSERT


def _slugify(value: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")
    collapsed = "-".join(part for part in slug.split("-") if part)
    return collapsed or "item"
