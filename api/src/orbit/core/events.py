"""Realtime event bus (ADR 0001 rule 6).

Every server → client WebSocket event is one of the models below, published to the Redis
channel `room:{code}` with `publish()`. Any API or worker process can publish; the process
holding a player's socket delivers it (task 3.5). Modules never touch sockets directly.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from redis.asyncio import Redis


class _Event(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)


class MemberJoined(_Event):
    type: Literal["member_joined"] = "member_joined"
    user_id: UUID
    name: str
    avatar: str | None = None


class GameStarted(_Event):
    type: Literal["game_started"] = "game_started"
    ends_at: datetime


class Progress(_Event):
    type: Literal["progress"] = "progress"
    finished: int
    total: int


class Scoring(_Event):
    type: Literal["scoring"] = "scoring"


class Reveal(_Event):
    type: Literal["reveal"] = "reveal"
    graph_url: str


class SocialAdded(_Event):
    type: Literal["social_added"] = "social_added"
    from_user: UUID = Field(alias="from")
    to_user: UUID = Field(alias="to")
    kind: Literal["follow", "like_profile"]


class RoomClosing(_Event):
    type: Literal["room_closing"] = "room_closing"
    expires_at: datetime


RoomEvent = Annotated[
    MemberJoined | GameStarted | Progress | Scoring | Reveal | SocialAdded | RoomClosing,
    Field(discriminator="type"),
]

_adapter: TypeAdapter[RoomEvent] = TypeAdapter(RoomEvent)


def channel(room_code: str) -> str:
    return f"room:{room_code}"


def dump(event: RoomEvent) -> str:
    """Wire format: JSON with `type` plus the payload fields from the design's WebSocket table."""
    return event.model_dump_json(by_alias=True)


def parse(raw: str | bytes) -> RoomEvent:
    return _adapter.validate_json(raw)


async def publish(redis: Redis, room_code: str, event: RoomEvent) -> int:
    """Send an event to everyone in the room. Returns how many subscribers received it."""
    return await redis.publish(channel(room_code), dump(event))
