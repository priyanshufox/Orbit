from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.accounts.models import User, UserRoot
from orbit.modules.content.models import Content
from orbit.modules.game.models import Question
from orbit.seed import run_all


async def test_seed_loads_expected_rows_and_is_idempotent(db: AsyncSession) -> None:
    first = await run_all(db)
    second = await run_all(db)

    assert first == {"users": 5, "questions": 30, "content": 100}
    # Users are inserted once; the banks are re-applied (upserted) every time.
    assert second == {"users": 0, "questions": 30, "content": 100}

    async def n(model: type) -> int:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()

    assert await n(User) == 5
    assert await n(Question) == 30
    assert await n(Content) == 100
    # dev5 has no roots, to exercise the "signal skipped" path in scoring.
    roots_per_user = (await db.execute(select(UserRoot.user_id).group_by(UserRoot.user_id))).all()
    assert len(roots_per_user) == 4


def test_banks_are_valid() -> None:
    from orbit.modules.content.seed import load_bank as facts
    from orbit.modules.game.seed import load_bank as questions

    qs, fs = questions(), facts()
    assert len(qs) >= 30
    assert len(fs) >= 100
    assert len({q["id"] for q in qs}) == len(qs)
    assert len({f["id"] for f in fs}) == len(fs)
    assert {q["kind"] for q in qs} == {"single", "multi", "slider"}
