"""Load dev seed data into the configured database. Safe to run repeatedly.

Run:  uv run python -m orbit.seed
Each module seeds its own tables (ADR 0001 rule 2); this only calls them in order.
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core.config import get_settings
from orbit.core.db import create_engine
from orbit.modules.accounts import seed as accounts_seed
from orbit.modules.content import seed as content_seed
from orbit.modules.game import seed as game_seed

SEEDERS = {
    "users": accounts_seed.seed,
    "questions": game_seed.seed,
    "content": content_seed.seed,
}


async def run_all(session: AsyncSession) -> dict[str, int]:
    """Insert whatever is missing. Returns rows inserted per seeder."""
    return {name: await seeder(session) for name, seeder in SEEDERS.items()}


async def main() -> None:
    settings = get_settings()
    if settings.is_production:
        raise SystemExit("Refusing to load dev seed data into production.")
    engine = create_engine(settings.database_url)
    async with AsyncSession(engine) as session, session.begin():
        inserted = await run_all(session)
    await engine.dispose()
    print("Inserted:", ", ".join(f"{n} {k}" for k, n in inserted.items()))


if __name__ == "__main__":
    asyncio.run(main())
