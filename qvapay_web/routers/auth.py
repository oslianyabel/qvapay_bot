"""Autenticación: login vía QvaPay, sesión propia (JWT en cookie), perfil."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from qvapay_bot.qvapay_client import COMMAND_INDEX
from qvapay_bot.state import ChatAuthState
from qvapay_web.deps import (
    CurrentUserDep,
    ManagerDep,
    QvaPayClientDep,
    SettingsDep,
    StateStoreDep,
)
from qvapay_web.schemas import LoginRequest
from qvapay_web.security import COOKIE_NAME, create_session_token

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_TOKEN_KEYS = ("accessToken", "access_token", "token")


def _extract_token(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in _TOKEN_KEYS:
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    qvapay_client: QvaPayClientDep,
    state_store: StateStoreDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "email": payload.email,
        "password": payload.password,
    }
    if payload.two_factor_code:
        arguments["two_factor_code"] = payload.two_factor_code

    login_response = await qvapay_client.execute(
        COMMAND_INDEX["login"], arguments, ChatAuthState()
    )
    if login_response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de QvaPay inválidas.",
        )

    token = _extract_token(login_response.body)
    if token is None:
        LOGGER.error("QvaPay login sin token en la respuesta: %r", login_response.body)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="QvaPay no devolvió un token de acceso.",
        )

    # Recuperar el perfil para obtener el uuid (id de usuario de la app).
    auth_state = ChatAuthState(bearer_token=token)
    profile_response = await qvapay_client.execute(
        COMMAND_INDEX["profile"], {}, auth_state
    )
    if not isinstance(profile_response.body, dict) or profile_response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener el perfil de QvaPay.",
        )

    profile = profile_response.body
    user_uuid = profile.get("uuid")
    if not isinstance(user_uuid, str) or not user_uuid.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El perfil de QvaPay no tiene uuid.",
        )
    user_id = user_uuid.strip()

    # Preservar reglas/estado previos: solo actualizamos las credenciales.
    stored = state_store.get_chat_state(user_id)
    stored.bearer_token = token
    stored.user_uuid = user_id
    stored.username = (
        profile.get("username").strip()
        if isinstance(profile.get("username"), str)
        else stored.username
    )
    stored.kyc = bool(profile.get("kyc", False))
    stored.p2p_enabled = bool(profile.get("p2p_enabled", False))
    state_store.save_chat_state(user_id, stored)

    session_token = create_session_token(
        user_id,
        secret=settings.jwt_secret,
        expire_minutes=settings.jwt_expire_minutes,
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.jwt_expire_minutes * 60,
    )

    balance = profile.get("balance")
    return {
        "uuid": user_id,
        "username": stored.username,
        "kyc": stored.kyc,
        "p2p_enabled": stored.p2p_enabled,
        "balance": float(balance) if isinstance(balance, (int, float)) else None,
    }


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(key=COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
async def me(user: CurrentUserDep, manager: ManagerDep) -> dict[str, Any]:
    auth = user.auth_state
    balance = await manager.fetch_balance(auth)
    return {
        "uuid": user.user_id,
        "username": auth.username,
        "kyc": auth.kyc,
        "p2p_enabled": auth.p2p_enabled,
        "balance": balance,
    }
