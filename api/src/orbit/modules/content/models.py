"""Persistent: the content bank that every room's deck draws from. Filled by the daily curator."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from orbit.core.db import Base, uuid_pk

CONTENT_TYPES = ("fact", "meme", "news")


class Content(Base):
    __tablename__ = "content"

    id: Mapped[UUID] = uuid_pk()
    type: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32))  # facts-bank | imgflip | newsdata | dev-seed
    source_url: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    # Only items that passed moderation are active (task 9.5).
    active: Mapped[bool] = mapped_column(default=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"type in {CONTENT_TYPES}", name="type"),
        CheckConstraint("cardinality(tags) between 1 and 3", name="tag_count"),
    )
