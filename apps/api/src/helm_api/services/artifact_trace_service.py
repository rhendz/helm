from __future__ import annotations

from helm_storage.db import SessionLocal
from helm_storage.models import (
    ActionItemORM,
    AgentRunORM,
    DigestItemORM,
    DraftReplyORM,
    OpportunityORM,
)
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError

SUPPORTED_ARTIFACT_TYPES = {"action", "draft", "digest", "opportunity"}


def get_artifact_trace(*, artifact_type: str, artifact_id: int) -> dict:
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        return {
            "status": "not_found",
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "source_pointers": [],
            "run_context": [],
            "reason": "unsupported_artifact_type",
        }

    try:
        with SessionLocal() as session:
            pointers = _resolve_source_pointers(
                session=session,
                artifact_type=artifact_type,
                artifact_id=artifact_id,
            )
            if pointers is None:
                return {
                    "status": "not_found",
                    "artifact_type": artifact_type,
                    "artifact_id": artifact_id,
                    "source_pointers": [],
                    "run_context": [],
                    "reason": "artifact_not_found",
                }

            run_context = _lookup_run_context(session=session, pointers=pointers)
            return {
                "status": "ok",
                "artifact_type": artifact_type,
                "artifact_id": artifact_id,
                "source_pointers": pointers,
                "run_context": run_context,
                "reason": None,
            }
    except SQLAlchemyError:
        return {
            "status": "unavailable",
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "source_pointers": [],
            "run_context": [],
            "reason": "storage_unavailable",
        }


def _resolve_source_pointers(*, session, artifact_type: str, artifact_id: int) -> list[dict] | None:  # noqa: ANN001
    if artifact_type == "action":
        artifact = session.get(ActionItemORM, artifact_id)
        if artifact is None:
            return None
        pointers = [
            {"key": "artifact_id", "value": str(artifact.id)},
            {"key": "source_type", "value": artifact.source_type},
        ]
        if artifact.source_id:
            pointers.append({"key": "source_id", "value": artifact.source_id})
        return pointers

    if artifact_type == "draft":
        artifact = session.get(DraftReplyORM, artifact_id)
        if artifact is None:
            return None
        pointers = [
            {"key": "artifact_id", "value": str(artifact.id)},
            {"key": "channel_type", "value": artifact.channel_type},
        ]
        if artifact.thread_id:
            pointers.append({"key": "thread_id", "value": artifact.thread_id})
        if artifact.contact_id is not None:
            pointers.append({"key": "contact_id", "value": str(artifact.contact_id)})
        return pointers

    if artifact_type == "digest":
        artifact = session.get(DigestItemORM, artifact_id)
        if artifact is None:
            return None
        pointers = [
            {"key": "artifact_id", "value": str(artifact.id)},
            {"key": "domain", "value": artifact.domain},
        ]
        if artifact.related_action_id is not None:
            pointers.append({"key": "related_action_id", "value": str(artifact.related_action_id)})
        if artifact.related_contact_id is not None:
            pointers.append(
                {"key": "related_contact_id", "value": str(artifact.related_contact_id)}
            )
        return pointers

    artifact = session.get(OpportunityORM, artifact_id)
    if artifact is None:
        return None
    pointers = [
        {"key": "artifact_id", "value": str(artifact.id)},
        {"key": "channel_source", "value": artifact.channel_source},
    ]
    if artifact.contact_id is not None:
        pointers.append({"key": "contact_id", "value": str(artifact.contact_id)})
    return pointers


def _lookup_run_context(*, session, pointers: list[dict]) -> list[dict]:  # noqa: ANN001
    source_type = _pointer_value(pointers, "source_type")
    source_id = _pointer_value(pointers, "source_id")
    artifact_id = _pointer_value(pointers, "artifact_id")

    predicates = []
    if source_type and source_id:
        predicates.append(
            and_(
                AgentRunORM.source_type == source_type,
                AgentRunORM.source_id == source_id,
            )
        )
    if artifact_id:
        predicates.append(AgentRunORM.source_id == artifact_id)

    if not predicates:
        return []

    records = list(
        session.execute(
            select(AgentRunORM).where(or_(*predicates)).order_by(AgentRunORM.id.desc()).limit(20)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": run.id,
            "agent_name": run.agent_name,
            "status": run.status,
            "source_type": run.source_type,
            "source_id": run.source_id,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "error_present": bool(run.error_message),
        }
        for run in records
    ]


def _pointer_value(pointers: list[dict], key: str) -> str | None:
    for pointer in pointers:
        if pointer["key"] == key:
            return pointer["value"]
    return None
