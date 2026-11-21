"""Cross-module flows, run by the worker and a few routes. Every step goes through a module's
service (ADR 0001 rule 2); nothing here touches a table directly.

  reveal          SCORING -> score every pair -> project to Neo4j -> REVEALED + `reveal` event
  graph_for       the reveal graph, rebuilt from Postgres if Neo4j lost it (task 6.7)
  expire          snapshot each member's ego graph -> delete the room in both stores -> audit
  delete_account  DELETE /me: remove from Neo4j, delete identity (cascades), audit
"""

from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core import events
from orbit.core.config import Settings
from orbit.modules.accounts import service as accounts
from orbit.modules.game import service as game
from orbit.modules.graph import service as graph
from orbit.modules.graph.driver import GraphDriver
from orbit.modules.graph.schemas import GraphView
from orbit.modules.privacy import service as privacy
from orbit.modules.rooms import service as rooms
from orbit.modules.rooms.state import RoomState
from orbit.modules.scoring import domain
from orbit.modules.scoring import service as scoring

log = structlog.get_logger("orbit.pipeline")


async def score(session: AsyncSession, code: str, settings: Settings) -> list[domain.PairScore]:
    members = await rooms.member_ids(session, code)
    data = await game.round_data(session, code)
    roots = await accounts.normalised_roots(session, members)
    hobbies = await accounts.hobbies_for(session, members)
    players = [
        domain.Player(
            user_id=m,
            answers=dict(data.answers.get(m, {})),
            reactions=dict(data.reactions.get(m, {})),
            roots=domain.RootsInfo(
                birth_city=roots[m].birth_city,
                school=roots[m].school,
                childhood=roots[m].childhood,
            ),
            hobbies=hobbies.get(m, frozenset()),
        )
        for m in members
    ]
    questions = {
        q: domain.QuestionInfo(kind=kind, prompt=prompt, choices=tuple(choices))
        for q, (kind, prompt, choices) in data.questions.items()
    }
    content_types = {c: t for c, (t, _) in data.content.items()}
    pairs = domain.score_room(
        players, questions, content_types, data.social, reaction_values=settings.reaction_values
    )
    await scoring.write_scores(session, code, pairs)
    log.info("round.scored", room=code, players=len(players), pairs=len(pairs))
    return pairs


async def project(
    session: AsyncSession, driver: GraphDriver, code: str, settings: Settings
) -> GraphView:
    member_list = await rooms.members(session, code)
    ids = [m.user_id for m in member_list]
    data = await game.round_data(session, code)
    roots = await accounts.normalised_roots(session, ids)
    places = {
        uid: {c for c in [r.birth_city, r.school[1] if r.school else None, *r.childhood] if c}
        for uid, r in roots.items()
    }
    return await graph.project_room(
        driver,
        code,
        [graph.PersonIn(id=m.user_id, name=m.name, avatar_url=m.avatar_url) for m in member_list],
        [graph.ScoreIn(**s) for s in await scoring.get_scores(session, code)],
        follows=[(a, b) for a, b, kind in data.social if kind == "follow"],
        reactions={u: dict(r) for u, r in data.reactions.items()},
        places=places,
        threshold=settings.edge_threshold,
        top_k=settings.edges_always_shown,
        use_gds=settings.graph_use_gds,
    )


async def reveal(
    session: AsyncSession, redis: Redis, driver: GraphDriver, code: str, settings: Settings
) -> bool:
    room = await rooms.get_room(session, code)
    if room is None or RoomState(room.state) != RoomState.SCORING:
        return False
    await score(session, code, settings)
    await project(session, driver, code, settings)
    if not await rooms.move(session, code, RoomState.REVEALED):
        return False
    await events.publish(redis, code, events.Reveal(graph_url=f"/rooms/{code}/graph"))
    log.info("round.revealed", room=code)
    return True


async def graph_for(
    session: AsyncSession, driver: GraphDriver, code: str, settings: Settings
) -> GraphView | None:
    view = await graph.read_graph(driver, code)
    if view is None and await scoring.has_scores(session, code):
        log.warning("graph.rebuilding_from_postgres", room=code)
        view = await project(session, driver, code, settings)
    return view


async def expire(
    session: AsyncSession, driver: GraphDriver, code: str, settings: Settings
) -> dict[str, int] | None:
    room = await rooms.get_room(session, code)
    if room is None:
        return None
    members = await rooms.member_ids(session, code)
    snapshots = 0
    if RoomState(room.state) == RoomState.REVEALED:
        view = await graph_for(session, driver, code, settings)
        if view is not None:
            snapshots = await privacy.write_snapshots(session, view, members)
    await rooms.delete_room(session, code)
    nodes = await graph.delete_room(driver, code)
    detail = {"room": code, "members": len(members), "snapshots": snapshots, "graph_nodes": nodes}
    await privacy.audit(session, "room_expired", detail)
    log.info("room.expired", **detail)
    return detail


async def expire_due(session: AsyncSession, driver: GraphDriver, settings: Settings) -> list[str]:
    done = []
    for code in await rooms.expired_codes(session):
        try:
            await expire(session, driver, code, settings)
            done.append(code)
        except Exception:
            log.exception("room.expire_failed", room=code)
            await session.rollback()
    return done


async def delete_account(
    session: AsyncSession, redis: Redis, driver: GraphDriver, user_id: UUID
) -> None:
    codes = await rooms.rooms_of_member(session, user_id)
    await graph.remove_person_everywhere(driver, user_id)
    await accounts.delete_identity(session, user_id)
    for code in codes:
        await events.publish(redis, code, events.MemberLeft(user_id=user_id, reason="left"))
    await privacy.audit(session, "account_deleted", {"rooms_left": len(codes)})
