from __future__ import annotations

from email_agent.adapters import build_helm_runtime
from email_agent.operator import (
    DraftTransitionResult,
    approve_draft,
    list_open_actions,
    list_pending_drafts,
    snooze_draft,
)
from helm_observability.logging import get_logger

logger = get_logger("helm_telegram_bot.services.command_service")


class TelegramCommandService:
    def list_open_actions(self, *, limit: int = 5) -> list[object]:
        return list_open_actions(limit=limit, runtime=build_helm_runtime())

    def list_pending_drafts(self, *, limit: int = 5) -> list[object]:
        return list_pending_drafts(limit=limit, runtime=build_helm_runtime())

    def approve_draft(self, draft_id: int) -> DraftTransitionResult:
        result = approve_draft(draft_id, runtime=build_helm_runtime())
        if not result.ok:
            logger.warning("draft_transition_failed", action="approve", draft_id=draft_id)
        return result

    def snooze_draft(self, draft_id: int) -> DraftTransitionResult:
        result = snooze_draft(draft_id, runtime=build_helm_runtime())
        if not result.ok:
            logger.warning("draft_transition_failed", action="snooze", draft_id=draft_id)
        return result
