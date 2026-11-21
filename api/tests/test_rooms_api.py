"""Rooms and the round over HTTP (Phases 3-4)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx2 import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core.config import Settings, get_settings
from orbit.core.jobs import RecordingJobQueue
from orbit.modules.game.models import Answer
from orbit.modules.rooms.models import Room
from tests.conftest import TokenFactory, make_identity, make_player

Headers = dict[str, str]

pytestmark = pytest.mark.usefixtures("banks")


async def players(
    db: AsyncSession, make_token: TokenFactory, *names: str
) -> list[tuple[UUID, Headers]]:
    return [await make_player(db, make_token, n) for n in names]


async def room_with(client: AsyncClient, host: Headers, *joiners: Headers) -> str:
    res = await client.post("/rooms", headers=host)
    assert res.status_code == 201, res.text
    code = res.json()["code"]
    for h in joiners:
        assert (await client.post(f"/rooms/{code}/join", headers=h)).status_code == 200
    return code


async def started_room(client: AsyncClient, host: Headers, *joiners: Headers) -> tuple[str, dict]:
    code = await room_with(client, host, host, *joiners)
    res = await client.post(f"/rooms/{code}/start", headers=host)
    assert res.status_code == 200, res.text
    deck = (await client.get(f"/rooms/{code}/deck", headers=host)).json()
    return code, deck


# --- 3.1 / 3.3 create and join ---------------------------------------------------------------


async def test_create_join_and_view(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    (_, host), (_, guest) = await players(db, make_token, "Host", "Guest")
    res = await client.post("/rooms", headers=host)
    room = res.json()
    assert res.status_code == 201
    assert room["state"] == "CREATED"
    assert room["is_host"] is True
    assert room["members"] == []

    code = room["code"]
    joined = (await client.post(f"/rooms/{code.lower()}/join", headers=guest)).json()
    assert joined["state"] == "LOBBY"
    assert [m["name"] for m in joined["members"]] == ["Guest"]
    assert joined["is_member"] is True and joined["is_host"] is False
    # Joining twice is harmless.
    assert (await client.post(f"/rooms/{code}/join", headers=guest)).status_code == 200


async def test_needs_consent_and_existing_room(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    uid = await make_identity(db, "fresh@orbit.test", "Fresh")
    fresh = {"Authorization": f"Bearer {make_token(uid, 'fresh@orbit.test')}"}
    assert (await client.post("/rooms", headers=fresh)).json()["detail"] == "onboarding_required"
    ((_, host),) = await players(db, make_token, "Host")
    assert (await client.get("/rooms/ZZZZZZ", headers=host)).status_code == 404
    assert (await client.get("/rooms/nope", headers=host)).status_code == 404


async def test_room_cap(
    app: FastAPI,
    client: AsyncClient,
    db: AsyncSession,
    make_token: TokenFactory,
    test_settings: Settings,
) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"room_member_cap": 2}
    )
    (_, host), (_, a), (_, b) = await players(db, make_token, "Host", "A", "B")
    code = await room_with(client, host, host, a)
    res = await client.post(f"/rooms/{code}/join", headers=b)
    assert res.status_code == 409
    assert res.json()["detail"] == "room_full"


async def test_join_rate_limit(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    (_, host), (_, guest) = await players(db, make_token, "Host", "Guest")
    code = await room_with(client, host)
    statuses = [
        (await client.post(f"/rooms/{code}/join", headers=guest)).status_code for _ in range(11)
    ]
    assert statuses[:10] == [200] * 10
    assert statuses[10] == 429


async def test_rooms_per_host_per_day(
    app: FastAPI,
    client: AsyncClient,
    db: AsyncSession,
    make_token: TokenFactory,
    test_settings: Settings,
) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(
        update={"rooms_per_host_per_day": 2}
    )
    ((_, host),) = await players(db, make_token, "Host")
    assert [(await client.post("/rooms", headers=host)).status_code for _ in range(3)] == [
        201,
        201,
        429,
    ]


# --- 3.8 leave and kick ----------------------------------------------------------------------


async def test_kick_removes_and_blocks_rejoin(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    (_, host), (guest_id, guest) = await players(db, make_token, "Host", "Guest")
    code = await room_with(client, host, guest)
    assert (
        await client.post(f"/rooms/{code}/kick", json={"user_id": str(guest_id)}, headers=guest)
    ).status_code == 403
    assert (
        await client.post(f"/rooms/{code}/kick", json={"user_id": str(guest_id)}, headers=host)
    ).status_code == 204
    view = (await client.get(f"/rooms/{code}", headers=host)).json()
    assert view["members"] == []
    rejoin = await client.post(f"/rooms/{code}/join", headers=guest)
    assert rejoin.status_code == 403
    assert rejoin.json()["detail"] == "kicked"


async def test_leave_deletes_my_round_data(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    (_, host), (guest_id, guest) = await players(db, make_token, "Host", "Guest")
    code, deck = await started_room(client, host, guest)
    q = next(c for c in deck["cards"] if c["kind"] == "question" and c["question_kind"] == "single")
    assert (
        await client.put(
            f"/rooms/{code}/answers/{q['id']}", json={"value": {"choice": 0}}, headers=guest
        )
    ).status_code == 204

    assert (await client.post(f"/rooms/{code}/leave", headers=guest)).status_code == 204
    left = await db.scalar(
        select(func.count())
        .select_from(Answer)
        .where(Answer.room_code == code, Answer.user_id == guest_id)
    )
    assert left == 0
    assert (await client.get(f"/rooms/{code}/deck", headers=guest)).status_code == 403


# --- 4.3-4.9 the round -----------------------------------------------------------------------


async def test_start_rules(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory, jobs: RecordingJobQueue
) -> None:
    (_, host), (_, guest) = await players(db, make_token, "Host", "Guest")
    code = await room_with(client, host, host)
    assert (await client.post(f"/rooms/{code}/start", headers=host)).status_code == 409  # 1 player
    await client.post(f"/rooms/{code}/join", headers=guest)
    assert (await client.post(f"/rooms/{code}/start", headers=guest)).status_code == 403  # not host
    res = await client.post(f"/rooms/{code}/start", headers=host)
    assert res.status_code == 200
    ends_at = datetime.fromisoformat(res.json()["ends_at"])
    assert timedelta(seconds=295) < ends_at - datetime.now(UTC) <= timedelta(seconds=300)
    end_job = next(c for c in jobs.calls if c[0] == "end_round")
    assert end_job[1] == (code,)
    assert end_job[2]["job_id"] == f"end:{code}"
    assert end_job[2]["defer_until"] == ends_at
    assert (await client.post(f"/rooms/{code}/start", headers=host)).status_code == 409  # twice


async def test_same_deck_for_everyone(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    (_, host), (_, guest) = await players(db, make_token, "Host", "Guest")
    code, deck = await started_room(client, host, guest)
    other = (await client.get(f"/rooms/{code}/deck", headers=guest)).json()
    assert [c["id"] for c in deck["cards"]] == [c["id"] for c in other["cards"]]
    kinds = [c["kind"] for c in deck["cards"]]
    assert kinds.count("question") == 10
    assert kinds.count("content") == 15


async def test_answers_and_reactions_are_idempotent_and_validated(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    (_, host), (_, guest) = await players(db, make_token, "Host", "Guest")
    code, deck = await started_room(client, host, guest)
    single = next(c for c in deck["cards"] if c.get("question_kind") == "single")
    card = next(c for c in deck["cards"] if c["kind"] == "content")
    url = f"/rooms/{code}/answers/{single['id']}"

    assert (await client.put(url, json={"value": {"choice": 0}}, headers=guest)).status_code == 204
    assert (await client.put(url, json={"value": {"choice": 1}}, headers=guest)).status_code == 204
    assert (await client.put(url, json={"value": {"choice": 99}}, headers=guest)).status_code == 422
    assert (
        await client.put(f"/rooms/{code}/answers/{card['id']}", json={"value": {}}, headers=guest)
    ).status_code == 404
    r_url = f"/rooms/{code}/reactions/{card['id']}"
    assert (await client.put(r_url, json={"reaction": "laugh"}, headers=guest)).status_code == 204
    assert (await client.put(r_url, json={"reaction": "laugh"}, headers=guest)).status_code == 204

    resumed = (await client.get(f"/rooms/{code}/deck", headers=guest)).json()
    assert resumed["answers"] == {single["id"]: {"choice": 1}}
    assert resumed["reactions"] == {card["id"]: "laugh"}


async def test_writes_rejected_after_the_round(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    (_, host), (_, guest) = await players(db, make_token, "Host", "Guest")
    code, deck = await started_room(client, host, guest)
    await db.execute(
        update(Room)
        .where(Room.code == code)
        .values(ends_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    q = next(c for c in deck["cards"] if c.get("question_kind") == "single")
    res = await client.put(
        f"/rooms/{code}/answers/{q['id']}", json={"value": {"choice": 0}}, headers=guest
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "round_over"


async def test_social_rules(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    (host_id, host), (guest_id, guest), (stranger_id, _) = await players(
        db, make_token, "Host", "Guest", "Stranger"
    )
    code, _ = await started_room(client, host, guest)
    url = f"/rooms/{code}/social"
    assert (
        await client.post(url, json={"to_user": str(host_id), "kind": "follow"}, headers=guest)
    ).status_code == 204
    assert (
        await client.post(url, json={"to_user": str(host_id), "kind": "follow"}, headers=guest)
    ).status_code == 204
    assert (
        await client.post(url, json={"to_user": str(guest_id), "kind": "follow"}, headers=guest)
    ).status_code == 422
    assert (
        await client.post(url, json={"to_user": str(stranger_id), "kind": "follow"}, headers=guest)
    ).status_code == 404


async def test_last_finisher_ends_round_once(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory, jobs: RecordingJobQueue
) -> None:
    (_, host), (_, guest) = await players(db, make_token, "Host", "Guest")
    code, _ = await started_room(client, host, guest)
    assert (await client.post(f"/rooms/{code}/finish", headers=host)).status_code == 204
    assert (await client.get(f"/rooms/{code}", headers=host)).json()["state"] == "PLAYING"
    assert (await client.post(f"/rooms/{code}/finish", headers=guest)).status_code == 204
    assert (await client.get(f"/rooms/{code}", headers=host)).json()["state"] == "SCORING"
    assert jobs.names().count("score_room") == 1
    # Late join after the round: refused.
    ((_, late),) = await players(db, make_token, "Late")
    res = await client.post(f"/rooms/{code}/join", headers=late)
    assert res.status_code == 409
    assert res.json()["detail"] == "round_over"
