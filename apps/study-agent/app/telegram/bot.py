from __future__ import annotations

from app.telegram.handlers import register_handlers
from telegram.ext import ApplicationBuilder


def build_application(token: str, llm_client):
    application = ApplicationBuilder().token(token).build()
    register_handlers(application, llm_client)
    return application
