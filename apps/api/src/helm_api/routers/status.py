from fastapi import APIRouter, Query

from helm_api.schemas import AgentRunFailureResponse, DraftTransitionFailureResponse, StatusResponse
from helm_api.services.status_service import (
    get_runtime_status,
    list_recent_failed_agent_runs,
    list_recent_failed_draft_transitions,
)

router = APIRouter(prefix="/v1/status", tags=["status"])


@router.get("", response_model=StatusResponse)
def get_status() -> StatusResponse:
    return StatusResponse(**get_runtime_status())


@router.get("/agent-runs/failures", response_model=list[AgentRunFailureResponse])
def get_failed_agent_runs(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AgentRunFailureResponse]:
    return [AgentRunFailureResponse(**item) for item in list_recent_failed_agent_runs(limit=limit)]


@router.get("/draft-transitions/failures", response_model=list[DraftTransitionFailureResponse])
def get_failed_draft_transitions(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[DraftTransitionFailureResponse]:
    return [
        DraftTransitionFailureResponse(**item)
        for item in list_recent_failed_draft_transitions(limit=limit)
    ]
