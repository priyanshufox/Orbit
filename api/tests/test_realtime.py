"""Realtime delivery (tasks 3.4, 3.5)."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from starlette.websockets import WebSocketDisconnect

from orbit.core import events
from orbit.core.auth import TokenVerifier
from orbit.core.config import Settings
from orbit.core.jobs import RecordingJobQueue
from orbit.core.realtime import CLOSE_REMOVED, ConnectionManager, RedisFanout
from orbit.main import create_app
from orbit.modules.accounts.models import User, auth_user
from orbit.modules.rooms.models import Room
from tests.conftest import TokenFactory


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed: int | None = None

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = code


async def wait_for(predicate, limit: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + limit
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("timed out")
        await asyncio.sleep(0.02)


async def test_event_published_on_one_worker_reaches_socket_on_another(
    test_settings: Settings,
) -> None:
    # Two "processes": separate Redis connections, managers and subscriptions.
    redis_a = Redis.from_url(test_settings.redis_url, decode_responses=True)
    redis_b = Redis.from_url(test_settings.redis_url, decode_responses=True)
    worker_a, worker_b = ConnectionManager(), ConnectionManager()
    fan_a, fan_b = RedisFanout(redis_a, worker_a), RedisFanout(redis_b, worker_b)
    fan_a.start()
    fan_b.start()
    try:
        await asyncio.wait_for(asyncio.gather(fan_a.ready.wait(), fan_b.ready.wait()), 3)
        code, player = uuid4().hex[:6].upper(), uuid4()
        socket = FakeSocket()
        worker_b.add(code, player, socket)  # type: ignore[arg-type]

        sent = events.Progress(finished=1, total=4)
        await events.publish(redis_a, code, sent)
        await wait_for(lambda: socket.sent)
        assert events.parse(socket.sent[0]) == sent

        await events.publish(redis_a, code, events.MemberLeft(user_id=player, reason="kicked"))
        await wait_for(lambda: socket.closed is not None)
        assert socket.closed == CLOSE_REMOVED
        assert worker_b.count(code) == 0
    finally:
        await fan_a.stop()
        await fan_b.stop()
        await redis_a.aclose()
        await redis_b.aclose()


# --- Real WebSocket through the app ----------------------------------------------------------


async def _users(url: str, names: list[str]) -> list[tuple[UUID, str]]:
    engine = create_async_engine(url, poolclass=NullPool)
    out = []
    async with engine.begin() as conn:
        for name in names:
            uid, email = uuid4(), f"ws-{name}-{uuid4().hex[:6]}@orbit.test"
            await conn.execute(
                insert(auth_user).values(id=uid, email=email, name=name, emailVerified=True)
            )
            await conn.execute(
                insert(User).values(
                    id=uid,
                    email=email,
                    name=name,
                    birth_year=1999,
                    is_adult=True,
                    consented_at=datetime.now(UTC),
                )
            )
            out.append((uid, email))
    await engine.dispose()
    return out


async def _cleanup(url: str, ids: list[UUID]) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(delete(Room).where(Room.host_id.in_(ids)))
        await conn.execute(delete(auth_user).where(auth_user.c.id.in_(ids)))
    await engine.dispose()


@pytest.fixture
def ws_users(
    migrated_db: str, make_token: TokenFactory
) -> Iterator[list[tuple[UUID, dict[str, str], str]]]:
    users = asyncio.run(_users(migrated_db, ["Host", "Guest", "Stranger"]))
    yield [
        (uid, {"Authorization": f"Bearer {make_token(uid, email)}"}, make_token(uid, email))
        for uid, email in users
    ]
    asyncio.run(_cleanup(migrated_db, [u[0] for u in users]))


def test_websocket_auth_membership_and_live_events(
    test_settings: Settings, token_verifier: TokenVerifier, ws_users: list
) -> None:
    (_, host, host_token), (_, guest, _), (_, _, stranger_token) = ws_users
    app = create_app(test_settings, token_verifier=token_verifier, jobs=RecordingJobQueue())
    with TestClient(app) as client:
        code = client.post("/rooms", headers=host).json()["code"]
        client.post(f"/rooms/{code}/join", headers=host)

        with client.websocket_connect(f"/ws/rooms/{code}") as ws:
            ws.send_json({"type": "auth", "token": host_token})
            assert ws.receive_json() == {"type": "ready", "state": "LOBBY"}
            ws.send_text("ping")
            assert ws.receive_text() == "pong"

            client.post(f"/rooms/{code}/join", headers=guest)
            event = events.parse(ws.receive_text())
            assert isinstance(event, events.MemberJoined)
            assert event.name == "Guest"

        with client.websocket_connect(f"/ws/rooms/{code}") as ws:
            ws.send_json({"type": "auth", "token": "not-a-jwt"})
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_text()
            assert closed.value.code == 4401

        with client.websocket_connect(f"/ws/rooms/{code}") as ws:
            ws.send_json({"type": "auth", "token": stranger_token})
            with pytest.raises(WebSocketDisconnect) as closed:
                ws.receive_text()
            assert closed.value.code == 4403
