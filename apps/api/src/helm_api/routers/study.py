from fastapi import APIRouter

from helm_api.schemas import StudyIngestRequest, StudyIngestResponse
from helm_api.services.study_service import ingest_manual_study_note

router = APIRouter(prefix="/v1/study", tags=["study"])


@router.post("/ingest", response_model=StudyIngestResponse)
def ingest_study(payload: StudyIngestRequest) -> StudyIngestResponse:
    return StudyIngestResponse(
        **ingest_manual_study_note(source_type=payload.source_type, raw_text=payload.raw_text)
    )
