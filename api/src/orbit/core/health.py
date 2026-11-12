"""Liveness endpoint. Readiness checks (database, Redis, Neo4j) are added as those clients land."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from orbit.core.config import SettingsDep

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok"]
    env: str


@router.get("/health")
def health(settings: SettingsDep) -> Health:
    return Health(status="ok", env=settings.app_env)
