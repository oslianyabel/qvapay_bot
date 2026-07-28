"""Aplicación FastAPI: ciclo de vida, middleware, routers y estáticos del SPA."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from qvapay_bot.config import Settings
from qvapay_bot.events import EventBus, WebNotifier
from qvapay_bot.http_client import AsyncHttpClient
from qvapay_bot.p2p_monitor import P2PMonitorManager
from qvapay_bot.p2p_repository import P2PMonitorStateStore
from qvapay_bot.qvapay_client import QvaPayClient
from qvapay_bot.state import BotStateStore
from qvapay_web.routers import auth, events, history, monitor

LOGGER = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.from_env()
    http_client = AsyncHttpClient(settings.http_timeout_seconds)
    qvapay_client = QvaPayClient(
        http_client=http_client, base_url=settings.qvapay_base_url
    )
    state_store = BotStateStore(settings.state_file)
    repository = P2PMonitorStateStore(settings.p2p_state_file)
    event_bus = EventBus()
    manager = P2PMonitorManager(
        state_store=state_store,
        repository=repository,
        qvapay_client=qvapay_client,
        notifier=WebNotifier(event_bus),
    )

    app.state.settings = settings
    app.state.http_client = http_client
    app.state.qvapay_client = qvapay_client
    app.state.state_store = state_store
    app.state.repository = repository
    app.state.event_bus = event_bus
    app.state.manager = manager

    await manager.restore_tasks()
    LOGGER.info("Web app iniciada; monitores restaurados.")
    try:
        yield
    finally:
        await manager.shutdown()
        LOGGER.info("Web app detenida; monitores cancelados.")


def create_app() -> FastAPI:
    app = FastAPI(title="QvaPay P2P Monitor", lifespan=lifespan)

    # CORS necesita conocer los orígenes en tiempo de import (antes del lifespan),
    # así que leemos la config de entorno directamente aquí.
    try:
        cors_origins = list(Settings.from_env().cors_origins)
    except ValueError:
        cors_origins = ["http://localhost:5173"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(monitor.router, prefix="/api")
    app.include_router(history.router, prefix="/api")
    app.include_router(events.router, prefix="/api")

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    if not FRONTEND_DIST.is_dir():
        LOGGER.info("Frontend build no encontrado en %s (modo API-only).", FRONTEND_DIST)
        return

    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets", StaticFiles(directory=assets_dir), name="assets"
        )

    index_file = FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


app = create_app()
