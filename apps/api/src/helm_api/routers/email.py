from fastapi import APIRouter, HTTPException, Query

from helm_api.schemas import (
    EmailDraftResponse,
    EmailProposalResponse,
    EmailThreadDetailResponse,
    EmailThreadReprocessRequest,
    EmailThreadReprocessResponse,
    EmailThreadResponse,
)
from helm_api.services.email_service import (
    get_thread_detail,
    list_drafts,
    list_proposals,
    list_threads,
    reprocess_thread,
)

router = APIRouter(prefix="/v1/email", tags=["email"])


@router.get("/threads", response_model=list[EmailThreadResponse])
def get_email_threads(limit: int = Query(default=20, ge=1, le=100)) -> list[EmailThreadResponse]:
    return [EmailThreadResponse(**item) for item in list_threads(limit=limit)]


@router.get("/proposals", response_model=list[EmailProposalResponse])
def get_email_proposals(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EmailProposalResponse]:
    return [EmailProposalResponse(**item) for item in list_proposals(limit=limit)]


@router.get("/drafts", response_model=list[EmailDraftResponse])
def get_email_drafts(limit: int = Query(default=20, ge=1, le=100)) -> list[EmailDraftResponse]:
    return [EmailDraftResponse(**item) for item in list_drafts(limit=limit)]


@router.get("/threads/{thread_id}", response_model=EmailThreadDetailResponse)
def get_email_thread_detail(thread_id: int) -> EmailThreadDetailResponse:
    detail = get_thread_detail(thread_id=thread_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Email thread not found")
    return EmailThreadDetailResponse(**detail)


@router.post(
    "/threads/{thread_id}/reprocess",
    response_model=EmailThreadReprocessResponse,
)
def reprocess_email_thread_route(
    thread_id: int,
    payload: EmailThreadReprocessRequest,
) -> EmailThreadReprocessResponse:
    return EmailThreadReprocessResponse(
        **reprocess_thread(thread_id=thread_id, dry_run=payload.dry_run),
    )
