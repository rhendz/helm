from fastapi import APIRouter

from helm_api.schemas import DraftRequeueRequest, DraftRequeueResponse, DraftResponse
from helm_api.services.draft_service import list_drafts, requeue_stale_drafts

router = APIRouter(prefix="/v1/drafts", tags=["drafts"])


@router.get("", response_model=list[DraftResponse])
def get_drafts() -> list[DraftResponse]:
    return [DraftResponse(**item) for item in list_drafts()]


@router.post("/requeue-stale", response_model=DraftRequeueResponse)
def requeue_stale(payload: DraftRequeueRequest) -> DraftRequeueResponse:
    return DraftRequeueResponse(
        **requeue_stale_drafts(
            stale_after_hours=payload.stale_after_hours,
            limit=payload.limit,
            dry_run=payload.dry_run,
        )
    )
