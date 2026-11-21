"""Load seed data. Safe to run repeatedly.

  uv run python -m orbit.seed          # dev: 5 dev users + question bank + facts bank
  uv run python -m orbit.seed --banks  # any environment: question and facts banks only

Each module seeds its own tables (ADR 0001 rule 2); this only calls them in order.
"""

import argparse
import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from orbit.core.config import get_settings
from orbit.core.db import create_engine
from orbit.modules.accounts import seed as accounts_seed
from orbit.modules.content import seed as content_seed
from orbit.modules.game import seed as game_seed

Seeder = Callable[[AsyncSession], Awaitable[int]]

BANKS: dict[str, Seeder] = {"questions": game_seed.seed, "content": content_seed.seed}
DEV: dict[str, Seeder] = {"users": accounts_seed.seed, **BANKS}


async def run_all(session: AsyncSession, seeders: dict[str, Seeder] = DEV) -> dict[str, int]:
    """Returns rows inserted (users) or loaded (banks) per seeder."""
    return {name: await seeder(session) for name, seeder in seeders.items()}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--banks", action="store_true", help="question and facts banks only")
    args = parser.parse_args()
    settings = get_settings()
    if settings.is_production and not args.banks:
        raise SystemExit("Refusing to load dev users into production; use --banks.")
    engine = create_engine(settings.database_url)
    async with AsyncSession(engine) as session, session.begin():
        result = await run_all(session, BANKS if args.banks else DEV)
    await engine.dispose()
    print("Loaded:", ", ".join(f"{n} {k}" for k, n in result.items()))


if __name__ == "__main__":
    asyncio.run(main())
