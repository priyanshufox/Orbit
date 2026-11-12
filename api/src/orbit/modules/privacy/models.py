"""Persistent: each player's graph snapshot, written just before a room expires."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from orbit.core.db import Base, uuid_pk


class GraphSnapshot(Base):
    __tablename__ = "graph_snapshots"

    id: Mapped[UUID] = uuid_pk()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Plain text, not a foreign key: the room row is deleted at expiry but the snapshot stays.
    room_code: Mapped[str] = mapped_column(String(6))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Own ego graph + scores, re-renderable by the history page (task 8.4).
    graph: Mapped[dict[str, Any]] = mapped_column(JSONB)
