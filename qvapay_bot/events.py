"""EventBus en memoria (colas asyncio) que alimenta los streams SSE por usuario."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from qvapay_bot.notifier import MonitorEvent

LOGGER = logging.getLogger(__name__)

# Límite de eventos en cola por suscriptor; si un cliente lento se satura, se
# descartan los eventos más antiguos en vez de bloquear al monitor.
_MAX_QUEUE_SIZE = 100


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[MonitorEvent]]] = defaultdict(
            set
        )

    def subscribe(self, user_id: str) -> asyncio.Queue[MonitorEvent]:
        queue: asyncio.Queue[MonitorEvent] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._subscribers[user_id].add(queue)
        return queue

    def unsubscribe(self, user_id: str, queue: asyncio.Queue[MonitorEvent]) -> None:
        subscribers = self._subscribers.get(user_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(user_id, None)

    def publish(self, event: MonitorEvent) -> None:
        subscribers = self._subscribers.get(event.user_id)
        if not subscribers:
            return
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Cliente lento: descartamos el evento más viejo y encolamos el nuevo.
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    LOGGER.debug(
                        "Dropped SSE event user_id=%s type=%s",
                        event.user_id,
                        event.type,
                    )


class WebNotifier:
    """`MonitorNotifier` que publica los eventos del monitor en el `EventBus`."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    async def emit(self, event: MonitorEvent) -> None:
        self._event_bus.publish(event)
