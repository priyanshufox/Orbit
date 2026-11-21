"""Schema behaviour: migrations, cascades and constraints (roadmap 1.2-1.4)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.accounts.models import User, UserRoot
from orbit.modules.content.models import Content
from orbit.modules.game.models import Answer, Question, Reaction, Social
from orbit.modules.privacy.models import GraphSnapshot
from orbit.modules.rooms.models import Room, RoomMember
from orbit.modules.scoring.models import Score
from tests.conftest import alembic_config, make_identity

ROOM_TABLES = [RoomMember, Answer, Reaction, Social, Score]


async def count(db: AsyncSession, model: type, **where: object) -> int:
    stmt = select(func.count()).select_from(model).filter_by(**where)
    return (await db.execute(stmt)).scalar_one()


async def make_user(db: AsyncSession, name: str) -> User:
    email = f"{name}-{uuid4().hex[:8]}@orbit.test"
    user_id = await make_identity(db, email, name)
    user = User(id=user_id, email=email, name=name, birth_year=2000, is_adult=True)
    db.add(user)
    await db.flush()
    return user


async def make_played_room(db: AsyncSession) -> tuple[Room, User, User]:
    """A room where two members answered, reacted, followed each other and got a score."""
    a, b = await make_user(db, "a"), await make_user(db, "b")
    q = Question(kind="single", prompt="Chai or coffee?", options={"choices": ["Chai", "Coffee"]})
    c = Content(type="fact", source="test", payload={"text": "x"}, tags=["food"], active=True)
    room = Room(
        code=uuid4().hex[:6].upper(),
        host_id=a.id,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    db.add_all([q, c, room])
    await db.flush()
    db.add_all([RoomMember(room_code=room.code, user_id=u.id) for u in (a, b)])
    await db.flush()
    lo, hi = sorted([a.id, b.id])
    db.add_all(
        [
            *(
                Answer(room_code=room.code, user_id=u.id, question_id=q.id, value={"choice": 0})
                for u in (a, b)
            ),
            *(
                Reaction(room_code=room.code, user_id=u.id, content_id=c.id, reaction="laugh")
                for u in (a, b)
            ),
            Social(room_code=room.code, from_user=a.id, to_user=b.id, kind="follow"),
            Social(room_code=room.code, from_user=b.id, to_user=a.id, kind="follow"),
            Score(room_code=room.code, user_a=lo, user_b=hi, total=Decimal("0.8123"), reasons=[]),
            GraphSnapshot(user_id=a.id, room_code=room.code, graph={"nodes": [], "edges": []}),
        ]
    )
    await db.flush()
    return room, a, b


def test_migrations_downgrade_and_upgrade(migrated_db: str) -> None:
    cfg = alembic_config(migrated_db)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


async def test_deleting_room_removes_all_room_data(db: AsyncSession) -> None:
    room, a, _ = await make_played_room(db)
    for model in ROOM_TABLES:
        assert await count(db, model, room_code=room.code) > 0, model.__tablename__

    await db.delete(room)
    await db.flush()

    for model in ROOM_TABLES:
        assert await count(db, model, room_code=room.code) == 0, model.__tablename__
    # Persistent data survives the room.
    assert await count(db, User, id=a.id) == 1
    assert await count(db, GraphSnapshot, room_code=room.code) == 1


async def test_removing_a_member_removes_only_their_room_data(db: AsyncSession) -> None:
    room, a, b = await make_played_room(db)
    await db.execute(
        text("delete from room_members where room_code = :r and user_id = :u"),
        {"r": room.code, "u": a.id},
    )

    assert await count(db, Answer, room_code=room.code, user_id=a.id) == 0
    assert await count(db, Reaction, room_code=room.code, user_id=a.id) == 0
    assert await count(db, Social, room_code=room.code) == 0  # both directions involved a
    assert await count(db, Score, room_code=room.code) == 0
    assert await count(db, Answer, room_code=room.code, user_id=b.id) == 1
    assert await count(db, Reaction, room_code=room.code, user_id=b.id) == 1


async def test_deleting_user_removes_roots_and_snapshots(db: AsyncSession) -> None:
    room, a, _ = await make_played_room(db)
    db.add(UserRoot(user_id=a.id, kind="birth", slot=0, city="mumbai"))
    await db.flush()

    await db.execute(text("delete from users where id = :u"), {"u": a.id})

    assert await count(db, UserRoot, user_id=a.id) == 0
    assert await count(db, GraphSnapshot, user_id=a.id) == 0
    # a hosted the room: it stays for the others, now without a host.
    remaining = await db.get(Room, room.code, populate_existing=True)
    assert remaining is not None
    assert remaining.host_id is None


async def test_deleting_sign_in_identity_removes_profile(db: AsyncSession) -> None:
    _, a, _ = await make_played_room(db)
    await db.execute(text('delete from auth."user" where id = :u'), {"u": a.id})
    assert await count(db, User, id=a.id) == 0
    assert await count(db, GraphSnapshot, user_id=a.id) == 0


async def _rejects(db: AsyncSession, *rows: object) -> None:
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            db.add_all(rows)
            await db.flush()


async def test_constraints(db: AsyncSession) -> None:
    room, a, b = await make_played_room(db)
    hi, lo = sorted([a.id, b.id], reverse=True)
    stranger: UUID = (await make_user(db, "stranger")).id

    kid_id = await make_identity(db, "kid@orbit.test", "kid")
    await _rejects(
        db, User(id=kid_id, email="kid@orbit.test", name="kid", birth_year=2012, is_adult=False)
    )
    await _rejects(
        db,
        User(
            id=uuid4(), email="ghost@orbit.test", name="no identity", birth_year=2000, is_adult=True
        ),
    )
    await _rejects(db, UserRoot(user_id=a.id, kind="childhood", slot=4, city="pune"))
    await _rejects(db, UserRoot(user_id=a.id, kind="birth", slot=0, city="pune", school="x"))
    await _rejects(db, Social(room_code=room.code, from_user=a.id, to_user=a.id, kind="follow"))
    await _rejects(db, Social(room_code=room.code, from_user=a.id, to_user=stranger, kind="follow"))
    await _rejects(db, Score(room_code=room.code, user_a=hi, user_b=lo, total=Decimal("0.5")))
    await _rejects(db, Score(room_code=room.code, user_a=lo, user_b=hi, total=Decimal("1.5")))
    await _rejects(db, Content(type="video", source="t", payload={}, tags=["food"]))
    await _rejects(db, Content(type="fact", source="t", payload={}, tags=[]))
