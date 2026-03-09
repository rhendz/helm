from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from helm_api.dependencies import get_db
from helm_api.schemas import StudyIngestRequest, StudyIngestResponse
from helm_api.services.study_service import ingest_manual_study_note

router = APIRouter(prefix="/v1/study", tags=["study"])


@router.post("/ingest", response_model=StudyIngestResponse)
def ingest_study(payload: StudyIngestRequest, db: Session = Depends(get_db)) -> StudyIngestResponse:
    if not payload.raw_text.strip():
        raise HTTPException(status_code=422, detail="raw_text must not be empty")
    result = ingest_manual_study_note(
        source_type=payload.source_type,
        raw_text=payload.raw_text,
        db=db,
    )
    return StudyIngestResponse(**result)
