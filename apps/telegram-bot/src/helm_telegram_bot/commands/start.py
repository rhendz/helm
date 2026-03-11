from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    await update.message.reply_text(
        "\n".join(
            [
                "Helm bot is online.",
                "Job controls: /jobs, /jobs paused, /jobs active, /job <job_name>",
            ]
        )
    )
