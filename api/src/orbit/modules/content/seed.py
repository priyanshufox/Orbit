"""Load the facts bank (task 4.2) from data/facts.json. Safe in production; idempotent.

The bank is LLM-drafted; review it by hand before launch (design: Content pipeline).
"""

import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.content.models import Content
from orbit.modules.content.tags import TAGS

BANK = Path(__file__).parent / "data" / "facts.json"


def fact_id(text: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"orbit-fact:{text}")


def load_bank(path: Path = BANK) -> list[dict[str, Any]]:
    rows = []
    for fact in json.loads(path.read_text()):
        tags = fact["tags"]
        if not 1 <= len(tags) <= 3 or not set(tags) <= set(TAGS):
            raise ValueError(f"bad tags {tags} on {fact['text']!r}")
        rows.append(
            {
                "id": fact_id(fact["text"]),
                "type": "fact",
                "source": "facts-bank",
                "source_url": fact.get("source_url"),
                "payload": {"text": fact["text"]},
                "tags": tags,
                "active": True,
            }
        )
    return rows


async def seed(session: AsyncSession) -> int:
    rows = load_bank()
    stmt = insert(Content).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"], set_={"tags": stmt.excluded.tags, "payload": stmt.excluded.payload}
    )
    await session.execute(stmt)
    # Placeholder cards from earlier dev seeds are retired in favour of the real bank.
    await session.execute(update(Content).where(Content.source == "dev-seed").values(active=False))
    return len(rows)
