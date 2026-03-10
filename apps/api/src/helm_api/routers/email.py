from fastapi import APIRouter, HTTPException, Query

from helm_api.schemas import (
    CompleteScheduledTaskResponse,
    CreateScheduledTaskRequest,
    CreateScheduledTaskResponse,
    EmailDraftResponse,
    EmailIngestRequest,
    EmailIngestResponse,
    EmailProposalResponse,
    EmailThreadDetailResponse,
    EmailThreadOverrideRequest,
    EmailThreadOverrideResponse,
    EmailThreadReprocessRequest,
    EmailThreadReprocessResponse,
    EmailThreadResponse,
    ScheduledTaskResponse,
)
from helm_api.services.email_service import (
    complete_task,
    create_thread_task,
    get_thread_detail,
    ingest_manual_email_messages,
    list_drafts,
    list_proposals,
    list_tasks,
    list_thread_tasks,
    list_threads,
    override_thread,
    reprocess_thread,
)

router = APIRouter(prefix="/v1/email", tags=["email"])


@router.post("/ingest", response_model=EmailIngestResponse)
def ingest_email(payload: EmailIngestRequest) -> EmailIngestResponse:
    return EmailIngestResponse(
        **ingest_manual_email_messages(
            source_type=payload.source_type,
            messages=[
                message.model_dump(mode="json", by_alias=True)
                for message in payload.messages
            ],
        )
    )


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


@router.get("/tasks", response_model=list[ScheduledTaskResponse])
def get_email_tasks(
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, pattern="^(pending|completed)$"),
) -> list[ScheduledTaskResponse]:
    return [ScheduledTaskResponse(**item) for item in list_tasks(status=status, limit=limit)]


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


@router.post("/threads/{thread_id}/override", response_model=EmailThreadOverrideResponse)
def override_email_thread(
    thread_id: int,
    payload: EmailThreadOverrideRequest,
) -> EmailThreadOverrideResponse:
    return EmailThreadOverrideResponse(
        **override_thread(
            thread_id=thread_id,
            business_state=payload.business_state,
            visible_labels=payload.visible_labels,
            current_summary=payload.current_summary,
            latest_confidence_band=payload.latest_confidence_band,
            action_reason=payload.action_reason,
        )
    )


@router.get("/threads/{thread_id}/tasks", response_model=list[ScheduledTaskResponse])
def get_email_thread_tasks(thread_id: int) -> list[ScheduledTaskResponse]:
    return [ScheduledTaskResponse(**item) for item in list_thread_tasks(thread_id=thread_id)]


@router.post("/threads/{thread_id}/tasks", response_model=CreateScheduledTaskResponse)
def create_email_thread_task(
    thread_id: int,
    payload: CreateScheduledTaskRequest,
) -> CreateScheduledTaskResponse:
    return CreateScheduledTaskResponse(
        **create_thread_task(
            thread_id=thread_id,
            task_type=payload.task_type,
            due_at=payload.due_at,
            created_by=payload.created_by,
        )
    )


@router.post(
    "/threads/{thread_id}/tasks/{task_id}/complete",
    response_model=CompleteScheduledTaskResponse,
)
def complete_email_thread_task(
    thread_id: int,
    task_id: int,
) -> CompleteScheduledTaskResponse:
    return CompleteScheduledTaskResponse(
        **complete_task(thread_id=thread_id, task_id=task_id),
    )
