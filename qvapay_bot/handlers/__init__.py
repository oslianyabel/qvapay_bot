"""PTB-based handlers package. Entry point: build_application()."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from qvapay_bot.handlers.callback_handlers import (
    applied_detail_callback,
    applied_list_page_callback,
    cancel_p2p_callback,
    monitor_on_confirm_callback,
)
from qvapay_bot.handlers.command_handlers import (
    auth_status_command,
    balance_command,
    help_command,
    history_command,
    login_command,
    monitor_off_command,
    monitor_on_command,
    monitor_status_command,
    monitor_test_command,
    rules_show_command,
)
from qvapay_bot.handlers.conversation import (
    build_api_conversation,
    build_rules_conversation,
)
from qvapay_bot.handlers.error_handler import error_handler
from qvapay_bot.http_client import AsyncHttpClient
from qvapay_bot.p2p_monitor import P2PMonitorManager
from qvapay_bot.p2p_repository import P2PMonitorStateStore
from qvapay_bot.qvapay_client import QvaPayClient
from qvapay_bot.state import BotStateStore

if TYPE_CHECKING:
    from qvapay_bot.config import Settings

LOGGER = logging.getLogger(__name__)


async def _post_init(app: Application) -> None:  # type: ignore[type-arg]
    manager: P2PMonitorManager = app.bot_data["p2p_monitor_manager"]
    await manager.restore_jobs(app.job_queue)
    LOGGER.info("post_init complete — monitor jobs restored")


def build_application(settings: Settings) -> Application:  # type: ignore[type-arg]
    http_client = AsyncHttpClient(settings.http_timeout_seconds)
    qvapay_client = QvaPayClient(
        http_client=http_client,
        base_url=settings.qvapay_base_url,
    )
    state_store = BotStateStore(settings.state_file)
    p2p_repository = P2PMonitorStateStore(settings.p2p_state_file)
    p2p_monitor_manager = P2PMonitorManager(
        settings=settings,
        state_store=state_store,
        repository=p2p_repository,
        qvapay_client=qvapay_client,
    )

    app: Application = (  # type: ignore[type-arg]
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .build()
    )

    app.bot_data["settings"] = settings
    app.bot_data["http_client"] = http_client
    app.bot_data["qvapay_client"] = qvapay_client
    app.bot_data["state_store"] = state_store
    app.bot_data["p2p_repository"] = p2p_repository
    app.bot_data["p2p_monitor_manager"] = p2p_monitor_manager

    from telegram.ext import filters

    allowed = filters.Chat(chat_id=settings.allowed_chat_ids)

    # --- Conversation handlers (must be added before generic command handlers) ---
    app.add_handler(build_rules_conversation(allowed))
    app.add_handler(build_api_conversation(allowed))

    # --- Simple command handlers ---
    app.add_handler(CommandHandler(["start", "help"], help_command, filters=allowed))
    app.add_handler(CommandHandler("cancel", help_command, filters=allowed))
    app.add_handler(CommandHandler("auth_status", auth_status_command, filters=allowed))
    app.add_handler(CommandHandler("login", login_command, filters=allowed))
    app.add_handler(CommandHandler("balance", balance_command, filters=allowed))
    app.add_handler(CommandHandler("monitor_on", monitor_on_command, filters=allowed))
    app.add_handler(CommandHandler("monitor_off", monitor_off_command, filters=allowed))
    app.add_handler(
        CommandHandler("monitor_status", monitor_status_command, filters=allowed)
    )
    app.add_handler(CommandHandler("rules_show", rules_show_command, filters=allowed))
    app.add_handler(CommandHandler("history", history_command, filters=allowed))
    app.add_handler(
        CommandHandler("monitor_test", monitor_test_command, filters=allowed)
    )

    # --- Callback query handlers ---
    app.add_handler(CallbackQueryHandler(applied_detail_callback, pattern=r"^adh:"))
    app.add_handler(CallbackQueryHandler(applied_list_page_callback, pattern=r"^adlp:"))
    app.add_handler(CallbackQueryHandler(cancel_p2p_callback, pattern=r"^cp2p:"))
    app.add_handler(
        CallbackQueryHandler(monitor_on_confirm_callback, pattern=r"^mon_on:")
    )

    # --- Error handler ---
    app.add_error_handler(error_handler)

    return app
