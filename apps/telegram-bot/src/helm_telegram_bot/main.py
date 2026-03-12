from helm_observability.logging import get_logger, setup_logging
from telegram.ext import Application, CommandHandler

from helm_telegram_bot.commands import actions, approve, digest, drafts, snooze, start, study, workflows
from helm_telegram_bot.config import get_settings


def main() -> None:
    setup_logging()
    logger = get_logger("helm_telegram_bot")
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler("start", start.handle))
    application.add_handler(CommandHandler("digest", digest.handle))
    application.add_handler(CommandHandler("actions", actions.handle))
    application.add_handler(CommandHandler("drafts", drafts.handle))
    application.add_handler(CommandHandler("study", study.handle))
    application.add_handler(CommandHandler("approve", approve.handle))
    application.add_handler(CommandHandler("reject", approve.reject))
    application.add_handler(CommandHandler("request_revision", approve.request_revision))
    application.add_handler(CommandHandler("snooze", snooze.handle))
    application.add_handler(CommandHandler("workflow_start", workflows.start))
    application.add_handler(CommandHandler("workflows", workflows.recent))
    application.add_handler(CommandHandler("workflow_needs_action", workflows.needs_action))
    application.add_handler(CommandHandler("workflow_versions", workflows.versions))
    application.add_handler(CommandHandler("workflow_retry", workflows.retry))
    application.add_handler(CommandHandler("workflow_replay", workflows.replay))
    application.add_handler(CommandHandler("workflow_terminate", workflows.terminate))

    logger.info("telegram_bot_started")
    application.run_polling()


if __name__ == "__main__":
    main()
