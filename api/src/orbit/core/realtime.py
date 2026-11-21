"""Delivering room events to WebSockets across API processes (tasks 3.4, 3.5).

Each API process keeps the sockets it accepted in a `ConnectionManager` and runs one
`RedisFanout`, which pattern-subscribes to `room:*`. An event published by any process (API or
worker) therefore reaches every socket in that room, wherever it is held.
"""

import asyncio
import contextlib
import json
from uuid import UUID

import structlog
from fastapi import WebSocket
from redis.asyncio import Redis

log = structlog.get_logger("orbit.realtime")

# Application close codes (4000-4999 are free for apps).
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404
CLOSE_REMOVED = 4410  # left the room or was kicked


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[WebSocket, UUID]] = {}

    def add(self, room_code: str, user_id: UUID, ws: WebSocket) -> None:
        self._rooms.setdefault(room_code, {})[ws] = user_id

    def remove(self, room_code: str, ws: WebSocket) -> None:
        sockets = self._rooms.get(room_code)
        if sockets is not None:
            sockets.pop(ws, None)
            if not sockets:
                del self._rooms[room_code]

    def count(self, room_code: str | None = None) -> int:
        if room_code is None:
            return sum(len(s) for s in self._rooms.values())
        return len(self._rooms.get(room_code, {}))

    async def deliver(self, room_code: str, raw: str) -> None:
        sockets = dict(self._rooms.get(room_code, {}))
        if not sockets:
            return
        for ws in list(sockets):
            try:
                await ws.send_text(raw)
            except Exception:  # a dead socket must not stop delivery to the rest
                self.remove(room_code, ws)

        event = json.loads(raw)
        if event.get("type") == "member_left":
            gone = UUID(event["user_id"])
            for ws, user_id in sockets.items():
                if user_id == gone:
                    self.remove(room_code, ws)
                    with contextlib.suppress(Exception):
                        await ws.close(code=CLOSE_REMOVED, reason=event.get("reason", "left"))


class RedisFanout:
    """One pattern subscription per process; reconnects with backoff if Redis drops."""

    def __init__(self, redis: Redis, manager: ConnectionManager) -> None:
        self._redis = redis
        self._manager = manager
        self._task: asyncio.Task[None] | None = None
        self.ready = asyncio.Event()

    async def _run(self) -> None:
        backoff = 0.5
        while True:
            try:
                pubsub = self._redis.pubsub()
                await pubsub.psubscribe("room:*")
                self.ready.set()
                backoff = 0.5
                async for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    room_code = message["channel"].split(":", 1)[1]
                    await self._manager.deliver(room_code, message["data"])
            except asyncio.CancelledError:
                raise
            except Exception:
                self.ready.clear()
                log.exception("realtime.fanout_error", retry_in=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="redis-fanout")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
