"""Rooms: lifecycle, membership and the round timer.

State changes are compare-and-set UPDATEs (`... WHERE state IN (allowed sources)`), so two
racing requests (timer job vs. last player finishing) cannot both move the room.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core import events
from orbit.core.config import Settings
from orbit.core.jobs import JobQueue
from orbit.modules.accounts import service as accounts
from orbit.modules.rooms import codes
from orbit.modules.rooms.models import Room, RoomMember
from orbit.modules.rooms.schemas import Member, RoomView
from orbit.modules.rooms.state import JOINABLE, RoomState, sources_for

log = structlog.get_logger("orbit.rooms")

MIN_PLAYERS = 2


class RoomNotFoundError(Exception):
    pass


class RoomClosedError(Exception):
    """The round is over; nobody new can join."""


class RoomFullError(Exception):
    pass


class KickedError(Exception):
    pass


class NotReadyError(Exception):
    """Start needs the lobby state and at least two players."""


@dataclass(frozen=True)
class RoomContext:
    """What other modules may know about a room (never the ORM object)."""

    code: str
    state: RoomState
    host_id: UUID | None
    started_at: datetime | None
    ends_at: datetime | None
    expires_at: datetime
    deck: dict[str, Any] | None
    is_host: bool
    is_member: bool


def _now() -> datetime:
    return datetime.now(UTC)


def kicked_key(code: str) -> str:
    return f"room:{code}:kicked"


async def get_room(session: AsyncSession, code: str) -> Room | None:
    return await session.get(Room, code)


async def is_member(session: AsyncSession, code: str, user_id: UUID) -> bool:
    return await session.get(RoomMember, (code, user_id)) is not None


async def context(session: AsyncSession, code: str, user_id: UUID) -> RoomContext:
    room = await get_room(session, code)
    if room is None:
        raise RoomNotFoundError
    return RoomContext(
        code=room.code,
        state=RoomState(room.state),
        host_id=room.host_id,
        started_at=room.started_at,
        ends_at=room.ends_at,
        expires_at=room.expires_at,
        deck=room.deck,
        is_host=room.host_id == user_id,
        is_member=await is_member(session, code, user_id),
    )


async def member_rows(session: AsyncSession, code: str) -> list[RoomMember]:
    stmt = select(RoomMember).where(RoomMember.room_code == code).order_by(RoomMember.joined_at)
    return list((await session.scalars(stmt)).all())


async def member_ids(session: AsyncSession, code: str) -> list[UUID]:
    return [m.user_id for m in await member_rows(session, code)]


async def members(session: AsyncSession, code: str) -> list[Member]:
    rows = await member_rows(session, code)
    profiles = await accounts.public_profiles(session, [m.user_id for m in rows])
    return [
        Member(
            user_id=m.user_id,
            name=profiles[m.user_id].name if m.user_id in profiles else "Player",
            avatar_url=profiles[m.user_id].avatar_url if m.user_id in profiles else None,
            finished=m.finished_at is not None,
        )
        for m in rows
    ]


async def view(session: AsyncSession, room: Room, user_id: UUID, settings: Settings) -> RoomView:
    member_list = await members(session, room.code)
    return RoomView(
        code=room.code,
        state=RoomState(room.state),
        host_id=room.host_id,
        is_host=room.host_id == user_id,
        is_member=any(m.user_id == user_id for m in member_list),
        member_cap=settings.room_member_cap,
        started_at=room.started_at,
        ends_at=room.ends_at,
        expires_at=room.expires_at,
        members=member_list,
    )


async def move(session: AsyncSession, code: str, target: RoomState, **values: Any) -> bool:
    """Compare-and-set state change. True if this call moved the room."""
    stmt = (
        update(Room)
        .where(Room.code == code, Room.state.in_([s.value for s in sources_for(target)]))
        .values(state=target.value, **values)
        .returning(Room.code)
    )
    moved = (await session.execute(stmt)).first() is not None
    await session.commit()
    if moved:
        log.info("room.state", room=code, state=target.value)
    return moved


# --- Create / join / leave -------------------------------------------------------------------


async def create(session: AsyncSession, host_id: UUID, settings: Settings) -> Room:
    expires_at = _now() + timedelta(hours=settings.room_ttl_hours)
    for _ in range(8):
        room = Room(code=codes.new_code(), host_id=host_id, expires_at=expires_at)
        session.add(room)
        try:
            await session.commit()
        except IntegrityError:  # code collision; try another
            await session.rollback()
            continue
        log.info("room.created", room=room.code)
        return room
    raise RuntimeError("could not allocate a room code")


async def join(
    session: AsyncSession, redis: Redis, room: Room, user_id: UUID, settings: Settings
) -> bool:
    """Add the user to the room. Returns False if they were already a member."""
    if await is_member(session, room.code, user_id):
        return False
    if RoomState(room.state) not in JOINABLE:
        raise RoomClosedError
    if await redis.sismember(kicked_key(room.code), str(user_id)):
        raise KickedError
    # Lock the room row so concurrent joins can't overshoot the cap.
    await session.execute(select(Room.code).where(Room.code == room.code).with_for_update())
    count = await session.scalar(
        select(func.count()).select_from(RoomMember).where(RoomMember.room_code == room.code)
    )
    if (count or 0) >= settings.room_member_cap:
        await session.rollback()
        raise RoomFullError
    session.add(RoomMember(room_code=room.code, user_id=user_id))
    await session.commit()
    if room.state == RoomState.CREATED:
        await move(session, room.code, RoomState.LOBBY)
    return True


async def remove_member(session: AsyncSession, code: str, user_id: UUID) -> bool:
    """Delete the membership and, by cascade, every answer, reaction, follow and score of it."""
    result = await session.execute(
        delete(RoomMember)
        .where(RoomMember.room_code == code, RoomMember.user_id == user_id)
        .returning(RoomMember.user_id)
    )
    removed = result.first() is not None
    await session.commit()
    return removed


async def kick(session: AsyncSession, redis: Redis, room: Room, user_id: UUID) -> bool:
    await redis.sadd(kicked_key(room.code), str(user_id))
    await redis.expireat(kicked_key(room.code), room.expires_at)
    return await remove_member(session, room.code, user_id)


# --- The round -------------------------------------------------------------------------------


async def start(
    session: AsyncSession, room: Room, deck: dict[str, Any], settings: Settings
) -> datetime:
    if RoomState(room.state) != RoomState.LOBBY:
        raise NotReadyError("not in lobby")
    if len(await member_ids(session, room.code)) < MIN_PLAYERS:
        raise NotReadyError("need at least two players")
    started = _now()
    ends_at = started + timedelta(seconds=settings.round_seconds)
    if not await move(
        session, room.code, RoomState.PLAYING, started_at=started, ends_at=ends_at, deck=deck
    ):
        raise NotReadyError("already started")
    return ends_at


async def progress(session: AsyncSession, code: str) -> tuple[int, int]:
    rows = await member_rows(session, code)
    return sum(1 for m in rows if m.finished_at is not None), len(rows)


async def mark_finished(session: AsyncSession, code: str, user_id: UUID) -> tuple[int, int]:
    await session.execute(
        update(RoomMember)
        .where(
            RoomMember.room_code == code,
            RoomMember.user_id == user_id,
            RoomMember.finished_at.is_(None),
        )
        .values(finished_at=_now())
    )
    await session.commit()
    return await progress(session, code)


async def end_round(session: AsyncSession, redis: Redis, jobs: JobQueue, code: str) -> bool:
    """PLAYING -> SCORING once (timer job and last finisher may both call), then queue scoring."""
    if not await move(session, code, RoomState.SCORING):
        return False
    await events.publish(redis, code, events.Scoring())
    await jobs.enqueue("score_room", code, job_id=f"score:{code}")
    return True


async def end_round_if_all_finished(
    session: AsyncSession, redis: Redis, jobs: JobQueue, code: str
) -> None:
    room = await get_room(session, code)
    if room is None or RoomState(room.state) != RoomState.PLAYING:
        return
    finished, total = await progress(session, code)
    if total > 0 and finished == total:
        await end_round(session, redis, jobs, code)


async def expired_codes(session: AsyncSession, now: datetime | None = None) -> list[str]:
    stmt = select(Room.code).where(Room.expires_at <= (now or _now()))
    return list((await session.scalars(stmt)).all())


async def delete_room(session: AsyncSession, code: str) -> None:
    """Hard delete; cascades to members and every room-scoped row."""
    await session.execute(delete(Room).where(Room.code == code))
    await session.commit()


async def rooms_hosted_by(session: AsyncSession, user_id: UUID) -> list[str]:
    return list((await session.scalars(select(Room.code).where(Room.host_id == user_id))).all())


async def rooms_of_member(session: AsyncSession, user_id: UUID) -> list[str]:
    stmt = select(RoomMember.room_code).where(RoomMember.user_id == user_id)
    return list((await session.scalars(stmt)).all())
