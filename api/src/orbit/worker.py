"""Worker process (arq): round timer, scoring + reveal, room expiry, content curation.

Run locally:  uv run arq orbit.worker.WorkerSettings
"""

from datetime import UTC, datetime
from typing import Any, ClassVar

import structlog
from arq import cron
from arq.connections import RedisSettings

from orbit import pipeline
from orbit.core import events
from orbit.core.config import get_settings
from orbit.core.db import create_engine, create_sessionmaker
from orbit.core.jobs import ArqJobQueue
from orbit.core.logging import configure_logging
from orbit.core.observability import init_sentry
from orbit.modules.graph.driver import create_driver, ensure_schema
from orbit.modules.rooms import service as rooms

log = structlog.get_logger("orbit.worker")


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job: proves the worker picks up and runs jobs from Redis."""
    log.info("job.ping", job_id=ctx.get("job_id"))
    return "pong"


async def end_round(ctx: dict[str, Any], code: str) -> bool:
    """Deferred to the round's `ends_at` (task 4.9). A no-op if everyone already finished."""
    async with ctx["sessionmaker"]() as session:
        return await rooms.end_round(session, ctx["redis"], ArqJobQueue(ctx["redis"]), code)


async def score_room(ctx: dict[str, Any], code: str) -> bool:
    """Score every pair, project to Neo4j, reveal (Phases 5-6)."""
    async with ctx["sessionmaker"]() as session:
        return await pipeline.reveal(session, ctx["redis"], ctx["neo4j"], code, ctx["settings"])


async def warn_room_closing(ctx: dict[str, Any], code: str) -> None:
    """One hour before deletion (task 8.3)."""
    async with ctx["sessionmaker"]() as session:
        room = await rooms.get_room(session, code)
    if room is not None:
        await events.publish(ctx["redis"], code, events.RoomClosing(expires_at=room.expires_at))


async def expire_rooms(ctx: dict[str, Any]) -> list[str]:
    """Hourly (task 8.2): snapshot, delete from Postgres and Neo4j, audit."""
    async with ctx["sessionmaker"]() as session:
        return await pipeline.expire_due(session, ctx["neo4j"], ctx["settings"])


async def curate_content(ctx: dict[str, Any]) -> dict[str, int]:
    """Daily (Phase 9): fetch, tag, moderate and store new cards."""
    from orbit.modules.content import curator

    async with ctx["sessionmaker"]() as session:
        return await curator.run(session, ctx["settings"])


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.is_production)
    init_sentry(settings, component="worker")
    ctx["settings"] = settings
    ctx["engine"] = create_engine(settings.database_url)
    ctx["sessionmaker"] = create_sessionmaker(ctx["engine"])
    ctx["neo4j"] = create_driver(
        settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password.get_secret_value()
    )
    try:
        await ensure_schema(ctx["neo4j"])
    except Exception:
        log.exception("worker.neo4j_schema_failed")
    log.info("worker.startup", env=settings.app_env, at=datetime.now(UTC).isoformat())


async def on_shutdown(ctx: dict[str, Any]) -> None:
    await ctx["neo4j"].close()
    await ctx["engine"].dispose()
    log.info("worker.shutdown")


FUNCTIONS: list[Any] = [
    ping,
    end_round,
    score_room,
    warn_room_closing,
    expire_rooms,
    curate_content,
]
CRON_JOBS: list[Any] = [
    cron(expire_rooms, minute=5, unique=True),  # hourly
    cron(curate_content, hour=3, minute=30, unique=True),  # daily, 03:30 UTC (09:00 IST)
]


class WorkerSettings:
    functions: ClassVar[list[Any]] = FUNCTIONS
    cron_jobs: ClassVar[list[Any]] = CRON_JOBS
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 3
