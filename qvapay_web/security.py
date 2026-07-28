"""Emisión y verificación de tokens de sesión (JWT) para la web app."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

COOKIE_NAME = "session"
_ALGORITHM = "HS256"


def create_session_token(
    user_id: str,
    *,
    secret: str,
    expire_minutes: int,
) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_session_token(token: str, *, secret: str) -> str | None:
    """Devuelve el `user_id` (claim `sub`) si el token es válido, si no None."""
    try:
        payload = jwt.decode(token, secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub else None
