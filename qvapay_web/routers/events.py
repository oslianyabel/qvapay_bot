"""Stream de eventos del monitor en vivo (Server-Sent Events)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from qvapay_web.deps import CurrentUserDep, EventBusDep

router = APIRouter(tags=["events"])

_HEARTBEAT_SECONDS = 15.0


@router.get("/events")
async def stream_events(
    request: Request,
    user: CurrentUserDep,
    event_bus: EventBusDep,
) -> StreamingResponse:
    user_id = user.user_id
    queue = event_bus.subscribe(user_id)

    async def event_generator() -> AsyncIterator[str]:
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=_HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                data = json.dumps(event.to_dict(), ensure_ascii=False)
                yield f"event: {event.type}\ndata: {data}\n\n"
        finally:
            event_bus.unsubscribe(user_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
