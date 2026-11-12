"""Redis client for the API process. The worker uses arq's own connection (`ctx["redis"]`)."""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis


def create_redis(url: str) -> Redis:
    return Redis.from_url(url, decode_responses=True)


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


RedisDep = Annotated[Redis, Depends(get_redis)]
