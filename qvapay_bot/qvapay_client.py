from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from qvapay_bot.http_client import (
    AsyncHttpClient,
    FileUpload,
    HttpResponse,
    JsonObject,
    JsonValue,
)
from qvapay_bot.state import ChatAuthState


class AuthMode(StrEnum):
    NONE = "none"
    BEARER = "bearer"
    EITHER = "either"


AVERAGE_TICK_ALIASES: dict[str, tuple[str, ...]] = {
    "CUP": ("CUP", "BANK_CUP"),
    "MLC": ("MLC", "BANK_MLC"),
    "TROPIPAY": ("TROPIPAY",),
    "ETECSA": ("ETECSA",),
    "ZELLE": ("ZELLE",),
    "CLASICA": ("CLASICA",),
    "BOLSATM": ("BOLSATM",),
    "BANDECPREPAGO": ("BANDECPREPAGO",),
    "SBERBANK": ("SBERBANK",),
    "USDTBSC": ("USDTBSC",),
}

LIST_P2P_COIN_ALIASES: dict[str, tuple[str, ...]] = {
    "CUP": ("CUP", "BANK_CUP"),
    "MLC": ("MLC", "BANK_MLC", "CMLC"),
    "TROPIPAY": ("TROPIPAY",),
    "ETECSA": ("ETECSA",),
    "ZELLE": ("ZELLE",),
    "CLASICA": ("CLASICA",),
    "BOLSATM": ("BOLSATM",),
    "BANDECPREPAGO": ("BANDECPREPAGO",),
    "SBERBANK": ("SBERBANK",),
    "USDTBSC": ("USDTBSC",),
}


@dataclass(slots=True, frozen=True)
class CommandSpec:
    command: str
    description: str
    method: str
    path_template: str
    auth_mode: AuthMode
    required_fields: tuple[str, ...] = ()
    path_fields: tuple[str, ...] = ()
    supports_photo: bool = False

    @property
    def usage(self) -> str:
        required = " ".join(f"{field}=..." for field in self.required_fields)
        return f"/{self.command} {required}".strip()


COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "login",
        "Login and store bearer token",
        "POST",
        "/auth/login",
        AuthMode.NONE,
        ("email", "password"),
    ),
    CommandSpec(
        "check_session",
        "Verify current bearer token",
        "POST",
        "/auth/check",
        AuthMode.BEARER,
    ),
    CommandSpec(
        "logout", "Logout current session", "GET", "/auth/logout", AuthMode.BEARER
    ),
    CommandSpec(
        "average", "Get P2P market averages", "GET", "/p2p/averages", AuthMode.NONE
    ),
    CommandSpec("profile", "Get user profile", "GET", "/user", AuthMode.BEARER),
)

_INTERNAL_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec("list_p2p", "List P2P offers", "GET", "/p2p", AuthMode.BEARER),
    CommandSpec(
        "p2p_detail",
        "Get P2P offer detail",
        "GET",
        "/p2p/{uuid}",
        AuthMode.BEARER,
        ("uuid",),
        ("uuid",),
    ),
    CommandSpec(
        "apply_p2p",
        "Apply to a P2P offer",
        "POST",
        "/p2p/{uuid}/apply",
        AuthMode.BEARER,
        ("uuid",),
        ("uuid",),
    ),
    CommandSpec(
        "cancel_p2p",
        "Cancel a P2P offer",
        "POST",
        "/p2p/{uuid}/cancel",
        AuthMode.BEARER,
        ("uuid",),
        ("uuid",),
    ),
    CommandSpec(
        "mark_p2p_paid",
        "Mark P2P as paid",
        "POST",
        "/p2p/{uuid}/paid",
        AuthMode.BEARER,
        ("uuid", "tx_id"),
        ("uuid",),
    ),
    CommandSpec(
        "rate_p2p",
        "Rate a P2P offer",
        "POST",
        "/p2p/{uuid}/rate",
        AuthMode.BEARER,
        ("uuid", "rating"),
        ("uuid",),
    ),
    CommandSpec(
        "get_p2p_chat",
        "Get P2P chat history",
        "GET",
        "/p2p/{uuid}/chat",
        AuthMode.BEARER,
        ("uuid",),
        ("uuid",),
    ),
    CommandSpec(
        "send_p2p_chat",
        "Send P2P chat message or image",
        "POST",
        "/p2p/{uuid}/chat",
        AuthMode.BEARER,
        ("uuid",),
        ("uuid",),
        True,
    ),
    CommandSpec(
        "list_payment_links",
        "List payment links",
        "GET",
        "/user/payment-links",
        AuthMode.BEARER,
    ),
    CommandSpec(
        "list_transactions", "List transactions", "GET", "/transaction", AuthMode.BEARER
    ),
    CommandSpec(
        "transaction_detail",
        "Get transaction detail",
        "GET",
        "/transaction/{uuid}",
        AuthMode.EITHER,
        ("uuid",),
        ("uuid",),
    ),
)

