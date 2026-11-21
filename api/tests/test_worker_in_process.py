"""RUN_WORKER_IN_PROCESS: the API runs the arq worker itself (free hosts without workers)."""

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI

from orbit.core.auth import TokenVerifier
from orbit.core.config import Settings
from orbit.main import create_app


async def test_api_runs_jobs_when_worker_is_in_process(
    test_settings: Settings, token_verifier: TokenVerifier
) -> None:
    settings = test_settings.model_copy(update={"run_worker_in_process": True})
    app: FastAPI = create_app(settings, token_verifier=token_verifier)
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        async with app.router.lifespan_context(app):
            job = await pool.enqueue_job("ping")
            assert job is not None
            assert await job.result(timeout=10) == "pong"
    finally:
        await pool.aclose()
