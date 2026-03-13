from __future__ import annotations

from collections.abc import Callable

from helm_orchestration.contracts import StepExecutionResult
from helm_orchestration.schemas import ExecutionFailurePayload, RetryState
from helm_orchestration.workflow_service import WorkflowOrchestrationService
from helm_storage.repositories import SQLAlchemyWorkflowRunRepository, WorkflowRunState, WorkflowRunStatus
from sqlalchemy.orm import Session

StepHandler = Callable[[WorkflowRunState], StepExecutionResult]


class WorkflowStepExecutionError(RuntimeError):
    def __init__(self, failure: ExecutionFailurePayload) -> None:
        super().__init__(failure.message)
        self.failure = failure


class WorkflowResumeService:
    def __init__(
        self,
        session: Session,
        *,
        workflow_service: WorkflowOrchestrationService,
        handlers: dict[str, StepHandler] | None = None,
    ) -> None:
        self._run_repo = SQLAlchemyWorkflowRunRepository(session)
        self._workflow_service = workflow_service
        self._handlers = handlers or {}

    def list_runnable_runs(self, *, limit: int | None = None) -> list[WorkflowRunState]:
        return self._run_repo.list_runnable(limit=limit)

    def resume_run(self, run_id: int) -> WorkflowRunState:
        state = self._workflow_service.start_current_step(run_id)
        current_step = state.current_step
        if current_step is None:
            raise ValueError(f"Workflow run {run_id} has no runnable current step.")
        handler = self._handlers.get(current_step.step_name)
        if handler is None:
            failure = ExecutionFailurePayload(
                error_type="missing_step_handler",
                message=f"No step handler registered for {current_step.step_name}.",
                retry_state=RetryState.TERMINAL,
                retryable=False,
                details={"step_name": current_step.step_name},
            )
            return self._workflow_service.fail_current_step(run_id, failure)
        try:
            result = handler(self._workflow_service.get_run_state(run_id))
        except WorkflowStepExecutionError as exc:
            return self._workflow_service.fail_current_step(run_id, exc.failure)
        except Exception as exc:  # noqa: BLE001
            failure = ExecutionFailurePayload(
                error_type="unhandled_step_exception",
                message=str(exc),
                retry_state=RetryState.RETRYABLE,
                retryable=True,
                details={"step_name": current_step.step_name},
            )
            return self._workflow_service.fail_current_step(run_id, failure)
        return self._workflow_service.complete_current_step(
            run_id,
            artifact_type=result.artifact_type.value,
            artifact_payload=result.payload,
            next_step_name=result.next_step_name,
        )

    def resume_runnable_runs(self, *, limit: int | None = None) -> list[WorkflowRunState]:
        completed: list[WorkflowRunState] = []
        for state in self.list_runnable_runs(limit=limit):
            if state.run.status not in {
                WorkflowRunStatus.PENDING.value,
                WorkflowRunStatus.RUNNING.value,
            }:
                continue
            completed.append(self.resume_run(state.run.id))
        return completed
