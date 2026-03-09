def list_drafts() -> list[dict]:
    from helm_storage.db import SessionLocal
    from helm_storage.models import DraftReplyORM
    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with SessionLocal() as session:
            stmt = (
                select(DraftReplyORM)
                .where(DraftReplyORM.status.in_(("pending", "snoozed")))
                .order_by(DraftReplyORM.created_at.asc())
            )
            records = list(session.scalars(stmt).all())
            return [
                {
                    "id": draft.id,
                    "channel_type": draft.channel_type,
                    "status": draft.status,
                    "preview": draft.draft_text[:120],
                }
                for draft in records
            ]
    except SQLAlchemyError:
        return []
