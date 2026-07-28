"""Inyección de dependencias y autenticación de la web app."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from qvapay_bot.config import Settings
from qvapay_bot.events import EventBus
from qvapay_bot.p2p_monitor import P2PMonitorManager
from qvapay_bot.p2p_repository import P2PMonitorStateStore
from qvapay_bot.qvapay_client import QvaPayClient
from qvapay_bot.state import BotStateStore, ChatAuthState
from qvapay_web.security import COOKIE_NAME, decode_session_token


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_state_store(request: Request) -> BotStateStore:
    return request.app.state.state_store


def get_repository(request: Request) -> P2PMonitorStateStore:
    return request.app.state.repository


def get_manager(request: Request) -> P2PMonitorManager:
    return request.app.state.manager


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_qvapay_client(request: Request) -> QvaPayClient:
    return request.app.state.qvapay_client


class CurrentUser:
    def __init__(self, user_id: str, auth_state: ChatAuthState) -> None:
        self.user_id = user_id
        self.auth_state = auth_state


def current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    state_store: Annotated[BotStateStore, Depends(get_state_store)],
) -> CurrentUser:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    user_id = decode_session_token(token, secret=settings.jwt_secret)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
    auth_state = state_store.get_chat_state(user_id)
    if not auth_state.has_bearer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        )
    return CurrentUser(user_id=user_id, auth_state=auth_state)


CurrentUserDep = Annotated[CurrentUser, Depends(current_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
StateStoreDep = Annotated[BotStateStore, Depends(get_state_store)]
RepositoryDep = Annotated[P2PMonitorStateStore, Depends(get_repository)]
ManagerDep = Annotated[P2PMonitorManager, Depends(get_manager)]
EventBusDep = Annotated[EventBus, Depends(get_event_bus)]
QvaPayClientDep = Annotated[QvaPayClient, Depends(get_qvapay_client)]
