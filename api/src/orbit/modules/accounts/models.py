"""Persistent: users and their optional roots. Survive room expiry; removed by DELETE /me.

Sign-in identity lives in `auth.user`, owned by Better Auth in the web app (tables created by
migration 3). An Orbit `users` row is created only after the age gate, with the same id, and is
deleted with the identity.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Table,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from orbit.core.db import Base, created_at

ROOT_KINDS = ("birth", "school", "childhood")
MAX_CHILDHOOD_CITIES = 3

AUTH_SCHEMA = "auth"

# Read-mostly view of Better Auth's identity table (only the columns Orbit uses). Its schema is
# managed by migration 3, not by autogenerate (migrations/env.py skips the auth schema).
auth_user = Table(
    "user",
    Base.metadata,
    Column("id", Uuid, primary_key=True),
    Column("email", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("image", Text),
    Column("emailVerified", Boolean, nullable=False),
    schema=AUTH_SCHEMA,
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        ForeignKey(auth_user.c.id, ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    # Under-18s never get a row (age gate, task 2.6), so is_adult is true for every stored user;
    # it is kept so the invariant is checkable in the data.
    birth_year: Mapped[int] = mapped_column(SmallInteger)
    is_adult: Mapped[bool]
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Picked at sign-up from accounts.hobbies.HOBBIES; feeds the answers signal and edge reasons.
    hobbies: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list, server_default=text("'{}'")
    )
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
