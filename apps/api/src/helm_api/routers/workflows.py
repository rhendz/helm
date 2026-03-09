from fastapi import APIRouter
from helm_agents.digest_agent import build_daily_digest

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


@router.post("/digest/run")
def run_digest() -> dict[str, str]:
    text = build_daily_digest()
    return {"status": "ok", "preview": text[:120]}
