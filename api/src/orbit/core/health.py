"""Liveness (`/health`) and readiness (`/health/ready`) endpoints."""

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from orbit.core.config import SettingsDep
from orbit.core.db import SessionDep
from orbit.core.redis import RedisDep

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok"]
    env: str


class Readiness(BaseModel):
    status: Literal["ok", "degraded"]
    postgres: bool
    redis: bool


@router.get("/health")
def health(settings: SettingsDep) -> Health:
    """The process is up. Does not touch dependencies."""
    return Health(status="ok", env=settings.app_env)


@router.get("/health/ready")
async def ready(session: SessionDep, redis: RedisDep, response: Response) -> Readiness:
    """Postgres and Redis answer. Returns 503 if either is down."""
    try:
        postgres_ok = (await session.execute(text("select 1"))).scalar() == 1
    except Exception:
        postgres_ok = False
    try:
        redis_ok = bool(await redis.ping())
    except Exception:
        redis_ok = False
    ok = postgres_ok and redis_ok
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Readiness(status="ok" if ok else "degraded", postgres=postgres_ok, redis=redis_ok)
