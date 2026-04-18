"""Global error handler for the PTB Application."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from qvapay_bot.handlers.common import send_text

LOGGER = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Unhandled exception", exc_info=context.error)

    chat_id: int | None = None
    if isinstance(update, Update) and update.effective_chat is not None:
        chat_id = update.effective_chat.id

    error_message = str(context.error) if context.error else "Unknown error"

    if chat_id is not None:
        try:
            await send_text(context.bot, chat_id, f"Error: {error_message}")
        except Exception:
            LOGGER.warning("Failed to send error message to chat_id=%s", chat_id)

    settings = context.bot_data.get("settings")
    if settings is not None and settings.telegram_dev_chat_id is not None:
        try:
            await send_text(
                context.bot,
                settings.telegram_dev_chat_id,
                f"Unhandled bot error\nchat_id={chat_id}\n{error_message}",
            )
        except Exception:
            LOGGER.warning("Failed to send error to dev chat")
