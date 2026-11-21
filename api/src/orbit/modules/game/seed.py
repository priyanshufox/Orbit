"""Load the question bank (task 4.1) from data/questions.json. Safe in production; idempotent.

Edit the JSON and reload: existing questions are updated in place (matched by prompt). A
question removed from the file is deactivated, not deleted, so past answers stay valid.
"""

import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.game.models import QUESTION_KINDS, Question

BANK = Path(__file__).parent / "data" / "questions.json"


def question_id(prompt: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"orbit-question:{prompt}")


def load_bank(path: Path = BANK) -> list[dict[str, Any]]:
    rows = []
    for q in json.loads(path.read_text()):
        if q["kind"] not in QUESTION_KINDS:
            raise ValueError(f"bad kind in {q['prompt']!r}")
        if q["kind"] == "slider":
            options = {"min_label": q["min_label"], "max_label": q["max_label"]}
        else:
            if len(q["choices"]) < 2:
                raise ValueError(f"needs 2+ choices: {q['prompt']!r}")
            options = {"choices": q["choices"]}
        rows.append(
            {
                "id": question_id(q["prompt"]),
                "kind": q["kind"],
                "prompt": q["prompt"],
                "options": options,
                "tags": q.get("tags", []),
                "active": True,
            }
        )
    return rows


async def seed(session: AsyncSession) -> int:
    rows = load_bank()
    stmt = insert(Question).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "kind": stmt.excluded.kind,
            "options": stmt.excluded.options,
            "tags": stmt.excluded.tags,
            "active": True,
        },
    ).returning(Question.id)
    await session.execute(stmt)
    keep = [r["id"] for r in rows]
    await session.execute(update(Question).where(Question.id.not_in(keep)).values(active=False))
    return len(rows)
