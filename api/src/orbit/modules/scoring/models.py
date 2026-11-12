"""Ephemeral: pairwise closeness scores for a room, written by the scoring job (task 5.7).

One row per unordered pair, stored with user_a < user_b so score(A, B) = score(B, A) holds by
construction. A sub-score is NULL when that signal was skipped for the pair.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from orbit.core.db import Base

Score01 = Numeric(5, 4)  # 0.0000 - 1.0000


def _member_fk(user_column: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        [user_column, "room_code"],
        ["room_members.user_id", "room_members.room_code"],
        ondelete="CASCADE",
    )


class Score(Base):
    __tablename__ = "scores"

    room_code: Mapped[str] = mapped_column(String(6), primary_key=True)
    user_a: Mapped[UUID] = mapped_column(primary_key=True)
    user_b: Mapped[UUID] = mapped_column(primary_key=True)
    answers: Mapped[Decimal | None] = mapped_column(Score01)
    reactions: Mapped[Decimal | None] = mapped_column(Score01)
    roots: Mapped[Decimal | None] = mapped_column(Score01)
    social: Mapped[Decimal | None] = mapped_column(Score01)
    total: Mapped[Decimal] = mapped_column(Score01)
    # Top contributing items for the tap-on-edge view (task 5.6). Never school or city names.
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    __table_args__ = (
        _member_fk("user_a"),
        _member_fk("user_b"),
        CheckConstraint("user_a < user_b", name="ordered_pair"),
        CheckConstraint("total between 0 and 1", name="total_range"),
    )
