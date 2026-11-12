"""Game data.

Persistent: `questions` (the bank). Ephemeral (deleted with the room or the member): answers,
reactions, social. Room-scoped rows reference `room_members`, never `rooms` directly.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from orbit.core.db import Base, uuid_pk

QUESTION_KINDS = ("single", "multi", "slider")
REACTIONS = ("like", "laugh", "skip", "send")
SOCIAL_KINDS = ("follow", "like_profile")


def _member_fk(user_column: str) -> ForeignKeyConstraint:
    """(user, room) -> room_members; user column first so constraint names stay unique."""
    return ForeignKeyConstraint(
        [user_column, "room_code"],
        ["room_members.user_id", "room_members.room_code"],
        ondelete="CASCADE",
    )


class Question(Base):
    """`options`: {"choices": [...]} for single/multi, {"min_label", "max_label"} for slider."""

    __tablename__ = "questions"

    id: Mapped[UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(16))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[dict[str, Any]] = mapped_column(JSONB)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (CheckConstraint(f"kind in {QUESTION_KINDS}", name="kind"),)


class Answer(Base):
    __tablename__ = "answers"

    room_code: Mapped[str] = mapped_column(String(6), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    # single: {"choice": i}; multi: {"choices": [i, ...]}; slider: {"value": 0..1}
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)

    __table_args__ = (_member_fk("user_id"),)


class Reaction(Base):
    __tablename__ = "reactions"

    room_code: Mapped[str] = mapped_column(String(6), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    content_id: Mapped[UUID] = mapped_column(ForeignKey("content.id"), primary_key=True)
    reaction: Mapped[str] = mapped_column(String(16))

    __table_args__ = (
        _member_fk("user_id"),
        CheckConstraint(f"reaction in {REACTIONS}", name="reaction"),
    )


class Social(Base):
    """A follow or profile like from one member to another in the same room."""

    __tablename__ = "social"

    room_code: Mapped[str] = mapped_column(String(6), primary_key=True)
    from_user: Mapped[UUID] = mapped_column(primary_key=True)
    to_user: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        _member_fk("from_user"),
        _member_fk("to_user"),
        CheckConstraint(f"kind in {SOCIAL_KINDS}", name="kind"),
        CheckConstraint("from_user <> to_user", name="not_self"),
    )
