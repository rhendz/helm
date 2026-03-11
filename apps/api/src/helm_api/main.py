from fastapi import FastAPI

from helm_api.config import settings
from helm_api.routers import (
    actions,
    artifacts,
    drafts,
    email,
    job_controls,
    replay,
    status,
    workflows,
)

app = FastAPI(title="helm-api", version="0.1.0")
app.include_router(actions.router)
app.include_router(artifacts.router)
app.include_router(drafts.router)
app.include_router(email.router)
app.include_router(workflows.router)
app.include_router(status.router)
app.include_router(replay.router)
app.include_router(job_controls.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
