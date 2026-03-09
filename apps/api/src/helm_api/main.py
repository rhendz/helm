from fastapi import FastAPI

from helm_api.config import settings
from helm_api.routers import actions, drafts, study, workflows
from helm_api.services.status_service import get_runtime_status

app = FastAPI(title="helm-api", version="0.1.0")
app.include_router(actions.router)
app.include_router(drafts.router)
app.include_router(study.router)
app.include_router(workflows.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


@app.get("/v1/status")
def status() -> dict[str, str]:
    return get_runtime_status()
