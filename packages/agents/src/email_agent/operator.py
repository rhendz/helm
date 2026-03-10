from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError

from email_agent.runtime import EmailAgentRuntime


@dataclass(frozen=True, slots=True)
class DraftTransitionResult:
    ok: bool
    message: str


@dataclass(frozen=True, slots=True)
class ActionView:
    id: int
    priority: int
    title: str


@dataclass(frozen=True, slots=True)
class DraftView:
    id: int
    status: str
    draft_text: str


def list_open_actions(
    *,
    limit: int = 5,
    runtime: EmailAgentRuntime,
) -> list[ActionView]:
    try:
        items = runtime.list_email_threads(limit=limit * 4)
    except SQLAlchemyError:
        return []

    results: list[ActionView] = []
    for item in items:
        if "Action" not in item.get("visible_labels", []):
            continue
        title = item.get("current_summary") or f"Thread {item['provider_thread_id']}"
        priority = 1 if "Urgent" in item.get("visible_labels", []) else 2
        results.append(ActionView(id=item["id"], priority=priority, title=title))
        if len(results) >= limit:
            break
    return results


def list_pending_drafts(
    *,
    limit: int = 5,
    runtime: EmailAgentRuntime,
) -> list[DraftView]:
    try:
        items = runtime.list_email_drafts(limit=limit, approval_status="pending_user")
        items.extend(runtime.list_email_drafts(limit=limit, approval_status="snoozed"))
    except SQLAlchemyError:
        return []

    results: list[DraftView] = []
    for item in items:
        if item.get("approval_status") not in {"pending_user", "snoozed"}:
            continue
        results.append(
            DraftView(
                id=item["id"],
                status=item["approval_status"],
                draft_text=item["preview"],
            )
        )
        if len(results) >= limit:
            break
    return results


def approve_draft(
    draft_id: int,
    *,
    runtime: EmailAgentRuntime,
) -> DraftTransitionResult:
    try:
        draft = runtime.get_email_draft_by_id(draft_id)
    except SQLAlchemyError:
        return DraftTransitionResult(ok=False, message="Storage unavailable.")
    if draft is None:
        runtime.create_draft_transition_audit(
            draft_id=draft_id,
            action="approve",
            from_status=None,
            to_status=None,
            success=False,
            reason="draft_not_found",
        )
        return DraftTransitionResult(ok=False, message=f"Draft {draft_id} not found.")
    if draft["approval_status"] not in {"pending_user", "snoozed"}:
        status = draft["approval_status"]
        runtime.create_draft_transition_audit(
            draft_id=draft_id,
            action="approve",
            from_status=status,
            to_status=status,
            success=False,
            reason="invalid_transition",
        )
        return DraftTransitionResult(
            ok=False,
            message=f"Draft {draft_id} is {status}; cannot approve.",
        )
    runtime.set_email_draft_approval_status(
        draft_id,
        approval_status="approved",
    )
    runtime.create_draft_transition_audit(
        draft_id=draft_id,
        action="approve",
        from_status=draft["approval_status"],
        to_status="approved",
        success=True,
        reason=None,
    )
    return DraftTransitionResult(
        ok=True,
        message=f"Approved draft {draft_id}. Not sent yet.",
    )


def snooze_draft(
    draft_id: int,
    *,
    runtime: EmailAgentRuntime,
) -> DraftTransitionResult:
    try:
        draft = runtime.get_email_draft_by_id(draft_id)
    except SQLAlchemyError:
        return DraftTransitionResult(ok=False, message="Storage unavailable.")
    if draft is None:
        runtime.create_draft_transition_audit(
            draft_id=draft_id,
            action="snooze",
            from_status=None,
            to_status=None,
            success=False,
            reason="draft_not_found",
        )
        return DraftTransitionResult(ok=False, message=f"Draft {draft_id} not found.")
    if draft["approval_status"] != "pending_user":
        status = draft["approval_status"]
        runtime.create_draft_transition_audit(
            draft_id=draft_id,
            action="snooze",
            from_status=status,
            to_status=status,
            success=False,
            reason="invalid_transition",
        )
        return DraftTransitionResult(
            ok=False,
            message=f"Draft {draft_id} is {status}; cannot snooze.",
        )
    runtime.set_email_draft_approval_status(
        draft_id,
        approval_status="snoozed",
    )
    runtime.create_draft_transition_audit(
        draft_id=draft_id,
        action="snooze",
        from_status=draft["approval_status"],
        to_status="snoozed",
        success=True,
        reason=None,
    )
    return DraftTransitionResult(
        ok=True,
        message=f"Snoozed draft {draft_id} for later review.",
    )
