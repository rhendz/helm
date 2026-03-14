from __future__ import annotations

from helm_storage.repositories import (
    SQLAlchemyWorkflowRunRepository,
    WorkflowRunState,
    WorkflowRunStatus,
)
from sqlalchemy.orm import Session

from helm_orchestration.contracts import WorkflowSpecialistStep
from helm_orchestration.schemas import ExecutionFailurePayload, RetryState
from helm_orchestration.workflow_service import WorkflowOrchestrationService


class WorkflowResumeService:
    def __init__(
        self,
        session: Session,
        *,
        workflow_service: WorkflowOrchestrationService,
        specialist_steps: dict[tuple[str, str], WorkflowSpecialistStep] | None = None,
    ) -> None:
        self._run_repo = SQLAlchemyWorkflowRunRepository(session)
        self._workflow_service = workflow_service
        self._specialist_steps = specialist_steps or {}

    def list_runnable_runs(self, *, limit: int | None = None) -> list[WorkflowRunState]:
        return self._run_repo.list_runnable(limit=limit)

    def resume_run(self, run_id: int) -> WorkflowRunState:
        state = self._workflow_service.get_run_state(run_id)
        if state.run.needs_action:
            raise ValueError(f"Workflow run {run_id} is awaiting operator action.")
        current_step = state.current_step
        if current_step is None:
            raise ValueError(f"Workflow run {run_id} has no runnable current step.")
        if current_step.step_name == "apply_schedule":
            return self._workflow_service.execute_pending_sync_step(run_id)
        dispatch_key = (state.run.workflow_type, current_step.step_name)
        specialist_step = self._specialist_steps.get(dispatch_key)
        if specialist_step is None:
            failure = ExecutionFailurePayload(
                error_type="missing_step_handler",
                message=(
                    "No specialist handler registered for "
                    f"{state.run.workflow_type}:{current_step.step_name}."
                ),
                retry_state=RetryState.TERMINAL,
                retryable=False,
                details={
                    "workflow_type": state.run.workflow_type,
                    "step_name": current_step.step_name,
                },
            )
            return self._workflow_service.fail_current_step(run_id, failure)
        return self._workflow_service.execute_specialist_step(run_id, specialist_step)

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
