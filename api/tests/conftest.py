"""Shared fixtures. DB and Redis tests need the local infra (or CI service containers).

Tests use their own database, `<name>_test`, rebuilt from the Alembic migrations once per run,
and Redis database 1. Each `db` test runs inside a transaction that is rolled back.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import insert, make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from orbit.core.auth import TokenVerifier
from orbit.core.config import Settings
from orbit.core.db import get_session
from orbit.core.jobs import RecordingJobQueue
from orbit.core.realtime import ConnectionManager
from orbit.main import create_app
from orbit.modules.accounts.models import User, auth_user
from orbit.modules.graph.driver import GraphDriver, create_driver, ensure_schema

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
    await client.flushdb()  # rate-limit counters and kick lists from earlier tests
    yield client
    await client.aclose()


# --- Sign-in ---------------------------------------------------------------------------------

ISSUER = "http://web.test"


class _StaticKeys:
    """Stands in for the web app's /api/auth/jwks: one Ed25519 key, as Better Auth uses."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._jwk = jwt.PyJWK.from_dict(
            {
                **jwt.algorithms.OKPAlgorithm.to_jwk(private_key.public_key(), as_dict=True),
                "kid": "test-key",
                "alg": "EdDSA",
            }
        )

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        if jwt.get_unverified_header(token).get("kid") != "test-key":
            raise jwt.PyJWKClientError("unknown kid")
        return self._jwk


_SIGNING_KEY = Ed25519PrivateKey.generate()

TokenFactory = Callable[..., str]


@pytest.fixture(scope="session")
def make_token() -> TokenFactory:
    """`make_token(user_id, email, **claims)` -> a JWT shaped like Better Auth's."""

    def factory(
        user_id: UUID, email: str, *, key: Ed25519PrivateKey | None = None, **claims: Any
    ) -> str:
        now = int(time.time())
        payload = {
            "sub": str(user_id),
            "email": email,
            "iss": ISSUER,
            "aud": ISSUER,
            "iat": now,
            "exp": now + 900,
            **claims,
        }
        return jwt.encode(
            payload, key or _SIGNING_KEY, algorithm="EdDSA", headers={"kid": "test-key"}
        )

    return factory


@pytest.fixture(scope="session")
def token_verifier() -> TokenVerifier:
    return TokenVerifier(_StaticKeys(_SIGNING_KEY), issuer=ISSUER, audience=ISSUER)


async def make_identity(db: AsyncSession, email: str, name: str = "") -> UUID:
    """What Better Auth writes when someone signs in for the first time."""
    user_id = uuid4()
    await db.execute(
        insert(auth_user).values(id=user_id, email=email, name=name, emailVerified=True)
    )
    return user_id


@pytest.fixture(scope="session")
async def neo4j(test_settings: Settings) -> AsyncIterator[GraphDriver]:
    driver = create_driver(
        test_settings.neo4j_uri,
        test_settings.neo4j_user,
        test_settings.neo4j_password.get_secret_value(),
    )
    await ensure_schema(driver)
    yield driver
    await driver.close()


@pytest.fixture
def jobs() -> RecordingJobQueue:
    return RecordingJobQueue()


@pytest.fixture
def app(
    test_settings: Settings,
    token_verifier: TokenVerifier,
    db: AsyncSession,
    redis: Redis,
    neo4j: GraphDriver,
    jobs: RecordingJobQueue,
) -> FastAPI:
    """The API wired to the rolled-back test session, test Redis/Neo4j, a recording job queue
    and the test signing key. (Lifespan doesn't run under ASGITransport, so state is set here.)"""
    application = create_app(test_settings, token_verifier=token_verifier, jobs=jobs)

    async def _session() -> AsyncIterator[AsyncSession]:
        yield db

    application.dependency_overrides[get_session] = _session
    application.state.redis = redis
    application.state.jobs = jobs
    application.state.neo4j = neo4j
    application.state.connections = ConnectionManager()
    return application


async def make_player(
    db: AsyncSession, make_token: TokenFactory, name: str
) -> tuple[UUID, dict[str, str]]:
    """An adult who passed the age gate and consented, plus auth headers for them."""
    email = f"{name.lower()}-{uuid4().hex[:8]}@orbit.test"
    user_id = await make_identity(db, email, name)
    from datetime import UTC, datetime

    db.add(
        User(
            id=user_id,
            email=email,
            name=name,
            birth_year=1999,
            is_adult=True,
            consented_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return user_id, {"Authorization": f"Bearer {make_token(user_id, email, name=name)}"}


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.test") as c:
        yield c


@pytest.fixture
async def banks(db: AsyncSession) -> None:
    """The real question and facts banks, inside the test's rolled-back transaction."""
    from orbit.modules.content import seed as content_seed
    from orbit.modules.game import seed as game_seed

    await game_seed.seed(db)
    await content_seed.seed(db)
