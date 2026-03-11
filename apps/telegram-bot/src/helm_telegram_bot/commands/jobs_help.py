from telegram import Update
from telegram.ext import ContextTypes

from helm_telegram_bot.commands.common import reject_if_unauthorized


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_if_unauthorized(update, context):
        return
    if not update.message:
        return
    await update.message.reply_text(
        "\n".join(
            [
                "Job control commands:",
                "/jobs - list all jobs",
                "/jobs paused - list paused jobs",
                "/jobs active - list active jobs",
                "/job <job_name> - inspect one job",
                "/pause_job <job_name> - pause a job",
                "/resume_job <job_name> - resume a job",
                "/run_job <job_name> - run a manually runnable job",
                "/run_replay [limit] - run bounded replay work",
            ]
        )
    )
