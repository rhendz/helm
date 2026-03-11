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
    draft_id = parse_single_id_arg(context.args)
    if draft_id is None:
        await update.message.reply_text("Usage: /draft <draft_id>")
        return
    draft = _service.get_draft_detail(draft_id)
    if draft is None:
        await update.message.reply_text(f"Draft {draft_id} not found.")
        return
    subject = draft.draft_subject or "(no subject)"
    proposal = draft.action_proposal_id if draft.action_proposal_id is not None else "(none)"
    audit_lines = ["(none)"]
    if draft.transition_audits:
        audit_lines = [
            (
                f"{item['action']}: {item['from_status']} -> {item['to_status']} "
                f"({'ok' if item['success'] else 'failed'})"
            )
            for item in draft.transition_audits[:3]
        ]
    send_attempt_lines = ["(none)"]
    if draft.send_attempts:
        send_attempt_lines = [
            f"{item['attempt_number']}: {item['status']}"
            f"{' ' + item['failure_class'] if item.get('failure_class') else ''}"
            for item in draft.send_attempts[:3]
        ]
    await update.message.reply_text(
        "\n".join(
            [
                f"Draft {draft.id}",
                f"Thread: {draft.email_thread_id}",
                f"Proposal: {proposal}",
                f"Status: {draft.status}",
                f"Approval: {draft.approval_status}",
                f"Subject: {subject}",
                f"Body: {draft.draft_body}",
                "Recent audits:",
                *audit_lines,
                "Recent send attempts:",
                *send_attempt_lines,
            ]
        )
    )
