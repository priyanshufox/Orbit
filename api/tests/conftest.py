"""Shared fixtures. DB and Redis tests need the local infra (or CI service containers).

Tests use their own database, `<name>_test`, rebuilt from the Alembic migrations once per run,
and Redis database 1. Each `db` test runs inside a transaction that is rolled back.
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from redis.asyncio import Redis
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from orbit.core.config import Settings

API_DIR = Path(__file__).resolve().parents[1]


def _test_settings() -> Settings:
    base = Settings()
    db_url = make_url(base.database_url)
    db_url = db_url.set(database=f"{db_url.database}_test")
    redis_url = base.redis_url.rsplit("/", 1)[0] + "/1"
    return Settings(
        _env_file=None,
        app_env="test",
        database_url=db_url.render_as_string(hide_password=False),
        redis_url=redis_url,
    )


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return _test_settings()


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


async def _recreate_database(url: str) -> None:
    target = make_url(url)
    admin = create_async_engine(
        target.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=None
    )
    async with admin.connect() as conn:
        await conn.execute(text(f'drop database if exists "{target.database}" with (force)'))
        await conn.execute(text(f'create database "{target.database}"'))
    await admin.dispose()


@pytest.fixture(scope="session")
def migrated_db(test_settings: Settings) -> Iterator[str]:
    """A fresh test database at the latest migration."""
    url = test_settings.database_url
    asyncio.run(_recreate_database(url))
    command.upgrade(alembic_config(url), "head")
    yield url


@pytest.fixture(scope="session")
async def engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(migrated_db)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session whose work is rolled back after the test, even if the test commits."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def redis(test_settings: Settings) -> AsyncIterator[Redis]:
    client = Redis.from_url(test_settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()
