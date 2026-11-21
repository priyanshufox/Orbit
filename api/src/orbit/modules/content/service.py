"""Content bank reads for other modules (the deck, scoring explanations)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.content.models import Content


@dataclass(frozen=True)
class Item:
    id: UUID
    type: str
    tags: tuple[str, ...]
    payload: dict[str, Any]
    source_url: str | None


def _item(c: Content) -> Item:
    return Item(
        id=c.id, type=c.type, tags=tuple(c.tags), payload=c.payload, source_url=c.source_url
    )


async def active_pool(session: AsyncSession) -> list[tuple[UUID, tuple[str, ...]]]:
    rows = (await session.execute(select(Content.id, Content.tags).where(Content.active))).all()
    return [(row.id, tuple(row.tags)) for row in rows]


async def items(session: AsyncSession, ids: list[UUID]) -> dict[UUID, Item]:
    if not ids:
        return {}
    rows = (await session.scalars(select(Content).where(Content.id.in_(ids)))).all()
    return {c.id: _item(c) for c in rows}
