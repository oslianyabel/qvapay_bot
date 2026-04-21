"""Shared constants, utilities and helpers for PTB handlers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from qvapay_bot.http_client import JsonValue
from qvapay_bot.p2p_models import P2PMonitorRules, P2POfferType

TELEGRAM_MESSAGE_LIMIT = 4096
CANCEL_COMMAND = "/cancel"

APPLIED_DETAIL_CALLBACK_PREFIX = "adh:"
APPLIED_LIST_PAGE_CALLBACK_PREFIX = "adlp:"
CANCEL_P2P_CALLBACK_PREFIX = "cp2p:"
LOGIN_USER_CALLBACK_PREFIX = "login_user:"
MONITOR_ON_CONFIRM_CALLBACK_PREFIX = "mon_on:"
P2P_RULE_NAME_CALLBACK_PREFIX = "prn:"
P2P_RULE_COIN_CALLBACK_PREFIX = "prc:"
P2P_OFFER_TYPE_CALLBACK_PREFIX = "pot:"

P2P_RULE_COIN_OPTIONS: tuple[str, ...] = ("ETECSA", "BANK_CUP", "ZELLE", "BOLSATM")
P2P_RULE_NAME_OPTIONS: tuple[tuple[str, str], ...] = (
    ("coin", "Moneda"),
    ("ratio", "Ratio"),
    ("amount", "Monto"),
    ("only_kyc", "Solo KYC"),
    ("only_vip", "Solo VIP"),
    ("offer_type", "Tipo de oferta"),
    ("poll_interval", "Intervalo de consulta"),
    ("reset", "Reiniciar"),
)

RULE_DYNAMIC_FIELDS: dict[str, tuple[str, ...]] = {
    "coin": ("rule_coin",),
    "ratio": ("min_ratio", "max_ratio"),
    "amount": ("min_amount", "max_amount"),
    "only_kyc": ("rule_boolean",),
    "only_vip": ("rule_boolean",),
    "offer_type": ("target_type",),
    "poll_interval": ("poll_interval_seconds",),
    "reset": (),
}

RULE_NAME_ALIASES: dict[str, str] = {
    "coin": "coin",
    "moneda": "coin",
    "currency": "coin",
    "ratio": "ratio",
    "amount": "amount",
    "monto": "amount",
    "kyc": "only_kyc",
    "only_kyc": "only_kyc",
    "solo kyc": "only_kyc",
    "vip": "only_vip",
    "only_vip": "only_vip",
    "solo vip": "only_vip",
    "type": "offer_type",
    "offer_type": "offer_type",
    "tipo": "offer_type",
    "tipo de oferta": "offer_type",
    "poll_interval": "poll_interval",
    "intervalo": "poll_interval",
    "intervalo de consulta": "poll_interval",
    "reset": "reset",
    "reiniciar": "reset",
}

from qvapay_bot.p2p_models import MIN_P2P_POLL_INTERVAL_SECONDS  # noqa: E402

FIELD_PROMPTS: dict[str, str] = {
    "email": "Envía el email.",
    "password": "Envía la contraseña.",
    "uuid": "Envía el UUID.",
    "tx_id": "Envía el ID de transacción.",
    "rating": "Envía la calificación.",
    "token": "Envía el token de acceso.",
    "app_id": "Envía el app ID.",
    "app_secret": "Envía el app secret.",
    "name": "Envía el nombre.",
    "product_id": "Envía el ID del producto.",
    "amount": "Envía el monto.",
    "message": "Envía el mensaje o adjunta una foto.",
    "coin_filter": "Envía la moneda para filtrar, por ejemplo CUP o ZELLE.",
    "min_ratio": "Envía el ratio mínimo o 'skip'.",
    "max_ratio": "Envía el ratio máximo o 'skip'.",
    "min_amount": "Envía el monto mínimo o 'skip'.",
    "max_amount": "Envía el monto máximo o 'skip'.",
    "poll_interval_seconds": f"Envía el intervalo de consulta en segundos, mínimo {MIN_P2P_POLL_INTERVAL_SECONDS}.",
    "target_type": "Envía el tipo de oferta: buy, sell o any.",
    "rule_name": "Envía el nombre de la regla: coin, ratio, amount, only_kyc, only_vip, offer_type o reset.",
    "rule_coin": "Envía el filtro de moneda, por ejemplo BANK_CUP o CUP. Envía 'skip' para borrarlo.",
    "rule_boolean": "Envía sí o no.",
    "two_factor_code": "Envía el código 2FA (PIN de 4 dígitos u OTP de 6 dígitos).",
}

LIST_P2P_FILTER_FIELDS: tuple[str, ...] = (
    "coin_filter",
    "min_ratio",
    "max_ratio",
    "min_amount",
    "max_amount",
)

AVERAGE_DISPLAY_ORDER: tuple[str, ...] = (
    "CUP",
    "MLC",
    "TROPIPAY",
    "ETECSA",
    "ZELLE",
    "CLASICA",
    "BOLSATM",
    "BANDECPREPAGO",
    "SBERBANK",
    "USDTBSC",
)

AVERAGE_TICK_ICONS: dict[str, str] = {
    "CUP": "💰",
    "MLC": "💵",
    "TROPIPAY": "💶",
    "ETECSA": "📱",
    "ZELLE": "🏦",
    "CLASICA": "💷",
    "BOLSATM": "💸",
    "BANDECPREPAGO": "🏦",
    "SBERBANK": "🏦",
    "USDTBSC": "🪙",
}

CUSTOM_HELP: dict[str, str] = {
    "monitor_on": "/monitor_on\nActiva el monitor P2P para este chat. El bot preguntará el intervalo y mostrará las reglas para confirmar.",
    "monitor_off": "/monitor_off\nDesactiva el monitor P2P para este chat.",
    "monitor_status": "/monitor_status\nMuestra la configuración del monitor, las reglas y el último estado de ejecución.",
    "rules": "/rules\nConfigura una regla de forma interactiva: moneda, ratio, monto, solo KYC, solo VIP, tipo de oferta o reiniciar.",
    "rules_show": "/rules_show\nMuestra las reglas P2P activas.",
    "history": "/history\nLista las ofertas P2P procesadas por el monitor.",
    "monitor_test": "/monitor_test\nEjecuta un ciclo de monitoreo inmediatamente y muestra el resultado.",
    "balance": "/balance\nMuestra el saldo disponible en tu cuenta QvaPay.",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def split_text(text: str) -> list[str]:
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        return [text]
    chunks: list[str] = []
    remaining = text
    while remaining:
        chunk = remaining[:TELEGRAM_MESSAGE_LIMIT]
        split_at = chunk.rfind("\n")
        if split_at > 0 and len(remaining) > TELEGRAM_MESSAGE_LIMIT:
            chunk = chunk[:split_at]
        chunks.append(chunk)
        remaining = remaining[len(chunk) :].lstrip("\n")
    return chunks


async def send_text(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    parse_mode: str | None = None,
) -> None:
    for chunk in split_text(text):
        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=parse_mode)


async def send_message_with_keyboard(
    bot: Bot,
    chat_id: int,
    text: str,
    keyboard_rows: list[list[dict[str, str]]],
    *,
    parse_mode: str | None = None,
) -> None:
    inline_keyboard = [
        [
            InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
            for btn in row
        ]
        for row in keyboard_rows
    ]
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard),
        parse_mode=parse_mode,
    )


async def reply_text(
    update: Update, text: str, *, parse_mode: str | None = None
) -> None:
    if update.effective_message is None:
        return
    for chunk in split_text(text):
        await update.effective_message.reply_text(chunk, parse_mode=parse_mode)


async def reply_with_keyboard(
    update: Update,
    text: str,
    keyboard_rows: list[list[dict[str, str]]],
    *,
    parse_mode: str | None = None,
) -> None:
    if update.effective_message is None:
        return
    inline_keyboard = [
        [
            InlineKeyboardButton(text=btn["text"], callback_data=btn["callback_data"])
            for btn in row
        ]
        for row in keyboard_rows
    ]
    await update.effective_message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard),
        parse_mode=parse_mode,
    )


def to_float(value: JsonValue | None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def to_optional_float(value: JsonValue | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().strip("'\"").lower()
        if stripped in {"", "skip", "none", "any"}:
            return None
        return float(value.strip())
    return None


def parse_yes_no(value: JsonValue | None) -> bool:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        raise ValueError("Se esperaba sí o no.")
    normalized = value.strip().lower()
    if normalized in {"yes", "y", "true", "1", "on", "si", "sí"}:
        return True
    if normalized in {"no", "n", "false", "0", "off"}:
        return False
    raise ValueError("Se esperaba sí o no.")


def parse_offer_type(value: JsonValue | None) -> P2POfferType:
    if not isinstance(value, str):
        raise ValueError("El tipo de oferta debe ser buy, sell o any.")
    normalized = value.strip().lower()
    if normalized in {"any", "both", "all"}:
        return P2POfferType.ANY
    if normalized == "buy":
        return P2POfferType.BUY
    if normalized == "sell":
        return P2POfferType.SELL
    raise ValueError("El tipo de oferta debe ser buy, sell o any.")


def validate_monitor_rules(rules: P2PMonitorRules) -> None:
    if (
        rules.min_ratio is not None
        and rules.max_ratio is not None
        and rules.min_ratio > rules.max_ratio
    ):
        raise ValueError("min_ratio no puede ser mayor que max_ratio.")
    if (
        rules.min_amount is not None
        and rules.max_amount is not None
        and rules.min_amount > rules.max_amount
    ):
        raise ValueError("min_amount no puede ser mayor que max_amount.")


def format_rule_change(rule_name: str, state: Any) -> str:
    def _val(v: float | None) -> str:
        return str(v) if v is not None else "cualquiera"

    rules = state.rules
    if rule_name == "reset":
        return "✅ Reglas reiniciadas."
    if rule_name == "coin":
        return f"Moneda: {rules.coin or 'cualquiera'}"
    if rule_name == "ratio":
        return f"Ratio mín: {_val(rules.min_ratio)} | máx: {_val(rules.max_ratio)}"
    if rule_name == "amount":
        return f"Monto mín: {_val(rules.min_amount)} | máx: {_val(rules.max_amount)}"
    if rule_name == "only_kyc":
        return f"Solo KYC: {'sí' if rules.only_kyc else 'no'}"
    if rule_name == "only_vip":
        return f"Solo VIP: {'sí' if rules.only_vip else 'no'}"
    if rule_name == "offer_type":
        label = "Comprar" if state.target_type == P2POfferType.BUY else "Vender"
        return f"Tipo de oferta: {label}"
    if rule_name == "poll_interval":
        return f"Intervalo de consulta: {state.poll_interval_seconds}s"
    return f"Regla actualizada: {rule_name}"


def apply_profile_payload(auth_state: Any, payload: dict[str, Any]) -> None:
    user_uuid = payload.get("uuid")
    username = payload.get("username")
    if isinstance(user_uuid, str) and user_uuid.strip():
        auth_state.user_uuid = user_uuid.strip()
    if isinstance(username, str) and username.strip():
        auth_state.username = username.strip()
    if "kyc" in payload:
        auth_state.kyc = bool(payload.get("kyc"))
    if "p2p_enabled" in payload:
        auth_state.p2p_enabled = bool(payload.get("p2p_enabled"))


def format_average_response(payload: dict[str, JsonValue]) -> str:
    lines = ["Tasa de cambio promedio P2P QvaPay.com x USD:", ""]
    latest_update: datetime | None = None
    for tick in AVERAGE_DISPLAY_ORDER:
        raw_value = payload.get(tick)
        if not isinstance(raw_value, dict):
            continue
        average_value = raw_value.get("average", 0)
        if not isinstance(average_value, (int, float)):
            average_value = 0
        icon = AVERAGE_TICK_ICONS[tick]
        lines.append(f"{icon} {tick}: ${average_value:.2f}")
        updated_at = raw_value.get("updated_at")
        parsed_date = parse_updated_at(updated_at)
        if parsed_date is not None and (
            latest_update is None or parsed_date > latest_update
        ):
            latest_update = parsed_date

    if latest_update is not None:
        lines.extend(
            [
                "",
                "Ultima actualizacion: "
                f"{latest_update.day}/{latest_update.month}/{latest_update.year}, "
                f"{latest_update:%H:%M:%S}",
            ]
        )
    return "\n".join(lines)


def parse_updated_at(value: JsonValue | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_help_for_command(spec: Any) -> str:
    examples: dict[str, str] = {
        "average": "/average",
        "login": '/login email="jane@example.com" password="secret123" remember=true',
        "list_p2p": "/list_p2p",
        "mark_p2p_paid": "/mark_p2p_paid uuid=offer-uuid tx_id=REF-123",
        "rate_p2p": '/rate_p2p uuid=offer-uuid rating=5 comment="Excelente" tags=\'["rapido","confiable"]\'',
        "send_p2p_chat": '/send_p2p_chat uuid=offer-uuid message="Payment proof"',
        "transaction_detail": "/transaction_detail uuid=transaction-uuid",
    }
    example = examples.get(spec.command, spec.usage)
    lines = [
        f"/{spec.command}",
        spec.description,
        f"Method: {spec.method} {spec.path_template}",
        f"Usage: {spec.usage}",
        f"Example: {example}",
    ]
    if spec.supports_photo:
        lines.append(
            "Photo upload: attach a Telegram photo and use the command in the caption."
        )
    return "\n".join(lines)


async def fetch_coin_averages(context: ContextTypes.DEFAULT_TYPE) -> dict[str, float]:
    from qvapay_bot.qvapay_client import COMMAND_INDEX

    qvapay_client = context.bot_data["qvapay_client"]
    response = await qvapay_client.execute(
        COMMAND_INDEX["average"],
        {},
        __import__("qvapay_bot.state", fromlist=["ChatAuthState"]).ChatAuthState(),
    )
    averages: dict[str, float] = {}
    if response.status_code == 200 and isinstance(response.body, dict):
        for coin, raw in response.body.items():
            if isinstance(raw, dict):
                avg = raw.get("average")
                if isinstance(avg, (int, float)) and avg > 0:
                    averages[coin] = float(avg)
    return averages


async def refresh_applied_statuses(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
) -> bool:
    import logging

    from qvapay_bot.p2p_models import OfferProcessResult
    from qvapay_bot.qvapay_client import COMMAND_INDEX

    logger = logging.getLogger(__name__)

    state_store = context.bot_data["state_store"]
    p2p_repository = context.bot_data["p2p_repository"]
    qvapay_client = context.bot_data["qvapay_client"]

    auth_state = state_store.get_chat_state(chat_id)
    if not auth_state.has_bearer:
        return False

    monitor_state = p2p_repository.get_chat_state(chat_id)
    _TERMINAL_STATUSES = {"cancelled", "completed", "rejected"}
    updated = False

    for entry in monitor_state.applied_history:
        if entry.result != OfferProcessResult.APPLIED:
            continue
        if entry.status.lower() in _TERMINAL_STATUSES:
            continue
        try:
            response = await qvapay_client.execute(
                COMMAND_INDEX["p2p_detail"],
                {"uuid": entry.uuid},
                auth_state,
            )
            if response.status_code == 200 and isinstance(response.body, dict):
                p2p_data = response.body.get("p2p")
                if isinstance(p2p_data, dict):
                    new_status = str(p2p_data.get("status", "")).strip().lower()
                    if new_status and new_status != entry.status:
                        logger.info(
                            "Offer status updated chat_id=%s uuid=%s %s -> %s",
                            chat_id,
                            entry.uuid,
                            entry.status,
                            new_status,
                        )
                        entry.status = new_status
                        updated = True
        except Exception:
            logger.warning(
                "Failed to refresh status for offer chat_id=%s uuid=%s",
                chat_id,
                entry.uuid,
            )

    if updated:
        p2p_repository.save_chat_state(chat_id, monitor_state)
    return updated
