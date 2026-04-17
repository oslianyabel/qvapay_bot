from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from qvapay_bot.config import Settings
from qvapay_bot.http_client import AsyncHttpClient, FileUpload, JsonObject, JsonValue
from qvapay_bot.p2p_formatter import (
    format_applied_detail,
    format_applied_list_keyboard,
    format_cancel_p2p_keyboard,
    format_cycle_report,
    format_monitor_on_confirmation,
    format_monitor_status,
    format_rules,
)
from qvapay_bot.p2p_models import (
    MIN_P2P_POLL_INTERVAL_SECONDS,
    OfferProcessResult,
    P2PMonitorChatState,
    P2PMonitorRules,
    P2POfferType,
)
from qvapay_bot.p2p_monitor import P2PMonitorManager
from qvapay_bot.p2p_repository import P2PMonitorStateStore
from qvapay_bot.qvapay_client import (
    COMMAND_INDEX,
    COMMAND_SPECS,
    LIST_P2P_COIN_ALIASES,
    CommandSpec,
    QvaPayClient,
    parse_scalar,
    pretty_payload,
)
from qvapay_bot.state import BotStateStore, ChatAuthState, PendingCommandState

TELEGRAM_MESSAGE_LIMIT = 4096
CANCEL_COMMAND = "/cancel"
APPLIED_DETAIL_CALLBACK_PREFIX = "adh:"
APPLIED_LIST_PAGE_CALLBACK_PREFIX = "adlp:"
CANCEL_P2P_CALLBACK_PREFIX = "cp2p:"
MONITOR_ON_CONFIRM_CALLBACK_PREFIX = "mon_on:"
P2P_RULE_NAME_CALLBACK_PREFIX = "prn:"
P2P_RULE_COIN_CALLBACK_PREFIX = "prc:"
P2P_OFFER_TYPE_CALLBACK_PREFIX = "pot:"
P2P_RULE_COIN_OPTIONS: tuple[str, ...] = ("ETECSA", "BANK_CUP", "ZELLE")
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
UTILITY_COMMAND_FIELDS: dict[str, tuple[str, ...]] = {}
CUSTOM_COMMANDS = {
    "monitor_on",
    "monitor_off",
    "monitor_status",
    "rules",
    "rules_show",
    "history",
    "monitor_test",
    "balance",
}
CUSTOM_COMMAND_FIELDS: dict[str, tuple[str, ...]] = {}
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


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ParsedCommand:
    name: str
    arguments: dict[str, JsonValue]


