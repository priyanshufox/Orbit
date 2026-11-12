from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orbit.modules.accounts.models import User, UserRoot
from orbit.modules.content.models import Content
from orbit.modules.game.models import Question
from orbit.seed import run_all


async def test_seed_loads_expected_rows_and_is_idempotent(db: AsyncSession) -> None:
    first = await run_all(db)
    second = await run_all(db)

    assert first == {"users": 5, "questions": 15, "content": 40}
    assert second == {"users": 0, "questions": 0, "content": 0}

    async def n(model: type) -> int:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()

    assert await n(User) == 5
    assert await n(Question) == 15
    assert await n(Content) == 40
    # dev5 has no roots, to exercise the "signal skipped" path in scoring.
    roots_per_user = (await db.execute(select(UserRoot.user_id).group_by(UserRoot.user_id))).all()
    assert len(roots_per_user) == 4
