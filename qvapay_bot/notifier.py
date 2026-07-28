"""Abstracción de notificaciones del monitor P2P.

El `P2PMonitorManager` emite `MonitorEvent`s a través de un `MonitorNotifier` en vez
de depender de Telegram. La web app implementa el notifier sobre un `EventBus` que
alimenta el stream SSE por usuario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from qvapay_bot.p2p_models import utcnow_iso


class EventType:
    CYCLE_STARTED = "cycle_started"
    OFFER_SELECTED = "offer_selected"
    APPLY_RESULT = "apply_result"
    CYCLE_COMPLETED = "cycle_completed"
    ERROR = "error"
    BALANCE_LOW = "balance_low"
    MONITOR_STOPPED = "monitor_stopped"


@dataclass(slots=True)
class MonitorEvent:
    type: str
    user_id: str
    data: dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "user_id": self.user_id,
            "at": self.at,
            "data": self.data,
        }


@runtime_checkable
class MonitorNotifier(Protocol):
    async def emit(self, event: MonitorEvent) -> None: ...


class NullNotifier:
    """Notifier que descarta todo. Útil para tests o ejecuciones headless."""

    async def emit(self, event: MonitorEvent) -> None:  # noqa: D102
        return None
