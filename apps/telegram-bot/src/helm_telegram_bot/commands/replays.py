from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized
from helm_telegram_bot.services.command_service import TelegramCommandService

_VALID_STATUSES = {"pending", "processing", "completed", "failed", "dead_lettered"}
_service = TelegramCommandService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    if len(context.args) > 1:
        await update.message.reply_text(
            "Usage: /replays [pending|processing|completed|failed|dead_lettered]"
        )
        return
    status = context.args[0] if context.args else None
    if status is not None and status not in _VALID_STATUSES:
        await update.message.reply_text(
            "Usage: /replays [pending|processing|completed|failed|dead_lettered]"
        )
        return
    items = _service.list_replay_queue(status=status)
    if not items:
        if status is None:
            await update.message.reply_text("No replay items.")
            return
        await update.message.reply_text(f"No replay items with status {status}.")
        return
    title = "Replay items:" if status is None else f"Replay items ({status}):"
    lines = [title]
    for item in items:
        source_id = item.source_id or "(none)"
        run_context = ""
        if item.agent_run_id is not None:
            agent_name = item.agent_name or "unknown_agent"
            run_context = f" run={agent_name}#{item.agent_run_id}"
        error = f" last_error={item.last_error}" if item.last_error else ""
        origin_error = ""
        if item.agent_run_error_message and item.agent_run_error_message != item.last_error:
            origin_error = f" origin_error={item.agent_run_error_message}"
        lines.append(
            f"{item.id}: {item.status} attempts={item.attempts} "
            f"{item.source_type}/{source_id}{run_context}{error}{origin_error}"
        )
    await update.message.reply_text("\n".join(lines))
