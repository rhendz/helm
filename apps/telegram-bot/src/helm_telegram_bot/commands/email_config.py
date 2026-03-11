from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized
from helm_telegram_bot.services.command_service import TelegramCommandService

_service = TelegramCommandService()


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    config = _service.get_email_config()
    lines = [
        "Email config:",
        f"timezone: {config.timezone_name}",
        f"followup_business_days: {config.default_follow_up_business_days}",
        f"approval_required_before_send: {str(config.approval_required_before_send).lower()}",
    ]
    await update.message.reply_text("\n".join(lines))
