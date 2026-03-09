def list_actions() -> list[dict]:
    from helm_storage.db import SessionLocal
    from helm_storage.repositories.action_items import SQLAlchemyActionItemRepository
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with SessionLocal() as session:
            repository = SQLAlchemyActionItemRepository(session)
            records = repository.list_open()
            return [
                {
                    "id": item.id,
                    "title": item.title,
                    "priority": item.priority,
                    "status": item.status,
                }
                for item in records
            ]
    except SQLAlchemyError:
        return []
