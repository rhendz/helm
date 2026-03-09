from fastapi import APIRouter

from helm_api.schemas import ActionItemResponse
from helm_api.services.action_service import list_actions

router = APIRouter(prefix="/v1/actions", tags=["actions"])


@router.get("", response_model=list[ActionItemResponse])
def get_actions() -> list[ActionItemResponse]:
    return [ActionItemResponse(**item) for item in list_actions()]
