"""Dev seed: 40 placeholder fact cards spread over the fixed tag list.

They are clearly labelled placeholders (source "dev-seed"), not real facts; the facts bank
arrives in task 4.2.
"""

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.content.models import Content
from orbit.modules.content.tags import TAGS

DEV_FACT_COUNT = 40


def dev_facts() -> list[dict]:
    rows = []
    for i in range(DEV_FACT_COUNT):
        primary = TAGS[i % len(TAGS)]
        # Every third card gets a second tag so multi-tag decks get exercised.
        tags = [primary] if i % 3 else [primary, TAGS[(i + 4) % len(TAGS)]]
        rows.append(
            {
                "id": uuid5(NAMESPACE_URL, f"orbit-dev-fact:{i}"),
                "type": "fact",
                "source": "dev-seed",
                "payload": {"text": f"Dev fact {i + 1}: placeholder card about {primary}."},
                "tags": tags,
                "active": True,
            }
        )
    return rows


async def seed(session: AsyncSession) -> int:
    res = await session.execute(insert(Content).values(dev_facts()).on_conflict_do_nothing())
    return res.rowcount
