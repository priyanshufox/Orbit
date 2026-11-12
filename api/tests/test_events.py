import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from redis.asyncio import Redis

from orbit.core import events
from orbit.core.events import (
    GameStarted,
    MemberJoined,
    Progress,
    Reveal,
    RoomClosing,
    Scoring,
    SocialAdded,
)

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)

ALL_EVENTS = [
    MemberJoined(user_id=uuid4(), name="Diya", avatar=None),
    GameStarted(ends_at=NOW),
    Progress(finished=3, total=8),
    Scoring(),
    Reveal(graph_url="/rooms/ABC123/graph"),
    SocialAdded(from_user=uuid4(), to_user=uuid4(), kind="follow"),
    RoomClosing(expires_at=NOW),
]


@pytest.mark.parametrize("event", ALL_EVENTS, ids=lambda e: e.type)
def test_round_trip(event: events.RoomEvent) -> None:
    assert events.parse(events.dump(event)) == event


def test_wire_format_matches_design() -> None:
    a, b = uuid4(), uuid4()
    raw = events.dump(SocialAdded(from_user=a, to_user=b, kind="like_profile"))
    assert raw == f'{{"type":"social_added","from":"{a}","to":"{b}","kind":"like_profile"}}'


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValidationError):
        events.parse('{"type":"nope"}')


async def test_publish_reaches_subscriber(redis: Redis) -> None:
    code = uuid4().hex[:6].upper()
    pubsub = redis.pubsub()
    await pubsub.subscribe(events.channel(code))
    await pubsub.get_message(timeout=1)  # subscribe confirmation

    sent = Progress(finished=1, total=2)
    receivers = await events.publish(redis, code, sent)

    msg = None
    for _ in range(20):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if msg:
            break
        await asyncio.sleep(0.05)
    await pubsub.aclose()

    assert receivers == 1
    assert msg is not None
    assert events.parse(msg["data"]) == sent
