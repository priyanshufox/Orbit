"""A whole round against real Postgres, Redis and Neo4j (Phases 5-8)."""

import asyncio
import math
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx2 import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from orbit import pipeline
from orbit.core import events
from orbit.core.config import Settings
from orbit.modules.accounts.models import User
from orbit.modules.game.models import Answer, Reaction, Social
from orbit.modules.graph import service as graph
from orbit.modules.graph.driver import GraphDriver
from orbit.modules.privacy.models import AuditLog, GraphSnapshot
from orbit.modules.rooms.models import Room, RoomMember
from orbit.modules.scoring.models import Score
from tests.conftest import TokenFactory, make_player

pytestmark = pytest.mark.usefixtures("banks")

Player = tuple[UUID, dict[str, str]]


def answer_for(card: dict, style: str) -> dict:
    kind = card["question_kind"]
    n = len(card["options"].get("choices", []))
    if style == "ab":
        return (
            {"choice": 0}
            if kind == "single"
            else {"choices": [0]}
            if kind == "multi"
            else {"value": 0.9}
        )
    return (
        {"choice": n - 1}
        if kind == "single"
        else {"choices": [n - 1]}
        if kind == "multi"
        else {"value": 0.1}
    )


async def play_round(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> tuple[str, list[Player]]:
    """A and B think alike; C and D think alike; the two pairs differ. A follows B."""
    ps = [await make_player(db, make_token, n) for n in ("Asha", "Bilal", "Chitra", "Dev")]
    (a_id, a), (b_id, _), (_, c), (_, d) = ps
    code = (await client.post("/rooms", headers=a)).json()["code"]
    for _, h in ps:
        await client.post(f"/rooms/{code}/join", headers=h)
    assert (await client.post(f"/rooms/{code}/start", headers=a)).status_code == 200
    deck = (await client.get(f"/rooms/{code}/deck", headers=a)).json()

    for (_, h), style, reaction in (
        (ps[0], "ab", "laugh"),
        (ps[1], "ab", "laugh"),
        (ps[2], "cd", "skip"),
        (ps[3], "cd", "skip"),
    ):
        for card in deck["cards"]:
            if card["kind"] == "question":
                r = await client.put(
                    f"/rooms/{code}/answers/{card['id']}",
                    json={"value": answer_for(card, style)},
                    headers=h,
                )
            else:
                r = await client.put(
                    f"/rooms/{code}/reactions/{card['id']}", json={"reaction": reaction}, headers=h
                )
            assert r.status_code == 204, r.text
    await client.post(
        f"/rooms/{code}/social", json={"to_user": str(b_id), "kind": "follow"}, headers=a
    )
    for _, h in ps:
        await client.post(f"/rooms/{code}/finish", headers=h)
    assert (await client.get(f"/rooms/{code}", headers=a)).json()["state"] == "SCORING"
    assert a_id != b_id and c != d
    return code, ps


@pytest.fixture
async def revealed(
    client: AsyncClient,
    db: AsyncSession,
    redis: Redis,
    neo4j: GraphDriver,
    test_settings: Settings,
    make_token: TokenFactory,
) -> AsyncIterator[tuple[str, list[Player]]]:
    code, ps = await play_round(client, db, make_token)
    assert await pipeline.reveal(db, redis, neo4j, code, test_settings)
    yield code, ps
    await graph.delete_room(neo4j, code)


async def test_reveal_scores_and_graph(
    client: AsyncClient,
    revealed: tuple[str, list[Player]],
    make_token: TokenFactory,
    db: AsyncSession,
) -> None:
    code, ps = revealed
    (a_id, a), (b_id, _), (c_id, _), (d_id, d) = ps
    assert (await client.get(f"/rooms/{code}", headers=a)).json()["state"] == "REVEALED"

    view = (await client.get(f"/rooms/{code}/graph", headers=d)).json()
    assert len(view["nodes"]) == 4
    community = {UUID(n["id"]): n["community"] for n in view["nodes"]}
    assert community[a_id] == community[b_id]
    assert community[c_id] == community[d_id]
    assert community[a_id] != community[c_id]

    edges = {frozenset((UUID(e["a"]), UUID(e["b"]))): e for e in view["edges"]}
    ab = edges[frozenset((a_id, b_id))]
    assert ab["total"] > 0.8
    assert ab["answers"] == pytest.approx(1.0)
    assert ab["reactions"] == pytest.approx(1.0)
    assert any(r["text"].startswith("Same answer on 10 of 10 questions") for r in ab["reasons"])
    assert any(r["text"].startswith("You both laughed at 15 of 15") for r in ab["reasons"])
    assert view["follows"] == [{"from_user": str(a_id), "to_user": str(b_id)}]
    # Planets are placed by closeness: A-B (alike) sit closer than A-C (different).
    xyz = {UUID(n["id"]): (n["x"], n["y"], n["z"]) for n in view["nodes"]}
    assert math.dist(xyz[a_id], xyz[b_id]) < math.dist(xyz[a_id], xyz[c_id])
    # Every player has at least one drawn edge.
    assert {p for pair in edges for p in pair} == {a_id, b_id, c_id, d_id}

    ((_, stranger),) = [await make_player(db, make_token, "Stranger")]
    assert (await client.get(f"/rooms/{code}/graph", headers=stranger)).status_code == 403


async def test_graph_not_available_before_reveal(
    client: AsyncClient, db: AsyncSession, make_token: TokenFactory
) -> None:
    code, ps = await play_round(client, db, make_token)
    res = await client.get(f"/rooms/{code}/graph", headers=ps[0][1])
    assert res.status_code == 409


async def test_graph_rebuilds_when_neo4j_loses_it(
    client: AsyncClient, neo4j: GraphDriver, revealed: tuple[str, list[Player]]
) -> None:
    code, ps = revealed
    await graph.delete_room(neo4j, code)
    assert await graph.read_graph(neo4j, code) is None
    view = (await client.get(f"/rooms/{code}/graph", headers=ps[0][1])).json()
    assert len(view["nodes"]) == 4
    assert await graph.count_room_nodes(neo4j, code) > 0


async def test_gds_and_python_louvain_agree(
    db: AsyncSession,
    neo4j: GraphDriver,
    test_settings: Settings,
    revealed: tuple[str, list[Player]],
) -> None:
    code, _ = revealed
    with_gds = await pipeline.project(
        db, neo4j, code, test_settings.model_copy(update={"graph_use_gds": True})
    )
    python = await pipeline.project(
        db, neo4j, code, test_settings.model_copy(update={"graph_use_gds": False})
    )

    def groups(view) -> set[frozenset[UUID]]:
        out: dict[int, set[UUID]] = {}
        for n in view.nodes:
            out.setdefault(n.community, set()).add(n.id)
        return {frozenset(g) for g in out.values()}

    assert groups(with_gds) == groups(python)


async def test_follow_after_reveal_is_pushed_and_drawn(
    client: AsyncClient, redis: Redis, revealed: tuple[str, list[Player]]
) -> None:
    code, ps = revealed
    (a_id, _), _, (c_id, c), _ = ps
    pubsub = redis.pubsub()
    await pubsub.subscribe(events.channel(code))
    await pubsub.get_message(timeout=1)

    assert (
        await client.post(
            f"/rooms/{code}/social", json={"to_user": str(a_id), "kind": "follow"}, headers=c
        )
    ).status_code == 204
    msg = None
    for _ in range(40):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if msg:
            break
        await asyncio.sleep(0.02)
    await pubsub.aclose()
    assert msg is not None
    assert events.parse(msg["data"]) == events.SocialAdded(
        from_user=c_id, to_user=a_id, kind="follow"
    )

    view = (await client.get(f"/rooms/{code}/graph", headers=c)).json()
    assert {"from_user": str(c_id), "to_user": str(a_id)} in view["follows"]


async def test_expiry_snapshots_then_deletes_everywhere(
    client: AsyncClient,
    db: AsyncSession,
    neo4j: GraphDriver,
    test_settings: Settings,
    revealed: tuple[str, list[Player]],
) -> None:
    code, ps = revealed
    await db.execute(
        update(Room)
        .where(Room.code == code)
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    assert code in await pipeline.expire_due(db, neo4j, test_settings)

    for model in (Room, RoomMember, Answer, Reaction, Social, Score):
        column = Room.code if model is Room else model.room_code
        assert (
            await db.scalar(select(func.count()).select_from(model).where(column == code)) == 0
        ), model.__tablename__
    assert await graph.count_room_nodes(neo4j, code) == 0

    snaps = await db.scalar(
        select(func.count()).select_from(GraphSnapshot).where(GraphSnapshot.room_code == code)
    )
    assert snaps == 4
    mine = (await client.get("/me/snapshots", headers=ps[0][1])).json()
    assert mine[0]["room_code"] == code
    assert mine[0]["graph"]["me"] == str(ps[0][0])
    assert len(mine[0]["graph"]["nodes"]) >= 2

    audit = (await db.scalars(select(AuditLog).where(AuditLog.action == "room_expired"))).all()
    entry = next(a for a in audit if a.detail.get("room") == code)
    assert entry.detail["members"] == 4 and entry.detail["snapshots"] == 4
    assert set(entry.detail) == {"room", "members", "snapshots", "graph_nodes"}  # no personal data


async def test_delete_account_everywhere(
    client: AsyncClient, db: AsyncSession, neo4j: GraphDriver, revealed: tuple[str, list[Player]]
) -> None:
    code, ps = revealed
    b_id, b = ps[1]
    assert (await client.delete("/me", headers=b)).status_code == 202
    assert await db.get(User, b_id, populate_existing=True) is None
    assert await db.scalar(text('select count(*) from auth."user" where id = :u'), {"u": b_id}) == 0
    view = await graph.read_graph(neo4j, code)
    assert view is not None
    assert b_id not in {n.id for n in view.nodes}
    assert (
        await db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "account_deleted")
        )
        >= 1
    )
