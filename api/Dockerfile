# Orbit API + worker: one image, two commands (ADR 0001).
#   API:    docker run IMAGE                       (uvicorn, port 8000)
#   Worker: docker run IMAGE arq orbit.worker.WorkerSettings
#   Migrate before each release: docker run IMAGE alembic upgrade head
#   Or all in one (hosts without a release step): docker run IMAGE sh start.sh
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini start.sh ./
RUN uv sync --locked --no-dev

FROM python:3.13-slim
RUN useradd --create-home --uid 10001 orbit
WORKDIR /app
COPY --from=build --chown=orbit /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 APP_ENV=production
USER orbit
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "orbit.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
