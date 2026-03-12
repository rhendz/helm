from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from helm_api.dependencies import get_db
from helm_api.schemas import (
    ReplayEnqueueRequest,
    ReplayEnqueueResponse,
    ReplayReprocessRequest,
    ReplayReprocessResponse,
    WorkflowReplayRequest,
    WorkflowReplayResponse,
)
from helm_api.services.replay_service import (
    enqueue_failed_agent_run,
    reprocess_failed_runs,
    request_workflow_run_replay,
)

router = APIRouter(prefix="/v1/replay", tags=["replay"])


@router.post("/enqueue", response_model=ReplayEnqueueResponse)
def enqueue_replay(payload: ReplayEnqueueRequest) -> ReplayEnqueueResponse:
    return ReplayEnqueueResponse(**enqueue_failed_agent_run(agent_run_id=payload.agent_run_id))


@router.post("/reprocess", response_model=ReplayReprocessResponse)
def reprocess_replay(payload: ReplayReprocessRequest) -> ReplayReprocessResponse:
    return ReplayReprocessResponse(
        **reprocess_failed_runs(
            source_type=payload.source_type,
            source_id=payload.source_id,
            since_hours=payload.since_hours,
            limit=payload.limit,
            dry_run=payload.dry_run,
        )
    )


@router.post("/workflow-runs/{run_id}", response_model=WorkflowReplayResponse)
def replay_workflow_run(
    run_id: int,
    payload: WorkflowReplayRequest,
    db: Session = Depends(get_db),
) -> WorkflowReplayResponse:
    del db
    try:
        return WorkflowReplayResponse(
            **request_workflow_run_replay(
                run_id=run_id,
                actor=payload.actor,
                reason=payload.reason,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
