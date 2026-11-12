"""API process entry point (REST + WebSocket).

Run locally:  uv run uvicorn orbit.main:app --reload
"""

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from orbit.core import health
from orbit.core.auth import TokenVerifier
from orbit.core.config import Settings, get_settings
from orbit.core.db import create_engine, create_sessionmaker
from orbit.core.logging import configure_logging
from orbit.core.openapi import install_openapi
from orbit.core.redis import create_redis
from orbit.modules.accounts.router import router as accounts_router

log = structlog.get_logger("orbit.api")


def create_app(
    settings: Settings | None = None, *, token_verifier: TokenVerifier | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.is_production)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Clients connect lazily, so startup succeeds even if a dependency is briefly down;
        # /health/ready reports it.
        engine = create_engine(settings.database_url)
        app.state.sessionmaker = create_sessionmaker(engine)
        app.state.redis = create_redis(settings.redis_url)
        log.info("api.startup", env=settings.app_env)
        try:
            yield
        finally:
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
    install_openapi(app)
    return app


app = create_app()
