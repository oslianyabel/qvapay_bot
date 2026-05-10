"""Simple command handlers (no conversation state needed)."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from qvapay_bot.handlers.common import (
    CUSTOM_HELP,
    fetch_coin_averages,
    format_average_response,
    format_help_for_command,
    refresh_applied_statuses,
    reply_text,
    reply_with_keyboard,
    validate_monitor_rules,
)
from qvapay_bot.p2p_formatter import (
    format_applied_list_keyboard,
    format_cycle_report,
    format_monitor_on_confirmation,
    format_monitor_status,
    format_rules,
)
from qvapay_bot.qvapay_client import (
    COMMAND_INDEX,
    COMMAND_SPECS,
    CommandSpec,
    pretty_payload,
)

LOGGER = logging.getLogger(__name__)

MONITOR_ON_CONFIRM_CALLBACK_PREFIX = "mon_on:"


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is None or update.effective_chat is None:
        return

    args = context.args
    command_name = ""
    if args:
        command_name = args[0].strip().removeprefix("/")

    if command_name:
        if command_name in CUSTOM_HELP:
            await reply_text(update, CUSTOM_HELP[command_name])
            return
        spec = COMMAND_INDEX.get(command_name)
        if spec is None or spec.command not in {s.command for s in COMMAND_SPECS}:
            await reply_text(update, f"Comando no encontrado: /{command_name}")
            return
        await reply_text(update, format_help_for_command(spec))
        return

    sections = [
        "Utilidades:",
        "/help command - Muestra ayuda de un comando",
        "/cancel - Cancela la acción pendiente",
        "/auth_status - Muestra el estado de autenticación",
        "",
        "Monitor P2P:",
        "/monitor_on - Activa el monitor P2P para este chat",
        "/monitor_off - Desactiva el monitor P2P",
        "/monitor_status - Muestra el estado y configuración del monitor",
        "/rules - Configura una regla del monitor de forma interactiva",
        "/rules_show - Muestra las reglas P2P activas",
        "/history - Lista las últimas ofertas procesadas por el monitor",
        "/monitor_test - Ejecuta un ciclo de monitoreo y muestra el resultado",
        "",
        "Comandos QvaPay:",
        "/balance - Muestra el saldo disponible en tu cuenta",
    ]
    sections.extend(f"/{spec.command} - {spec.description}" for spec in COMMAND_SPECS)
    await reply_text(update, "\n".join(sections))


async def auth_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    state_store = context.bot_data["state_store"]
    state = state_store.get_chat_state(chat_id)
    status_lines = [
        f"Token de acceso configurado: {'sí' if state.has_bearer else 'no'}",
        f"Credenciales de la app configuradas: {'sí' if state.has_app_credentials else 'no'}",
        f"UUID de usuario: {state.user_uuid or '-'}",
        f"Nombre de usuario: {state.username or '-'}",
    ]
    await reply_text(update, "\n".join(status_lines))


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    state_store = context.bot_data["state_store"]
    qvapay_client = context.bot_data["qvapay_client"]
    auth_state = state_store.get_chat_state(chat_id)

    if not auth_state.has_bearer:
        await reply_text(update, "Debes iniciar sesión para consultar el saldo.")
        return

    response = await qvapay_client.execute(COMMAND_INDEX["profile"], {}, auth_state)
    if response.status_code == 200 and isinstance(response.body, dict):
        balance = response.body.get("balance")
        username = response.body.get("username") or auth_state.username or "-"
        balance_str = (
            f"{balance:.2f}" if isinstance(balance, (int, float)) else str(balance)
        )
        await reply_text(
            update,
            f"💰 Saldo disponible\nUsuario: {username}\nBalance: {balance_str} QUSD",
        )
    else:
        await reply_text(
            update,
            f"Error al obtener el saldo.\nHTTP {response.status_code}\n{pretty_payload(response.body)}",
        )


async def monitor_on_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    p2p_repository = context.bot_data["p2p_repository"]
    monitor_state = p2p_repository.get_chat_state(chat_id)

    try:
        validate_monitor_rules(monitor_state.rules)
    except ValueError as exc:
        await reply_text(update, str(exc))
        return

    poll_interval = monitor_state.poll_interval_seconds
    confirmation_text = format_monitor_on_confirmation(monitor_state, poll_interval)
    keyboard_rows = [
        [
            {
                "text": "✅ Confirmar",
                "callback_data": f"{MONITOR_ON_CONFIRM_CALLBACK_PREFIX}confirm:{poll_interval}",
            },
            {
                "text": "❌ Cancelar",
                "callback_data": f"{MONITOR_ON_CONFIRM_CALLBACK_PREFIX}cancel",
            },
        ]
    ]
    await reply_with_keyboard(
        update, confirmation_text, keyboard_rows, parse_mode="HTML"
    )


async def monitor_off_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    p2p_repository = context.bot_data["p2p_repository"]
    p2p_monitor_manager = context.bot_data["p2p_monitor_manager"]
    monitor_state = p2p_repository.get_chat_state(chat_id)
    monitor_state.enabled = False
    p2p_repository.save_chat_state(chat_id, monitor_state)
    await p2p_monitor_manager.stop_chat(chat_id, context.job_queue)
    await reply_text(update, "⏹ Monitoreo desactivado.")


async def monitor_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    p2p_repository = context.bot_data["p2p_repository"]
    state_store = context.bot_data["state_store"]
    qvapay_client = context.bot_data["qvapay_client"]
    monitor_state = p2p_repository.get_chat_state(chat_id)
    auth_state = state_store.get_chat_state(chat_id)
    balance: float | None = None
    if auth_state.has_bearer:
        response = await qvapay_client.execute(COMMAND_INDEX["profile"], {}, auth_state)
        if response.status_code == 200 and isinstance(response.body, dict):
            raw = response.body.get("balance")
            if isinstance(raw, (int, float)):
                balance = float(raw)
    await reply_text(update, format_monitor_status(monitor_state, balance))


async def rules_show_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    p2p_repository = context.bot_data["p2p_repository"]
    monitor_state = p2p_repository.get_chat_state(chat_id)
    await reply_text(update, format_rules(monitor_state))


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id

    await refresh_applied_statuses(context, chat_id)

    p2p_repository = context.bot_data["p2p_repository"]
    monitor_state = p2p_repository.get_chat_state(chat_id)
    coin_averages = await fetch_coin_averages(context)
    header, keyboard_rows = format_applied_list_keyboard(
        monitor_state.applied_history,
        monitor_state.lost_race_history,
        page=0,
        coin_averages=coin_averages,
    )
    if keyboard_rows:
        await reply_with_keyboard(update, header, keyboard_rows, parse_mode="HTML")
    else:
        await reply_text(update, header)


async def monitor_test_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    state_store = context.bot_data["state_store"]
    p2p_monitor_manager = context.bot_data["p2p_monitor_manager"]
    auth_state = state_store.get_chat_state(chat_id)
    report = await p2p_monitor_manager.run_cycle_once(
        chat_id,
        auth_state,
        force=True,
        notify=False,
        dry_run=True,
    )
    await reply_text(update, format_cycle_report(report))


def _format_api_response(
    spec: CommandSpec,
    status_code: int,
    payload: Any,
) -> str:
    if spec.command == "average" and status_code == 200 and isinstance(payload, dict):
        return format_average_response(payload)
    return f"/{spec.command}\nHTTP {status_code}\n\n{pretty_payload(payload)}"
