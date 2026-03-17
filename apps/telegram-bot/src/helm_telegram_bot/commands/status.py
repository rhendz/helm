from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized
from helm_telegram_bot.config import get_settings
from helm_telegram_bot.services.workflow_status_service import TelegramWorkflowStatusService

_service = TelegramWorkflowStatusService()


def _format_status(
    pending: list[dict[str, object]],
    recent: list[dict[str, object]],
    timezone: str,
) -> str:
    lines: list[str] = [f"📋 Helm Status\nTimezone: {timezone}"]

    # Pending approvals section
    lines.append("")
    if pending:
        lines.append("⏳ Pending approvals:")
        for run in pending:
            run_id = run["id"]
            checkpoint = run.get("approval_checkpoint")
            if isinstance(checkpoint, dict):
                proposal_summary = checkpoint.get("proposal_summary") or "Proposal available"
                artifact_id = checkpoint.get("target_artifact_id")
                lines.append(
                    f"• Run {run_id} — {proposal_summary}\n"
                    f"  /approve {run_id} {artifact_id} to confirm"
                )
            else:
                lines.append(f"• Run {run_id} — needs action")
    else:
        lines.append("✅ No pending approvals.")

    # Recent completions section
    lines.append("")
    if recent:
        lines.append("Recent completions:")
        for run in recent:
            workflow_type = run.get("workflow_type") or "workflow"
            completion_summary = run.get("completion_summary")
            if isinstance(completion_summary, dict):
                headline = completion_summary.get("headline") or run.get("last_event_summary") or "completed"
            else:
                headline = run.get("last_event_summary") or "completed"
            lines.append(f"• {workflow_type} — {headline}")
    else:
        lines.append("No recent activity.")

    return "\n".join(lines)


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return

    pending = _service.list_runs_needing_action(limit=5)
    recent = _service.list_recent_runs(limit=5)
    timezone = get_settings().operator_timezone

    text = _format_status(pending, recent, timezone)
    await update.message.reply_text(text)
