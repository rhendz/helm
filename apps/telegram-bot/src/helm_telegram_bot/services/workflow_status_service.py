from __future__ import annotations

from helm_api.services.workflow_status_service import WorkflowRunCreateInput, WorkflowStatusService
from helm_storage.db import SessionLocal


class TelegramWorkflowStatusService:
    def start_run(self, *, request_text: str, submitted_by: str, chat_id: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).create_run(
                WorkflowRunCreateInput(
                    workflow_type="weekly_digest",
                    first_step_name="normalize_request",
                    request_text=request_text,
                    submitted_by=submitted_by,
                    channel="telegram",
                    metadata={"chat_id": chat_id},
                )
            )

    def list_recent_runs(self, *, limit: int = 5) -> list[dict[str, object]]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).list_runs(limit=limit)

    def list_runs_needing_action(self, *, limit: int = 5) -> list[dict[str, object]]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).list_runs(needs_action=True, limit=limit)

    def retry_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).retry_run(run_id, reason=reason)

    def terminate_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).terminate_run(run_id, reason=reason)
