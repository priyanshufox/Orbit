"""Fixed-window rate limits in Redis (task 10.2)."""

from fastapi import HTTPException, status
from redis.asyncio import Redis


async def allow(redis: Redis, key: str, *, limit: int, window_seconds: int) -> bool:
    """Count one hit on `key`; False once more than `limit` hits land in the window."""
    full_key = f"ratelimit:{key}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(full_key)
        pipe.expire(full_key, window_seconds, nx=True)
        count, _ = await pipe.execute()
    return int(count) <= limit


async def enforce(redis: Redis, key: str, *, limit: int, window_seconds: int) -> None:
    if not await allow(redis, key, limit=limit, window_seconds=window_seconds):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            headers={"Retry-After": str(window_seconds)},
        )
