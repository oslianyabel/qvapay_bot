from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self

DEFAULT_BASE_URL = "https://api.qvapay.com"
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_STATE_FILE = Path("data/bot_state.json")
DEFAULT_P2P_STATE_FILE = Path("data/p2p_monitor_state.json")
DEFAULT_ALLOWED_CHAT_IDS: frozenset[int] = frozenset({6595595136, 1138837437})


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", maxsplit=1)
        normalized_key = key.strip()
        normalized_value = value.strip().strip('"').strip("'")
        os.environ.setdefault(normalized_key, normalized_value)


@dataclass(slots=True, frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_dev_chat_id: int | None
    qvapay_base_url: str
    http_timeout_seconds: float
    state_file: Path
    p2p_state_file: Path
    allowed_chat_ids: frozenset[int]
    qvapay_email: str
    qvapay_password: str
    qvapay_email2: str
    qvapay_password2: str

    @classmethod
    def from_env(cls) -> Self:
        _load_dotenv(Path(".env"))

        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        raw_telegram_dev_chat_id = os.getenv("TELEGRAM_DEV_CHAT_ID", "").strip()
        telegram_dev_chat_id = (
            int(raw_telegram_dev_chat_id) if raw_telegram_dev_chat_id else None
        )

        qvapay_base_url = os.getenv("QVAPAY_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        http_timeout_seconds = float(
            os.getenv("HTTP_TIMEOUT_SECONDS", str(DEFAULT_HTTP_TIMEOUT))
        )
        state_file = Path(os.getenv("BOT_STATE_FILE", str(DEFAULT_STATE_FILE)))
        p2p_state_file = Path(
            os.getenv("BOT_P2P_STATE_FILE", str(DEFAULT_P2P_STATE_FILE))
        )

        raw_allowed = os.getenv("ALLOWED_CHAT_IDS", "").strip()
        if raw_allowed:
            allowed_chat_ids: frozenset[int] = frozenset(
                int(part.strip())
                for part in raw_allowed.split(",")
                if part.strip().lstrip("-").isdigit()
            )
        else:
            allowed_chat_ids = DEFAULT_ALLOWED_CHAT_IDS

        qvapay_email = os.getenv("EMAIL", "").strip()
        qvapay_password = os.getenv("PASSWORD", "").strip()
        qvapay_email2 = os.getenv("EMAIL2", "").strip()
        qvapay_password2 = os.getenv("PASSWORD2", "").strip()

        return cls(
            telegram_bot_token=telegram_bot_token,
            telegram_dev_chat_id=telegram_dev_chat_id,
            qvapay_base_url=qvapay_base_url,
            http_timeout_seconds=http_timeout_seconds,
            state_file=state_file,
            p2p_state_file=p2p_state_file,
            allowed_chat_ids=allowed_chat_ids,
            qvapay_email=qvapay_email,
            qvapay_password=qvapay_password,
            qvapay_email2=qvapay_email2,
            qvapay_password2=qvapay_password2,
        )
