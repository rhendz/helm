from __future__ import annotations

from dataclasses import dataclass

from helm_storage.db import SessionLocal
from helm_storage.models import ActionItemORM, DraftReplyORM
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError


@dataclass(frozen=True, slots=True)
class DraftTransitionResult:
    ok: bool
    message: str


class TelegramCommandService:
    def list_open_actions(self, *, limit: int = 5) -> list[ActionItemORM]:
        try:
            with SessionLocal() as session:
                stmt = (
                    select(ActionItemORM)
                    .where(ActionItemORM.status == "open")
                    .order_by(ActionItemORM.priority.asc(), ActionItemORM.created_at.asc())
                    .limit(limit)
                )
                return list(session.scalars(stmt).all())
        except SQLAlchemyError:
            return []

    def list_pending_drafts(self, *, limit: int = 5) -> list[DraftReplyORM]:
        try:
            with SessionLocal() as session:
                stmt = (
                    select(DraftReplyORM)
                    .where(DraftReplyORM.status.in_(("pending", "snoozed")))
                    .order_by(DraftReplyORM.created_at.asc())
                    .limit(limit)
                )
                return list(session.scalars(stmt).all())
        except SQLAlchemyError:
            return []

    def approve_draft(self, draft_id: int) -> DraftTransitionResult:
        try:
            with SessionLocal() as session:
                draft = session.get(DraftReplyORM, draft_id)
                if draft is None:
                    return DraftTransitionResult(ok=False, message=f"Draft {draft_id} not found.")
                if draft.status not in {"pending", "snoozed"}:
                    return DraftTransitionResult(
                        ok=False, message=f"Draft {draft_id} is {draft.status}; cannot approve."
                    )
                draft.status = "approved"
                session.commit()
                return DraftTransitionResult(
                    ok=True, message=f"Approved draft {draft_id}. Not sent yet."
                )
        except SQLAlchemyError:
            return DraftTransitionResult(ok=False, message="Storage unavailable.")

    def snooze_draft(self, draft_id: int) -> DraftTransitionResult:
        try:
            with SessionLocal() as session:
                draft = session.get(DraftReplyORM, draft_id)
                if draft is None:
                    return DraftTransitionResult(ok=False, message=f"Draft {draft_id} not found.")
                if draft.status != "pending":
                    return DraftTransitionResult(
                        ok=False, message=f"Draft {draft_id} is {draft.status}; cannot snooze."
                    )
                draft.status = "snoozed"
                session.commit()
                return DraftTransitionResult(
                    ok=True, message=f"Snoozed draft {draft_id} for later review."
                )
        except SQLAlchemyError:
            return DraftTransitionResult(ok=False, message="Storage unavailable.")
