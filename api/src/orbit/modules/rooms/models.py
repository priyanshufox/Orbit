"""Ephemeral: rooms and their members. Deleting a room cascades to every room-scoped row.

Answers, reactions, social and scores reference `room_members (room_code, user_id)`, so
removing one member (leave / kick / "delete my data") also removes that player's room data.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from orbit.core.db import Base, created_at

ROOM_STATES = ("CREATED", "LOBBY", "PLAYING", "SCORING", "REVEALED", "EXPIRED")


class Room(Base):
    __tablename__ = "rooms"

    code: Mapped[str] = mapped_column(String(6), primary_key=True)
    # SET NULL: a host deleting their account must not wipe everyone else's room.
    host_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    state: Mapped[str] = mapped_column(String(16), default="CREATED")
    created_at: Mapped[datetime] = created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Frozen at start so every member (and late joiners) get the same cards even if the content
    # bank changes mid-round: {"questions": [uuid, ...], "content": [uuid, ...]}.
    deck: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (CheckConstraint(f"state in {ROOM_STATES}", name="state"),)


class RoomMember(Base):
    __tablename__ = "room_members"

    room_code: Mapped[str] = mapped_column(
        ForeignKey("rooms.code", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
