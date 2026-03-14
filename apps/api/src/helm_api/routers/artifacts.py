from fastapi import APIRouter

from helm_api.schemas import ArtifactTraceResponse
from helm_api.services.artifact_trace_service import get_artifact_trace

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])


@router.get("/{artifact_type}/{artifact_id}/trace", response_model=ArtifactTraceResponse)
def get_artifact_trace_view(artifact_type: str, artifact_id: int) -> ArtifactTraceResponse:
    return ArtifactTraceResponse(
        **get_artifact_trace(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
        )
    )