COMMAND_INDEX = {
    spec.command: spec for spec in (*COMMAND_SPECS, *_INTERNAL_COMMAND_SPECS)
}


def parse_scalar(value: str) -> JsonValue:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None

    if value.startswith("{") or value.startswith("["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)

    try:
        return float(value)
    except ValueError:
        return value


def pretty_payload(payload: JsonValue | str | None) -> str:
    if payload is None:
        return "No response body"
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, indent=2, ensure_ascii=True)
    return str(payload)


class QvaPayClient:
    def __init__(self, http_client: AsyncHttpClient, base_url: str) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")

    async def execute(
        self,
        spec: CommandSpec,
        arguments: dict[str, JsonValue],
        auth_state: ChatAuthState,
        *,
        photo: FileUpload | None = None,
    ) -> HttpResponse:
        self._validate_auth(spec, auth_state)
        normalized_arguments = self._normalize_arguments(spec, arguments)
        self._validate_arguments(spec, normalized_arguments, photo)

        path_arguments = {
            field: str(normalized_arguments[field])
            for field in spec.path_fields
            if field in normalized_arguments
        }
        path = spec.path_template.format(**path_arguments)

        remaining_arguments = {
            key: value
            for key, value in normalized_arguments.items()
            if key not in spec.path_fields
        }
        headers = self._build_headers(spec, auth_state)
        url = f"{self._base_url}{path}"

        query: JsonObject | None = None
        json_body: JsonValue | None = None
        multipart_fields: JsonObject | None = None
        multipart_files: dict[str, FileUpload] | None = None

        if spec.method == "GET":
            query = remaining_arguments
        elif photo is not None:
            multipart_fields = remaining_arguments
            multipart_files = {"file": photo}
        else:
            json_body = remaining_arguments

        response = await self._http_client.request(
            spec.method,
            url,
            headers=headers,
            query=query,
            json_body=json_body,
            multipart_fields=multipart_fields,
            multipart_files=multipart_files,
        )
        normalized_body = self._normalize_response_body(spec, response.body)

        if normalized_body is response.body:
            return response

        return HttpResponse(
            status_code=response.status_code,
            headers=response.headers,
            body=normalized_body,
        )

    @staticmethod
    def _normalize_arguments(
        spec: CommandSpec,
        arguments: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        normalized_arguments = dict(arguments)

        if spec.command == "login" and "two_factor_code" in normalized_arguments:
            normalized_arguments["two_factor_code"] = str(
                normalized_arguments["two_factor_code"]
            )

        return normalized_arguments

    @staticmethod
    def _normalize_response_body(
        spec: CommandSpec,
        body: JsonValue | str | None,
    ) -> JsonValue | str | None:
        if spec.command != "average" or not isinstance(body, dict):
            return body

        filtered: JsonObject = {}
        for output_tick, aliases in AVERAGE_TICK_ALIASES.items():
            for alias in aliases:
                value = body.get(alias)
                if isinstance(value, dict):
                    filtered[output_tick] = value
                    break

        return filtered

    @staticmethod
    def _validate_arguments(
        spec: CommandSpec,
        arguments: dict[str, JsonValue],
        photo: FileUpload | None,
    ) -> None:
        if spec.command == "send_p2p_chat":
            has_message = "message" in arguments and str(arguments["message"]).strip()
            if not (has_message or photo is not None):
                raise ValueError(
                    "send_p2p_chat requires message=... or a photo attachment"
                )

        missing_fields = [
            field for field in spec.required_fields if field not in arguments
        ]
        if missing_fields:
            fields = ", ".join(missing_fields)
            raise ValueError(f"Missing required fields: {fields}")

    @staticmethod
    def _validate_auth(spec: CommandSpec, auth_state: ChatAuthState) -> None:
        if spec.auth_mode == AuthMode.NONE:
            return
        if spec.auth_mode == AuthMode.BEARER and not auth_state.has_bearer:
            raise ValueError(
                "This command requires a bearer token. Use /login or /set_token."
            )
        if spec.auth_mode == AuthMode.EITHER and not (
            auth_state.has_app_credentials or auth_state.has_bearer
        ):
            raise ValueError(
                "This command requires /set_token or /set_app credentials."
            )

    @staticmethod
    def _build_headers(spec: CommandSpec, auth_state: ChatAuthState) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if spec.auth_mode == AuthMode.BEARER and auth_state.bearer_token:
            headers["Authorization"] = f"Bearer {auth_state.bearer_token}"
        elif spec.auth_mode == AuthMode.EITHER:
            if auth_state.has_app_credentials:
                headers["app-id"] = auth_state.app_id or ""
                headers["app-secret"] = auth_state.app_secret or ""
            elif auth_state.bearer_token:
                headers["Authorization"] = f"Bearer {auth_state.bearer_token}"
        return headers
