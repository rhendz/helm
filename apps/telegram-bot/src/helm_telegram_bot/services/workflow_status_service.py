from __future__ import annotations

from helm_api.services.replay_service import request_workflow_run_replay
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

    def get_run_detail(self, run_id: int) -> dict[str, object] | None:
        with SessionLocal() as session:
            return WorkflowStatusService(session).get_run_detail(run_id)

    def retry_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).retry_run(run_id, reason=reason)

    def terminate_run(self, run_id: int, *, reason: str) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).terminate_run(run_id, reason=reason)

    def request_replay(self, run_id: int, *, actor: str, reason: str) -> dict[str, object]:
        return request_workflow_run_replay(run_id=run_id, actor=actor, reason=reason)["run"]

    def approve_run(self, run_id: int, *, actor: str, target_artifact_id: int) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).approve_run(
                run_id,
                actor=actor,
                target_artifact_id=target_artifact_id,
            )

    def reject_run(self, run_id: int, *, actor: str, target_artifact_id: int) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).reject_run(
                run_id,
                actor=actor,
                target_artifact_id=target_artifact_id,
            )

    def request_revision(
        self,
        run_id: int,
        *,
        actor: str,
        target_artifact_id: int,
        feedback: str,
    ) -> dict[str, object]:
        with SessionLocal() as session:
            return WorkflowStatusService(session).request_revision(
                run_id,
                actor=actor,
                target_artifact_id=target_artifact_id,
                feedback=feedback,
            )
