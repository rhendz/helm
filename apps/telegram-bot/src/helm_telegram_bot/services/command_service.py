from __future__ import annotations

from dataclasses import dataclass

from helm_observability.logging import get_logger
from helm_storage.db import SessionLocal
from helm_storage.models import ActionItemORM, DraftReplyORM
from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
from helm_storage.repositories.draft_transition_audits import (
    SQLAlchemyDraftTransitionAuditRepository,
)
from sqlalchemy.exc import SQLAlchemyError

logger = get_logger("helm_telegram_bot.services.command_service")


@dataclass(frozen=True, slots=True)
class DraftTransitionResult:
    ok: bool
    message: str


class TelegramCommandService:
    def list_open_actions(self, *, limit: int = 5) -> list[ActionItemORM]:
        try:
            with SessionLocal() as session:
                repository = SQLAlchemyActionItemRepository(session)
                return repository.list_open()[:limit]
        except SQLAlchemyError:
            return []

    def list_pending_drafts(self, *, limit: int = 5) -> list[DraftReplyORM]:
        try:
            with SessionLocal() as session:
                repository = SQLAlchemyDraftReplyRepository(session)
                return repository.list_pending()[:limit]
        except SQLAlchemyError:
            return []

    def approve_draft(self, draft_id: int) -> DraftTransitionResult:
        try:
            with SessionLocal() as session:
                repository = SQLAlchemyDraftReplyRepository(session)
                audit_repository = SQLAlchemyDraftTransitionAuditRepository(session)
                draft = repository.get_by_id(draft_id)
                if draft is None:
                    audit_repository.create(
                        draft_id=draft_id,
                        action="approve",
                        from_status=None,
                        to_status=None,
                        success=False,
                        reason="draft_not_found",
                    )
                    return DraftTransitionResult(ok=False, message=f"Draft {draft_id} not found.")
                if draft.status not in {"pending", "snoozed"}:
                    audit_repository.create(
                        draft_id=draft_id,
                        action="approve",
                        from_status=draft.status,
                        to_status=draft.status,
                        success=False,
                        reason="invalid_status",
                    )
                    return DraftTransitionResult(
                        ok=False, message=f"Draft {draft_id} is {draft.status}; cannot approve."
                    )
                from_status = draft.status
                repository.approve(draft_id)
                audit_repository.create(
                    draft_id=draft_id,
                    action="approve",
                    from_status=from_status,
                    to_status="approved",
                    success=True,
                    reason=None,
                )
                return DraftTransitionResult(
                    ok=True, message=f"Approved draft {draft_id}. Not sent yet."
                )
        except SQLAlchemyError:
            logger.warning("draft_transition_failed", action="approve", draft_id=draft_id)
            return DraftTransitionResult(ok=False, message="Storage unavailable.")

    def snooze_draft(self, draft_id: int) -> DraftTransitionResult:
        try:
            with SessionLocal() as session:
                repository = SQLAlchemyDraftReplyRepository(session)
                audit_repository = SQLAlchemyDraftTransitionAuditRepository(session)
                draft = repository.get_by_id(draft_id)
                if draft is None:
                    audit_repository.create(
                        draft_id=draft_id,
                        action="snooze",
                        from_status=None,
                        to_status=None,
                        success=False,
                        reason="draft_not_found",
                    )
                    return DraftTransitionResult(ok=False, message=f"Draft {draft_id} not found.")
                if draft.status != "pending":
                    audit_repository.create(
                        draft_id=draft_id,
                        action="snooze",
                        from_status=draft.status,
                        to_status=draft.status,
                        success=False,
                        reason="invalid_status",
                    )
                    return DraftTransitionResult(
                        ok=False, message=f"Draft {draft_id} is {draft.status}; cannot snooze."
                    )
                from_status = draft.status
                repository.snooze(draft_id)
                audit_repository.create(
                    draft_id=draft_id,
                    action="snooze",
                    from_status=from_status,
                    to_status="snoozed",
                    success=True,
                    reason=None,
                )
                return DraftTransitionResult(
                    ok=True, message=f"Snoozed draft {draft_id} for later review."
                )
        except SQLAlchemyError:
            logger.warning("draft_transition_failed", action="snooze", draft_id=draft_id)
            return DraftTransitionResult(ok=False, message="Storage unavailable.")
