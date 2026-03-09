def list_drafts() -> list[dict]:
    from helm_storage.db import SessionLocal
    from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with SessionLocal() as session:
            repository = SQLAlchemyDraftReplyRepository(session)
            stale_ids = {
                row.id
                for row in repository.list_stale(
                    stale_after_hours=72,
                    include_snoozed=True,
                )
            }
            records = repository.list_pending()
            return [
                {
                    "id": draft.id,
                    "channel_type": draft.channel_type,
                    "status": draft.status,
                    "preview": draft.draft_text[:120],
                    "is_stale": draft.id in stale_ids,
                }
                for draft in records
            ]
    except SQLAlchemyError:
        return []


def requeue_stale_drafts(*, stale_after_hours: int, limit: int, dry_run: bool) -> dict:
    from helm_storage.db import SessionLocal
    from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with SessionLocal() as session:
            repository = SQLAlchemyDraftReplyRepository(session)
            stale = repository.list_stale(
                stale_after_hours=stale_after_hours,
                include_snoozed=True,
                limit=limit,
            )
            stale_ids = [row.id for row in stale]

            requeued_count = 0
            if not dry_run:
                for row in stale:
                    if row.status == "snoozed" and repository.requeue(row.id):
                        requeued_count += 1

            return {
                "status": "accepted",
                "stale_after_hours": stale_after_hours,
                "dry_run": dry_run,
                "matched_count": len(stale_ids),
                "requeued_count": requeued_count,
                "draft_ids": stale_ids,
            }
    except SQLAlchemyError:
        return {
            "status": "unavailable",
            "stale_after_hours": stale_after_hours,
            "dry_run": dry_run,
            "matched_count": 0,
            "requeued_count": 0,
            "draft_ids": [],
        }
