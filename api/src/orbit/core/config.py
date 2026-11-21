"""App settings, read from environment variables and the repo-root `.env` file."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# api/src/orbit/core/config.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    web_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://orbit:orbit@localhost:5432/orbit"
    redis_url: str = "redis://localhost:6379/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("orbit-dev-password")

    # Sign-in tokens come from Better Auth in the web app (task 2.4).
    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_issuer: str = "http://localhost:3000"
    auth_audience: str | None = None  # defaults to the issuer, as Better Auth does

    # --- Rooms and rounds (design: Room lifecycle) ---
    round_seconds: int = 300
    room_ttl_hours: int = 48
    room_member_cap: int = 20
    answer_grace_seconds: int = 15  # late network writes accepted after the timer
    # --- Abuse limits (task 10.2) ---
    joins_per_minute: int = 10
    rooms_per_host_per_day: int = 10
    # --- Scoring knobs, tuned in playtests (task 10.6) ---
    edge_threshold: float = 0.4
    edges_always_shown: int = 3
    # JSON in .env, e.g. REACTION_VALUES='{"like": 1, "laugh": 1, "send": 1.5, "skip": -1}'
    reaction_values: dict[str, float] = {"like": 1.0, "laugh": 1.0, "send": 1.5, "skip": -1.0}
    graph_use_gds: bool = True  # Neo4j GDS Louvain when installed; Python fallback otherwise

    # --- Content pipeline (Phase 9); each source is skipped when its key is missing ---
    anthropic_api_key: SecretStr | None = None
    content_llm_model: str = "claude-opus-5-5"
    imgflip_username: str | None = None
    imgflip_password: SecretStr | None = None
    newsdata_api_key: SecretStr | None = None
    memes_per_day: int = 20
    news_per_day: int = 50

    # --- Observability (task 10.3) ---
    sentry_dsn: str | None = None
    # GET /health/metrics needs header X-Metrics-Token with this value; unset = endpoint off.
    metrics_token: SecretStr | None = None

    log_level: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def token_audience(self) -> str:
        return self.auth_audience or self.auth_issuer


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Use in endpoints: `def handler(settings: SettingsDep)`. create_app() overrides get_settings,
# so tests that pass their own Settings see them here too.
SettingsDep = Annotated[Settings, Depends(get_settings)]
