"""API process entry point (REST + WebSocket).

Run locally:  uv run uvicorn orbit.main:app --reload
"""

import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from arq.connections import RedisSettings
from arq.worker import Worker, create_worker
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from orbit.core import health
from orbit.core.auth import TokenVerifier
from orbit.core.config import Settings, get_settings
from orbit.core.db import create_engine, create_sessionmaker
from orbit.core.jobs import JobQueue, LazyArqJobQueue
from orbit.core.logging import configure_logging
from orbit.core.observability import init_sentry
from orbit.core.openapi import install_openapi
from orbit.core.realtime import ConnectionManager, RedisFanout
from orbit.core.redis import create_redis
from orbit.modules.accounts.router import router as accounts_router
from orbit.modules.game.router import router as game_router
from orbit.modules.graph.driver import create_driver, ensure_schema
from orbit.modules.graph.router import router as graph_router
from orbit.modules.privacy.router import router as privacy_router
from orbit.modules.rooms.router import router as rooms_router
from orbit.modules.rooms.ws import router as ws_router

log = structlog.get_logger("orbit.api")


async def _start_worker(settings: Settings) -> tuple[Worker, asyncio.Task[None]]:
    """The arq worker as a background task of this process (RUN_WORKER_IN_PROCESS)."""
    from orbit.worker import WorkerSettings

    worker = create_worker(
        WorkerSettings,
        handle_signals=False,
        redis_settings=RedisSettings.from_dsn(settings.redis_url),
        ctx={"settings": settings},
    )
    task = asyncio.create_task(worker.async_run(), name="arq-worker")
    return worker, task


async def _stop_worker(worker: Worker, task: asyncio.Task[None]) -> None:
    # close() cancels running jobs (arq retries them later), then runs the worker's on_shutdown.
    with contextlib.suppress(asyncio.CancelledError):
        await worker.close()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def create_app(
    settings: Settings | None = None,
    *,
    token_verifier: TokenVerifier | None = None,
    jobs: JobQueue | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.is_production)
    init_sentry(settings, component="api")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Clients connect lazily, so startup succeeds even if a dependency is briefly down;
        # /health/ready reports it.
        engine = create_engine(settings.database_url)
        app.state.sessionmaker = create_sessionmaker(engine)
        app.state.redis = create_redis(settings.redis_url)
        own_jobs = LazyArqJobQueue(settings.redis_url) if jobs is None else None
        app.state.jobs = jobs or own_jobs
        # Realtime: this process's sockets + one Redis subscription delivering room events.
        app.state.connections = ConnectionManager()
        fanout = RedisFanout(app.state.redis, app.state.connections)
        fanout.start()
        app.state.neo4j = create_driver(
            settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password.get_secret_value()
        )
        try:
            await ensure_schema(app.state.neo4j)
        except Exception:  # Neo4j down at boot: the graph rebuilds from Postgres later
            log.exception("api.neo4j_schema_failed")
        worker = await _start_worker(settings) if settings.run_worker_in_process else None
        log.info("api.startup", env=settings.app_env, worker_in_process=worker is not None)
        try:
            yield
        finally:
            if worker is not None:
                await _stop_worker(*worker)
            await fanout.stop()
            await app.state.neo4j.close()
            if own_jobs is not None:
                await own_jobs.close()
            await app.state.redis.aclose()
            await engine.dispose()
            log.info("api.shutdown")

    app = FastAPI(
        title="Orbit API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.token_verifier = token_verifier or TokenVerifier.from_jwks_url(
        settings.auth_jwks_url, issuer=settings.auth_issuer, audience=settings.token_audience
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request.failed", method=request.method, path=request.url.path)
            raise
        response.headers["x-request-id"] = request_id
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round((time.perf_counter() - start) * 1000, 1),
        )
        return response

    app.include_router(health.router)
    app.include_router(accounts_router)
    app.include_router(rooms_router)
    app.include_router(game_router)
    app.include_router(graph_router)
    app.include_router(privacy_router)
    app.include_router(ws_router)
    install_openapi(app)
    return app


app = create_app()
