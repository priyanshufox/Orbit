"""Background jobs: a thin seam over arq so services can enqueue work and tests can record it.

The worker (`orbit.worker`) registers the job functions by name.
"""

from datetime import datetime
from typing import Annotated, Any, Protocol

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import Depends, Request


class JobQueue(Protocol):
    async def enqueue(
        self,
        name: str,
        *args: Any,
        job_id: str | None = None,
        defer_until: datetime | None = None,
    ) -> None: ...


class ArqJobQueue:
    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue(
        self,
        name: str,
        *args: Any,
        job_id: str | None = None,
        defer_until: datetime | None = None,
    ) -> None:
        # A repeated job_id is a no-op in arq, which makes "end this round" safe to request twice.
        await self._redis.enqueue_job(name, *args, _job_id=job_id, _defer_until=defer_until)


class LazyArqJobQueue:
    """Connects to Redis on first use, so the API boots (and reports itself not ready) even
    when Redis is briefly down."""

    def __init__(self, redis_url: str) -> None:
        self._settings = RedisSettings.from_dsn(redis_url)
        self._pool: ArqRedis | None = None

    async def enqueue(
        self,
        name: str,
        *args: Any,
        job_id: str | None = None,
        defer_until: datetime | None = None,
    ) -> None:
        if self._pool is None:
            self._pool = await create_pool(self._settings)
        await ArqJobQueue(self._pool).enqueue(name, *args, job_id=job_id, defer_until=defer_until)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()


class RecordingJobQueue:
    """For tests and scripts: remembers what would have been enqueued."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue(
        self,
        name: str,
        *args: Any,
        job_id: str | None = None,
        defer_until: datetime | None = None,
    ) -> None:
        self.calls.append((name, args, {"job_id": job_id, "defer_until": defer_until}))

    def names(self) -> list[str]:
        return [c[0] for c in self.calls]


def get_jobs(request: Request) -> JobQueue:
    return request.app.state.jobs


JobsDep = Annotated[JobQueue, Depends(get_jobs)]
