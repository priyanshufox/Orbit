from fastapi.testclient import TestClient

from orbit.core.config import Settings
from orbit.main import create_app


def make_client(**overrides: str) -> TestClient:
    settings = Settings(_env_file=None, **overrides)  # ignore any local .env
    return TestClient(create_app(settings))


def test_health_ok() -> None:
    with make_client(app_env="test") as client:
        res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "env": "test"}


def test_request_id_is_echoed_or_generated() -> None:
    with make_client() as client:
        echoed = client.get("/health", headers={"x-request-id": "abc123"})
        generated = client.get("/health")
    assert echoed.headers["x-request-id"] == "abc123"
    assert len(generated.headers["x-request-id"]) == 32


def test_cors_allows_web_origin_only() -> None:
    with make_client(web_url="http://localhost:3000") as client:
        ok = client.options(
            "/health",
            headers={"origin": "http://localhost:3000", "access-control-request-method": "GET"},
        )
        bad = client.options(
            "/health",
            headers={"origin": "https://evil.example", "access-control-request-method": "GET"},
        )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in bad.headers


def test_ready_when_postgres_and_redis_answer(test_settings: Settings, migrated_db: str) -> None:
    with TestClient(create_app(test_settings)) as client:
        res = client.get("/health/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "postgres": True, "redis": True}


def test_not_ready_when_redis_is_down(test_settings: Settings, migrated_db: str) -> None:
    broken = test_settings.model_copy(update={"redis_url": "redis://localhost:1/0"})
    with TestClient(create_app(broken)) as client:
        res = client.get("/health/ready")
    assert res.status_code == 503
    assert res.json() == {"status": "degraded", "postgres": True, "redis": False}


def test_docs_hidden_in_production() -> None:
    with make_client(app_env="production") as client:
        assert client.get("/docs").status_code == 404
    with make_client(app_env="development") as client:
        assert client.get("/docs").status_code == 200
