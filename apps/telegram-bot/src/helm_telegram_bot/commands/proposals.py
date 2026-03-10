from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import (
    _INVALID_ARG,
    parse_optional_choice_arg,
    reject_if_unauthorized,
)
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()
_ALLOWED_TYPES = {"reply", "review"}


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    proposal_type = parse_optional_choice_arg(context.args, allowed=_ALLOWED_TYPES)
    if proposal_type is _INVALID_ARG:
        await update.message.reply_text("Usage: /proposals [reply|review]")
        return
    proposals = _service.list_proposals(proposal_type=proposal_type)
    if not proposals:
        if proposal_type is None:
            await update.message.reply_text("No proposed email actions.")
        else:
            await update.message.reply_text(f"No {proposal_type} proposals.")
        return
    title = "Email proposals:" if proposal_type is None else f"Proposals ({proposal_type}):"
    lines = [title]
    for proposal in proposals:
        rationale = proposal.rationale or "(no rationale)"
        lines.append(f"{proposal.id}: thread {proposal.email_thread_id} {rationale}")
    await update.message.reply_text("\n".join(lines))
