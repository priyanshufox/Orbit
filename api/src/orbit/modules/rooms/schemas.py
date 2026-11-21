from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from orbit.modules.rooms.state import RoomState


class Member(BaseModel):
    user_id: UUID
    name: str
    avatar_url: str | None
    finished: bool


class RoomView(BaseModel):
    code: str
    state: RoomState
    host_id: UUID | None
    is_host: bool
    is_member: bool
    member_cap: int
    started_at: datetime | None
    ends_at: datetime | None
    expires_at: datetime
    members: list[Member]


class Kick(BaseModel):
    user_id: UUID


class Started(BaseModel):
    ends_at: datetime
