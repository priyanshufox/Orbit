"""Liveness (`/health`) and readiness (`/health/ready`) endpoints."""

import hmac
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from orbit.core.config import SettingsDep
from orbit.core.db import SessionDep
from orbit.core.realtime import ConnectionManager
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


class Metrics(BaseModel):
    rooms_by_state: dict[str, int]
    members_in_open_rooms: int
    sockets_on_this_process: int


@router.get("/health/metrics", include_in_schema=False)
async def metrics(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    x_metrics_token: str | None = Header(default=None),
) -> Metrics:
    """Basic per-room metrics for dashboards (task 10.3). Counts only, no personal data."""
    expected = settings.metrics_token.get_secret_value() if settings.metrics_token else None
    if not expected or not x_metrics_token or not hmac.compare_digest(expected, x_metrics_token):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    by_state = dict(
        (await session.execute(text("select state, count(*) from rooms group by state"))).all()
    )
    members = await session.scalar(
        text(
            "select count(*) from room_members m "
            "join rooms r on r.code = m.room_code where r.state <> 'EXPIRED'"
        )
    )
    manager: ConnectionManager | None = getattr(request.app.state, "connections", None)
    return Metrics(
        rooms_by_state={str(k): int(v) for k, v in by_state.items()},
        members_in_open_rooms=int(members or 0),
        sockets_on_this_process=manager.count() if manager else 0,
    )
