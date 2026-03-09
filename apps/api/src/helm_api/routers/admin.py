from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from helm_agents.digest_agent import build_daily_digest
from helm_api.services.agent_run_service import (
    create_agent_run,
    get_agent_run,
    list_recent_agent_runs,
    mark_agent_run_failure,
    mark_agent_run_success,
)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/agent-runs")
def list_agent_runs(
    limit: int = Query(default=20, ge=1, le=200), status: str | None = Query(default=None)
) -> dict:
    runs_payload = list_recent_agent_runs(limit=limit, status=status)
    return {"status": "ok", **runs_payload}


@router.post("/agent-runs/{run_id}/reprocess")
def reprocess_failed_run(run_id: int) -> dict[str, str]:
    run = get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="agent_run_not_found")
    if run["status"] != "failed":
        return {"status": "ignored", "reason": "run_not_failed", "run_id": str(run_id)}
    if run["agent_name"] != "digest_workflow":
        # TODO(v1-phase2-api-owner): support reprocess handlers for email/study workflows.
        return {
            "status": "not_supported",
            "reason": "reprocess_handler_missing",
            "run_id": str(run_id),
        }

    retry_run_id = create_agent_run(
        agent_name="digest_workflow",
        source_type="reprocess",
        source_id=str(run_id),
    )
    try:
        digest = build_daily_digest()
    except Exception as exc:  # noqa: BLE001
        mark_agent_run_failure(retry_run_id, error=exc)
        raise

    mark_agent_run_success(retry_run_id)
    payload = {
        "status": "reprocessed",
        "original_run_id": str(run_id),
        "digest_preview": digest[:120],
    }
    if retry_run_id is not None:
        payload["retry_run_id"] = str(retry_run_id)
    return payload
