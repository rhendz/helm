from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import parse_single_id_arg, reject_if_unauthorized
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    thread_id = parse_single_id_arg(context.args)
    if thread_id is None:
        await update.message.reply_text("Usage: /thread <thread_id>")
        return
    thread = _service.get_thread_detail(thread_id)
    if thread is None:
        await update.message.reply_text(f"Thread {thread_id} not found.")
        return
    labels = ", ".join(thread.visible_labels) if thread.visible_labels else "(none)"
    summary = thread.current_summary or "(no summary)"
    reason = thread.action_reason or "(none)"
    confidence = thread.latest_confidence_band or "(none)"
    proposal = (
        f"{thread.latest_proposal_type} [{thread.latest_proposal_status}]"
        if thread.latest_proposal_type and thread.latest_proposal_status
        else "(none)"
    )
    draft = (
        f"{thread.latest_draft_approval_status}: {thread.latest_draft_preview}"
        if thread.latest_draft_approval_status and thread.latest_draft_preview
        else "(none)"
    )
    latest_message_from = thread.latest_message_from or "(unknown)"
    latest_message_subject = thread.latest_message_subject or "(no subject)"
    latest_message_snippet = thread.latest_message_snippet or "(no snippet)"
    await update.message.reply_text(
        "\n".join(
            [
                f"Thread {thread.id}",
                f"State: {thread.business_state}",
                f"Labels: {labels}",
                f"Confidence: {confidence}",
                f"Reason: {reason}",
                f"Summary: {summary}",
                f"Latest proposal: {proposal}",
                f"Latest draft: {draft}",
                f"Pending tasks: {thread.pending_task_count}",
                f"Latest message from: {latest_message_from}",
                f"Latest message subject: {latest_message_subject}",
                f"Latest message snippet: {latest_message_snippet}",
            ]
        )
    )
