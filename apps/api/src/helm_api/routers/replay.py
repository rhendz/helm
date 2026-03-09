from fastapi import APIRouter

from helm_api.schemas import (
    ReplayEnqueueRequest,
    ReplayEnqueueResponse,
    ReplayReprocessRequest,
    ReplayReprocessResponse,
)
from helm_api.services.replay_service import enqueue_failed_agent_run, reprocess_failed_runs

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
