from datetime import timedelta

from fastapi import APIRouter, HTTPException, Response, status

from orbit.core import events, ratelimit
from orbit.core.config import SettingsDep
from orbit.core.db import SessionDep
from orbit.core.jobs import JobsDep
from orbit.core.redis import RedisDep
from orbit.modules.accounts.deps import ConsentedUserDep
from orbit.modules.game import service as game
from orbit.modules.graph import service as graph
from orbit.modules.graph.driver import Neo4jDep
from orbit.modules.rooms import service
from orbit.modules.rooms.deps import HostRoomDep, MemberRoomDep, RoomDep
from orbit.modules.rooms.schemas import Kick, RoomView, Started
from orbit.modules.rooms.state import RoomState

router = APIRouter(prefix="/rooms", tags=["rooms"])

NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "room_not_found")


async def _row(session: SessionDep, code: str):
    room = await service.get_room(session, code)
    if room is None:
        raise NOT_FOUND
    return room


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_room(
    user: ConsentedUserDep,
    session: SessionDep,
    redis: RedisDep,
    jobs: JobsDep,
    settings: SettingsDep,
) -> RoomView:
    """Create a room; you are its host (task 3.1). The host joins as a player separately."""
    await ratelimit.enforce(
        redis, f"rooms:{user.id}", limit=settings.rooms_per_host_per_day, window_seconds=86_400
    )
    room = await service.create(session, user.id, settings)
    await jobs.enqueue(
        "warn_room_closing",
        room.code,
        job_id=f"closing:{room.code}",
        defer_until=room.expires_at - timedelta(hours=1),
    )
    return await service.view(session, room, user.id, settings)


@router.get("/{code}")
async def get_room(
    room: RoomDep, user: ConsentedUserDep, session: SessionDep, settings: SettingsDep
) -> RoomView:
    return await service.view(session, await _row(session, room.code), user.id, settings)


@router.post(
    "/{code}/join",
    responses={
        403: {"description": "kicked from this room"},
        409: {"description": "room_full or round_over"},
        429: {"description": "rate_limited"},
    },
)
async def join_room(
    room: RoomDep,
    user: ConsentedUserDep,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> RoomView:
    """Join (task 3.3). Idempotent for existing members. Late joiners can join mid-round."""
    await ratelimit.enforce(
        redis, f"join:{user.id}", limit=settings.joins_per_minute, window_seconds=60
    )
    row = await _row(session, room.code)
    try:
        added = await service.join(session, redis, row, user.id, settings)
    except service.RoomClosedError:
        raise HTTPException(status.HTTP_409_CONFLICT, "round_over") from None
    except service.RoomFullError:
        raise HTTPException(status.HTTP_409_CONFLICT, "room_full") from None
    except service.KickedError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "kicked") from None
    if added:
        await events.publish(
            redis,
            room.code,
            events.MemberJoined(user_id=user.id, name=user.name, avatar=user.avatar_url),
        )
    await session.refresh(row)
    return await service.view(session, row, user.id, settings)


@router.post("/{code}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_room(
    room: MemberRoomDep,
    user: ConsentedUserDep,
    session: SessionDep,
    redis: RedisDep,
    jobs: JobsDep,
    driver: Neo4jDep,
) -> Response:
    """Leave and delete my data (task 3.8): answers, reactions, follows and scores go with it."""
    if await service.remove_member(session, room.code, user.id):
        await events.publish(redis, room.code, events.MemberLeft(user_id=user.id, reason="left"))
        await graph.remove_person(driver, room.code, user.id)
        await service.end_round_if_all_finished(session, redis, jobs, room.code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{code}/kick", status_code=status.HTTP_204_NO_CONTENT)
async def kick_member(
    body: Kick,
    room: HostRoomDep,
    session: SessionDep,
    redis: RedisDep,
    jobs: JobsDep,
    driver: Neo4jDep,
) -> Response:
    """Host removes a player (and their data); they cannot rejoin this room."""
    if await service.kick(session, redis, await _row(session, room.code), body.user_id):
        await events.publish(
            redis, room.code, events.MemberLeft(user_id=body.user_id, reason="kicked")
        )
        await graph.remove_person(driver, room.code, body.user_id)
        await service.end_round_if_all_finished(session, redis, jobs, room.code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{code}/start", responses={409: {"description": "not_ready"}})
async def start_round(
    room: HostRoomDep,
    session: SessionDep,
    redis: RedisDep,
    jobs: JobsDep,
    settings: SettingsDep,
) -> Started:
    """Start the 5-minute round (task 4.4): freeze the deck, tell everyone, schedule the end."""
    row = await _row(session, room.code)
    deck = await game.draw_deck(session, seed=f"{row.code}:{row.created_at.isoformat()}")
    try:
        ends_at = await service.start(session, row, deck, settings)
    except service.NotReadyError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, f"not_ready: {e}") from None
    await events.publish(redis, room.code, events.GameStarted(ends_at=ends_at))
    await jobs.enqueue("end_round", room.code, job_id=f"end:{room.code}", defer_until=ends_at)
    return Started(ends_at=ends_at)


@router.post("/{code}/finish", status_code=status.HTTP_204_NO_CONTENT)
async def finish(
    room: MemberRoomDep,
    user: ConsentedUserDep,
    session: SessionDep,
    redis: RedisDep,
    jobs: JobsDep,
) -> Response:
    """I'm done with my deck (task 4.8). The last finisher ends the round early (4.9)."""
    if room.state != RoomState.PLAYING:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    finished, total = await service.mark_finished(session, room.code, user.id)
    await events.publish(redis, room.code, events.Progress(finished=finished, total=total))
    if finished == total:
        await service.end_round(session, redis, jobs, room.code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
