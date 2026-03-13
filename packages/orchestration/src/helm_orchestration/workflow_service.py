from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from helm_orchestration.schemas import (
    ExecutionFailurePayload,
    RetryState,
    SCHEMA_VERSION,
    ValidationOutcome,
    ValidationReport,
    WorkflowSummaryArtifact,
)
from helm_orchestration.contracts import WorkflowSpecialistStep, WorkflowStepExecutionError
from helm_orchestration.validators import ValidatorRegistry
from helm_storage.repositories import (
    NewWorkflowArtifact,
    NewWorkflowEvent,
    NewWorkflowRun,
    NewWorkflowSpecialistInvocation,
    NewWorkflowStep,
    SQLAlchemyWorkflowArtifactRepository,
    SQLAlchemyWorkflowEventRepository,
    SQLAlchemyWorkflowRunRepository,
    SQLAlchemyWorkflowSpecialistInvocationRepository,
    SQLAlchemyWorkflowStepRepository,
    WorkflowArtifactType,
    WorkflowRunPatch,
    WorkflowRunState,
    WorkflowRunStatus,
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
    ) -> None:
        self._session = session
        self._run_repo = SQLAlchemyWorkflowRunRepository(session)
        self._step_repo = SQLAlchemyWorkflowStepRepository(session)
        self._artifact_repo = SQLAlchemyWorkflowArtifactRepository(session)
        self._event_repo = SQLAlchemyWorkflowEventRepository(session)
        self._invocation_repo = SQLAlchemyWorkflowSpecialistInvocationRepository(session)
        self._validator_registry = validator_registry or ValidatorRegistry()

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
        candidate_artifact = self._artifact_repo.create(
            NewWorkflowArtifact(
                run_id=run_id,
                step_id=step.id,
                artifact_type=artifact_type,
                schema_version=SCHEMA_VERSION,
                producer_step_name=step.step_name,
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
                    failure_class="schema_validation_failed",
                    retry_state=RetryState.AWAITING_OPERATOR.value,
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

        if next_step_name is None:
            self._run_repo.update(
                run_id,
                WorkflowRunPatch(
                    status=WorkflowRunStatus.COMPLETED.value,
                    current_step_name=step.step_name,
                    current_step_attempt=step.attempt_number,
                    needs_action=False,
                    validation_outcome_summary=validation_report.outcome.value if validation_report else None,
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
                failure_class="",
                retry_state="",
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
                failure_class=failure.error_type,
                retry_state=failure.retry_state.value,
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
                failure_class="",
                retry_state=RetryState.RETRYABLE.value,
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
        return self.get_run_state(run_id)

    def terminate_run(self, run_id: int, *, reason: str) -> WorkflowRunState:
        state = self.get_run_state(run_id)
        current_step = state.current_step
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
                retry_state=RetryState.TERMINAL.value,
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
                details={"reason": reason},
            )
        )
        return self.get_run_state(run_id)

    def build_final_summary_artifact(self, run_id: int, *, final_summary_text: str) -> WorkflowSummaryArtifact:
        state = self.get_run_state(run_id)
        latest_artifacts = state.latest_artifacts
        request_artifact = latest_artifacts[WorkflowArtifactType.RAW_REQUEST.value]
        validation_ids = tuple(
            artifact.id
            for artifact in self._artifact_repo.list_for_run(run_id)
            if artifact.artifact_type == WorkflowArtifactType.VALIDATION_RESULT.value
        )
        intermediate_ids = tuple(
            artifact.id
            for artifact in self._artifact_repo.list_for_run(run_id)
            if artifact.artifact_type
            in {
                WorkflowArtifactType.NORMALIZED_TASK.value,
                WorkflowArtifactType.SCHEDULE_PROPOSAL.value,
            }
        )
        return WorkflowSummaryArtifact(
            request_artifact_id=request_artifact.id,
            intermediate_artifact_ids=intermediate_ids,
            validation_artifact_ids=validation_ids,
            final_summary_text=final_summary_text,
        )

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
