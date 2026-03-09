from fastapi import APIRouter

from helm_api.schemas import DraftResponse
from helm_api.services.draft_service import list_drafts

router = APIRouter(prefix="/v1/drafts", tags=["drafts"])


@router.get("", response_model=list[DraftResponse])
def get_drafts() -> list[DraftResponse]:
    return [DraftResponse(**item) for item in list_drafts()]