class QvaPayTelegramBot:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http_client = AsyncHttpClient(settings.http_timeout_seconds)
        self._qvapay_client = QvaPayClient(
            http_client=self._http_client,
            base_url=settings.qvapay_base_url,
        )
        self._state_store = BotStateStore(settings.state_file)
        self._p2p_repository = P2PMonitorStateStore(settings.p2p_state_file)

        async def _send_html_with_keyboard(
            chat_id: int,
            text: str,
            keyboard_rows: list[list[dict[str, str]]],
        ) -> None:
            await self._send_message_with_keyboard(
                chat_id, text, keyboard_rows, parse_mode="HTML"
            )

        self._p2p_monitor_manager = P2PMonitorManager(
            settings=settings,
            state_store=self._state_store,
            repository=self._p2p_repository,
            qvapay_client=self._qvapay_client,
            send_text=self._send_text,
            send_message_with_keyboard=_send_html_with_keyboard,
        )

    async def run(self) -> None:
        LOGGER.info(
            "Bot starting base_url=%s state_file=%s p2p_state_file=%s",
            self._settings.qvapay_base_url,
            self._settings.state_file,
            self._settings.p2p_state_file,
        )
        await self._p2p_monitor_manager.restore_tasks()
        LOGGER.info("Bot ready, polling for updates")
        offset = 0
        while True:
            updates = await self._get_updates(offset)
            for update in updates:
                offset = max(offset, update.get("update_id", 0) + 1)
                try:
                    await self._handle_update(update)
                except Exception as exc:
                    chat_id = self._extract_chat_id(update)
                    if chat_id is not None:
                        await self._send_text(chat_id, f"Error: {exc}")
                    if self._settings.telegram_dev_chat_id is not None:
                        await self._send_text(
                            self._settings.telegram_dev_chat_id,
                            f"Unhandled bot error\nchat_id={chat_id}\n{exc}",
                        )

    async def _get_updates(self, offset: int) -> list[dict[str, Any]]:
        response = await self._http_client.request(
            "GET",
            f"{self._settings.telegram_api_base_url}/getUpdates",
            query={
                "offset": offset,
                "timeout": self._settings.telegram_poll_timeout_seconds,
            },
        )
        payload = response.body if isinstance(response.body, dict) else {}
        result = payload.get("result", []) if isinstance(payload, dict) else []
        if not isinstance(result, list):
            return []
        return [item for item in result if isinstance(item, dict)]

    async def _handle_update(self, update: dict[str, Any]) -> None:
        callback_query = update.get("callback_query")
        if isinstance(callback_query, dict):
            await self._handle_callback_query(callback_query)
            return

        message = update.get("message")
        if not isinstance(message, dict):
            return

        chat = message.get("chat", {})
        chat_id = chat.get("id")
        if not isinstance(chat_id, int):
            return

        if chat_id not in self._settings.allowed_chat_ids:
            return

        text = self._extract_message_text(message)
        auth_state = self._state_store.get_chat_state(chat_id)
        if text == CANCEL_COMMAND:
            await self._handle_cancel(chat_id, auth_state)
            return

        if auth_state.pending_command is not None:
            if text.startswith("/"):
                await self._send_text(
                    chat_id,
                    f"Hay una acción pendiente. Envía {CANCEL_COMMAND} para cancelarla.",
                )
                return
            await self._handle_pending_command_input(chat_id, message, text, auth_state)
            return

        if not text.startswith("/"):
            return

        parsed_command = self._parse_command(text)
        await self._dispatch_command(chat_id, parsed_command, message, auth_state)

    async def _dispatch_command(
        self,
        chat_id: int,
        parsed_command: ParsedCommand,
        message: dict[str, Any],
        auth_state: ChatAuthState,
    ) -> None:
        LOGGER.info(
            "Command received chat_id=%s command=/%s", chat_id, parsed_command.name
        )
        if parsed_command.name in {"start", "help"}:
            await self._handle_help(chat_id, parsed_command.arguments)
            return
        if parsed_command.name in CUSTOM_COMMANDS:
            await self._dispatch_custom_command(chat_id, parsed_command, auth_state)
            return
        if parsed_command.name == "auth_status":
            await self._handle_auth_status(chat_id)
            return

        spec = COMMAND_INDEX.get(parsed_command.name)
        if spec is None or spec.command not in {s.command for s in COMMAND_SPECS}:
            await self._send_text(
                chat_id, f"Comando desconocido: /{parsed_command.name}"
            )
            return

        if spec.command == "login":
            login_arguments: dict[str, JsonValue] = {
                "email": self._settings.qvapay_email,
                "password": self._settings.qvapay_password,
                "remember": True,
            }
            await self._execute_api_command(
                chat_id, spec, login_arguments, message, auth_state
            )
            return

        prompt_fields = self._get_prompt_fields(spec.command, spec)
        missing_fields = self._get_missing_fields(
            prompt_fields, parsed_command.arguments
        )
        if missing_fields:
            await self._start_pending_command(
                chat_id,
                auth_state,
                PendingCommandState(
                    command_name=spec.command,
                    command_kind="api",
                    field_order=list(prompt_fields),
                    arguments=dict(parsed_command.arguments),
                ),
            )
            return

        await self._execute_api_command(
            chat_id,
            spec,
            parsed_command.arguments,
            message,
            auth_state,
        )

    async def _dispatch_custom_command(
        self,
        chat_id: int,
        parsed_command: ParsedCommand,
        auth_state: ChatAuthState,
    ) -> None:
        if parsed_command.name in {
            "monitor_on",
            "monitor_off",
            "monitor_status",
            "rules_show",
            "history",
            "monitor_test",
            "balance",
        }:
            try:
                await self._execute_custom_command(
                    chat_id,
                    parsed_command.name,
                    parsed_command.arguments,
                    auth_state,
                )
            except ValueError as exc:
                await self._send_text(chat_id, str(exc))
            return

        if parsed_command.name == "rules":
            await self._start_pending_command(
                chat_id,
                auth_state,
                PendingCommandState(
                    command_name="rules",
                    command_kind="custom",
                    field_order=["rule_name"],
                    arguments={},
                ),
            )
            return

        field_order = CUSTOM_COMMAND_FIELDS.get(parsed_command.name, ())
        missing_fields = self._get_missing_fields(field_order, parsed_command.arguments)
        if missing_fields:
            await self._start_pending_command(
                chat_id,
                auth_state,
                PendingCommandState(
                    command_name=parsed_command.name,
                    command_kind="custom",
                    field_order=list(field_order),
                    arguments=dict(parsed_command.arguments),
                ),
            )
            return

        try:
            await self._execute_custom_command(
                chat_id,
                parsed_command.name,
                parsed_command.arguments,
                auth_state,
            )
        except ValueError as exc:
            await self._send_text(chat_id, str(exc))

    async def _execute_custom_command(
        self,
        chat_id: int,
        command_name: str,
        arguments: dict[str, JsonValue],
        auth_state: ChatAuthState,
    ) -> None:
        LOGGER.info(
            "Executing custom command chat_id=%s command=%s", chat_id, command_name
        )
        monitor_state = self._p2p_repository.get_chat_state(chat_id)

        if command_name == "monitor_on":
            poll_interval = monitor_state.poll_interval_seconds
            self._validate_monitor_rules(monitor_state.rules)
            confirmation_text = format_monitor_on_confirmation(
                monitor_state, poll_interval
            )
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
            await self._send_message_with_keyboard(
                chat_id, confirmation_text, keyboard_rows, parse_mode="HTML"
            )
            return

        if command_name == "monitor_off":
            monitor_state.enabled = False
            self._p2p_repository.save_chat_state(chat_id, monitor_state)
            await self._p2p_monitor_manager.stop_chat(chat_id)
            await self._send_text(chat_id, "⏹ Monitoreo desactivado.")
            return

        if command_name == "monitor_status":
            await self._send_text(chat_id, format_monitor_status(monitor_state))
            return

        if command_name == "rules_show":
            await self._send_text(chat_id, format_rules(monitor_state))
            return

        if command_name == "rules":
            rule_name = str(arguments["rule_name"])
            if rule_name == "reset":
                monitor_state.rules = P2PMonitorRules()
                monitor_state.target_type = P2POfferType.ANY
            elif rule_name == "coin":
                rule_coin = arguments.get("rule_coin")
                monitor_state.rules.coin = (
                    str(rule_coin) if isinstance(rule_coin, str) else None
                )
            elif rule_name == "ratio":
                monitor_state.rules.min_ratio = self._to_optional_float(
                    arguments.get("min_ratio")
                )
                monitor_state.rules.max_ratio = self._to_optional_float(
                    arguments.get("max_ratio")
                )
            elif rule_name == "amount":
                min_amount = self._to_optional_float(arguments.get("min_amount"))
                max_amount = self._to_optional_float(arguments.get("max_amount"))
                if monitor_state.target_type == P2POfferType.BUY:
                    balance = await self._p2p_monitor_manager.fetch_balance(auth_state)
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
                monitor_state.rules.only_kyc = self._parse_yes_no(
                    arguments.get("rule_boolean")
                )
            elif rule_name == "only_vip":
                monitor_state.rules.only_vip = self._parse_yes_no(
                    arguments.get("rule_boolean")
                )
            elif rule_name == "offer_type":
                new_type = self._parse_offer_type(arguments.get("target_type"))
                if new_type == P2POfferType.BUY:
                    balance = await self._p2p_monitor_manager.fetch_balance(auth_state)
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

            self._validate_monitor_rules(monitor_state.rules)
            self._p2p_repository.save_chat_state(chat_id, monitor_state)
            await self._p2p_monitor_manager.restart_chat(chat_id, auth_state)
            await self._send_text(
                chat_id, self._format_rule_change(rule_name, monitor_state)
            )
            return

        if command_name == "history":
            updated = await self._refresh_applied_statuses(
                chat_id, auth_state, monitor_state
            )
            if updated:
                self._p2p_repository.save_chat_state(chat_id, monitor_state)
            coin_averages = await self._fetch_coin_averages()
            header, keyboard_rows = format_applied_list_keyboard(
                monitor_state.applied_history,
                monitor_state.lost_race_history,
                page=0,
                coin_averages=coin_averages,
            )
            if keyboard_rows:
                await self._send_message_with_keyboard(
                    chat_id, header, keyboard_rows, parse_mode="HTML"
                )
            else:
                await self._send_text(chat_id, header)
            return

        if command_name == "cancel_p2p":
            updated = await self._refresh_applied_statuses(
                chat_id, auth_state, monitor_state
            )
            if updated:
                self._p2p_repository.save_chat_state(chat_id, monitor_state)
            header, keyboard_rows = format_cancel_p2p_keyboard(
                monitor_state.applied_history
            )
            if keyboard_rows:
                await self._send_message_with_keyboard(
                    chat_id, header, keyboard_rows, parse_mode="HTML"
                )
            else:
                await self._send_text(chat_id, header)
            return

        if command_name == "monitor_test":
            report = await self._p2p_monitor_manager.run_cycle_once(
                chat_id,
                auth_state,
                force=True,
                notify=False,
            )
            await self._send_text(chat_id, format_cycle_report(report))
            return

        if command_name == "balance":
            if not auth_state.has_bearer:
                await self._send_text(
                    chat_id, "Debes iniciar sesión para consultar el saldo."
                )
                return
            response = await self._qvapay_client.execute(
                COMMAND_INDEX["profile"],
                {},
                auth_state,
            )
            if response.status_code == 200 and isinstance(response.body, dict):
                balance = response.body.get("balance")
                username = response.body.get("username") or auth_state.username or "-"
                balance_str = (
                    f"{balance:.2f}"
                    if isinstance(balance, (int, float))
                    else str(balance)
                )
                await self._send_text(
                    chat_id,
                    f"💰 Saldo disponible\nUsuario: {username}\nBalance: {balance_str} QUSD",
                )
            else:
                await self._send_text(
                    chat_id,
                    f"Error al obtener el saldo.\nHTTP {response.status_code}\n{pretty_payload(response.body)}",
                )
            return

        raise ValueError(f"Comando personalizado no soportado: {command_name}")

    async def _execute_api_command(
        self,
        chat_id: int,
        spec: CommandSpec,
        arguments: dict[str, JsonValue],
        message: dict[str, Any],
        auth_state: ChatAuthState,
    ) -> None:
        LOGGER.info(
            "Executing API command chat_id=%s command=%s", chat_id, spec.command
        )
        execution_arguments = self._build_execution_arguments(spec, arguments)
        photo = await self._extract_photo_upload(message, spec)
        response = await self._qvapay_client.execute(
            spec,
            execution_arguments,
            auth_state,
            photo=photo,
        )
        if spec.command == "login" and response.status_code == 202:
            has_otp = isinstance(response.body, dict) and bool(
                response.body.get("has_otp")
            )
            code_hint = "6-digit OTP" if has_otp else "4-digit PIN"
            auth_state.pending_command = PendingCommandState(
                command_name="login",
                command_kind="api",
                field_order=["two_factor_code"],
                arguments=dict(arguments),
            )
            self._state_store.save_chat_state(chat_id, auth_state)
            await self._send_text(
                chat_id,
                f"Se requiere 2FA. Envía tu {code_hint}. Envía {CANCEL_COMMAND} para cancelar.",
            )
            return

        formatted_payload = self._format_command_payload(spec, arguments, response.body)
        if response.status_code < 400:
            await self._persist_auth_side_effects(
                chat_id, spec.command, formatted_payload, auth_state
            )
        formatted = self._format_api_response(
            spec, response.status_code, formatted_payload
        )
        await self._send_text(chat_id, formatted)

    async def _handle_help(
        self,
        chat_id: int,
        arguments: dict[str, JsonValue],
    ) -> None:
        command_name = str(arguments.get("command", "")).strip().removeprefix("/")
        if command_name:
            if command_name in CUSTOM_HELP:
                await self._send_text(chat_id, CUSTOM_HELP[command_name])
                return
            spec = COMMAND_INDEX.get(command_name)
            if spec is None or spec.command not in {s.command for s in COMMAND_SPECS}:
                await self._send_text(
                    chat_id, f"Comando no encontrado: /{command_name}"
                )
                return
            await self._send_text(chat_id, self._format_help_for_command(spec))
            return

        sections = [
            "Utilidades:",
            "/help command=<nombre> - Muestra ayuda de un comando",
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
        sections.extend(
            f"/{spec.command} - {spec.description}" for spec in COMMAND_SPECS
        )
        await self._send_text(chat_id, "\n".join(sections))

    async def _handle_auth_status(self, chat_id: int) -> None:
        state = self._state_store.get_chat_state(chat_id)
        status_lines = [
            f"Token de acceso configurado: {'sí' if state.has_bearer else 'no'}",
            f"Credenciales de la app configuradas: {'sí' if state.has_app_credentials else 'no'}",
            f"UUID de usuario: {state.user_uuid or '-'}",
            f"Nombre de usuario: {state.username or '-'}",
        ]
        await self._send_text(chat_id, "\n".join(status_lines))

    async def _persist_auth_side_effects(
        self,
        chat_id: int,
        command_name: str,
        body: JsonValue | str | None,
        auth_state: ChatAuthState,
    ) -> None:
        if command_name == "login" and isinstance(body, dict):
            access_token = body.get("accessToken")
            if isinstance(access_token, str) and access_token.strip():
                auth_state.bearer_token = access_token.strip()
            raw_me = body.get("me")
            me: dict[str, Any] = raw_me if isinstance(raw_me, dict) else {}
            self._apply_profile_payload(auth_state, me)
            self._state_store.save_chat_state(chat_id, auth_state)
            await self._p2p_monitor_manager.restart_chat(chat_id, auth_state)
            return

        if command_name == "profile" and isinstance(body, dict):
            self._apply_profile_payload(auth_state, body)
            self._state_store.save_chat_state(chat_id, auth_state)
            return

        if command_name == "logout":
            auth_state.bearer_token = None
            auth_state.user_uuid = None
            auth_state.username = None
            auth_state.kyc = False
            auth_state.p2p_enabled = False
            self._state_store.save_chat_state(chat_id, auth_state)
            await self._p2p_monitor_manager.stop_chat(chat_id)

    async def _handle_cancel(self, chat_id: int, auth_state: ChatAuthState) -> None:
        if auth_state.pending_command is None:
            await self._send_text(chat_id, "No hay ninguna acción pendiente.")
            return
        auth_state.pending_command = None
        self._state_store.save_chat_state(chat_id, auth_state)
        await self._send_text(chat_id, "Acción cancelada.")

    async def _handle_pending_command_input(
        self,
        chat_id: int,
        message: dict[str, Any],
        text: str,
        auth_state: ChatAuthState,
    ) -> None:
        pending_command = auth_state.pending_command
        if pending_command is None:
            return
        if pending_command.command_kind == "custom":
            await self._handle_custom_pending_command_input(chat_id, text, auth_state)
            return

        next_field = self._get_next_pending_field(pending_command)
        if next_field is None:
            auth_state.pending_command = None
            self._state_store.save_chat_state(chat_id, auth_state)
            return

        spec = COMMAND_INDEX.get(pending_command.command_name)
        has_photo = self._message_has_photo(message)
        if next_field == "message" and has_photo:
            pass
        elif not text.strip():
            await self._send_text(chat_id, self._build_field_prompt(next_field))
            return

        if text.strip():
            if next_field == "two_factor_code":
                pending_command.arguments[next_field] = text.strip()
            else:
                pending_command.arguments[next_field] = parse_scalar(text.strip())

        following_field = self._get_next_pending_field(pending_command)
        if following_field is not None:
            self._state_store.save_chat_state(chat_id, auth_state)
            await self._send_text(chat_id, self._build_field_prompt(following_field))
            return

        auth_state.pending_command = None
        self._state_store.save_chat_state(chat_id, auth_state)
        if pending_command.command_kind == "utility":
            await self._execute_utility_command(
                chat_id,
                pending_command.command_name,
                pending_command.arguments,
                auth_state,
            )
            return
        if spec is None:
            raise ValueError(
                f"Comando pendiente desconocido: {pending_command.command_name}"
            )
        await self._execute_api_command(
            chat_id, spec, pending_command.arguments, message, auth_state
        )

    async def _handle_custom_pending_command_input(
        self,
        chat_id: int,
        text: str,
        auth_state: ChatAuthState,
    ) -> None:
        pending_command = auth_state.pending_command
        if pending_command is None:
            return

        next_field = self._get_next_pending_field(pending_command)
        if next_field is None:
            auth_state.pending_command = None
            self._state_store.save_chat_state(chat_id, auth_state)
            await self._execute_custom_command(
                chat_id,
                pending_command.command_name,
                pending_command.arguments,
                auth_state,
            )
            return

        raw_value = text.strip()
        if not raw_value:
            prompt = self._build_custom_field_prompt(
                pending_command.command_name, next_field
            )
            keyboard_rows = self._get_field_keyboard(
                pending_command.command_name, next_field, chat_id
            )
            if keyboard_rows:
                await self._send_message_with_keyboard(chat_id, prompt, keyboard_rows)
            else:
                await self._send_text(chat_id, prompt)
            return

        parsed_value = self._parse_custom_field_value(
            pending_command.command_name,
            next_field,
            raw_value,
        )
        pending_command.arguments[next_field] = parsed_value
        if pending_command.command_name == "rules" and next_field == "rule_name":
            rule_name = str(parsed_value)
            pending_command.field_order = ["rule_name", *RULE_DYNAMIC_FIELDS[rule_name]]

        following_field = self._get_next_pending_field(pending_command)
        if following_field is not None:
            self._state_store.save_chat_state(chat_id, auth_state)
            prompt = self._build_custom_field_prompt(
                pending_command.command_name, following_field
            )
            keyboard_rows = self._get_field_keyboard(
                pending_command.command_name, following_field, chat_id
            )
            if keyboard_rows:
                await self._send_message_with_keyboard(chat_id, prompt, keyboard_rows)
            else:
                await self._send_text(chat_id, prompt)
            return

        auth_state.pending_command = None
        self._state_store.save_chat_state(chat_id, auth_state)
        try:
            await self._execute_custom_command(
                chat_id,
                pending_command.command_name,
                pending_command.arguments,
                auth_state,
            )
        except ValueError as exc:
            await self._send_text(chat_id, str(exc))

    async def _start_pending_command(
        self,
        chat_id: int,
        auth_state: ChatAuthState,
        pending_command: PendingCommandState,
    ) -> None:
        auth_state.pending_command = pending_command
        self._state_store.save_chat_state(chat_id, auth_state)
        next_field = self._get_next_pending_field(pending_command)
        if next_field is None:
            return
        prompt = (
            self._build_custom_field_prompt(pending_command.command_name, next_field)
            if pending_command.command_kind == "custom"
            else self._build_field_prompt(next_field)
        )
        intro = f"Iniciando /{pending_command.command_name}. "
        keyboard_rows = self._get_field_keyboard(
            pending_command.command_name, next_field, chat_id
        )
        if keyboard_rows:
            await self._send_message_with_keyboard(
                chat_id, intro + prompt, keyboard_rows
            )
        else:
            await self._send_text(chat_id, intro + prompt)

    @staticmethod
    def _get_prompt_fields(command_name: str, spec: CommandSpec) -> tuple[str, ...]:
        if command_name == "list_p2p":
            return LIST_P2P_FILTER_FIELDS
        if command_name == "send_p2p_chat":
            return ("uuid", "message")
        return spec.required_fields

    @staticmethod
    def _build_execution_arguments(
        spec: CommandSpec,
        arguments: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        if spec.command != "list_p2p":
            return arguments
        return {"page": 1, "take": 100}

    @staticmethod
    def _format_command_payload(
        spec: CommandSpec,
        request_arguments: dict[str, JsonValue],
        response_body: JsonValue | str | None,
    ) -> JsonValue | str | None:
        if spec.command != "list_p2p":
            return response_body
        return QvaPayTelegramBot._filter_list_p2p_response(
            request_arguments, response_body
        )

    @staticmethod
    def _get_missing_fields(
        field_order: tuple[str, ...] | list[str],
        arguments: dict[str, JsonValue],
    ) -> list[str]:
        return [
            field
            for field in field_order
            if not QvaPayTelegramBot._has_value(arguments, field)
        ]

    @staticmethod
    def _get_next_pending_field(pending_command: PendingCommandState) -> str | None:
        for field in pending_command.field_order:
            if not QvaPayTelegramBot._has_value(pending_command.arguments, field):
                return field
        return None

    @staticmethod
    def _has_value(arguments: dict[str, Any], field_name: str) -> bool:
        if field_name not in arguments:
            return False
        value = arguments[field_name]
        if isinstance(value, str):
            return bool(value.strip())
        return True  # None means the field was explicitly skipped

    @staticmethod
    def _build_field_prompt(field_name: str) -> str:
        prompt = FIELD_PROMPTS.get(field_name, f"Envía el valor para {field_name}.")
        return f"{prompt} Envía {CANCEL_COMMAND} para cancelar."

    @staticmethod
    def _build_custom_field_prompt(command_name: str, field_name: str) -> str:
        if command_name == "rules" and field_name == "target_type":
            return "Selecciona el tipo de oferta para el monitor. Envía /cancel para cancelar."
        if command_name == "rules" and field_name == "rule_name":
            return "¿Qué regla deseas configurar?"
        if command_name == "rules" and field_name == "rule_coin":
            return "Selecciona la moneda. Envía /cancel para cancelar."
        prompt = FIELD_PROMPTS.get(field_name, f"Envía el valor para {field_name}.")
        return f"{prompt} Envía {CANCEL_COMMAND} para cancelar."

    def _get_field_keyboard(
        self,
        command_name: str,
        field_name: str,
        chat_id: int | None = None,
    ) -> list[list[dict[str, str]]]:
        if command_name == "rules" and field_name == "rule_name":
            return [
                [
                    {
                        "text": label,
                        "callback_data": f"{P2P_RULE_NAME_CALLBACK_PREFIX}{key}",
                    }
                ]
                for key, label in P2P_RULE_NAME_OPTIONS
            ]
        if command_name == "rules" and field_name == "rule_coin":
            return [
                [
                    {
                        "text": c,
                        "callback_data": f"{P2P_RULE_COIN_CALLBACK_PREFIX}{c}",
                    }
                ]
                for c in P2P_RULE_COIN_OPTIONS
            ]
        if field_name == "target_type":
            coin: str | None = None
            if chat_id is not None:
                coin = self._p2p_repository.get_chat_state(chat_id).rules.coin
            coin_label = coin or "la moneda"
            return [
                [
                    {
                        "text": f"🛒 Comprar — Das QUSD, recibes {coin_label}",
                        "callback_data": f"{P2P_OFFER_TYPE_CALLBACK_PREFIX}buy",
                    }
                ],
                [
                    {
                        "text": f"💰 Vender — Das {coin_label}, recibes QUSD",
                        "callback_data": f"{P2P_OFFER_TYPE_CALLBACK_PREFIX}sell",
                    }
                ],
            ]
        return []

    @staticmethod
    def _filter_list_p2p_response(
        arguments: dict[str, JsonValue],
        response_body: JsonValue | str | None,
    ) -> JsonValue | str | None:
        if not isinstance(response_body, dict):
            return response_body
        offers = response_body.get("offers")
        if not isinstance(offers, list):
            return response_body

        normalized_coin = str(arguments.get("coin_filter", "")).strip().upper()
        coin_aliases = LIST_P2P_COIN_ALIASES.get(normalized_coin, (normalized_coin,))
        min_ratio = QvaPayTelegramBot._to_float(arguments.get("min_ratio"))
        max_ratio = QvaPayTelegramBot._to_float(arguments.get("max_ratio"))
        min_amount = QvaPayTelegramBot._to_float(arguments.get("min_amount"))
        max_amount = QvaPayTelegramBot._to_float(arguments.get("max_amount"))

        filtered_offers: list[JsonValue] = []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            offer_coin = str(offer.get("coin", "")).strip().upper()
            if normalized_coin and offer_coin not in coin_aliases:
                continue
            amount = QvaPayTelegramBot._to_float(offer.get("amount"))
            receive = QvaPayTelegramBot._to_float(offer.get("receive"))
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

        filters: JsonObject = {
            "coin": normalized_coin,
            "min_ratio": min_ratio,
            "max_ratio": max_ratio,
            "min_amount": min_amount,
            "max_amount": max_amount,
        }
        return {
            "filters": filters,
            "count": len(filtered_offers),
            "offers": filtered_offers,
        }

    @staticmethod
    def _to_float(value: JsonValue | None) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            try:
                return float(value.strip())
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_optional_float(value: JsonValue | None) -> float | None:
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

    def _parse_custom_field_value(
        self,
        command_name: str,
        field_name: str,
        raw_value: str,
    ) -> JsonValue:
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
            return self._parse_offer_type(raw_value).value
        if field_name == "rule_name":
            normalized = RULE_NAME_ALIASES.get(raw_value.strip().lower())
            if normalized is None:
                raise ValueError(
                    "Regla no válida. Usa coin, ratio, amount, only_kyc, only_vip, offer_type o reset."
                )
            return normalized
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
            return self._parse_yes_no(raw_value)
        if field_name == "uuid":
            return raw_value.strip()
        raise ValueError(f"Campo no soportado: {field_name} para /{command_name}")

    @staticmethod
    def _parse_yes_no(value: JsonValue | None) -> bool:
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

    @staticmethod
    def _parse_offer_type(value: JsonValue | None) -> P2POfferType:
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

    @staticmethod
    def _validate_monitor_rules(rules: P2PMonitorRules) -> None:
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

    @staticmethod
    def _format_rule_change(rule_name: str, state: P2PMonitorChatState) -> str:
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
            return (
                f"Monto mín: {_val(rules.min_amount)} | máx: {_val(rules.max_amount)}"
            )
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

    @staticmethod
    def _apply_profile_payload(
        auth_state: ChatAuthState, payload: dict[str, Any]
    ) -> None:
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

    @staticmethod
    def _message_has_photo(message: dict[str, Any]) -> bool:
        photos = message.get("photo")
        return isinstance(photos, list) and bool(photos)

    async def _extract_photo_upload(
        self,
        message: dict[str, Any],
        spec: CommandSpec,
    ) -> FileUpload | None:
        if not spec.supports_photo:
            return None
        photos = message.get("photo")
        if not isinstance(photos, list) or not photos:
            return None
        largest_photo = photos[-1]
        if not isinstance(largest_photo, dict):
            return None
        file_id = largest_photo.get("file_id")
        if not isinstance(file_id, str):
            return None

        get_file_response = await self._http_client.request(
            "GET",
            f"{self._settings.telegram_api_base_url}/getFile",
            query={"file_id": file_id},
        )
        payload = (
            get_file_response.body if isinstance(get_file_response.body, dict) else {}
        )
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        file_path = result.get("file_path") if isinstance(result, dict) else None
        if not isinstance(file_path, str):
            raise ValueError("Telegram no devolvió una ruta para la foto adjunta")

        status_code, content, headers = await self._http_client.get_bytes(
            f"{self._settings.telegram_file_base_url}/{file_path}"
        )
        if status_code >= 400:
            raise ValueError("No se pudo descargar la foto adjunta de Telegram")

        filename = PurePosixPath(file_path).name or "telegram-photo.jpg"
        return FileUpload(
            filename=filename, content=content, content_type=headers.get("Content-Type")
        )

    async def _send_text(
        self, chat_id: int, text: str, *, parse_mode: str | None = None
    ) -> None:
        for chunk in self._split_text(text):
            body: dict[str, Any] = {"chat_id": chat_id, "text": chunk}
            if parse_mode is not None:
                body["parse_mode"] = parse_mode
            await self._http_client.request(
                "POST",
                f"{self._settings.telegram_api_base_url}/sendMessage",
                json_body=body,
            )

    async def _send_message_with_keyboard(
        self,
        chat_id: int,
        text: str,
        keyboard_rows: list[list[dict[str, str]]],
        *,
        parse_mode: str | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": {"inline_keyboard": keyboard_rows},
        }
        if parse_mode is not None:
            body["parse_mode"] = parse_mode
        await self._http_client.request(
            "POST",
            f"{self._settings.telegram_api_base_url}/sendMessage",
            json_body=body,
        )

    async def _answer_callback_query(self, callback_query_id: str) -> None:
        await self._http_client.request(
            "POST",
            f"{self._settings.telegram_api_base_url}/answerCallbackQuery",
            json_body={"callback_query_id": callback_query_id},
        )

    async def _handle_callback_query(self, callback_query: dict[str, Any]) -> None:
        callback_query_id = str(callback_query.get("id", ""))
        data = callback_query.get("data", "")
        cq_message = callback_query.get("message")
        chat_id: int | None = None
        if isinstance(cq_message, dict):
            chat = cq_message.get("chat", {})
            raw_id = chat.get("id")
            if isinstance(raw_id, int):
                chat_id = raw_id

        await self._answer_callback_query(callback_query_id)

        if not isinstance(chat_id, int):
            return

        if chat_id not in self._settings.allowed_chat_ids:
            return

        if isinstance(data, str) and data.startswith(CANCEL_P2P_CALLBACK_PREFIX):
            payload = data[len(CANCEL_P2P_CALLBACK_PREFIX) :]
            # payload format: {uuid}:{evaluated_at} — UUID is always 36 chars
            if len(payload) >= 37 and payload[36] == ":":
                uuid = payload[:36]
            else:
                uuid = payload

            auth_state = self._state_store.get_chat_state(chat_id)
            if not auth_state.has_bearer:
                await self._send_text(
                    chat_id, "Debes iniciar sesión para cancelar una oferta."
                )
                return

            response = await self._qvapay_client.execute(
                COMMAND_INDEX["cancel_p2p"],
                {"uuid": uuid},
                auth_state,
            )
            if response.status_code < 400:
                monitor_state = self._p2p_repository.get_chat_state(chat_id)
                for entry in monitor_state.applied_history:
                    if entry.uuid == uuid:
                        entry.status = "cancelled"
                        break
                self._p2p_repository.save_chat_state(chat_id, monitor_state)
                await self._send_text(
                    chat_id, f"Oferta {uuid} cancelada correctamente."
                )
            else:
                await self._send_text(
                    chat_id,
                    f"Error al cancelar la oferta.\nHTTP {response.status_code}\n{pretty_payload(response.body)}",
                )
            return

        if isinstance(data, str) and data.startswith(APPLIED_LIST_PAGE_CALLBACK_PREFIX):
            raw_page = data[len(APPLIED_LIST_PAGE_CALLBACK_PREFIX) :]
            try:
                page = int(raw_page)
            except ValueError:
                page = 0
            monitor_state = self._p2p_repository.get_chat_state(chat_id)
            coin_averages = await self._fetch_coin_averages()
            header, keyboard_rows = format_applied_list_keyboard(
                monitor_state.applied_history,
                monitor_state.lost_race_history,
                page=page,
                coin_averages=coin_averages,
            )
            if keyboard_rows:
                await self._send_message_with_keyboard(
                    chat_id, header, keyboard_rows, parse_mode="HTML"
                )
            else:
                await self._send_text(chat_id, header)
            return

        if isinstance(data, str) and data.startswith(APPLIED_DETAIL_CALLBACK_PREFIX):
            payload = data[len(APPLIED_DETAIL_CALLBACK_PREFIX) :]
            # payload format: {uuid}:{evaluated_at} — UUID is always 36 chars
            if len(payload) >= 37 and payload[36] == ":":
                uuid = payload[:36]
                evaluated_at = payload[37:]
            else:
                uuid = payload
                evaluated_at = ""

            monitor_state = self._p2p_repository.get_chat_state(chat_id)
            entry = None
            for collection in (
                monitor_state.applied_history,
                monitor_state.lost_race_history,
            ):
                for e in collection:
                    if e.uuid == uuid and (
                        not evaluated_at or e.evaluated_at == evaluated_at
                    ):
                        entry = e
                        break
                if entry is not None:
                    break

            if entry is None:
                await self._send_text(
                    chat_id, f"No se encontraron datos para la oferta {uuid}."
                )
                return

            await self._send_text(
                chat_id, format_applied_detail(entry), parse_mode="HTML"
            )
            return

        for prefix, field_name in (
            (P2P_RULE_NAME_CALLBACK_PREFIX, "rule_name"),
            (P2P_RULE_COIN_CALLBACK_PREFIX, "rule_coin"),
            (P2P_OFFER_TYPE_CALLBACK_PREFIX, "target_type"),
        ):
            if isinstance(data, str) and data.startswith(prefix):
                selected_value = data[len(prefix) :]
                auth_state = self._state_store.get_chat_state(chat_id)
                if (
                    auth_state.pending_command is not None
                    and auth_state.pending_command.command_kind == "custom"
                ):
                    await self._handle_custom_pending_command_input(
                        chat_id, selected_value, auth_state
                    )
                return

        if isinstance(data, str) and data.startswith(
            MONITOR_ON_CONFIRM_CALLBACK_PREFIX
        ):
            payload = data[len(MONITOR_ON_CONFIRM_CALLBACK_PREFIX) :]
            if payload == "cancel":
                await self._send_text(chat_id, "Activación del monitor cancelada.")
                return
            if payload.startswith("confirm:"):
                interval_str = payload[len("confirm:") :]
                try:
                    poll_interval = int(interval_str)
                except ValueError:
                    await self._send_text(chat_id, "Error: intervalo inválido.")
                    return
                auth_state = self._state_store.get_chat_state(chat_id)
                monitor_state = self._p2p_repository.get_chat_state(chat_id)
                monitor_state.enabled = True
                monitor_state.poll_interval_seconds = poll_interval
                self._p2p_repository.save_chat_state(chat_id, monitor_state)
                await self._p2p_monitor_manager.restart_chat(chat_id, auth_state)
                await self._send_text(chat_id, format_monitor_status(monitor_state))
            return

    async def _fetch_coin_averages(self) -> dict[str, float]:
        response = await self._qvapay_client.execute(
            COMMAND_INDEX["average"],
            {},
            ChatAuthState(),
        )
        averages: dict[str, float] = {}
        if response.status_code == 200 and isinstance(response.body, dict):
            for coin, raw in response.body.items():
                if isinstance(raw, dict):
                    avg = raw.get("average")
                    if isinstance(avg, (int, float)) and avg > 0:
                        averages[coin] = float(avg)
        return averages

    async def _refresh_applied_statuses(
        self,
        chat_id: int,
        auth_state: ChatAuthState,
        monitor_state: P2PMonitorChatState,
    ) -> bool:
        """Refresca el status de QvaPay para entradas aplicadas exitosamente.

        Llama a GET /p2p/{uuid} para cada entrada con result=APPLIED cuyo status
        actual no sea terminal. Devuelve True si alguna entrada fue actualizada.
        """
        if not auth_state.has_bearer:
            return False

        _TERMINAL_STATUSES = {"cancelled", "completed", "rejected"}
        updated = False

        for entry in monitor_state.applied_history:
            if entry.result != OfferProcessResult.APPLIED:
                continue
            if entry.status.lower() in _TERMINAL_STATUSES:
                continue
            try:
                response = await self._qvapay_client.execute(
                    COMMAND_INDEX["p2p_detail"],
                    {"uuid": entry.uuid},
                    auth_state,
                )
                if response.status_code == 200 and isinstance(response.body, dict):
                    p2p_data = response.body.get("p2p")
                    if isinstance(p2p_data, dict):
                        new_status = str(p2p_data.get("status", "")).strip().lower()
                        if new_status and new_status != entry.status:
                            LOGGER.info(
                                "Offer status updated chat_id=%s uuid=%s %s -> %s",
                                chat_id,
                                entry.uuid,
                                entry.status,
                                new_status,
                            )
                            entry.status = new_status
                            updated = True
            except Exception:
                LOGGER.warning(
                    "Failed to refresh status for offer chat_id=%s uuid=%s",
                    chat_id,
                    entry.uuid,
                )

        return updated

    @staticmethod
    def _extract_chat_id(update: dict[str, Any]) -> int | None:
        message = update.get("message") or update.get("edited_message")
        if isinstance(message, dict):
            chat = message.get("chat", {})
            chat_id = chat.get("id")
            if isinstance(chat_id, int):
                return chat_id
        cq = update.get("callback_query")
        if isinstance(cq, dict):
            cq_message = cq.get("message")
            if isinstance(cq_message, dict):
                chat = cq_message.get("chat", {})
                chat_id = chat.get("id")
                if isinstance(chat_id, int):
                    return chat_id
        return None

    @staticmethod
    def _extract_message_text(message: dict[str, Any]) -> str:
        text = message.get("text") or message.get("caption") or ""
        return text.strip() if isinstance(text, str) else ""

    @staticmethod
    def _parse_command(text: str) -> ParsedCommand:
        parts = shlex.split(text)
        command_name = parts[0].split("@", maxsplit=1)[0].removeprefix("/")
        arguments: dict[str, JsonValue] = {}
        for token in parts[1:]:
            if "=" not in token:
                continue
            key, value = token.split("=", maxsplit=1)
            arguments[key] = parse_scalar(value)
        return ParsedCommand(name=command_name, arguments=arguments)

    @staticmethod
    def _format_api_response(
        spec: CommandSpec,
        status_code: int,
        payload: JsonValue | str | None,
    ) -> str:
        if (
            spec.command == "average"
            and status_code == 200
            and isinstance(payload, dict)
        ):
            return QvaPayTelegramBot._format_average_response(payload)
        return f"/{spec.command}\nHTTP {status_code}\n\n{pretty_payload(payload)}"

    @staticmethod
    def _format_average_response(payload: dict[str, JsonValue]) -> str:
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
            parsed_date = QvaPayTelegramBot._parse_updated_at(updated_at)
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

    @staticmethod
    def _parse_updated_at(value: JsonValue | None) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None

    @staticmethod
    def _format_help_for_command(spec: CommandSpec) -> str:
        examples = {
            "average": "/average",
            "login": '/login email="jane@example.com" password="secret123" remember=true',
            "list_p2p": "/list_p2p",
            "mark_p2p_paid": "/mark_p2p_paid uuid=offer-uuid tx_id=REF-123",
            "rate_p2p": '/rate_p2p uuid=offer-uuid rating=5 comment="Excelente" tags='
            "'"
            '["rapido","confiable"]'
            "'",
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

    @staticmethod
    def _split_text(text: str) -> list[str]:
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
