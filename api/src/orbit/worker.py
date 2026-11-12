"""Worker process entry point (arq jobs: round timer, scoring, expiry, content curator).

Run locally:  uv run arq orbit.worker.WorkerSettings
Modules register their jobs in FUNCTIONS / CRON_JOBS as they land.
"""

from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings

from orbit.core.config import get_settings
from orbit.core.logging import configure_logging

log = structlog.get_logger("orbit.worker")


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job: proves the worker picks up and runs jobs from Redis."""
    log.info("job.ping", job_id=ctx.get("job_id"))
    return "pong"


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.is_production)
    log.info("worker.startup", env=settings.app_env)


async def on_shutdown(ctx: dict[str, Any]) -> None:
    log.info("worker.shutdown")


FUNCTIONS: list[Any] = [ping]
CRON_JOBS: list[Any] = []


class WorkerSettings:
    functions: ClassVar[list[Any]] = FUNCTIONS
    cron_jobs: ClassVar[list[Any]] = CRON_JOBS
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
