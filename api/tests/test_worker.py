import asyncio

from orbit.worker import WorkerSettings, ping


def test_worker_registers_jobs() -> None:
    # arq refuses to start with no functions or cron jobs.
    assert WorkerSettings.functions or WorkerSettings.cron_jobs


def test_ping_job() -> None:
    assert asyncio.run(ping({"job_id": "t1"})) == "pong"
