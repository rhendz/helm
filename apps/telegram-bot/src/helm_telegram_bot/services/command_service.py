from __future__ import annotations

from dataclasses import dataclass

from helm_storage.db import SessionLocal
from helm_storage.models import ActionItemORM, DraftReplyORM
from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
from sqlalchemy.exc import SQLAlchemyError


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
                draft = repository.get_by_id(draft_id)
                if draft is None:
                    return DraftTransitionResult(ok=False, message=f"Draft {draft_id} not found.")
                if draft.status not in {"pending", "snoozed"}:
                    return DraftTransitionResult(
                        ok=False, message=f"Draft {draft_id} is {draft.status}; cannot approve."
                    )
                repository.approve(draft_id)
                return DraftTransitionResult(
                    ok=True, message=f"Approved draft {draft_id}. Not sent yet."
                )
        except SQLAlchemyError:
            return DraftTransitionResult(ok=False, message="Storage unavailable.")

    def snooze_draft(self, draft_id: int) -> DraftTransitionResult:
        try:
            with SessionLocal() as session:
                repository = SQLAlchemyDraftReplyRepository(session)
                draft = repository.get_by_id(draft_id)
                if draft is None:
                    return DraftTransitionResult(ok=False, message=f"Draft {draft_id} not found.")
                if draft.status != "pending":
                    return DraftTransitionResult(
                        ok=False, message=f"Draft {draft_id} is {draft.status}; cannot snooze."
                    )
                repository.snooze(draft_id)
                return DraftTransitionResult(
                    ok=True, message=f"Snoozed draft {draft_id} for later review."
                )
        except SQLAlchemyError:
            return DraftTransitionResult(ok=False, message="Storage unavailable.")
