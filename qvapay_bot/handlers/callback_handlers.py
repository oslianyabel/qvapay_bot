"""CallbackQuery handlers for inline button interactions."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from qvapay_bot.handlers.common import (
    fetch_coin_averages,
    reply_text,
    reply_with_keyboard,
)
from qvapay_bot.p2p_formatter import (
    format_applied_detail,
    format_applied_list_keyboard,
    format_monitor_status,
)
from qvapay_bot.qvapay_client import COMMAND_INDEX, pretty_payload

LOGGER = logging.getLogger(__name__)


async def applied_detail_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None or update.effective_chat is None:
        return
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data or ""
    payload = data[len("adh:") :]

    if len(payload) >= 37 and payload[36] == ":":
        uuid = payload[:36]
        evaluated_at = payload[37:]
    else:
        uuid = payload
        evaluated_at = ""

    p2p_repository = context.bot_data["p2p_repository"]
    monitor_state = p2p_repository.get_chat_state(chat_id)
    entry = None
    for collection in (monitor_state.applied_history, monitor_state.lost_race_history):
        for e in collection:
            if e.uuid == uuid and (not evaluated_at or e.evaluated_at == evaluated_at):
                entry = e
                break
        if entry is not None:
            break

    if entry is None:
        await reply_text(update, f"No se encontraron datos para la oferta {uuid}.")
        return

    await reply_text(update, format_applied_detail(entry), parse_mode="HTML")


async def applied_list_page_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None or update.effective_chat is None:
        return
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data or ""
    raw_page = data[len("adlp:") :]
    try:
        page = int(raw_page)
    except ValueError:
        page = 0

    p2p_repository = context.bot_data["p2p_repository"]
    monitor_state = p2p_repository.get_chat_state(chat_id)
    coin_averages = await fetch_coin_averages(context)
    header, keyboard_rows = format_applied_list_keyboard(
        monitor_state.applied_history,
        monitor_state.lost_race_history,
        page=page,
        coin_averages=coin_averages,
    )
    if keyboard_rows:
        await reply_with_keyboard(update, header, keyboard_rows, parse_mode="HTML")
    else:
        await reply_text(update, header)


async def cancel_p2p_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None or update.effective_chat is None:
        return
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data or ""
    payload = data[len("cp2p:") :]

    if len(payload) >= 37 and payload[36] == ":":
        uuid = payload[:36]
    else:
        uuid = payload

    state_store = context.bot_data["state_store"]
    qvapay_client = context.bot_data["qvapay_client"]
    p2p_repository = context.bot_data["p2p_repository"]
    auth_state = state_store.get_chat_state(chat_id)

    if not auth_state.has_bearer:
        await reply_text(update, "Debes iniciar sesión para cancelar una oferta.")
        return

    response = await qvapay_client.execute(
        COMMAND_INDEX["cancel_p2p"],
        {"uuid": uuid},
        auth_state,
    )
    if response.status_code < 400:
        monitor_state = p2p_repository.get_chat_state(chat_id)
        for entry in monitor_state.applied_history:
            if entry.uuid == uuid:
                entry.status = "cancelled"
                break
        p2p_repository.save_chat_state(chat_id, monitor_state)
        await reply_text(update, f"Oferta {uuid} cancelada correctamente.")
    else:
        await reply_text(
            update,
            f"Error al cancelar la oferta.\nHTTP {response.status_code}\n{pretty_payload(response.body)}",
        )


async def monitor_on_confirm_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None or update.effective_chat is None:
        return
    await query.answer()

    chat_id = update.effective_chat.id
    data = query.data or ""
    payload = data[len("mon_on:") :]

    if payload == "cancel":
        await reply_text(update, "Activación del monitor cancelada.")
        return

    if payload.startswith("confirm:"):
        interval_str = payload[len("confirm:") :]
        try:
            poll_interval = int(interval_str)
        except ValueError:
            await reply_text(update, "Error: intervalo inválido.")
            return

        state_store = context.bot_data["state_store"]
        p2p_repository = context.bot_data["p2p_repository"]
        p2p_monitor_manager = context.bot_data["p2p_monitor_manager"]
        auth_state = state_store.get_chat_state(chat_id)
        monitor_state = p2p_repository.get_chat_state(chat_id)
        monitor_state.enabled = True
        monitor_state.poll_interval_seconds = poll_interval
        p2p_repository.save_chat_state(chat_id, monitor_state)
        await p2p_monitor_manager.restart_chat(chat_id, auth_state, context.job_queue)
        await reply_text(update, format_monitor_status(monitor_state))
