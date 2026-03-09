def list_actions() -> list[dict]:
    from helm_storage.db import SessionLocal
    from helm_storage.models import ActionItemORM
    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError

    try:
        with SessionLocal() as session:
            stmt = (
                select(ActionItemORM)
                .where(ActionItemORM.status == "open")
                .order_by(ActionItemORM.priority.asc(), ActionItemORM.created_at.asc())
            )
            records = list(session.scalars(stmt).all())
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
