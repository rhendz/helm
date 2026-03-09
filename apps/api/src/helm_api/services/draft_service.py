def list_drafts() -> list[dict]:
    from helm_storage.db import SessionLocal
    from helm_storage.repositories.draft_replies import SQLAlchemyDraftReplyRepository
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with SessionLocal() as session:
            repository = SQLAlchemyDraftReplyRepository(session)
            records = repository.list_pending()
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
