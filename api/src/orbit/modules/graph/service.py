"""The per-room Neo4j graph (tasks 6.2-6.7).

Neo4j holds a projection of Postgres: everything here can be rebuilt from Postgres at any time
(`project_room` wipes and rewrites a room's subgraph), which is how `GET /graph` recovers if
Neo4j was reset.
"""

import contextlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import structlog
from neo4j import AsyncDriver, AsyncManagedTransaction
from neo4j.exceptions import ClientError

from orbit.modules.graph import clusters, layout
from orbit.modules.graph.edges import select_edges
from orbit.modules.graph.schemas import EdgeReason, Follow, GraphEdge, GraphNode, GraphView

log = structlog.get_logger("orbit.graph")


@dataclass(frozen=True)
class PersonIn:
    id: UUID
    name: str
    avatar_url: str | None = None


@dataclass(frozen=True)
class ScoreIn:
    a: UUID
    b: UUID
    total: float
    answers: float | None = None
    reactions: float | None = None
    roots: float | None = None
    social: float | None = None
    reasons: list[dict[str, Any]] = field(default_factory=list)


async def _write_room(
    tx: AsyncManagedTransaction,
    room: str,
    people: list[dict[str, Any]],
    places: list[dict[str, str]],
    reacted: list[dict[str, str]],
    follows: list[dict[str, str]],
    edges: list[dict[str, Any]],
) -> None:
    await tx.run("MATCH (n {room: $room}) DETACH DELETE n", room=room)
    await tx.run(
        "UNWIND $people AS p "
        "CREATE (:Person {room: $room, id: p.id, name: p.name, avatar_url: p.avatar_url})",
        room=room,
        people=people,
    )
    # Shared Place = shared history (design: Data model). Never returned by any endpoint.
    await tx.run(
        """
        UNWIND $places AS pl
        MATCH (p:Person {room: $room, id: pl.person})
        MERGE (x:Place {room: $room, city: pl.city})
        CREATE (p)-[:FROM]->(x)
        """,
        room=room,
        places=places,
    )
    await tx.run(
        """
        UNWIND $reacted AS r
        MATCH (p:Person {room: $room, id: r.person})
        MERGE (c:Content {room: $room, id: r.content})
        CREATE (p)-[:REACTED {type: r.type}]->(c)
        """,
        room=room,
        reacted=reacted,
    )
    await tx.run(
        """
        UNWIND $follows AS f
        MATCH (a:Person {room: $room, id: f.from}), (b:Person {room: $room, id: f.to})
        MERGE (a)-[:FOLLOWS]->(b)
        """,
        room=room,
        follows=follows,
    )
    await tx.run(
        """
        UNWIND $edges AS e
        MATCH (a:Person {room: $room, id: e.a}), (b:Person {room: $room, id: e.b})
        CREATE (a)-[:CLOSE_TO {total: e.total, answers: e.answers, reactions: e.reactions,
                               roots: e.roots, social: e.social, reasons: e.reasons}]->(b)
        """,
        room=room,
        edges=edges,
    )


GDS_PROJECT = """
MATCH (a:Person {room: $room})-[r:CLOSE_TO]->(b:Person {room: $room})
WITH gds.graph.project($name, a, b, {relationshipProperties: r {.total}},
                       {undirectedRelationshipTypes: ['*']}) AS g
RETURN g.graphName AS graph
"""
GDS_LOUVAIN = """
CALL gds.louvain.stream($name, {relationshipWeightProperty: 'total'})
YIELD nodeId, communityId
RETURN gds.util.asNode(nodeId).id AS id, communityId
"""


async def _gds_louvain(driver: AsyncDriver, room: str) -> dict[UUID, int] | None:
    """Louvain via Neo4j Graph Data Science. None if GDS isn't installed (e.g. Aura Free)."""
    name = f"orbit-{room}-{uuid4().hex[:8]}"
    try:
        async with driver.session() as s:
            await (await s.run(GDS_PROJECT, room=room, name=name)).consume()
            result = await s.run(GDS_LOUVAIN, name=name)
            rows = [r async for r in result]
    except ClientError as e:
        log.info("graph.gds_unavailable", error=e.code)
        return None
    finally:
        with contextlib.suppress(Exception):
            async with driver.session() as s:
                await (await s.run("CALL gds.graph.drop($name, false)", name=name)).consume()
    return {UUID(r["id"]): int(r["communityId"]) for r in rows}


