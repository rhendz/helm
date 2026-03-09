from fastapi import APIRouter

from helm_api.schemas import ReplayEnqueueRequest, ReplayEnqueueResponse
from helm_api.services.replay_service import enqueue_failed_agent_run

router = APIRouter(prefix="/v1/replay", tags=["replay"])


@router.post("/enqueue", response_model=ReplayEnqueueResponse)
def enqueue_replay(payload: ReplayEnqueueRequest) -> ReplayEnqueueResponse:
    return ReplayEnqueueResponse(**enqueue_failed_agent_run(agent_run_id=payload.agent_run_id))
