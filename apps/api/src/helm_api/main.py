from fastapi import FastAPI

from helm_api.config import settings
from helm_api.routers import actions, drafts, linkedin, status, study, workflows

app = FastAPI(title="helm-api", version="0.1.0")
app.include_router(actions.router)
app.include_router(drafts.router)
app.include_router(study.router)
app.include_router(workflows.router)
app.include_router(status.router)
app.include_router(linkedin.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
