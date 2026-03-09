from fastapi import APIRouter

from helm_api.schemas import LinkedInIngestRequest, LinkedInIngestResponse
from helm_api.services.linkedin_service import ingest_manual_linkedin_events

router = APIRouter(prefix="/v1/linkedin", tags=["linkedin"])


@router.post("/ingest", response_model=LinkedInIngestResponse)
def ingest_linkedin(payload: LinkedInIngestRequest) -> LinkedInIngestResponse:
    return LinkedInIngestResponse(
        **ingest_manual_linkedin_events(
            source_type=payload.source_type,
            events=[event.model_dump(mode="json") for event in payload.events],
        )
    )