async def project_room(
    driver: AsyncDriver,
    room: str,
    people: list[PersonIn],
    scores: list[ScoreIn],
    *,
    follows: Iterable[tuple[UUID, UUID]] = (),
    reactions: dict[UUID, dict[UUID, str]] | None = None,
    places: dict[UUID, set[str]] | None = None,
    threshold: float,
    top_k: int,
    use_gds: bool = True,
) -> GraphView:
    """(Re)write the room's subgraph, pick edges, find communities. Idempotent."""
    chosen = select_edges(((s.a, s.b, s.total) for s in scores), threshold=threshold, top_k=top_k)
    edge_rows = [
        {
            "a": str(s.a),
            "b": str(s.b),
            "total": s.total,
            "answers": s.answers,
            "reactions": s.reactions,
            "roots": s.roots,
            "social": s.social,
            "reasons": json.dumps(s.reasons),
        }
        for s in scores
        if (min(s.a, s.b, key=str), max(s.a, s.b, key=str)) in chosen
    ]
    async with driver.session() as session:
        await session.execute_write(
            _write_room,
            room,
            [{"id": str(p.id), "name": p.name, "avatar_url": p.avatar_url} for p in people],
            [
                {"person": str(u), "city": c}
                for u, cities in (places or {}).items()
                for c in sorted(cities)
            ],
            [
                {"person": str(u), "content": str(c), "type": t}
                for u, per in (reactions or {}).items()
                for c, t in per.items()
            ],
            [{"from": str(a), "to": str(b)} for a, b in follows],
            edge_rows,
        )

    communities = None
    if use_gds and edge_rows:
        communities = await _gds_louvain(driver, room)
    if communities is None:
        communities = clusters.louvain(
            [p.id for p in people], [(UUID(e["a"]), UUID(e["b"]), e["total"]) for e in edge_rows]
        )
    # People without any drawn edge get their own community.
    next_label = max(communities.values(), default=-1) + 1
    for p in people:
        if p.id not in communities:
            communities[p.id] = next_label
            next_label += 1
    labels = clusters.relabel(communities)
    # Place planets from every pair's score (not only drawn edges): closer = more similar.
    coords = layout.positions(
        [p.id for p in people], {frozenset((s.a, s.b)): s.total for s in scores}
    )
    async with driver.session() as session:
        await session.run(
            "UNWIND $rows AS r MATCH (p:Person {room: $room, id: r.id}) "
            "SET p.community = r.c, p.x = r.x, p.y = r.y, p.z = r.z",
            room=room,
            rows=[
                {"id": str(k), "c": v, "x": coords[k][0], "y": coords[k][1], "z": coords[k][2]}
                for k, v in labels.items()
            ],
        )
    log.info("graph.projected", room=room, people=len(people), edges=len(edge_rows))
    view = await read_graph(driver, room)
    if view is None:  # we just wrote the people, so this means Neo4j lost the write
        raise RuntimeError(f"projection of room {room} is missing after write")
    return view


async def read_graph(driver: AsyncDriver, room: str) -> GraphView | None:
    """The room's graph, or None if Neo4j has no projection for it (rebuild from Postgres)."""
    async with driver.session() as s:
        nodes = [
            r
            async for r in await s.run(
                "MATCH (p:Person {room: $room}) RETURN p.id AS id, p.name AS name, "
                "p.avatar_url AS avatar_url, coalesce(p.community, 0) AS community, "
                "coalesce(p.x, 0.0) AS x, coalesce(p.y, 0.0) AS y, coalesce(p.z, 0.0) AS z "
                "ORDER BY p.name",
                room=room,
            )
        ]
        if not nodes:
            return None
        edges = [
            r
            async for r in await s.run(
                "MATCH (a:Person {room: $room})-[r:CLOSE_TO]->(b:Person {room: $room}) "
                "RETURN a.id AS a, b.id AS b, r ORDER BY r.total DESC",
                room=room,
            )
        ]
        follows = [
            r
            async for r in await s.run(
                "MATCH (a:Person {room: $room})-[:FOLLOWS]->(b:Person {room: $room}) "
                "RETURN a.id AS a, b.id AS b",
                room=room,
            )
        ]
    return GraphView(
        room_code=room,
        nodes=[GraphNode(**dict(n)) for n in nodes],
        edges=[
            GraphEdge(
                a=e["a"],
                b=e["b"],
                total=e["r"]["total"],
                answers=e["r"].get("answers"),
                reactions=e["r"].get("reactions"),
                roots=e["r"].get("roots"),
                social=e["r"].get("social"),
                reasons=[EdgeReason(**x) for x in json.loads(e["r"].get("reasons") or "[]")],
            )
            for e in edges
        ],
        follows=[Follow(from_user=f["a"], to_user=f["b"]) for f in follows],
    )


async def add_follow(driver: AsyncDriver, room: str, from_user: UUID, to_user: UUID) -> None:
    async with driver.session() as s:
        await s.run(
            "MATCH (a:Person {room: $room, id: $a}), (b:Person {room: $room, id: $b}) "
            "MERGE (a)-[:FOLLOWS]->(b)",
            room=room,
            a=str(from_user),
            b=str(to_user),
        )


async def remove_person(driver: AsyncDriver, room: str, user_id: UUID) -> None:
    async with driver.session() as s:
        await s.run(
            "MATCH (p:Person {room: $room, id: $id}) DETACH DELETE p", room=room, id=str(user_id)
        )


async def remove_person_everywhere(driver: AsyncDriver, user_id: UUID) -> None:
    async with driver.session() as s:
        await s.run("MATCH (p:Person {id: $id}) DETACH DELETE p", id=str(user_id))


async def delete_room(driver: AsyncDriver, room: str) -> int:
    """Remove every node of the room (and its relationships). Returns how many nodes went."""
    async with driver.session() as s:
        result = await s.run(
            "MATCH (n {room: $room}) DETACH DELETE n RETURN count(n) AS n", room=room
        )
        record = await result.single()
    return int(record["n"]) if record else 0


async def count_room_nodes(driver: AsyncDriver, room: str) -> int:
    async with driver.session() as s:
        record = await (
            await s.run("MATCH (n {room: $room}) RETURN count(n) AS n", room=room)
        ).single()
    return int(record["n"]) if record else 0
