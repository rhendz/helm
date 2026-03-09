from fastapi import APIRouter
from helm_agents.digest_agent import generate_daily_digest
from helm_observability.agent_runs import record_agent_run

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


@router.post("/digest/run")
def run_digest() -> dict[str, str | int]:
    result = None

    def _execute() -> None:
        nonlocal result
        result = generate_daily_digest()

    record_agent_run(
        agent_name="digest_agent",
        source_type="api",
        source_id="v1/workflows/digest/run",
        execute=_execute,
    )

    if result is None:
        return {"status": "error", "preview": "Digest run failed.", "action_count": 0}

    return {
        "status": "ok",
        "preview": result.text[:120],
        "action_count": result.action_count,
        "digest_item_count": result.digest_item_count,
        "pending_draft_count": result.pending_draft_count,
    }
