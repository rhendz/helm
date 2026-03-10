from fastapi import APIRouter, Query

from helm_api.schemas import EmailDraftResponse, EmailProposalResponse, EmailThreadResponse
from helm_api.services.email_service import (
    list_drafts,
    list_proposals,
    list_threads,
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
