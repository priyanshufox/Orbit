"""Persistent: users and their optional roots. Survive room expiry; removed by DELETE /me."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from orbit.core.db import Base, created_at, uuid_pk

ROOT_KINDS = ("birth", "school", "childhood")
MAX_CHILDHOOD_CITIES = 3


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    # Under-18s never get a row (age gate, task 2.6), so is_adult is true for every stored user;
    # it is kept so the invariant is checkable in the data.
    birth_year: Mapped[int] = mapped_column(SmallInteger)
    is_adult: Mapped[bool]
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()

    __table_args__ = (CheckConstraint("is_adult", name="adult_only"),)


class UserRoot(Base):
    """One row per root. Birth and school use slot 0; childhood cities use slots 1-3."""

    __tablename__ = "user_roots"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    slot: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=0)
    city: Mapped[str] = mapped_column(String(120))
    school: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        CheckConstraint(f"kind in {ROOT_KINDS}", name="kind"),
        CheckConstraint(
            f"(kind in ('birth', 'school') and slot = 0)"
            f" or (kind = 'childhood' and slot between 1 and {MAX_CHILDHOOD_CITIES})",
            name="slot",
        ),
        CheckConstraint("(kind = 'school') = (school is not null)", name="school_only_for_school"),
    )
