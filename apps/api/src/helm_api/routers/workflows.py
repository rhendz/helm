from fastapi import APIRouter
from helm_agents.digest_agent import generate_daily_digest
from helm_observability.agent_runs import record_agent_run
from helm_orchestration.linkedin_flow import run_linkedin_triage_workflow

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


@router.post("/linkedin-triage/run")
def run_linkedin_triage() -> dict[str, str | int]:
    result = None

    def _execute() -> None:
        nonlocal result
        result = run_linkedin_triage_workflow()

    record_agent_run(
        agent_name="linkedin_triage_agent",
        source_type="api",
        source_id="v1/workflows/linkedin-triage/run",
        execute=_execute,
    )

    if result is None:
        return {
            "status": "error",
            "scanned_messages": 0,
            "created_opportunities": 0,
            "created_drafts": 0,
        }

    return {
        "status": "ok",
        "scanned_messages": result.scanned_messages,
        "created_opportunities": result.created_opportunities,
        "created_drafts": result.created_drafts,
        "workflow_status": result.workflow_status,
    }
