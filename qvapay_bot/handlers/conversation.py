"""ConversationHandlers for multi-step flows: /rules and generic API commands."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from qvapay_bot.handlers.common import (
    CANCEL_COMMAND,
    FIELD_PROMPTS,
    LOGIN_USER_CALLBACK_PREFIX,
    MIN_P2P_POLL_INTERVAL_SECONDS,
    P2P_OFFER_TYPE_CALLBACK_PREFIX,
    P2P_RULE_COIN_CALLBACK_PREFIX,
    P2P_RULE_COIN_OPTIONS,
    P2P_RULE_NAME_CALLBACK_PREFIX,
    P2P_RULE_NAME_OPTIONS,
    RULE_DYNAMIC_FIELDS,
    RULE_NAME_ALIASES,
    apply_profile_payload,
    format_rule_change,
    parse_offer_type,
    parse_yes_no,
    reply_text,
    reply_with_keyboard,
    to_optional_float,
    validate_monitor_rules,
)
from qvapay_bot.p2p_models import P2PMonitorRules, P2POfferType
from qvapay_bot.qvapay_client import (
    COMMAND_INDEX,
    COMMAND_SPECS,
    CommandSpec,
    parse_scalar,
    pretty_payload,
)
from qvapay_bot.state import ChatAuthState

LOGGER = logging.getLogger(__name__)

# ConversationHandler states
RULE_NAME, RULE_VALUE = range(2)
API_FIELD = 10
LOGIN_USER = 20


# ---------------------------------------------------------------------------
# /rules ConversationHandler
# ---------------------------------------------------------------------------


async def _rules_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat is None:
        return ConversationHandler.END
    keyboard_rows = [
        [{"text": label, "callback_data": f"{P2P_RULE_NAME_CALLBACK_PREFIX}{key}"}]
        for key, label in P2P_RULE_NAME_OPTIONS
    ]
    await reply_with_keyboard(update, "¿Qué regla deseas configurar?", keyboard_rows)
    context.user_data["rules_args"] = {}  # type: ignore[index]
    return RULE_NAME


async def _rules_name_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()
    raw = (query.data or "")[len(P2P_RULE_NAME_CALLBACK_PREFIX) :]
    return await _process_rule_name(update, context, raw)


async def _rules_name_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return ConversationHandler.END
    raw = (update.effective_message.text or "").strip()
    return await _process_rule_name(update, context, raw)


async def _process_rule_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str
) -> int:
    normalized = RULE_NAME_ALIASES.get(raw.strip().lower())
    if normalized is None:
        await reply_text(
            update,
            "Regla no válida. Usa coin, ratio, amount, only_kyc, only_vip, offer_type o reset.",
        )
        return RULE_NAME

    context.user_data["rules_args"]["rule_name"] = normalized  # type: ignore[index]
    dynamic_fields = RULE_DYNAMIC_FIELDS[normalized]

    if not dynamic_fields:
        # "reset" — execute immediately
        return await _execute_rules(update, context)

    context.user_data["rules_fields"] = list(dynamic_fields)  # type: ignore[index]
    context.user_data["rules_field_idx"] = 0  # type: ignore[index]
    return await _prompt_next_rule_value(update, context)


async def _prompt_next_rule_value(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    fields: list[str] = context.user_data.get("rules_fields", [])  # type: ignore[assignment]
    idx: int = context.user_data.get("rules_field_idx", 0)  # type: ignore[assignment]
    if idx >= len(fields):
        return await _execute_rules(update, context)

    field_name = fields[idx]
    chat_id = update.effective_chat.id if update.effective_chat else None

    # Build keyboard for specific fields
    keyboard_rows: list[list[dict[str, str]]] = []
    if field_name == "rule_coin":
        prompt = "Selecciona la moneda. Envía /cancel para cancelar."
        keyboard_rows = [
            [{"text": c, "callback_data": f"{P2P_RULE_COIN_CALLBACK_PREFIX}{c}"}]
            for c in P2P_RULE_COIN_OPTIONS
        ]
    elif field_name == "target_type":
        prompt = (
            "Selecciona el tipo de oferta para el monitor. Envía /cancel para cancelar."
        )
        coin: str | None = None
        if chat_id is not None:
            p2p_repository = context.bot_data["p2p_repository"]
            coin = p2p_repository.get_chat_state(chat_id).rules.coin
        coin_label = coin or "la moneda"
        keyboard_rows = [
            [
                {
                    "text": f"🛒 Comprar — Compras QUSD, vendes {coin_label}",
                    "callback_data": f"{P2P_OFFER_TYPE_CALLBACK_PREFIX}sell",
                }
            ],
            [
                {
                    "text": f"💰 Vender — Vendes QUSD, compras {coin_label}",
                    "callback_data": f"{P2P_OFFER_TYPE_CALLBACK_PREFIX}buy",
                }
            ],
        ]
    else:
        prompt = FIELD_PROMPTS.get(field_name, f"Envía el valor para {field_name}.")
        prompt = f"{prompt} Envía {CANCEL_COMMAND} para cancelar."

    if keyboard_rows:
        await reply_with_keyboard(update, prompt, keyboard_rows)
    else:
        await reply_text(update, prompt)
    return RULE_VALUE


async def _rule_value_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()
    data = query.data or ""

    for prefix, _field in (
        (P2P_RULE_COIN_CALLBACK_PREFIX, "rule_coin"),
        (P2P_OFFER_TYPE_CALLBACK_PREFIX, "target_type"),
    ):
        if data.startswith(prefix):
            raw = data[len(prefix) :]
            return await _process_rule_value(update, context, raw)
    return RULE_VALUE


async def _rule_value_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None:
        return ConversationHandler.END
    raw = (update.effective_message.text or "").strip()
    return await _process_rule_value(update, context, raw)


async def _process_rule_value(
    update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str
) -> int:
    fields: list[str] = context.user_data.get("rules_fields", [])  # type: ignore[assignment]
    idx: int = context.user_data.get("rules_field_idx", 0)  # type: ignore[assignment]
    field_name = fields[idx]

    try:
        parsed = _parse_rule_field_value(field_name, raw)
    except ValueError as exc:
        await reply_text(update, str(exc))
        return RULE_VALUE

    context.user_data["rules_args"][field_name] = parsed  # type: ignore[index]
    context.user_data["rules_field_idx"] = idx + 1  # type: ignore[index]

    if idx + 1 >= len(fields):
        return await _execute_rules(update, context)

    return await _prompt_next_rule_value(update, context)


async def _execute_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat is None:
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    arguments: dict[str, Any] = context.user_data.get("rules_args", {})  # type: ignore[assignment]
    rule_name = str(arguments.get("rule_name", ""))

    p2p_repository = context.bot_data["p2p_repository"]
    state_store = context.bot_data["state_store"]
    p2p_monitor_manager = context.bot_data["p2p_monitor_manager"]
    auth_state = state_store.get_chat_state(chat_id)
    monitor_state = p2p_repository.get_chat_state(chat_id)

    try:
        if rule_name == "reset":
            monitor_state.rules = P2PMonitorRules()
            monitor_state.target_type = P2POfferType.ANY
        elif rule_name == "coin":
            rule_coin = arguments.get("rule_coin")
            monitor_state.rules.coin = (
                str(rule_coin) if isinstance(rule_coin, str) else None
            )
        elif rule_name == "ratio":
            monitor_state.rules.min_ratio = to_optional_float(
                arguments.get("min_ratio")
            )
            monitor_state.rules.max_ratio = to_optional_float(
                arguments.get("max_ratio")
            )
        elif rule_name == "amount":
            min_amount = to_optional_float(arguments.get("min_amount"))
            max_amount = to_optional_float(arguments.get("max_amount"))
            if monitor_state.target_type == P2POfferType.BUY:
                balance = await p2p_monitor_manager.fetch_balance(auth_state)
                if balance is not None:
                    if min_amount is not None and min_amount > balance:
                        raise ValueError(
                            f"El monto mínimo ({min_amount}) excede tu saldo ({balance:.2f} QUSD)."
                        )
                    if max_amount is not None and max_amount > balance:
                        raise ValueError(
                            f"El monto máximo ({max_amount}) excede tu saldo ({balance:.2f} QUSD)."
                        )
            monitor_state.rules.min_amount = min_amount
            monitor_state.rules.max_amount = max_amount
        elif rule_name == "only_kyc":
            monitor_state.rules.only_kyc = parse_yes_no(arguments.get("rule_boolean"))
        elif rule_name == "only_vip":
            monitor_state.rules.only_vip = parse_yes_no(arguments.get("rule_boolean"))
        elif rule_name == "offer_type":
            new_type = parse_offer_type(arguments.get("target_type"))
            if new_type == P2POfferType.BUY:
                balance = await p2p_monitor_manager.fetch_balance(auth_state)
                if balance is not None:
                    rules = monitor_state.rules
                    if rules.min_amount is not None and rules.min_amount > balance:
                        raise ValueError(
                            f"El monto mínimo actual ({rules.min_amount}) excede tu saldo ({balance:.2f} QUSD). Ajusta la regla de monto primero."
                        )
                    if rules.max_amount is not None and rules.max_amount > balance:
                        raise ValueError(
                            f"El monto máximo actual ({rules.max_amount}) excede tu saldo ({balance:.2f} QUSD). Ajusta la regla de monto primero."
                        )
            monitor_state.target_type = new_type
        elif rule_name == "poll_interval":
            poll_interval = arguments.get("poll_interval_seconds")
            if not isinstance(poll_interval, int):
                raise ValueError("Intervalo de consulta inválido.")
            monitor_state.poll_interval_seconds = poll_interval
        else:
            raise ValueError(f"Regla no soportada: {rule_name}")

        validate_monitor_rules(monitor_state.rules)
        p2p_repository.save_chat_state(chat_id, monitor_state)
        await p2p_monitor_manager.restart_chat(chat_id, auth_state, context.job_queue)
        await reply_text(update, format_rule_change(rule_name, monitor_state))
    except ValueError as exc:
        await reply_text(update, str(exc))

    return ConversationHandler.END


async def _rules_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await reply_text(update, "Configuración de reglas cancelada.")
    return ConversationHandler.END


def _parse_rule_field_value(field_name: str, raw_value: str) -> Any:
    if field_name == "poll_interval_seconds":
        if not raw_value.isdigit():
            raise ValueError(
                "El intervalo de consulta debe ser un número entero de segundos."
            )
        interval = int(raw_value)
        if interval < MIN_P2P_POLL_INTERVAL_SECONDS:
            raise ValueError(
                f"El intervalo de consulta debe ser al menos {MIN_P2P_POLL_INTERVAL_SECONDS} segundos."
            )
        return interval
    if field_name == "target_type":
        return parse_offer_type(raw_value).value
    if field_name == "rule_coin":
        if raw_value.strip().strip("'\"").lower() in {"skip", "none", "any"}:
            return None
        return raw_value.strip().upper()
    if field_name in {"min_ratio", "max_ratio", "min_amount", "max_amount"}:
        if raw_value.strip().strip("'\"").lower() in {"skip", "none", "any"}:
            return None
        numeric_value = float(raw_value.strip())
        if numeric_value <= 0:
            raise ValueError(f"{field_name} debe ser mayor que cero.")
        return numeric_value
    if field_name == "rule_boolean":
        return parse_yes_no(raw_value)
    return raw_value.strip()


def build_rules_conversation(allowed: filters.BaseFilter) -> ConversationHandler:  # type: ignore[type-arg]
    return ConversationHandler(
        entry_points=[CommandHandler("rules", _rules_entry, filters=allowed)],
        states={
            RULE_NAME: [
                CallbackQueryHandler(
                    _rules_name_callback, pattern=f"^{P2P_RULE_NAME_CALLBACK_PREFIX}"
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & allowed, _rules_name_text
                ),
            ],
            RULE_VALUE: [
                CallbackQueryHandler(
                    _rule_value_callback,
                    pattern=f"^({P2P_RULE_COIN_CALLBACK_PREFIX}|{P2P_OFFER_TYPE_CALLBACK_PREFIX})",
                ),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & allowed, _rule_value_text
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", _rules_cancel, filters=allowed)],
        per_chat=True,
        per_user=False,
    )


# ---------------------------------------------------------------------------
# Generic API command ConversationHandler (for commands with missing fields)
# ---------------------------------------------------------------------------


async def _api_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None or update.effective_chat is None:
        return ConversationHandler.END

    text = (update.effective_message.text or "").strip()
    if not text.startswith("/"):
        return ConversationHandler.END

    parts = text.split()
    command_name = parts[0].split("@", maxsplit=1)[0].removeprefix("/")

    spec = COMMAND_INDEX.get(command_name)
    if spec is None or spec.command not in {s.command for s in COMMAND_SPECS}:
        await reply_text(update, f"Comando desconocido: /{command_name}")
        return ConversationHandler.END

    # Parse inline arguments
    arguments: dict[str, Any] = {}
    for token in parts[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", maxsplit=1)
        arguments[key] = parse_scalar(value)

    prompt_fields = _get_prompt_fields(spec)
    missing = [
        f
        for f in prompt_fields
        if f not in arguments
        or (isinstance(arguments.get(f), str) and not arguments[f].strip())
    ]

    if not missing:
        return await _execute_api(update, context, spec, arguments)

    context.user_data["api_spec_command"] = spec.command  # type: ignore[index]
    context.user_data["api_args"] = arguments  # type: ignore[index]
    context.user_data["api_fields"] = list(prompt_fields)  # type: ignore[index]
    context.user_data["api_field_idx"] = _find_first_missing(prompt_fields, arguments)  # type: ignore[index]

    idx: int = context.user_data["api_field_idx"]  # type: ignore[assignment]
    field = prompt_fields[idx]
    prompt = FIELD_PROMPTS.get(field, f"Envía el valor para {field}.")
    await reply_text(
        update,
        f"Iniciando /{spec.command}. {prompt} Envía {CANCEL_COMMAND} para cancelar.",
    )
    return API_FIELD


async def _api_field_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message is None or update.effective_chat is None:
        return ConversationHandler.END

    text = (update.effective_message.text or "").strip()
    if not text:
        return API_FIELD

    fields: list[str] = context.user_data.get("api_fields", [])  # type: ignore[assignment]
    idx: int = context.user_data.get("api_field_idx", 0)  # type: ignore[assignment]
    arguments: dict[str, Any] = context.user_data.get("api_args", {})  # type: ignore[assignment]

    field = fields[idx]
    if field == "two_factor_code":
        arguments[field] = text
    else:
        arguments[field] = parse_scalar(text)

    # Find next missing
    next_idx = _find_next_missing(fields, arguments, idx + 1)
    if next_idx is None:
        command_name: str = context.user_data.get("api_spec_command", "")  # type: ignore[assignment]
        spec = COMMAND_INDEX.get(command_name)
        if spec is None:
            return ConversationHandler.END
        return await _execute_api(update, context, spec, arguments)

    context.user_data["api_field_idx"] = next_idx  # type: ignore[index]
    next_field = fields[next_idx]
    prompt = FIELD_PROMPTS.get(next_field, f"Envía el valor para {next_field}.")
    await reply_text(update, f"{prompt} Envía {CANCEL_COMMAND} para cancelar.")
    return API_FIELD


async def _api_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await reply_text(update, "Acción cancelada.")
    return ConversationHandler.END


async def _execute_api(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    spec: CommandSpec,
    arguments: dict[str, Any],
) -> int:
    if update.effective_chat is None:
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    state_store = context.bot_data["state_store"]
    qvapay_client = context.bot_data["qvapay_client"]
    auth_state = state_store.get_chat_state(chat_id)

    execution_args = _build_execution_arguments(spec, arguments)
    response = await qvapay_client.execute(spec, execution_args, auth_state)

    # Handle login 2FA
    if spec.command == "login" and response.status_code == 202:
        has_otp = isinstance(response.body, dict) and bool(response.body.get("has_otp"))
        notified = isinstance(response.body, dict) and bool(response.body.get("notified"))
        if has_otp:
            prompt_2fa = (
                "🔐 Se requiere verificación en dos pasos.\n"
                "Ingresa el código de 6 dígitos de tu aplicación autenticadora."
            )
        elif notified:
            prompt_2fa = (
                "🔐 Se requiere verificación en dos pasos.\n"
                "Te enviamos un PIN de 4 dígitos a tu correo. Revísalo e ingrésalo aquí."
            )
        else:
            prompt_2fa = (
                "🔐 Se requiere verificación en dos pasos.\n"
                "Ingresa tu código de verificación de 4 dígitos."
            )
        # Re-enter with 2FA field
        context.user_data["api_spec_command"] = "login"  # type: ignore[index]
        context.user_data["api_args"] = arguments  # type: ignore[index]
        context.user_data["api_fields"] = ["email", "password", "two_factor_code"]  # type: ignore[index]
        context.user_data["api_field_idx"] = 2  # type: ignore[index]
        await reply_text(
            update,
            f"{prompt_2fa}\n\nEnvía {CANCEL_COMMAND} para cancelar.",
        )
        return API_FIELD

    payload = _format_command_payload(spec, arguments, response.body)
    if response.status_code < 400:
        await _persist_auth_side_effects(
            context, chat_id, spec.command, payload, auth_state
        )

    from qvapay_bot.handlers.common import (
        format_average_response,
        format_check_session_response,
        format_login_response,
        format_profile_response,
    )

    html_parse_mode: str | None = None

    if (
        spec.command == "average"
        and response.status_code == 200
        and isinstance(payload, dict)
    ):
        formatted = format_average_response(payload)
    elif (
        spec.command == "profile"
        and response.status_code == 200
        and isinstance(payload, dict)
    ):
        formatted = format_profile_response(payload)
        html_parse_mode = "HTML"
    elif (
        spec.command == "login"
        and response.status_code == 200
        and isinstance(payload, dict)
    ):
        formatted = format_login_response(payload)
        html_parse_mode = "HTML"
    elif (
        spec.command == "check_session"
        and response.status_code == 200
        and isinstance(payload, dict)
    ):
        formatted = format_check_session_response(payload)
    else:
        formatted = (
            f"/{spec.command}\nHTTP {response.status_code}\n\n{pretty_payload(payload)}"
        )

    await reply_text(update, formatted, parse_mode=html_parse_mode)
    return ConversationHandler.END


async def _persist_auth_side_effects(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    command_name: str,
    body: Any,
    auth_state: ChatAuthState,
) -> None:
    state_store = context.bot_data["state_store"]
    p2p_monitor_manager = context.bot_data["p2p_monitor_manager"]

    if command_name == "login" and isinstance(body, dict):
        access_token = body.get("accessToken")
        if isinstance(access_token, str) and access_token.strip():
            auth_state.bearer_token = access_token.strip()
        raw_me = body.get("me")
        me: dict[str, Any] = raw_me if isinstance(raw_me, dict) else {}
        apply_profile_payload(auth_state, me)
        login_user = context.user_data.get("login_user")  # type: ignore[union-attr]
        if isinstance(login_user, str) and login_user.strip():
            auth_state.logged_in_as = login_user.strip()
        state_store.save_chat_state(chat_id, auth_state)
        await p2p_monitor_manager.restart_chat(chat_id, auth_state, context.job_queue)
        return

    if command_name == "profile" and isinstance(body, dict):
        apply_profile_payload(auth_state, body)
        state_store.save_chat_state(chat_id, auth_state)
        return

    if command_name == "logout":
        auth_state.bearer_token = None
        auth_state.user_uuid = None
        auth_state.username = None
        auth_state.kyc = False
        auth_state.p2p_enabled = False
        state_store.save_chat_state(chat_id, auth_state)
        await p2p_monitor_manager.stop_chat(chat_id, context.job_queue)


def _get_prompt_fields(spec: CommandSpec) -> tuple[str, ...]:
    if spec.command == "list_p2p":
        from qvapay_bot.handlers.common import LIST_P2P_FILTER_FIELDS

        return LIST_P2P_FILTER_FIELDS
    if spec.command == "send_p2p_chat":
        return ("uuid", "message")
    return spec.required_fields


def _build_execution_arguments(
    spec: CommandSpec, arguments: dict[str, Any]
) -> dict[str, Any]:
    if spec.command != "list_p2p":
        return arguments
    return {"page": 1, "take": 100}


def _format_command_payload(
    spec: CommandSpec, request_arguments: dict[str, Any], response_body: Any
) -> Any:
    if spec.command != "list_p2p":
        return response_body
    return _filter_list_p2p_response(request_arguments, response_body)


def _filter_list_p2p_response(arguments: dict[str, Any], response_body: Any) -> Any:
    from qvapay_bot.handlers.common import to_float
    from qvapay_bot.qvapay_client import LIST_P2P_COIN_ALIASES

    if not isinstance(response_body, dict):
        return response_body
    offers = response_body.get("offers")
    if not isinstance(offers, list):
        return response_body

    normalized_coin = str(arguments.get("coin_filter", "")).strip().upper()
    coin_aliases = LIST_P2P_COIN_ALIASES.get(normalized_coin, (normalized_coin,))
    min_ratio = to_float(arguments.get("min_ratio"))
    max_ratio = to_float(arguments.get("max_ratio"))
    min_amount = to_float(arguments.get("min_amount"))
    max_amount = to_float(arguments.get("max_amount"))

    filtered_offers: list[Any] = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        offer_coin = str(offer.get("coin", "")).strip().upper()
        if normalized_coin and offer_coin not in coin_aliases:
            continue
        amount = to_float(offer.get("amount"))
        receive = to_float(offer.get("receive"))
        if amount is None or receive is None or amount <= 0:
            continue
        ratio = receive / amount
        if min_ratio is not None and ratio < min_ratio:
            continue
        if max_ratio is not None and ratio > max_ratio:
            continue
        if min_amount is not None and amount < min_amount:
            continue
        if max_amount is not None and amount > max_amount:
            continue
        filtered_offer = dict(offer)
        filtered_offer["ratio"] = round(ratio, 4)
        filtered_offers.append(filtered_offer)

    return {
        "filters": {
            "coin": normalized_coin,
            "min_ratio": min_ratio,
            "max_ratio": max_ratio,
            "min_amount": min_amount,
            "max_amount": max_amount,
        },
        "count": len(filtered_offers),
        "offers": filtered_offers,
    }


def _find_first_missing(
    fields: tuple[str, ...] | list[str], arguments: dict[str, Any]
) -> int:
    for i, field in enumerate(fields):
        if field not in arguments or (
            isinstance(arguments.get(field), str) and not arguments[field].strip()
        ):
            return i
    return 0


def _find_next_missing(
    fields: list[str], arguments: dict[str, Any], start: int
) -> int | None:
    for i in range(start, len(fields)):
        field = fields[i]
        if field not in arguments or (
            isinstance(arguments.get(field), str) and not arguments[field].strip()
        ):
            return i
    return None


async def _login_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat is None:
        return ConversationHandler.END
    keyboard_rows = [
        [
            {
                "text": "Carlitos",
                "callback_data": f"{LOGIN_USER_CALLBACK_PREFIX}carlitos",
            }
        ],
        [{"text": "Osliani", "callback_data": f"{LOGIN_USER_CALLBACK_PREFIX}osliani"}],
    ]
    await reply_with_keyboard(
        update, "¿Con qué usuario deseas iniciar sesión?", keyboard_rows
    )
    return LOGIN_USER


async def _login_user_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None or update.effective_chat is None:
        return ConversationHandler.END
    await query.answer()

    data = query.data or ""
    selected_user = data[len(LOGIN_USER_CALLBACK_PREFIX) :]
    settings = context.bot_data["settings"]

    if selected_user == "carlitos":
        email: str = settings.qvapay_email
        password: str = settings.qvapay_password
        user_label = "Carlitos"
    elif selected_user == "osliani":
        email = settings.qvapay_email2
        password = settings.qvapay_password2
        user_label = "Osliani"
    else:
        await reply_text(update, "Usuario no reconocido.")
        return ConversationHandler.END

    await reply_text(update, f"Iniciando sesión como {user_label}...")
    context.user_data["login_user"] = selected_user  # type: ignore[index]
    spec = COMMAND_INDEX["login"]
    arguments: dict[str, Any] = {"email": email, "password": password, "remember": True}
    return await _execute_api(update, context, spec, arguments)


def build_api_conversation(allowed: filters.BaseFilter) -> ConversationHandler:  # type: ignore[type-arg]
    api_command_names = [s.command for s in COMMAND_SPECS if s.command != "login"]
    return ConversationHandler(
        entry_points=[
            CommandHandler("login", _login_entry, filters=allowed),
            *[
                CommandHandler(cmd, _api_entry, filters=allowed)
                for cmd in api_command_names
            ],
        ],
        states={
            LOGIN_USER: [
                CallbackQueryHandler(
                    _login_user_callback, pattern=f"^{LOGIN_USER_CALLBACK_PREFIX}"
                ),
            ],
            API_FIELD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & allowed, _api_field_text
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", _api_cancel, filters=allowed)],
        per_chat=True,
        per_user=False,
    )
