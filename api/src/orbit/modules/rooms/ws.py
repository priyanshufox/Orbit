"""`/ws/rooms/{code}` (task 3.4): server -> client room events.

Browsers can't set headers on a WebSocket, so the first client message authenticates:
`{"type": "auth", "token": "<JWT>"}` within 10 s. The server answers `{"type": "ready"}` and
then forwards every `RoomEvent` for the room. The client may send "ping"; the server says
"pong". Close codes: 4401 bad token, 4403 not host or member, 4404 no such room, 4410 removed.
"""

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from orbit.core.auth import InvalidTokenError, TokenVerifier
from orbit.core.realtime import (
    CLOSE_FORBIDDEN,
    CLOSE_NOT_FOUND,
    CLOSE_UNAUTHORIZED,
    ConnectionManager,
)
from orbit.modules.rooms import codes, service

router = APIRouter()

AUTH_TIMEOUT_SECONDS = 10


@router.websocket("/ws/rooms/{code}")
async def room_socket(ws: WebSocket, code: str) -> None:
    await ws.accept()
    code = codes.normalise(code)
    try:
        hello = await asyncio.wait_for(ws.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
        verifier: TokenVerifier = ws.app.state.token_verifier
        if not isinstance(hello, dict) or hello.get("type") != "auth":
            raise InvalidTokenError("expected auth message")
        identity = await verifier.averify(str(hello.get("token", "")))
    except (TimeoutError, InvalidTokenError, ValueError, WebSocketDisconnect):
        with contextlib.suppress(Exception):
            await ws.close(code=CLOSE_UNAUTHORIZED)
        return

    async with ws.app.state.sessionmaker() as session:
        try:
            room = await service.context(session, code, identity.user_id)
        except service.RoomNotFoundError:
            await ws.close(code=CLOSE_NOT_FOUND)
            return
    if not (room.is_host or room.is_member):
        await ws.close(code=CLOSE_FORBIDDEN)
        return

    manager: ConnectionManager = ws.app.state.connections
    manager.add(code, identity.user_id, ws)
    try:
        await ws.send_json({"type": "ready", "state": room.state.value})
        while True:
            if await ws.receive_text() == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(code, ws)
