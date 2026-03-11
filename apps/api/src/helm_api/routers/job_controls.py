from fastapi import APIRouter, HTTPException

from helm_api.schemas import JobControlListResponse, JobControlResponse
from helm_api.services.job_control_service import (
    get_job_control,
    list_job_controls,
    set_job_pause,
)

router = APIRouter(prefix="/v1/job-controls", tags=["job-controls"])


@router.get("", response_model=JobControlListResponse)
def get_job_controls() -> JobControlListResponse:
    return JobControlListResponse(
        items=[JobControlResponse(**item) for item in list_job_controls()]
    )


@router.get("/{job_name}", response_model=JobControlResponse)
def get_job_control_detail(job_name: str) -> JobControlResponse:
    item = get_job_control(job_name=job_name)
    if item is None:
        raise HTTPException(status_code=404, detail="Job control not found.")
    return JobControlResponse(**item)


@router.post("/{job_name}/pause", response_model=JobControlResponse)
def pause_job(job_name: str) -> JobControlResponse:
    return JobControlResponse(**set_job_pause(job_name=job_name, paused=True))


@router.post("/{job_name}/resume", response_model=JobControlResponse)
def resume_job(job_name: str) -> JobControlResponse:
    return JobControlResponse(**set_job_pause(job_name=job_name, paused=False))
