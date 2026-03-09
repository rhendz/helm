from fastapi import APIRouter
from helm_agents.digest_agent import build_daily_digest

from helm_api.services.agent_run_service import (
    create_agent_run,
    mark_agent_run_failure,
    mark_agent_run_success,
)

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


@router.post("/digest/run")
def run_digest() -> dict[str, str]:
    run_id = create_agent_run(agent_name="digest_workflow", source_type="api", source_id=None)
    try:
        text = build_daily_digest()
    except Exception as exc:  # noqa: BLE001
        mark_agent_run_failure(run_id, error=exc)
        raise

    mark_agent_run_success(run_id)
    payload = {"status": "ok", "digest": text}
    if run_id is not None:
        payload["run_id"] = str(run_id)
    return payload
