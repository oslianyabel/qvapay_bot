from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self

DEFAULT_BASE_URL = "https://api.qvapay.com"
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_STATE_FILE = Path("data/bot_state.json")
DEFAULT_P2P_STATE_FILE = Path("data/p2p_monitor_state.json")
DEFAULT_JWT_EXPIRE_MINUTES = 60 * 24 * 7  # 7 días
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8000
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


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
    qvapay_base_url: str
    http_timeout_seconds: float
    state_file: Path
    p2p_state_file: Path
    jwt_secret: str
    jwt_expire_minutes: int
    cors_origins: tuple[str, ...]
    web_host: str
    web_port: int
    cookie_secure: bool

    @classmethod
    def from_env(cls) -> Self:
        _load_dotenv(Path(".env"))

        qvapay_base_url = os.getenv("QVAPAY_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        http_timeout_seconds = float(
            os.getenv("HTTP_TIMEOUT_SECONDS", str(DEFAULT_HTTP_TIMEOUT))
        )
        state_file = Path(os.getenv("BOT_STATE_FILE", str(DEFAULT_STATE_FILE)))
        p2p_state_file = Path(
            os.getenv("BOT_P2P_STATE_FILE", str(DEFAULT_P2P_STATE_FILE))
        )

        jwt_secret = os.getenv("JWT_SECRET", "").strip()
        if not jwt_secret:
            raise ValueError("JWT_SECRET is required")

        jwt_expire_minutes = int(
            os.getenv("JWT_EXPIRE_MINUTES", str(DEFAULT_JWT_EXPIRE_MINUTES))
        )

        raw_cors = os.getenv("CORS_ORIGINS", "").strip()
        if raw_cors:
            cors_origins = tuple(
                part.strip() for part in raw_cors.split(",") if part.strip()
            )
        else:
            cors_origins = DEFAULT_CORS_ORIGINS

        web_host = os.getenv("WEB_HOST", DEFAULT_WEB_HOST).strip() or DEFAULT_WEB_HOST
        web_port = int(os.getenv("WEB_PORT", str(DEFAULT_WEB_PORT)))
        cookie_secure = os.getenv("COOKIE_SECURE", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        return cls(
            qvapay_base_url=qvapay_base_url,
            http_timeout_seconds=http_timeout_seconds,
            state_file=state_file,
            p2p_state_file=p2p_state_file,
            jwt_secret=jwt_secret,
            jwt_expire_minutes=jwt_expire_minutes,
            cors_origins=cors_origins,
            web_host=web_host,
            web_port=web_port,
            cookie_secure=cookie_secure,
        )
