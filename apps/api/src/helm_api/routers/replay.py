from fastapi import APIRouter, Query

from helm_api.schemas import (
    ReplayEnqueueRequest,
    ReplayEnqueueResponse,
    ReplayQueueItemResponse,
    ReplayReprocessRequest,
    ReplayReprocessResponse,
    ReplayRequeueResponse,
)
from helm_api.services.replay_service import (
    enqueue_failed_agent_run,
    list_replay_items,
    reprocess_failed_runs,
    requeue_replay_item,
)

router = APIRouter(prefix="/v1/replay", tags=["replay"])


@router.post("/enqueue", response_model=ReplayEnqueueResponse)
def enqueue_replay(payload: ReplayEnqueueRequest) -> ReplayEnqueueResponse:
    return ReplayEnqueueResponse(**enqueue_failed_agent_run(agent_run_id=payload.agent_run_id))


@router.get("/items", response_model=list[ReplayQueueItemResponse])
def get_replay_items(
    status: str | None = Query(
        default=None,
        pattern="^(pending|processing|completed|failed|dead_lettered)$",
    ),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ReplayQueueItemResponse]:
    items = list_replay_items(status=status, limit=limit)
    return [ReplayQueueItemResponse(**item) for item in items]


@router.post("/{replay_id}/requeue", response_model=ReplayRequeueResponse)
def requeue_replay(replay_id: int) -> ReplayRequeueResponse:
    return ReplayRequeueResponse(**requeue_replay_item(replay_id=replay_id))


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
