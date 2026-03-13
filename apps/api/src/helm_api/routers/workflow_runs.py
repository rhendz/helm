from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from helm_api.dependencies import get_db
from helm_api.schemas import (
    WorkflowRunActionRequest,
    WorkflowRunCreateRequest,
    WorkflowRunDetailResponse,
    WorkflowRunSummaryResponse,
)
from helm_api.services.workflow_status_service import WorkflowRunCreateInput, WorkflowStatusService

router = APIRouter(prefix="/v1/workflow-runs", tags=["workflow-runs"])


@router.post("", response_model=WorkflowRunSummaryResponse)
def create_workflow_run(
    payload: WorkflowRunCreateRequest,
    db: Session = Depends(get_db),
) -> WorkflowRunSummaryResponse:
    service = WorkflowStatusService(db)
    created = service.create_run(
        WorkflowRunCreateInput(
            workflow_type=payload.workflow_type,
            first_step_name=payload.first_step_name,
            request_text=payload.request_text,
            submitted_by=payload.submitted_by,
            channel=payload.channel,
            metadata=payload.metadata,
        )
    )
    return WorkflowRunSummaryResponse(**created)


@router.get("", response_model=list[WorkflowRunSummaryResponse])
def list_workflow_runs(
    needs_action: bool | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[WorkflowRunSummaryResponse]:
    service = WorkflowStatusService(db)
    return [WorkflowRunSummaryResponse(**item) for item in service.list_runs(needs_action=needs_action, limit=limit)]


@router.get("/{run_id}", response_model=WorkflowRunDetailResponse)
def get_workflow_run_detail(
    run_id: int,
    db: Session = Depends(get_db),
) -> WorkflowRunDetailResponse:
    service = WorkflowStatusService(db)
    detail = service.get_run_detail(run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return WorkflowRunDetailResponse(**detail)


@router.post("/{run_id}/retry", response_model=WorkflowRunSummaryResponse)
def retry_workflow_run(
    run_id: int,
    payload: WorkflowRunActionRequest,
    db: Session = Depends(get_db),
) -> WorkflowRunSummaryResponse:
    service = WorkflowStatusService(db)
    try:
        result = service.retry_run(run_id, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkflowRunSummaryResponse(**result)


@router.post("/{run_id}/terminate", response_model=WorkflowRunSummaryResponse)
def terminate_workflow_run(
    run_id: int,
    payload: WorkflowRunActionRequest,
    db: Session = Depends(get_db),
) -> WorkflowRunSummaryResponse:
    service = WorkflowStatusService(db)
    try:
        result = service.terminate_run(run_id, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkflowRunSummaryResponse(**result)
