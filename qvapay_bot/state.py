from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class PendingCommandState:
    command_name: str
    command_kind: str
    field_order: list[str]
    arguments: dict[str, Any]


@dataclass(slots=True)
class ChatAuthState:
    bearer_token: str | None = None
    app_id: str | None = None
    app_secret: str | None = None
    user_uuid: str | None = None
    username: str | None = None
    kyc: bool = False
    p2p_enabled: bool = False
    pending_command: PendingCommandState | None = None
    logged_in_as: str | None = None

    @property
    def has_bearer(self) -> bool:
        return bool(self.bearer_token)

    @property
    def has_app_credentials(self) -> bool:
        return bool(self.app_id and self.app_secret)


class BotStateStore:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._chats: dict[str, ChatAuthState] = {}
        self._load()

    def get_chat_state(self, chat_id: int) -> ChatAuthState:
        key = str(chat_id)
        if key not in self._chats:
            self._chats[key] = ChatAuthState()
        return self._chats[key]

    def save_chat_state(self, chat_id: int, state: ChatAuthState) -> None:
        self._chats[str(chat_id)] = state
        self._save()

    def clear_chat_state(self, chat_id: int) -> None:
        self._chats[str(chat_id)] = ChatAuthState()
        self._save()

    def iter_chat_states(self) -> list[tuple[int, ChatAuthState]]:
        return [
            (int(chat_id), state)
            for chat_id, state in self._chats.items()
            if chat_id.isdigit()
        ]

    def _load(self) -> None:
        if not self._file_path.exists():
            return

        raw_data = json.loads(self._file_path.read_text(encoding="utf-8"))
        chats = raw_data.get("chats", {})
        self._chats = {
            key: ChatAuthState(
                bearer_token=value.get("bearer_token"),
                app_id=value.get("app_id"),
                app_secret=value.get("app_secret"),
                user_uuid=value.get("user_uuid"),
                username=value.get("username"),
                kyc=bool(value.get("kyc", False)),
                p2p_enabled=bool(value.get("p2p_enabled", False)),
                pending_command=self._load_pending_command(
                    value.get("pending_command")
                ),
                logged_in_as=self._parse_logged_in_as(value),
            )
            for key, value in chats.items()
            if isinstance(value, dict)
        }

    @staticmethod
    def _parse_logged_in_as(value: Any) -> str | None:
        raw = value.get("logged_in_as")
        return str(raw) if isinstance(raw, str) and raw.strip() else None

    @staticmethod
    def _load_pending_command(value: Any) -> PendingCommandState | None:
        if not isinstance(value, dict):
            return None

        command_name = value.get("command_name")
        command_kind = value.get("command_kind")
        field_order = value.get("field_order")
        arguments = value.get("arguments")

        if not isinstance(command_name, str) or not isinstance(command_kind, str):
            return None
        if not isinstance(field_order, list) or not all(
            isinstance(field, str) for field in field_order
        ):
            return None
        if not isinstance(arguments, dict):
            return None

        return PendingCommandState(
            command_name=command_name,
            command_kind=command_kind,
            field_order=field_order,
            arguments=arguments,
        )

    def _save(self) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"chats": {key: asdict(value) for key, value in self._chats.items()}}
        self._file_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
